# Plan: 高级功能

> **模块**: advanced
> **优先级**: P2
> **对应 Spec**: docs/spec.md#2.2 (F-11, F-12), #2.5 (F-24, F-25), #2.6

## 目标

实现高级功能：
1. 人工介入节点
2. 讨论总结自动生成
3. 成本分析和执行追踪
4. 策划案文档生成

## 前置依赖

- `plan-backend-core.md` - 需要基础框架
- `plan-memory.md` - 需要记忆系统
- `plan-websocket.md` - 需要实时通信

## 技术方案

### 人工介入机制

**状态机定义**:

```
┌─────────┐  pause   ┌────────┐  resume/inject  ┌─────────┐
│ RUNNING │ ───────► │ PAUSED │ ──────────────► │ RUNNING │
└─────────┘          └────────┘                 └─────────┘
     │                                               │
     │ complete                                      │ complete
     ▼                                               ▼
┌──────────┐                                   ┌──────────┐
│ FINISHED │                                   │ FINISHED │
└──────────┘                                   └──────────┘

状态约束:
- RUNNING → PAUSED: 只能在 Agent 发言间隙暂停
- PAUSED → RUNNING: inject 后自动 resume，或直接 resume
- RUNNING → FINISHED: 讨论正常结束
- PAUSED 超时(可选): 30分钟无操作自动 FINISHED
```

**讨论流程**:
```
Agent A 发言 → Agent B 发言 → [人工介入点] → Agent C 发言
                                    ↓
                            用户输入意见
                                    ↓
                          注入为 "user" 消息
```

**注入消息结构**:
```python
injected_message = {
    "role": "user",           # 固定为 user，区别于 agent
    "content": user_input,
    "source": "intervention", # 标识来源为人工介入
    "timestamp": "...",
    "save_to_memory": True    # 记入讨论历史和记忆系统
}
```

### 成本追踪模型

```python
class CostMetrics:
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    estimated_cost: float  # USD
    model_breakdown: Dict[str, int]  # 按模型统计
```

## 任务清单

### Task 6.1: 实现人工介入 API

**执行**:
- 创建 `backend/src/api/routes/intervention.py`
- 实现 POST `/api/discussions/{id}/pause` - 暂停讨论
- 实现 POST `/api/discussions/{id}/inject` - 注入用户消息
- 实现 POST `/api/discussions/{id}/resume` - 继续讨论

**验证**:
- API 接口正常响应
- 讨论可暂停和继续

**输出文件**:
- `backend/src/api/routes/intervention.py`

---

### Task 6.2: 实现讨论暂停机制

**执行**:
- 更新 `backend/src/crew/discussion_crew.py`
- 添加暂停检查点
- 实现讨论状态持久化
- 支持从暂停点继续

**验证**:
- 讨论可在任意轮次暂停
- 暂停后可继续

**输出文件**:
- `backend/src/crew/discussion_crew.py` (更新)

---

### Task 6.3: 前端人工介入 UI

**执行**:
- 更新 `frontend/src/components/chat/InputBox.vue`
- 显示"暂停"按钮（讨论进行中）
- 暂停后显示输入框
- 提交后继续讨论

**验证**:
- UI 状态正确切换
- 用户输入正确注入讨论

**输出文件**:
- `frontend/src/components/chat/InputBox.vue` (更新)
- `frontend/src/components/chat/InterventionPanel.vue`

---

### Task 6.4: 实现讨论总结生成

**执行**:
- 创建 `backend/src/agents/summarizer.py`
- 定义总结 Agent
- 分析讨论内容，提取关键点
- 生成结构化总结

**验证**:
- 讨论结束后生成总结
- 总结包含关键决策点

**输出文件**:
- `backend/src/agents/summarizer.py`

---

### Task 6.5: 实现总结 API

**执行**:
- 更新 `backend/src/api/routes/discussion.py`
- 实现 POST `/api/discussions/{id}/summarize` - 生成总结
- 实现 GET `/api/discussions/{id}/summary` - 获取总结
- 总结自动保存到记忆系统

**验证**:
- 总结 API 正常工作
- 总结内容正确保存

**输出文件**:
- `backend/src/api/routes/discussion.py` (更新)

---

### Task 6.6: 实现执行追踪详情

**执行**:
- 更新 `backend/src/monitoring/langfuse_client.py`
- 记录每个 Agent 的执行步骤
- 记录思考过程和决策点
- 支持追踪 ID 关联

**验证**:
- Langfuse 显示详细执行链路
- 可追踪每个 Agent 的决策过程

