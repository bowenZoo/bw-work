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

    def create_final_decisions_prompt(self, topic: str) -> str:
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
