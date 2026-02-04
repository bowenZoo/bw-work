# Plan: 记忆系统

> **模块**: memory
> **优先级**: P1
> **对应 Spec**: docs/spec.md#2.4

## 目标

实现项目级记忆系统：
1. 讨论历史存储（SQLite）
2. 设计决策追踪
3. 语义检索（Chroma 向量数据库）
4. 知识库管理

## 前置依赖

- `plan-backend-core.md` - 需要 Agent 和讨论流程基础

## 技术方案

### 架构设计

```
backend/src/memory/
├── __init__.py
├── base.py                  # 记忆接口定义
├── discussion_memory.py     # 讨论记忆
├── decision_tracker.py      # 决策追踪
├── vector_store.py          # 向量存储（Chroma）
└── knowledge_base.py        # 知识库管理

data/
├── projects/{project_id}/
│   ├── discussions/         # 讨论记录 (JSON)
│   │   └── {discussion_id}.json
│   ├── drafts/              # 策划案版本
│   ├── decisions.md         # 决策记录
│   └── config.yaml          # 项目配置
├── knowledge/               # 全局知识库
│   ├── templates/
│   └── references/
└── chroma/                  # 向量数据库
```

### 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| 结构化存储 | SQLite | 轻量，无需额外服务（仅存索引/元数据） |
| 向量数据库 | Chroma | 项目技术栈指定，Python 原生 |
| 文件存储 | JSON/Markdown | **事实来源**，可读性好，版本控制友好 |
| 嵌入模型 | QWen Embedding | 替代 OpenAI Ada，本地可用 |

### 数据模型

```python
# Discussion 模型
class Discussion:
    id: str
    project_id: str
    topic: str
    messages: List[Message]
    summary: Optional[str]
    created_at: datetime
    updated_at: datetime

# Message 模型
class Message:
    id: str
    agent_id: str
    agent_role: str
    content: str
    timestamp: datetime

# Decision 模型
class Decision:
    id: str
    discussion_id: str
    title: str
    description: str
    rationale: str
    made_by: str
    created_at: datetime
```

## 任务清单

### Task 3.1: 定义记忆系统接口

**执行**:
- 创建 `backend/src/memory/__init__.py`
- 创建 `backend/src/memory/base.py`
- 定义 MemoryStore 抽象基类
- 定义核心方法：save, load, search, delete

**验证**:
- `cd backend && python -c "from src.memory.base import MemoryStore"` → exit_code == 0

**输出文件**:
- `backend/src/memory/__init__.py`
- `backend/src/memory/base.py`

---

### Task 3.2: 实现讨论记忆存储

**执行**:
- 创建 `backend/src/memory/discussion_memory.py`
- 实现讨论保存：
  - **JSON 文件**：讨论正文（事实来源，便于阅读和 Git 版本控制）
  - **SQLite**：索引和元数据（用于快速查询，可从 JSON 重建）
- 实现讨论加载
- 实现历史讨论列表查询
- 实现自动归档（阈值可配置，默认 100 条，超出移至 archive/）

**验证**:
- `cd backend && python -c "from src.memory.discussion_memory import DiscussionMemory; dm = DiscussionMemory(); print(dm)"` → exit_code == 0
- 单元测试通过

**输出文件**:
- `backend/src/memory/discussion_memory.py`
- `backend/tests/test_memory.py`

---

### Task 3.3: 实现决策追踪器

**执行**:
- 创建 `backend/src/memory/decision_tracker.py`
- 实现决策记录（写入 decisions.md）
- 实现决策查询
- 格式化决策输出（包含上下文和原因）

**验证**:
- `cd backend && python -c "from src.memory.decision_tracker import DecisionTracker"` → exit_code == 0
- 决策记录格式正确

**输出文件**:
- `backend/src/memory/decision_tracker.py`

---

### Task 3.4: 集成 Chroma 向量数据库

**执行**:
- 创建 `backend/src/memory/vector_store.py`
- 配置 Chroma 持久化存储（路径从环境变量或 config 读取）
- 实现文本嵌入和存储
- 实现语义相似性搜索
- **降级模式**：当 embedding 模型不可用时，回退到关键词搜索

**验证**:
- `cd backend && python -c "from src.memory.vector_store import VectorStore; vs = VectorStore(); print(vs)"` → exit_code == 0
- 语义搜索返回相关结果（或降级模式下关键词搜索可用）

**注意**：测试时可设置 `VECTOR_STORE_ENABLED=false` 跳过向量依赖

**输出文件**:
- `backend/src/memory/vector_store.py`
- `backend/tests/test_vector_store.py`

---

### Task 3.5: 实现知识库管理

**执行**:
- 创建 `backend/src/memory/knowledge_base.py`
- 实现知识文档导入（**P1: 仅 Markdown**，PDF 作为 P2 扩展）
- 实现知识检索（结合向量搜索或降级到关键词）
- 支持模板管理

**验证**:
- `cd backend && python -c "from src.memory.knowledge_base import KnowledgeBase"` → exit_code == 0

**输出文件**:
- `backend/src/memory/knowledge_base.py`

---

### Task 3.6: 创建数据目录结构

**执行**:
- 创建 `data/` 目录结构
- 创建 `data/projects/.gitkeep`
- 创建 `data/knowledge/templates/` 目录
- 创建 `data/knowledge/references/` 目录
- 添加 `.gitignore` 规则

**验证**:
- `ls data/projects data/knowledge/templates data/knowledge/references` → 目录存在

**输出文件**:
- `data/projects/.gitkeep`
- `data/knowledge/templates/.gitkeep`
- `data/knowledge/references/.gitkeep`
- `.gitignore` (更新)

---

### Task 3.7: 集成记忆系统到 Crew

**执行**:
- 更新 `backend/src/crew/discussion_crew.py`
- 讨论开始时加载历史上下文
- 讨论结束时保存讨论记录
- Agent 可查询历史决策

**验证**:
- 讨论后记录自动保存到 `data/projects/`
- 新讨论可引用历史决策

**输出文件**:
- `backend/src/crew/discussion_crew.py` (更新)

---

### Task 3.8: 添加记忆 API 接口

**执行**:
- 创建 `backend/src/api/routes/memory.py`
- 实现 GET `/api/discussions` - 获取讨论历史列表
- 实现 GET `/api/discussions/{id}/messages` - 获取讨论消息
- 实现 GET `/api/search` - 语义搜索
- 实现 GET `/api/decisions` - 获取决策列表

**验证**:
- API 接口正常返回数据
- 搜索功能返回相关结果

**输出文件**:
- `backend/src/api/routes/memory.py`
- `backend/src/api/routes/__init__.py` (更新)

## 验收标准

- [ ] 讨论内容自动保存到项目目录 (Spec AC-13)
- [ ] 新讨论可引用历史决策 (Spec AC-14)
- [ ] 支持按关键词搜索历史内容 (Spec AC-15)
- [ ] 决策记录包含上下文和原因 (Spec AC-16)
- [ ] 历史记录存储阈值可配置（默认 100 条），超出自动归档
- [ ] 向量搜索返回相关结果（或降级模式下关键词搜索可用）
- [ ] 所有单元测试通过（无外部依赖时使用降级模式）
