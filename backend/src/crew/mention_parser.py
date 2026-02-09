"""Mention parser for identifying mentioned roles in Lead Planner output.

This module parses the Lead Planner's text to identify which roles are being
addressed or asked to respond.
"""

import re
from typing import NamedTuple


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


def parse_mentioned_roles(text: str) -> list[str]:
    """Parse text to identify mentioned roles.

    The function checks for:
    1. Direct role name mentions
    2. Role alias mentions
    3. Pattern-based mentions (e.g., "系统策划，你觉得...")

    Args:
        text: The text to parse (typically Lead Planner's output).

    Returns:
        List of mentioned role names. Returns empty list if no specific
        roles are mentioned (which typically means all roles should respond).
    """
    mentioned: set[str] = set()

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


def parse_speaker_block(text: str) -> list[str] | None:
    """Parse explicit speaker assignment block from Lead Planner output.

    Looks for a ```speakers block that lists which roles should speak next.

    Args:
        text: The Lead Planner's output text.

    Returns:
        List of role names if block found and valid, None otherwise.
    """
    match = re.search(r"```speakers\s*\n(.+?)\n```", text, re.DOTALL)
    if not match:
        return None

    raw = match.group(1).strip()
    # Split by comma, Chinese comma, or newline
    candidates = re.split(r"[,，\n]", raw)

    # Build alias → role mapping
    alias_map: dict[str, str] = {}
    for p in ROLE_PATTERNS:
        alias_map[p.role] = p.role
        for alias in p.aliases:
            alias_map[alias] = p.role

    result: list[str] = []
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        if candidate in alias_map:
            role = alias_map[candidate]
            if role not in result:
                result.append(role)

    return result if result else None


def parse_next_speakers(text: str) -> list[str]:
    """Parse who should speak next from Lead Planner's output.

    Tries structured ```speakers block first, falls back to mention-based parsing.

    Args:
        text: The Lead Planner's output text.

    Returns:
        List of role names that should respond. Empty list means all respond.
    """
    # Try structured block first
    speakers = parse_speaker_block(text)
    if speakers is not None:
        return speakers

    # Fallback to mention-based parsing
    return parse_mentioned_roles(text)


def get_all_roles() -> list[str]:
    """Get all defined role names.

    Returns:
        List of all role names.
    """
    return [pattern.role for pattern in ROLE_PATTERNS]
