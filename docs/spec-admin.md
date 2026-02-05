# 管理后台 (Admin System) 规格文档

> **版本**: 1.0
> **创建时间**: 2026-02-05

## 1. 项目概述

### 1.1 背景

当前系统的配置项（LLM API Key、Langfuse 配置、图像服务配置等）依赖环境变量或配置文件管理，存在以下问题：

- 修改配置需要重启服务
- 敏感信息明文存储在 `.env` 文件中
- 缺乏统一的配置管理界面
- 无法追踪配置变更历史

本模块旨在提供一个独立的管理后台，支持：
- 可视化的配置管理
- 敏感信息加密存储
- 配置热更新（无需重启服务）
- 操作日志审计

### 1.2 目标

1. **核心目标**：提供安全、便捷的系统配置管理界面
2. **安全目标**：敏感信息加密存储，访问需要认证
3. **运维目标**：支持配置热更新，减少服务重启
4. **审计目标**：记录配置变更历史和操作日志

### 1.3 非目标

- 不提供多租户管理功能
- 不提供复杂的 RBAC 权限系统（仅支持单一管理员角色）
- 不提供配置的导入/导出功能（可后续迭代）
- 不提供 API 使用量统计分析（可后续迭代）

## 2. 功能规格

### 2.1 认证系统

#### 用户故事

- US-01: 作为管理员，我希望通过用户名密码登录管理后台，以便安全地访问配置
- US-02: 作为管理员，我希望登录后获得 Token，以便后续请求无需重复认证
- US-03: 作为系统部署者，我希望可以通过环境变量设置初始管理员，以便首次部署时快速配置

#### 功能点

| ID | 功能 | 优先级 | 描述 |
|----|------|--------|------|
| F-01 | 登录认证 | P0 | 用户名/密码认证，返回 JWT Token |
| F-02 | Token 验证 | P0 | 验证 JWT Token 有效性，保护管理 API |
| F-03 | Token 刷新 | P1 | 支持 Token 过期前刷新 |
| F-04 | 登出功能 | P1 | 清除 Token，结束会话 |
| F-05 | 初始管理员配置 | P0 | 通过环境变量或首次启动向导设置初始管理员 |

#### 认证流程

```
┌─────────────────────────────────────────────────────────────────┐
│  登录流程                                                        │
│                                                                 │
│  1. 用户访问 /admin                                              │
│     ↓                                                           │
│  2. 前端检查 localStorage 是否有有效 Token                        │
│     ├── 有效 → 进入管理界面                                       │
│     └── 无效 → 跳转登录页                                         │
│                                                                 │
│  3. 用户输入用户名/密码                                           │
│     ↓                                                           │
│  4. POST /api/admin/auth/login                                  │
│     ├── 成功 → 返回 JWT Token，存储到 localStorage               │
│     └── 失败 → 显示错误信息                                       │
│                                                                 │
│  5. 后续请求携带 Authorization: Bearer {token}                   │
└─────────────────────────────────────────────────────────────────┘
```

#### JWT Token 规格

| 字段 | 说明 |
|------|------|
| `sub` | 用户名 |
| `exp` | 过期时间（默认 24 小时） |
| `iat` | 签发时间 |
| `type` | Token 类型（`access` / `refresh`） |

#### 验收标准

- [ ] AC-01: 正确的用户名密码可以成功登录并获取 Token
- [ ] AC-02: 错误的用户名或密码返回 401 错误
- [ ] AC-03: 未携带 Token 的管理 API 请求返回 401 错误
- [ ] AC-04: 过期 Token 的请求返回 401 错误
- [ ] AC-05: 可通过环境变量 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD` 设置初始管理员
- [ ] AC-06: 首次启动时如未设置环境变量，提示用户设置初始管理员

### 2.2 LLM API Key 管理

#### 用户故事

- US-04: 作为管理员，我希望在界面上配置 OpenAI API Key，以便系统可以调用 LLM 服务
- US-05: 作为管理员，我希望 API Key 显示时脱敏，以便防止泄露
- US-06: 作为管理员，我希望支持多个 LLM Provider，以便未来扩展

#### 功能点

| ID | 功能 | 优先级 | 描述 |
|----|------|--------|------|
| F-06 | OpenAI API Key 配置 | P0 | 配置 OpenAI API Key |
| F-07 | API Key 脱敏显示 | P0 | 显示时只展示后 4 位 |
| F-08 | API Key 加密存储 | P0 | 使用 AES-256 加密存储 |
| F-09 | API Key 验证 | P1 | 配置后验证 Key 是否有效 |
| F-10 | 多 Provider 支持 | P2 | 支持 Anthropic、Gemini 等其他 Provider |

#### Provider 配置结构

```yaml
llm_providers:
  openai:
    name: OpenAI
    api_key: "sk-****"  # 加密存储
    api_base: "https://api.openai.com/v1"  # 可选
    default_model: "gpt-4"
    enabled: true

  anthropic:  # 未来扩展
    name: Anthropic
    api_key: "sk-ant-****"
    enabled: false
