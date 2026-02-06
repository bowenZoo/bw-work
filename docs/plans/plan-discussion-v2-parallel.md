# Plan: 讨论系统 V2 - 并行发言机制

> **模块**: discussion-v2-parallel
> **优先级**: P1
> **对应 Spec**: docs/spec-discussion-v2.md#2.1

## 目标

实现主策划点名后，被点名者并行回答的机制：
1. 解析主策划输出，识别被点名角色
2. 使用 `asyncio.gather()` 并行调用被点名的 Agent
3. 未被点名的 Agent 本轮静默
4. WebSocket 实时广播各 Agent 状态（thinking/speaking）

## 前置依赖

- plan-discussion-v2-global.md (WebSocket 重构)

## 技术方案

### 流程设计

```
主策划开场（提问 A 和 B）
    ├── A 思考并回答 ──┐
    └── B 思考并回答 ──┴── 主策划总结
```

### 核心实现

```python
# 识别被点名角色（从主策划输出解析）
mentioned_roles = parse_mentioned_roles(lead_planner_output)

# 并行调用
tasks = [agent.respond(context) for agent in agents if agent.role in mentioned_roles]
responses = await asyncio.gather(*tasks)
```

### 角色识别规则

主策划点名的几种方式：
- 直接点名：`系统策划，你觉得...`
- 提问：`数值策划能否说明...`
- 邀请：`请玩家代言人从用户角度...`

识别关键词：
- `系统策划` / `系统` / `技术`
- `数值策划` / `数值` / `平衡`
- `玩家代言人` / `玩家` / `用户`

## 任务清单

### Task V2P-3.1: 实现角色点名解析器

**执行**:
- 创建 `backend/src/crew/mention_parser.py`
- 实现 `parse_mentioned_roles(text: str) -> list[str]` 函数
- 识别规则：
  1. 直接匹配角色名称
  2. 匹配角色别名
  3. 匹配问句模式（`xxx，你...` / `请xxx...`）

```python
from typing import NamedTuple

class MentionPattern(NamedTuple):
    """角色点名模式"""
    role: str          # 标准角色名
    aliases: list[str] # 别名列表
    patterns: list[str] # 正则模式

ROLE_PATTERNS = [
    MentionPattern(
        role="系统策划",
        aliases=["系统", "技术", "架构"],
        patterns=[
            r"系统策划[，,]",
            r"请系统策划",
            r"系统(?:策划)?(?:能否|可以|来)",
        ]
    ),
    MentionPattern(
        role="数值策划",
        aliases=["数值", "平衡", "经济"],
        patterns=[
            r"数值策划[，,]",
            r"请数值策划",
            r"数值(?:策划)?(?:能否|可以|来)",
        ]
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
        ]
    ),
]

def parse_mentioned_roles(text: str) -> list[str]:
    """解析文本中被点名的角色"""
    mentioned = set()

    for pattern in ROLE_PATTERNS:
        # 检查直接名称
        if pattern.role in text:
            mentioned.add(pattern.role)
            continue

        # 检查别名
        for alias in pattern.aliases:
            if alias in text:
                mentioned.add(pattern.role)
                break

        # 检查正则模式
        for regex in pattern.patterns:
            if re.search(regex, text):
                mentioned.add(pattern.role)
                break

    return list(mentioned)
```

**验证**:
- `cd backend && python -m pytest tests/test_mention_parser.py -v` → exit_code == 0

**输出文件**:
- `backend/src/crew/mention_parser.py`
- `backend/tests/test_mention_parser.py`

---

### Task V2P-3.2: 更新 Agent 基类支持异步

**执行**:
- 更新 `backend/src/agents/base.py`
- 添加 `respond_async(context: str) -> str` 异步方法
- 确保 LLM 调用支持异步

```python
class BaseAgent:
    async def respond_async(self, context: str) -> str:
        """异步响应方法"""
        # 构建 task
        task = Task(
            description=self._build_response_prompt(context),
            expected_output="回应内容",
            agent=self.build_agent(),
        )

        # 使用 asyncio 运行
        crew = Crew(
            agents=[self.build_agent()],
            tasks=[task],
            process=Process.sequential,
        )

        result = await crew.kickoff_async()
        return str(result)
```

**验证**:
- `cd backend && python -c "from src.agents.base import BaseAgent; import asyncio; print('ok')"` → exit_code == 0

