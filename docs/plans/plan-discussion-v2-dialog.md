# Plan: 讨论系统 V2 - 精简对话与议题展示

> **模块**: discussion-v2-dialog
> **优先级**: P0
> **对应 Spec**: docs/spec-discussion-v2.md#2.4, #2.5

## 目标

1. 优化 Agent prompt，限制输出长度（< 200 字）
2. 前端添加议题卡片组件，展示讨论议题和附件
3. 附件支持 Modal 预览（Markdown 渲染）

## 前置依赖

- 无（可独立执行）

## 技术方案

### 架构设计

```
backend/src/config/roles/
├── system_designer.yaml    # 更新 prompt 约束
├── number_designer.yaml    # 更新 prompt 约束
├── player_advocate.yaml    # 更新 prompt 约束
└── lead_planner.yaml       # 更新 prompt 约束

frontend/src/
├── components/
│   └── discussion/
│       ├── TopicCard.vue       # 新增：议题卡片
│       └── AttachmentPreview.vue  # 新增：附件预览 Modal
└── views/
    └── DiscussionView.vue      # 更新：集成议题卡片
```

### Prompt 约束模板

```yaml
constraints:
  - 每次发言不超过 200 字
  - 直击要点，不说废话
  - 有不同意见直接说，不绕弯
  - 不重复别人说过的内容
  - 如需详述，等主策划追问
```

## 任务清单

### Task V2D-1.1: 更新 Agent Prompt 约束

**执行**:
- 更新 `backend/src/config/roles/system_designer.yaml`
  - 在 `backstory` 末尾添加约束
  - 在 `goal` 中强调简洁表达
- 更新 `backend/src/config/roles/number_designer.yaml`
  - 同上约束
- 更新 `backend/src/config/roles/player_advocate.yaml`
  - 同上约束
- 更新 `backend/src/config/roles/lead_planner.yaml`
  - 添加约束
  - 增加控场职责：决定何时深入、何时下一话题

**约束内容**（添加到每个 YAML 的 backstory）:
```yaml
## 发言规范
- 每次发言控制在 200 字以内
- 直击要点，不说废话和客套话
- 有不同意见直接说，不需要铺垫
- 不重复其他角色已说过的内容
- 如需详细展开，等主策划追问再补充
```

**验证**:
- `cd backend && python -c "from src.agents import SystemDesigner; a = SystemDesigner(); print(len(a._config.backstory) > 100)"` → exit_code == 0

**输出文件**:
- `backend/src/config/roles/system_designer.yaml` (更新)
- `backend/src/config/roles/number_designer.yaml` (更新)
- `backend/src/config/roles/player_advocate.yaml` (更新)
- `backend/src/config/roles/lead_planner.yaml` (更新)

---

### Task V2D-1.2: 创建议题卡片组件

**执行**:
- 创建 `frontend/src/components/discussion/TopicCard.vue`
- Props:
  - `topic: string` - 议题标题
  - `status: 'pending' | 'running' | 'completed'` - 讨论状态
  - `attachment?: { filename: string; content: string }` - 附件信息
- 功能:
  - 显示议题标题
  - 显示讨论状态（图标 + 文字）
  - 附件按钮（有附件时显示）
  - 点击附件按钮触发 `@preview-attachment` 事件

**样式设计**:
```
┌─────────────────────────────────────┐
│ 📋 讨论议题                           │
├─────────────────────────────────────┤
│ 《角色养成系统设计》                  │
│                                      │
│ 附件：[📄 GDD.md]  ← 点击预览        │
│                                      │
│ 状态：🔵 进行中                       │
└─────────────────────────────────────┘
```

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0

**输出文件**:
- `frontend/src/components/discussion/TopicCard.vue`
- `frontend/src/components/discussion/index.ts`

---

### Task V2D-1.3: 创建附件预览 Modal 组件

**执行**:
- 创建 `frontend/src/components/discussion/AttachmentPreview.vue`
- Props:
  - `visible: boolean` - 控制显示
  - `filename: string` - 文件名
  - `content: string` - 文件内容（Markdown）
- 功能:
  - Modal 遮罩层
  - 顶部显示文件名 + 关闭按钮
  - 内容区 Markdown 渲染
  - 底部下载按钮（可选）
- 事件:
  - `@close` - 关闭 Modal
- Markdown 渲染使用 `marked` 库（已安装）或 Vue 内置方案

**样式设计**:
```
┌──────────────────────────────────────┐
│ 📄 GDD.md                        [X] │
├──────────────────────────────────────┤
│                                      │
│  # 游戏设计文档                       │
│                                      │
│  ## 核心玩法                          │
│  - 角色养成                          │
│  - 战斗系统                          │
│  ...                                 │
│                                      │
├──────────────────────────────────────┤
│                         [下载] [关闭] │
└──────────────────────────────────────┘
```

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0

**输出文件**:
- `frontend/src/components/discussion/AttachmentPreview.vue`

---

### Task V2D-1.4: 集成议题卡片到讨论页面

