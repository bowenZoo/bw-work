# Plan: 讨论系统 V2 - 议程管理与圆桌 UI

> **模块**: discussion-v2-agenda
> **优先级**: P1
> **对应 Spec**: docs/spec-discussion-v2.md#2.5(议程管理), #4.2(圆桌布局)

## 目标

1. 实现动态议程管理（议题列表、状态追踪、小结生成）
2. 重构前端为圆桌布局（头像围绕、历史记录、当前发言）
3. 议题小结支持预览和下载

## 前置依赖

- plan-discussion-v2-global.md (全局讨论)
- plan-discussion-v2-parallel.md (并行发言)

## 技术方案

### 议程数据模型

```python
class AgendaItem(BaseModel):
    id: str
    title: str
    status: Literal["pending", "in_progress", "completed", "skipped"]
    summary: str | None = None
    created_at: datetime

class Agenda(BaseModel):
    items: list[AgendaItem]
    current_index: int = 0
```

### 圆桌布局

```
┌─────────────────────────────────────────────────────────────────────┐
│ 📋 角色养成系统设计                              [📎附件] [⏸暂停]  │
├─────────────────────────────────────────────┬───────────────────────┤
│ 📝 议程 - 🔵 2. 养成系统 ← 当前    [展开▼]  │ 💬 当前发言          │
├─────────────────────────────────────────────┤                       │
│                                             │ 👑 主策划:            │
│      👤 系统策划      👤 数值策划           │                       │
│       (思考中)          (空闲)              │ "养成系统我建议       │
│           ╲              ╱                  │  分三层：..."         │
│             ╲    💬    ╱                    │                       │
│           ╱      ╲                          │                       │
│      👤 玩家代言人    👑 主策划             │                       │
│         (空闲)        (发言中)              │                       │
├─────────────────────────────────────────────┤                       │
│ ▼ 历史记录 [全部|主策划|系统|数值|玩家]     │                       │
│ 👑: 今天讨论角色养成系统...                 │                       │
│ 👤: 从系统角度来看...                       │                       │
├─────────────────────────────────────────────┴───────────────────────┤
│ 💬 [用户输入：发表你的观点...]                              [发送]  │
└─────────────────────────────────────────────────────────────────────┘
```

## 任务清单

### Task V2A-4.1: 后端议程数据模型

**执行**:
- 创建 `backend/src/models/agenda.py`
- 定义议程相关数据模型

```python
from datetime import datetime
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field

class AgendaItemStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"

class AgendaItem(BaseModel):
    """单个议题"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: str | None = None
    status: AgendaItemStatus = AgendaItemStatus.PENDING
    summary: str | None = None  # 议题小结
    summary_details: dict | None = None  # 详细小结（观点、结论等）
    started_at: datetime | None = None
    completed_at: datetime | None = None

class Agenda(BaseModel):
    """讨论议程"""
    items: list[AgendaItem] = Field(default_factory=list)
    current_index: int = 0

    @property
    def current_item(self) -> AgendaItem | None:
        if 0 <= self.current_index < len(self.items):
            return self.items[self.current_index]
        return None

    def add_item(self, title: str, description: str | None = None) -> AgendaItem:
        item = AgendaItem(title=title, description=description)
        self.items.append(item)
        return item

    def start_current(self) -> None:
        if self.current_item:
            self.current_item.status = AgendaItemStatus.IN_PROGRESS
            self.current_item.started_at = datetime.now()

    def complete_current(self, summary: str) -> None:
        if self.current_item:
            self.current_item.status = AgendaItemStatus.COMPLETED
            self.current_item.summary = summary
            self.current_item.completed_at = datetime.now()
            self.current_index += 1

    def skip_current(self) -> None:
        if self.current_item:
            self.current_item.status = AgendaItemStatus.SKIPPED
            self.current_index += 1
```

**验证**:
- `cd backend && python -c "from src.models.agenda import Agenda, AgendaItem; print('ok')"` → exit_code == 0

**输出文件**:
- `backend/src/models/__init__.py`
- `backend/src/models/agenda.py`

---