**输出文件**:
- `backend/src/agents/base.py` (更新)

---

### Task V2P-3.3: 实现并行讨论轮次

**执行**:
- 更新 `backend/src/crew/discussion_crew.py`
- 重构 `run()` 方法，支持动态任务生成
- 实现 `_run_parallel_responses()` 方法

```python
async def _run_parallel_responses(
    self,
    mentioned_roles: list[str],
    context: str,
) -> list[tuple[str, str]]:
    """并行调用被点名的 Agent

    Args:
        mentioned_roles: 被点名的角色列表
        context: 讨论上下文

    Returns:
        [(role, response), ...] 按完成顺序
    """
    # 筛选被点名的 agents
    agents_to_call = [
        agent for agent in self._discussion_agents
        if agent.role in mentioned_roles
    ]

    if not agents_to_call:
        # 默认全部参与
        agents_to_call = self._discussion_agents

    # 广播 thinking 状态
    for agent in agents_to_call:
        self._broadcast_status(agent.role, AgentStatus.THINKING)

    # 并行调用
    async def call_agent(agent):
        response = await agent.respond_async(context)
        return (agent.role, response)

    results = await asyncio.gather(*[
        call_agent(agent) for agent in agents_to_call
    ])

    return results
```

**验证**:
- `cd backend && python -m pytest tests/test_discussion_crew.py -v -k parallel` → exit_code == 0

**输出文件**:
- `backend/src/crew/discussion_crew.py` (更新)

---

### Task V2P-3.4: 重构讨论流程为动态轮次

**执行**:
- 更新 `backend/src/crew/discussion_crew.py`
- 将固定任务列表改为动态生成
- 新流程：
  1. 主策划开场
  2. 解析点名 → 并行响应 → 主策划总结
  3. 重复步骤 2 直到讨论充分或达到最大轮次
  4. 主策划最终决策

```python
async def run_dynamic(
    self,
    topic: str,
    max_rounds: int = 5,
    attachment: str | None = None,
) -> str:
    """运行动态讨论流程"""
    self._init_discussion(topic)
    set_discussion_state(self._discussion_id, DiscussionState.RUNNING)

    # Phase 0: 主策划开场
    opening = await self._lead_planner_opening(topic, attachment)
    self._broadcast_message(self._lead_planner.role, opening)
    self._record_message(self._lead_planner.role, opening)

    # Phase 1-N: 动态讨论轮次
    context = f"议题：{topic}\n\n主策划开场：\n{opening}"
    round_num = 0

    while round_num < max_rounds:
        round_num += 1

        # 解析被点名角色
        mentioned_roles = parse_mentioned_roles(context)

        # 并行响应
        responses = await self._run_parallel_responses(mentioned_roles, context)

        # 记录和广播响应
        for role, response in responses:
            self._broadcast_status(role, AgentStatus.SPEAKING)
            self._broadcast_message(role, response)
            self._record_message(role, response)
            self._broadcast_status(role, AgentStatus.IDLE)
            context += f"\n\n{role}：\n{response}"

        # 主策划总结
        summary = await self._lead_planner_summary(round_num, context)
        self._broadcast_message(self._lead_planner.role, summary)
        self._record_message(self._lead_planner.role, summary)
        context += f"\n\n主策划总结：\n{summary}"

        # 检查是否继续
        status, questions = parse_discussion_status(summary)
        if status == DiscussionStatus.SUFFICIENT:
            break

    # Final: 最终决策
    final_decision = await self._lead_planner_final_decision(topic, context)
    self._broadcast_message(self._lead_planner.role, final_decision)
    self._record_message(self._lead_planner.role, final_decision)

    self._save_discussion(summary=final_decision)
    return final_decision
```

**验证**:
- `cd backend && python -m pytest tests/test_discussion_crew.py -v -k dynamic` → exit_code == 0

**输出文件**:
- `backend/src/crew/discussion_crew.py` (更新)

---

### Task V2P-3.5: 前端并行状态显示

**执行**:
- 更新 `frontend/src/composables/useGlobalDiscussion.ts`
- 支持同时多个 Agent 处于 thinking 状态
- 更新 `agentStatuses` 为 Map 结构

