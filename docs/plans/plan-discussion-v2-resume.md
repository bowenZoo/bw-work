# Plan: 讨论系统 V2 - 讨论恢复

> **模块**: discussion-v2-resume
> **优先级**: P2
> **对应 Spec**: docs/spec-discussion-v2.md#2.6

## 目标

从历史记录中选择讨论，继续讨论：
1. 历史列表页添加"继续讨论"按钮
2. 继续时加载原讨论的上下文作为背景
3. 用户输入追加问题/方向
4. 创建新讨论，引用原讨论

## 前置依赖

- plan-discussion-v2-global.md (全局讨论)
- plan-history.md (历史记录页面，已存在)

## 技术方案

### 继续讨论流程

```
1. 用户在历史列表点击"继续讨论"
     ↓
2. 弹出对话框，显示原议题 + 追加输入框
     ↓
3. 用户输入追加问题/方向
     ↓
4. 调用 POST /api/discussions/{id}/continue
     ↓
5. 后端：
   - 加载原讨论摘要 + 最后 N 条消息
   - 创建新讨论，topic 标记为"[继续] 原议题"
   - 将上下文作为附件传入
     ↓
6. 自动跳转到新讨论页面
```

### 上下文构建

```markdown
## 前序讨论上下文

### 原始话题: {original_topic}

### 讨论总结
{summary}

### 关键讨论内容
**系统策划**: {last_message}...
**数值策划**: {last_message}...
**玩家代言人**: {last_message}...

---

## 继续讨论

用户希望在以上讨论基础上，继续探讨以下问题：

**{follow_up_topic}**
```

## 任务清单

### Task V2R-5.1: 完善继续讨论 API

**执行**:
- 检查并完善 `backend/src/api/routes/discussion.py` 中的 `/continue` 端点
- 确保上下文构建逻辑正确
- 添加对原讨论消息的智能摘取

**现有 API 检查点**:
- `/api/discussions/{id}/continue` 已存在
- 需确认上下文构建是否符合 Spec 要求

**改进点**:
```python
def _build_continuation_context(
    original: DiscussionState,
    stored: Discussion,
    follow_up: str,
    max_messages_per_agent: int = 2,
) -> str:
    """构建继续讨论的上下文"""
    context_parts = [
        "## 前序讨论上下文",
        "",
        f"### 原始话题: {original.topic}",
        "",
    ]

    # 添加摘要
    if stored.summary:
        context_parts.extend([
            "### 讨论总结",
            stored.summary[:2000],  # 限制长度
            "",
        ])

    # 提取每个角色的最后几条消息
    if stored.messages:
        context_parts.append("### 关键讨论内容")
        agent_messages: dict[str, list[str]] = {}
        for msg in stored.messages:
            if msg.agent_role not in agent_messages:
                agent_messages[msg.agent_role] = []
            agent_messages[msg.agent_role].append(msg.content[:500])

        for role, contents in agent_messages.items():
            # 取最后 N 条
            recent = contents[-max_messages_per_agent:]
            for content in recent:
                context_parts.append(f"**{role}**: {content}...")
        context_parts.append("")

    # 添加继续讨论部分
    context_parts.extend([
        "---",
        "",
        "## 继续讨论",
        "",
        "用户希望在以上讨论基础上，继续探讨以下问题：",
        "",
        f"**{follow_up}**",
    ])

    return "\n".join(context_parts)
```

**验证**:
- `cd backend && python -m pytest tests/test_discussion.py -v -k continue` → exit_code == 0

**输出文件**:
- `backend/src/api/routes/discussion.py` (更新)

---

### Task V2R-5.2: 添加继续讨论的讨论标记

**执行**:
- 更新 `backend/src/api/routes/discussion.py`
- `DiscussionState` 添加 `continued_from` 字段
- 响应中包含原讨论引用

```python
class DiscussionState(BaseModel):
    # ... 现有字段
    continued_from: str | None = None  # 原讨论 ID

class GetDiscussionResponse(BaseModel):
    # ... 现有字段
    continued_from: str | None = None
    is_continuation: bool = False
```

**验证**:
- `cd backend && python -c "from src.api.routes.discussion import DiscussionState; print('ok')"` → exit_code == 0

**输出文件**:
- `backend/src/api/routes/discussion.py` (更新)

---

### Task V2R-5.3: 前端继续讨论对话框

**执行**:
- 创建 `frontend/src/components/history/ContinueDiscussionModal.vue`
- 功能:
  - 显示原讨论议题
  - 显示原讨论摘要（如有）
  - 追加问题/方向输入框
  - 确认/取消按钮

**Props**:
```typescript
interface Props {
  visible: boolean
  discussion: DiscussionSummary | null
}

interface Emits {
  (e: 'confirm', followUp: string): void
  (e: 'close'): void
}
```

**样式**:
```
┌──────────────────────────────────────┐
│ 继续讨论                         [X] │
├──────────────────────────────────────┤
│                                      │
│ 原议题：角色养成系统设计             │
│                                      │
│ 原讨论摘要：                         │
│ 讨论了养成系统的三层结构设计...      │
│                                      │
│ ────────────────────────────────     │
│ 追加问题/方向：                      │
│ ┌──────────────────────────────┐    │
│ │ 想深入讨论装备强化的数值平衡  │    │
│ └──────────────────────────────┘    │
│                                      │
├──────────────────────────────────────┤
│                    [取消] [继续讨论]  │
└──────────────────────────────────────┘
```

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0

**输出文件**:
- `frontend/src/components/history/ContinueDiscussionModal.vue`

---

### Task V2R-5.4: 更新历史列表页添加继续按钮