### Task V2A-4.2: 主策划生成初始议程

**执行**:
- 更新 `backend/src/agents/lead_planner.py`
- 添加 `create_agenda_prompt()` 方法
- 主策划开场时生成初始议程

```python
def create_agenda_prompt(self, topic: str, attachment: str | None = None) -> str:
    """生成议程规划 prompt"""
    return f"""
作为主策划，请为以下议题规划讨论议程：

议题：{topic}
{f"参考资料：{attachment[:1000]}..." if attachment else ""}

请规划 3-5 个需要讨论的关键点，按讨论优先级排序。
输出格式：
```agenda
1. [议题标题1] - 简要描述
2. [议题标题2] - 简要描述
...
```
"""

def parse_agenda_output(output: str) -> list[dict]:
    """解析议程输出"""
    items = []
    # 匹配格式：1. [标题] - 描述 或 1. 标题 - 描述
    pattern = r'\d+\.\s*\[?([^\]\n-]+)\]?\s*[-—]\s*(.+)'
    for match in re.finditer(pattern, output):
        items.append({
            "title": match.group(1).strip(),
            "description": match.group(2).strip(),
        })
    return items
```

**验证**:
- `cd backend && python -c "from src.agents.lead_planner import parse_agenda_output; print('ok')"` → exit_code == 0

**输出文件**:
- `backend/src/agents/lead_planner.py` (更新)

---

### Task V2A-4.3: 议程管理 API

**执行**:
- 更新 `backend/src/api/routes/discussion.py`
- 添加议程相关 API 端点

```python
class AgendaItemResponse(BaseModel):
    id: str
    title: str
    description: str | None
    status: str
    summary: str | None

class AgendaResponse(BaseModel):
    items: list[AgendaItemResponse]
    current_index: int

@router.get("/current/agenda", response_model=AgendaResponse)
async def get_current_agenda():
    """获取当前讨论的议程"""
    discussion = get_current_discussion()
    if discussion is None:
        raise HTTPException(404, "无活跃讨论")
    # 从讨论状态中获取议程
    return AgendaResponse(...)

@router.post("/current/agenda/items")
async def add_agenda_item(request: AddAgendaItemRequest):
    """添加新议题（主策划动态添加）"""
    ...

@router.post("/current/agenda/items/{item_id}/skip")
async def skip_agenda_item(item_id: str):
    """跳过某个议题"""
    ...

@router.get("/current/agenda/items/{item_id}/summary")
async def get_agenda_item_summary(item_id: str):
    """获取议题小结"""
    ...
```

**验证**:
- `cd backend && python -m pytest tests/test_discussion.py -v -k agenda` → exit_code == 0

**输出文件**:
- `backend/src/api/routes/discussion.py` (更新)

---

### Task V2A-4.4: 议题小结生成

**执行**:
- 更新 `backend/src/crew/discussion_crew.py`
- 议题完成时自动生成小结
- 小结格式符合 Spec 要求

```python
async def _generate_agenda_item_summary(
    self,
    item: AgendaItem,
    discussion_content: str,
) -> str:
    """生成议题小结"""
    prompt = f"""
请为以下议题生成讨论小结：

议题：{item.title}

讨论内容：
{discussion_content}

请按以下格式输出：

# 议题小结：{item.title}

## 讨论结论
- 结论1
- 结论2

## 各方观点
- 系统策划：...
- 数值策划：...
- 玩家代言人：...

## 遗留问题
- 问题1（如有）

## 下一步行动
- 行动1
"""
    # 调用 LLM 生成
    ...
```

**小结数据结构**:
```python
class AgendaSummaryDetails(BaseModel):
    conclusions: list[str]  # 讨论结论
    viewpoints: dict[str, str]  # 各方观点 {角色: 观点}
    open_questions: list[str]  # 遗留问题
    next_steps: list[str]  # 下一步行动
```

**验证**:
- `cd backend && python -m pytest tests/test_discussion_crew.py -v -k summary` → exit_code == 0

**输出文件**:
- `backend/src/crew/discussion_crew.py` (更新)
- `backend/src/models/agenda.py` (更新)

