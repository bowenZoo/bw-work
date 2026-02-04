# Plan: 前端可视化

> **模块**: frontend
> **优先级**: P1
> **对应 Spec**: docs/spec.md#2.3

## 目标

搭建 Vue 3 前端框架，实现：
1. 讨论界面（类聊天界面）
2. Agent 头像和状态显示
3. WebSocket 实时通信
4. 基础布局和样式

## 前置依赖

- `plan-backend-core.md` - 需要后端 API 接口

## 技术方案

### 架构设计

```
frontend/
├── src/
│   ├── assets/              # 静态资源
│   │   └── agents/          # Agent 头像
│   ├── components/          # 组件
│   │   ├── chat/            # 聊天组件
│   │   │   ├── ChatContainer.vue
│   │   │   ├── MessageBubble.vue
│   │   │   └── InputBox.vue
│   │   ├── agent/           # Agent 组件
│   │   │   ├── AgentAvatar.vue
│   │   │   └── AgentStatus.vue
│   │   └── layout/          # 布局组件
│   │       ├── Header.vue
│   │       └── Sidebar.vue
│   ├── composables/         # 组合式函数
│   │   ├── useWebSocket.ts
│   │   └── useDiscussion.ts
│   ├── stores/              # Pinia 状态
│   │   ├── discussion.ts
│   │   └── agents.ts
│   ├── types/               # TypeScript 类型
│   │   └── index.ts
│   ├── views/               # 页面
│   │   ├── HomeView.vue
│   │   └── DiscussionView.vue
│   ├── App.vue
│   ├── main.ts
│   └── router.ts
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
└── tailwind.config.js
```

### 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| 构建工具 | Vite | 快速开发，HMR 支持 |
| UI 框架 | Vue 3 | 项目技术栈指定 |
| 状态管理 | Pinia | Vue 3 官方推荐 |
| 样式 | TailwindCSS | 项目技术栈指定，快速开发 |
| 实时通信 | WebSocket | 原生 API，足够简单 |
| 类型 | TypeScript | 项目技术栈指定 |

## 任务清单

### Task 2.1: 初始化 Vue 3 项目

**执行**:
- 使用 `pnpm create vite frontend --template vue-ts`
- 安装依赖：`pinia`, `vue-router`, `tailwindcss`, `vue-tsc`, `lucide-vue-next`（图标库）
- 配置 TailwindCSS
- 配置 TypeScript
- 在 package.json 添加 script: `"type-check": "vue-tsc --noEmit"`
- 配置 vite.config.ts 开发服务器端口为 18001：
  ```ts
  server: { port: 18001 }
  ```

**验证**:
- `cd frontend && pnpm install && pnpm build` → exit_code == 0
- `cd frontend && pnpm dev &; sleep 5; curl http://localhost:18001; kill %1` → 返回 HTML

**输出文件**:
- `frontend/package.json`
- `frontend/vite.config.ts`
- `frontend/tsconfig.json`
- `frontend/tailwind.config.js`
- `frontend/postcss.config.js`
- `frontend/src/main.ts`
- `frontend/src/App.vue`

---

### Task 2.2: 定义 TypeScript 类型

**执行**:
- 创建 `frontend/src/types/index.ts`
- **按 plan-websocket.md 的消息协议定义类型，确保前后端一致**：
  - `ServerMessage` - type: 'message' | 'status' | 'error' | 'pong'，data 结构与后端一致
  - `Agent` - id, name, role, status: 'thinking' | 'speaking' | 'idle'
  - `Message` - id, agentId, agentRole, content, timestamp
  - `Discussion` - id, topic, messages, status

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0

**输出文件**:
- `frontend/src/types/index.ts`

---

### Task 2.3: 实现 Pinia 状态管理

**执行**:
- 创建 `frontend/src/stores/agents.ts` - Agent 状态
- 创建 `frontend/src/stores/discussion.ts` - 讨论状态
- 实现 actions：addMessage, setAgentStatus, startDiscussion

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0

**输出文件**:
- `frontend/src/stores/agents.ts`
- `frontend/src/stores/discussion.ts`
- `frontend/src/stores/index.ts`

---

### Task 2.4: 实现 WebSocket 通信

**执行**:
- 创建 `frontend/src/composables/useWebSocket.ts`
- **连接地址配置**：从 `import.meta.env.VITE_WS_URL` 读取，默认 `ws://localhost:18000`
- 实现连接、断开逻辑
- **重连策略**：固定 3 秒间隔，最多重试 5 次，超过后更新状态提示用户刷新
- 实现消息接收和发送（ping 心跳）
- 处理连接状态：connecting / connected / disconnected / error

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0

**输出文件**:
- `frontend/src/composables/useWebSocket.ts`

---

### Task 2.5: 实现聊天消息组件