```

#### 验收标准

- [ ] AC-07: 可在管理界面配置 OpenAI API Key
- [ ] AC-08: API Key 显示为 `sk-****xxxx` 格式（只显示后 4 位）
- [ ] AC-09: API Key 在数据库中加密存储
- [ ] AC-10: 配置保存后立即生效，无需重启服务

### 2.3 Langfuse 监控配置

#### 用户故事

- US-07: 作为管理员，我希望在界面上配置 Langfuse 连接信息，以便启用监控功能
- US-08: 作为管理员，我希望可以测试 Langfuse 连接是否正常

#### 功能点

| ID | 功能 | 优先级 | 描述 |
|----|------|--------|------|
| F-11 | Langfuse 配置管理 | P0 | 配置 Public Key、Secret Key、Host |
| F-12 | 连接测试 | P1 | 测试 Langfuse 连接是否正常 |
| F-13 | 启用/禁用开关 | P0 | 可临时禁用 Langfuse 监控 |

#### 配置项

| 配置项 | 说明 | 是否加密 |
|--------|------|----------|
| `public_key` | Langfuse Public Key | 否 |
| `secret_key` | Langfuse Secret Key | 是 |
| `host` | Langfuse Host 地址 | 否 |
| `enabled` | 是否启用 | 否 |

#### 验收标准

- [ ] AC-11: 可在管理界面配置 Langfuse 连接信息
- [ ] AC-12: Secret Key 加密存储并脱敏显示
- [ ] AC-13: 可测试 Langfuse 连接状态
- [ ] AC-14: 可通过开关启用/禁用 Langfuse 监控

### 2.4 图像服务配置

#### 用户故事

- US-09: 作为管理员，我希望在界面上配置图像生成服务的 API Key
- US-10: 作为管理员，我希望可以选择默认的图像生成 Provider

#### 功能点

| ID | 功能 | 优先级 | 描述 |
|----|------|--------|------|
| F-14 | 图像服务 Key 配置 | P0 | 配置各图像服务商的 API Key |
| F-15 | 默认 Provider 选择 | P0 | 设置默认使用的图像服务 |
| F-16 | Provider 启用/禁用 | P1 | 单独启用或禁用某个 Provider |
| F-17 | 服务可用性测试 | P2 | 测试图像服务是否可用 |

#### 支持的图像服务

| Provider | 配置项 | 说明 |
|----------|--------|------|
| OpenAI DALL-E | `api_key` | 使用 LLM 的 OpenAI Key |
| kie.ai | `api_key`, `base_url` | 通用市场模型 |
| wenwen-ai | `api_key`, `base_url` | Midjourney 集成 |
| nanobanana | `api_key`, `base_url` | 多功能图像服务 |

#### 验收标准

- [ ] AC-15: 可在管理界面配置各图像服务的 API Key
- [ ] AC-16: 可选择默认的图像生成 Provider
- [ ] AC-17: 图像服务 API Key 加密存储并脱敏显示

### 2.5 配置持久化

#### 用户故事

- US-11: 作为管理员，我希望配置持久化存储，以便服务重启后配置不丢失
- US-12: 作为管理员，我希望敏感信息加密存储，以便提高安全性

#### 功能点

| ID | 功能 | 优先级 | 描述 |
|----|------|--------|------|
| F-18 | SQLite 配置存储 | P0 | 使用 SQLite 存储配置 |
| F-19 | AES-256 加密 | P0 | 敏感字段使用 AES-256 加密 |
| F-20 | 配置热更新 | P0 | 修改配置后立即生效 |
| F-21 | 配置版本管理 | P2 | 记录配置变更历史 |

#### 数据库设计

```sql
-- 配置表
CREATE TABLE admin_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,        -- 配置分类：llm, langfuse, image, general
    key TEXT NOT NULL,             -- 配置键
    value TEXT NOT NULL,           -- 配置值（敏感字段加密）
    encrypted INTEGER DEFAULT 0,   -- 是否加密
    updated_at TEXT NOT NULL,
    UNIQUE(category, key)
);

-- 管理员账户表
CREATE TABLE admin_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,   -- bcrypt 哈希
    created_at TEXT NOT NULL,
    last_login TEXT
);

