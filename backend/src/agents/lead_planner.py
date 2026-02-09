"""Lead Planner Agent - Moderates discussions and makes decisions."""

import re
from enum import Enum
from typing import Any

from src.agents.base import BaseAgent


class DiscussionStatus(str, Enum):
    """Status of the discussion as determined by Lead Planner."""

    CONTINUE = "continue"  # Need more discussion
    SUFFICIENT = "sufficient"  # Discussion is sufficient, move to final decision
    REFINE = "refine"  # Need to refine specific points


def parse_discussion_status(summary: str) -> tuple[DiscussionStatus, list[str]]:
    """Parse the Lead Planner's summary to extract discussion status.

    Args:
        summary: The Lead Planner's round summary output.

    Returns:
        Tuple of (status, questions) where questions are any targeted questions found.
    """
    summary_lower = summary.lower()

    # Check for "discussion sufficient" indicators
    sufficient_patterns = [
        "讨论充分",
        "进入总结阶段",
        "可以总结",
        "已有结论",
        "无需继续",
    ]
    for pattern in sufficient_patterns:
        if pattern in summary_lower:
            return DiscussionStatus.SUFFICIENT, []

    # Extract targeted questions (format: [问题]? → @角色)
    questions: list[str] = []
    question_pattern = r"(.+?)\s*[?？]\s*→\s*@\s*(\S+)"
    matches = re.findall(question_pattern, summary)
    for question, role in matches:
        questions.append(f"{question.strip()}? (→ {role})")

    # If there are targeted questions, need refinement
    if questions:
        return DiscussionStatus.REFINE, questions

    # Default: continue discussion
    return DiscussionStatus.CONTINUE, []


class DecisionPoint:
    """Represents a single decision extracted from the final decision document."""

    def __init__(
        self,
        title: str,
        decision: str,
        rationale: str,
        alternatives: list[str] | None = None,
        related_discussion: str | None = None,
    ):
        self.title = title
        self.decision = decision
        self.rationale = rationale
        self.alternatives = alternatives or []
        self.related_discussion = related_discussion


class VisualConceptRequest:
    """Represents a request for visual concept generation."""

    def __init__(
        self,
        type: str,
        description: str,
    ):
        self.type = type  # e.g., "UI 概念图", "场景概念", "角色设计"
        self.description = description


def parse_visual_requirements(final_document: str) -> list[VisualConceptRequest]:
    """Parse the Lead Planner's final document to extract visual concept requests.

    Args:
        final_document: The final decision document from Lead Planner.

    Returns:
        List of VisualConceptRequest objects.
    """
    requests: list[VisualConceptRequest] = []

    # Look for "需要的视觉概念" section
    visual_section_pattern = r"##\s*\d*\.?\s*需要的视觉概念\s*\n(.*?)(?=\n##|\Z)"
    match = re.search(visual_section_pattern, final_document, re.DOTALL)

    if not match:
        return requests

    section_content = match.group(1)

    # Parse list items with type and description
    # Format: - 图类型：描述内容
    # Or: - 需要什么类型的图（描述）
    item_pattern = r"-\s*(.+?)[：:]\s*(.+?)(?=\n-|\Z)"
    items = re.findall(item_pattern, section_content, re.DOTALL)

    for type_text, desc_text in items:
        type_text = type_text.strip()
        desc_text = desc_text.strip()
        if type_text and desc_text:
            requests.append(VisualConceptRequest(type=type_text, description=desc_text))

    return requests


