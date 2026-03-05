# BW-Work 架构重构规格书

## 核心理念
- 大厅=首页，讨论+项目卡片混排
- 讨论原子化，可自由存在或归属项目阶段
- 项目=阶段流水线(DAG依赖)，每阶段多文档
- 文档版本管理(数据库)
- 讨论穿透(AI看到项目所有文档)
- 无侧边栏，右上角下拉菜单

## 默认阶段模板
1. concept(概念孵化) → 无前置
2. core-gameplay(核心玩法GDD) → concept
3. art-style(美术风格定义) → concept
4. tech-prototype(技术选型&原型) → concept
5. system-design(系统设计文档) → core-gameplay
6. numbers(数值框架) → core-gameplay
7. ui-ux(UI/UX界面设计) → core-gameplay
8. level-content(关卡/内容规划) → system-design
9. art-assets(美术资源需求清单) → art-style

Created: 2026-03-05
