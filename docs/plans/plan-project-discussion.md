# Plan: 项目级策划讨论

> **模块**: project-discussion
> **优先级**: P0/P1 (核心工作流)
> **对应 Spec**: docs/spec.md#2.8

## 目标

实现项目级策划讨论工作流，支持：
1. GDD 上传与解析 (F-38, F-39) - 支持 Markdown/PDF/Word 格式
2. 模块自动识别 (F-40) - AI 识别 GDD 中的功能模块
3. 批量模块选择 (F-41) - 用户一次选择多个模块，设置讨论顺序
4. 依次自动讨论 (F-42) - 按顺序自动进行每个模块的讨论
5. 讨论断点恢复 (F-43) - 支持中断后从上次位置继续
6. 项目级记忆 (F-44) - 跨模块共享上下文，保持一致性
7. 策划案生成 (F-45) - 每个模块讨论后生成结构化策划案
8. 策划案汇总 (F-46) - 所有模块完成后生成项目级汇总文档
9. 讨论进度追踪 (F-47) - 实时显示讨论进度和状态
10. 模块依赖校验与自动排序 - 保证顺序合法
11. 长任务可恢复 - 服务重启后可继续批量讨论
12. 存储与推送规模控制 - 控制断点体积与 WS 频率

## 前置依赖

- `plan-backend-core.md` - 需要 Agent 角色和 Crew 讨论框架
- `plan-memory.md` - 需要讨论记忆存储、决策追踪
- `plan-websocket.md` - 需要 WebSocket 实时推送

## 技术方案

### 架构设计

```
backend/src/
├── project/                          # 项目级讨论模块 (新增)
│   ├── __init__.py
│   ├── registry.py                   # 项目/批量讨论注册表（持久化）
│   ├── gdd/                          # GDD 处理
│   │   ├── __init__.py
│   │   ├── parser.py                 # GDD 解析器 (统一入口)
│   │   ├── parsers/                  # 格式解析器
│   │   │   ├── __init__.py
│   │   │   ├── markdown.py           # Markdown 解析
│   │   │   ├── pdf.py                # PDF 解析
│   │   │   └── docx.py               # Word 解析
│   │   └── module_detector.py        # 模块识别 (AI)
│   ├── discussion/                   # 批量讨论
│   │   ├── __init__.py
│   │   ├── batch_runner.py           # 批量讨论执行器
│   │   ├── executor.py               # 后台执行与恢复
│   │   ├── checkpoint.py             # 断点管理
│   │   └── project_memory.py         # 项目级记忆
│   ├── output/                       # 输出生成
│   │   ├── __init__.py
│   │   ├── design_doc.py             # 策划案生成
│   │   └── summary.py                # 项目汇总
│   └── models.py                     # 数据模型定义
├── api/routes/
│   └── project.py                    # 项目级讨论 API (新增)

frontend/src/
├── views/
│   └── ProjectView.vue               # 项目讨论页面 (新增)
├── components/
│   └── project/                      # 项目相关组件 (新增)
│       ├── GddUploader.vue           # GDD 上传组件
│       ├── ModuleSelector.vue        # 模块选择器
│       ├── DiscussionProgress.vue    # 讨论进度面板
│       └── DesignDocPreview.vue      # 策划案预览

data/projects/{project_id}/
├── gdd/                              # GDD 文档
│   ├── original/                     # 原始上传文件
│   └── parsed/                       # 解析后数据
├── design/                           # 策划案输出
│   ├── index.md                      # 项目策划案索引
│   ├── {module}-system.md            # 模块策划案
│   └── assets/                       # 配图资源
└── checkpoints/                      # 讨论断点
```

### 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| PDF 解析 | PyMuPDF (fitz) | 速度快，文本提取质量好 |
| Word 解析 | python-docx | 官方推荐，稳定 |
| Markdown 解析 | markdown-it-py | 完整支持 GFM，解析速度快 |
| 模块识别 | LLM (Claude/GPT) | 需要语义理解能力 |
| 进度追踪 | WebSocket | 实时推送 |

> 说明：扫描件 PDF 不支持 OCR（如需支持，后续可引入 Tesseract）。

### 状态机

