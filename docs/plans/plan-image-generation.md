# Plan: 图像生成系统

> **模块**: image-generation
> **优先级**: P1
> **对应 Spec**: docs/spec.md#2.7

## 目标

实现图像生成系统，支持：
1. 视觉概念 Agent（F-30）- 参与讨论并生成配图
2. Prompt 工程模块（F-31）- 将文字描述转化为图像 prompt
3. 多后端图像服务（F-32）- 支持 OpenAI / OpenAI 兼容 / 任务轮询型服务（配置驱动）
4. 风格模板系统（F-33）- YAML 配置的风格预设
5. 主动请求配图（F-34）- Agent 可请求生成配图
6. 图像存储管理（F-36）- 本地 + 云存储支持
7. 异步图像生成（F-37）- WebSocket 推送生成结果

## 前置依赖

- `plan-backend-core.md` - 需要 Agent 基类和 Crew 框架
- `plan-websocket.md` - 需要 WebSocket 消息推送机制

## 技术方案

### 架构设计

```
backend/src/
├── agents/
│   └── visual_concept.py         # 视觉概念 Agent
├── image/                         # 图像生成模块
│   ├── __init__.py
│   ├── service.py                 # 图像服务抽象层
│   ├── prompt_engineer.py         # Prompt 工程
│   ├── style_manager.py           # 风格模板管理
│   ├── storage.py                 # 图像存储管理
│   └── backends/                  # 图像服务后端
│       ├── __init__.py
│       ├── base.py                # 后端基类
│       ├── openai.py              # OpenAI Images 后端
│       ├── openai_compatible.py   # OpenAI 兼容后端（配置驱动）
│       └── task_polling.py        # 任务轮询型后端（配置驱动）
├── api/
│   └── routes/
│       └── image.py               # 图像 API 路由
├── config/
│   ├── image_styles.yaml          # 风格模板配置
│   └── image_providers.yaml       # Provider 配置（URL/鉴权/参数映射）

data/projects/{project_id}/
└── images/                        # 生成的图片
    ├── img_001.png
    ├── metadata.json              # 图片元数据索引
    └── requests.json              # 生成请求索引（状态/错误）
```

### 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| HTTP 客户端 | httpx | 异步支持，与 FastAPI 生态一致 |
| 图像处理 | Pillow | 格式转换、缩略图生成 |
| 配置格式 | YAML | 风格模板便于非开发人员修改 |
| 云存储 | boto3 (可选) | S3/OSS 兼容，按需安装 |

### 状态机

**图像生成请求状态**:
```
PENDING → PROCESSING → COMPLETED
                    ↘ FAILED
```

状态说明：
- `PENDING`: 请求已创建，等待处理
- `PROCESSING`: 正在调用图像服务生成
- `COMPLETED`: 生成成功，图像已存储
- `FAILED`: 生成失败（超时、服务错误等）

### 数据模型

```python
# 图像生成请求
class ImageRequest:
    id: str                        # 请求 ID (img_xxx)
    project_id: str
    discussion_id: Optional[str]   # 关联讨论 ID
    prompt: str                    # 原始文字描述
    enhanced_prompt: str           # 增强后的图像 prompt
    style_id: str                  # 风格模板 ID
    provider_id: str               # 选用的 provider
    task_id: Optional[str]         # 异步任务 ID
    status: str                    # 状态 (pending/processing/completed/failed)
    error: Optional[str]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

# 图像元数据
class ImageMetadata:
    id: str
    filename: str
    prompt: str
    style: str
    provider_id: str
    width: int
    height: int
    created_at: datetime
    discussion_id: Optional[str]
    agent: str                     # 请求生成的 Agent
    generation_time_ms: int
```

### WebSocket 消息格式

```typescript
// 图像生成开始
{
  type: "image_generation_start",
  request_id: "img_001",
  prompt: "游戏角色概念设计...",
  style: "concept_character",
  provider_id: "provider_a"
}

// 图像生成完成
{
  type: "image_generation_complete",
  request_id: "img_001",
  image_url: "/api/images/projects/{project_id}/img_001.png",
  metadata: {
    width: 1024,
    height: 1536,
    provider_id: "provider_a",
    generation_time_ms: 15000
  }
}

// 图像生成失败
{
  type: "image_generation_error",
  request_id: "img_001",
  error: "Backend service unavailable"
}
```

