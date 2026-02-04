# Plan: 示例模板

> **模块**: example
> **优先级**: P0
> **对应 Spec**: docs/spec.md#2.1

## 目标

这是一个 Plan 模板，展示标准格式。

## 技术方案

### 架构设计

_架构图或描述_

### 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| 示例 | Python | 项目主语言 |

## 任务清单

### Task 1.1: 创建示例文件

**执行**:
- 创建 `backend/src/example.py`
- 实现 hello 函数

**验证**:
- `python -m pytest tests/test_example.py -v` → exit_code == 0

**输出文件**:
- `backend/src/example.py`
- `tests/test_example.py`

### Task 1.2: 添加类型检查

**执行**:
- 为 example.py 添加 type hints
- 运行类型检查

**验证**:
- `python -m mypy backend/src/example.py` → exit_code == 0

**输出文件**:
- `backend/src/example.py` (更新)

## 验收标准

- [ ] 示例文件创建成功 (Spec AC-01)
- [ ] 所有测试通过
- [ ] 类型检查通过
