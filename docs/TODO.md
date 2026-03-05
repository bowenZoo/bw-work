# BW-Work 待做工作清单

> 更新时间: 2026-03-05 11:38

## ✅ 已完成

### Phase 1 — 后端架构重构
- [x] 5张新表（project_stages, documents, document_versions, discussion_outputs, project_members）
- [x] stages.py 路由（hall, project detail, stages CRUD, documents CRUD, versions, outputs, archive）
- [x] 9阶段 DAG 依赖模板 + 自动解锁

### Phase 2 — 前端重构
- [x] HallView 大厅首页（讨论+项目卡片混排）
- [x] ProjectDetailView 阶段流水线（9阶段、状态徽章、文档/讨论卡片）
- [x] DocumentView 文档编辑页（编辑/保存/版本历史/回退）
- [x] UserMenu 右上角下拉菜单（替代 SidePanel）
- [x] 路由重写
- [x] 退出登录清屏+弹登录框
- [x] 注册/登录后自动刷新大厅

### Phase 3 — 讨论生态
- [x] 讨论归档 UI（已完成讨论→归档到项目阶段）
- [x] 讨论穿透（项目讨论自动注入所有已有文档为 AI 上下文）
- [x] 讨论产出自动生成（完成时从最终结果创建 output）
- [x] 产出采纳 UI（产出卡片→新建文档/合并已有文档）

---

## 🔜 待做

### P0 — 核心功能完善
- [ ] **Markdown 渲染**：DocumentView 目前纯文本，需 Markdown 渲染
- [ ] **讨论列表管理**：大厅排序/筛选/搜索，区分状态
- [ ] **数据迁移**：已有 lobby 讨论关联到项目 stage

### P1 — 体验优化
- [ ] **新建讨论弹窗美化**：改模态框+可选关联项目/阶段
- [ ] **新建项目弹窗**：加描述字段、选择初始阶段模板
- [ ] **ProjectDetailView 阶段折叠**：locked 默认折叠
- [ ] **讨论卡片状态标识**：显示运行中/已完成/等待中
- [ ] **文档编辑器升级**：textarea→富文本或 Markdown 编辑器

### P2 — 进阶功能
- [ ] **讨论产出预览**：采纳前查看完整内容、对比已有文档
- [ ] **文档导出**：Markdown/PDF
- [ ] **GitHub 同步**：完成阶段时自动 push
- [ ] **项目成员管理**：邀请/移除/权限控制
- [ ] **阶段自定义**：修改/增删阶段，自定义 DAG

### P3 — 远期
- [ ] 多项目仪表盘
- [ ] AI 助手增强（主动引用项目文档）
- [ ] 移动端适配
- [ ] 通知系统

---

## 🐛 已知问题
- [ ] `/api/documents/` 路径冲突（旧document.py vs 新stages.py），用 `/api/docs/` 绕过
- [ ] `admin_users` 和 `users` 两套用户表，长期应合并
- [ ] 文件注册表 `_index.json` vs `projects` DB 表双数据源

---

## 🏗 架构参考

### 数据流
```
大厅讨论 → 📦归档到项目阶段 → 讨论产出 → 📝采纳 → 正式文档（带版本）
```

### 9阶段 DAG
```
概念孵化 ──→ 核心玩法GDD ──→ 系统设计文档 ──→ 关卡/内容规划
         ├─→ 美术风格定义 ──→ 美术资源需求清单
         └─→ 技术选型&原型
核心玩法GDD ──→ 数值框架
            └─→ UI/UX界面设计
```

### 关键文件
| 文件 | 职责 |
|------|------|
| backend/src/api/routes/stages.py | 新架构后端 API |
| backend/src/admin/database.py | 所有 DB CRUD |
| backend/src/crew/discussion_crew.py | 讨论引擎（穿透+自动产出） |
| frontend/src/views/HallView.vue | 大厅首页 |
| frontend/src/views/ProjectDetailView.vue | 项目阶段流水线 |
| frontend/src/views/DocumentView.vue | 文档编辑+版本历史 |
| frontend/src/views/DiscussionView.vue | 讨论页（含归档UI） |
