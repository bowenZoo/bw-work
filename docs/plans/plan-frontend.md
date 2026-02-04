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
- 安装依赖：`pinia`, `vue-router`, `tailwindcss`
- 配置 TailwindCSS
- 配置 TypeScript
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
- 定义 Agent 类型（id, name, role, avatar, status）
- 定义 Message 类型（id, agentId, content, timestamp）
- 定义 Discussion 类型（id, topic, messages, status）

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
- 实现连接、断开、重连逻辑
- 实现消息接收和发送
- 处理连接状态

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
- 根据 Agent 角色显示不同头像/图标
- 显示在线/离线/思考中状态

**验证**:
- 组件可正常渲染，状态切换正常

**输出文件**:
- `frontend/src/components/agent/AgentAvatar.vue`
- `frontend/src/assets/agents/` (SVG 图标)

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
- 与后端 API 对接

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
