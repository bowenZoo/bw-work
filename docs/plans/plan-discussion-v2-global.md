# Plan: 讨论系统 V2 - 全局单例讨论

> **模块**: discussion-v2-global
> **优先级**: P0
> **对应 Spec**: docs/spec-discussion-v2.md#2.2

## 目标

实现全站唯一活跃讨论机制：
1. 后端维护全局 `current_discussion_id`
2. 所有用户共享同一个讨论
3. WebSocket 广播给所有客户端（不按 discussion_id 分组）
4. 新用户加入时获取当前讨论状态和历史消息

## 前置依赖

- plan-discussion-v2-dialog.md (可并行，但建议先完成)

## 技术方案

### 架构设计

```
backend/src/api/
├── routes/
│   └── discussion.py          # 更新：全局讨论 API
└── websocket/
    ├── manager.py             # 更新：全局广播模式
    └── handlers.py            # 更新：移除 discussion_id 路径

frontend/src/
├── composables/
│   └── useGlobalDiscussion.ts # 新增：全局讨论 composable
├── stores/
│   └── discussion.ts          # 更新：全局讨论状态
└── views/
    └── DiscussionView.vue     # 更新：使用全局讨论
```

### API 设计

```
GET  /api/discussions/current     # 获取当前活跃讨论
POST /api/discussions/current     # 创建新讨论（替换当前）
POST /api/discussions/current/join # 加入当前讨论（获取历史）

WebSocket: ws://host/ws/discussion  # 移除 {discussion_id}
```

### 全局状态管理

```python
# backend/src/api/routes/discussion.py

import threading

_current_discussion: DiscussionState | None = None
_current_discussion_lock = threading.Lock()

def get_current_discussion() -> DiscussionState | None:
    with _current_discussion_lock:
        return _current_discussion

def set_current_discussion(discussion: DiscussionState | None) -> None:
    with _current_discussion_lock:
        global _current_discussion
        _current_discussion = discussion
```

## 任务清单

### Task V2G-2.1: 后端全局讨论状态管理

**执行**:
- 更新 `backend/src/api/routes/discussion.py`
- 添加全局讨论状态变量和锁:
  ```python
  _current_discussion: DiscussionState | None = None
  _current_discussion_lock = threading.Lock()
  ```
- 实现 `get_current_discussion()` 和 `set_current_discussion()` 函数
- 讨论启动时调用 `set_current_discussion(discussion)`
- 讨论结束时调用 `set_current_discussion(None)`

**状态机**:
```
None → PENDING → RUNNING → COMPLETED → None
                    ↓
                  FAILED → None
```

**验证**:
- `cd backend && python -c "from src.api.routes.discussion import get_current_discussion, set_current_discussion"` → exit_code == 0

**输出文件**:
- `backend/src/api/routes/discussion.py` (更新)

---

### Task V2G-2.2: 实现全局讨论 API 端点

**执行**:
- 更新 `backend/src/api/routes/discussion.py`
- 添加新端点：

**GET /api/discussions/current**:
```python
@router.get("/current", response_model=GetDiscussionResponse | None)
async def get_current_discussion_api():
    """获取当前活跃讨论"""
    discussion = get_current_discussion()
    if discussion is None:
        return None
    return GetDiscussionResponse(...)
```

**POST /api/discussions/current**:
```python
class CreateCurrentDiscussionRequest(BaseModel):
    topic: str
    rounds: int = 3
    attachment: AttachmentInfo | None = None

@router.post("/current", response_model=CreateDiscussionResponse)
async def create_current_discussion(request: CreateCurrentDiscussionRequest):
    """创建新的全局讨论（替换当前）"""
    current = get_current_discussion()
    if current and current.status == DiscussionStatus.RUNNING:
        raise HTTPException(400, "讨论正在进行中，无法创建新讨论")

    # 创建并设置为当前讨论
    discussion = DiscussionState(...)
    set_current_discussion(discussion)

    # 自动启动讨论
    asyncio.create_task(_run_discussion_async(discussion.id))

    return CreateDiscussionResponse(...)
```

**POST /api/discussions/current/join**:
```python
class JoinDiscussionResponse(BaseModel):
    discussion: GetDiscussionResponse | None
    messages: list[MessageResponse]

@router.post("/current/join", response_model=JoinDiscussionResponse)
async def join_current_discussion():
    """加入当前讨论，获取历史消息"""
    discussion = get_current_discussion()
    if discussion is None:
        return JoinDiscussionResponse(discussion=None, messages=[])

    # 从 memory 获取历史消息
    stored = _discussion_memory.load(discussion.id)
    messages = [MessageResponse(...) for m in stored.messages] if stored else []

    return JoinDiscussionResponse(discussion=..., messages=messages)
```

