# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

多 Agent 协作系统，模拟游戏策划团队进行设计讨论。后端用 CrewAI 编排 AI Agent 讨论，前端用 Vue 3 实时展示讨论过程。

**技术栈**: CrewAI + FastAPI + Vue 3 + Vite + Tailwind CSS + WebSocket + SQLite + Langfuse

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

# E2E 测试（需要前后端已启动）
cd frontend && pnpm test:e2e
cd frontend && pnpm test:e2e:ui    # 带调试 UI

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
| 项目路由 | `backend/src/api/routes/project.py` | 项目管理、GDD 上传解析 |
| 图片路由 | `backend/src/api/routes/image.py` | AI 概念图生成 |
| 讨论引擎 | `backend/src/crew/discussion_crew.py` | CrewAI 编排核心，暂停/恢复/checkpoint 状态机 |
| Agent 基类 | `backend/src/agents/base.py` | 从 YAML 加载角色配置，构建 CrewAI Agent |
| WebSocket 管理 | `backend/src/api/websocket/manager.py` | ConnectionManager (per-discussion) + GlobalConnectionManager |
| 记忆系统 | `backend/src/memory/discussion_memory.py` | JSON 文件 (数据源) + SQLite (索引) 混合存储 |
| Admin 模块 | `backend/src/admin/` | JWT 认证、API Key 加密存储、配置管理、审计日志 |
| 项目模块 | `backend/src/project/` | GDD 解析（MD/PDF/DOCX）、讨论执行器、设计文档输出 |
| 图片服务 | `backend/src/image/` | 多后端图片生成（OpenAI/兼容API）、提示词工程、风格管理 |
| 数据模型 | `backend/src/models/` | Pydantic 模型（Agenda、DocPlan、Checkpoint） |
| 监控 | `backend/src/monitoring/langfuse_client.py` | Langfuse 集成，LLM 调用追踪 |
| 角色配置 | `backend/src/config/roles/*.yaml` | Agent 的 role/goal/backstory 定义 |
| 讨论风格 | `backend/src/config/discussion_styles.yaml` | Socratic / Directive / Debate 三种风格 |
| 游戏知识库 | `backend/src/config/knowledge/game_industry.yaml` | 行业指标基准（留存、付费、抽卡等）|

### 前端核心模块

**UI 库**: Tailwind CSS + lucide-vue-next 图标 + Marked（markdown 渲染）+ DOMPurify（XSS 防护）

**路径别名**: `@` → `frontend/src/`（配置在 `vite.config.ts`）

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

**页面视图**: HomeView（大厅）、DiscussionView（讨论详情）、ProjectView（项目管理）、HistoryView（历史记录）、Admin 后台（登录/仪表盘/LLM配置/图片配置/讨论配置/Langfuse配置/审计日志）

### WebSocket 双通道

- **全局通道** `/ws/discussion` — 大厅页面，接收活跃讨论列表和观众数
- **讨论通道** `/ws/{discussion_id}` — 讨论详情页，接收消息、状态、checkpoint 等实时事件

### 两层 Agent 架构

| 层 | 位置 | 用途 |
|---|------|------|
| 开发 Agents | `.claude/agents/` | 辅助开发本项目（slash 命令调用） |
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

### Lint 与格式化

- Ruff: line-length=88, 规则 `E,F,I,N,W,UP`（忽略 E501），配置在 `backend/pyproject.toml`
- pytest: asyncio_mode=auto, pythonpath=["."]，**必须在 `backend/` 目录下运行**
- 前端类型检查: `vue-tsc --noEmit`

### Git 提交

格式: `feat:` / `fix:` / `docs:` / `refactor:` / `style:` / `test:`

### Agent 定义

每个策划 Agent 必须包含 `role`、`goal`、`backstory`、`tools`，配置在 `backend/src/config/roles/` 的 YAML 文件中。

### E2E 测试规范（Playwright）

测试文件位于 `frontend/e2e/`，使用 `frontend/e2e/fixtures.ts` 提供的 `authedPage` fixture。

**什么时候必须写测试：**

| 变更类型 | 操作 |
|----------|------|
| 新增页面/路由（新 `.vue` 文件在 `views/`） | 在 `e2e/` 创建对应 `xxx.spec.ts`，覆盖页面加载和核心交互 |
| 新增弹窗/对话框 | 在对应 spec 文件添加「打开→交互→关闭」测试用例 |
| 新增后端 API 端点 | 在对应 spec 文件添加 API 调用测试（直接用 `request` fixture） |
| Bug 修复 | 添加验证该 bug 不再出现的回归测试 |
| 修改认证/权限逻辑 | 在 `auth.spec.ts` 添加覆盖新逻辑的用例 |