---

### Task V2A-4.5: 前端议程组件

**执行**:
- 创建 `frontend/src/components/discussion/AgendaPanel.vue`
- 功能:
  - 显示议程列表
  - 高亮当前议题
  - 已完成议题可点击查看小结
  - 支持展开/收起

**Props**:
```typescript
interface Props {
  agenda: Agenda
  collapsed?: boolean
}
```

**样式**:
```
📝 议程 - 🔵 2. 养成系统 ← 当前    [展开▼]
──────────────────────────────────────────
展开后：
✅ 1. 核心玩法定义           [查看小结]
🔵 2. 付费模式设计  ← 当前
⬜ 3. 数值平衡方案
⬜ 4. 新手引导流程
➕ [主策划可添加新议题]
```

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0

**输出文件**:
- `frontend/src/components/discussion/AgendaPanel.vue`

---

### Task V2A-4.6: 前端议题小结 Modal

**执行**:
- 创建 `frontend/src/components/discussion/AgendaSummaryModal.vue`
- 功能:
  - Modal 展示议题小结
  - Markdown 渲染
  - 下载为 Markdown 文件
  - 分享链接（可选）

**Props**:
```typescript
interface Props {
  visible: boolean
  item: AgendaItem | null
}
```

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0

**输出文件**:
- `frontend/src/components/discussion/AgendaSummaryModal.vue`

---

### Task V2A-4.7: 前端圆桌布局组件

**执行**:
- 创建 `frontend/src/components/discussion/RoundTable.vue`
- 功能:
  - 4 个头像围绕中心
  - 头像状态显示（idle/thinking/speaking）
  - 点击头像筛选历史发言

**Props**:
```typescript
interface Props {
  agents: Agent[]
  statuses: Map<string, AgentStatus>
  currentSpeaker?: string
}
```

**头像布局（CSS Grid 或 Flex）**:
```
      👤 系统策划      👤 数值策划
       (思考中)          (空闲)
           ╲              ╱
             ╲    💬    ╱
           ╱      ╲
      👤 玩家代言人    👑 主策划
         (空闲)        (发言中)
```

**头像状态样式**:
- idle: 灰色边框
- thinking: 黄色脉冲动画 + "思考中"文字
- speaking: 绿色光晕 + 放大 1.2x

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0

**输出文件**:
- `frontend/src/components/discussion/RoundTable.vue`

---

### Task V2A-4.8: 前端当前发言组件

**执行**:
- 创建 `frontend/src/components/discussion/CurrentSpeech.vue`
- 功能:
  - 大块区域显示当前发言
  - Markdown 渲染
  - 实时打字机效果（可选）
  - 发言角色和头像显示

**Props**:
```typescript
interface Props {
  speaker: Agent | null
  content: string
  isStreaming?: boolean
}
```

**样式**:
```
┌─────────────────────────────────┐
│ 💬 当前发言                      │
│                                 │
│ 👑 主策划:                       │
│                                 │
│ "养成系统我建议分三层：          │
│  - 基础属性                      │
│  - 技能成长                      │
│  - 装备强化                      │
│                                 │
│  系统策划觉得技术上可行吗？"     │
│                                 │
└─────────────────────────────────┘
```

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0

**输出文件**:
- `frontend/src/components/discussion/CurrentSpeech.vue`

---

### Task V2A-4.9: 前端历史记录组件

**执行**:
- 创建 `frontend/src/components/discussion/HistoryPanel.vue`
- 功能:
  - 消息列表展示
  - Tab 切换筛选（全部/主策划/系统/数值/玩家）
  - 滚动加载更多
  - 点击消息跳转到对应议题

**Props**:
```typescript
interface Props {
  messages: Message[]
  filter?: string  // 筛选角色
}
```

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0

**输出文件**:
- `frontend/src/components/discussion/HistoryPanel.vue`

---

### Task V2A-4.10: 重构讨论页面为圆桌布局

**执行**:
- 更新 `frontend/src/views/DiscussionView.vue`
- 整合新组件：
  - 顶部：TopicCard + 暂停按钮
  - 左上：AgendaPanel
  - 左中：RoundTable
  - 左下：HistoryPanel
  - 右侧：CurrentSpeech
  - 底部：UserInputBox

