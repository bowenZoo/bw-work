// Changelog data — add new entries at the TOP (newest first)
export interface ChangelogEntry {
  version: string
  date: string
  items: { type: 'new' | 'fix' | 'improve' | 'break'; text: string }[]
}

export const CHANGELOG: ChangelogEntry[] = [
  {
    version: 'v1.4.0',
    date: '2026-03-07',
    items: [
      { type: 'new', text: '超级制作人 AI 辅助发言：轮到制作人时自动生成果断推进/协商共识/深度追问三种发言建议' },
      { type: 'new', text: '讨论回放时间轴：可拖拽进度条逐帧回看历史发言' },
      { type: 'new', text: 'Agent 发言统计面板：每人发言次数、字数、平均发言长度' },
      { type: 'new', text: '关键词高亮与决策标记：快速定位重要内容' },
      { type: 'new', text: '全文搜索：跨讨论搜索关键词' },
      { type: 'new', text: '议程进度追踪：可手动勾选各议程项完成状态' },
      { type: 'new', text: '批量管理：支持批量归档/删除/打标签' },
      { type: 'new', text: '决策日志面板：汇总历次关键决策' },
      { type: 'new', text: '讨论对比：并排查看两场讨论内容差异' },
      { type: 'new', text: '自动打标签：讨论结束后根据关键词自动生成标签' },
      { type: 'new', text: '讨论完成浏览器通知' },
      { type: 'new', text: '系统管理整合进主界面：LLM 配置、图像服务、Langfuse、数据管理、审计日志均可从个人菜单直接访问，不再需要单独后台' },
      { type: 'fix', text: '修复创意总监会让 AI 主策划"分享项目诞生初心"的问题：现在 AI 会正确邀请制作人（你）亲自表达' },
    ],
  },
  {
    version: 'v1.3.0',
    date: '2026-03-06',
    items: [
      { type: 'new', text: '用户注册与认证系统：支持账号注册、登录、个人资料编辑' },
      { type: 'new', text: '项目管理：可创建项目并在项目内组织多轮讨论' },
      { type: 'new', text: '讨论密码保护：可为敏感讨论设置访问密码' },
      { type: 'new', text: '消息节流控制：防止制作人发言过于频繁影响讨论节奏' },
      { type: 'improve', text: '主策划 Checkpoint 机制升级：支持 silent / progress / decision 三种类型' },
      { type: 'improve', text: '讨论风格选择：Socratic / Directive / Debate 三种模式' },
    ],
  },
  {
    version: 'v1.2.0',
    date: '2026-03-05',
    items: [
      { type: 'new', text: 'WebSocket 实时推送：Agent 发言、状态变化实时展示' },
      { type: 'new', text: 'Agent 状态栏：实时显示各 Agent 思考/发言/空闲状态' },
      { type: 'new', text: '决策卡片（DecisionCard）：制作人可对阻塞性问题选择选项或自由输入' },
      { type: 'new', text: '设计文档面板：讨论过程中实时生成并预览设计文档' },
      { type: 'improve', text: '上下文窗口优化：三层结构（议题+历史摘要+当前轮），控制 token 消耗' },
    ],
  },
  {
    version: 'v1.1.0',
    date: '2026-03-04',
    items: [
      { type: 'new', text: '多 Agent 角色体系：主策划、系统策划、数值策划、玩家代言人、运营策划、视觉概念设计师' },
      { type: 'new', text: '苏格拉底式追问模式：主策划通过追问驱动设计决策' },
      { type: 'new', text: 'LLM 多方案配置：支持 OpenAI / Moonshot / DeepSeek / Qwen 等' },
      { type: 'new', text: 'Langfuse 监控集成：追踪所有 LLM 调用' },
    ],
  },
  {
    version: 'v1.0.0',
    date: '2026-03-03',
    items: [
      { type: 'new', text: '项目初始发布：CrewAI + FastAPI + Vue 3 多 Agent 游戏策划讨论系统' },
      { type: 'new', text: '基础讨论流程：创建讨论 → AI 多轮发言 → 生成讨论摘要' },
    ],
  },
]