**执行**:
- 更新 `frontend/src/views/DiscussionView.vue`
- 在消息流上方添加 `TopicCard` 组件
- 添加 `AttachmentPreview` Modal
- 状态管理:
  - `showAttachmentPreview: boolean`
  - `currentAttachment: { filename: string; content: string } | null`
- 事件处理:
  - `handlePreviewAttachment()` - 打开预览
  - `handleClosePreview()` - 关闭预览

**数据来源**:
- 从 `GET /api/discussions/{id}` 获取讨论详情
- 从响应中提取 `topic` 和 `attachment`
- 需确认后端 API 是否返回 attachment 字段（现有 API 已支持）

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0
- 讨论页面显示议题卡片
- 点击附件可打开预览 Modal

**输出文件**:
- `frontend/src/views/DiscussionView.vue` (更新)

---

### Task V2D-1.5: 添加 Markdown 渲染依赖

**执行**:
- 检查 `frontend/package.json` 是否已有 `marked` 或 `markdown-it`
- 如无，安装 `marked` + `@types/marked`:
  ```bash
  cd frontend && pnpm add marked @types/marked
  ```
- 创建 `frontend/src/utils/markdown.ts` 封装 Markdown 渲染函数
  - `renderMarkdown(content: string): string`
  - 配置安全选项（sanitize）
  - 代码高亮支持（可选，使用 highlight.js）

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0
- `cd frontend && pnpm build` → exit_code == 0

**输出文件**:
- `frontend/package.json` (更新，如需安装)
- `frontend/src/utils/markdown.ts`

---

### Task V2D-1.6: 用户参与输入框组件

**执行**:
- 创建 `frontend/src/components/discussion/UserInputBox.vue`
- Props:
  - `disabled: boolean` - 讨论结束时禁用
  - `placeholder?: string` - 占位文本
- 功能:
  - 文本输入框（限制 200 字）
  - 发送按钮
  - 字数统计显示
  - 节流控制（每分钟最多 2 条）
- 事件:
  - `@send(content: string)` - 发送消息

**限制逻辑**:
```typescript
// 节流控制
const lastSentTimes: number[] = []
const MAX_MESSAGES_PER_MINUTE = 2

function canSend(): boolean {
  const now = Date.now()
  // 清理超过 1 分钟的记录
  while (lastSentTimes.length && now - lastSentTimes[0] > 60000) {
    lastSentTimes.shift()
  }
  return lastSentTimes.length < MAX_MESSAGES_PER_MINUTE
}
```

**样式设计**:
```
────────────────────────────────────────
💬 [发表你的观点...]           12/200 [发送]
────────────────────────────────────────
```

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0

**输出文件**:
- `frontend/src/components/discussion/UserInputBox.vue`

---

### Task V2D-1.7: 集成用户输入到讨论页面

**执行**:
- 更新 `frontend/src/views/DiscussionView.vue`
- 在页面底部添加 `UserInputBox` 组件
- 发送消息时调用 `POST /api/discussions/{id}/inject` API
- 显示用户消息到消息流（role: "User"）

**API 调用**（已有，见 intervention.py）:
```typescript
async function sendUserMessage(content: string) {
  await api.post(`/discussions/${discussionId}/inject`, {
    content,
    save_to_memory: true,
  })
}
```

**状态控制**:
- 讨论 status !== 'running' 时禁用输入框
- 暂停状态时显示提示文字

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0
- 用户输入后消息出现在消息流中
- 主策划能回应用户消息

**输出文件**:
- `frontend/src/views/DiscussionView.vue` (更新)

---

### Task V2D-1.8: 主策划回应用户消息 Prompt

**执行**:
- 更新 `backend/src/config/roles/lead_planner.yaml`
- 在 backstory 中添加用户消息处理逻辑：

```yaml
## 用户消息处理
当收到用户（观众）的消息时：
1. 先简短回应用户（如"感谢反馈"、"好问题"）
2. 判断是否需要其他角色来回答
3. 如需要，点名相关角色回应用户提出的问题
4. 如果是简单问题或建议，可以直接回应
5. 将用户反馈纳入讨论考量
```

- 更新 `backend/src/agents/lead_planner.py`
- 在 `create_round_summary_prompt` 中添加检查用户消息的逻辑

**验证**:
- `cd backend && python -c "from src.agents import LeadPlanner; a = LeadPlanner(); print('用户' in a._config.backstory)"` → exit_code == 0

**输出文件**:
- `backend/src/config/roles/lead_planner.yaml` (更新)
- `backend/src/agents/lead_planner.py` (更新，如需)

## 验收标准

- [ ] Agent 每次发言 < 300 字（允许适当超出，但明显简短）
- [ ] 讨论开始前/中显示议题卡片
- [ ] 附件可点击预览，Markdown 正确渲染
- [ ] 用户可在讨论进行中发送消息
- [ ] 用户消息有频率限制（每分钟 2 条）
- [ ] 主策划能回应用户消息
- [ ] TypeScript 无类型错误
