# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

多 Agent 协作系统，模拟游戏策划团队进行设计讨论。后端用 CrewAI 编排 AI Agent 讨论，前端用 Vue 3 实时展示讨论过程。

**技术栈**: CrewAI + FastAPI + Vue 3 + Vite + WebSocket + SQLite + Langfuse

## 常用命令

```bash
# 启动后端（端口 18000）
cd backend && .venv/bin/python -m uvicorn src.api.main:app --reload --port 18000

# 启动前端（端口 18001）
cd frontend && pnpm dev --port 18001

# 一键重启前后端（推荐）
/restart

# 运行后端测试
cd backend && .venv/bin/python -m pytest tests/test_discussion_v2_fixes.py -v

# 运行单个测试
cd backend && .venv/bin/python -m pytest tests/test_discussion_v2_fixes.py::test_name -v

# 后端 Lint
cd backend && .venv/bin/ruff check src/

# 前端类型检查
cd frontend && pnpm type-check

# 前端构建
cd frontend && pnpm build

# Docker 部署
docker-compose up -d --build
```

## 架构概览

### 数据流

```
用户创建讨论 → POST /api/discussions/current
                    ↓
          ThreadPoolExecutor 启动 DiscussionCrew
                    ↓
          CrewAI crew.kickoff() 按轮次执行
                    ↓
          每个 Agent 发言 → 保存到 DiscussionMemory (JSON+SQLite)
                         → WebSocket 广播到前端
                    ↓
          每轮结束 Lead Planner 生成 Checkpoint
                    ↓
          PROGRESS → 前端展示 ProgressNotice（非阻塞）
          DECISION → 前端展示 DecisionCard → 制作人响应 → 讨论继续
                    ↓
          前端 useDiscussion composable 接收并更新 Pinia store
```

### 后端核心模块

| 模块 | 路径 | 职责 |
|------|------|------|
| API 入口 | `backend/src/api/main.py` | FastAPI app、中间件、lifespan 启停 |
| 讨论路由 | `backend/src/api/routes/discussion.py` | 讨论 CRUD、启动、暂停/恢复 |
| Checkpoint 路由 | `backend/src/api/routes/checkpoint.py` | 决策响应、制作人发言、checkpoint 查询 |
| 讨论引擎 | `backend/src/crew/discussion_crew.py` | CrewAI 编排核心，暂停/恢复/checkpoint 状态机 |
| Agent 基类 | `backend/src/agents/base.py` | 从 YAML 加载角色配置，构建 CrewAI Agent |
| WebSocket 管理 | `backend/src/api/websocket/manager.py` | ConnectionManager (per-discussion) + GlobalConnectionManager |
| 记忆系统 | `backend/src/memory/discussion_memory.py` | JSON 文件 (数据源) + SQLite (索引) 混合存储 |
| 角色配置 | `backend/src/config/roles/*.yaml` | Agent 的 role/goal/backstory 定义 |
| 讨论风格 | `backend/src/config/discussion_styles.yaml` | Socratic / Directive / Debate 三种风格 |
| 游戏知识库 | `backend/src/config/knowledge/game_industry.yaml` | 行业指标基准（留存、付费、抽卡等）|

### 前端核心模块

| 模块 | 路径 | 职责 |
|------|------|------|
| 讨论 composable | `frontend/src/composables/useDiscussion.ts` | 讨论全生命周期：创建、WebSocket 连接、消息分发 |
| 大厅 composable | `frontend/src/composables/useLobby.ts` | 全局 WebSocket，活跃讨论列表，观众计数 |
| 讨论 store | `frontend/src/stores/discussion.ts` | Pinia 讨论状态 |
| Agent store | `frontend/src/stores/agents.ts` | Agent 状态（thinking/speaking/idle/writing） |
| 类型定义 | `frontend/src/types/index.ts` | 所有 TypeScript 接口，与后端响应结构对齐 |
| DecisionCard | `frontend/src/components/chat/DecisionCard.vue` | Checkpoint DECISION 卡片，支持选项和自由输入 |
| ProducerInput | `frontend/src/components/discussion/ProducerInput.vue` | 制作人发言输入（节流 3 条/分钟）|
| DecisionLogPanel | `frontend/src/components/discussion/DecisionLogPanel.vue` | 决策历史时间线面板 |

### WebSocket 双通道