## 任务清单

### Task 7.1: 定义图像服务抽象层

**执行**:
- 创建 `backend/src/image/` 目录结构
- 创建 `backend/src/image/__init__.py`
- 创建 `backend/src/image/backends/base.py`
- 定义 `ImageBackend` 抽象基类：
  ```python
  class ImageBackend(ABC):
      @abstractmethod
      async def generate(self, prompt: str, params: dict) -> ImageResult:
          """生成图像，返回图像数据或 URL"""
          pass

      @abstractmethod
      async def check_status(self, task_id: str) -> TaskStatus:
          """检查异步任务状态（异步后端）"""
          pass

      @property
      @abstractmethod
      def supports_sync(self) -> bool:
          """是否支持同步生成"""
          pass
  ```
- 定义 `ImageResult`、`TaskStatus` 数据类

**验证**:
- `cd backend && python -c "from src.image.backends.base import ImageBackend, ImageResult"` → exit_code == 0

**输出文件**:
- `backend/src/image/__init__.py`
- `backend/src/image/backends/__init__.py`
- `backend/src/image/backends/base.py`

---

### Task 7.2: 实现 OpenAI Images 后端（同步）

**执行**:
- 创建 `backend/src/image/backends/openai.py`
- 实现 `OpenAiBackend(ImageBackend)` 类
- 使用 OpenAI SDK 调用 Images API
- 支持同步生成模式
- 实现参数映射（size、quality、style）

**接口规格**:
- 端点：`POST https://api.openai.com/v1/images/generations`
- 认证：`Authorization: Bearer {OPENAI_API_KEY}`
- 请求体：
  ```json
  {
    "model": "gpt-image-1",
    "prompt": "...",
    "size": "1024x1024",
    "quality": "standard",
    "n": 1
  }
  ```

**验证**:
- `cd backend && python -c "from src.image.backends.openai import OpenAiBackend"` → exit_code == 0
- Mock 测试验证请求格式正确

**输出文件**:
- `backend/src/image/backends/openai.py`
- `backend/tests/test_image_backends.py`

---

### Task 7.3: 实现 OpenAI 兼容后端（配置驱动）

**执行**:
- 创建 `backend/src/image/backends/openai_compatible.py`
- 实现 `OpenAiCompatibleBackend(ImageBackend)` 类
- 采用 OpenAI 兼容接口格式
- 从 provider 配置读取 `api_base`、`model`、`extra_params`

**接口规格**:
- 端点：OpenAI 兼容格式（`{api_base}/v1/images/generations`）
- 认证：Token 方式（由 provider 配置指定）
- 允许扩展参数（如 `style`、`seed` 等）

**验证**:
- `cd backend && python -c "from src.image.backends.openai_compatible import OpenAiCompatibleBackend"` → exit_code == 0
- Mock 测试验证请求映射

**输出文件**:
- `backend/src/image/backends/openai_compatible.py`
- `backend/tests/test_image_backends.py` (更新)

---

### Task 7.4: 实现任务轮询型后端（配置驱动）

**执行**:
- 创建 `backend/src/image/backends/task_polling.py`
- 实现 `TaskPollingBackend(ImageBackend)` 类
- 实现通用异步轮询模式：
  1. 提交生成请求，获取 `task_id`
  2. 轮询任务状态直到完成
  3. 下载并返回图像
- 轮询间隔/超时可配置（默认 2s / 120s）
- 回调模式作为 P2 扩展（配置 `callback_url`）

**接口规格**:
- 提交端点：`{api_base}{submit_path}`
- 查询端点：`{api_base}{status_path}`
- 结果端点：`{api_base}{result_path}`（可选）
- 认证：Token 方式（由 provider 配置指定）

**验证**:
- `cd backend && python -c "from src.image.backends.task_polling import TaskPollingBackend"` → exit_code == 0

**输出文件**:
- `backend/src/image/backends/task_polling.py`

---

### Task 7.5: 实现 Provider 配置与选择逻辑

**执行**:
**执行**:
- 创建 `backend/src/config/image_providers.yaml`
- 创建 `backend/src/image/providers.py`
- 实现 `ProviderRegistry`：
  - 加载 provider 配置
  - 根据 `provider_id` 选择后端类型与参数
  - 支持环境变量注入 token

