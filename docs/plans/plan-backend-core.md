# Plan: 后端核心 - Agent 角色与讨论流程

> **模块**: backend-core
> **优先级**: P0
> **对应 Spec**: docs/spec.md#2.1, #2.2, #2.5

## 目标

搭建后端核心框架，实现：
1. 基础 Agent 角色定义（系统策划、数值策划、玩家代言人）
2. 多轮讨论流程编排（CrewAI）
3. Langfuse 监控集成
4. FastAPI 基础 API

## 前置依赖

无前置依赖，这是第一个执行的 Plan。

## 技术方案

### 架构设计

```
backend/
├── src/
│   ├── agents/              # Agent 定义
│   │   ├── __init__.py
│   │   ├── base.py          # Agent 基类
│   │   ├── system_designer.py
│   │   ├── number_designer.py
│   │   └── player_advocate.py
│   ├── crew/                # CrewAI 编排
│   │   ├── __init__.py
│   │   └── discussion_crew.py
│   ├── api/                 # FastAPI 接口
│   │   ├── __init__.py
│   │   ├── main.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       └── discussion.py
│   ├── config/              # 配置
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   └── roles/           # 角色 YAML 配置
│   │       ├── system_designer.yaml
│   │       ├── number_designer.yaml
│   │       └── player_advocate.yaml
│   └── monitoring/          # 监控
│       ├── __init__.py
│       └── langfuse_client.py
├── tests/
│   ├── __init__.py
│   ├── test_agents.py
│   └── test_crew.py
├── pyproject.toml
└── requirements.txt
```

### 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| Web 框架 | FastAPI | 异步支持，OpenAPI 自动文档 |
| Agent 编排 | CrewAI | 项目技术栈指定 |
| 监控 | Langfuse | 项目技术栈指定 |
| 配置管理 | Pydantic Settings | 类型安全，环境变量支持 |
| 角色配置 | YAML | 便于非开发人员修改 |

## 任务清单

### Task 1.1: 初始化后端项目结构

**执行**:
- 创建 `backend/` 目录结构
- 创建 `pyproject.toml` 配置文件
- 创建 `requirements.txt` 依赖文件
- 创建 `backend/src/__init__.py` 等基础文件

**验证**:
- `ls backend/src/agents backend/src/api backend/src/config` → 目录存在
- `cat backend/pyproject.toml` → 文件内容正确

**输出文件**:
- `backend/pyproject.toml`
- `backend/requirements.txt`
- `backend/src/__init__.py`
- `backend/src/agents/__init__.py`
- `backend/src/api/__init__.py`
- `backend/src/config/__init__.py`

---

### Task 1.2: 实现 Agent 基类和配置加载

**执行**:
- 创建 `backend/src/agents/base.py`，定义 Agent 基类
- 实现 YAML 配置加载逻辑
- 定义 Agent 的 role、goal、backstory 接口

**验证**:
- `cd backend && python -c "from src.agents.base import BaseAgent"` → exit_code == 0

**输出文件**:
- `backend/src/agents/base.py`
- `backend/src/config/settings.py`

---

### Task 1.3: 创建角色 YAML 配置文件

**执行**:
- 创建 `backend/src/config/roles/system_designer.yaml`
- 创建 `backend/src/config/roles/number_designer.yaml`
- 创建 `backend/src/config/roles/player_advocate.yaml`
- 每个配置包含 role、goal、backstory、focus_areas

**验证**:
- `python -c "import yaml; yaml.safe_load(open('backend/src/config/roles/system_designer.yaml'))"` → exit_code == 0

**输出文件**:
- `backend/src/config/roles/system_designer.yaml`
- `backend/src/config/roles/number_designer.yaml`
- `backend/src/config/roles/player_advocate.yaml`

---

### Task 1.4: 实现三个核心 Agent

**执行**:
- 实现 `backend/src/agents/system_designer.py` - 系统策划角色
- 实现 `backend/src/agents/number_designer.py` - 数值策划角色
- 实现 `backend/src/agents/player_advocate.py` - 玩家代言人角色
- 每个 Agent 继承基类，加载对应 YAML 配置