**项目讨论状态**（与现有 `pending/running/completed/failed` 对齐）:
```
pending → running → completed
             ↓          ↓
          paused      failed
             ↓
          running (恢复)
```

**模块讨论状态**:
```
pending → running → completed
             ↓          ↓
          paused      skipped
             ↓          ↓
          running     failed
```

### 数据模型

```python
# 项目
@dataclass
class Project:
    id: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

# GDD 文档
@dataclass
class GDDDocument:
    id: str                           # gdd_{uuid}
    project_id: str
    filename: str
    upload_time: datetime
    raw_content_path: str             # 原始文本路径（避免大文本入库）
    parsed_content_path: str          # 解析结果路径
    content_hash: str                 # 文件 hash，用于缓存/版本识别
    parser_version: str               # 解析器版本
    parsed_content: Optional[ParsedGDD]
    status: Literal["uploading", "parsing", "ready", "error"]
    error: Optional[str]

@dataclass
class ParsedGDD:
    title: str                        # 项目名称
    overview: str                     # 项目概述
    modules: List[GDDModule]          # 识别的模块列表

@dataclass
class GDDModule:
    id: str                           # 模块 ID (如 "combat", "economy")
    name: str                         # 模块名称
    description: str                  # 模块简述
    source_section: str               # GDD 中的原始章节内容
    keywords: List[str]               # 关键词（用于记忆检索）
    dependencies: List[str]           # 依赖的其他模块 ID
    estimated_rounds: int             # 预估讨论轮数

# 项目讨论
@dataclass
class ProjectDiscussion:
    id: str                           # disc_batch_{uuid}
    project_id: str
    gdd_id: str
    selected_modules: List[str]
    module_order: List[str]
    status: Literal["pending", "running", "paused", "completed", "failed"]
    progress: DiscussionProgress
    checkpoint: Optional[DiscussionCheckpoint]
    created_at: datetime
    updated_at: datetime

@dataclass
class DiscussionProgress:
    total_modules: int
    completed_modules: int
    current_module: Optional[str]
    current_round: int

# 断点数据
@dataclass
class DiscussionCheckpoint:
    project_id: str
    gdd_id: str
    selected_modules: List[str]
    current_module_index: int
    current_module_state: ModuleState
    completed_modules: List[CompletedModule]
    created_at: datetime
    updated_at: datetime

@dataclass
class ModuleState:
    module_id: str
    discussion_id: str
    round: int
    message_count: int
    last_message_id: Optional[str]    # 仅保存游标，不保存全量消息

@dataclass
class CompletedModule:
    module_id: str
    design_doc_path: str
    key_decisions: List[str]

# 模块讨论结果
@dataclass
class ModuleDiscussionResult:
    module_id: str
    module_name: str
    discussion_id: str
    status: Literal["completed", "skipped", "failed"]
    design_doc: DesignDoc
    key_decisions: List[Decision]
    duration_minutes: float
    token_usage: int

@dataclass
class DesignDoc:
    path: str
    version: str
    sections: List[str]
    created_at: datetime
```

### WebSocket 消息格式

**WebSocket 路由建议**:
- 项目级进度：`/ws/projects/{project_id}`
- 模块级消息复用现有 `/ws/{discussion_id}`（与单讨论兼容）

```typescript
// 项目讨论开始
{
  type: "project_discussion_start",
  project_id: string,
  total_modules: number,
  module_order: string[]
}

// 模块讨论开始
{
  type: "module_discussion_start",
  project_id: string,
  module_id: string,
  module_name: string,
  module_index: number,
  total_modules: number
}

// 模块讨论进度
{
  type: "module_discussion_progress",
  project_id: string,
  module_id: string,
  round: number,
  speaker: string,
  message_id: string,
  summary: string,         // 默认推送摘要
  message?: string         // 可选：按需推送全文
}

// 模块讨论完成
{
  type: "module_discussion_complete",
  project_id: string,
  module_id: string,
  design_doc_path: string,
  key_decisions: string[]
}

// 项目讨论完成
{
  type: "project_discussion_complete",
  project_id: string,
  total_duration_minutes: number,
  design_docs: string[],
  summary_path: string
}

// 讨论暂停（断点保存）
{
  type: "discussion_paused",
  project_id: string,
  checkpoint_id: string,
  current_module: string,
  completed_modules: number
}

// GDD 解析进度
{
  type: "gdd_parsing_progress",
  gdd_id: string,
  status: "parsing" | "detecting_modules" | "ready" | "error",
  message: string
}
```

