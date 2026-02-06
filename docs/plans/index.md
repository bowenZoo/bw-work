# 实施计划索引

> **对应 Spec**: [docs/spec.md](../spec.md), [docs/spec-admin.md](../spec-admin.md), [docs/spec-discussion-v2.md](../spec-discussion-v2.md)
> **创建时间**: 2026-02-04
> **更新时间**: 2026-02-06
> **总任务数**: 156 个

## 执行批次

| 批次 | Plan | 任务数 | 状态 | 依赖 |
|------|------|--------|------|------|
| 1 | [plan-backend-core.md](./plan-backend-core.md) | 9 | pending | - |
| 2 | [plan-websocket.md](./plan-websocket.md) | 6 | pending | Batch 1 |
| 3 | [plan-memory.md](./plan-memory.md) | 8 | pending | Batch 1 |
| 3 | [plan-frontend.md](./plan-frontend.md) | 13 | pending | Batch 1 |
| 4 | [plan-history.md](./plan-history.md) | 7 | pending | Batch 3 |
| 5 | [plan-advanced.md](./plan-advanced.md) | 10 | pending | Batch 2, 3 |
| 6 | [plan-image-generation.md](./plan-image-generation.md) | 15 | pending | Batch 2 |
| 7 | [plan-admin.md](./plan-admin.md) | 19 | pending | Batch 1, 3 |
| 8 | [plan-project-discussion.md](./plan-project-discussion.md) | 20 | pending | Batch 2, 3 |
| 9 | [plan-discussion-v2-dialog.md](./plan-discussion-v2-dialog.md) | 8 | pending | - |
| 10 | [plan-discussion-v2-global.md](./plan-discussion-v2-global.md) | 10 | pending | Batch 9 |
| 11 | [plan-discussion-v2-parallel.md](./plan-discussion-v2-parallel.md) | 8 | pending | Batch 10 |
| 12 | [plan-discussion-v2-agenda.md](./plan-discussion-v2-agenda.md) | 12 | pending | Batch 10, 11 |
| 13 | [plan-discussion-v2-resume.md](./plan-discussion-v2-resume.md) | 10 | pending | Batch 10 |

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

### Batch 6: 图像生成系统 (Phase 4)

- **[plan-image-generation.md](./plan-image-generation.md)** - 图像生成系统
  - 视觉概念 Agent（F-30）
  - Prompt 工程模块（F-31）
  - 多后端图像服务（F-32）- kie.ai、wenwen-ai、nanobanana、DALL-E
  - 风格模板系统（F-33）
  - 主动请求配图（F-34）
  - 图像存储管理（F-36）
  - 异步图像生成（F-37）
  - **15 个任务**，预计 3-4 天

### Batch 7: 管理后台系统

- **[plan-admin.md](./plan-admin.md)** - 管理后台系统
  - 管理员认证（JWT Token）
  - LLM API Key 加密管理
  - Langfuse 监控配置
  - 图像服务配置
  - 配置热更新
  - 操作日志审计
  - **19 个任务**，预计 4-5 天

### Batch 8: 项目级策划讨论 (Phase 5)

- **[plan-project-discussion.md](./plan-project-discussion.md)** - 项目级策划讨论
  - GDD 上传与解析（F-38, F-39）- 支持 Markdown/PDF/Word
  - 模块自动识别（F-40）- AI 识别 GDD 中的功能模块
  - 批量模块选择（F-41）- 用户选择模块并设置讨论顺序
  - 依次自动讨论（F-42）- 按顺序自动进行各模块讨论
  - 讨论断点恢复（F-43）- 支持中断后从断点继续
  - 项目级记忆（F-44）- 跨模块共享上下文，保持一致性
  - 策划案生成（F-45）- 每个模块生成结构化策划案
  - 策划案汇总（F-46）- 项目级汇总文档
  - 讨论进度追踪（F-47）- 实时显示讨论进度
  - **20 个任务**，预计 5-6 天

### Batch 9-13: 讨论系统 V2 重构

> 对应 Spec: [docs/spec-discussion-v2.md](../spec-discussion-v2.md)

- **[plan-discussion-v2-dialog.md](./plan-discussion-v2-dialog.md)** - 精简对话与议题展示
  - Agent Prompt 优化（限制 200 字）
  - 议题卡片组件
  - 附件预览 Modal
  - 用户参与输入框
  - 主策划回应用户消息
  - **8 个任务**，预计 1-2 天

