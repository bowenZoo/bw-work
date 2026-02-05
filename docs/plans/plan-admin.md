# Plan: 管理后台系统 (Admin System)

> **模块**: admin
> **优先级**: P0
> **对应 Spec**: docs/spec-admin.md

## 目标

实现独立的管理后台系统，支持：
1. 管理员认证（JWT Token）
2. LLM API Key 加密管理（可热更新）
3. Langfuse 监控配置
4. 图像服务配置
5. 配置热更新
6. 操作日志审计
7. 管理端安全策略（CSP、会话撤销、登录锁定）

## 前置依赖

- plan-backend-core (基础 FastAPI 框架)
- plan-frontend (Vue 3 基础框架)

## 技术方案

### 架构设计

```
backend/
├── src/
│   ├── admin/                  # 管理后台模块
│   │   ├── __init__.py
│   │   ├── models.py           # Pydantic 模型
│   │   ├── database.py         # SQLite 数据库管理
│   │   ├── crypto.py           # AES-256 加密工具
│   │   ├── auth.py             # JWT 认证
│   │   ├── config_store.py     # 配置存储（热更新支持）
│   │   ├── audit_log.py        # 操作日志
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── auth.py         # 认证 API
│   │       ├── config.py       # 配置 API
│   │       └── logs.py         # 日志 API
│   └── api/
│       └── main.py             # 挂载 admin 路由

frontend/
└── src/
    ├── views/
    │   └── admin/              # 管理后台页面
    │       ├── AdminLayout.vue
    │       ├── LoginView.vue
    │       ├── DashboardView.vue
    │       ├── LlmConfigView.vue
    │       ├── LangfuseConfigView.vue
    │       ├── ImageConfigView.vue
    │       └── AuditLogView.vue
    ├── stores/
    │   └── admin.ts            # Admin 状态管理
    ├── composables/
    │   └── useAdminAuth.ts     # 认证 composable
    └── router.ts               # 添加 /admin 路由

data/
└── admin/
    └── admin.db                # 管理后台数据库
```

### 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| 数据库 | SQLite | 与现有项目一致，轻量级 |
| JWT | python-jose | FastAPI 官方推荐 |
| 密码哈希 | passlib[bcrypt] | 安全性高，业界标准 |
| 加密 | cryptography (AES-256-GCM) | Python 标准加密库 |
| 状态管理 | Pinia | 与现有前端一致 |

---

## 任务清单

### Phase 1: 核心认证

#### Task 1.1: 创建 Admin 模块目录结构

**执行**:
- 创建 `backend/src/admin/` 目录
- 创建 `backend/src/admin/__init__.py`
- 创建 `backend/src/admin/models.py` - Pydantic 模型定义
- 创建 `data/admin/` 目录

**验证**:
- `ls backend/src/admin` → 目录存在
- `ls data/admin` → 目录存在

**输出文件**:
- `backend/src/admin/__init__.py`
- `backend/src/admin/models.py`

---

#### Task 1.2: 实现数据库初始化

**执行**:
- 创建 `backend/src/admin/database.py`
- 实现 SQLite 数据库连接管理
- 创建 `admin_users` 表
- 创建 `admin_refresh_tokens` 表（refresh token 轮换/撤销）
- 创建 `admin_login_attempts` 表（登录失败锁定）
- 创建 `admin_config` 表
- 创建 `admin_audit_log` 表
- 支持通过环境变量 `ADMIN_DB_PATH` 自定义数据库路径

**验证**:
- `cd backend && python -c "from src.admin.database import AdminDatabase; db = AdminDatabase(); db.init_db()"` → exit_code == 0
- `ls data/admin/admin.db` → 文件存在

**输出文件**:
- `backend/src/admin/database.py`

---

#### Task 1.3: 实现 AES-256 加密工具

**执行**:
- 创建 `backend/src/admin/crypto.py`
- 实现 AES-256-GCM 加密/解密函数（随机 nonce）
- 仅支持 **32 字节 Base64** 密钥（严验长度）
- 支持从环境变量 `ADMIN_ENCRYPTION_KEY` 读取密钥
- 开发态允许自动生成并落盘 `data/admin/.keys/admin_encryption.key`（权限 600）
- 生产态强制要求环境变量，不允许自动生成
- 实现 `encrypt_value()` 和 `decrypt_value()` 函数