## 任务清单

### Phase 1: GDD 上传与解析 (F-38, F-39, F-40)

---

### Task 8.0: 实现项目实体与最小项目 API

**执行**:
- 创建 `backend/src/project/registry.py`
- 定义 `Project` 模型与持久化（SQLite 或 JSON 索引）
- 实现 `POST /api/projects` 创建项目
- 实现 `GET /api/projects` 列表
- 实现 `GET /api/projects/{project_id}` 获取详情
- 约束 `project_id` 规则（可读 slug 或 UUID）

**验证**:
- `cd backend && python -c "from src.project.registry import ProjectRegistry"` → exit_code == 0
- 项目创建/查询流程正常

**输出文件**:
- `backend/src/project/registry.py`
- `backend/src/api/routes/project.py` (更新)

---

### Task 8.1: 定义项目讨论数据模型

**执行**:
- 创建 `backend/src/project/__init__.py`
- 创建 `backend/src/project/models.py`
- 定义数据模型：
  - `Project` - 项目实体
  - `GDDDocument` - GDD 文档
  - `ParsedGDD` - 解析后的 GDD
  - `GDDModule` - 识别的模块
  - `ProjectDiscussion` - 项目讨论
  - `DiscussionCheckpoint` - 断点数据
  - `ModuleDiscussionResult` - 模块讨论结果

**验证**:
- `cd backend && python -c "from src.project.models import GDDDocument, ProjectDiscussion"` → exit_code == 0

**输出文件**:
- `backend/src/project/__init__.py`
- `backend/src/project/models.py`

---

### Task 8.2: 实现 GDD 格式解析器

**执行**:
- 创建 `backend/src/project/gdd/__init__.py`
- 创建 `backend/src/project/gdd/parsers/__init__.py`
- 创建 `backend/src/project/gdd/parsers/markdown.py` - Markdown 解析
- 创建 `backend/src/project/gdd/parsers/pdf.py` - PDF 解析 (PyMuPDF)
- 创建 `backend/src/project/gdd/parsers/docx.py` - Word 解析 (python-docx)
- 每个解析器返回统一的 `ParsedText` 结构
- PDF 解析器检测“文本过少”并提示可能为扫描件（不支持 OCR）

**接口定义**:
```python
class GDDFormatParser(ABC):
    @abstractmethod
    def parse(self, file_path: Path) -> ParsedText:
        """解析文件，返回结构化文本"""
        pass

    @abstractmethod
    def supports(self, file_extension: str) -> bool:
        """是否支持该格式"""
        pass

@dataclass
class ParsedText:
    title: str
    content: str                    # 纯文本内容
    sections: List[Section]         # 章节结构
    metadata: dict                  # 元数据（作者、日期等）
```

**验证**:
- `cd backend && python -c "from src.project.gdd.parsers import MarkdownParser, PdfParser, DocxParser"` → exit_code == 0
- Markdown 解析测试通过
- PDF 解析测试通过
- Word 解析测试通过
- 扫描件 PDF 能返回可理解的错误提示

**输出文件**:
- `backend/src/project/gdd/__init__.py`
- `backend/src/project/gdd/parsers/__init__.py`
- `backend/src/project/gdd/parsers/markdown.py`
- `backend/src/project/gdd/parsers/pdf.py`
- `backend/src/project/gdd/parsers/docx.py`
- `backend/tests/test_gdd_parsers.py`

---

### Task 8.3: 实现 GDD 解析统一入口

**执行**:
- 创建 `backend/src/project/gdd/parser.py`
- 实现 `GDDParser` 类：
  - 根据文件扩展名选择解析器
  - 调用格式解析器获取文本
  - 保存原始文件到 `data/projects/{project_id}/gdd/original/`
  - 保存解析结果到 `data/projects/{project_id}/gdd/parsed/`
  - 计算文件 hash（用于缓存与版本识别）