-- 操作日志表
CREATE TABLE admin_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    action TEXT NOT NULL,          -- 操作类型：login, config_update, etc.
    target TEXT,                   -- 操作目标
    details TEXT,                  -- 操作详情（JSON）
    ip_address TEXT,
    created_at TEXT NOT NULL
);
```

#### 加密方案

| 组件 | 说明 |
|------|------|
| 算法 | AES-256-GCM |
| 密钥来源 | 环境变量 `ADMIN_ENCRYPTION_KEY` |
| 密钥派生 | PBKDF2（如使用密码短语） |
| 存储格式 | Base64 编码的密文 |

#### 验收标准

- [ ] AC-18: 配置存储在 SQLite 数据库中
- [ ] AC-19: 敏感字段（API Key、Secret Key）使用 AES-256 加密
- [ ] AC-20: 修改配置后服务自动加载新配置，无需重启
- [ ] AC-21: 加密密钥通过环境变量 `ADMIN_ENCRYPTION_KEY` 配置

### 2.6 操作日志

#### 用户故事

- US-13: 作为管理员，我希望查看配置变更历史，以便追踪问题
- US-14: 作为管理员，我希望查看登录记录，以便发现异常访问

#### 功能点

| ID | 功能 | 优先级 | 描述 |
|----|------|--------|------|
| F-22 | 登录日志 | P1 | 记录登录时间、IP 地址 |
| F-23 | 配置变更日志 | P1 | 记录配置变更内容 |
| F-24 | 日志查询 | P1 | 按时间、类型查询日志 |
| F-25 | 日志清理 | P2 | 自动清理超过 90 天的日志 |

#### 日志类型

| 类型 | 说明 | 记录内容 |
|------|------|----------|
| `login` | 登录 | 用户名、IP、时间 |
| `login_failed` | 登录失败 | 用户名、IP、时间、原因 |
| `logout` | 登出 | 用户名、时间 |
| `config_update` | 配置更新 | 类别、键、旧值（脱敏）、新值（脱敏） |
| `config_delete` | 配置删除 | 类别、键 |

#### 验收标准

- [ ] AC-22: 登录和登录失败都有日志记录
- [ ] AC-23: 配置变更有日志记录（敏感值脱敏）
- [ ] AC-24: 可在管理界面查看操作日志
- [ ] AC-25: 超过 90 天的日志自动清理

### 2.7 前端管理界面

#### 用户故事

- US-15: 作为管理员，我希望有独立的管理入口，以便与主应用分离
- US-16: 作为管理员，我希望界面简洁直观，以便快速完成配置

#### 功能点

| ID | 功能 | 优先级 | 描述 |
|----|------|--------|------|
| F-26 | 管理页面路由 | P0 | `/admin` 路由入口 |
| F-27 | 登录页面 | P0 | 用户名/密码登录界面 |
| F-28 | 配置仪表盘 | P0 | 配置状态概览 |
| F-29 | LLM 配置页 | P0 | LLM API Key 配置界面 |
| F-30 | 监控配置页 | P0 | Langfuse 配置界面 |
| F-31 | 图像服务配置页 | P0 | 图像服务配置界面 |
| F-32 | 操作日志页 | P1 | 操作日志查看界面 |
| F-33 | 路由守卫 | P0 | 未登录时跳转登录页 |

#### 页面结构

```
/admin
├── /login              # 登录页
├── /dashboard          # 仪表盘（默认页）
├── /config
│   ├── /llm            # LLM 配置
│   ├── /langfuse       # Langfuse 配置
│   └── /image          # 图像服务配置
└── /logs               # 操作日志
```

#### 界面布局

```
┌─────────────────────────────────────────────────────────────────┐
│  Logo        管理后台                           [管理员] [登出]  │
├─────────┬───────────────────────────────────────────────────────┤
│         │                                                       │
│  仪表盘  │   ┌─────────────────────────────────────────────────┐ │
│         │   │  LLM 配置                                        │ │
│  配置    │   │                                                 │ │
│  ├ LLM   │   │  OpenAI API Key: sk-****1234  [编辑] [测试]    │ │
│  ├ 监控  │   │  状态: 已配置                                   │ │
│  └ 图像  │   │                                                 │ │
│         │   └─────────────────────────────────────────────────┘ │
│  日志    │                                                       │
│         │                                                       │
└─────────┴───────────────────────────────────────────────────────┘
```

#### 验收标准

- [ ] AC-26: `/admin` 路由可正常访问
- [ ] AC-27: 未登录时自动跳转到 `/admin/login`
- [ ] AC-28: 登录后可访问配置页面
- [ ] AC-29: 各配置页面可正常显示和编辑配置
- [ ] AC-30: 界面与主应用风格一致（使用相同的 TailwindCSS 主题）

## 3. 技术约束

### 3.1 技术栈

**后端:**
| 技术 | 用途 |
|------|------|
| FastAPI | API 路由 |
| SQLite | 配置存储 |
| python-jose | JWT Token 处理 |
| bcrypt / passlib | 密码哈希 |
| cryptography | AES-256 加密 |

**前端:**
| 技术 | 用途 |
|------|------|
| Vue 3 | UI 框架 |
| Vue Router | 路由管理 |
| Pinia | 状态管理 |
| TailwindCSS | 样式 |

### 3.2 API 设计

#### 认证 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/admin/auth/login` | 登录 |
| POST | `/api/admin/auth/logout` | 登出 |
| POST | `/api/admin/auth/refresh` | 刷新 Token |
| GET | `/api/admin/auth/me` | 获取当前用户信息 |

