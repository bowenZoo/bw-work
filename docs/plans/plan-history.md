# Plan: 讨论历史与回放

> **模块**: history
> **优先级**: P2
> **对应 Spec**: docs/spec.md#2.3 (F-16)

## 目标

实现讨论历史浏览和回放功能：
1. 历史讨论列表
2. 讨论详情查看
3. 讨论回放（时间线模式）

## 前置依赖

- `plan-frontend.md` - 需要前端基础框架
- `plan-memory.md` - 需要讨论存储功能

## 技术方案

### 架构设计

```
frontend/src/
├── views/
│   └── HistoryView.vue        # 历史列表页
├── components/
│   └── history/
│       ├── HistoryList.vue    # 历史列表
│       ├── HistoryCard.vue    # 历史卡片
│       └── PlaybackControl.vue # 回放控制器
├── composables/
│   └── usePlayback.ts         # 回放逻辑
```

### 回放机制

```typescript
interface PlaybackState {
  discussion: Discussion;
  currentIndex: number;    // 当前消息索引
  isPlaying: boolean;
  speed: number;           // 播放速度 (0.5x, 1x, 2x)
}

// 回放控制
- play(): 开始播放
- pause(): 暂停
- seek(index): 跳转到指定消息
- setSpeed(speed): 设置播放速度

// 时间语义：固定间隔模式
// 每条消息间隔 = 1500ms / speed
// 例如：1x 速度下每 1.5 秒显示一条消息
// 系统消息默认显示，保持回放完整性
```

### 数据一致性假设

- **讨论消息不可变、只追加**：讨论一旦产生，消息序列不可修改或重排
- **列表分页稳定**：新讨论追加在列表头部，不影响已加载页的顺序
- 如需隐藏/删除内容，使用软删除（标记 `deleted_at`），保留原始顺序

## 任务清单

### Task 5.1: 实现历史列表与详情 API

**执行**:
- 确保 `backend/src/api/routes/memory.py` 已实现
- 实现 GET `/api/discussions` 返回列表
  - 支持分页参数（page, limit）
  - 支持按时间排序（created_at DESC）
  - 响应格式：`{ items: Discussion[], hasMore: boolean }`
- 实现 GET `/api/discussions/{id}/messages` 返回讨论消息
  - 消息按 `created_at ASC` 排序（时间顺序，用于回放）
  - 响应格式：`{ discussion: DiscussionMeta, messages: Message[] }`

**验证**:
- `curl http://localhost:18000/api/discussions` → 返回讨论列表，含 hasMore 字段
- `curl http://localhost:18000/api/discussions/{id}/messages` → 返回讨论消息序列

**输出文件**:
- `backend/src/api/routes/memory.py` (确认/更新)

---

### Task 5.2: 实现历史列表组件

**执行**:
- 创建 `frontend/src/components/history/HistoryList.vue`
- 显示讨论列表（话题、时间、消息数）
- 支持无限滚动加载
- 显示空状态

**验证**:
- 组件正常渲染历史列表
- 无限滚动正常工作

**输出文件**:
- `frontend/src/components/history/HistoryList.vue`

---

### Task 5.3: 实现历史卡片组件

**执行**:
- 创建 `frontend/src/components/history/HistoryCard.vue`
- 显示讨论摘要信息
- 显示参与的 Agent 头像
- 点击跳转到详情

**验证**:
- 卡片正常显示讨论信息
- 点击跳转正常

**输出文件**:
- `frontend/src/components/history/HistoryCard.vue`
- `frontend/src/components/history/index.ts`

---

### Task 5.4: 实现历史页面

**执行**:
- 创建 `frontend/src/views/HistoryView.vue`
- 整合历史列表组件
- 添加搜索过滤功能（客户端过滤，适用于小规模数据）
- 配置路由 `/history`

**验证**:
- 历史页面正常加载
- 搜索过滤正常工作

**输出文件**:
- `frontend/src/views/HistoryView.vue`
- `frontend/src/router.ts` (更新)

**备注**: 搜索为客户端过滤实现，在讨论数 < 500 时性能良好。如未来数据量增长，可扩展为后端搜索（添加 `q` 参数）。

---

### Task 5.5: 实现回放控制器组件

**执行**:
- 创建 `frontend/src/components/history/PlaybackControl.vue`
- 播放/暂停按钮
- 进度条（可拖拽）
- 速度选择器
- 当前消息指示

**验证**:
- 控制器 UI 正常渲染
- 控制操作触发正确事件

**输出文件**:
- `frontend/src/components/history/PlaybackControl.vue`

---

### Task 5.6: 实现回放逻辑

**执行**:
- 创建 `frontend/src/composables/usePlayback.ts`
- 实现播放状态管理
- 实现定时器控制（根据速度）
- 实现消息逐条显示

**验证**:
- 回放功能正常工作
- 速度切换正常
- 暂停/继续正常

**输出文件**:
- `frontend/src/composables/usePlayback.ts`

---

### Task 5.7: 实现讨论详情回放页

**执行**:
- 更新 `frontend/src/views/DiscussionView.vue`
- 支持查看模式（历史讨论）
- 集成回放控制器
- 消息逐条显示动画

**验证**:
- 历史讨论可回放
- 动画效果流畅

**输出文件**:
- `frontend/src/views/DiscussionView.vue` (更新)

## 验收标准

- [ ] 可查看历史讨论记录 (Spec AC-12)
- [ ] 历史列表正确显示讨论信息
- [ ] 回放功能流畅
- [ ] 支持播放速度调节
- [ ] 支持进度跳转