- 实现文件大小限制（10MB）

**验证**:
- `cd backend && python -c "from src.project.gdd.parser import GDDParser"` → exit_code == 0
- 不同格式的 GDD 文件均可正确解析

**输出文件**:
- `backend/src/project/gdd/parser.py`

---

### Task 8.4: 实现模块自动识别 (AI)

**执行**:
- 创建 `backend/src/project/gdd/module_detector.py`
- 实现 `ModuleDetector` 类：
  - 使用 LLM 分析 GDD 内容
  - 识别功能模块列表
  - 提取模块名称、描述、关键词
  - 分析模块间依赖关系
  - 预估讨论轮数
- 定义识别 Prompt 模板
- 实现结果缓存（key = content_hash + parser_version + prompt_version）

**Prompt 设计要点**:
- 输入：GDD 完整文本 + 章节结构
- 输出：JSON 格式的模块列表
- 要求：识别功能模块（非技术模块），提取依赖关系

**验证**:
- `cd backend && python -c "from src.project.gdd.module_detector import ModuleDetector"` → exit_code == 0
- 模块识别结果包含必要字段
- 依赖关系分析合理

**输出文件**:
- `backend/src/project/gdd/module_detector.py`
- `backend/src/project/gdd/prompts/module_detection.txt` (Prompt 模板)
- `backend/tests/test_module_detector.py`

---

### Task 8.5: 实现 GDD 上传 API

**执行**:
- 创建 `backend/src/api/routes/project.py`
- 实现 `POST /api/projects/{project_id}/gdd` - GDD 上传
  - 接收 multipart/form-data 文件
  - 验证文件格式和大小
  - 验证 project 存在
  - 异步解析和模块识别
  - 扫描件 PDF 返回明确错误（提示需可复制文本）
  - 返回 gdd_id 和解析状态
- 实现 `GET /api/projects/{project_id}/gdd/{gdd_id}` - 获取 GDD 状态
- 实现 `GET /api/projects/{project_id}/gdd/{gdd_id}/modules` - 获取识别的模块

**API 规格**:
```
POST /api/projects/{project_id}/gdd
Content-Type: multipart/form-data
Request:
  file: File (GDD 文档，限制 10MB)
Response:
{
  "gdd_id": "gdd_001",
  "filename": "my-game-gdd.md",
  "status": "parsing",
  "message": "GDD 上传成功，正在解析..."
}

GET /api/projects/{project_id}/gdd/{gdd_id}/modules
Response:
{
  "gdd_id": "gdd_001",
  "status": "ready",
  "modules": [...],
  "suggested_order": ["combat", "economy", "progression"]
}
```

**验证**:
- `cd backend && python -c "from src.api.routes.project import router"` → exit_code == 0
- 文件上传和解析流程正常
- API 响应格式正确

**输出文件**:
- `backend/src/api/routes/project.py`
- `backend/src/api/routes/__init__.py` (更新)
- `backend/src/api/main.py` (更新，挂载路由)
- `backend/tests/test_project_api.py`

---

### Phase 2: 批量讨论与断点恢复 (F-41, F-42, F-43, F-44)

---

### Task 8.6: 实现项目级记忆

**执行**:
- 创建 `backend/src/project/discussion/project_memory.py`
- 实现 `ProjectMemory` 类：
  - 加载 GDD 上下文
  - 存储已完成模块的关键决策摘要
  - 维护项目术语表
  - 存储约束条件
  - 提供记忆检索接口（供 Agent 使用）
- 实现一致性检查接口（检测跨模块冲突）

**记忆类型**:
| 类型 | 内容 | 用途 |
|------|------|------|
| GDD 上下文 | 完整 GDD 内容 | 确保讨论符合总体设计 |
| 模块决策 | 已完成模块的关键决策 | 保持跨模块一致性 |
| 术语表 | 项目专有名词定义 | 统一术语使用 |
| 约束条件 | 技术/资源约束 | 确保方案可行性 |

**验证**:
- `cd backend && python -c "from src.project.discussion.project_memory import ProjectMemory"` → exit_code == 0
- 记忆存储和检索正常

