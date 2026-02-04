# 游戏策划 AI 团队

一个可视化的多 Agent 协作系统，用于游戏策划讨论和方案产出。

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                      策划团队系统                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌─────────────┐     WebSocket      ┌─────────────────┐   │
│   │   CrewAI    │ ─────────────────► │   Vue3 前端     │   │
│   │  (Python)   │    事件流推送       │  (参考ChatDev)  │   │
│   └──────┬──────┘                    └─────────────────┘   │
│          │                                                  │
│          ▼                                                  │
│   ┌─────────────┐                                          │
│   │  Langfuse   │  ← 追踪、调试、成本分析                   │
│   └─────────────┘                                          │
│          │                                                  │
│          ▼                                                  │
│   ┌─────────────────────────────────────────────────────┐  │
│   │  记忆系统 (参考 OpenClaw)                            │  │
│   │  • 项目记忆 - 讨论历史、设计决策                      │  │
│   │  • 角色记忆 - 每个 Agent 的风格和学习                 │  │
│   │  • 知识库 - 设计规范、竞品分析                        │  │
│   └─────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 策划角色

| 角色 | 职责 | 关注点 |
|------|------|--------|
| 系统策划 | 玩法循环、系统设计 | 有趣、自洽 |
| 数值策划 | 平衡性、经济系统 | 留存、付费 |
| 关卡策划 | 内容节奏、难度曲线 | 体验感 |
| 叙事策划 | 世界观、剧情 | 沉浸感 |
| 玩家代言人 | 模拟玩家视角 | 找问题 |

## 参考项目

```
github/
├── crewAI/      # 核心：Agent 编排框架
├── ChatDev/     # 参考：前端可视化 (Vite + Vue3)
├── openclaw/    # 参考：记忆系统设计
├── langfuse/    # 核心：Agent 监控追踪
└── MetaGPT/     # 参考：角色设计、结构化输出
```

## 目录结构

```
bw-work/
├── CLAUDE.md                    # Claude Code 项目配置
├── README.md                    # 本文件
├── .claude/                     # 开发工作流配置
│   ├── settings.local.json      # 权限配置
│   ├── agents/                  # 开发 Agents（辅助开发本项目）
│   │   ├── spec-generator.md    # 规格文档生成
│   │   ├── plan-generator.md    # 实施计划生成
│   │   ├── code-reviewer.md     # 代码审核
│   │   └── auto-developer.md    # 自动开发
│   └── skills/                  # 开发命令
│       ├── bwf-spec/SKILL.md    # /bwf-spec - 生成规格文档
│       ├── bwf-plan/SKILL.md    # /bwf-plan - 生成实施计划
│       └── bwf-dev/SKILL.md     # /bwf-dev - 自动开发闭环
├── github/                      # 参考项目
│   ├── crewAI/                  # Agent 编排框架
│   ├── ChatDev/                 # 前端可视化参考
│   ├── openclaw/                # 记忆系统参考
│   ├── langfuse/                # 监控追踪
│   └── MetaGPT/                 # 角色设计参考
├── backend/                     # Python 后端 (待实现)
│   └── src/
│       ├── agents/              # 策划 Agents（CrewAI 实现）
│       ├── memory/              # 记忆系统
│       └── api/                 # FastAPI 接口
├── frontend/                    # Vue3 前端 (待实现)
│   └── ...
└── data/                        # 数据存储
    ├── projects/                # 项目记忆
    └── knowledge/               # 全局知识库
```

## 两层 Agent 架构

| 层 | 位置 | 用途 | 技术 |
|---|------|------|------|
| 开发层 | `.claude/agents/` | 辅助开发本项目 | Claude Code |
| 业务层 | `backend/src/agents/` | 策划团队核心功能 | CrewAI |

## 核心功能

### Phase 1: MVP
- [ ] 基础 Agent 角色定义
- [ ] 多轮讨论流程
- [ ] 终端输出查看
- [ ] Langfuse 接入

### Phase 2: 可视化
- [ ] 前端框架搭建
- [ ] 实时对话展示
- [ ] Agent 状态面板
- [ ] 讨论历史回放

### Phase 3: 记忆系统
- [ ] 项目级记忆存储
- [ ] 语义检索 (向量数据库)
- [ ] 设计决策追踪
- [ ] 知识库管理

### Phase 4: 高级功能
- [ ] 人工介入节点
- [ ] 策划案自动生成
- [ ] 多项目并行
- [ ] 成本控制

## 技术栈

**后端:**
- Python 3.11+
- CrewAI
- FastAPI
- SQLite + Chroma (向量数据库)
- Langfuse SDK

**前端:**
- Vite + Vue 3
- TypeScript
- TailwindCSS
- WebSocket

## 开发流程

使用 Claude Code 的 Spec-Driven Development (SDD) 流程：

```bash
# 1. 生成规格文档
/bwf-spec

# 2. 生成实施计划
/bwf-plan

# 3. 自动开发（逐 Plan 执行）
/bwf-dev docs/plans/plan-backend.md
/bwf-dev docs/plans/plan-frontend.md

# 4. 从中断处继续
/bwf-dev --continue
```

## 快速开始

```bash
# 克隆后进入目录
cd bw-work

# 查看参考项目
ls github/

# 开始开发（生成规格文档）
/bwf-spec
```
