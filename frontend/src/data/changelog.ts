// 此文件由 scripts/gen-changelog.mjs 自动生成，请勿手动编辑
// 更新方式：git commit 后自动触发，或手动运行 pnpm gen:changelog
export interface ChangelogEntry {
  version: string
  date: string
  items: { type: 'new' | 'fix' | 'improve' | 'break'; text: string }[]
}

export const CHANGELOG: ChangelogEntry[] = [
  {
    "version": "v1.11.0",
    "date": "2026-03-08",
    "items": [
      {
        "type": "new",
        "text": "大厅公告自动从 git log 生成，无需手动维护"
      },
      {
        "type": "new",
        "text": "决策卡移至右下方 + WebMCP bridge 讨论页工具 + 自动重试机制"
      },
      {
        "type": "fix",
        "text": "producer-assist 决策卡始终返回答案选项"
      },
      {
        "type": "fix",
        "text": "修复项目讨论排队问题及 E2E 测试选择器"
      }
    ]
  },
  {
    "version": "v1.10.0",
    "date": "2026-03-07",
    "items": [
      {
        "type": "new",
        "text": "决策卡架构重设计 — 超级制作人右侧叠卡模式"
      },
      {
        "type": "new",
        "text": "数据管理优化 + 超级制作人按问题建议 + 交互体验修复"
      },
      {
        "type": "new",
        "text": "超级制作人 AI 辅助发言 — 三方向建议面板"
      },
      {
        "type": "fix",
        "text": "补上缺失的 </style> 闭合标签，修复 Vite 模板编译报错"
      },
      {
        "type": "fix",
        "text": "删除 SVG 中多余的 </polyline> 闭合标签导致的 Vue 编译报错"
      },
      {
        "type": "new",
        "text": "10 项优化功能 — 统计/搜索/标签/决策/对比/回放/进度/批量/通知"
      },
      {
        "type": "new",
        "text": "前端讨论视图新功能 UI"
      },
      {
        "type": "new",
        "text": "讨论新功能 — 预设议程/投票量化/数值校验/跨项目记忆/摘要同步/分支探索/AI助理"
      }
    ]
  },
  {
    "version": "v1.9.0",
    "date": "2026-03-06",
    "items": [
      {
        "type": "fix",
        "text": "折叠流式消息未触发 + 角色过滤 fallback 路径缺失"
      },
      {
        "type": "fix",
        "text": "发言人过滤/角色颜色/制作人提示/折叠功能"
      },
      {
        "type": "new",
        "text": "模型快速切换 + 制作人暂停轮次"
      },
      {
        "type": "new",
        "text": "制作人轮次暂停等待——speakers块中含制作人时暂停并等待输入"
      },
      {
        "type": "new",
        "text": "大厅项目/讨论状态显示、阶段关键文档提示、后端重启生效模型端点"
      },
      {
        "type": "fix",
        "text": "修复 DiscussionView defineProps 语法错误"
      },
      {
        "type": "fix",
        "text": "概念孵化阶段agent显示、文档范围、顶端模型展示"
      },
      {
        "type": "fix",
        "text": "概念孵化讨论自动启动、User-Agent代理兼容、讨论阶段路由与UI"
      },
      {
        "type": "new",
        "text": "概念孵化流程——创建项目自动创建孵化讨论并跳转"
      }
    ]
  },
  {
    "version": "v1.8.0",
    "date": "2026-03-05",
    "items": [
      {
        "type": "new",
        "text": "通知铃铛+红点系统 & 私密项目权限弹框改为当前页弹出"
      },
      {
        "type": "new",
        "text": "管理员项目删除功能(API+UI+WebMCP工具)"
      },
      {
        "type": "new",
        "text": "新增8个WebMCP验收工具(crew/access/pending/approve)"
      },
      {
        "type": "fix",
        "text": "pending角色不算有权限+3bug全部修复验证通过"
      },
      {
        "type": "fix",
        "text": "人员Tab选择保持+私密项目弹窗+管理员审批权限申请"
      },
      {
        "type": "fix",
        "text": "3个bug修复 - 权限申请改弹窗+防undefined+人员Tab默认选中主策划"
      },
      {
        "type": "fix",
        "text": "修复模板字符串转义+白屏问题"
      },
      {
        "type": "new",
        "text": "私密项目大厅可见+申请权限页面+access-request API"
      },
      {
        "type": "fix",
        "text": "hall项目权限字段+webmcp返回is_public/user_role"
      },
      {
        "type": "new",
        "text": "项目权限控制系统 - 公开/私密可见性 + 角色拦截 + 前端canEdit"
      },
      {
        "type": "fix",
        "text": "项目创建FK修复+slug→integer自动转换+数据迁移+成员中文+公开私密选项"
      },
      {
        "type": "new",
        "text": "运营策划→市场运营 重写提示词+加入API列表"
      },
      {
        "type": "fix",
        "text": "人员Tab加载API默认提示词"
      },
      {
        "type": "fix",
        "text": "removeAgent空数组时先物化再移除"
      },
      {
        "type": "fix",
        "text": "移除重复watch导入"
      },
      {
        "type": "new",
        "text": "人员Tab重写-参与列表+提示词详情+增删按钮"
      },
      {
        "type": "new",
        "text": "高级选项弹窗分Tab-基础+人员"
      },
      {
        "type": "fix",
        "text": "高级选项弹窗移到Transition外避免编译错误"
      },
      {
        "type": "new",
        "text": "讨论弹窗-密码附件提到主界面+高级选项独立弹窗"
      },
      {
        "type": "new",
        "text": "讨论弹窗精简-目标字段+折叠高级选项+无滚动"
      },
      {
        "type": "new",
        "text": "新建讨论弹窗恢复完整功能-密码/人员/风格/Prompt编辑/附件"
      },
      {
        "type": "new",
        "text": "useHall增加createDiscussion完整参数+风格加载"
      },
      {
        "type": "new",
        "text": "全站移动端响应式适配"
      },
      {
        "type": "new",
        "text": "项目成员管理+阶段自定义+讨论模板"
      },
      {
        "type": "new",
        "text": "产出预览弹窗+文档导出Markdown+阶段内新建讨论弹窗"
      },
      {
        "type": "fix",
        "text": "去重bw_create_project工具+讨论排序+返回按钮优化"
      },
      {
        "type": "new",
        "text": "卡片hover效果+进度条+空状态+讨论参与人数"
      },
      {
        "type": "fix",
        "text": "修复模板字符串转义问题"
      },
      {
        "type": "new",
        "text": "弹窗美化+项目描述+阶段折叠动画"
      },
      {
        "type": "new",
        "text": "大厅搜索+状态筛选tabs+讨论状态徽章"
      },
      {
        "type": "new",
        "text": "讨论产出采纳系统"
      },
      {
        "type": "new",
        "text": "讨论穿透 - AI自动注入项目文档上下文"
      },
      {
        "type": "new",
        "text": "讨论归档到项目阶段 UI"
      },
      {
        "type": "fix",
        "text": "注册/登录后自动刷新大厅数据"
      },
      {
        "type": "new",
        "text": "文档编辑页 + 版本历史"
      },
      {
        "type": "fix",
        "text": "退出登录后清空页面并弹出登录框"
      },
      {
        "type": "new",
        "text": "Phase2 前端 - 大厅+项目详情+阶段流水线+UserMenu"
      },
      {
        "type": "new",
        "text": "后端Phase1 - 阶段流水线+文档版本管理+大厅API"
      },
      {
        "type": "improve",
        "text": "SidePanel提升到App.vue全局, 设置面板用drawer覆盖"
      },
      {
        "type": "new",
        "text": "项目列表页添加全局侧栏SidePanel"
      },
      {
        "type": "new",
        "text": "superadmin用户token直接访问admin API, 无需二次登录"
      },
      {
        "type": "fix",
        "text": "管理员登录即拥有admin API权限, 去掉二次登录"
      },
      {
        "type": "new",
        "text": "管理后台功能迁移到主界面"
      },
      {
        "type": "fix",
        "text": "HomeView正确引用三大设置组件(替换placeholder)"
      },
      {
        "type": "new",
        "text": "个人中心/系统设置/审计日志三大功能页"
      },
      {
        "type": "fix",
        "text": "讨论卡片传递owner_name/owner_avatar到allCards"
      },
      {
        "type": "fix",
        "text": "sqlite3.Row不支持.get()"
      },
      {
        "type": "fix",
        "text": "owner_avatar UnboundLocalError"
      },
      {
        "type": "fix",
        "text": "修复讨论列表owner_name为null"
      }
    ]
  },
  {
    "version": "v1.7.0",
    "date": "2026-03-04",
    "items": [
      {
        "type": "fix",
        "text": "所有显示名字处都显示首字母头像"
      },
      {
        "type": "new",
        "text": "纯色首字母头像 — 替代卡通动物头像"
      },
      {
        "type": "new",
        "text": "用户系统+头像+讨论优化"
      }
    ]
  },
  {
    "version": "v1.6.0",
    "date": "2026-02-18",
    "items": [
      {
        "type": "new",
        "text": "Checkpoint 驱动交互 v2.0 + 游戏知识库 + CLAUDE.md 更新"
      }
    ]
  },
  {
    "version": "v1.5.0",
    "date": "2026-02-11",
    "items": [
      {
        "type": "new",
        "text": "运营策划 + 观众即时消息 + 排队机制 + UI 多项改进"
      }
    ]
  },
  {
    "version": "v1.4.0",
    "date": "2026-02-10",
    "items": [
      {
        "type": "fix",
        "text": "默认密码恢复为 123456"
      },
      {
        "type": "fix",
        "text": "代码审查修复 — 安全加固 + Bug 修复 + 代码质量"
      },
      {
        "type": "new",
        "text": "Prompt 预览编辑 + 讨论密码保护 + Markdown 渲染修复"
      },
      {
        "type": "fix",
        "text": "讨论风格 review 修复 — 缓存/校验/接口/类型"
      },
      {
        "type": "new",
        "text": "讨论风格选择 + Agent 思维框架强化"
      },
      {
        "type": "improve",
        "text": "首页改为统一卡片网格布局"
      },
      {
        "type": "new",
        "text": "讨论流程动态化 — 议题驱动 + 文档重组 + 干预消化 + 整体审视"
      },
      {
        "type": "new",
        "text": "多 LLM Profile 机制 — 支持多供应商配置切换"
      }
    ]
  },
  {
    "version": "v1.3.0",
    "date": "2026-02-09",
    "items": [
      {
        "type": "new",
        "text": "主策划默认提示词加入第一性原理思维"
      },
      {
        "type": "improve",
        "text": "AgentConfigEditor 改为始终显示 Agent 选择列表"
      },
      {
        "type": "new",
        "text": "文档预览弹窗增加下载按钮"
      },
      {
        "type": "new",
        "text": "文档预览增加下载按钮"
      },
      {
        "type": "new",
        "text": "多讨论并发 + Agent 自定义配置"
      },
      {
        "type": "new",
        "text": "讨论页面重构 — 消息流 + 阶段总结面板"
      },
      {
        "type": "new",
        "text": "讨论系统动态发言分配 - 主策划决定每轮谁来说"
      }
    ]
  },
  {
    "version": "v1.2.0",
    "date": "2026-02-06",
    "items": [
      {
        "type": "new",
        "text": "讨论结果自动整理为策划文档 + 文档浏览器"
      },
      {
        "type": "new",
        "text": "讨论系统自动暂停 + 多项改进"
      },
      {
        "type": "fix",
        "text": "添加缺失的 getAgentDisplayName/getAgentAvatar 导出"
      },
      {
        "type": "fix",
        "text": "修复全局讨论死锁 + V2 集成测试"
      },
      {
        "type": "new",
        "text": "讨论系统 V2 重构"
      },
      {
        "type": "new",
        "text": "主策划主持讨论 + 历史记录 API + 角色扩展"
      }
    ]
  },
  {
    "version": "v1.1.0",
    "date": "2026-02-05",
    "items": [
      {
        "type": "new",
        "text": "聊天消息支持 Markdown 渲染 (OpenClaw 风格)"
      },
      {
        "type": "new",
        "text": "讨论页面添加返回主页按钮"
      },
      {
        "type": "fix",
        "text": "修复配置读取和前端连接问题"
      },
      {
        "type": "new",
        "text": "首页添加历史记录入口"
      },
      {
        "type": "new",
        "text": "管理后台 BW 风格重构及讨论附件功能"
      },
      {
        "type": "new",
        "text": "实现项目级策划讨论功能 (plan-project-discussion)"
      },
      {
        "type": "new",
        "text": "实现管理后台系统 (plan-admin)"
      },
      {
        "type": "new",
        "text": "界面中文化及品牌调整"
      },
      {
        "type": "fix",
        "text": "persist discussion state and integrate cost panel"
      },
      {
        "type": "new",
        "text": "实现图像生成系统 (plan-image-generation)"
      },
      {
        "type": "new",
        "text": "实现高级功能模块 (plan-advanced)"
      },
      {
        "type": "improve",
        "text": "将 WebSocket 配置移到 settings 并添加 content 字段"
      },
      {
        "type": "new",
        "text": "实现前端界面与后端记忆系统"
      },
      {
        "type": "new",
        "text": "实现 WebSocket 实时通信模块"
      },
      {
        "type": "fix",
        "text": "统一 Frontend Plan 图标库为 Lucide"
      },
      {
        "type": "fix",
        "text": "补充 Frontend Plan 5 个实现细节"
      },
      {
        "type": "new",
        "text": "实现后端核心模块"
      },
      {
        "type": "fix",
        "text": "WebSocket Plan 轻量补充"
      },
      {
        "type": "fix",
        "text": "补充 WebSocket Plan 3 个实现细节"
      },
      {
        "type": "fix",
        "text": "修复 WebSocket Plan 6 个技术细节问题"
      }
    ]
  },
  {
    "version": "v1.0.0",
    "date": "2026-02-04",
    "items": [
      {
        "type": "fix",
        "text": "Task 1.7 补充 /health 路由实现步骤"
      },
      {
        "type": "fix",
        "text": "修复 codex P3 级别问题"
      },
      {
        "type": "fix",
        "text": "修复新成员上手一致性问题"
      },
      {
        "type": "new",
        "text": "初始化项目结构和开发流程"
      }
    ]
  }
]