**验证**:
- `cd backend && python -c "from src.agents import SystemDesigner, NumberDesigner, PlayerAdvocate"` → exit_code == 0

**输出文件**:
- `backend/src/agents/system_designer.py`
- `backend/src/agents/number_designer.py`
- `backend/src/agents/player_advocate.py`
- `backend/src/agents/__init__.py` (更新导出)

---

### Task 1.5: 实现 CrewAI 讨论编排

**执行**:
- 创建 `backend/src/crew/` 目录
- 实现 `backend/src/crew/discussion_crew.py`
- 定义讨论任务和流程
- 实现 Agent 轮流发言逻辑

**验证**:
- `cd backend && python -c "from src.crew.discussion_crew import DiscussionCrew"` → exit_code == 0

**输出文件**:
- `backend/src/crew/__init__.py`
- `backend/src/crew/discussion_crew.py`

---

### Task 1.6: 集成 Langfuse 监控

**执行**:
- 创建 `backend/src/monitoring/` 目录
- 实现 `backend/src/monitoring/langfuse_client.py`
- 配置 Langfuse 追踪回调
- 在 Crew 执行中启用追踪

**验证**:
- `cd backend && python -c "from src.monitoring.langfuse_client import get_langfuse_handler"` → exit_code == 0

**输出文件**:
- `backend/src/monitoring/__init__.py`
- `backend/src/monitoring/langfuse_client.py`

---

### Task 1.7: 实现 FastAPI 基础接口

**执行**:
- 创建 `backend/src/api/main.py` - FastAPI 应用入口
- 实现 GET `/health` - 健康检查接口（返回 `{"status": "ok"}`）
- 创建 `backend/src/api/routes/discussion.py` - 讨论相关路由
- 实现 POST `/api/discussions` - 创建讨论
- 实现 GET `/api/discussions/{id}` - 获取讨论状态
- 实现 POST `/api/discussions/{id}/start` - 启动讨论

**验证**:
- `cd backend && python -c "from src.api.main import app"` → exit_code == 0
- `cd backend && python -m uvicorn src.api.main:app --host 0.0.0.0 --port 18000 &; sleep 3; curl -s http://localhost:18000/health; kill %1` → contains "ok"

**输出文件**:
- `backend/src/api/main.py`
- `backend/src/api/routes/__init__.py`
- `backend/src/api/routes/discussion.py`

---

### Task 1.8: 编写单元测试

**执行**:
- 创建 `backend/tests/` 目录
- 编写 `backend/tests/test_agents.py` - Agent 单元测试
- 编写 `backend/tests/test_crew.py` - Crew 集成测试
- 配置 pytest

**验证**:
- `cd backend && python -m pytest tests/ -v` → exit_code == 0

**输出文件**:
- `backend/tests/__init__.py`
- `backend/tests/conftest.py`
- `backend/tests/test_agents.py`
- `backend/tests/test_crew.py`

---

### Task 1.9: 创建示例运行脚本

**执行**:
- 创建 `backend/scripts/run_discussion.py` - 命令行运行讨论
- 支持参数：话题、参与 Agent、讨论轮数
- 终端实时输出讨论内容

**验证**:
- `cd backend && python scripts/run_discussion.py --topic "设计一个背包系统" --rounds 2` → 输出讨论内容

**输出文件**:
- `backend/scripts/run_discussion.py`

## 验收标准

- [ ] 三个核心 Agent 定义完成，各有独特的 role/goal/backstory (Spec AC-01)
- [ ] Agent 之间可进行多轮对话 (Spec AC-02)
- [ ] 每个 Agent 发言体现其职责特点 (Spec AC-03)
- [ ] 角色配置可通过 YAML 文件修改 (Spec AC-04)
- [ ] 用户可输入话题启动讨论 (Spec AC-05)
- [ ] 讨论过程在终端实时显示 (Spec AC-06)
- [ ] 每轮讨论有明确的发言顺序 (Spec AC-07)
- [ ] 讨论可正常结束并输出结论 (Spec AC-08)
- [ ] Langfuse 可正常接收追踪数据 (Spec AC-17)
- [ ] 所有单元测试通过
