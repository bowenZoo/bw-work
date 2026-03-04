# BW-Work 功能路线图

> 更新时间: 2026-03-04

## 总览

| Phase | 内容 | 状态 | 优先级 |
|-------|------|------|--------|
| 1 | 账号与权限系统 | ✅ 完成 | P0 |
| 2.1 | 讨论分享 | ⏳ 待开发 | P0 |
| 2.2 | 讨论继续（Resume） | ✅ 完成 | P0 |
| 2.3 | 讨论模板 | ⏳ 待开发 | P1 |
| 3.1 | 项目空间 | 📋 规划中 | P1 |
| 3.2 | 文档中心 | 📋 规划中 | P2 |
| 3.3 | 知识库 | 📋 规划中 | P2 |
| 4.1 | 多模型配置 | 📋 规划中 | P2 |
| 4.2 | 讨论干预增强 | 📋 规划中 | P2 |
| 4.3 | 图片生成集成 | 📋 规划中 | P3 |
| 5.1 | 多人实时协作 | 📋 规划中 | P3 |
| 5.2 | 导出功能 | 📋 规划中 | P3 |
| 5.3 | Webhook/API 集成 | 📋 规划中 | P3 |

---

## Phase 1: 账号与权限系统

### 目标
为 BW-Work 添加用户注册/登录、角色权限、讨论归属，管理员在主页侧边栏内管理。

### 角色
- **superadmin**: 管理所有用户和讨论、系统配置、审计日志
- **user**: 创建和管理自己的讨论

### 后端
- `users` 表: id, username, email, password_hash, display_name, role, is_active, created_at, last_login
- `discussions` 表新增 owner_id 字段
- 认证 API: `/api/auth/*` (register/login/refresh/logout/me)
- 用户管理 API: `/api/admin/users/*` (superadmin only)
- 讨论权限: owner 或 superadmin 可删除/中断
- 向后兼容: 未登录用户仍可使用

### 前端
- 可折叠侧边栏（默认收起48px，展开200px）
- Header 用户区域（登录/注册/用户菜单）
- 登录/注册 Modal
- 讨论卡片操作菜单
- 管理面板嵌入主内容区（不跳 /admin）

---

## Phase 2.1: 讨论分享

### 目标
生成分享链接，他人只读浏览。

### 后端
- `discussion_shares` 表
- POST `/api/discussions/:id/share` — 生成链接
- GET `/api/shared/:token` — 公开只读访问

### 前端
- 分享弹窗: 复制链接、过期时间
- `/shared/:token` 只读页面

---

## Phase 2.2: 讨论继续（Resume）

### 目标
中断/失败的讨论从断点恢复。

### 实现
- POST `/api/discussions/:id/resume`
- 恢复上下文 + 可选补充需求

---

## Phase 2.3: 讨论模板

### 目标
预设模板一键开始讨论。

### 实现
- `discussion_templates` 表
- 模板 CRUD（admin 管理，user 使用）

---

## Phase 3+

- **3.1** 项目空间（多项目管理、成员邀请）
- **3.2** 文档中心（GDD 归档、版本历史、Markdown 编辑）
- **3.3** 知识库（参考文档上传、AI 引用）
- **4.1** 多模型配置（Agent 级别模型选择）
- **4.2** 讨论干预增强（暂停修改、投票机制）
- **4.3** 图片生成集成（DALL-E/Midjourney）
- **5.1** 多人实时协作
- **5.2** 导出 PDF/Word/Markdown
- **5.3** Webhook + 公开 API

---

## 变更日志

| 日期 | 变更 |
|------|------|
| 2026-03-04 | 初始版本，Phase 1 子代理开发中 |