**输出文件**:
- `backend/src/project/discussion/__init__.py`
- `backend/src/project/discussion/project_memory.py`
- `backend/tests/test_project_memory.py`

---

### Task 8.7: 实现断点管理

**执行**:
- 创建 `backend/src/project/discussion/checkpoint.py`
- 实现 `CheckpointManager` 类：
  - 保存断点状态到 `data/projects/{project_id}/checkpoints/`
  - 加载断点状态
  - 删除过期断点（可配置保留数量）
- 断点数据包含：
  - 当前模块索引
  - 当前讨论轮数
  - 已完成模块列表
  - 消息游标（last_message_id / message_count），不保存全文
- 实现原子写（写临时文件后 rename，防止中断导致损坏）
- 断点体积限制与保留策略（按数量/时间）

**验证**:
- `cd backend && python -c "from src.project.discussion.checkpoint import CheckpointManager"` → exit_code == 0
- 断点保存和恢复正常
- 断点数据完整性测试通过

**输出文件**:
- `backend/src/project/discussion/checkpoint.py`
- `backend/tests/test_checkpoint.py`

---

### Task 8.8: 实现批量讨论执行器

**执行**:
- 创建 `backend/src/project/discussion/batch_runner.py`
- 实现 `BatchDiscussionRunner` 类：
  - 按顺序执行每个模块的讨论
  - 每个模块讨论前：
    1. 加载项目级记忆
    2. 注入 GDD 模块上下文
  - 每个模块讨论后：
    1. 生成策划案
    2. 更新项目级记忆
    3. 保存断点状态
  - 支持暂停/恢复
  - 集成 WebSocket 进度推送
- 集成后台执行器 `executor.py`：
  - 任务持久化注册（可恢复）
  - 服务启动时扫描 pending/running 任务并恢复
  - 并发数与队列长度可配置

**状态机实现**:
```python
class BatchRunnerState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"

# 状态转换
PENDING → RUNNING (start)
RUNNING → PAUSED (pause)
RUNNING → COMPLETED (all modules done)
RUNNING → FAILED (unrecoverable error)
PAUSED → RUNNING (resume)
```

**验证**:
- `cd backend && python -c "from src.project.discussion.batch_runner import BatchDiscussionRunner"` → exit_code == 0
- 批量讨论流程正常
- 暂停/恢复功能正常

**输出文件**:
- `backend/src/project/discussion/batch_runner.py`
- `backend/src/project/discussion/executor.py`
- `backend/tests/test_batch_runner.py`

---

### Task 8.9: 实现批量讨论 API

**执行**:
- 更新 `backend/src/api/routes/project.py`
- 实现 `POST /api/projects/{project_id}/discussions/batch` - 启动批量讨论
  - 校验模块依赖关系（拓扑排序）
  - 若未提供 order，则按依赖自动排序
- 实现 `POST /api/projects/{project_id}/discussions/{id}/pause` - 暂停讨论
- 实现 `POST /api/projects/{project_id}/discussions/{id}/resume` - 恢复讨论
- 实现 `POST /api/projects/{project_id}/discussions/{id}/skip` - 跳过当前模块
- 实现 `GET /api/projects/{project_id}/discussions/{id}` - 获取讨论状态
- 实现 `GET /api/projects/{project_id}/checkpoints` - 获取断点列表

**API 规格**:
```
POST /api/projects/{project_id}/discussions/batch
Request:
{
  "gdd_id": "gdd_001",
  "modules": ["combat", "economy", "progression"],
  "order": ["combat", "economy", "progression"] // 可选，缺省自动拓扑排序
}
Response:
{
  "discussion_id": "disc_batch_001",
  "status": "running",
  "project_ws_url": "/ws/projects/{project_id}"
}

POST /api/projects/{project_id}/discussions/{id}/pause
Response:
{
  "status": "paused",
  "checkpoint_id": "cp_001"
}

POST /api/projects/{project_id}/discussions/{id}/resume
Response:
{
  "status": "resumed",
  "current_module": "economy",
  "completed_modules": 1
}

POST /api/projects/{project_id}/discussions/{id}/skip
Response:
{
  "status": "skipped",
  "skipped_module": "economy",
  "current_module": "progression"
}
```