**验证**:
- `cd backend && python -c "from src.admin.crypto import encrypt_value, decrypt_value; assert decrypt_value(encrypt_value('test')) == 'test'"` → exit_code == 0

**输出文件**:
- `backend/src/admin/crypto.py`

---

#### Task 1.4: 实现密码哈希和 JWT 认证

**执行**:
- 创建 `backend/src/admin/auth.py`
- 实现 bcrypt 密码哈希（cost factor >= 12）
- 实现 JWT Token 生成（access token 24h，refresh token 7d）
- 实现 refresh token **轮换** 与 **撤销**（数据库表存储）
- 实现 Token 验证中间件（access token）
- 支持 refresh token 失效（logout 即撤销）
- 支持环境变量 `ADMIN_JWT_SECRET` 和 `ADMIN_JWT_EXPIRE_HOURS`

**验证**:
- `cd backend && python -c "from src.admin.auth import hash_password, verify_password; assert verify_password('test', hash_password('test'))"` → exit_code == 0
- `cd backend && python -c "from src.admin.auth import create_access_token, verify_token; token = create_access_token('admin'); assert verify_token(token) is not None"` → exit_code == 0

**输出文件**:
- `backend/src/admin/auth.py`

---

#### Task 1.5: 实现初始管理员配置

**执行**:
- 在 `backend/src/admin/database.py` 添加初始管理员创建逻辑
- 支持环境变量 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD`
- 首次启动时自动创建初始管理员
- 如果未设置环境变量：
  - 生成一次性 bootstrap token，写入 `data/admin/.bootstrap_token`（权限 600）
  - 需要通过该 token 完成首次密码设置
- 禁止在日志打印明文密码

**验证**:
- `ADMIN_USERNAME=test ADMIN_PASSWORD=test123 cd backend && python -c "from src.admin.database import AdminDatabase; db = AdminDatabase(); db.init_db(); assert db.get_admin_user('test') is not None"` → exit_code == 0

**输出文件**:
- `backend/src/admin/database.py` (更新)

---

#### Task 1.6: 实现认证 API 路由

**执行**:
- 创建 `backend/src/admin/routes/__init__.py`
- 创建 `backend/src/admin/routes/auth.py`
- 实现 `POST /api/admin/auth/login` - 登录
- 实现 `POST /api/admin/auth/logout` - 登出
- 实现 `POST /api/admin/auth/refresh` - 刷新 Token
- 实现 `GET /api/admin/auth/me` - 获取当前用户信息
- 实现登录失败锁定（5 次失败锁定 15 分钟，DB 持久化）

**验证**:
- `cd backend && python -c "from src.admin.routes.auth import router"` → exit_code == 0

**输出文件**:
- `backend/src/admin/routes/__init__.py`
- `backend/src/admin/routes/auth.py`

---

#### Task 1.7: 挂载 Admin 路由到 FastAPI

**执行**:
- 更新 `backend/src/api/main.py`，挂载 `/api/admin` 路由前缀
- 添加 Admin 相关 CORS 配置
- 确保 Admin API 需要认证（除登录接口外）
- 管理端 API 增加基础安全响应头（建议：CSP、X-Frame-Options）

**验证**:
- `cd backend && python -c "from src.api.main import app; routes = [r.path for r in app.routes]; assert '/api/admin/auth/login' in str(routes) or any('admin' in str(r.path) for r in app.routes)"` → exit_code == 0

**输出文件**:
- `backend/src/api/main.py` (更新)

---

#### Task 1.8: 实现前端登录页面

**执行**:
- 创建 `frontend/src/views/admin/` 目录
- 创建 `frontend/src/views/admin/LoginView.vue` - 登录页面
- 创建 `frontend/src/stores/admin.ts` - Admin 状态管理
- 创建 `frontend/src/composables/useAdminAuth.ts` - 认证逻辑
- 实现用户名/密码表单
- 默认 Token 存储到 localStorage（可配置为 sessionStorage）
- 添加基础 XSS 保护提示（CSP 配合）

**验证**:
- `ls frontend/src/views/admin/LoginView.vue` → 文件存在
- `cd frontend && npx tsc --noEmit` → exit_code == 0

**输出文件**:
- `frontend/src/views/admin/LoginView.vue`
- `frontend/src/stores/admin.ts`
- `frontend/src/composables/useAdminAuth.ts`

---

#### Task 1.9: 实现前端路由守卫

**执行**:
- 更新 `frontend/src/router.ts`，添加 `/admin` 路由
- 创建 `frontend/src/views/admin/AdminLayout.vue` - 管理后台布局
- 实现路由守卫：未登录时跳转到 `/admin/login`
- Token 过期时自动跳转登录页

**验证**:
- `cd frontend && npx tsc --noEmit` → exit_code == 0

**输出文件**:
- `frontend/src/router.ts` (更新)
- `frontend/src/views/admin/AdminLayout.vue`

---

### Phase 2: 配置管理

#### Task 2.1: 实现配置存储服务

**执行**:
- 创建 `backend/src/admin/config_store.py`
- 实现配置 CRUD 操作
- 实现敏感字段自动加密/解密
- 实现配置脱敏显示（只显示后 4 位）
- 支持配置分类（llm, langfuse, image, general）

**验证**:
- `cd backend && python -c "from src.admin.config_store import ConfigStore; store = ConfigStore(); store.set('llm', 'openai_api_key', 'sk-test1234', encrypted=True); assert store.get('llm', 'openai_api_key') == 'sk-test1234'"` → exit_code == 0

**输出文件**:
- `backend/src/admin/config_store.py`

---

#### Task 2.2: 实现配置热更新机制

**执行**:
- 更新 `backend/src/config/settings.py`，支持从 ConfigStore 读取配置
- 实现配置优先级：环境变量 > 数据库配置 > 默认值
- 添加 `reload_config()` 函数支持热更新
- 配置变更时自动通知相关模块：
  - Langfuse：调用 `shutdown` + `init` 重新创建 client
  - LLM：刷新 provider 配置，重建 client（惰性初始化）
  - 图像服务：重读配置文件或 DB 配置

**验证**:
- `cd backend && python -c "from src.config.settings import settings, reload_config; reload_config()"` → exit_code == 0

**输出文件**:
- `backend/src/config/settings.py` (更新)

---

#### Task 2.3: 实现配置 API 路由

**执行**:
- 创建 `backend/src/admin/routes/config.py`
- 实现 `GET /api/admin/config` - 获取所有配置（脱敏）
- 实现 `GET /api/admin/config/{category}` - 获取某类配置
- 实现 `PUT /api/admin/config/{category}/{key}` - 更新配置
- 实现 `DELETE /api/admin/config/{category}/{key}` - 删除配置
- 实现 `POST /api/admin/config/test/{category}` - 测试配置连接
- 配置测试接口必须限制目标域名或使用固定配置（防 SSRF）

**验证**:
- `cd backend && python -c "from src.admin.routes.config import router"` → exit_code == 0

**输出文件**:
- `backend/src/admin/routes/config.py`

---

#### Task 2.4: 实现 LLM 配置前端页面

**执行**:
- 创建 `frontend/src/views/admin/LlmConfigView.vue`
- 实现 OpenAI API Key 配置表单
- 实现 API Key 脱敏显示
- 实现配置保存和测试功能
- 支持多 Provider 预留结构

**验证**:
- `ls frontend/src/views/admin/LlmConfigView.vue` → 文件存在
- `cd frontend && npx tsc --noEmit` → exit_code == 0

**输出文件**:
- `frontend/src/views/admin/LlmConfigView.vue`

---

#### Task 2.5: 实现 Langfuse 配置前端页面

**执行**:
- 创建 `frontend/src/views/admin/LangfuseConfigView.vue`
- 实现 Public Key、Secret Key、Host 配置表单
- 实现启用/禁用开关
- 实现连接测试功能

**验证**:
- `ls frontend/src/views/admin/LangfuseConfigView.vue` → 文件存在
- `cd frontend && npx tsc --noEmit` → exit_code == 0

**输出文件**:
- `frontend/src/views/admin/LangfuseConfigView.vue`

---

#### Task 2.6: 实现图像服务配置前端页面

**执行**:
- 创建 `frontend/src/views/admin/ImageConfigView.vue`
- 实现各图像服务 API Key 配置（kie.ai, wenwen-ai, nanobanana, DALL-E）
- 实现默认 Provider 选择
- 实现 Provider 启用/禁用开关

**验证**:
- `ls frontend/src/views/admin/ImageConfigView.vue` → 文件存在
- `cd frontend && npx tsc --noEmit` → exit_code == 0

**输出文件**:
- `frontend/src/views/admin/ImageConfigView.vue`

---

#### Task 2.7: 实现仪表盘页面

**执行**:
- 创建 `frontend/src/views/admin/DashboardView.vue`
- 显示配置状态概览（LLM、Langfuse、图像服务配置状态）
- 显示最近操作日志（5 条）
- 显示系统信息

**验证**:
- `ls frontend/src/views/admin/DashboardView.vue` → 文件存在
- `cd frontend && npx tsc --noEmit` → exit_code == 0

**输出文件**:
- `frontend/src/views/admin/DashboardView.vue`

---

### Phase 3: 操作日志

#### Task 3.1: 实现审计日志服务

**执行**:
- 创建 `backend/src/admin/audit_log.py`
- 实现日志记录函数
- 支持日志类型：login, login_failed, logout, config_update, config_delete
- 实现敏感值脱敏
- 实现日志查询（按时间、类型过滤）
- 记录审计字段：ip、user_agent、action、target、before/after(masked)

**验证**:
- `cd backend && python -c "from src.admin.audit_log import AuditLogger; logger = AuditLogger(); logger.log('login', 'admin', target='admin')"` → exit_code == 0

**输出文件**:
- `backend/src/admin/audit_log.py`

---

#### Task 3.2: 实现日志 API 路由

**执行**:
- 创建 `backend/src/admin/routes/logs.py`
- 实现 `GET /api/admin/logs` - 查询操作日志
- 支持分页、时间范围过滤、类型过滤

**验证**:
- `cd backend && python -c "from src.admin.routes.logs import router"` → exit_code == 0

**输出文件**:
- `backend/src/admin/routes/logs.py`

---

#### Task 3.3: 实现日志查看前端页面

**执行**:
- 创建 `frontend/src/views/admin/AuditLogView.vue`
- 实现日志列表展示
- 实现时间范围和类型过滤
- 实现分页功能

**验证**:
- `ls frontend/src/views/admin/AuditLogView.vue` → 文件存在
- `cd frontend && npx tsc --noEmit` → exit_code == 0

**输出文件**:
- `frontend/src/views/admin/AuditLogView.vue`

---

#### Task 3.4: 实现日志自动清理

**执行**:
- 更新 `backend/src/admin/audit_log.py`
- 实现超过 90 天的日志自动清理
- 可通过配置调整清理周期
- 服务启动时执行清理

**验证**:
- `cd backend && python -c "from src.admin.audit_log import AuditLogger; logger = AuditLogger(); logger.cleanup_old_logs()"` → exit_code == 0

**输出文件**:
- `backend/src/admin/audit_log.py` (更新)

---

### Phase 4: 测试与完善

#### Task 4.1: 编写后端单元测试

**执行**:
- 创建 `backend/tests/admin/` 目录
- 创建 `backend/tests/admin/test_crypto.py` - 加密测试
- 创建 `backend/tests/admin/test_auth.py` - 认证测试
- 创建 `backend/tests/admin/test_config_store.py` - 配置存储测试
- 创建 `backend/tests/admin/test_lockout.py` - 登录锁定测试
- 创建 `backend/tests/admin/test_refresh_tokens.py` - refresh token 轮换/撤销测试

**验证**:
- `cd backend && python -m pytest tests/admin/ -v` → exit_code == 0

**输出文件**:
- `backend/tests/admin/__init__.py`
- `backend/tests/admin/test_crypto.py`
- `backend/tests/admin/test_auth.py`
- `backend/tests/admin/test_config_store.py`

---

#### Task 4.2: 编写 API 集成测试

**执行**:
- 创建 `backend/tests/admin/test_api_auth.py` - 认证 API 测试
- 创建 `backend/tests/admin/test_api_config.py` - 配置 API 测试
- 创建 `backend/tests/admin/test_api_logs.py` - 日志 API 测试
- 创建 `backend/tests/admin/test_api_security.py` - SSRF 防护与认证保护测试

**验证**:
- `cd backend && python -m pytest tests/admin/test_api_*.py -v` → exit_code == 0

**输出文件**:
- `backend/tests/admin/test_api_auth.py`
- `backend/tests/admin/test_api_config.py`
- `backend/tests/admin/test_api_logs.py`

---

#### Task 4.3: 更新依赖文件

**执行**:
- 更新 `backend/requirements.txt`，添加新依赖：
  - `python-jose[cryptography]`
  - `passlib[bcrypt]`
  - `cryptography`
- 更新 `backend/pyproject.toml`，添加依赖声明

**验证**:
- `cd backend && pip install -r requirements.txt` → exit_code == 0
- `cd backend && python -c "import jose; import passlib; import cryptography"` → exit_code == 0

**输出文件**:
- `backend/requirements.txt` (更新)
- `backend/pyproject.toml` (更新)

---

## 验收标准

### 认证系统
- [ ] AC-01: 正确的用户名密码可以成功登录并获取 Token
- [ ] AC-02: 错误的用户名或密码返回 401 错误
- [ ] AC-03: 未携带 Token 的管理 API 请求返回 401 错误
- [ ] AC-04: 过期 Token 的请求返回 401 错误
- [ ] AC-05: 可通过环境变量 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD` 设置初始管理员
- [ ] AC-06: 首次启动时如未设置环境变量，生成 bootstrap token 并强制完成初始化
- [ ] AC-07: logout 能使 refresh token 失效
- [ ] AC-08: 5 次失败锁定 15 分钟（跨进程有效）