def parse_agenda_output(output: str) -> list[dict[str, str]]:
    """Parse the Lead Planner's agenda output to extract agenda items.

    Args:
        output: The Lead Planner's agenda output, formatted in the ```agenda block.

    Returns:
        List of dicts with 'title' and 'description' keys.
    """
    items: list[dict[str, str]] = []

    # Try to extract content from ```agenda block first
    agenda_block_match = re.search(r"```agenda\s*\n(.*?)\n```", output, re.DOTALL)
    content = agenda_block_match.group(1) if agenda_block_match else output

    # Match format: N. [标题] - 描述 or N. 标题 - 描述
    # Support both [] wrapped titles and plain titles
    pattern = r"(\d+)\.\s*\[?([^\]\n-]+?)\]?\s*[-—]\s*(.+?)(?=\n\d+\.|\Z)"
    for match in re.finditer(pattern, content, re.DOTALL):
        title = match.group(2).strip()
        description = match.group(3).strip()
        if title:
            items.append({
                "title": title,
                "description": description,
            })

    # Fallback: try simpler format if no items found
    if not items:
        # Match: N. 标题
        simple_pattern = r"(\d+)\.\s*(.+?)(?=\n\d+\.|\Z)"
        for match in re.finditer(simple_pattern, content, re.DOTALL):
            title = match.group(2).strip()
            # Split on dash if present
            if " - " in title:
                parts = title.split(" - ", 1)
                items.append({
                    "title": parts[0].strip().strip("[]"),
                    "description": parts[1].strip() if len(parts) > 1 else "",
                })
            else:
                items.append({
                    "title": title.strip("[]"),
                    "description": "",
                })

    return items


def parse_final_decisions(final_document: str) -> list[DecisionPoint]:
    """Parse the Lead Planner's final decision document to extract decision points.

    Args:
        final_document: The final decision document from Lead Planner.

    Returns:
        List of DecisionPoint objects extracted from the document.
    """
    decisions: list[DecisionPoint] = []

    # Pattern to match decision blocks
    # Looking for: ### 决策点 N: [标题]
    decision_pattern = r"###\s*决策点\s*\d+[：:]\s*(.+?)(?=###\s*决策点|\n##\s|\Z)"
    matches = re.findall(decision_pattern, final_document, re.DOTALL)

    for match in matches:
        # Extract title from the first line
        lines = match.strip().split("\n", 1)
        title = lines[0].strip()
        content = lines[1] if len(lines) > 1 else ""

        # Extract decision
        decision_match = re.search(
            r"\*\*最终决策\*\*[：:]\s*(.+?)(?=\n-|\n\*\*|\Z)",
            content,
            re.DOTALL,
        )
        decision_text = decision_match.group(1).strip() if decision_match else ""

        # Extract rationale
        rationale_match = re.search(
            r"\*\*决策理由\*\*[：:]\s*(.+?)(?=\n-|\n\*\*|\Z)",
            content,
            re.DOTALL,
        )
        rationale = rationale_match.group(1).strip() if rationale_match else ""

        # Extract alternatives
        alternatives: list[str] = []
        alt_section_match = re.search(
            r"\*\*考虑过的替代方案\*\*[：:]?\s*(.+?)(?=\n\*\*|\Z)",
            content,
            re.DOTALL,
        )
        if alt_section_match:
            alt_text = alt_section_match.group(1)
            # Match lines starting with - 方案
            alt_items = re.findall(r"-\s*方案[A-Z]?[：:]\s*(.+?)(?=\n\s*-|\Z)", alt_text, re.DOTALL)
            alternatives = [item.strip() for item in alt_items if item.strip()]

        # Extract related discussion
        related_match = re.search(
            r"\*\*相关讨论\*\*[：:]\s*(.+?)(?=\n\*\*|\n###|\Z)",
            content,
            re.DOTALL,
        )
        related = related_match.group(1).strip() if related_match else None

        if title and decision_text:
            decisions.append(
                DecisionPoint(
                    title=title,
                    decision=decision_text,
                    rationale=rationale,
                    alternatives=alternatives,
                    related_discussion=related,
                )
            )

    return decisions


