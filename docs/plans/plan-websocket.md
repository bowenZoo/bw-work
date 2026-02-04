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

```typescript
// 客户端 → 服务端
interface ClientMessage {
  type: 'subscribe' | 'unsubscribe' | 'ping';
  discussion_id?: string;
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
- 配置 CORS（允许 WebSocket 跨域）

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

**验证**:
- 讨论过程中消息实时推送到客户端
- Agent 状态变更正确广播

**输出文件**:
- `backend/src/crew/discussion_crew.py` (更新)

---

### Task 4.6: 编写 WebSocket 测试

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
- [ ] WebSocket 延迟 < 500ms
- [ ] 支持多客户端同时连接
- [ ] 连接断开后可重连
- [ ] 所有测试通过
