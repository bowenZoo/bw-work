---
name: bwf-spec
description: 生成项目规格文档。分析需求，产出结构化的 Spec。
argument-hint: [--output=<path>]
allowed-tools: Read, Write, Glob, Grep, WebFetch, Task, AskUserQuestion
context: fork
---

# /bwf-spec - 生成规格文档

<command-name>bwf-spec</command-name>

## 功能

根据需求描述生成项目规格文档 (Spec)，为后续 Plan 提供基础。

## 语法

```bash
/bwf-spec                           # 交互式生成
/bwf-spec --output=docs/spec.md     # 指定输出路径
```

## 执行流程

```
1. 收集需求
   - 读取 README.md（如有）
   - 询问用户补充需求
       ↓
2. 调用 spec-generator agent
       ↓
3. 生成 docs/spec.md
       ↓
4. 输出结果摘要
```

## 输出

- `docs/spec.md` - 规格文档

## 示例

```bash
# 生成规格文档
/bwf-spec

# 输出
✅ 规格文档已生成: docs/spec.md
   - 功能模块: 5 个
   - 用户故事: 12 个
   - 验收标准: 28 条
```