**执行**:
- 更新 `frontend/src/views/HistoryView.vue`
- 在列表项添加"继续讨论"按钮
- 集成 `ContinueDiscussionModal`
- 点击确认后调用 API 并跳转

**列表项更新**:
```vue
<template>
  <div class="history-item">
    <div class="info">
      <h3>{{ item.topic }}</h3>
      <p>{{ item.summary }}</p>
      <span class="time">{{ formatTime(item.created_at) }}</span>
    </div>
    <div class="actions">
      <button @click="viewDetail(item.id)">查看详情</button>
      <button @click="playback(item.id)">回放</button>
      <button
        v-if="item.status === 'completed'"
        @click="openContinueModal(item)"
      >
        继续讨论
      </button>
    </div>
  </div>
</template>
```

**API 调用**:
```typescript
async function handleContinue(followUp: string) {
  const response = await api.post(`/discussions/${selectedItem.value.id}/continue`, {
    follow_up: followUp,
    rounds: 2,
  })

  // 跳转到新讨论
  router.push(`/discussion`)
}
```

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0
- 点击继续讨论可打开对话框
- 确认后跳转到新讨论

**输出文件**:
- `frontend/src/views/HistoryView.vue` (更新)

---

### Task V2R-5.5: 讨论页显示"续前讨论"标识

**执行**:
- 更新 `frontend/src/views/DiscussionView.vue`
- 如果讨论是继续的，显示"续前讨论"标识
- 可点击查看原讨论

**标识设计**:
```
┌─────────────────────────────────────────────┐
│ 📋 [继续] 角色养成系统设计 - 装备强化数值   │
│ ↳ 续前讨论：原议题 [查看原讨论]             │
├─────────────────────────────────────────────┤
│ ...                                         │
└─────────────────────────────────────────────┘
```

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0
- 续前讨论正确显示标识

**输出文件**:
- `frontend/src/views/DiscussionView.vue` (更新)
- `frontend/src/components/discussion/TopicCard.vue` (更新)

---

### Task V2R-5.6: 历史记录详情页添加继续按钮

**执行**:
- 更新 `frontend/src/views/HistoryDetailView.vue` 或回放页
- 在详情页/回放页添加"继续讨论"入口
- 复用 `ContinueDiscussionModal`

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0

**输出文件**:
- `frontend/src/views/HistoryDetailView.vue` 或相关页面 (更新)

---

### Task V2R-5.7: 主策划处理续前上下文

**执行**:
- 更新 `backend/src/agents/lead_planner.py`
- 在开场 prompt 中识别续前讨论
- 引导讨论基于原有结论深入

```python
def create_opening_prompt(
    self,
    topic: str,
    attachment: str | None = None,
) -> str:
    """创建开场 prompt"""
    # 检测是否是续前讨论
    is_continuation = attachment and "## 前序讨论上下文" in attachment

    if is_continuation:
        return f"""
作为主策划，这是一次续前讨论。

议题：{topic}

请仔细阅读前序讨论的上下文，然后：
1. 简要回顾之前的讨论结论
2. 明确本次讨论要深入的方向
3. 提出 2-3 个需要进一步探讨的问题
4. 点名相关角色参与讨论

参考资料：
{attachment}
"""
    else:
        # 原有逻辑
        ...
```

**验证**:
- `cd backend && python -c "from src.agents.lead_planner import LeadPlanner; print('ok')"` → exit_code == 0

**输出文件**:
- `backend/src/agents/lead_planner.py` (更新)

---

### Task V2R-5.8: 添加讨论链查询

**执行**:
- 更新 `backend/src/api/routes/discussion.py`
- 添加讨论链查询 API

```python
class DiscussionChainResponse(BaseModel):
    chain: list[DiscussionSummaryItem]  # 从最早到最新

@router.get("/{discussion_id}/chain", response_model=DiscussionChainResponse)
async def get_discussion_chain(discussion_id: str):
    """获取讨论链（原讨论 → 续前讨论 → ...）"""
    chain = []
    current_id = discussion_id

    # 向前追溯
    while current_id:
        discussion = get_discussion_state(current_id)
        if discussion is None:
            break
        chain.insert(0, discussion)
        current_id = discussion.continued_from

    # 向后查找续前讨论
    # ... 如需支持

    return DiscussionChainResponse(chain=chain)
```

**验证**:
- `cd backend && python -m pytest tests/test_discussion.py -v -k chain` → exit_code == 0

**输出文件**:
- `backend/src/api/routes/discussion.py` (更新)

---

### Task V2R-5.9: 前端讨论链展示

**执行**:
- 创建 `frontend/src/components/discussion/DiscussionChain.vue`
- 功能:
  - 显示讨论链（面包屑或时间线）
  - 点击可跳转到对应讨论

**样式**:
```
讨论链：
[原] 角色养成系统设计 → [续1] 装备强化数值 → [当前] 强化失败保护
```

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0

**输出文件**:
- `frontend/src/components/discussion/DiscussionChain.vue`

---

### Task V2R-5.10: 集成讨论链到详情页

**执行**:
- 更新 `frontend/src/views/DiscussionView.vue`
- 在议题卡片下方显示讨论链（如果存在）

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0
- 续前讨论显示完整讨论链

**输出文件**:
- `frontend/src/views/DiscussionView.vue` (更新)

## 验收标准

- [ ] 可从历史记录继续讨论 (Spec 验收)
- [ ] 继续对话框显示原议题和摘要
- [ ] 新讨论包含原讨论上下文
- [ ] 讨论页显示"续前讨论"标识
- [ ] 可查看原讨论
- [ ] 讨论链正确显示
- [ ] 主策划能识别续前讨论并合理引导
- [ ] TypeScript 无类型错误
