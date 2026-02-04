# 实施计划索引

> **对应 Spec**: [docs/spec.md](../spec.md)
> **创建时间**: 2026-02-04
> **总任务数**: 52 个

## 执行批次

| 批次 | Plan | 任务数 | 状态 | 依赖 |
|------|------|--------|------|------|
| 1 | [plan-backend-core.md](./plan-backend-core.md) | 9 | pending | - |
| 2 | [plan-websocket.md](./plan-websocket.md) | 6 | pending | Batch 1 |
| 3 | [plan-memory.md](./plan-memory.md) | 8 | pending | Batch 1 |
| 3 | [plan-frontend.md](./plan-frontend.md) | 13 | pending | Batch 1 |
| 4 | [plan-history.md](./plan-history.md) | 7 | pending | Batch 3 |
| 5 | [plan-advanced.md](./plan-advanced.md) | 10 | pending | Batch 2, 3 |

## Plan 列表

### Batch 1: 后端核心 (基础)

- **[plan-backend-core.md](./plan-backend-core.md)** - 后端核心框架
  - Agent 角色定义（系统策划、数值策划、玩家代言人）
  - CrewAI 讨论编排
  - Langfuse 监控集成
  - FastAPI 基础 API
  - **9 个任务**，预计 2-3 天

### Batch 2: WebSocket 实时通信

- **[plan-websocket.md](./plan-websocket.md)** - WebSocket 服务
  - 连接管理器
  - 讨论实时推送
  - 消息协议定义
  - **6 个任务**，预计 1 天

### Batch 3: 可并行执行

- **[plan-memory.md](./plan-memory.md)** - 记忆系统
  - 讨论历史存储
  - 决策追踪
  - 语义检索（Chroma）
  - **8 个任务**，预计 2 天

- **[plan-frontend.md](./plan-frontend.md)** - 前端可视化
  - Vue 3 项目搭建
  - 聊天界面组件
  - Agent 状态面板
  - WebSocket 客户端
  - **13 个任务**，预计 3 天

### Batch 4: 历史与回放

- **[plan-history.md](./plan-history.md)** - 讨论历史
  - 历史列表浏览
  - 讨论回放功能
  - **7 个任务**，预计 1-2 天

### Batch 5: 高级功能

- **[plan-advanced.md](./plan-advanced.md)** - 高级特性
  - 人工介入节点
  - 讨论总结生成
  - 成本分析
  - 策划案生成
  - **10 个任务**，预计 2-3 天

## 依赖关系图

```
Batch 1: plan-backend-core (基础)
    │
    ├──→ Batch 2: plan-websocket
    │         │
    │         └──────────────────┐
    │                            │
    ├──→ Batch 3: plan-memory ───┼──→ Batch 5: plan-advanced
    │         │                  │
    │         └──→ Batch 4: plan-history
    │
    └──→ Batch 3: plan-frontend ─┘
```

## 里程碑对应

| 里程碑 | 包含 Plan | 预计工期 |
|--------|-----------|----------|
| Phase 1: MVP | plan-backend-core, plan-websocket | 3-4 天 |
| Phase 2: 可视化 | plan-frontend, plan-history | 4-5 天 |
| Phase 3: 记忆系统 | plan-memory | 2 天 |
| Phase 4: 高级功能 | plan-advanced | 2-3 天 |

## 下一步

```bash
# 开始执行第一个 Plan
/bwf-dev docs/plans/plan-backend-core.md
```

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-02-04 | 初始版本，生成 6 个 Plan |
