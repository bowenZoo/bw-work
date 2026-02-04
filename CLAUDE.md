# 游戏策划 AI 团队

> AI 策划团队，支持多角色讨论、方案迭代、文档产出

## 项目概述

这是一个多 Agent 协作系统，模拟游戏策划团队进行设计讨论。

## 技术栈

| 层级 | 技术 |
|------|------|
| Agent 编排 | CrewAI |
| 监控追踪 | Langfuse |
| 前端 | Vue 3 + Vite (参考 ChatDev) |
| 后端 | Python + FastAPI |
| 记忆存储 | SQLite + Chroma |
| 实时通信 | WebSocket |

## 目录结构

```
bw-work/
├── CLAUDE.md              # 本文件
├── README.md              # 项目说明
├── .claude/               # Claude Code 开发配置
│   ├── agents/            # 开发工作流 Agents（辅助开发本项目）
│   │   ├── spec-generator.md    # 规格文档生成
│   │   ├── plan-generator.md    # 实施计划生成
│   │   ├── code-reviewer.md     # 代码审核
│   │   └── auto-developer.md    # 自动开发
│   ├── skills/            # 开发命令
│   │   ├── bwf-spec/      # /bwf-spec - 生成规格文档
│   │   ├── bwf-plan/      # /bwf-plan - 生成实施计划
│   │   └── bwf-dev/       # /bwf-dev - 自动开发闭环
│   └── settings.local.json
├── .bwf/                  # 开发流程运行时数据
│   └── progress/          # 任务进度持久化
├── docs/                  # 项目文档
│   ├── spec.md            # 规格文档（由 /bwf-spec 生成）
│   └── plans/             # 实施计划（由 /bwf-plan 生成）
│       ├── index.md       # Plan 索引
│       └── plan-*.md      # 各模块 Plan
├── backend/               # Python 后端
│   └── src/
│       ├── agents/        # 策划团队 Agents（CrewAI 定义）
│       │   ├── system_designer.py   # 系统策划
│       │   ├── number_designer.py   # 数值策划
│       │   └── player_advocate.py   # 玩家代言人
│       ├── memory/        # 记忆系统
│       ├── api/           # FastAPI 接口
│       └── config/        # 角色配置 (YAML)
├── frontend/              # Vue 3 前端
│   └── src/
└── data/                  # 数据存储
    ├── projects/          # 项目记忆
    └── knowledge/         # 知识库
```

## 两层 Agent 说明

| 层 | 位置 | 用途 |
|---|------|------|
| 开发 Agents | `.claude/agents/` | 辅助开发本项目（规格、计划、代码审核） |
| 策划 Agents | `backend/src/agents/` | 实际的策划团队（系统策划、数值策划等） |

## 开发规范

### 命名规范

- Python: snake_case
- TypeScript: camelCase
- 组件: PascalCase
- 文件: kebab-case

### Git 提交规范

```
feat: 新功能
fix: Bug 修复
docs: 文档更新
refactor: 重构
style: 代码风格
test: 测试
```

### Agent 定义规范

每个 Agent 必须包含：
- `role`: 角色名称
- `goal`: 角色目标
- `backstory`: 背景设定
- `tools`: 可用工具列表

## 开发流程

```bash
# 1. 生成规格文档
/bwf-spec

# 2. 生成实施计划
/bwf-plan

# 3. 自动开发
/bwf-dev docs/plans/plan-backend.md

# 4. 从中断处继续
/bwf-dev --continue
```

## 最小流程示例

以下是一个可跑通的最小闭环示例，用于验证开发流程：

### 文件结构

```
docs/
├── spec.md                    # Spec 模板（已存在）
└── plans/
    ├── index.md               # Plan 索引（已存在）
    └── plan-example.md        # 示例 Plan（已存在）
.bwf/
└── progress/                  # 进度持久化目录
```

### 示例 Task（来自 plan-example.md）

```markdown
### Task 1.1: 创建示例文件

**执行**:
- 创建 `backend/src/example.py`
- 实现 hello 函数

**验证**:
- `python -m pytest tests/test_example.py -v` → exit_code == 0
```

### 验证命令规范

Plan 中的验证命令必须使用以下格式（已在 settings.local.json 中授权）：

| 工具 | 推荐写法 | 说明 |
|------|----------|------|
| pytest | `python -m pytest` 或 `pytest` | 两者均可 |
| ruff | `ruff check` | 代码检查 |
| mypy | `python -m mypy` 或 `mypy` | 类型检查 |
| black | `black --check` | 格式检查 |
| eslint | `eslint` | JS/TS 检查 |
| tsc | `tsc --noEmit` | TS 编译检查 |

### 快速验证流程

```bash
# 1. 查看示例 Plan
cat docs/plans/plan-example.md

# 2. 执行示例开发（测试流程）
/bwf-dev docs/plans/plan-example.md --task=1.1

# 3. 检查进度文件
cat .bwf/progress/plan-example.yaml
```

## 运行时命令

```bash
# 启动后端
cd backend && python -m uvicorn api.main:app --reload

# 启动前端
cd frontend && pnpm dev
```

## 参考项目

位于 `github/` 目录：
- `crewAI/` - Agent 编排核心
- `ChatDev/` - 前端可视化参考
- `openclaw/` - 记忆系统参考
- `langfuse/` - 监控追踪

## 注意事项

1. 每次讨论自动保存到 `data/projects/{project_id}/`
2. 策划案版本管理在 `data/projects/{project_id}/drafts/`
3. 决策记录在 `data/projects/{project_id}/decisions.md`
