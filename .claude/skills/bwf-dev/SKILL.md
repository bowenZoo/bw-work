---
name: bwf-dev
description: 自动开发闭环。读取 Plan，逐任务执行：开发 → 验证 → 安全检查 → 审核 → 修复 → 提交。
argument-hint: <plan-file> [--max-fix-rounds=3] [--task=<id>] [--continue] [--skip-review]
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Task, AskUserQuestion, TodoWrite
context: fork
---

# /bwf-dev - 自动开发闭环

<command-name>bwf-dev</command-name>

## 功能

读取 Plan 文件，逐任务执行开发工作，直到完成。

## 前置条件

必须先运行 `/bwf-plan` 生成实施计划。

## 语法

```bash
/bwf-dev docs/plans/plan-backend.md           # 开发指定 Plan
/bwf-dev docs/plans/plan-backend.md --task=1.2  # 只执行指定任务
/bwf-dev --continue                            # 从上次中断处继续
/bwf-dev --skip-review                         # 跳过代码审核
/bwf-dev --max-fix-rounds=5                    # 最多修复 5 轮
```

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `<plan-file>` | Plan 文件路径 | 必填 |
| `--max-fix-rounds` | 每任务最大修复轮次 | 3 |
| `--task` | 只执行指定任务 | 执行全部 |
| `--continue` | 从中断处继续 | false |
| `--skip-review` | 跳过代码审核 | false |

## 执行流程

```
1. 解析 Plan，提取任务列表
       ↓
2. For each Task:
   ┌──────────────────────────────────────────┐
   │  2.1 调用 auto-developer 执行开发         │
   │           ↓                              │
   │  2.2 运行验证命令                         │
   │           ↓                              │
   │       ┌───┴───┐                          │
   │    通过 ✅   失败 ❌                      │
   │       │       │                          │
   │       │   修复 → 重试                     │
   │       ↓       (max N 轮)                 │
   │  2.3 代码审核 (code-reviewer)            │
   │           ↓                              │
   │  2.4 Git Commit                          │
   └──────────────────────────────────────────┘
       ↓
3. 输出完成报告
```

## 进度持久化

每个任务完成后保存进度到 `.bwf/progress/{plan-name}.yaml`：

```yaml
plan: docs/plans/plan-backend.md
status: in_progress
tasks:
  - id: "1.1"
    status: completed
    commit: "abc1234"
  - id: "1.2"
    status: in_progress
```

## 输出示例

```
═══════════════════════════════════════════════════════════════
  开发完成
═══════════════════════════════════════════════════════════════

📄 Plan: docs/plans/plan-backend.md

| Task | 描述 | 轮次 | 审核 | Commit |
|------|------|------|------|--------|
| 1.1 | 创建项目结构 | 1 | ✅ | abc1234 |
| 1.2 | 实现核心 API | 2 | ✅ | def5678 |

总计: 2/2 任务完成

下一步: /bwf-dev docs/plans/plan-frontend.md
═══════════════════════════════════════════════════════════════
```
