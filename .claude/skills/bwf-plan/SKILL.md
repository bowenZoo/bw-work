---
name: bwf-plan
description: 根据 Spec 生成实施计划。拆分任务，定义技术方案，自动 Git 版本管理。
argument-hint: [--spec=<path>] [--output=<dir>] [--no-commit]
allowed-tools: Read, Write, Glob, Grep, Task, Bash
context: fork
---

# /bwf-plan - 生成实施计划

<command-name>bwf-plan</command-name>

## 功能

根据 Spec 生成可执行的实施计划 (Plan)，自动提交 Git 版本。

## 前置条件

必须先运行 `/bwf-spec` 生成规格文档。

## 语法

```bash
/bwf-plan                                    # 默认读取 docs/spec.md
/bwf-plan --spec=docs/spec.md               # 指定 Spec 文件
/bwf-plan --output=docs/plans/              # 指定输出目录
/bwf-plan --no-commit                        # 不自动提交
```

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--spec` | Spec 文件路径 | docs/spec.md |
| `--output` | 输出目录 | docs/plans/ |
| `--no-commit` | 不自动 Git 提交 | false |

## 执行流程

```
1. 检查 docs/spec.md 是否存在
       ↓
2. 读取 Spec，分析功能模块
       ↓
3. 读取已有 Plan（如有，作为上下文）
       ↓
4. 调用 plan-generator agent
       ↓
5. 为每个模块生成 Plan 文件
       ↓
6. 生成 Plan 索引 (index.md)
       ↓
7. Git 版本管理（除非 --no-commit）
   - git add docs/plans/
   - git commit -m "docs(plan): {变更摘要}"
       ↓
8. 输出执行批次建议
```

## 版本管理

**自动提交格式：**
```
docs(plan): {变更摘要}

Plan 列表:
- plan-backend.md (N tasks)
- plan-frontend.md (N tasks)
...

Co-Authored-By: Claude <noreply@anthropic.com>
```

**查看历史版本：**
```bash
# 查看 plan 提交历史
git log --oneline docs/plans/

# 对比版本差异
git diff HEAD~1 docs/plans/plan-backend.md
```

## 输出

```
docs/plans/
├── index.md              # Plan 索引和执行批次
├── plan-backend.md       # 后端 Plan
├── plan-frontend.md      # 前端 Plan
├── plan-memory.md        # 记忆系统 Plan
└── ...
```

## 示例

```bash
# 生成计划（自动提交）
/bwf-plan

# 输出
✅ 实施计划已生成:
   - Plan 数量: 4 个
   - 总任务数: 23 个
   - Git commit: def5678 "docs(plan): 初始计划"

   执行批次:
   Batch 1: plan-backend (基础)
   Batch 2: plan-memory, plan-frontend (可并行)

   下一步: /bwf-dev docs/plans/plan-backend.md
```