**执行**:
- 创建 `frontend/src/components/chat/MessageBubble.vue`
- 显示 Agent 头像、名称、消息内容
- 区分不同 Agent 的消息样式
- 显示消息时间戳

**验证**:
- 组件可正常渲染，无 TypeScript 错误

**输出文件**:
- `frontend/src/components/chat/MessageBubble.vue`

---

### Task 2.6: 实现聊天容器组件

**执行**:
- 创建 `frontend/src/components/chat/ChatContainer.vue`
- 消息列表展示，自动滚动到底部
- 加载状态显示
- 空状态处理

**验证**:
- 组件可正常渲染，消息列表滚动正常

**输出文件**:
- `frontend/src/components/chat/ChatContainer.vue`

---

### Task 2.7: 实现输入框组件

**执行**:
- 创建 `frontend/src/components/chat/InputBox.vue`
- 话题输入框
- 发送按钮
- 禁用状态（讨论进行中）

**验证**:
- 组件可正常渲染，输入和提交功能正常

**输出文件**:
- `frontend/src/components/chat/InputBox.vue`
- `frontend/src/components/chat/index.ts`

---

### Task 2.8: 实现 Agent 头像组件

**执行**:
- 创建 `frontend/src/components/agent/AgentAvatar.vue`
- **头像方案**：使用 Heroicons 或 Lucide 图标库（需在 Task 2.1 安装 `@heroicons/vue` 或 `lucide-vue-next`）
  - 系统策划：Cog / Settings 图标
  - 数值策划：Calculator 图标
  - 玩家代言人：UserCircle / ExclamationTriangle 图标
- 根据 Agent role 映射对应图标
- 显示状态指示器（idle/thinking/speaking 用不同颜色圆点）

**验证**:
- 组件可正常渲染，状态切换正常

**输出文件**:
- `frontend/src/components/agent/AgentAvatar.vue`

---

### Task 2.9: 实现 Agent 状态面板

**执行**:
- 创建 `frontend/src/components/agent/AgentStatus.vue`
- 显示 Agent 列表
- 显示当前发言者
- 显示各 Agent 状态

**验证**:
- 组件可正常渲染，状态更新正常

**输出文件**:
- `frontend/src/components/agent/AgentStatus.vue`
- `frontend/src/components/agent/index.ts`

---

### Task 2.10: 实现布局组件

**执行**:
- 创建 `frontend/src/components/layout/Header.vue` - 顶部导航
- 创建 `frontend/src/components/layout/Sidebar.vue` - 侧边栏（Agent 面板）
- 实现响应式布局

**验证**:
- 布局在不同屏幕尺寸下正常显示

**输出文件**:
- `frontend/src/components/layout/Header.vue`
- `frontend/src/components/layout/Sidebar.vue`
- `frontend/src/components/layout/index.ts`

---

### Task 2.11: 实现讨论页面

**执行**:
- 创建 `frontend/src/views/DiscussionView.vue`
- 整合聊天容器、输入框、Agent 状态面板
- 连接 WebSocket
- 处理讨论生命周期

**验证**:
- 页面可正常加载和交互

**输出文件**:
- `frontend/src/views/DiscussionView.vue`
- `frontend/src/views/HomeView.vue`

---

### Task 2.12: 配置路由

**执行**:
- 创建 `frontend/src/router.ts`
- 配置首页路由 `/`
- 配置讨论页路由 `/discussion/:id?`

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0
- 路由跳转正常

**输出文件**:
- `frontend/src/router.ts`
- `frontend/src/main.ts` (更新，引入 router)

---

### Task 2.13: 实现讨论业务逻辑

**执行**:
- 创建 `frontend/src/composables/useDiscussion.ts`
- 实现创建讨论、启动讨论、接收消息
- **对接后端 API**（见 plan-backend-core.md Task 1.7）：
  - `POST /api/discussions` - 创建讨论，返回 discussion_id
  - `GET /api/discussions/{id}` - 获取讨论状态
  - `POST /api/discussions/{id}/start` - 启动讨论
- API Base URL 从 `import.meta.env.VITE_API_URL` 读取，默认 `http://localhost:18000`

**验证**:
- 可创建讨论并接收实时消息

**输出文件**:
- `frontend/src/composables/useDiscussion.ts`
- `frontend/src/api/discussion.ts`

## 验收标准

- [ ] 前端可正常显示讨论对话 (Spec AC-09)
- [ ] 每条消息标识发言的 Agent (Spec AC-10)
- [ ] 页面实时更新，无需手动刷新 (Spec AC-11)
- [ ] WebSocket 连接稳定，支持断线重连
- [ ] TailwindCSS 样式正确应用
- [ ] TypeScript 无类型错误
- [ ] 首屏加载时间 < 3s
