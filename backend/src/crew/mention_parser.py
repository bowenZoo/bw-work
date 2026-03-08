"""Mention parser for identifying mentioned roles in Lead Planner output.

This module parses the Lead Planner's text to identify which roles are being
addressed or asked to respond.
"""

import re
from typing import NamedTuple

# Special role constant: when found in a speakers block, the discussion
# pauses and waits for the human producer to send a message.
PRODUCER_ROLE = "制作人"


class MentionPattern(NamedTuple):
    """Role mention pattern configuration.

    Attributes:
        role: Standard role name (e.g., "系统策划").
        aliases: Alternative names for the role.
        patterns: Regex patterns that indicate a mention.
    """

    role: str
    aliases: list[str]
    patterns: list[str]


# Role mention patterns configuration
ROLE_PATTERNS = [
    MentionPattern(
        role="系统策划",
        aliases=["系统", "技术", "架构"],
        patterns=[
            r"系统策划[，,]",
            r"请系统策划",
            r"系统(?:策划)?(?:能否|可以|来)",
            r"请从系统(?:角度|层面)",
            r"系统(?:策划)?(?:你|请)",
        ],
    ),
    MentionPattern(
        role="数值策划",
        aliases=["数值", "平衡", "经济"],
        patterns=[
            r"数值策划[，,]",
            r"请数值策划",
            r"数值(?:策划)?(?:能否|可以|来)",
            r"请从数值(?:角度|层面)",
            r"数值(?:策划)?(?:你|请)",
            r"平衡(?:性|方面)",
        ],
    ),
    MentionPattern(
        role="玩家代言人",
        aliases=["玩家", "用户", "体验"],
        patterns=[
            r"玩家代言人[，,]",
            r"请玩家代言人",
            r"玩家(?:代言人)?(?:能否|可以|来)",
            r"从玩家角度",
            r"用户(?:体验)?(?:方面|角度)",
            r"玩家(?:代言人)?(?:你|请)",
            r"体验(?:方面|角度)",
        ],
    ),
]


def parse_mentioned_roles(
    text: str,
    known_roles: list[str] | None = None,
) -> list[str]:
    """Parse text to identify mentioned roles.

    The function checks for:
    1. Direct role name mentions
    2. Role alias mentions
    3. Pattern-based mentions (e.g., "系统策划，你觉得...")

    When known_roles is provided, only those roles (plus static roles that are
    also in known_roles) will be returned. Dynamic roles are matched by direct
    name occurrence in the text.

    Args:
        text: The text to parse (typically Lead Planner's output).
        known_roles: Optional list of role display names present in the current
            discussion. When provided, only these roles are eligible for return.

    Returns:
        List of mentioned role names. Returns empty list if no specific
        roles are mentioned (which typically means all roles should respond).
    """
    mentioned: set[str] = set()

    if known_roles:
        # Dynamic roles: accept any known_role whose name appears directly in text
        for role in known_roles:
            if role in text:
                mentioned.add(role)
        # Static alias patterns: only apply for roles that are in known_roles
        for pattern in ROLE_PATTERNS:
            if pattern.role not in known_roles:
                continue
            if pattern.role in mentioned:
                continue
            for alias in pattern.aliases:
                if alias in text:
                    mentioned.add(pattern.role)
                    break
            else:
                for regex in pattern.patterns:
                    if re.search(regex, text):
                        mentioned.add(pattern.role)
                        break
    else:
        # Original broad matching (no known_roles filter)
        for pattern in ROLE_PATTERNS:
            # Check direct name
            if pattern.role in text:
                mentioned.add(pattern.role)
                continue
            # Check aliases
            for alias in pattern.aliases:
                if alias in text:
                    mentioned.add(pattern.role)
                    break
            else:
                # Check regex patterns only if no alias matched
                for regex in pattern.patterns:
                    if re.search(regex, text):
                        mentioned.add(pattern.role)
                        break

    return list(mentioned)