**验证**:
- API 接口正常响应
- 讨论启动/暂停/恢复流程正常

**输出文件**:
- `backend/src/api/routes/project.py` (更新)
- `backend/tests/test_project_api.py` (更新)

---

### Phase 3: 策划案输出 (F-45, F-46)

---

### Task 8.10: 实现策划案生成器

**执行**:
- 创建 `backend/src/project/output/__init__.py`
- 创建 `backend/src/project/output/design_doc.py`
- 实现 `DesignDocGenerator` 类：
  - 根据讨论内容生成结构化策划案
  - 使用 LLM 整理讨论要点
  - 按 Spec 定义的文档结构输出
  - 保存到 `data/projects/{project_id}/design/{module}-system.md`
- 定义策划案模板

**策划案文档结构** (来自 Spec):
```markdown
# {模块名} 策划案

> **版本**: 1.0
> **生成时间**: {timestamp}
> **讨论 ID**: {discussion_id}
> **基于 GDD**: {gdd_filename}

## 1. 功能概述
### 1.1 设计目标
### 1.2 核心体验
### 1.3 与其他系统的关系

## 2. 玩法描述
### 2.1 基础玩法
### 2.2 进阶玩法
### 2.3 玩法示例

## 3. 界面流程
### 3.1 主要界面
### 3.2 操作流程
### 3.3 界面跳转

## 4. 数值框架
### 4.1 核心公式
### 4.2 参数表
### 4.3 平衡目标

## 5. 边界处理
### 5.1 异常情况
### 5.2 防作弊
### 5.3 容错机制

## 6. 附录
### 6.1 讨论记录摘要
### 6.2 设计决策记录
### 6.3 待确认事项
```

**验证**:
- `cd backend && python -c "from src.project.output.design_doc import DesignDocGenerator"` → exit_code == 0
- 生成的策划案格式正确
- 策划案只包含策划内容，不含技术规格

**输出文件**:
- `backend/src/project/output/__init__.py`
- `backend/src/project/output/design_doc.py`
- `backend/src/project/output/templates/design_doc.md` (策划案模板)
- `backend/tests/test_design_doc.py`

---

### Task 8.11: 实现项目汇总生成

**执行**:
- 创建 `backend/src/project/output/summary.py`
- 实现 `ProjectSummaryGenerator` 类：
  - 汇总所有模块策划案
  - 生成项目级索引 `index.md`
  - 包含模块关系图
  - 包含关键决策汇总
- 输出到 `data/projects/{project_id}/design/index.md`

**索引文档结构**:
```markdown
# {项目名} 策划案索引

> **生成时间**: {timestamp}
> **GDD 来源**: {gdd_filename}
> **讨论时长**: {total_duration}

## 模块列表

| 模块 | 策划案 | 状态 | 讨论轮数 |
|------|--------|------|----------|
| 战斗系统 | [combat-system.md](./combat-system.md) | 已完成 | 5 |
| 经济系统 | [economy-system.md](./economy-system.md) | 已完成 | 4 |
| ... | ... | ... | ... |

## 模块关系

{模块依赖关系图}

## 关键决策汇总

| 模块 | 决策 | 原因 |
|------|------|------|
| 战斗系统 | 采用回合制 | 目标用户偏好 |
| ... | ... | ... |

## 待确认事项汇总

{汇总所有模块的待确认事项}
```

**验证**:
- `cd backend && python -c "from src.project.output.summary import ProjectSummaryGenerator"` → exit_code == 0
- 项目索引生成正确

**输出文件**:
- `backend/src/project/output/summary.py`
- `backend/src/project/output/templates/index.md` (索引模板)

---

### Task 8.12: 实现策划案 API

**执行**:
- 更新 `backend/src/api/routes/project.py`
- 实现 `GET /api/projects/{project_id}/design` - 获取策划案索引
- 实现 `GET /api/projects/{project_id}/design/{module_id}` - 获取模块策划案
- 实现 `GET /api/projects/{project_id}/design/export` - 导出策划案 (Markdown/PDF)
  - Markdown: 直接返回
  - PDF: 优先使用 markdown-pdf（如使用 weasyprint 需声明系统依赖）