**验证**:
- `cd backend && python -m pytest tests/test_discussion.py -v -k current` → exit_code == 0

**输出文件**:
- `backend/src/api/routes/discussion.py` (更新)

---

### Task V2G-2.3: 重构 WebSocket 为全局广播

**执行**:
- 更新 `backend/src/api/websocket/manager.py`
- 移除按 `discussion_id` 分组的逻辑
- 改为全局连接池:
  ```python
  class GlobalConnectionManager:
      def __init__(self):
          self._connections: set[WebSocket] = set()
          self._lock = asyncio.Lock()

      async def connect(self, websocket: WebSocket):
          await websocket.accept()
          async with self._lock:
              self._connections.add(websocket)

      async def disconnect(self, websocket: WebSocket):
          async with self._lock:
              self._connections.discard(websocket)

      async def broadcast(self, message: dict):
          """广播给所有连接的客户端"""
          async with self._lock:
              for ws in list(self._connections):
                  try:
                      await ws.send_json(message)
                  except Exception:
                      self._connections.discard(ws)
  ```
- 更新 `broadcast_sync()` 函数，移除 `discussion_id` 参数

**验证**:
- `cd backend && python -c "from src.api.websocket.manager import GlobalConnectionManager"` → exit_code == 0

**输出文件**:
- `backend/src/api/websocket/manager.py` (更新)

---

### Task V2G-2.4: 更新 WebSocket Handler

**执行**:
- 更新 `backend/src/api/websocket/handlers.py`
- 移除路径参数 `{discussion_id}`
- 新的端点：`/ws/discussion`
- 连接时：
  1. 接受连接
  2. 获取当前讨论状态
  3. 推送当前讨论信息 + 历史消息
- 消息处理：仅处理 ping/pong

```python
@router.websocket("/ws/discussion")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # 推送当前讨论状态
        current = get_current_discussion()
        if current:
            await websocket.send_json({
                "type": "sync",
                "data": {
                    "discussion": current.model_dump(),
                    "messages": get_discussion_messages(current.id),
                }
            })

        # 保持连接，处理心跳
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
```

**验证**:
- WebSocket 可正常连接到 `/ws/discussion`
- 连接时收到当前讨论状态

**输出文件**:
- `backend/src/api/websocket/handlers.py` (更新)

---

### Task V2G-2.5: 更新 discussion_crew 广播调用

**执行**:
- 更新 `backend/src/crew/discussion_crew.py`
- `broadcast_sync()` 调用移除 `discussion_id` 参数
- 或保留参数但内部忽略（向后兼容）

```python
# 更新前
broadcast_sync(self._discussion_id, event.to_dict())

# 更新后
broadcast_sync(event.to_dict())  # 或 broadcast_sync(self._discussion_id, event.to_dict())
```

**验证**:
- 讨论消息能正确广播到所有客户端

**输出文件**:
- `backend/src/crew/discussion_crew.py` (更新)
- `backend/src/api/websocket/manager.py` (更新 broadcast_sync 签名)

---

### Task V2G-2.6: 前端全局讨论 Composable

**执行**:
- 创建 `frontend/src/composables/useGlobalDiscussion.ts`
- 功能:
  - 连接全局 WebSocket
  - 管理全局讨论状态
  - 提供创建/加入讨论方法

```typescript
import { ref, computed, onMounted, onUnmounted } from 'vue'

export function useGlobalDiscussion() {
  const ws = ref<WebSocket | null>(null)
  const discussion = ref<Discussion | null>(null)
  const messages = ref<Message[]>([])
  const isConnected = ref(false)

  const isDiscussionActive = computed(() =>
    discussion.value?.status === 'running'
  )

  function connect() {
    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:18000'
    ws.value = new WebSocket(`${wsUrl}/ws/discussion`)

    ws.value.onopen = () => {
      isConnected.value = true
    }

    ws.value.onmessage = (event) => {
      const data = JSON.parse(event.data)
      handleMessage(data)
    }

    ws.value.onclose = () => {
      isConnected.value = false
      // 自动重连
      setTimeout(connect, 3000)
    }
  }

  function handleMessage(data: ServerMessage) {
    switch (data.type) {
      case 'sync':
        discussion.value = data.data.discussion
        messages.value = data.data.messages
        break
      case 'message':
        messages.value.push(data.data)
        break
      case 'status':
        // 更新 agent 状态
        break
    }
  }

  async function createDiscussion(topic: string, attachment?: string) {
    const response = await api.post('/discussions/current', {
      topic,
      attachment: attachment ? { filename: 'attachment.md', content: attachment } : null,
    })
    discussion.value = response.data
  }

  async function joinDiscussion() {
    const response = await api.post('/discussions/current/join')
    discussion.value = response.data.discussion
    messages.value = response.data.messages
  }

  onMounted(connect)
  onUnmounted(() => ws.value?.close())

  return {
    discussion,
    messages,
    isConnected,
    isDiscussionActive,
    createDiscussion,
    joinDiscussion,
  }
}
```

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0

