---
name: bwf-plan
description: 根据 Spec 生成实施计划。拆分任务，定义技术方案。
argument-hint: [--spec=<path>] [--output=<dir>]
allowed-tools: Read, Write, Glob, Grep, Task
context: fork
---

# /bwf-plan - 生成实施计划

<command-name>bwf-plan</command-name>

## 功能

根据 Spec 生成可执行的实施计划 (Plan)。

## 前置条件

必须先运行 `/bwf-spec` 生成规格文档。

## 语法

```bash
/bwf-plan                                    # 默认读取 docs/spec.md
/bwf-plan --spec=docs/spec.md               # 指定 Spec 文件
/bwf-plan --output=docs/plans/              # 指定输出目录
```

## 执行流程

```
1. 检查 docs/spec.md 是否存在
       ↓
2. 读取 Spec，分析功能模块
       ↓
3. 调用 plan-generator agent
       ↓
4. 为每个模块生成 Plan 文件
       ↓
5. 生成 Plan 索引 (index.md)
       ↓
6. 输出执行批次建议
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
# 生成计划
/bwf-plan

# 输出
✅ 实施计划已生成:
   - Plan 数量: 4 个
   - 总任务数: 23 个

   执行批次:
   Batch 1: plan-backend (基础)
   Batch 2: plan-memory, plan-frontend (可并行)

   下一步: /bwf-dev docs/plans/plan-backend.md
```