### LLM 配置
- [ ] AC-07: 可在管理界面配置 OpenAI API Key
- [ ] AC-08: API Key 显示为 `sk-****xxxx` 格式（只显示后 4 位）
- [ ] AC-09: API Key 在数据库中加密存储
- [ ] AC-10: 配置保存后立即生效，无需重启服务

### Langfuse 配置
- [ ] AC-11: 可在管理界面配置 Langfuse 连接信息
- [ ] AC-12: Secret Key 加密存储并脱敏显示
- [ ] AC-13: 可测试 Langfuse 连接状态
- [ ] AC-14: 可通过开关启用/禁用 Langfuse 监控

### 图像服务配置
- [ ] AC-15: 可在管理界面配置各图像服务的 API Key
- [ ] AC-16: 可选择默认的图像生成 Provider
- [ ] AC-17: 图像服务 API Key 加密存储并脱敏显示

### 配置持久化
- [ ] AC-18: 配置存储在 SQLite 数据库中
- [ ] AC-19: 敏感字段（API Key、Secret Key）使用 AES-256 加密
- [ ] AC-20: 修改配置后服务自动加载新配置，无需重启
- [ ] AC-21: 加密密钥通过环境变量 `ADMIN_ENCRYPTION_KEY` 配置
- [ ] AC-22: 配置测试接口不允许访问非白名单域名