**输出文件**:
- `frontend/src/composables/useGlobalDiscussion.ts`

---

### Task V2G-2.7: 更新前端讨论页面

**执行**:
- 更新 `frontend/src/views/DiscussionView.vue`
- 使用 `useGlobalDiscussion()` 替换原有逻辑
- 移除 `discussion_id` 路由参数依赖
- 页面加载时自动加入当前讨论

**路由更新** (`frontend/src/router.ts`):
```typescript
// 更新前
{ path: '/discussion/:id?', component: DiscussionView }

// 更新后
{ path: '/discussion', component: DiscussionView }
```

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0
- 所有用户访问 /discussion 看到同一个讨论

**输出文件**:
- `frontend/src/views/DiscussionView.vue` (更新)
- `frontend/src/router.ts` (更新)

---

### Task V2G-2.8: 更新首页讨论状态展示

**执行**:
- 更新 `frontend/src/views/HomeView.vue` 或 `ProjectView.vue`
- 显示当前全局讨论状态:
  - 无讨论：显示"开始新讨论"按钮
  - 进行中：显示"加入讨论"按钮 + 议题预览
  - 已结束：显示"开始新讨论"按钮 + 最近讨论链接

**状态展示**:
```
┌──────────────────────────────────────┐
│ 🟢 讨论进行中                         │
│ 议题：角色养成系统设计                 │
│ 参与者：4 人正在观看                   │
│                                      │
│        [加入讨论]                     │
└──────────────────────────────────────┘

或

┌──────────────────────────────────────┐
│ ⚪ 当前无讨论                         │
│                                      │
│     [发起新讨论]                      │
└──────────────────────────────────────┘
```

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0
- 首页正确显示当前讨论状态

**输出文件**:
- `frontend/src/views/HomeView.vue` 或 `frontend/src/views/ProjectView.vue` (更新)

---

### Task V2G-2.9: 添加讨论竞争处理

**执行**:
- 更新 `backend/src/api/routes/discussion.py`
- 多用户同时发起新讨论时的处理:
  - 加锁，先到先得
  - 其他用户收到 "讨论已开始" 响应

```python
@router.post("/current", response_model=CreateDiscussionResponse)
async def create_current_discussion(request: CreateCurrentDiscussionRequest):
    with _current_discussion_lock:
        current = _current_discussion
        if current and current.status == DiscussionStatus.RUNNING:
            # 返回已存在的讨论，而不是报错
            return CreateDiscussionResponse(
                id=current.id,
                topic=current.topic,
                rounds=current.rounds,
                status=current.status,
                created_at=current.created_at,
                message="讨论已在进行中，已自动加入"
            )

        # 创建新讨论...
```

**验证**:
- 并发创建请求不会报错
- 后续请求返回已存在的讨论

**输出文件**:
- `backend/src/api/routes/discussion.py` (更新)

---

### Task V2G-2.10: WebSocket 连接数统计

**执行**:
- 更新 `backend/src/api/websocket/manager.py`
- 添加连接数统计方法

```python
class GlobalConnectionManager:
    @property
    def connection_count(self) -> int:
        return len(self._connections)
```

- 更新 WebSocket 事件，包含观看人数
- 前端显示当前观看人数

**广播格式**:
```json
{
  "type": "viewers",
  "data": {
    "count": 5
  }
}
```

**验证**:
- 前端显示观看人数
- 人数随连接/断开实时更新

**输出文件**:
- `backend/src/api/websocket/manager.py` (更新)
- `backend/src/api/websocket/handlers.py` (更新)
- `frontend/src/composables/useGlobalDiscussion.ts` (更新)

## 验收标准

- [ ] 所有用户访问 /discussion 看到同一个讨论 (Spec 验收)
- [ ] 新用户加入时能获取历史消息
- [ ] 讨论结束后，任何用户可发起新讨论
- [ ] 多用户同时发起讨论时不会冲突
- [ ] WebSocket 连接稳定，支持断线重连
- [ ] 首页显示当前讨论状态
- [ ] TypeScript 无类型错误