**Provider 配置结构**:
```yaml
providers:
  openai_default:
    backend: openai
    api_base: "https://api.openai.com/v1"
    api_key_env: "OPENAI_API_KEY"
    model: "gpt-image-1"
  provider_a:
    backend: openai_compatible
    api_base: "https://example.com/v1"
    api_key_env: "PROVIDER_A_TOKEN"
    extra_params:
      style: "concept"
  provider_b:
    backend: task_polling
    api_base: "https://example.com"
    api_key_env: "PROVIDER_B_TOKEN"
    submit_path: "/api/generate"
    status_path: "/api/tasks/{task_id}"
    result_path: "/api/tasks/{task_id}/result"
    poll_interval_sec: 2
```

**验证**:
- `cd backend && python -c "from src.image.providers import ProviderRegistry"` → exit_code == 0

**输出文件**:
- `backend/src/config/image_providers.yaml`
- `backend/src/image/providers.py`

---

### Task 7.6: 实现 Prompt 工程模块

**执行**:
- 创建 `backend/src/image/prompt_engineer.py`
- 实现 `PromptEngineer` 类
- 功能：
  1. 将策划文字描述转化为专业图像 prompt
  2. 根据风格模板添加前缀/后缀
  3. 处理中文描述（翻译或保留）
  4. 负向 prompt 生成（避免常见问题）
- 使用 LLM 增强 prompt（可配置开关）

**Prompt 增强流程**:
```
原始描述 → [LLM 增强(可选)] → 风格前缀 + 增强描述 + 风格后缀 → 最终 prompt
```

**验证**:
- `cd backend && python -c "from src.image.prompt_engineer import PromptEngineer"` → exit_code == 0
- 单元测试验证 prompt 增强效果

**输出文件**:
- `backend/src/image/prompt_engineer.py`
- `backend/tests/test_prompt_engineer.py`

---

### Task 7.7: 实现风格模板系统

**执行**:
- 创建 `backend/src/image/style_manager.py`
- 创建 `backend/src/config/image_styles.yaml`
- 实现 `StyleManager` 类：
  - 加载 YAML 风格配置
  - 根据 style_id 获取风格参数
  - 推荐后端选择逻辑
- 预设 6 种风格模板（见 Spec 2.7）

**风格配置结构**:
```yaml
styles:
  concept_character:
    name: 游戏概念图-角色
    prompt_prefix: "game character concept art, detailed design sheet,"
    prompt_suffix: "professional quality, artstation"
    recommended_backends:
      - openai_default
      - provider_b
    default_params:
      aspect_ratio: "2:3"
      quality: "high"
```

**验证**:
- `cd backend && python -c "from src.image.style_manager import StyleManager; sm = StyleManager(); print(sm.get_style('concept_character'))"` → exit_code == 0
- YAML 配置可正确解析

**输出文件**:
- `backend/src/image/style_manager.py`
- `backend/src/config/image_styles.yaml`

---

### Task 7.8: 实现图像存储管理

**执行**:
- 创建 `backend/src/image/storage.py`
- 实现 `ImageStorage` 类：
  - 本地存储：保存到 `data/projects/{project_id}/images/`
  - 云存储接口：预留 S3/OSS 扩展（P2）
  - 元数据管理：维护 `metadata.json` + `requests.json`（请求状态）
  - 图像 URL 生成
- 文件并发安全：文件锁 + 原子写（写临时文件后 rename）
- 配置项：`IMAGE_STORAGE_TYPE=local|oss|s3`

**存储结构**:
```
data/projects/{project_id}/images/
├── img_001.png
├── img_001_thumb.png        # 缩略图 (可选)
├── img_002.png
├── metadata.json
└── requests.json
```

**metadata.json 结构**:
```json
{
  "img_001": {
    "filename": "img_001.png",
    "prompt": "原始 prompt",
    "style": "concept_character",
    "provider_id": "provider_a",
    "width": 1024,
    "height": 1536,
    "created_at": "2026-02-05T10:00:00Z",
    "discussion_id": "disc_123",
    "agent": "visual_concept",
    "generation_time_ms": 15000
  }
}
```

**requests.json 结构**:
```json
{
  "img_001": {
    "provider_id": "openai_default",
    "task_id": null,
    "status": "completed",
    "error": null,
    "created_at": "2026-02-05T10:00:00Z",
    "updated_at": "2026-02-05T10:00:05Z"
  }
}
```