def parse_speaker_block(
    text: str,
    known_roles: list[str] | None = None,
) -> list[str] | None:
    """Parse explicit speaker assignment block from Lead Planner output.

    Looks for a ```speakers block that lists which roles should speak next.

    Args:
        text: The Lead Planner's output text.
        known_roles: Optional list of role display names actually present in the
            current discussion. When provided, only these roles (plus 制作人) are
            accepted — any name not in known_roles and not resolvable via the
            static alias map is discarded. This prevents the LLM from naming
            agents that do not exist in the current discussion.

    Returns:
        List of role names if block found and valid, None otherwise.
    """
    match = re.search(r"```speakers\s*\n(.+?)\n```", text, re.DOTALL)
    if not match:
        return None

    raw = match.group(1).strip()
    # Split by comma, Chinese comma, or newline
    candidates = re.split(r"[,，\n]", raw)

    # Build alias → role mapping from static patterns
    alias_map: dict[str, str] = {}
    for p in ROLE_PATTERNS:
        alias_map[p.role] = p.role
        for alias in p.aliases:
            alias_map[alias] = p.role
    # Producer is a special pass-through role (human turn)
    alias_map[PRODUCER_ROLE] = PRODUCER_ROLE

    # Also register every known_role directly so dynamic roles are recognised
    if known_roles:
        for role in known_roles:
            alias_map[role] = role

    result: list[str] = []
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        role = alias_map.get(candidate)
        if role is None:
            continue
        # When known_roles is supplied, drop static-alias roles that are not
        # actually participating in this discussion (except 制作人).
        if known_roles and role != PRODUCER_ROLE and role not in known_roles:
            continue
        if role not in result:
            result.append(role)

    return result if result else None


def parse_next_speakers(
    text: str,
    known_roles: list[str] | None = None,
) -> list[str]:
    """Parse who should speak next from Lead Planner's output.

    Tries structured ```speakers block first, falls back to mention-based parsing.

    Args:
        text: The Lead Planner's output text.
        known_roles: Optional list of role display names present in the
            current discussion. Passed through to sub-parsers to limit results
            to roles that actually exist in the discussion.

    Returns:
        List of role names that should respond. Empty list means all respond.
    """
    # Try structured block first
    speakers = parse_speaker_block(text, known_roles=known_roles)
    if speakers is not None:
        return speakers

    # Fallback to mention-based parsing (also filtered by known_roles)
    return parse_mentioned_roles(text, known_roles=known_roles)


def sanitize_speakers_in_text(
    text: str,
    known_roles: list[str] | None = None,
) -> str:
    """Rewrite the ```speakers block to only contain valid known roles.

    Prevents hallucinated role names from appearing in the displayed text
    while leaving the block parseable for routing. If no valid roles survive
    the filter, the block is removed so mention-based fallback can take over.

    Args:
        text: The Lead Planner's output text.
        known_roles: List of role display names actually present in the
            current discussion. Roles not in this list are removed.

    Returns:
        Text with the speakers block sanitized to only valid roles.
    """
    if not known_roles:
        return text

    pattern = re.compile(r"(```speakers\s*\n)(.+?)(\n```)", re.DOTALL)
    match = pattern.search(text)
    if not match:
        return text

    raw = match.group(2).strip()
    candidates = re.split(r"[,，\n]", raw)

    # Build alias → role mapping (same logic as parse_speaker_block)
    alias_map: dict[str, str] = {}
    for p in ROLE_PATTERNS:
        alias_map[p.role] = p.role
        for alias in p.aliases:
            alias_map[alias] = p.role
    alias_map[PRODUCER_ROLE] = PRODUCER_ROLE
    for role in known_roles:
        alias_map[role] = role

    valid_roles: list[str] = []
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        role = alias_map.get(candidate)
        if role is None:
            continue
        if role != PRODUCER_ROLE and role not in known_roles:
            continue
        if role not in valid_roles:
            valid_roles.append(role)

    if not valid_roles:
        # Remove the invalid block; parse_next_speakers falls back to mention parsing
        return pattern.sub("", text).strip()

    new_content = ", ".join(valid_roles)
    replacement = f"{match.group(1)}{new_content}{match.group(3)}"
    return text[: match.start()] + replacement + text[match.end() :]


def get_all_roles() -> list[str]:
    """Get all defined role names.

    Returns:
        List of all role names.
    """
    return [pattern.role for pattern in ROLE_PATTERNS]


# ── Super Producer (@超级制作人) ──────────────────────────────────────────────

SUPER_PRODUCER_ROLE = "超级制作人"
_SUPER_PRODUCER_TAG = "@超级制作人"


def parse_super_producer_mentions(
    text: str,
    from_agent: str = "",
) -> list[dict]:
    """Extract @超级制作人 question mentions from an agent message.

    Format: @超级制作人：<question>  OR  @超级制作人 <question>
    Each occurrence on its own line produces one decision card.

    Args:
        text: Agent message content.
        from_agent: Role name of the agent who wrote this message.

    Returns:
        List of {"from_agent": str, "question": str} dicts, one per mention.
    """
    questions: list[dict] = []
    # Match @超级制作人 followed by optional ：/: and then the question text up to EOL
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith(_SUPER_PRODUCER_TAG):
            continue
        # Remove the tag and optional delimiter
        after = stripped[len(_SUPER_PRODUCER_TAG):].lstrip("：: \t")
        after = after.strip()
        if len(after) >= 5:
            questions.append({"from_agent": from_agent, "question": after})
    return questions
