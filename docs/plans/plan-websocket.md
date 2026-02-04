# Plan: WebSocket 实时通信

> **模块**: websocket
> **优先级**: P0
> **对应 Spec**: docs/spec.md#2.2 (F-10), #2.3 (F-17)

## 目标

实现后端 WebSocket 服务，支持：
1. 讨论过程实时推送
2. 客户端连接管理
3. 消息广播机制

## 前置依赖

- `plan-backend-core.md` - 需要 FastAPI 基础框架

## 技术方案

### 架构设计

```
backend/src/
├── api/
│   └── websocket/
│       ├── __init__.py
│       ├── manager.py       # 连接管理器
│       ├── handlers.py      # 消息处理器
│       └── events.py        # 事件定义
```

### 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| WebSocket | FastAPI WebSocket | 与 FastAPI 无缝集成 |
| 消息格式 | JSON | 通用，易解析 |
| 连接管理 | 内存存储 | MVP 阶段足够，后续可扩展 Redis |

### 消息协议

> **设计决策**: 连接路径 `/ws/{discussion_id}` 已指定讨论 ID，因此协议中不再需要 subscribe/unsubscribe。
> 一个连接对应一个讨论，如需监听多个讨论，客户端建立多个连接即可（MVP 阶段足够）。

```typescript
// 客户端 → 服务端
interface ClientMessage {
  type: 'ping';  // 心跳，其他操作通过 HTTP API
}

// 服务端 → 客户端
interface ServerMessage {
  type: 'message' | 'status' | 'error' | 'pong';
  data: {
    discussion_id: string;
    agent_id?: string;
    agent_role?: string;
    content?: string;
    status?: 'thinking' | 'speaking' | 'idle';
    timestamp: string;
  };
}
```

## 任务清单

### Task 4.1: 实现 WebSocket 连接管理器

**执行**:
- 创建 `backend/src/api/websocket/` 目录
- 创建 `backend/src/api/websocket/manager.py`
- 实现 ConnectionManager 类
- 管理客户端连接（按 discussion_id 分组）
- 实现连接、断开、广播方法

**连接清理策略**:
- 心跳超时：30 秒无 ping 响应则标记为断开
- 断开检测：发送消息时捕获 `WebSocketDisconnect`，立即从连接池移除
- 主动清理：`disconnect()` 时从 `dict[discussion_id, set[websocket]]` 移除
- 内存回收：依赖 Python GC，连接对象无其他引用时自动回收

**验证**:
- `cd backend && python -c "from src.api.websocket.manager import ConnectionManager"` → exit_code == 0

**输出文件**:
- `backend/src/api/websocket/__init__.py`
- `backend/src/api/websocket/manager.py`

---

### Task 4.2: 定义 WebSocket 事件

**执行**:
- 创建 `backend/src/api/websocket/events.py`
- 定义事件类型枚举
- 定义消息数据模型（Pydantic）
- 实现消息序列化

**验证**:
- `cd backend && python -c "from src.api.websocket.events import MessageEvent, StatusEvent"` → exit_code == 0

**输出文件**:
- `backend/src/api/websocket/events.py`

---

### Task 4.3: 实现 WebSocket 端点

**执行**:
- 创建 `backend/src/api/websocket/handlers.py`
- 实现 `/ws/{discussion_id}` 端点
- 处理客户端连接和断开
- 处理心跳（ping/pong）

**验证**:
- WebSocket 连接可正常建立
- 心跳机制正常工作

**输出文件**:
- `backend/src/api/websocket/handlers.py`

---

### Task 4.4: 集成 WebSocket 到主应用

**执行**:
- 更新 `backend/src/api/main.py`
- 挂载 WebSocket 路由
- 实现 WebSocket 跨域检查（在 handler 中校验 `websocket.headers.get("origin")`）

> **注意**: FastAPI 的 CORSMiddleware 仅处理 HTTP 请求，不影响 WebSocket。
> WebSocket 跨域需在接受连接时手动校验 Origin header，拒绝不在允许列表的来源。

**验证**:
- `cd backend && python -m uvicorn src.api.main:app --reload &; sleep 3; kill %1` → 无错误

**输出文件**:
- `backend/src/api/main.py` (更新)

---

### Task 4.5: 实现讨论实时推送

**执行**:
- 更新 `backend/src/crew/discussion_crew.py`
- Agent 发言时触发 WebSocket 广播
- 发送 Agent 状态变更（thinking/speaking/idle）
- 发送讨论结束事件

**异步桥接方案**:
> CrewAI 的 Agent 逻辑是同步的，而 WebSocket 广播是 async。直接 await 会报 event loop 错误。

采用 `asyncio.run_coroutine_threadsafe()` 桥接：
```python
# 在 Crew 同步代码中调用
import asyncio
from src.api.websocket.manager import manager

def broadcast_sync(discussion_id: str, message: dict):
    loop = asyncio.get_event_loop()
    asyncio.run_coroutine_threadsafe(
        manager.broadcast(discussion_id, message),
        loop
    )
```

或者使用消息队列（如 `asyncio.Queue`）解耦，Crew 放消息、WS handler 取消息广播。MVP 阶段用 `run_coroutine_threadsafe` 即可。

**验证**:
- 讨论过程中消息实时推送到客户端
- Agent 状态变更正确广播

**输出文件**:
- `backend/src/crew/discussion_crew.py` (更新)

---

### Task 4.6: 编写 WebSocket 测试

**前置依赖**:
- 确保 `pyproject.toml` 或 `requirements-dev.txt` 包含：
  - `pytest-asyncio` - 异步测试支持
  - `httpx` - TestClient 的 WebSocket 测试支持
  - `websockets`（可选）- 如需真实连接测试

**执行**:
- 创建 `backend/tests/test_websocket.py`
- 测试连接建立和断开
- 测试消息广播
- 测试多客户端场景

**验证**:
- `cd backend && python -m pytest tests/test_websocket.py -v` → exit_code == 0

**输出文件**:
- `backend/tests/test_websocket.py`

## 验收标准

- [ ] 讨论过程在前端实时显示 (Spec AC-06)
- [ ] 页面实时更新，无需手动刷新 (Spec AC-11)
- [ ] WebSocket 延迟体感流畅（观察性指标，目标 < 500ms，可通过浏览器 DevTools Network 面板观察）
- [ ] 支持多客户端同时连接
- [ ] 连接断开后可重连
- [ ] 所有测试通过