```typescript
// stores/agents.ts 更新
const agentStatuses = ref<Map<string, AgentStatus>>(new Map())

function handleStatusMessage(data: StatusMessage) {
  agentStatuses.value.set(data.agent_id, data.status)
}

// 获取所有正在思考的 agents
const thinkingAgents = computed(() =>
  Array.from(agentStatuses.value.entries())
    .filter(([_, status]) => status === 'thinking')
    .map(([id, _]) => id)
)
```

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0

**输出文件**:
- `frontend/src/stores/agents.ts` (更新)
- `frontend/src/composables/useGlobalDiscussion.ts` (更新)

---

### Task V2P-3.6: 前端并行消息展示

**执行**:
- 更新 `frontend/src/components/chat/ChatContainer.vue`
- 处理并行消息的展示顺序
- 消息带序号，按序号排序

**消息模型更新**:
```typescript
interface Message {
  id: string
  agentId: string
  agentRole: string
  content: string
  timestamp: string
  sequence?: number  // 新增：序号，用于排序
}
```

**展示逻辑**:
```typescript
const sortedMessages = computed(() =>
  [...messages.value].sort((a, b) => {
    // 优先按 sequence 排序，其次按 timestamp
    if (a.sequence !== undefined && b.sequence !== undefined) {
      return a.sequence - b.sequence
    }
    return new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  })
)
```

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0
- 并行消息按正确顺序显示

**输出文件**:
- `frontend/src/types/index.ts` (更新)
- `frontend/src/components/chat/ChatContainer.vue` (更新)

---

### Task V2P-3.7: 后端消息序号支持

**执行**:
- 更新 `backend/src/api/websocket/events.py`
- `MessageEvent` 添加 `sequence` 字段
- `DiscussionCrew` 维护全局序号计数器

```python
class MessageEvent(BaseModel):
    type: Literal["message"] = "message"
    data: MessageData

class MessageData(BaseModel):
    discussion_id: str
    agent_id: str
    agent_role: str
    content: str
    timestamp: str
    sequence: int  # 新增

# discussion_crew.py
class DiscussionCrew:
    def __init__(self, ...):
        ...
        self._message_sequence = 0

    def _next_sequence(self) -> int:
        self._message_sequence += 1
        return self._message_sequence
```

**验证**:
- `cd backend && python -c "from src.api.websocket.events import MessageEvent; print('ok')"` → exit_code == 0

**输出文件**:
- `backend/src/api/websocket/events.py` (更新)
- `backend/src/crew/discussion_crew.py` (更新)

---

### Task V2P-3.8: 添加并行发言测试

**执行**:
- 创建 `backend/tests/test_parallel_discussion.py`
- 测试用例：
  1. 点名单个角色 → 只有该角色响应
  2. 点名多个角色 → 多个角色并行响应
  3. 不点名 → 所有角色响应
  4. 消息序号正确递增

```python
import pytest
from src.crew.mention_parser import parse_mentioned_roles
from src.crew.discussion_crew import DiscussionCrew

class TestMentionParser:
    def test_single_mention(self):
        text = "系统策划，你觉得这个技术方案可行吗？"
        roles = parse_mentioned_roles(text)
        assert roles == ["系统策划"]

    def test_multiple_mentions(self):
        text = "系统策划和数值策划，请分别从你们的角度分析一下"
        roles = parse_mentioned_roles(text)
        assert set(roles) == {"系统策划", "数值策划"}

    def test_alias_mention(self):
        text = "从玩家角度来看，这个设计体验如何？"
        roles = parse_mentioned_roles(text)
        assert "玩家代言人" in roles

    def test_no_mention(self):
        text = "大家觉得这个方案怎么样？"
        roles = parse_mentioned_roles(text)
        assert roles == []  # 空则默认全部参与

@pytest.mark.asyncio
class TestParallelDiscussion:
    async def test_parallel_responses(self):
        crew = DiscussionCrew(discussion_id="test-parallel")
        # ...测试并行响应
```

**验证**:
- `cd backend && python -m pytest tests/test_parallel_discussion.py -v` → exit_code == 0

**输出文件**:
- `backend/tests/test_parallel_discussion.py`

## 验收标准

- [ ] 主策划点名 A 和 B 时，A 和 B 同时显示"思考中" (Spec 验收)
- [ ] 被点名的角色并行响应
- [ ] 未被点名的角色静默
- [ ] 消息按正确顺序显示
- [ ] 消息带序号，前端排序正确
- [ ] 测试用例全部通过
- [ ] TypeScript 无类型错误