**布局结构**:
```vue
<template>
  <div class="discussion-layout">
    <!-- 顶部栏 -->
    <header class="discussion-header">
      <TopicCard :topic="..." />
      <div class="actions">
        <button @click="toggleAttachment">📎附件</button>
        <button @click="togglePause">⏸暂停</button>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="discussion-main">
      <!-- 左侧面板 -->
      <aside class="left-panel">
        <AgendaPanel :agenda="agenda" />
        <RoundTable :agents="agents" :statuses="statuses" />
        <HistoryPanel :messages="messages" />
      </aside>

      <!-- 右侧发言区 -->
      <section class="right-panel">
        <CurrentSpeech :speaker="currentSpeaker" :content="currentContent" />
      </section>
    </main>

    <!-- 底部输入 -->
    <footer class="discussion-footer">
      <UserInputBox @send="handleUserMessage" />
    </footer>
  </div>
</template>

<style>
.discussion-layout {
  display: grid;
  grid-template-rows: auto 1fr auto;
  height: 100vh;
}

.discussion-main {
  display: grid;
  grid-template-columns: 60% 40%;
  overflow: hidden;
}

.left-panel {
  display: flex;
  flex-direction: column;
}

/* 响应式 */
@media (max-width: 768px) {
  .discussion-main {
    grid-template-columns: 1fr;
  }
  .right-panel {
    display: none; /* 或改为 Tab 切换 */
  }
}
</style>
```

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0
- 布局在桌面和移动端正确显示

**输出文件**:
- `frontend/src/views/DiscussionView.vue` (更新)

---

### Task V2A-4.11: WebSocket 议程事件

**执行**:
- 更新 `backend/src/api/websocket/events.py`
- 添加议程相关事件

```python
class AgendaEventType(str, Enum):
    AGENDA_INIT = "agenda_init"      # 初始化议程
    ITEM_START = "item_start"        # 开始议题
    ITEM_COMPLETE = "item_complete"  # 完成议题
    ITEM_SKIP = "item_skip"          # 跳过议题
    ITEM_ADD = "item_add"            # 添加议题

class AgendaEvent(BaseModel):
    type: AgendaEventType
    data: dict
```

- 更新 `DiscussionCrew` 广播议程变更

**验证**:
- `cd backend && python -c "from src.api.websocket.events import AgendaEvent; print('ok')"` → exit_code == 0

**输出文件**:
- `backend/src/api/websocket/events.py` (更新)
- `backend/src/crew/discussion_crew.py` (更新)

---

### Task V2A-4.12: 前端议程状态同步

**执行**:
- 更新 `frontend/src/composables/useGlobalDiscussion.ts`
- 处理议程相关 WebSocket 事件
- 更新议程状态

```typescript
function handleAgendaEvent(event: AgendaEvent) {
  switch (event.type) {
    case 'agenda_init':
      agenda.value = event.data
      break
    case 'item_start':
      updateAgendaItem(event.data.item_id, { status: 'in_progress' })
      break
    case 'item_complete':
      updateAgendaItem(event.data.item_id, {
        status: 'completed',
        summary: event.data.summary,
      })
      break
    // ...
  }
}
```

**验证**:
- `cd frontend && pnpm run type-check` → exit_code == 0
- 议程状态实时同步

**输出文件**:
- `frontend/src/composables/useGlobalDiscussion.ts` (更新)
- `frontend/src/stores/discussion.ts` (更新)

## 验收标准

- [ ] 讨论开始时显示初始议程
- [ ] 当前议题高亮显示
- [ ] 议题完成后生成小结
- [ ] 已完成议题可点击查看小结
- [ ] 圆桌布局正确显示 4 个角色
- [ ] 头像状态正确反映 Agent 状态
- [ ] 历史记录支持按角色筛选
- [ ] 当前发言区 Markdown 正确渲染
- [ ] 响应式布局在移动端可用
- [ ] TypeScript 无类型错误