**验证**:
- API 接口正常响应
- 策划案内容完整

**输出文件**:
- `backend/src/api/routes/project.py` (更新)

---

### Phase 4: 前端界面 (F-41, F-47)

---

### Task 8.13: 实现 GDD 上传组件

**执行**:
- 创建 `frontend/src/components/project/GddUploader.vue`
- 实现功能：
  - 拖拽上传或点击选择
  - 文件格式验证 (.md, .pdf, .docx)
  - 文件大小验证 (10MB)
  - 上传进度显示
  - 解析状态显示

**验证**:
- 组件渲染正常
- 文件上传功能正常
- 错误提示友好

**输出文件**:
- `frontend/src/components/project/GddUploader.vue`

---

### Task 8.14: 实现模块选择器组件

**执行**:
- 创建 `frontend/src/components/project/ModuleSelector.vue`
- 实现功能：
  - 显示识别出的所有模块
  - 支持多选（Checkbox）
  - 支持拖拽调整讨论顺序
  - 显示模块依赖关系
  - 显示预估总耗时
  - 智能排序建议（按依赖关系）
  - 校验当前顺序是否合法（依赖冲突提示）

**验证**:
- 模块列表显示正确
- 多选和排序功能正常
- 依赖关系可视化

**输出文件**:
- `frontend/src/components/project/ModuleSelector.vue`

---

### Task 8.15: 实现讨论进度面板

**执行**:
- 创建 `frontend/src/components/project/DiscussionProgress.vue`
- 实现功能：
  - 显示整体进度（已完成/总数）
  - 显示当前讨论模块
  - 显示当前轮数
  - 实时消息流展示
  - 暂停/恢复按钮
  - 断点恢复提示

**数据来源**:
- WebSocket: `module_discussion_progress`、`module_discussion_complete` 等事件

**验证**:
- 进度显示准确
- WebSocket 实时更新
- 暂停/恢复功能正常

**输出文件**:
- `frontend/src/components/project/DiscussionProgress.vue`

---

### Task 8.16: 实现策划案预览组件

**执行**:
- 创建 `frontend/src/components/project/DesignDocPreview.vue`
- 实现功能：
  - Markdown 渲染
  - 目录导航
  - 导出按钮（Markdown/PDF）
  - 版本信息显示

**验证**:
- Markdown 渲染正确
- 导出功能正常

**输出文件**:
- `frontend/src/components/project/DesignDocPreview.vue`

---

### Task 8.17: 实现项目讨论页面

**执行**:
- 创建 `frontend/src/views/ProjectView.vue`
- 集成所有项目相关组件
- 实现页面流程：
  1. GDD 上传 → 显示 GddUploader
  2. 模块选择 → 显示 ModuleSelector
  3. 讨论进行 → 显示 DiscussionProgress
  4. 结果查看 → 显示 DesignDocPreview
- 添加路由配置

**验证**:
- 页面流程正常
- 各阶段切换正确

**输出文件**:
- `frontend/src/views/ProjectView.vue`
- `frontend/src/router/index.ts` (更新)

---

### Task 8.18: 添加 WebSocket 事件处理

**执行**:
- 更新 `backend/src/api/websocket/events.py`
- 添加项目讨论相关事件：
  - `GddParsingProgressEvent`
  - `ProjectDiscussionStartEvent`
  - `ModuleDiscussionStartEvent`
  - `ModuleDiscussionProgressEvent`
  - `ModuleDiscussionCompleteEvent`
  - `ProjectDiscussionCompleteEvent`
  - `DiscussionPausedEvent`
- 更新 `backend/src/api/websocket/handlers.py`
- 实现 WebSocket 房间机制（按项目隔离）
- 进度推送节流（如 200-500ms）以避免洪泛
- 保持 `/ws/{discussion_id}` 兼容现有讨论流

**验证**:
- WebSocket 事件正确推送
- 多客户端订阅正常

**输出文件**:
- `backend/src/api/websocket/events.py` (更新)
- `backend/src/api/websocket/handlers.py` (更新)
- `frontend/src/composables/useProjectWebSocket.ts` (新增)