#### 配置 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/config` | 获取所有配置（脱敏） |
| GET | `/api/admin/config/{category}` | 获取某类配置 |
| PUT | `/api/admin/config/{category}/{key}` | 更新配置 |
| DELETE | `/api/admin/config/{category}/{key}` | 删除配置 |
| POST | `/api/admin/config/test/{category}` | 测试配置连接 |

#### 日志 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/logs` | 查询操作日志 |

### 3.3 安全要求

| 要求 | 说明 |
|------|------|
| 密码存储 | bcrypt 哈希，cost factor >= 12 |
| API Key 存储 | AES-256-GCM 加密 |
| Token 有效期 | Access Token 24h，Refresh Token 7d |
| 登录限制 | 连续 5 次失败锁定 15 分钟 |
| HTTPS | 生产环境强制 HTTPS |

### 3.4 性能要求

| 指标 | 要求 |
|------|------|
| 配置加载时间 | < 100ms |
| 配置更新生效时间 | < 1s |
| 登录响应时间 | < 500ms |

### 3.5 兼容性

- 与现有 `settings.py` 配置兼容
- 环境变量优先级高于数据库配置
- 数据库配置未设置时回退到环境变量

### 3.6 配置优先级

```
环境变量 > 数据库配置 > 默认值
```

**说明**：
- 环境变量始终具有最高优先级，便于 CI/CD 和容器化部署
- 数据库配置通过管理界面设置，支持热更新
- 默认值在代码中定义，作为兜底

## 4. 参考

### 4.1 项目内参考

| 模块 | 参考点 |
|------|--------|
| `backend/src/config/settings.py` | 现有配置结构 |
| `backend/src/memory/discussion_memory.py` | SQLite 使用模式 |
| `frontend/src/router.ts` | 路由结构 |

### 4.2 技术参考

| 技术 | 文档 |
|------|------|
| FastAPI Security | fastapi.tiangolo.com/tutorial/security |
| python-jose | github.com/mpdavis/python-jose |
| Vue Router Navigation Guards | router.vuejs.org/guide/advanced/navigation-guards |

## 5. 里程碑规划

### Phase 1: 核心认证 (P0)

- 管理员账户表创建 (F-18)
- 登录认证 API (F-01, F-02)
- 初始管理员配置 (F-05)
- 前端登录页面 (F-27)
- 路由守卫 (F-33)

### Phase 2: 配置管理 (P0)

- 配置存储表创建 (F-18)
- 配置加密存储 (F-19)
- LLM 配置管理 (F-06, F-07, F-08)
- Langfuse 配置管理 (F-11, F-13)
- 图像服务配置 (F-14, F-15)
- 配置热更新 (F-20)
- 前端配置页面 (F-29, F-30, F-31)

### Phase 3: 增强功能 (P1)

- Token 刷新 (F-03)
- 登出功能 (F-04)
- 连接测试 (F-09, F-12)
- 操作日志 (F-22, F-23, F-24)
- 前端日志页面 (F-32)
- 配置仪表盘 (F-28)

### Phase 4: 扩展功能 (P2)

- 多 LLM Provider 支持 (F-10)
- Provider 启用/禁用 (F-16)
- 服务可用性测试 (F-17)
- 配置版本管理 (F-21)
- 日志自动清理 (F-25)

---

## 附录

### A. 环境变量列表

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `ADMIN_USERNAME` | 初始管理员用户名 | - |
| `ADMIN_PASSWORD` | 初始管理员密码 | - |
| `ADMIN_ENCRYPTION_KEY` | 配置加密密钥（32 字节 Base64） | 随机生成 |
| `ADMIN_JWT_SECRET` | JWT 签名密钥 | 随机生成 |
| `ADMIN_JWT_EXPIRE_HOURS` | JWT 过期时间（小时） | 24 |

### B. 数据库文件位置

```
data/
└── admin/
    └── admin.db          # 管理后台数据库
```

### C. 文档版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0 | 2026-02-05 | 初始版本 |