**验证**:
- `cd backend && python -c "from src.image.storage import ImageStorage"` → exit_code == 0
- 图像保存和读取正常

**输出文件**:
- `backend/src/image/storage.py`
- `backend/tests/test_image_storage.py`

---

### Task 7.9: 实现图像服务主类

**执行**:
- 创建 `backend/src/image/service.py`
- 实现 `ImageService` 类：
  - 统一的图像生成入口
  - 后端选择逻辑（根据风格推荐或手动指定）
  - 同步/异步模式自动选择
  - 错误处理和重试机制（最多 2 次重试）
  - WebSocket 状态推送集成
  - 请求状态持久化（写入 `requests.json`）
  - 异步轮询在后台任务中执行（避免阻塞 API 请求）

**调用流程**:
```
ImageService.generate(description, style_id, project_id)
    ↓
1. PromptEngineer.enhance(description, style)
    ↓
2. StyleManager.get_backend(style_id)
    ↓
3. Backend.generate(enhanced_prompt, params)
    ↓
4. ImageStorage.save(image_data, metadata)
    ↓
5. WebSocket.broadcast(image_generation_complete)
    ↓
return ImageResult
```

**验证**:
- `cd backend && python -c "from src.image.service import ImageService"` → exit_code == 0
- 集成测试验证完整流程

**输出文件**:
- `backend/src/image/service.py`
- `backend/tests/test_image_service.py`

---

### Task 7.10: 创建视觉概念 Agent

**执行**:
- 创建 `backend/src/agents/visual_concept.py`
- 创建 `backend/src/config/roles/visual_concept.yaml`
- 实现 `VisualConceptAgent(BaseAgent)` 类
- 双重角色支持：
  1. **团队成员模式**：参与讨论，从视觉角度提供建议
  2. **服务模式**：被其他 Agent 调用生成配图
- 定义 Agent Tools：
  - `generate_image(description, style)` - 生成图像
  - `suggest_visual(topic)` - 提供视觉建议

**角色配置**:
```yaml
# visual_concept.yaml
role: 视觉概念设计师
goal: 将策划文字描述转化为直观的视觉概念图，帮助团队更好地理解和沟通设计意图
backstory: |
  你是一位资深的游戏概念设计师，擅长将抽象的设计概念转化为具体的视觉表达。
  你关注画面构图、色彩搭配、风格一致性，并能根据项目需求推荐合适的美术风格。
focus_areas:
  - 视觉表达
  - 美术风格
  - 画面构图
  - 色彩方案
```

**验证**:
- `cd backend && python -c "from src.agents.visual_concept import VisualConceptAgent"` → exit_code == 0
- Agent 可正常参与讨论

**输出文件**:
- `backend/src/agents/visual_concept.py`
- `backend/src/config/roles/visual_concept.yaml`
- `backend/src/agents/__init__.py` (更新导出)

---

### Task 7.11: 集成视觉概念 Agent 到 Crew

**执行**:
- 更新 `backend/src/crew/discussion_crew.py`
- 添加视觉概念 Agent 到讨论团队（可选参与）
- 实现 Agent 间配图请求机制：
  - 其他 Agent 可通过 Tool 调用请求配图
  - 视觉概念 Agent 处理请求并返回结果
- 配置是否启用视觉概念 Agent

**调用示例**:
```python
# 在讨论中，系统策划可以请求配图
@tool
def request_image(description: str, style: str = "concept_character") -> str:
    """请求视觉概念 Agent 生成配图"""
    # 调用 ImageService 生成图像
    result = image_service.generate(description, style, project_id)
    return f"已生成配图: {result.image_url}"
```

**验证**:
- 视觉概念 Agent 可正常参与讨论
- 其他 Agent 可请求生成配图

**输出文件**:
- `backend/src/crew/discussion_crew.py` (更新)
- `backend/src/crew/tools.py` (新增或更新)

---

### Task 7.12: 实现图像 API 路由

**执行**:
- 创建 `backend/src/api/routes/image.py`
- 实现以下接口：
  - `POST /api/images/generate` - 请求生成图像
    ```json
    {
      "description": "角色设计描述",
      "style_id": "concept_character",
      "project_id": "proj_001",
      "discussion_id": "disc_123"  // 可选
    }
    ```
  - `GET /api/images/{request_id}` - 查询生成状态
  - `GET /api/images/projects/{project_id}` - 获取项目图片列表
  - `GET /api/images/projects/{project_id}/{image_id}` - 获取图片（静态文件服务）
  - `GET /api/styles` - 获取可用风格列表