- **全局通道** `/ws/discussion` — 大厅页面，接收活跃讨论列表和观众数
- **讨论通道** `/ws/{discussion_id}` — 讨论详情页，接收消息、状态、checkpoint 等实时事件

### 两层 Agent 架构

| 层 | 位置 | 用途 |
|---|------|------|
| 开发 Agents | `.claude/agents/` | 辅助开发本项目（spec、plan、code review） |
| 策划 Agents | `backend/src/agents/` | 业务运行时的 AI 策划角色 |

策划 Agent 列表：LeadPlanner（主持）、SystemDesigner、NumberDesigner、PlayerAdvocate、OperationsAnalyst、VisualConceptAgent、DocumentGenerator、Summarizer

### 并发模型

- 讨论在 `ThreadPoolExecutor` 中**同步**运行 `crew.kickoff()`
- FastAPI 异步处理 HTTP/WebSocket
- `broadcast_sync()` 通过存储的 event loop 引用桥接 sync→async
- `_discussion_semaphore` 限制并发讨论数（默认 2）

## Checkpoint 机制（v2.0）

Lead Planner 在每轮讨论结束时生成 Checkpoint，有三种类型：

| 类型 | 行为 |
|------|------|
| `silent` | 后台记录，不向前端推送 |
| `progress` | 推送非阻塞进展通报（ProgressNotice），讨论不暂停 |
| `decision` | 推送阻塞性决策卡片（DecisionCard），讨论暂停等待制作人响应 |

**关键 API**:
- `GET /api/discussions/{id}/checkpoints` — 获取所有 checkpoint
- `POST /api/discussions/{id}/checkpoint/{checkpoint_id}/respond` — 响应决策（`option_id` 或 `free_input`）
- `POST /api/discussions/{id}/producer-message` — 制作人直接发言

## 开发规范

### 命名

- Python: snake_case | TypeScript: camelCase | Vue 组件: PascalCase | 文件名: kebab-case

### Git 提交

格式: `feat:` / `fix:` / `docs:` / `refactor:` / `style:` / `test:`

### Agent 定义

每个策划 Agent 必须包含 `role`、`goal`、`backstory`、`tools`，配置在 `backend/src/config/roles/` 的 YAML 文件中。

## 关键陷阱

### CrewAI 遥测阻塞

`crew.kickoff()` 在 ThreadPoolExecutor 中会因 telemetry 挂起。**必须**在 import crewai 之前设置环境变量：
```python
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TESTING"] = "true"
```
已在 `backend/src/api/main.py` 顶部设置。

### WebSocket 路由顺序

FastAPI 中 `/ws/{discussion_id}` 会吞掉 `/ws/discussion`。**固定路径路由必须注册在参数路由之前**。见 `backend/src/api/websocket/handlers.py`。

### 僵尸讨论

服务器重启后 "running" 状态的讨论无后台任务。`main.py` lifespan 启动时会清理这些讨论。创建新讨论时也会检测 30 分钟超时。

### Context 无限膨胀

`run_orchestrated()`/`run_dynamic()` 中累加 context 会导致 token 爆炸。使用 `_build_windowed_context()` 构建三层结构（议题 + 历史摘要 + 当前轮），控制在 ~4-8K tokens。见 `backend/src/crew/discussion_crew.py`。

## 端口分配

| 服务 | 端口 |
|------|------|
| 后端 API | 18000 |
| 前端 Dev | 18001 |

前端 `vite.config.ts` 配置了 `/api` → `localhost:18000` 和 `/ws` → `ws://localhost:18000` 代理。

## 开发工作流（Spec-Driven）

```bash
/bwf-spec                              # 1. 生成规格文档 → docs/spec.md
/bwf-plan                              # 2. 生成实施计划 → docs/plans/plan-*.md
/bwf-dev docs/plans/plan-backend.md    # 3. 按 Plan 自动开发
/bwf-dev --continue                    # 4. 中断后继续
```

Plan 中验证命令必须使用 settings.local.json 中已授权的格式（`python -m pytest`、`ruff check`、`tsc --noEmit` 等）。

## 配置说明

- `.claude/settings.local.json` 是团队统一配置（已提交），非个人私有文件
- 个人覆盖用 `~/.claude/settings.json`（全局优先级更高）
- 讨论数据保存在 `data/projects/{project_id}/`
- 后端虚拟环境: `backend/.venv/`
