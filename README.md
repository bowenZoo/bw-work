# BW-Work: AI Game Design Team

多 Agent 协作系统，模拟游戏策划团队进行设计讨论。后端用 CrewAI 编排 AI Agent 讨论，前端用 Vue 3 实时展示讨论过程。

## 技术栈

- **后端**: Python 3.10+ / FastAPI / CrewAI / SQLite / Langfuse
- **前端**: Vue 3 / TypeScript / Vite / Tailwind CSS / Pinia
- **通信**: WebSocket 双通道（全局 + 讨论级）
- **部署**: Docker Compose

## 快速开始

### 环境准备

```bash
# 后端
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 前端
cd frontend
pnpm install
```

### 配置

复制并编辑环境变量：

```bash
cp backend/.env.example backend/.env
# 编辑 .env，填入 LLM API Key 等配置
```

### 启动开发服务

```bash
# 后端（端口 18000）
cd backend && .venv/bin/python -m uvicorn src.api.main:app --reload --port 18000

# 前端（端口 18001）
cd frontend && pnpm dev --port 18001
```

### Docker 部署

```bash
docker-compose up -d --build
```

## 架构概览

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
```

### 策划 Agent 团队

| Agent | 角色 |
|-------|------|
| LeadPlanner | 主持人，控制讨论节奏与 Checkpoint |
| SystemDesigner | 系统设计师 |
| NumberDesigner | 数值设计师 |
| PlayerAdvocate | 玩家代言人 |
| OperationsAnalyst | 运营分析师 |
| VisualConceptAgent | 视觉概念设计 |
| DocumentGenerator | 文档生成器 |
| Summarizer | 总结器 |

### 项目结构

```
bw-work/
├── backend/
│   ├── src/
│   │   ├── api/          # FastAPI 路由、WebSocket、中间件
│   │   ├── agents/       # Agent 基类与构建
│   │   ├── crew/         # CrewAI 讨论引擎核心
│   │   ├── memory/       # JSON+SQLite 混合记忆系统
│   │   ├── admin/        # 认证、配置管理、审计日志
│   │   ├── project/      # 项目管理、GDD 解析、输出
│   │   ├── image/        # AI 图片生成服务
│   │   ├── models/       # Pydantic 数据模型
│   │   ├── monitoring/   # Langfuse 集成
│   │   └── config/       # 角色配置、讨论风格、知识库
│   └── tests/
├── frontend/
│   └── src/
│       ├── views/        # 页面（大厅、讨论、项目、历史、Admin）
│       ├── components/   # Vue 组件
│       ├── composables/  # 组合式函数（useDiscussion, useLobby）
│       ├── stores/       # Pinia 状态管理
│       └── types/        # TypeScript 类型定义
├── docs/                 # Spec 文档和实施计划
├── data/                 # 运行时数据（gitignored）
└── docker-compose.yml
```

## Checkpoint 机制

讨论采用 Checkpoint 驱动交互（v2.0），Lead Planner 在每轮讨论结束时生成 Checkpoint：

| 类型 | 行为 |
|------|------|
| `silent` | 后台记录，不向前端推送 |
| `progress` | 推送非阻塞进展通报，讨论不暂停 |
| `decision` | 推送阻塞性决策卡片，讨论暂停等待制作人响应 |

## 开发

```bash
# 后端测试
cd backend && .venv/bin/python -m pytest tests/ -v

# 后端 Lint
cd backend && .venv/bin/ruff check src/

# 前端类型检查
cd frontend && pnpm type-check

# 前端构建
cd frontend && pnpm build
```

## 端口分配

| 服务 | 端口 |
|------|------|
| 后端 API | 18000 |
| 前端 Dev | 18001 |

## License

MIT