**验证**:
- `cd backend && python -c "from src.api.routes.image import router"` → exit_code == 0
- API 接口正常响应

**输出文件**:
- `backend/src/api/routes/image.py`
- `backend/src/api/routes/__init__.py` (更新)
- `backend/src/api/main.py` (更新，挂载路由)

---

### Task 7.13: 实现 WebSocket 图像事件推送

**执行**:
- 更新 `backend/src/api/websocket/events.py`
- 添加图像相关事件类型：
  - `ImageGenerationStartEvent`
  - `ImageGenerationCompleteEvent`
  - `ImageGenerationErrorEvent`
- 更新 `backend/src/image/service.py` 集成 WebSocket 推送

**事件推送时机**:
1. 收到生成请求 → `image_generation_start`
2. 图像生成完成 → `image_generation_complete`
3. 生成失败 → `image_generation_error`

**验证**:
- WebSocket 客户端可收到图像生成事件
- 事件格式符合 Spec 定义

**输出文件**:
- `backend/src/api/websocket/events.py` (更新)
- `backend/src/image/service.py` (更新)

---

### Task 7.14: 编写集成测试

**执行**:
- 创建 `backend/tests/test_image_integration.py`
- 测试完整的图像生成流程：
  1. 请求生成图像
  2. 验证 WebSocket 事件推送
  3. 验证图像存储
  4. 验证元数据记录
- 使用 Mock 后端避免真实 API 调用
- 测试错误处理场景

**测试用例**:
- 同步生成流程（OpenAI）
- 异步生成流程（任务轮询型）
- 超时处理
- 后端不可用回退
- 多客户端 WebSocket 推送

**验证**:
- `cd backend && python -m pytest tests/test_image_integration.py -v` → exit_code == 0

**输出文件**:
- `backend/tests/test_image_integration.py`
- `backend/tests/conftest.py` (更新，添加 fixtures)

---

### Task 7.15: 添加配置和环境变量

**执行**:
- 更新 `backend/src/config/settings.py`
- 添加图像服务相关配置：
  ```python
  # 图像服务配置
  IMAGE_STORAGE_TYPE: str = "local"  # local | oss | s3
  IMAGE_STORAGE_PATH: str = "data/projects"
  IMAGE_PROVIDERS_PATH: str = "config/image_providers.yaml"
  IMAGE_DEFAULT_PROVIDER: str = "openai_default"

  # 后端服务配置（通过 provider 配置引用环境变量）
  OPENAI_API_KEY: str = ""

  # 生成配置
  IMAGE_GENERATION_TIMEOUT: int = 120  # 秒
  IMAGE_ENABLE_PROMPT_ENHANCEMENT: bool = True
  ```
- 更新 `.env.example`

**验证**:
- 配置可正确加载
- 缺少必要配置时有友好提示

**输出文件**:
- `backend/src/config/settings.py` (更新)
- `backend/.env.example` (更新)

## 验收标准

- [ ] 视觉概念 Agent 可作为团队成员参与讨论 (Spec AC-23)
- [ ] 视觉概念 Agent 可被其他 Agent 调用生成配图 (Spec AC-24)
- [ ] 支持至少 2 个图像生成后端 (Spec AC-25)
  - OpenAI（同步）
  - OpenAI 兼容或任务轮询型（异步）
- [ ] 风格模板可通过 YAML 配置文件扩展 (Spec AC-26)
- [ ] 简单图片同步返回，复杂图片异步推送 (Spec AC-27)
- [ ] 生成的图片正确存储并可通过 API 访问 (Spec AC-28)
- [ ] 图片元数据正确记录并与讨论关联 (Spec AC-29)
- [ ] 所有单元测试通过
- [ ] 集成测试覆盖主要流程

## 暂不实现（P2 或后续迭代）

根据 Spec 2.7"暂不实现"章节，以下功能在本 Plan 中预留接口但不完整实现：

- F-35 自动配图 - 讨论结束后自动配图
- 成本控制机制
- 图片编辑功能（裁剪、调整）
- 图生图功能（基于已有图片生成变体）
- 批量生成功能
- 云存储完整实现（仅预留接口）
