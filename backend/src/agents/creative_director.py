"""Creative Director Agent - Moderates concept incubation discussions."""

from src.agents.lead_planner import LeadPlanner


class CreativeDirector(LeadPlanner):
    """Creative Director agent for moderating concept incubation sessions.

    Replaces the Lead Planner as moderator in concept-stage discussions.
    Focuses on helping the producer (user) articulate and expand creative ideas.
    """

    role_name = "creative_director"

    def create_opening_prompt(self, topic: str, attachment: str | None = None) -> str:
        """Create concept-incubation opening prompt.

        Greets producer by name, introduces the project, and invites the
        producer to share their initial creative vision first.
        """
        attachment_section = ""
        if attachment:
            attachment_section = f"\n\n---\n背景资料：\n{attachment}\n---\n"

        return f"""作为创意总监，请为以下游戏概念孵化会开场：

项目议题：{topic}
{attachment_section}

**你的团队**（以下角色参与孵化讨论）：
- 主策划：负责将创意转化为可落地的设计方向
- 市场总监：负责从市场和用户角度提供洞察
- 制作人（用户）：项目的创意主人，每轮必须邀请发言

**开场任务：**
1. 【热情欢迎】以创意总监的热情风格开场，简介本次孵化会的目的
2. 【项目解读】基于议题，分享你对这个游戏概念的初步感受和最令你兴奋的潜力点
3. 【核心问题】提出 1-2 个开放式问题，邀请制作人分享他们最初的创意冲动和愿景
4. 【等待制作人】明确表示下一步先听制作人的想法，用以下格式指定发言人：
```speakers
制作人
```

**风格要求：**充满热情，富有创意激励性，重点是让制作人感到被倾听和被鼓励。"""

    def create_round_summary_prompt(self, round_num: int, topic: str) -> str:
        """Create concept-incubation round summary prompt."""
        return f"""作为创意总监，请总结第{round_num}轮概念孵化讨论：

议题：{topic}

请完成以下任务：
1. 【创意亮点】提炼本轮讨论中最有潜力的 2-3 个创意方向或亮点
2. 【制作人核心想法】准确捕捉制作人在本轮表达的核心创意意图
3. 【团队观点】市场总监和主策划提供了哪些有价值的补充
4. 【延伸可能】基于本轮创意，还有哪些值得探索的方向
5. 【下一步邀请】提出一个开放式问题，邀请制作人继续分享，用以下格式指定发言人：
```speakers
制作人, 主策划
```

**判断孵化进度：**
- 如果创意方向已经足够清晰和丰富，在最后加上：`[孵化充分]`
- 如果还需要继续探索，继续引导制作人挖掘

**严格控制在 300 字以内。**"""

    def create_doc_plan_prompt(self, topic: str, attachment: str | None = None) -> str:
        """Create concept-incubation doc plan prompt.

        Unlike the generic doc plan, concept incubation only produces
        concept-stage documents: a creative brief and a market analysis.
        """
        attachment_section = ""
        if attachment:
            truncated = attachment[:3000] if len(attachment) > 3000 else attachment
            attachment_section = f"\n\n参考资料:\n{truncated}"

        return f"""作为创意总监，请为以下概念孵化项目规划文档结构：

话题：{topic}
{attachment_section}

本次是**概念孵化阶段**，仅需规划概念阶段的文档，不要规划系统设计、数值平衡等后期文档。

概念孵化阶段通常只需要以下两类文档：
1. **游戏创意简报**（概念定位、制作人愿景、核心亮点、目标玩家）
2. **市场可行性分析**（市场机会、竞品分析、差异化定位）

请根据话题灵活调整章节内容，保持精简（每个文件 3-5 个章节即可）。

严格按以下 JSON 格式输出（不要输出其他任何内容）：
```json
{{{{
  "files": [
    {{{{
      "filename": "游戏创意简报.md",
      "title": "游戏创意简报",
      "sections": [
        {{{{"id": "s1", "title": "核心创意与定位", "description": "一句话概括游戏独特价值，以及在市场中的定位"}}}},
        {{{{"id": "s2", "title": "制作人愿景与玩家体验", "description": "制作人希望带给玩家的核心情感体验"}}}},
        {{{{"id": "s3", "title": "创意亮点列表", "description": "经过讨论验证的核心创意亮点"}}}},
        {{{{"id": "s4", "title": "目标玩家画像", "description": "最核心的目标玩家群体描述"}}}}
      ]
    }}}},
    {{{{
      "filename": "市场可行性分析.md",
      "title": "市场可行性分析",
      "sections": [
        {{{{"id": "s5", "title": "市场机会与时机", "description": "当前市场中存在的机会窗口"}}}},
        {{{{"id": "s6", "title": "竞品对比", "description": "主要竞争产品分析及差异化空间"}}}},
        {{{{"id": "s7", "title": "差异化战略", "description": "与竞品相比的核心差异和竞争优势"}}}}
      ]
    }}}}
  ]
}}}}
```"""


        """Create concept-incubation final document generation prompt."""
        return f"""作为创意总监，请基于整个概念孵化讨论，生成《创意点文档》：

议题：{topic}

请生成以下结构的创意点文档：

# 游戏创意点文档

## 核心创意
（一句话描述这个游戏最独特、最令人兴奋的创意核心）

## 制作人愿景
（制作人希望通过这个游戏带给玩家的核心体验和情感）

## 创意亮点列表
- 亮点1：（具体描述）
- 亮点2：（具体描述）
- 亮点3：（具体描述）
（列出所有经过讨论验证的创意亮点）

## 目标玩家画像
（根据市场总监的分析，描述最核心的目标玩家群体）

## 市场差异化
（这个游戏与市场上现有产品的核心差异点）

## 下一步方向
（基于概念孵化的成果，建议进入哪个核心设计方向）

---
*本文档由创意总监根据概念孵化讨论整理生成。*"""
