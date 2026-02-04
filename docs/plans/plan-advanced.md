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

```
讨论流程:
Agent A 发言 → Agent B 发言 → [人工介入点] → Agent C 发言
                                    ↓
                            用户输入意见
                                    ↓
                          注入为 "用户" 消息
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

### Task 6.7: 实现成本分析

**执行**:
- 创建 `backend/src/monitoring/cost_tracker.py`
- 统计 Token 使用量
- 按模型计算成本
- 提供成本报告 API

**验证**:
- Token 使用量正确统计
- 成本计算准确

**输出文件**:
- `backend/src/monitoring/cost_tracker.py`
- `backend/src/api/routes/monitoring.py`

---

### Task 6.8: 实现策划案生成

**执行**:
- 创建 `backend/src/agents/document_generator.py`
- 根据讨论内容生成策划案模板
- 支持 Markdown 格式输出
- 保存到 `data/projects/{id}/drafts/`

**验证**:
- 策划案正确生成
- 格式规范，内容完整

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
- 显示预估成本
- 显示按 Agent 的使用分布

**验证**:
- 面板正确显示成本信息
- 数据实时更新

**输出文件**:
- `frontend/src/components/monitoring/CostPanel.vue`
- `frontend/src/components/monitoring/index.ts`

## 验收标准

- [ ] 用户可在讨论中插入意见 (Spec F-11)
- [ ] 讨论结束后自动生成总结 (Spec F-12)
- [ ] 可查看每次讨论的执行链路 (Spec AC-18)
- [ ] 成本数据准确记录 (Spec AC-19)
- [ ] 可从讨论生成结构化策划案 (Spec AC-20)
- [ ] 策划案保存在指定目录 (Spec AC-21)