class LeadPlanner(BaseAgent):
    """Lead Planner agent for moderating design discussions.

    The Lead Planner is responsible for:
    - Opening discussions with clear objectives
    - Summarizing each round of discussion
    - Identifying consensus and disagreements
    - Asking targeted questions to drive deeper exploration
    - Making final decisions with clear rationale
    - Ensuring discussions produce actionable outcomes
    """

    role_name = "lead_planner"

    def get_tools(self) -> list[Any]:
        """Get tools available to the Lead Planner.

        Returns:
            Empty list (no special tools needed for moderation).
        """
        return []

    def _is_continuation_attachment(self, attachment: str | None) -> bool:
        """检测附件是否是续前讨论上下文。

        Args:
            attachment: 附件内容

        Returns:
            是否是续前讨论
        """
        if not attachment:
            return False
        return "## 前序讨论上下文" in attachment

    def create_opening_prompt(self, topic: str, attachment: str | None = None) -> str:
        """Create the opening prompt for a discussion.

        Args:
            topic: The discussion topic.
            attachment: Optional attachment content.

        Returns:
            Opening prompt for the Lead Planner.
        """
        # 检测是否是续前讨论
        is_continuation = self._is_continuation_attachment(attachment)

        if is_continuation:
            # 续前讨论的开场 prompt
            return f"""作为主策划，这是一次**续前讨论**。

议题：{topic}

请仔细阅读前序讨论的上下文，然后：
1. 【回顾总结】简要回顾之前讨论达成的共识和关键结论
2. 【本次目标】明确本次继续讨论要深入探讨的方向
3. 【核心问题】提出 2-3 个需要进一步探讨的具体问题
4. 【点名讨论】指定相关角色参与回答。不需要所有人都发言——只点名最相关的角色。用以下格式：
```speakers
角色名1, 角色名2
```

**你的团队成员**（只有以下角色参与讨论，请只向他们提问）：
- 系统策划：负责系统设计、技术架构、功能逻辑、客户端/服务器实现方案
- 数值策划：负责数值设计、经济系统、平衡性、数据分析、运营指标
- 玩家代言人：负责玩家体验、用户反馈、市场角度、可玩性评估

---
前序讨论上下文：
{attachment}
---

请以主持人身份开场，基于之前的讨论成果，引导团队深入探讨新的问题。"""

        # 普通讨论的开场 prompt
        attachment_section = ""
        if attachment:
            attachment_section = f"\n\n---\n附件内容：\n{attachment}\n---\n"

        return f"""作为主策划，请为以下话题主持讨论的开场：

话题：{topic}
{attachment_section}

**你的团队成员**（只有以下角色参与讨论，请只向他们提问）：
- 系统策划：负责系统设计、技术架构、功能逻辑、客户端/服务器实现方案
- 数值策划：负责数值设计、经济系统、平衡性、数据分析、运营指标
- 玩家代言人：负责玩家体验、用户反馈、市场角度、可玩性评估

请完成以下任务：
1. 【讨论目标】明确本次讨论要达成什么目标
2. 【关键问题】列出需要团队回答的3-5个核心问题（分配给上述角色）
3. 【讨论范围】界定本次讨论的边界，哪些是要讨论的，哪些不是
4. 【期望产出】说明讨论结束后需要产出什么文档或决策
5. 【发言人指定】像真正的主持人一样，指定谁来回答你的问题。不需要所有人都发言——只点名与当前议题最相关的角色。用以下格式指定：
```speakers
角色名1, 角色名2
```

请以主持人的身份开场，引导团队进入讨论。"""

    def create_round_summary_prompt(
        self,
        round_num: int,
        topic: str,
    ) -> str:
        """Create prompt for round summary.

        Args:
            round_num: Current round number.
            topic: The discussion topic.

        Returns:
            Summary prompt for the Lead Planner.
        """
        return f"""作为主策划，请对第{round_num}轮讨论进行总结：

话题：{topic}

**提醒**：你的团队只有系统策划、数值策划、玩家代言人三个角色。

请按以下格式输出：

## 本轮总结

### 【已达成共识】
- 列出本轮中各方已经达成一致的观点
- 每个共识点简洁明确

### 【存在分歧】
- 列出各方意见不同的点
- 说明各方的立场和理由

### 【需要深入】
- 对于需要进一步讨论的点，提出具体问题
- 只能指定以下角色回答：系统策划 / 数值策划 / 玩家代言人
- 格式：[问题]? → @角色

### 【临时决策】（如有）
- 对于已经讨论充分的点，给出你的决策
- 说明决策理由

### 【下一步】
选择以下之一：
- **继续讨论**：说明下一轮需要聚焦的问题
- **讨论充分，进入总结阶段**：所有关键问题已有结论

### 【下一轮发言人】
如果选择继续讨论，请指定下一轮谁来发言。不需要每个人都说话——只让需要回答的角色参与。
```speakers
角色名1, 角色名2
```
可选角色：系统策划、数值策划、玩家代言人"""

    def create_targeted_question_prompt(
        self,
        question: str,
        target_role: str,
        context: str,
    ) -> str:
        """Create prompt for targeted question to a specific role.

        Args:
            question: The specific question to ask.
            target_role: The role that should answer.
            context: Discussion context so far.

        Returns:
            Targeted question prompt.
        """
        return f"""作为{target_role}，请回答主策划的问题：

**主策划的问题**：
{question}

**讨论背景**：
{context}

请从你的专业角度，针对性地回答这个问题。
回答应该：
1. 直接回应问题核心
2. 给出具体的建议或方案
3. 说明你的理由或依据"""

    def create_final_decision_prompt(self, topic: str) -> str:
        """Create prompt for final decision and document generation.

        Args:
            topic: The discussion topic.

        Returns:
            Final decision prompt.
        """
        return f"""作为主策划，请对话题"{topic}"的讨论做最终总结和决策。

**提醒**：参与本次讨论的角色只有：系统策划、数值策划、玩家代言人。

请按以下格式输出：

# {topic} - 策划决策文档

## 1. 设计概述
综合各方意见，给出最终确定的设计方案概述。

## 2. 关键决策

对于每个决策点，请按以下格式记录：

### 决策点 1: [决策标题]
- **最终决策**: [你的决定]
- **决策理由**: [为什么这样决定]
- **考虑过的替代方案**:
  - 方案A: [描述] - 未采用原因: [原因]
  - 方案B: [描述] - 未采用原因: [原因]
- **相关讨论**: [哪些角色提出了什么观点]

（重复以上格式列出所有决策点）

## 3. 待确认事项
列出需要进一步确认或后续讨论的问题。

## 4. 风险与注意事项
识别的潜在风险和需要注意的点。

## 5. 下一步行动
- [ ] 列出具体的执行任务
- [ ] 指定责任人（只能是：主策划/系统策划/数值策划/玩家代言人）
- [ ] 估计优先级

## 6. 需要的视觉概念
如果需要概念图，请列出：
- 需要什么类型的图（UI 概念图、场景概念、角色设计等）
- 简要描述图的内容要求"""

    def create_agenda_prompt(self, topic: str, attachment: str | None = None) -> str:
        """Create prompt for agenda planning.

        Args:
            topic: The discussion topic.
            attachment: Optional attachment content.

        Returns:
            Agenda planning prompt for the Lead Planner.
        """
        attachment_section = ""
        if attachment:
            # Truncate long attachments
            truncated = attachment[:2000] if len(attachment) > 2000 else attachment
            attachment_section = f"\n\n参考资料：\n{truncated}..."

        return f"""作为主策划，请为以下议题规划讨论议程：

议题：{topic}
{attachment_section}

请规划 3-5 个需要讨论的关键点，按讨论优先级排序。
输出格式：
```agenda
1. [议题标题1] - 简要描述
2. [议题标题2] - 简要描述
3. [议题标题3] - 简要描述
```

注意：
- 每个议题应该是独立可讨论的
- 标题简洁明了，不超过 20 字
- 描述说明为什么需要讨论这个点"""

    def __repr__(self) -> str:
        """Return string representation of the agent."""
        return f"<LeadPlanner(role='{self.role}')>"