### 操作日志
- [ ] AC-23: 登录和登录失败都有日志记录
- [ ] AC-24: 配置变更有日志记录（敏感值脱敏）
- [ ] AC-25: 日志包含 ip/user_agent/action/target/before/after
- [ ] AC-26: 可在管理界面查看操作日志
- [ ] AC-27: 超过 90 天的日志自动清理

### 前端管理界面
- [ ] AC-28: `/admin` 路由可正常访问
- [ ] AC-29: 未登录时自动跳转到 `/admin/login`
- [ ] AC-30: 登录后可访问配置页面
- [ ] AC-31: 各配置页面可正常显示和编辑配置
- [ ] AC-32: 界面与主应用风格一致（使用相同的 TailwindCSS 主题）

---

## 环境变量汇总

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `ADMIN_USERNAME` | 初始管理员用户名 | `admin` |
| `ADMIN_PASSWORD` | 初始管理员密码 | 随机生成 |
| `ADMIN_ENCRYPTION_KEY` | 配置加密密钥（32 字节 Base64） | **必须设置（生产）** |
| `ADMIN_JWT_SECRET` | JWT 签名密钥 | **必须设置（生产）** |
| `ADMIN_JWT_EXPIRE_HOURS` | JWT 过期时间（小时） | `24` |
| `ADMIN_DB_PATH` | 数据库文件路径 | `data/admin/admin.db` |

---

## 执行建议

1. **Phase 1** 优先完成，确保认证流程可用
2. **Phase 2** 按 LLM → Langfuse → 图像服务顺序实现
3. **Phase 3** 可与 Phase 2 并行开发
4. **Phase 4** 在所有功能完成后执行

**预计工期**: 4-5 天
