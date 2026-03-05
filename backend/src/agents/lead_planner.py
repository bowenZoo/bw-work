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
- 数值策划：负责数值设计、经济系统、平衡性、数据分析
- 玩家代言人：负责玩家体验、用户反馈、市场角度、可玩性评估
- 市场运营：负责运营可行性、MVP 判断、付费健康度、留存设计、上线节奏

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
- 数值策划：负责数值设计、经济系统、平衡性、数据分析
- 玩家代言人：负责玩家体验、用户反馈、市场角度、可玩性评估
- 市场运营：负责运营可行性、MVP 判断、付费健康度、留存设计、上线节奏

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

**提醒**：你的团队只有系统策划、数值策划、玩家代言人、市场运营四个角色。

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
- 只能指定以下角色回答：系统策划 / 数值策划 / 玩家代言人 / 市场运营
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
可选角色：系统策划、数值策划、玩家代言人、市场运营"""

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

**提醒**：参与本次讨论的角色只有：系统策划、数值策划、玩家代言人、市场运营。

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

## 3. 可落地性检查

### 3.1 MVP 范围
- **必须有（P0）**：没有这些功能就不能上线的最小可玩版本
- **应该有（P1）**：上线后第一个版本更新加入
- **可以有（P2）**：锦上添花，视资源情况安排
- **明确不做**：讨论中提到但决定不纳入的

### 3.2 复杂度评估
- 方案涉及的新系统/新机制数量
- 系统间的依赖关系（哪些必须同时上线，哪些可以独立）
- 是否有可以复用现有机制的部分

### 3.3 运营可持续性
- 内容消耗速度 vs 产出速度是否匹配
- 付费模型是否健康（免费玩家体验底线、付费压力曲线）
- 主要生态风险及应对预案

## 4. 风险清单

| 风险 | 类型 | 影响 | 缓解方案 |
|------|------|------|----------|
| [具体风险] | 已知/潜在 | 高/中/低 | [应对措施] |

## 5. 待确认事项
列出需要进一步确认或后续讨论的问题。

## 6. 下一步行动
- [ ] 列出具体的执行任务
- [ ] 指定责任人（只能是：主策划/系统策划/数值策划/玩家代言人/市场运营）
- [ ] 标明优先级（P0/P1/P2）

## 7. 需要的视觉概念
如果需要概念图，请列出：
- 需要什么类型的图（UI 概念图、场景概念、角色设计等）
- 简要描述图的内容要求"""

    def create_doc_plan_prompt(self, topic: str, attachment: str | None = None) -> str:
        attachment_section = ""
        if attachment:
            truncated = attachment[:3000] if len(attachment) > 3000 else attachment
            attachment_section = f"\n\n参考资料:\n{truncated}"

        return f"""作为主策划，请为以下话题规划策划文档结构：

话题：{topic}
{attachment_section}

请输出一个 JSON 格式的文档规划。规划要求：
1. 文件数量和章节数量完全由你根据话题需要自行决定，不设任何限制
2. 每个文件聚焦一个独立的设计领域，文件之间尽量解耦
3. 每个章节应该是一个可独立讨论的设计点
4. 章节顺序要合理，前置知识在前
5. 文件名使用中文，后缀 .md

严格按以下 JSON 格式输出（不要输出其他任何内容）：
```json
{{{{
  "files": [
    {{{{
      "filename": "核心玩法设计.md",
      "title": "核心玩法设计方案",
      "sections": [
        {{{{"id": "s1", "title": "系统概述", "description": "定义核心玩法的目标和基本框架"}}}},
        {{{{"id": "s2", "title": "核心循环", "description": "玩家的主要游戏循环和反馈机制"}}}}
      ]
    }}}}
  ]
}}}}
```"""

    def create_section_discussion_prompt(self, section_title: str, section_description: str,
                                          current_content: str, round_num: int) -> str:
        content_section = ""
        if current_content and current_content.strip():
            content_section = f"\n\n当前章节已有内容：\n{current_content}"

        return f"""作为主策划，本轮（第{round_num}轮）聚焦讨论以下章节：

**章节**: {section_title}
**章节目标**: {section_description}
{content_section}

请引导团队讨论这个章节的内容，提出 2-3 个具体问题。
指定谁来回答（只能指定：系统策划、数值策划、玩家代言人、市场运营）。

用以下格式指定发言人：
```speakers
角色名1, 角色名2
```"""

    def create_section_summary_prompt(self, section_title: str, round_num: int) -> str:
        return f"""作为主策划，请对第{round_num}轮关于"{section_title}"章节的讨论进行总结：

请按以下格式输出：
### 本轮讨论要点
- 列出讨论达成的结论
- 列出需要记入文档的关键设计决策

### 章节状态评估
选择以下之一：
- **章节完成**：该章节讨论已充分，可以写入文档
- **需要继续**：该章节还需要更多讨论

### 下一轮发言人
```speakers
角色名1, 角色名2
```

---
**可选：议题管理指令**

如果在讨论中发现了新的议题、某个已有议题已经讨论充分、或需要调整议题优先级，可以输出以下代码块：

```agenda_update
complete: <议题ID>
add: [新议题标题] - 新议题描述
priority: <议题ID> high|low
```

- complete: 标记某个议题为已完结
- add: 新增一个讨论中发现的新议题
- priority: 调整议题优先级为 high 或 low

如果没有需要变更的议题，不要输出此代码块。

---
**可选：文档结构调整指令**

如果在讨论中发现当前文档结构需要调整（如章节内容过大需要拆分、多个章节重复需要合并、需要新增章节或文件），可以输出以下代码块：

```doc_restructure
split: <section_id> -> [新标题1](新描述1), [新标题2](新描述2)
merge: <section_id1>, <section_id2> -> [合并后标题]
add_section: <file_index>:<after_section_id> [新章节标题](新章节描述)
add_file: [文件名.md](文件标题) sections: [标题1](描述1), [标题2](描述2)
```

- split: 将一个章节拆分为多个
- merge: 将多个章节合并为一个
- add_section: 在指定文件的指定位置添加新章节
- add_file: 新增一个文件及其章节

如果不需要调整文档结构，不要输出此代码块。

---
**可选：文档结构重规划指令**

如果发现文档整体结构存在严重问题（如文件分类错误、章节划分不合理、遗漏关键领域），且无法通过 split/merge/add 修复，可以输出以下代码块触发完整重规划：

```doc_restructure
replan: <重规划原因>
```

注意：replan 是破坏性操作，会重建所有文件和章节（内容会迁移），仅在结构问题严重时使用。"""

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

    # ------------------------------------------------------------------
    # 干预消化 & 整体审视 Prompt 方法
    # ------------------------------------------------------------------

    def create_intervention_digest_prompt(
        self,
        user_messages: list[str],
        current_section: str,
        discussion_context: str,
    ) -> str:
        """创建观众干预消化 prompt，让主策划独立理解和分析观众意见。

        Args:
            user_messages: 观众发送的消息列表。
            current_section: 当前正在讨论的章节标题。
            discussion_context: 当前讨论的上下文摘要。

        Returns:
            干预消化 prompt。
        """
        messages_block = "\n".join(
            f"- 观众消息 {i+1}: {msg}" for i, msg in enumerate(user_messages)
        )

        return f"""作为主策划，你收到了观众（用户）的实时反馈。请独立消化这些意见，不要直接转发给团队。

**当前讨论章节**: {current_section}

**讨论上下文**:
{discussion_context}

**观众消息**:
{messages_block}

请按以下格式输出你的分析：

### 观点理解
- 逐条理解观众的核心诉求，用你自己的话复述

### 关键诉求
- 提炼出观众最关心的 1-3 个核心诉求
- 区分「具体建议」和「方向性意见」

### 关联分析
- 这些意见与当前讨论章节「{current_section}」的关联度
- 是否涉及已讨论完成的章节
- 是否暗示需要新增讨论议题

### 后续引导方向
- 你打算如何将这些意见融入后续讨论
- 是直接在当前章节中吸纳，还是需要回溯或新增议题
- 给出具体的引导策略"""

    def create_intervention_assessment_prompt(
        self,
        digest_summary: str,
        current_section: str,
        completed_sections: list[dict],
        doc_plan_summary: str,
    ) -> str:
        """创建干预影响评估 prompt，判断观众意见的影响范围。

        Args:
            digest_summary: 前一步消化分析的输出。
            current_section: 当前讨论章节标题。
            completed_sections: 已完成章节列表，每项包含 "id", "title", "summary"。
            doc_plan_summary: 文档规划摘要。

        Returns:
            影响评估 prompt。
        """
        completed_block = "\n".join(
            f"- {s['id']}: {s['title']} — {s.get('summary', '(无摘要)')}"
            for s in completed_sections
        ) if completed_sections else "(暂无已完成章节)"

        return f"""作为主策划，请根据你对观众意见的消化分析，评估其对讨论的影响范围。

**你的消化分析**:
{digest_summary}

**当前讨论章节**: {current_section}

**已完成的章节**:
{completed_block}

**文档规划概览**:
{doc_plan_summary}

请严格按以下格式输出评估结果（用代码块包裹）：

```intervention_assessment
impact_level: <CURRENT_ONLY | REOPEN | NEW_TOPIC>
summary: <一句话总结影响>
current_section_actions:
  - <对当前章节的具体调整>
reopen_sections:
  - section_id: <要重开的章节 ID>
    reason: <重开原因>
    focus: <重开后聚焦的问题>
new_topics:
  - title: <新议题标题>
    description: <新议题描述>
    priority: <high | medium | low>
```

**约束**:
- impact_level 三选一：
  - CURRENT_ONLY: 仅影响当前章节，在当前讨论中吸纳即可
  - REOPEN: 需要回溯重开已完成的章节（最多重开 3 个）
  - NEW_TOPIC: 需要新增讨论议题
- reopen_sections 最多 3 个，选择影响最大的
- 优先选择 CURRENT_ONLY，只有观众意见确实与已完成章节强相关时才选 REOPEN"""

    def create_holistic_review_prompt(
        self,
        all_file_contents: list[dict],
        doc_plan_summary: str,
        pending_agenda_items: list[str],
        discussion_summary: str,
    ) -> str:
        """创建整体审视 prompt，在所有章节完成后对文档进行全局审查。

        Args:
            all_file_contents: 所有文件内容列表，每项包含 "filename", "title", "content"。
            doc_plan_summary: 文档规划摘要。
            pending_agenda_items: 尚未讨论的待定议题列表。
            discussion_summary: 整个讨论过程的摘要。

        Returns:
            整体审视 prompt。
        """
        files_block = ""
        for f in all_file_contents:
            files_block += f"\n---\n**文件**: {f['filename']} ({f['title']})\n{f['content']}\n"

        pending_block = "\n".join(
            f"- {item}" for item in pending_agenda_items
        ) if pending_agenda_items else "(无待定议题)"

        return f"""作为主策划，所有章节讨论已完成。请对全部产出文档进行整体审视。

**文档规划概览**:
{doc_plan_summary}

**讨论过程摘要**:
{discussion_summary}

**待定议题（未讨论）**:
{pending_block}

**全部文档内容**:
{files_block}

请从以下维度进行审视：

### 1. 跨章节一致性
- 不同章节之间是否存在术语不统一、数值矛盾、逻辑冲突
- 前后引用是否准确

### 2. 完整性
- 文档规划中的每个章节是否都有实质性内容
- 是否有重要设计点遗漏
- 待定议题是否需要补充到现有文档中

### 3. 观众意见回应
- 讨论中收到的观众反馈是否已在文档中得到体现
- 是否有未回应的重要观众诉求

### 4. 整体质量
- 文档是否具备可执行性
- 是否需要补充细节或示例

请严格按以下格式输出审视结果（用代码块包裹）：

```holistic_review
conclusion: <APPROVED | NEEDS_REVISION | NEEDS_NEW_TOPIC>
quality_score: <1-10>
summary: <一句话总结审视结论>
consistency_issues:
  - file: <文件名>
    section: <章节 ID>
    issue: <问题描述>
    suggestion: <修改建议>
completeness_gaps:
  - description: <缺失内容描述>
    suggested_section: <建议补充到哪个章节>
    priority: <high | medium | low>
revision_actions:
  - section_id: <需要修改的章节 ID>
    file: <文件名>
    action: <具体修改要求>
new_topics:
  - title: <新议题标题>
    reason: <为什么需要新增>
```

**约束**:
- conclusion 四选一：
  - APPROVED: 文档质量合格，可以定稿
  - NEEDS_REVISION: 需要修改部分章节内容（不需要新的讨论轮次）
  - NEEDS_NEW_TOPIC: 发现重大遗漏，需要新增讨论议题
  - NEEDS_RESTRUCTURE: 文档整体结构存在严重问题（文件分类错误、章节划分不合理），需要重新规划文档结构
- quality_score: 1-10 分，7 分以上才可 APPROVED
- 如果 conclusion 为 NEEDS_RESTRUCTURE，请额外输出 `restructure_reason: <具体原因>`
- NEEDS_RESTRUCTURE 仅在结构问题无法通过 NEEDS_REVISION 修复时使用
- 审视要客观严格，但不要吹毛求疵"""

    # ------------------------------------------------------------------
    # Replan Prompts
    # ------------------------------------------------------------------

    def create_replan_prompt(
        self,
        topic: str,
        all_file_contents: list[dict],
        current_plan_summary: str,
        reason: str,
    ) -> str:
        """创建文档结构重规划 prompt。

        Args:
            topic: 讨论话题。
            all_file_contents: 所有文件内容列表，每项包含 "filename", "title", "sections"。
                sections 是 {section_id: {title, content}} 的字典。
            current_plan_summary: 当前文档规划摘要。
            reason: 重规划原因。

        Returns:
            重规划 prompt。
        """
        files_block = ""
        for f in all_file_contents:
            files_block += f"\n### 文件: {f['filename']} ({f['title']})\n"
            for sid, info in f.get("sections", {}).items():
                content_preview = info.get("content", "")[:500]
                files_block += f"- [{sid}] {info.get('title', '')}: {content_preview}\n"

        return f"""作为主策划，当前文档结构需要重新规划。

**话题**: {topic}

**重规划原因**: {reason}

**当前文档结构**:
{current_plan_summary}

**当前所有内容**:
{files_block}

请输出一个全新的文档规划 JSON。要求：
1. 根据话题和已有内容重新组织文件和章节结构
2. 每个新章节必须带 `source_sections` 字段，标明内容来自哪些旧章节
3. 如果新章节是全新的（无旧内容对应），source_sections 为空数组
4. 不要丢失任何已讨论的内容——所有旧章节都必须被某个新章节引用
5. 文件数量和章节数量由你自行决定，不设限制

严格按以下 JSON 格式输出（不要输出其他任何内容）：
```json
{{{{
  "files": [
    {{{{
      "filename": "新文件名.md",
      "title": "新文件标题",
      "sections": [
        {{{{
          "id": "s1",
          "title": "新章节标题",
          "description": "章节描述",
          "source_sections": ["旧s1", "旧s3"]
        }}}}
      ]
    }}}}
  ]
}}}}
```"""

    def create_content_migration_prompt(
        self,
        new_section_title: str,
        new_section_description: str,
        source_contents: list[dict],
    ) -> str:
        """创建内容迁移 prompt，将多个旧章节内容重组为新章节。

        Args:
            new_section_title: 新章节标题。
            new_section_description: 新章节描述。
            source_contents: 来源内容列表，每项包含 "title", "content"。

        Returns:
            内容迁移 prompt。
        """
        sources_block = "\n\n".join(
            f"### 来源: {s['title']}\n{s['content']}"
            for s in source_contents
        )

        return f"""你是专业的游戏策划文档编辑。

请将以下多个章节的内容重组为一个新的章节。

**新章节标题**: {new_section_title}
**新章节目标**: {new_section_description}

**来源内容**:
{sources_block}

要求：
1. 保留所有关键信息，去除重复内容
2. 按照新章节的目标重新组织结构
3. 输出纯 Markdown 格式（不含章节标题 ##）
4. 不要输出解释性文字，只输出重组后的内容

直接输出内容："""

    # ------------------------------------------------------------------
    # Checkpoint 相关 Prompt 方法
    # ------------------------------------------------------------------

    def create_checkpoint_prompt(
        self,
        round_num: int,
        section_title: str,
        section_description: str,
        recent_messages: list[str],
        discussion_context: str,
        briefing: str,
        pending_decisions: list[str],
    ) -> str:
        """创建 Checkpoint 生成 prompt。

        主策划在每轮结束后调用，自主判断是否需要通知制作人。

        Args:
            round_num: 当前轮次。
            section_title: 当前章节标题。
            section_description: 当前章节描述。
            recent_messages: 本轮所有 agent 的发言。
            discussion_context: 已有讨论摘要。
            briefing: 制作人的 briefing。
            pending_decisions: 已有未回答的决策问题列表。
        """
        messages_block = "\n".join(
            f"- {msg}" for msg in recent_messages[-10:]
        )
        pending_block = "\n".join(
            f"- {d}" for d in pending_decisions
        ) if pending_decisions else "(无)"

        briefing_block = f"\n**制作人简报**: {briefing}" if briefing else ""

        return f"""作为主策划，第{round_num}轮关于「{section_title}」的讨论刚刚结束。请判断是否需要通知制作人。
{briefing_block}

**章节目标**: {section_description}

**本轮讨论记录**:
{messages_block}

**已有讨论摘要**:
{discussion_context}

**已有未回答的决策**:
{pending_block}

请判断当前讨论进展，选择以下三种 Checkpoint 之一：

1. **SILENT** — 讨论正常推进，无需通知制作人。常规讨论、尚在探索阶段。
2. **PROGRESS** — 达成共识、完成里程碑、发现重要分歧。通知制作人但不阻塞讨论。
3. **DECISION** — 核心分歧无法自行解决，需制作人定夺方向。阻塞讨论等待回答。

**判断原则**:
- 大部分轮次应该是 SILENT，只有真正有意义的节点才产出 PROGRESS 或 DECISION
- DECISION 仅在团队无法自行解决分歧时使用，不要滥用
- 如果已有未回答的决策，不要产生新的 DECISION（避免堆积）
- PROGRESS 用于记录重要的共识和里程碑

严格按以下格式输出（用代码块包裹）：

```checkpoint
type: SILENT
```

或：

```checkpoint
type: PROGRESS
title: "进展标题"
summary: "进展摘要"
key_points:
  - "关键点 1"
  - "关键点 2"
```

或：

```checkpoint
type: DECISION
question: "需要制作人回答的问题"
context: "为何需要此决策的背景说明"
options:
  - id: A
    label: "选项标题"
    description: "选项说明"
  - id: B
    label: "选项标题"
    description: "选项说明"
allow_free_input: true
```"""

    def create_decision_announcement_prompt(
        self,
        question: str,
        user_response: str,
        user_response_text: str,
        options_summary: str,
    ) -> str:
        """创建决策宣布 prompt。

        主策划公开宣布制作人的决策，并引导后续讨论。

        Args:
            question: 原始决策问题。
            user_response: 用户选择的选项 ID（或自由输入）。
            user_response_text: 用户的补充说明。
            options_summary: 选项概要文本。
        """
        response_block = ""
        if user_response:
            response_block += f"选择的选项: {user_response}"
        if user_response_text:
            response_block += f"\n补充说明: {user_response_text}"

        return f"""作为主策划，制作人已经对以下问题做出了决策。请向团队公开宣布并引导后续讨论。

**决策问题**: {question}

**选项概要**:
{options_summary}

**制作人的回答**:
{response_block}

请完成以下任务：
1. 以主持人身份公开宣布制作人的决策
2. 简要解释这个决策对后续讨论的影响
3. 给出团队下一步的讨论方向

语气要正式但友好，确保团队理解决策内容和原因。"""

    def create_producer_digest_prompt(
        self,
        user_messages: list[str],
        current_section: str,
        discussion_context: str,
    ) -> str:
        """创建制作人消息消化 prompt。

        主策划独立消化制作人的即时消息并给出后续引导。

        Args:
            user_messages: 制作人发送的消息列表。
            current_section: 当前讨论章节标题。
            discussion_context: 当前讨论上下文。
        """
        messages_block = "\n".join(
            f"- 制作人消息 {i+1}: {msg}" for i, msg in enumerate(user_messages)
        )

        return f"""作为主策划，你收到了制作人（用户）的实时消息。请消化并给出后续引导。

**当前讨论章节**: {current_section}

**讨论上下文**:
{discussion_context}

**制作人消息**:
{messages_block}

请按以下格式输出你的分析和引导：

### 理解确认
- 用你自己的话复述制作人的核心意图

### 行动判断
选择以下之一：
- **adjust** — 可以直接调整讨论方向，无需追问
- **follow_up_decision** — 需要向制作人追问确认（将生成 DECISION checkpoint）
- **acknowledged** — 已知悉，无需特别调整

### 后续引导
- 具体说明如何将制作人的意见融入后续讨论
- 如果选择 adjust，说明新的讨论方向"""

    def __repr__(self) -> str:
        """Return string representation of the agent."""
        return f"<LeadPlanner(role='{self.role}')>"
