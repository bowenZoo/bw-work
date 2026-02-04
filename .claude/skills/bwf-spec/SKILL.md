---
name: bwf-spec
description: 生成项目规格文档。分析需求，产出结构化的 Spec，自动 Git 版本管理。
argument-hint: [--output=<path>] [--no-commit] [--message=<msg>]
allowed-tools: Read, Write, Glob, Grep, WebFetch, Task, AskUserQuestion, Bash
context: fork
---

# /bwf-spec - 生成规格文档

<command-name>bwf-spec</command-name>

## 功能

根据需求描述生成项目规格文档 (Spec)，自动提交 Git 版本。

## 语法

```bash
/bwf-spec                           # 交互式生成
/bwf-spec --output=docs/spec.md     # 指定输出路径
/bwf-spec --no-commit               # 不自动提交
/bwf-spec --message="v2.0 新增XX"   # 自定义提交信息
```

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--output` | 输出路径 | docs/spec.md |
| `--no-commit` | 不自动 Git 提交 | false |
| `--message` | 自定义提交信息 | 自动生成 |

## 执行流程

```
1. 收集需求
   - 读取 README.md（如有）
   - 读取已有 docs/spec.md（如有，作为上下文）
   - 询问用户补充需求
       ↓
2. 调用 spec-generator agent
       ↓
3. 生成 docs/spec.md
       ↓
4. Git 版本管理（除非 --no-commit）
   - git add docs/spec.md
   - git commit -m "docs(spec): {变更摘要}"
       ↓
5. 输出结果摘要
```

## 版本管理

**自动提交格式：**
```
docs(spec): {变更摘要}

- 功能模块: {N} 个
- 用户故事: {N} 个
- 验收标准: {N} 条

Co-Authored-By: Claude <noreply@anthropic.com>
```

**查看历史版本：**
```bash
# 查看 spec 提交历史
git log --oneline docs/spec.md

# 对比版本差异
git diff HEAD~1 docs/spec.md

# 回滚到上一版本
git checkout HEAD~1 -- docs/spec.md
```

## 输出

- `docs/spec.md` - 规格文档
- Git commit - 版本记录

## 示例

```bash
# 生成规格文档（自动提交）
/bwf-spec

# 输出
✅ 规格文档已生成: docs/spec.md
   - 功能模块: 5 个
   - 用户故事: 12 个
   - 验收标准: 28 条
   - Git commit: abc1234 "docs(spec): 初始版本"
```