---

### Phase 5: 集成测试

---

### Task 8.19: 编写集成测试

**执行**:
- 创建 `backend/tests/test_project_integration.py`
- 测试完整流程：
  1. 上传 GDD
  2. 获取识别的模块
  3. 启动批量讨论
  4. 验证 WebSocket 事件
  5. 暂停/恢复讨论
  6. 验证策划案生成
- 创建测试用 GDD 文件
- 使用 Mock LLM 避免真实 API 调用

**测试用例**:
- GDD 解析流程（Markdown/PDF/Word）
- 模块识别准确性
- 批量讨论完整流程
- 依赖校验与自动排序
- 断点保存/恢复
- 跳过模块流程
- 服务重启后的任务恢复
- 策划案生成格式
- 并发安全性

**验证**:
- `cd backend && python -m pytest tests/test_project_integration.py -v` → exit_code == 0

**输出文件**:
- `backend/tests/test_project_integration.py`
- `backend/tests/fixtures/sample-gdd.md`
- `backend/tests/fixtures/sample-gdd.pdf`

---

### Task 8.20: 更新依赖和配置

**执行**:
- 更新 `backend/requirements.txt`
  - 添加 PyMuPDF (fitz)
  - 添加 python-docx
  - 添加 markdown-it-py
  - 如需 PDF 导出：添加 weasyprint（并记录系统依赖）
- 更新 `backend/src/config/settings.py`
  - 添加项目讨论相关配置
    ```python
    # GDD 配置
    GDD_MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    GDD_SUPPORTED_FORMATS: List[str] = [".md", ".pdf", ".docx"]
    GDD_TEXT_MIN_CHARS: int = 500             # 检测扫描件/无文本

    # 讨论配置
    PROJECT_DISCUSSION_MAX_ROUNDS_PER_MODULE: int = 10
    PROJECT_DISCUSSION_CHECKPOINT_RETENTION: int = 5
    PROJECT_DISCUSSION_CHECKPOINT_MESSAGE_LIMIT: int = 2000  # 恢复时加载的消息上限
    PROJECT_DISCUSSION_WS_THROTTLE_MS: int = 300
    PROJECT_DISCUSSION_MAX_CONCURRENCY: int = 2

    # 输出配置
    DESIGN_DOC_OUTPUT_PATH: str = "data/projects/{project_id}/design"
    ```
- 更新 `.env.example`

**验证**:
- 依赖安装正常
- 配置加载正确

**输出文件**:
- `backend/requirements.txt` (更新)
- `backend/src/config/settings.py` (更新)
- `backend/.env.example` (更新)

## 验收标准

- [ ] 支持上传 Markdown/PDF/Word 格式的 GDD 文件 (Spec AC-30)
- [ ] GDD 解析后能正确识别功能模块列表 (Spec AC-31)
- [ ] 用户可批量选择模块并调整讨论顺序 (Spec AC-32)
- [ ] 系统按顺序自动进行各模块讨论 (Spec AC-33)
- [ ] 讨论中断后可从断点恢复 (Spec AC-34)
- [ ] 各模块讨论能访问项目级记忆，保持一致性 (Spec AC-35)
- [ ] 每个模块讨论后生成符合规范的策划案文档 (Spec AC-36)
- [ ] 策划案输出到 `data/projects/{project_id}/design/` 目录 (Spec AC-37)
- [ ] 策划案只包含策划内容，不含技术规格 (Spec AC-38)
- [ ] 支持导出策划案为 Markdown/PDF 格式 (Spec AC-39)
- [ ] 批量讨论顺序符合模块依赖关系（自动排序或拒绝非法顺序）
- [ ] 可跳过模块并继续后续讨论
- [ ] 服务重启后可从断点恢复批量讨论
- [ ] WebSocket 进度推送可节流，避免洪泛
- [ ] 所有单元测试和集成测试通过

## 暂不实现（P2 或后续迭代）

根据 Spec 2.8"暂不实现"章节：

- 多人协作编辑 GDD
- GDD 版本对比
- 策划案在线编辑
- 与外部项目管理工具集成（如 Jira）
- 自动生成技术规格（由 bw-game 负责）