**文件对应关系：**
- `HallView.vue` 相关 → `e2e/hall.spec.ts`
- `ProjectDetailView.vue` 相关 → `e2e/project.spec.ts`
- `DiscussionView.vue` 相关 → `e2e/discussion.spec.ts`
- 认证相关 → `e2e/auth.spec.ts`
- 新页面 → 新建 `e2e/<page-name>.spec.ts`

**测试编写规则：**
- 使用 `authedPage` fixture（已登录状态），避免在每个测试重复登录
- 测试结束后必须清理创建的数据（`afterEach` 中调用 API 删除）
- 不测试真实 LLM 调用，只测试 UI 结构和 API 响应格式
- Selector 优先用语义化文本（`filter({ hasText: '...' })`），次选 CSS class

**运行命令：**
```bash
cd frontend
pnpm test:e2e                    # 无头运行全部测试
pnpm test:e2e:ui                 # 带 UI 调试器（推荐调试时用）
pnpm test:e2e:headed             # 有头模式（能看到浏览器）
pnpm test:e2e e2e/hall.spec.ts   # 只跑某个文件
pnpm test:e2e --grep "弹窗"      # 只跑匹配名称的测试
pnpm test:e2e:report             # 查看上次运行的 HTML 报告
```

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

## 部署

- **本地 Docker**: `docker-compose up -d --build`，数据卷挂载 `backend/data` 和 `data/admin`
- **远程部署**: `/deploy` 技能，rsync 同步到服务器后 Docker 重建
- Docker 中前端构建为静态文件由 nginx 代理（端口映射 18001→80）

## 开发工作流（Spec-Driven）

```bash
/bwf-spec                              # 1. 生成规格文档 → docs/spec.md
/bwf-plan                              # 2. 生成实施计划 → docs/plans/plan-*.md
/bwf-dev docs/plans/plan-backend.md    # 3. 按 Plan 自动开发
/bwf-dev --continue                    # 4. 中断后继续
```

Plan 中验证命令必须使用 settings.local.json 中已授权的格式（`python -m pytest`、`ruff check`、`tsc --noEmit` 等）。

## 开发 Agent 调用指南

> **重要**：`.claude/agents/` 下的自定义 Agent 只能通过 `/agent-name` **斜杠命令**调用，**不能**通过 `Agent` 工具的 `subagent_type` 参数调用。

### Agent 列表

| 斜杠命令 | 触发时机 |
|---------|---------|
| `/spec-writer` | 收到新功能需求，开发开始**之前**，将需求转化为 `docs/spec.md` |
| `/backend-dev` | 实现 FastAPI 路由、CrewAI 逻辑、WebSocket、数据库操作 |
| `/frontend-dev` | 实现 Vue 3 组件、Pinia store、实时 UI 交互 |
| `/test-engineer` | 新功能开发完成后补充测试；Bug 修复后写回归测试 |
| `/code-reviewer` | PR 合并前、大型功能开发完成后做质量/安全审查 |
| `/prompt-engineer` | 调整策划 Agent 角色配置、优化讨论质量、新增讨论风格 |

### 标准开发流程

```
需求 → /spec-writer (生成 spec.md)
     → /backend-dev (后端实现)
     → /frontend-dev (前端实现)   ← 可与后端并行
     → /test-engineer (补充测试)
     → /code-reviewer (审查)
     → git commit
```

### 测试工作流

每次新功能或 Bug 修复完成后，调用 `/test-engineer`：

```bash
# 后端单元/集成测试
cd backend && .venv/bin/python -m pytest tests/ -v

# E2E 测试（需要前后端已启动：后端 18000，前端 18001）
cd frontend && pnpm test:e2e e2e/<对应spec文件>.spec.ts

# 全部 E2E
cd frontend && pnpm test:e2e
```

`/test-engineer` 会根据变更类型自动判断：
- 新增 API 端点 → 写 pytest 测试
- 新增页面/组件 → 写 Playwright E2E 测试
- Bug 修复 → 写回归测试防止复现

## 配置说明

- `.claude/settings.local.json` 是团队统一配置（已提交），非个人私有文件
- 个人覆盖用 `~/.claude/settings.json`（全局优先级更高）
- 讨论数据保存在 `data/projects/{project_id}/`
- 后端虚拟环境: `backend/.venv/`