**输出文件**:
- `backend/src/monitoring/langfuse_client.py` (更新)

---

### Task 6.7: 成本数据对接 (Langfuse)

> **设计决策**: 不单独实现成本追踪，直接复用 Langfuse 的 token 统计能力，避免两个数据源不一致。

**前置条件**:
- 讨论创建时，必须将 `discussion_id` 作为 Langfuse trace 的 `session_id` 或 `metadata` 存入
- 这样才能按 discussion_id 查询统计数据

**执行**:
- 更新 `backend/src/monitoring/langfuse_client.py`
- 封装 `get_session_cost(discussion_id)` 方法，通过 session_id 从 Langfuse 查询
- 创建 `backend/src/api/routes/monitoring.py`
- 实现 GET `/api/monitoring/cost/{discussion_id}` - 返回 token 统计

**API 响应结构**:
```python
{
    "discussion_id": "xxx",
    "total_tokens": 12345,
    "prompt_tokens": 8000,
    "completion_tokens": 4345,
    "model_breakdown": {
        "claude-3-sonnet": 10000,
        "claude-3-haiku": 2345
    },
    "source": "langfuse"  # 标明数据来源
}
```

**验证**:
- API 返回 Langfuse 的 token 统计数据
- 数据与 Langfuse Dashboard 一致

**输出文件**:
- `backend/src/monitoring/langfuse_client.py` (更新)
- `backend/src/api/routes/monitoring.py`

---

### Task 6.8: 实现策划案生成

**执行**:
- 创建 `backend/src/agents/document_generator.py`
- 根据讨论内容生成策划案
- 支持 Markdown 格式输出
- 保存到 `data/projects/{project_id}/drafts/`

**模板结构**:
```markdown
# {项目名} - 策划案

> 生成时间: {timestamp}
> 来源讨论: {discussion_id}
> 版本: {version}

## 概述

{一句话描述核心设计}

## 核心设计

### {设计点1}
{从讨论中提取的关键点}

### {设计点2}
...

## 争议与决策

| 议题 | 各方观点 | 最终决定 |
|------|----------|----------|
| ... | ... | ... |

## 待定事项

- [ ] {未解决的问题1}
- [ ] {未解决的问题2}

---
*本文档由 AI 策划团队自动生成*
```

**版本命名规则**:
- 文件名: `{discussion_id}-{yyyyMMdd-HHmm}.md`
- 示例: `disc_abc123-20240115-1430.md`
- 同一讨论多次生成会产生多个版本文件

**验证**:
- 策划案正确生成
- 格式符合模板规范
- 文件保存到正确位置

**输出文件**:
- `backend/src/agents/document_generator.py`

---

### Task 6.9: 策划案 API

**执行**:
- 创建 `backend/src/api/routes/document.py`
- 实现 POST `/api/discussions/{id}/generate-doc` - 生成策划案
- 实现 GET `/api/documents/{id}` - 获取策划案
- 实现 GET `/api/documents/{id}/versions` - 获取版本列表

**验证**:
- API 正常工作
- 版本管理正确

**输出文件**:
- `backend/src/api/routes/document.py`

---

### Task 6.10: 前端成本面板

**执行**:
- 创建 `frontend/src/components/monitoring/CostPanel.vue`
- 显示当前讨论的 Token 使用量
- 显示按模型的使用分布（不显示金额，避免价格变动问题）
- 创建 `frontend/src/api/monitoring.ts` 封装 API 调用

**数据来源**:
- GET `/api/monitoring/cost/{discussion_id}` - 获取 token 统计

**组件 Props**:
```typescript
interface CostPanelProps {
  discussionId: string
  refreshInterval?: number  // 轮询间隔，默认 5000ms
}
```

**显示内容**:
- 总 Token 数
- Prompt / Completion 分布
- 按模型的使用比例（饼图或条形图）

**验证**:
- 面板正确显示 token 信息
- 数据与 API 返回一致

**输出文件**:
- `frontend/src/components/monitoring/CostPanel.vue`
- `frontend/src/components/monitoring/index.ts`
- `frontend/src/api/monitoring.ts`

## 验收标准

- [ ] 用户可在讨论中插入意见 (Spec F-11)
- [ ] 讨论结束后自动生成总结 (Spec F-12)
- [ ] 可查看每次讨论的执行链路 (Spec AC-18)
- [ ] 成本数据准确记录 (Spec AC-19)
- [ ] 可从讨论生成结构化策划案 (Spec AC-20)
- [ ] 策划案保存在指定目录 (Spec AC-21)