- **[plan-discussion-v2-global.md](./plan-discussion-v2-global.md)** - 全局单例讨论
  - 全局讨论状态管理
  - 全局讨论 API（current）
  - WebSocket 全局广播重构
  - 前端全局讨论 Composable
  - 观看人数统计
  - **10 个任务**，预计 2-3 天

- **[plan-discussion-v2-parallel.md](./plan-discussion-v2-parallel.md)** - 并行发言机制
  - 角色点名解析器
  - Agent 异步支持
  - 并行讨论轮次
  - 消息序号排序
  - **8 个任务**，预计 2-3 天

- **[plan-discussion-v2-agenda.md](./plan-discussion-v2-agenda.md)** - 议程管理与圆桌 UI
  - 议程数据模型
  - 主策划生成议程
  - 议题小结生成
  - 圆桌布局组件
  - 当前发言组件
  - 历史记录筛选
  - **12 个任务**，预计 3-4 天

- **[plan-discussion-v2-resume.md](./plan-discussion-v2-resume.md)** - 讨论恢复
  - 继续讨论 API 完善
  - 继续讨论对话框
  - 讨论链查询与展示
  - 主策划处理续前上下文
  - **10 个任务**，预计 2 天

## 依赖关系图

```
Batch 1: plan-backend-core (基础)
    │
    ├──→ Batch 2: plan-websocket
    │         │
    │         ├──────────────────┐
    │         │                  │
    │         └──→ Batch 6: plan-image-generation
    │
    ├──→ Batch 3: plan-memory ───┼──→ Batch 5: plan-advanced
    │         │                  │
    │         │                  ├──→ Batch 8: plan-project-discussion
    │         │                  │
    │         └──→ Batch 4: plan-history
    │
    ├──→ Batch 3: plan-frontend ─┼──→ Batch 7: plan-admin
    │                            │
    └────────────────────────────┘

独立分支（讨论系统 V2）：

Batch 9: plan-discussion-v2-dialog (可独立执行)
    │
    └──→ Batch 10: plan-discussion-v2-global
              │
              ├──→ Batch 11: plan-discussion-v2-parallel
              │         │
              │         └──→ Batch 12: plan-discussion-v2-agenda
              │
              └──→ Batch 13: plan-discussion-v2-resume
```

## 里程碑对应

| 里程碑 | 包含 Plan | 预计工期 |
|--------|-----------|----------|
| Phase 1: MVP | plan-backend-core, plan-websocket | 3-4 天 |
| Phase 2: 可视化 | plan-frontend, plan-history | 4-5 天 |
| Phase 3: 记忆系统 | plan-memory | 2 天 |
| Phase 4: 图像生成系统 | plan-image-generation | 3-4 天 |
| Phase 5: 项目级策划讨论 | plan-project-discussion | 5-6 天 |
| Phase 6: 高级功能 | plan-advanced | 2-3 天 |
| Phase 7: 管理后台 | plan-admin | 4-5 天 |
| **Phase 8: 讨论系统 V2** | plan-discussion-v2-* (5 个 Plan) | **10-14 天** |

## 讨论系统 V2 执行顺序

```bash
# Phase 8.1: 精简对话（可独立执行）
/bwf-dev docs/plans/plan-discussion-v2-dialog.md

# Phase 8.2: 全局单例
/bwf-dev docs/plans/plan-discussion-v2-global.md

# Phase 8.3: 并行发言
/bwf-dev docs/plans/plan-discussion-v2-parallel.md

# Phase 8.4: 议程管理（依赖 8.2, 8.3）
/bwf-dev docs/plans/plan-discussion-v2-agenda.md

# Phase 8.5: 讨论恢复（依赖 8.2）
/bwf-dev docs/plans/plan-discussion-v2-resume.md
```

## 下一步

```bash
# 开始执行第一个 Plan
/bwf-dev docs/plans/plan-backend-core.md

# 或从讨论系统 V2 开始（独立分支）
/bwf-dev docs/plans/plan-discussion-v2-dialog.md
```

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-02-04 | 初始版本，生成 6 个 Plan |
| 2026-02-05 | 新增 plan-image-generation.md (15 tasks)，对应 Spec 2.7 图像生成系统 |
| 2026-02-05 | 新增 plan-admin.md (19 tasks)，对应 Spec docs/spec-admin.md 管理后台系统 |
| 2026-02-05 | 新增 plan-project-discussion.md (20 tasks)，对应 Spec 2.8 项目级策划讨论 |
| 2026-02-06 | 新增讨论系统 V2 系列 Plan (5 个 Plan, 48 tasks)，对应 Spec docs/spec-discussion-v2.md |
