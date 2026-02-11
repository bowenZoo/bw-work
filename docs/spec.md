# 游戏策划 AI 团队 规格文档

> **版本**: 2.0
> **创建时间**: 2026-02-04
> **更新时间**: 2026-02-11

## 1. 项目概述

### 1.1 背景

游戏策划工作通常需要多角色协作讨论，包括系统策划、数值策划、关卡策划、叙事策划等。传统的策划讨论依赖人工会议，效率受限于时间和人员安排。

本项目旨在构建一个多 Agent 协作系统，模拟游戏策划团队进行设计讨论，支持：
- 多角色视角的方案讨论
- 自动化的方案迭代
- 结构化的文档产出
- 可视化的讨论过程

### 1.2 目标

1. **核心目标**：构建可视化的多 Agent 策划协作系统
2. **效率目标**：提高策划方案的迭代效率
3. **质量目标**：通过多角色视角提高方案完整性
4. **追溯目标**：保留讨论历史和决策过程

### 1.3 非目标

- 不替代人类策划的最终决策权
- 不处理具体的美术资源制作
- 不涉及实际游戏代码开发
- 不提供游戏引擎集成

## 2. 功能规格

### 2.1 Agent 角色系统

#### 用户故事

- US-01: 作为用户，我希望系统有多个策划角色，以便从不同视角讨论方案
- US-02: 作为用户，我希望每个角色有独特的关注点，以便覆盖策划的各个方面
- US-03: 作为用户，我希望角色可以配置，以便适应不同项目需求

#### 功能点

| ID | 功能 | 优先级 | 描述 |
|----|------|--------|------|
| F-01 | 系统策划角色 | P0 | 关注玩法循环、系统设计，追求有趣和自洽 |
| F-02 | 数值策划角色 | P0 | 关注平衡性、经济系统，追求留存和付费 |
| F-03 | 关卡策划角色 | P1 | 关注内容节奏、难度曲线，追求体验感 |
| F-04 | 叙事策划角色 | P1 | 关注世界观、剧情，追求沉浸感 |
| F-05 | 玩家代言人角色 | P0 | 模拟玩家视角，专门找问题 |
| F-06 | 角色配置管理 | P1 | 通过 YAML 文件配置角色属性 |

#### 验收标准

- [ ] AC-01: 每个角色有明确的 role、goal、backstory 定义
- [ ] AC-02: 角色之间可以进行多轮对话
- [ ] AC-03: 每个角色的发言体现其职责特点
- [ ] AC-04: 角色配置可通过 YAML 文件修改

### 2.2 多轮讨论流程

#### 用户故事

- US-04: 作为用户，我希望发起一个策划话题，让 Agent 团队讨论
- US-05: 作为用户，我希望看到讨论的实时进展
- US-06: 作为用户，我希望在讨论中可以人工介入

#### 功能点

| ID | 功能 | 优先级 | 描述 |
|----|------|--------|------|
| F-07 | 话题发起 | P0 | 用户输入策划话题，启动讨论 |
| F-08 | 多轮讨论 | P0 | Agent 轮流发言，相互回应 |
| F-09 | 讨论编排 | P0 | 使用 CrewAI 编排讨论顺序和流程 |
| F-10 | 实时输出 | P0 | 讨论过程实时推送到前端 |
| F-11 | 人工介入 | P2 | 用户可在讨论中插入意见 |
| F-12 | 讨论总结 | P1 | 讨论结束后自动生成总结 |

#### 验收标准

- [ ] AC-05: 用户可输入话题启动讨论
- [ ] AC-06: 讨论过程在终端或前端实时显示
- [ ] AC-07: 每轮讨论有明确的发言顺序
- [ ] AC-08: 讨论可正常结束并输出结论

### 2.3 前端可视化

#### 用户故事

- US-07: 作为用户，我希望在 Web 界面看到讨论过程
- US-08: 作为用户，我希望看到每个 Agent 的状态
- US-09: 作为用户，我希望可以回放历史讨论

#### 功能点

| ID | 功能 | 优先级 | 描述 |
|----|------|--------|------|
| F-13 | 对话展示 | P1 | 展示 Agent 对话，类似聊天界面 |
| F-14 | Agent 头像 | P1 | 每个角色有独特头像/图标 |
| F-15 | 状态面板 | P2 | 显示每个 Agent 的当前状态 |
| F-16 | 讨论历史 | P2 | 浏览和回放历史讨论 |
| F-17 | WebSocket 通信 | P1 | 前后端实时数据同步 |

#### 验收标准

- [ ] AC-09: 前端可正常显示讨论对话
- [ ] AC-10: 每条消息标识发言的 Agent
- [ ] AC-11: 页面实时更新，无需手动刷新
- [ ] AC-12: 可查看历史讨论记录

### 2.4 记忆系统

#### 用户故事

- US-10: 作为用户，我希望系统记住之前的讨论内容
- US-11: 作为用户，我希望 Agent 能引用之前的设计决策
- US-12: 作为用户，我希望可以构建项目知识库

#### 功能点

| ID | 功能 | 优先级 | 描述 |
|----|------|--------|------|
| F-18 | 项目记忆 | P1 | 存储讨论历史、设计决策 |
| F-19 | 角色记忆 | P2 | 每个 Agent 记住自己的风格和学习 |
| F-20 | 知识库 | P2 | 存储设计规范、竞品分析等 |
| F-21 | 语义检索 | P2 | 使用向量数据库进行相似性检索 |
| F-22 | 决策追踪 | P1 | 记录重要的设计决策及原因 |

#### 验收标准

- [ ] AC-13: 讨论内容自动保存到项目目录
- [ ] AC-14: 新讨论可引用历史决策
- [ ] AC-15: 支持按关键词搜索历史内容
- [ ] AC-16: 决策记录包含上下文和原因

### 2.5 监控追踪

#### 用户故事

- US-13: 作为开发者，我希望追踪 Agent 的执行过程
- US-14: 作为用户，我希望了解 API 调用成本
- US-15: 作为开发者，我希望调试 Agent 行为

#### 功能点

| ID | 功能 | 优先级 | 描述 |
|----|------|--------|------|
| F-23 | Langfuse 集成 | P0 | 接入 Langfuse 进行追踪 |
| F-24 | 执行追踪 | P1 | 记录每个 Agent 的执行步骤 |
| F-25 | 成本分析 | P1 | 统计 Token 使用和 API 成本 |
| F-26 | 调试面板 | P2 | 查看详细的执行日志 |

#### 验收标准

- [ ] AC-17: Langfuse 可正常接收追踪数据
- [ ] AC-18: 可查看每次讨论的执行链路
- [ ] AC-19: 成本数据准确记录

### 2.6 文档产出

#### 用户故事

- US-16: 作为用户，我希望讨论后自动生成策划案
- US-17: 作为用户，我希望策划案有版本管理

#### 功能点

| ID | 功能 | 优先级 | 描述 |
|----|------|--------|------|
| F-27 | 策划案生成 | P2 | 根据讨论自动生成策划文档 |
| F-28 | 版本管理 | P2 | 策划案版本追踪 |
| F-29 | 导出功能 | P2 | 支持导出 Markdown/PDF |

#### 验收标准

- [ ] AC-20: 可从讨论生成结构化策划案
- [ ] AC-21: 策划案保存在指定目录
- [ ] AC-22: 支持查看历史版本

### 2.7 图像生成系统

#### 用户故事

- US-18: 作为用户，我希望策划方案能自动配图，以便更直观地理解设计意图
- US-19: 作为策划 Agent，我希望在讨论中可以请求生成配图，以便更好地表达设计想法
- US-20: 作为用户，我希望根据方案风格自动选择合适的图像生成服务
- US-21: 作为用户，我希望可以自定义图像风格模板，以便适配不同项目需求

#### 功能点

| ID | 功能 | 优先级 | 描述 |
|----|------|--------|------|
| F-30 | 视觉概念 Agent | P1 | 新增策划团队成员，负责将文字描述转化为图像 prompt |
| F-31 | Prompt 工程模块 | P1 | 将策划文字描述转化为专业的图像生成 prompt |
| F-32 | 多后端图像服务 | P1 | 支持多个图像生成服务后端，按风格自动选择 |
| F-33 | 风格模板系统 | P1 | 预设多种游戏美术风格，支持自定义扩展 |
| F-34 | 主动请求配图 | P1 | 策划 Agent 可主动请求生成配图 |
| F-35 | 自动配图 | P2 | 讨论结束后自动为方案生成配图 |
| F-36 | 图像存储管理 | P1 | 本地存储与云存储支持 |
| F-37 | 异步图像生成 | P1 | 复杂图片通过 WebSocket 推送结果 |

#### 视觉概念 Agent 定位

视觉概念 Agent 具有双重角色：

1. **团队成员模式**：作为策划团队的一员参与讨论，从视觉角度提供设计建议
2. **服务模式**：作为工具被其他 Agent 调用，按需生成配图

```
┌─────────────────────────────────────────────────────────────┐
│  策划团队 (CrewAI Crew)                                      │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ 系统策划  │  │ 数值策划  │  │ 玩家代言人 │  │ 视觉概念  │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       │             │             │             │          │
│       └─────────────┴─────────────┴─────────────┘          │
│                           │                                 │
│                     讨论/请求配图                            │
│                           ↓                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  图像生成服务 (ImageService)                         │   │
│  │  ├── kie.ai         (通用市场模型)                   │   │
│  │  ├── wenwen-ai      (Midjourney 集成)               │   │
│  │  ├── nanobanana     (图生图、多尺寸)                 │   │
│  │  └── OpenAI DALL-E  (标准接口)                      │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

#### 图像服务后端

| 服务 | 认证方式 | 请求模式 | 特点 |
|------|----------|----------|------|
| kie.ai | Bearer token | 异步轮询 | 通用市场模型 |
| wenwen-ai | Token | OpenAI 兼容接口 | 支持 Midjourney 集成 |
| nanobanana/Evolink | Bearer token | 异步 + 回调 | 支持图生图、多尺寸、4K 质量 |
| OpenAI DALL-E | Bearer token | 同步 | 标准 OpenAI 格式 |

**nanobanana/Evolink 接口规格**：
- 端点：`POST /v1/images/generations`
- 支持功能：图生图、多尺寸输出、4K 质量

#### 风格模板

预设风格模板（可通过配置文件扩展）：

| 风格 ID | 名称 | 适用场景 | 推荐后端 |
|---------|------|----------|----------|
| `concept_character` | 游戏概念图-角色 | 角色设计方案 | wenwen-ai, nanobanana |
| `concept_scene` | 游戏概念图-场景 | 场景设计方案 | wenwen-ai, nanobanana |
| `concept_prop` | 游戏概念图-道具 | 道具/物品设计 | kie.ai, DALL-E |
| `ui_mockup` | UI 示意图 | 界面设计方案 | DALL-E |
| `pixel_art` | 像素风格 | 复古/独立游戏 | kie.ai |
| `cartoon` | 卡通风格 | 休闲/卡通游戏 | wenwen-ai |

**风格配置文件结构**（`backend/src/config/image_styles.yaml`）：

```yaml
styles:
  concept_character:
    name: 游戏概念图-角色
    prompt_prefix: "game character concept art, detailed design sheet,"
    prompt_suffix: "professional quality, artstation"
    recommended_backends:
      - wenwen-ai
      - nanobanana
    default_params:
      aspect_ratio: "2:3"
      quality: "high"

  custom_style:  # 用户可添加自定义风格
    name: 自定义风格
    prompt_prefix: "..."
    prompt_suffix: "..."
    recommended_backends:
      - kie.ai
```

#### 交互模式

| 模式 | 触发条件 | 响应方式 | 适用场景 |
|------|----------|----------|----------|
| 同步 | 简单图片请求 | 等待生成完成后返回 | UI 示意图、简单道具 |
| 异步 | 复杂图片请求 | 通过 WebSocket 推送结果 | 角色概念图、场景设计 |

**WebSocket 消息格式**：

```typescript
// 图像生成开始
{
  type: "image_generation_start",
  request_id: "img_001",
  prompt: "游戏角色概念设计...",
  style: "concept_character",
  backend: "wenwen-ai"
}

// 图像生成完成
{
  type: "image_generation_complete",
  request_id: "img_001",
  image_url: "/api/images/projects/{project_id}/img_001.png",
  metadata: {
    width: 1024,
    height: 1536,
    backend: "wenwen-ai",
    generation_time_ms: 15000
  }
}

// 图像生成失败
{
  type: "image_generation_error",
  request_id: "img_001",
  error: "Backend service unavailable"
}
```

#### 存储方案

**本地存储**（默认）：
```
data/projects/{project_id}/images/
├── img_001.png
├── img_002.png
└── metadata.json  # 图片元数据索引
```

**云存储**（可配置）：
- 支持 OSS/S3 兼容存储
- 配置项：`IMAGE_STORAGE_TYPE=local|oss|s3`

**元数据结构**：
```json
{
  "img_001": {
    "filename": "img_001.png",
    "prompt": "原始 prompt",
    "style": "concept_character",
    "backend": "wenwen-ai",
    "created_at": "2026-02-05T10:00:00Z",
    "discussion_id": "disc_123",
    "agent": "visual_concept"
  }
}
```

#### 验收标准

- [ ] AC-23: 视觉概念 Agent 可作为团队成员参与讨论
- [ ] AC-24: 视觉概念 Agent 可被其他 Agent 调用生成配图
- [ ] AC-25: 支持至少 2 个图像生成后端
- [ ] AC-26: 风格模板可通过 YAML 配置文件扩展
- [ ] AC-27: 简单图片同步返回，复杂图片异步推送
- [ ] AC-28: 生成的图片正确存储并可通过 API 访问
- [ ] AC-29: 图片元数据正确记录并与讨论关联

#### 暂不实现

- 成本控制机制（后续迭代）
- 图片编辑功能（裁剪、调整）
- 图生图功能（基于已有图片生成变体）
- 批量生成功能

### 2.8 项目级策划讨论

#### 概述

项目级策划讨论是一个完整的工作流，支持用户上传 GDD（Game Design Document），系统自动识别功能模块，用户批量选择模块后依次进行 AI 策划讨论，最终输出结构化的策划案文档。

与普通讨论的区别：
- **输入**：基于完整的 GDD 文档，而非单个话题
- **范围**：覆盖多个功能模块，保持跨模块一致性
- **输出**：结构化的策划案文档，可直接交付给开发团队
- **记忆**：项目级记忆贯穿所有模块讨论

```
┌─────────────────────────────────────────────────────────────────┐
│                    项目级策划讨论流程                             │
│                                                                 │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐      │
│  │ GDD上传  │───→│ 模块识别 │───→│ 批量选择 │───→│ 依次讨论 │      │
│  └─────────┘    └─────────┘    └─────────┘    └────┬────┘      │
│                                                    │            │
│                                              ┌─────▼─────┐      │
│                                              │  策划案生成 │      │
│                                              └─────┬─────┘      │
│                                                    │            │
│                                              ┌─────▼─────┐      │
│                                              │  输出到     │      │
│                                              │  design/   │      │
│                                              └───────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

#### 用户故事

- US-22: 作为用户，我希望上传 GDD 文档，让系统自动识别功能模块，以便快速开始策划讨论
- US-23: 作为用户，我希望一次选择多个模块，系统依次自动讨论，以便提高效率
- US-24: 作为用户，我希望讨论中断后可以恢复，以便不丢失进度
- US-25: 作为用户，我希望各模块讨论保持一致性，以便生成连贯的策划案
- US-26: 作为用户，我希望得到纯策划内容的文档，以便交付给开发团队自行生成技术规格

#### 功能点

| ID | 功能 | 优先级 | 描述 |
|----|------|--------|------|
| F-38 | GDD 上传 | P0 | Web 界面上传 GDD 文件（支持 Markdown/PDF/Word） |
| F-39 | GDD 解析 | P0 | 解析 GDD 内容，提取结构化信息 |
| F-40 | 模块自动识别 | P0 | AI 识别 GDD 中的功能模块列表 |
| F-41 | 批量模块选择 | P0 | 用户一次选择多个模块，设置讨论顺序 |
| F-42 | 依次自动讨论 | P0 | 按顺序自动进行每个模块的讨论 |
| F-43 | 讨论断点恢复 | P1 | 支持中断后从上次位置继续 |
| F-44 | 项目级记忆 | P0 | 跨模块共享上下文，保持一致性 |
| F-45 | 策划案生成 | P0 | 每个模块讨论后生成结构化策划案 |
| F-46 | 策划案汇总 | P1 | 所有模块完成后生成项目级汇总文档 |
| F-47 | 讨论进度追踪 | P1 | 实时显示讨论进度和状态 |

#### 详细流程

##### 1. GDD 上传与解析

**上传界面**：
- 支持拖拽上传或点击选择
- 支持格式：`.md`、`.pdf`、`.docx`
- 文件大小限制：10MB
- 上传后显示解析进度

**解析流程**：
```
GDD 文件 → 格式转换 → 文本提取 → 结构分析 → 模块识别
```

**数据结构**：
```typescript
interface GDDDocument {
  id: string;
  filename: string;
  upload_time: string;
  raw_content: string;      // 原始文本内容
  parsed_content: {
    title: string;          // 项目名称
    overview: string;       // 项目概述
    modules: GDDModule[];   // 识别的模块列表
  };
  status: "uploading" | "parsing" | "ready" | "error";
}

interface GDDModule {
  id: string;
  name: string;             // 模块名称
  description: string;      // 模块简述
  source_section: string;   // GDD 中的原始章节
  keywords: string[];       // 关键词（用于记忆检索）
  dependencies: string[];   // 依赖的其他模块 ID
  estimated_rounds: number; // 预估讨论轮数
}
```

##### 2. 模块自动识别

**识别策略**：
- 基于 GDD 章节结构识别
- 基于关键词匹配（如"战斗系统"、"经济系统"等）
- AI 分析识别潜在模块

**识别结果示例**：
```yaml
modules:
  - id: "combat"
    name: "战斗系统"
    description: "核心战斗机制，包括技能、伤害计算、状态效果"
    estimated_rounds: 5

  - id: "economy"
    name: "经济系统"
    description: "游戏货币、商店、交易系统"
    dependencies: ["combat"]  # 依赖战斗系统（掉落相关）
    estimated_rounds: 4

  - id: "progression"
    name: "成长系统"
    description: "角色升级、装备强化、天赋树"
    dependencies: ["combat", "economy"]
    estimated_rounds: 4
```

##### 3. 批量模块选择

**选择界面**：
- 显示识别出的所有模块
- 支持多选（Checkbox）
- 支持拖拽调整讨论顺序
- 显示模块依赖关系（推荐先讨论被依赖的模块）
- 显示预估总耗时

**智能排序建议**：
- 按依赖关系拓扑排序
- 被依赖多的模块优先
- 用户可手动调整

##### 4. 依次自动讨论

**讨论流程**：
```
┌─────────────────────────────────────────────────────────────┐
│  模块讨论循环                                                 │
│                                                             │
│  for each module in selected_modules:                       │
│      1. 加载项目级记忆                                        │
│      2. 注入 GDD 模块上下文                                   │
│      3. 启动策划团队讨论                                      │
│      4. 实时推送讨论进度                                      │
│      5. 讨论结束，生成策划案                                  │
│      6. 更新项目级记忆                                        │
│      7. 保存断点状态                                         │
│                                                             │
│  end for                                                    │
│                                                             │
│  生成项目汇总文档                                             │
└─────────────────────────────────────────────────────────────┘
```

**讨论上下文注入**：
每个模块讨论开始时，系统会注入：
- GDD 中该模块的原始描述
- 已完成模块的关键决策摘要
- 项目级约束和一致性要求

##### 5. 讨论断点恢复

**断点数据结构**：
```typescript
interface DiscussionCheckpoint {
  project_id: string;
  gdd_id: string;
  selected_modules: string[];
  current_module_index: number;
  current_module_state: {
    module_id: string;
    discussion_id: string;
    round: number;
    messages: Message[];
  };
  completed_modules: {
    module_id: string;
    design_doc_path: string;
    key_decisions: string[];
  }[];
  created_at: string;
  updated_at: string;
}
```

**恢复流程**：
1. 检测未完成的项目讨论
2. 显示恢复提示（上次位置、已完成模块数）
3. 用户确认恢复或重新开始
4. 加载断点状态，继续讨论

##### 6. 项目级记忆

**记忆类型**：

| 类型 | 内容 | 用途 |
|------|------|------|
| GDD 上下文 | 完整 GDD 内容 | 确保讨论符合总体设计 |
| 模块决策 | 已完成模块的关键决策 | 保持跨模块一致性 |
| 术语表 | 项目专有名词定义 | 统一术语使用 |
| 约束条件 | 技术/资源约束 | 确保方案可行性 |

**记忆检索**：
- 讨论时自动检索相关记忆
- 使用向量相似度 + 关键词匹配
- 注入到 Agent 上下文中

**一致性检查**：
- 讨论结束前检查与已有决策的冲突
- 冲突时提醒 Agent 重新讨论
- 记录冲突解决过程

#### 策划案输出规范

##### 输出位置

```
data/projects/{project_id}/design/
├── index.md                    # 项目策划案索引
├── combat-system.md            # 战斗系统策划案
├── economy-system.md           # 经济系统策划案
├── progression-system.md       # 成长系统策划案
└── assets/                     # 配图资源
    ├── combat-flow.png
    └── economy-flow.png
```

##### 策划案文档结构

每个模块的策划案采用统一格式：

```markdown
# {模块名} 策划案

> **版本**: 1.0
> **生成时间**: {timestamp}
> **讨论 ID**: {discussion_id}
> **基于 GDD**: {gdd_filename}

## 1. 功能概述

### 1.1 设计目标
{该模块要达成的核心目标}

### 1.2 核心体验
{玩家的核心体验是什么}

### 1.3 与其他系统的关系
{与其他模块的依赖和交互}

## 2. 玩法描述

### 2.1 基础玩法
{核心玩法机制描述}

### 2.2 进阶玩法
{深度玩法和策略空间}

### 2.3 玩法示例
{具体的玩法场景示例}

## 3. 界面流程

### 3.1 主要界面
{界面列表和功能说明}

### 3.2 操作流程
{用户操作流程图/描述}

### 3.3 界面跳转
{界面间的跳转关系}

## 4. 数值框架

### 4.1 核心公式
{关键数值公式，如伤害计算}

### 4.2 参数表
{可配置的数值参数}

### 4.3 平衡目标
{数值平衡的设计目标}

## 5. 边界处理

### 5.1 异常情况
{各种边界和异常情况的处理}

### 5.2 防作弊
{防止利用的设计考虑}

### 5.3 容错机制
{出错时的回退方案}

## 6. 附录

### 6.1 讨论记录摘要
{AI 讨论的关键点摘要}

### 6.2 设计决策记录
{重要决策及其原因}

### 6.3 待确认事项
{需要人工确认的问题}
```

##### 策划案特点说明

**只包含策划内容**：
- 不包含技术实现细节
- 不包含数据库设计
- 不包含 API 接口定义
- 不包含代码结构

**交付方式**：
- 策划案输出到 `data/projects/{project_id}/design/`
- 可导出为 Markdown/PDF
- 交付给 bw-game 后，由其自行生成 spec 和代码

#### 数据结构定义

##### 项目讨论状态

```typescript
interface ProjectDiscussion {
  id: string;
  project_id: string;
  gdd: GDDDocument;
  selected_modules: string[];
  module_order: string[];
  status: "pending" | "in_progress" | "paused" | "completed" | "error";
  progress: {
    total_modules: number;
    completed_modules: number;
    current_module: string | null;
    current_round: number;
  };
  checkpoint: DiscussionCheckpoint | null;
  created_at: string;
  updated_at: string;
}
```

##### 模块讨论结果

```typescript
interface ModuleDiscussionResult {
  module_id: string;
  module_name: string;
  discussion_id: string;
  status: "completed" | "skipped" | "error";
  design_doc: {
    path: string;
    version: string;
    sections: string[];
  };
  key_decisions: {
    id: string;
    topic: string;
    decision: string;
    reason: string;
    participants: string[];
  }[];
  duration_minutes: number;
  token_usage: number;
}
```

#### WebSocket 消息

##### 项目讨论进度

```typescript
// 项目讨论开始
{
  type: "project_discussion_start",
  project_id: string,
  total_modules: number,
  module_order: string[]
}

// 模块讨论开始
{
  type: "module_discussion_start",
  project_id: string,
  module_id: string,
  module_name: string,
  module_index: number,
  total_modules: number
}

// 模块讨论进度
{
  type: "module_discussion_progress",
  project_id: string,
  module_id: string,
  round: number,
  speaker: string,
  message: string
}

// 模块讨论完成
{
  type: "module_discussion_complete",
  project_id: string,
  module_id: string,
  design_doc_path: string,
  key_decisions: string[]
}

// 项目讨论完成
{
  type: "project_discussion_complete",
  project_id: string,
  total_duration_minutes: number,
  design_docs: string[],
  summary_path: string
}

// 讨论暂停（断点保存）
{
  type: "discussion_paused",
  project_id: string,
  checkpoint_id: string,
  current_module: string,
  completed_modules: number
}
```

#### API 接口

##### GDD 上传

```
POST /api/projects/{project_id}/gdd
Content-Type: multipart/form-data

Request:
  file: File (GDD 文档)

Response:
{
  "gdd_id": "gdd_001",
  "filename": "my-game-gdd.md",
  "status": "parsing",
  "message": "GDD 上传成功，正在解析..."
}
```

##### 获取识别的模块

```
GET /api/projects/{project_id}/gdd/{gdd_id}/modules

Response:
{
  "gdd_id": "gdd_001",
  "status": "ready",
  "modules": [
    {
      "id": "combat",
      "name": "战斗系统",
      "description": "核心战斗机制...",
      "dependencies": [],
      "estimated_rounds": 5
    },
    ...
  ],
  "suggested_order": ["combat", "economy", "progression"]
}
```

##### 启动批量讨论

```
POST /api/projects/{project_id}/discussions/batch

Request:
{
  "gdd_id": "gdd_001",
  "modules": ["combat", "economy", "progression"],
  "order": ["combat", "economy", "progression"]
}

Response:
{
  "discussion_id": "disc_batch_001",
  "status": "started",
  "websocket_url": "/ws/projects/{project_id}/discussions/disc_batch_001"
}
```

##### 暂停/恢复讨论

```
POST /api/projects/{project_id}/discussions/{discussion_id}/pause

Response:
{
  "status": "paused",
  "checkpoint_id": "cp_001"
}

POST /api/projects/{project_id}/discussions/{discussion_id}/resume

Response:
{
  "status": "resumed",
  "current_module": "economy",
  "completed_modules": 1
}
```

##### 获取策划案

```
GET /api/projects/{project_id}/design/{module_id}

Response:
{
  "module_id": "combat",
  "module_name": "战斗系统",
  "design_doc": {
    "path": "data/projects/proj_001/design/combat-system.md",
    "content": "# 战斗系统策划案\n...",
    "version": "1.0",
    "created_at": "2026-02-05T10:00:00Z"
  }
}
```

#### 验收标准

- [ ] AC-30: 支持上传 Markdown/PDF/Word 格式的 GDD 文件
- [ ] AC-31: GDD 解析后能正确识别功能模块列表
- [ ] AC-32: 用户可批量选择模块并调整讨论顺序
- [ ] AC-33: 系统按顺序自动进行各模块讨论
- [ ] AC-34: 讨论中断后可从断点恢复
- [ ] AC-35: 各模块讨论能访问项目级记忆，保持一致性
- [ ] AC-36: 每个模块讨论后生成符合规范的策划案文档
- [ ] AC-37: 策划案输出到 `data/projects/{project_id}/design/` 目录
- [ ] AC-38: 策划案只包含策划内容，不含技术规格
- [ ] AC-39: 支持导出策划案为 Markdown/PDF 格式

#### 暂不实现

- 多人协作编辑 GDD
- GDD 版本对比
- 策划案在线编辑
- 与外部项目管理工具集成（如 Jira）
- 自动生成技术规格（由 bw-game 负责）

### 2.9 讨论流程动态化改造

#### 概述

当前的文档驱动讨论流程（`run_document_centric`）存在三个核心局限：

1. **议题层(Agenda)是孤岛**：`Agenda` 模型和 `create_agenda_prompt` 已实现，但未真正接入 `run_document_centric` 主循环。议题仅作为展示数据，不影响讨论走向。
2. **文档结构一次性固化**：`DocPlan` 在 Phase 0 生成后不再变化，无法响应讨论中发现的新需求（如需拆分章节、新增文件）。
3. **观众干预缺乏回溯能力**：用户注入消息后，讨论只能在当前章节处理，无法回溯已完成章节进行修订。

本模块的目标是将这三个能力真正融入讨论主循环，使讨论过程具备"自适应"特性。

```
┌─────────────────────────────────────────────────────────────────┐
│               讨论流程动态化 - 三层改造                             │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Layer 1: 议题驱动 (Agenda-Driven)                       │   │
│  │  Agenda ←→ DocPlan sections (多对多)                      │   │
│  │  每轮结束：标记完结 / 新增议题 / 调整优先级                   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           ↕                                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Layer 2: 文档结构动态重组 (Dynamic DocPlan)              │   │
│  │  主策划每轮总结时可：拆分 / 合并 / 新增章节                   │   │
│  │  DocWriter 支持追加 section marker                        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           ↕                                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Layer 3: 干预回溯 (Intervention Retrospection)          │   │
│  │  观众消息 → 影响评估 → 当前章节处理 / 回溯修订              │   │
│  │  已完成章节可标记回 pending，保留内容允许修订                 │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

#### 用户故事

- US-27: 作为用户，我希望讨论开始时自动生成议程，并在讨论过程中看到议题的推进和完成状态
- US-28: 作为用户，我希望系统能在讨论中发现新议题并自动追加，而不是遗漏它们
- US-29: 作为用户，我希望策划文档的结构能随讨论深入而演化，而不是被初始规划限死
- US-30: 作为用户，我希望注入意见后，系统能智能判断影响范围，必要时回溯修订已完成的章节
- US-31: 作为用户，我希望文档结构变更时前端能实时更新，不需要刷新页面
- US-32: 作为用户，我希望观众干预后由主策划先统一思考消化，而不是直接让其他 agent 接话
- US-33: 作为用户，我希望讨论结束前主策划对整体策划案做一次全面审视，确认是否真的讨论完成

#### 功能点

| ID | 功能 | 优先级 | 描述 |
|----|------|--------|------|
| F-48 | 议题自动生成 | P0 | 讨论启动时主策划根据话题生成初始议程 |
| F-49 | 议题生命周期管理 | P0 | 每轮结束后主策划可标记议题完结、新增、调整优先级 |
| F-50 | 议题-章节多对多映射 | P0 | 建立议题与文档章节的关联关系 |
| F-51 | 章节拆分 | P1 | 主策划可将一个章节拆分为多个子章节 |
| F-52 | 章节合并 | P1 | 主策划可将多个相关章节合并为一个 |
| F-53 | 章节/文件新增 | P0 | 主策划可在讨论中途新增文件或章节 |
| F-54 | DocWriter 动态追加 | P0 | DocWriter 支持在已有骨架上追加 section marker |
| F-55 | 干预影响评估 | P0 | 观众消息注入后，主策划执行影响评估环节 |
| F-56 | 章节回溯修订 | P1 | 已完成章节可标记回 pending，保留内容允许增量修订 |
| F-57 | 文档变更广播 | P0 | DocPlan 变更后实时广播给前端 |
| F-58 | 干预后主策划优先消化 | P0 | 观众消息注入后，主策划先独立消化评估，再恢复其他 agent 讨论 |
| F-59 | 讨论完成前整体审视 | P0 | 所有章节完成后，主策划对全部策划案做整体审视，确认是否真正完成 |

#### 详细设计

##### 1. 议题层(Agenda)接入讨论流程

**现状分析**：

当前代码中 `Agenda`、`AgendaItem` 模型已完整实现（`backend/src/models/agenda.py`），`LeadPlanner.create_agenda_prompt` 已定义（`backend/src/agents/lead_planner.py:549`），`DiscussionCrew._init_agenda` 和 `complete_current_agenda_item` 方法已实现，前端 `AgendaPanel` 组件和 WebSocket 事件处理已就绪。但 `run_document_centric` 主循环从未调用这些方法。

**改造方案**：

在 `run_document_centric` 的 Phase 0（生成 DocPlan 之后）插入议题生成步骤，并在每轮 section summary 之后插入议题管理步骤。

```
Phase 0 流程变更:
  1. _generate_doc_plan(topic, attachment)        # 已有
  2. _doc_writer.create_skeleton(doc_plan)         # 已有
  3. [新增] _generate_initial_agenda(topic, attachment)
     └→ 调用 lead_planner.create_agenda_prompt()
     └→ 解析输出，调用 _init_agenda()
     └→ 广播 agenda_init 事件

每轮结束时的流程变更:
  1. _lead_planner_section_summary()              # 已有
  2. [新增] _agenda_round_update(summary, section)
     └→ 解析 summary 中的议题指令
     └→ 执行：标记完结 / 新增 / 调整优先级
     └→ 广播 agenda 事件
```

**议题管理指令格式**（在主策划 summary 中输出）：

```markdown
### 议题状态更新
```agenda_update
complete: <agenda_item_id>  # 标记议题完结
add: [新议题标题] - 描述     # 新增发现的议题
priority: <agenda_item_id> high|low  # 调整优先级
```（结束标记）
```

**议题-章节映射**：

在 `AgendaItem` 模型上新增 `related_sections` 字段，在 `SectionPlan` 上新增 `related_agenda_items` 字段，建立多对多关系。

```python
# agenda.py 扩展
class AgendaItem(BaseModel):
    # ... 已有字段 ...
    related_sections: list[str] = Field(default_factory=list)  # section IDs
    priority: int = 0  # 0=normal, 1=high, -1=low

# doc_plan.py 扩展
@dataclass
class SectionPlan:
    # ... 已有字段 ...
    related_agenda_items: list[str] = field(default_factory=list)  # agenda item IDs
```

**映射建立时机**：
- Phase 0 初始映射：根据议题标题与章节标题的语义匹配自动建立
- 讨论中动态映射：主策划在 section opening 中可声明当前章节关联哪些议题
- 映射广播：通过 `agenda_mapping_update` WebSocket 事件通知前端

##### 2. 文档结构动态重组

**现状分析**：

`DocPlan` 在 `_generate_doc_plan` 中一次性生成，后续仅有 `section.status` 的变更。`DocWriter.create_skeleton` 只在开头调用一次。需要支持运行时修改 `DocPlan` 并同步修改文件。

**支持的结构变更操作**：

| 操作 | 触发者 | 前置条件 | 影响 |
|------|--------|----------|------|
| 拆分章节 | 主策划 summary | 原章节尚未 completed | 原章节替换为多个子章节，内容分发 |
| 合并章节 | 主策划 summary | 被合并章节均未 completed | 多个章节合并为一个，内容合并 |
| 新增章节 | 主策划 summary | 无 | 在指定文件的指定位置插入新章节 |
| 新增文件 | 主策划 summary | 无 | 创建新文件和其章节 |

**DocPlan 变更操作接口**：

```python
# doc_plan.py 新增方法
class DocPlan:
    def split_section(self, section_id: str, new_sections: list[SectionPlan]) -> bool:
        """将一个章节拆分为多个子章节。"""

    def merge_sections(self, section_ids: list[str], merged: SectionPlan) -> bool:
        """将多个章节合并为一个。"""

    def add_section(self, file_index: int, section: SectionPlan,
                    after_section_id: str | None = None) -> bool:
        """在指定文件中添加新章节。"""

    def add_file(self, file_plan: "FilePlan") -> None:
        """添加新文件到文档计划。"""
```

**DocWriter 动态更新接口**：

```python
# doc_writer.py 新增方法
class DocWriter:
    def add_section_marker(self, filename: str, section_id: str,
                           title: str, description: str,
                           after_section_id: str | None = None) -> str:
        """在已有文件中追加 section marker。"""

    def split_section_content(self, filename: str, old_section_id: str,
                              new_sections: list[dict]) -> str:
        """拆分一个 section 的内容到多个新 section。"""

    def merge_section_content(self, filename: str, section_ids: list[str],
                              merged_section_id: str, merged_title: str) -> str:
        """合并多个 section 的内容为一个。"""

    def create_new_file(self, file_plan) -> None:
        """创建新的骨架文件。"""
```

**变更指令格式**（在主策划 summary 中输出）：

```markdown
### 文档结构调整
```doc_restructure
split: s3 -> [s3a: "战斗公式设计", s3b: "战斗反馈设计"]
merge: [s5, s6] -> s5_6: "音效与视觉反馈"
add_section: file=0, after=s2, id=s2b, title="玩家反馈循环", desc="..."
add_file: filename="数值平衡.md", title="数值平衡设计", sections=[{id: "sN1", ...}]
```（结束标记）
```

**变更处理流程**：

```
主策划 summary 输出
  │
  ├─ 解析 ```doc_restructure 代码块
  │
  ├─ 校验变更合法性
  │   ├─ 拆分：原章节未 completed
  │   ├─ 合并：所有目标章节未 completed
  │   ├─ 新增：section_id 不冲突
  │   └─ 新文件：filename 不冲突
  │
  ├─ 执行 DocPlan 变更
  │
  ├─ 执行 DocWriter 文件变更
  │
  ├─ 更新 Agenda 映射（如有关联）
  │
  └─ 广播 doc_plan 事件 + section_update 事件
```

##### 3. 观众干预后的回溯审视（主策划优先消化）

**现状分析**：

当前 `_inject_user_messages` 仅将消息记录到 memory 并广播，然后在下一轮正常讨论中作为上下文使用。不存在"影响评估"环节，也无法回溯已完成章节。更关键的是，**干预恢复后直接让所有 agent 正常讨论，没有让主策划先统一思考消化**。

**改造方案**：

在 `_inject_user_messages` 之后、其他 agent 恢复讨论之前，插入**主策划专属消化步骤**。主策划先独立消化观众意见、评估影响范围、规划处理方案，然后再恢复其他 agent 的正常讨论。

**核心原则**：观众干预后，必须由主策划先统一思考，而非直接让其他 agent 接话。

**主策划消化 + 影响评估流程**：

```
观众消息注入
  │
  ├─ _inject_user_messages(injected)          # 已有
  │
  └─ [新增] _lead_planner_digest_intervention(injected)
      │
      ├─ Step 1: 主策划消化（Digest）
      │   ├─ 调用 lead_planner 消化观众意见
      │   │   输入：用户消息 + 当前讨论上下文 + 当前章节 + 已讨论进度
      │   │   输出：消化总结（包含观点理解、关键诉求提取、与当前讨论的关联分析）
      │   ├─ 广播 lead_planner_digest 事件（让前端展示主策划的思考过程）
      │   └─ 将消化总结写入 memory（后续 agent 可参考）
      │
      ├─ Step 2: 影响评估（Assessment）
      │   ├─ 调用 lead_planner 评估影响范围
      │   │   输入：消化总结 + 当前 DocPlan + 当前章节内容 + 已完成章节列表
      │   ├─ 解析评估结果
      │   │   ├─ CURRENT_ONLY  → 仅在当前章节处理，无需回溯
      │   │   ├─ REOPEN:[s1,s3] → 需要重开指定已完成章节
      │   │   └─ NEW_TOPIC      → 需要新增议题和/或章节
      │   └─ 广播 intervention_assessment 事件
      │
      ├─ Step 3: 执行评估决策
      │   ├─ 执行回溯操作（如需要）
      │   │   ├─ section.status = "pending"（保留已有内容）
      │   │   ├─ 更新 DocPlan.current_section_id（可选：优先回溯）
      │   │   └─ 广播 section_reopened 事件
      │   ├─ 执行新增操作（如需要）
      │   │   ├─ 新增 Agenda item
      │   │   ├─ 新增 DocPlan section
      │   │   └─ DocWriter 追加 section marker
      │   └─ 广播处理方案给前端
      │
      └─ Step 4: 恢复讨论
          ├─ 主策划输出下一步讨论引导（将观众意见融入讨论方向）
          └─ 其他 agent 基于主策划的引导继续正常讨论
```

**影响评估 Prompt**：

```python
# lead_planner.py 新增方法
class LeadPlanner:
    def create_intervention_assessment_prompt(
        self,
        user_messages: list[str],
        current_section: str,
        completed_sections: list[dict],  # [{id, title, content_summary}]
        doc_plan_summary: str,
    ) -> str:
        """创建干预影响评估 prompt。"""
```

**评估结果格式**：

```markdown
### 干预影响评估
```intervention_assessment
impact_level: CURRENT_ONLY | REOPEN | NEW_TOPIC
affected_sections: [s1, s3]  # 需要重开的章节 ID
reason: "用户指出战斗系统需要考虑PvP场景，这影响了已完成的s1(系统概述)和当前的s3(战斗设计)"
action_plan:
  - reopen s1: "在系统概述中补充PvP模式说明"
  - current s3: "在当前章节的讨论中纳入PvP战斗设计"
  - add_agenda: "PvP 平衡性讨论" - "针对PvP模式的数值平衡专项讨论"
```（结束标记）
```

**回溯修订的约束**：

- 已完成章节标记回 `pending` 时，**保留已有内容**
- DocWriter 的 `update_section` 已支持增量更新（"在其基础上增补和完善，不要推翻已有结论"），天然适配回溯修订
- 回溯的章节在讨论队列中优先级低于当前章节（先完成当前，再回溯修订），除非用户明确要求立即回溯
- 每次回溯最多重开 3 个章节，避免过度回溯导致讨论失控

##### 4. 讨论完成前的整体审视

**现状分析**：

当前 `run_document_centric` 在所有章节的 `status` 变为 `completed` 后直接结束讨论，没有任何最终审查环节。这可能导致：
- 各章节虽然单独完善，但跨章节存在矛盾或不一致
- 讨论过程中发现的新议题未被处理就结束了
- 观众干预引发的修改与其他章节不协调
- 缺少一个"全局视角"来判断策划案是否真正完整

**改造方案**：

在所有章节完成后、讨论正式结束前，插入**主策划整体审视环节**。

**整体审视流程**：

```
所有章节 completed
  │
  └─ [新增] _lead_planner_holistic_review(doc_plan)
      │
      ├─ Step 1: 全局审视
      │   ├─ 调用 lead_planner 整体审视
      │   │   输入：所有文件内容 + DocPlan + Agenda(含未完成项) + 讨论历史摘要
      │   │   输出：审视报告
      │   └─ 广播 holistic_review 事件（前端展示审视过程）
      │
      ├─ Step 2: 解析审视结论
      │   ├─ APPROVED → 讨论真正完成，进入结束流程
      │   ├─ NEEDS_REVISION → 需要修订部分章节
      │   │   ├─ 指明需修订的章节及原因
      │   │   ├─ reopen 指定章节（status → pending）
      │   │   └─ 返回讨论主循环继续处理
      │   └─ NEEDS_NEW_TOPIC → 发现遗漏议题
      │       ├─ 新增 Agenda item + DocPlan section
      │       └─ 返回讨论主循环继续处理
      │
      └─ Step 3: 输出最终总结（仅 APPROVED 时）
          ├─ 生成跨章节一致性确认
          ├─ 标记所有 Agenda items 为 completed
          └─ 广播 discussion_completed 事件
```

**审视 Prompt**：

```python
# lead_planner.py 新增方法
class LeadPlanner:
    def create_holistic_review_prompt(
        self,
        all_file_contents: list[dict],      # [{filename, content}]
        doc_plan_summary: str,
        pending_agenda_items: list[str],     # 未完成的议题
        discussion_summary: str,             # 讨论过程摘要
    ) -> str:
        """创建整体审视 prompt。

        审视维度：
        1. 跨章节一致性：各章节之间是否存在矛盾或不协调
        2. 完整性检查：是否覆盖了所有议题，有无遗漏的关键设计点
        3. 观众意见回应：是否充分回应了观众的所有干预意见
        4. 整体质量：策划案整体是否达到可交付标准
        """
```

**审视结果格式**：

```markdown
### 整体审视报告
```holistic_review
conclusion: APPROVED | NEEDS_REVISION | NEEDS_NEW_TOPIC
review_dimensions:
  consistency: "各章节数值体系一致，战斗公式与经济系统参数匹配"
  completeness: "所有12个议题已完成讨论，无遗漏"
  audience_response: "已回应观众提出的PvP平衡问题"
  quality: "策划案内容详实，可作为开发参考"
revision_needed:
  - section: s2
    reason: "战斗系统中的数值与第5章经济系统的产出不匹配，需要统一"
  - section: s7
    reason: "缺少与新增PvP模式的交互说明"
new_topics:
  - title: "跨系统数值校验"
    description: "对战斗、经济、成长三个系统的数值进行交叉校验"
```（结束标记）
```

**审视约束**：

- 整体审视最多执行 2 次（防止无限循环）
- 第 2 次审视如仍为 NEEDS_REVISION，强制 APPROVED 并在最终总结中注明待改进项
- 审视过程中不执行文档结构变更（仅 reopen 已有章节或新增议题）
- 审视报告自动保存到讨论记录中

#### 数据模型变更

##### AgendaItem 扩展

```python
class AgendaItem(BaseModel):
    # ... 已有字段 ...
    related_sections: list[str] = Field(default_factory=list)  # 关联的 section IDs
    priority: int = Field(default=0)  # -1=low, 0=normal, 1=high
    source: str = Field(default="initial")  # "initial" | "discovered" | "intervention"
```

##### SectionPlan 扩展

```python
@dataclass
class SectionPlan:
    # ... 已有字段 ...
    related_agenda_items: list[str] = field(default_factory=list)  # 关联的 agenda item IDs
    revision_count: int = 0  # 被回溯修订的次数
    reopened_reason: str | None = None  # 重开原因（如有）
```

##### DocPlan 新增方法

```python
@dataclass
class DocPlan:
    # ... 已有字段和方法 ...

    def split_section(self, section_id: str, new_sections: list["SectionPlan"]) -> bool:
        """拆分章节。返回是否成功。"""

    def merge_sections(self, section_ids: list[str], merged: "SectionPlan") -> bool:
        """合并章节。返回是否成功。"""

    def add_section(self, file_index: int, section: "SectionPlan",
                    after_section_id: str | None = None) -> bool:
        """新增章节。返回是否成功。"""

    def add_file(self, file_plan: "FilePlan") -> None:
        """新增文件。"""

    def reopen_section(self, section_id: str, reason: str) -> bool:
        """将已完成章节标记回 pending，保留内容。"""

    def get_completed_sections(self) -> list[tuple["FilePlan", "SectionPlan"]]:
        """获取所有已完成的章节。"""

    def get_reopened_sections(self) -> list[tuple["FilePlan", "SectionPlan"]]:
        """获取所有被回溯重开的章节。"""
```

#### WebSocket 新增事件

```typescript
// 议题初始化（已有，但需在 run_document_centric 中调用）
{
  type: "agenda",
  data: {
    event_type: "agenda_init",
    agenda: Agenda
  }
}

// 议题-章节映射更新
{
  type: "agenda",
  data: {
    event_type: "mapping_update",
    mappings: Array<{
      agenda_item_id: string,
      section_ids: string[]
    }>
  }
}

// 文档结构变更
{
  type: "doc_restructure",
  data: {
    discussion_id: string,
    operation: "split" | "merge" | "add_section" | "add_file",
    details: object,  // 操作特定数据
    updated_doc_plan: DocPlan  // 变更后的完整 DocPlan
  }
}

// 章节重开（回溯）
{
  type: "section_reopened",
  data: {
    discussion_id: string,
    section_id: string,
    section_title: string,
    filename: string,
    reason: string
  }
}

// 干预影响评估结果
{
  type: "intervention_assessment",
  data: {
    discussion_id: string,
    impact_level: "CURRENT_ONLY" | "REOPEN" | "NEW_TOPIC",
    affected_sections: string[],
    reason: string,
    action_plan: string[]
  }
}

// [新增] 主策划消化观众干预（F-58）
{
  type: "lead_planner_digest",
  data: {
    discussion_id: string,
    digest_summary: string,        // 主策划的消化总结
    key_points: string[],          // 提取的关键诉求
    guidance: string               // 后续讨论引导方向
  }
}

// [新增] 整体审视报告（F-59）
{
  type: "holistic_review",
  data: {
    discussion_id: string,
    review_round: number,          // 第几次审视（1 或 2）
    conclusion: "APPROVED" | "NEEDS_REVISION" | "NEEDS_NEW_TOPIC",
    review_dimensions: {
      consistency: string,
      completeness: string,
      audience_response: string,
      quality: string
    },
    revisions_needed: Array<{section_id: string, reason: string}>,
    new_topics: Array<{title: string, description: string}>
  }
}
```

#### API 接口变更

##### 手动触发议题操作

```
POST /api/discussions/{discussion_id}/agenda/items/{item_id}/complete
Response: { "status": "completed", "item": AgendaItem }

POST /api/discussions/{discussion_id}/agenda/items/{item_id}/priority
Request: { "priority": 1 }  // -1, 0, 1
Response: { "status": "updated", "item": AgendaItem }
```

##### 手动触发文档重组（管理员/调试用）

```
POST /api/discussions/{discussion_id}/doc-plan/restructure
Request: {
  "operation": "add_section",
  "params": {
    "file_index": 0,
    "section": { "id": "sN", "title": "...", "description": "..." },
    "after_section_id": "s3"
  }
}
Response: { "status": "success", "doc_plan": DocPlan }
```

#### 代码改动范围

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `backend/src/models/agenda.py` | 扩展 | AgendaItem 新增 `related_sections`、`priority`、`source` |
| `backend/src/models/doc_plan.py` | 扩展 | SectionPlan 新增字段; DocPlan 新增 `split_section`/`merge_sections`/`add_section`/`add_file`/`reopen_section` |
| `backend/src/agents/lead_planner.py` | 扩展 | 新增 `create_intervention_digest_prompt`、`create_intervention_assessment_prompt`、`create_holistic_review_prompt`; 修改 `create_section_summary_prompt` 加入议题和结构调整指令格式 |
| `backend/src/agents/doc_writer.py` | 扩展 | 新增 `add_section_marker`/`split_section_content`/`merge_section_content`/`create_new_file` |
| `backend/src/crew/discussion_crew.py` | 核心改动 | `run_document_centric` 主循环插入议题生成、议题管理、结构变更处理、干预消化评估、整体审视步骤 |
| `backend/src/api/routes/intervention.py` | 扩展 | 新增议题优先级调整、手动文档重组接口 |
| `backend/src/api/websocket/events.py` | 扩展 | 新增 `doc_restructure`、`section_reopened`、`intervention_assessment` 事件 |
| `frontend/src/composables/useDiscussion.ts` | 扩展 | 处理新 WebSocket 事件，更新本地 docPlan/agenda 状态 |
| `frontend/src/types/index.ts` | 扩展 | 新增事件类型定义 |
| `frontend/src/components/discussion/AgendaPanel.vue` | 扩展 | 展示议题-章节映射、议题来源标签 |

#### `run_document_centric` 改造后伪代码

```python
def run_document_centric(self, topic, max_rounds, attachment, auto_pause_interval):
    self._init_discussion(topic)

    # Phase 0a: 生成文档计划
    doc_plan = self._generate_doc_plan(topic, attachment)
    self._doc_writer.create_skeleton(doc_plan)
    self._broadcast_doc_plan_event(doc_plan)

    # Phase 0b: [新增] 生成初始议程
    agenda = self._generate_initial_agenda(topic, attachment)
    self._establish_agenda_section_mapping(agenda, doc_plan)
    self._broadcast_agenda_event("agenda_init", agenda.to_dict())

    # Phase 1-N: 逐章节讨论
    for round_num in range(1, max_rounds + 1):
        file_plan, section = self._pick_next_section(doc_plan)
        if file_plan is None:
            break

        # ... 已有的 section opening / agents discuss / section summary ...

        opening = self._lead_planner_section_opening(section, ...)
        round_responses = self._run_agents_parallel_sync(...)
        summary = self._lead_planner_section_summary(...)

        # [新增] 解析并执行议题管理指令
        self._process_agenda_directives(summary, section)

        # [新增] 解析并执行文档结构变更指令
        self._process_doc_restructure(summary, doc_plan, section)

        # DocWriter 更新章节
        self._doc_writer.update_section(...)

        # 检查暂停/干预
        injected = self._check_pause_and_wait()
        if injected:
            self._inject_user_messages(injected)

            # [新增] 主策划优先消化 + 影响评估（F-58）
            # 关键：主策划先独立消化，再恢复其他 agent 讨论
            digest = self._lead_planner_digest_intervention(injected, section)
            self._broadcast_event("lead_planner_digest", digest)

            assessment = self._assess_intervention_impact(digest, doc_plan, section)
            self._execute_assessment_actions(assessment, doc_plan)

            # 主策划输出讨论引导，融入观众意见
            self._lead_planner_post_intervention_guidance(digest, assessment)

        # 广播更新后的状态
        self._broadcast_doc_plan_event(doc_plan)

    # [新增] Phase Final: 讨论完成前整体审视（F-59）
    holistic_review_count = 0
    max_holistic_reviews = 2

    while holistic_review_count < max_holistic_reviews:
        review = self._lead_planner_holistic_review(doc_plan, agenda)
        self._broadcast_event("holistic_review", review)
        holistic_review_count += 1

        if review.conclusion == "APPROVED":
            break
        elif review.conclusion in ("NEEDS_REVISION", "NEEDS_NEW_TOPIC"):
            self._execute_review_actions(review, doc_plan, agenda)
            # 回到讨论主循环处理新增/重开的章节
            for round_num in range(round_num + 1, max_rounds + 1):
                file_plan, section = self._pick_next_section(doc_plan)
                if file_plan is None:
                    break
                # ... 正常讨论流程 ...
        else:
            break

    if holistic_review_count >= max_holistic_reviews and review.conclusion != "APPROVED":
        # 强制结束，注明待改进项
        self._force_complete_with_notes(review)

    self._finalize_discussion(doc_plan, agenda)
```

#### 验收标准

- [ ] AC-40: 讨论启动时自动生成议程并展示在前端 AgendaPanel 中
- [ ] AC-41: 每轮结束后，主策划可通过 summary 中的指令标记议题完结
- [ ] AC-42: 讨论过程中发现的新议题能自动追加到议程
- [ ] AC-43: 议题与文档章节的多对多映射在前端可视化展示
- [ ] AC-44: 主策划可在讨论中途新增文档章节，DocWriter 正确追加 section marker
- [ ] AC-45: 主策划可拆分章节，原内容正确分发到子章节
- [ ] AC-46: 文档结构变更后，前端实时更新 DocPlan 展示
- [ ] AC-47: 观众消息注入后，系统执行影响评估并展示评估结果
- [ ] AC-48: 影响评估判定需要回溯时，已完成章节正确标记回 pending
- [ ] AC-49: 回溯修订的章节保留已有内容，DocWriter 在已有内容基础上增量更新
- [ ] AC-50: 每次回溯最多重开 3 个章节，超出时提示用户确认
- [ ] AC-51: 观众干预后，主策划先独立消化评估，产出消化总结后再恢复其他 agent 讨论
- [ ] AC-52: 主策划消化过程通过 WebSocket 广播，前端展示主策划的思考过程
- [ ] AC-53: 所有章节完成后，主策划执行整体审视，检查跨章节一致性和完整性
- [ ] AC-54: 整体审视判定 NEEDS_REVISION 时，正确 reopen 相关章节并继续讨论
- [ ] AC-55: 整体审视最多 2 次，第 2 次仍有问题则强制结束并注明待改进项

#### 暂不实现

- 议题投票机制（Agent 对议题优先级投票）
- 章节之间的依赖关系建模（如 s2 依赖 s1 的结论）
- 多次回溯的冲突检测（同一章节被多次回溯）
- 文档结构变更的撤销/回退
- 前端拖拽调整文档结构

### 2.10 Checkpoint 驱动交互重设计

#### 概述

当前系统的交互模型存在几个核心问题：

1. **用户输入过于简单**：新建讨论仅有一个 topic 单行文本框，无法提供足够的讨论背景和约束
2. **固定轮次总结造成干扰**：每轮都生成 section summary，打断了讨论节奏，很多总结是噪音
3. **用户介入流程笨重**：手动暂停 → 输入 → 恢复 的三步操作过于繁琐
4. **右侧面板信息杂乱**：轮次总结面板堆积大量低价值信息，真正重要的决策节点被淹没
5. **缺乏双向对话通道**：用户（制作人）与主策划之间缺少结构化的对话机制

本模块通过引入 **Checkpoint 驱动模型**，将讨论控制权交给主策划（Lead Planner），让其根据讨论进展按需生成不同级别的 Checkpoint，替代固定周期的轮次总结。同时重设计用户交互界面和右侧面板，建立制作人与主策划的双向通道。

```
┌─────────────────────────────────────────────────────────────────┐
│              Checkpoint 驱动交互模型                                │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Layer 1: 讨论简报 (Briefing)                            │   │
│  │  新建讨论时用户提供详细背景、约束、期望产出                     │   │
│  │  替代原有的单行 topic 输入                                  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           ↓                                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Layer 2: Checkpoint 驱动 (Checkpoint-Driven)            │   │
│  │  主策划按需生成三种 Checkpoint：                              │   │
│  │  • 静默继续 (SILENT)：不打扰用户                             │   │
│  │  • 进展通报 (PROGRESS)：非阻塞通知                           │   │
│  │  • 决策请求 (DECISION)：阻塞等待用户回答                      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           ↕                                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Layer 3: 制作人通道 (Producer Channel)                   │   │
│  │  用户随时发消息 → 当前 agent 说完后暂停                       │   │
│  │  主策划消化用户意见 → 决定调整方向或追问                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           ↓                                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Layer 4: 决策日志面板 (Decision Log)                     │   │
│  │  右侧面板从"轮次总结"改为"决策日志"                           │   │
│  │  只记录有意义的节点：共识、决策、里程碑                        │   │
│  │  待决策项置顶显示                                           │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

#### 用户故事

- US-34: 作为制作人，我希望新建讨论时能提供详细的讨论简报（背景、约束、期望产出），以便策划团队有足够上下文
- US-35: 作为制作人，我希望讨论过程中只在关键节点被通知，而不是每轮都收到总结
- US-36: 作为制作人，我希望在核心分歧出现时收到结构化的选择题（带选项），以便快速做出决策
- US-37: 作为制作人，我希望决策回答后主策划公开宣布并继续讨论，确保团队知晓
- US-38: 作为制作人，我希望随时可以在聊天框发送消息，不需要手动暂停流程
- US-39: 作为制作人，我希望右侧面板展示决策日志而非轮次总结，让关键信息一目了然
- US-40: 作为制作人，我希望待决策的 Checkpoint 始终置顶显示，不会被淹没

#### 功能点

| ID | 功能 | 优先级 | 描述 |
|----|------|--------|------|
| F-60 | 讨论简报输入 | P0 | 新建讨论时的多行文本框，支持背景、约束、期望产出三段式输入 |
| F-61 | Checkpoint 生成引擎 | P0 | 主策划在每轮结束后生成 Checkpoint，类型为 SILENT/PROGRESS/DECISION |
| F-62 | 进展通报卡片 | P0 | 非阻塞的里程碑/共识通知，展示在决策日志和聊天流中 |
| F-63 | 决策请求卡片 | P0 | 阻塞式决策卡片，带 2-4 个选项 + 自由输入，必须回答才能继续 |
| F-64 | 决策宣布机制 | P0 | 用户回答后主策划公开宣布决策内容并继续讨论 |
| F-65 | 用户即时发言 | P0 | 用户随时发消息，当前 agent 说完后自动暂停，主策划消化后恢复 |
| F-66 | 决策日志面板 | P0 | 右侧面板重设计，展示决策时间线（共识/决策/里程碑） |
| F-67 | 待决策项置顶 | P0 | 未回答的决策请求在右侧面板和聊天流中置顶/高亮 |
| F-68 | 制作人-主策划通道 | P1 | 制作人与主策划之间的双向结构化对话 |
| F-69 | Checkpoint 历史记录 | P1 | 所有 Checkpoint 持久化存储，支持讨论回溯查看 |

#### 详细设计

##### 1. 讨论简报输入 (F-60)

**现状分析**：

当前 `CreateCurrentDiscussionRequest` 只有 `topic: str` 字段（单行文本），以及可选的 `attachment`（文件附件）。用户无法在创建讨论时提供结构化的讨论背景信息。

**改造方案**：

在新建讨论的创建表单中增加 `briefing` 字段，替代原有的简单 topic 输入。`topic` 字段保留作为简短标题（一句话总结），新增 `briefing` 作为详细的讨论简报。

**API 变更**：

```python
class CreateCurrentDiscussionRequest(BaseModel):
    topic: str = Field(..., min_length=1, description="讨论标题（一句话总结）")
    briefing: str = Field(default="", description="讨论简报：背景、约束、期望产出")
    rounds: int = Field(default=10, ge=1, le=50)
    auto_pause_interval: int = Field(default=0, ge=0, le=50)  # 默认改为 0（禁用固定暂停）
    attachment: AttachmentInfo | None = None
    agents: list[str] = Field(default_factory=list)
    agent_configs: dict = Field(default_factory=dict)
    discussion_style: str = Field(default="")
    password: str = Field(default="123456")
```

**DiscussionState 扩展**：

```python
class DiscussionState(BaseModel):
    # ... 已有字段 ...
    briefing: str = ""  # 讨论简报
```

**前端变更（HomeView.vue）**：

在创建讨论的表单中，将 topic 输入框拆分为两部分：

```
┌──────────────────────────────────────────────┐
│  讨论标题                                       │
│  ┌──────────────────────────────────────────┐ │
│  │ [单行文本框: 简短标题]                     │ │
│  └──────────────────────────────────────────┘ │
│                                                │
│  讨论简报                                       │
│  ┌──────────────────────────────────────────┐ │
│  │ [多行文本框]                               │ │
│  │                                            │ │
│  │ 请提供以下信息：                             │ │
│  │ • 讨论背景和上下文                           │ │
│  │ • 已知的约束条件                             │ │
│  │ • 期望的讨论产出                             │ │
│  │                                            │ │
│  └──────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

**Briefing 注入方式**：

Briefing 内容将作为主策划 system prompt 的一部分注入，使所有 Agent 在讨论全程都能引用制作人提供的背景信息。

```python
# discussion_crew.py 中的 briefing 注入
def _build_briefing_context(self, topic: str, briefing: str, attachment: str | None) -> str:
    """构建包含 briefing 的讨论上下文。"""
    parts = [f"## 讨论主题\n{topic}"]
    if briefing:
        parts.append(f"\n## 制作人简报\n{briefing}")
    if attachment:
        parts.append(f"\n## 附件内容\n{attachment}")
    return "\n".join(parts)
```

##### 2. Checkpoint 驱动模型 (F-61 ~ F-64)

**核心理念**：

取消固定的每轮 section summary + round summary 机制。改为由主策划在每轮讨论结束后自主判断，生成三种 Checkpoint 之一：

| 类型 | 名称 | 行为 | 触发场景 |
|------|------|------|----------|
| `SILENT` | 静默继续 | 讨论正常推进，不产出任何通知 | 常规讨论进展，无重大节点 |
| `PROGRESS` | 进展通报 | 非阻塞通知，前端展示但不中断讨论 | 达成共识、完成里程碑、发现重要分歧 |
| `DECISION` | 决策请求 | 阻塞式等待用户回答后才继续 | 核心分歧无法自行解决、方向不明需制作人定夺 |

**Checkpoint 数据模型**：

```python
# backend/src/models/checkpoint.py (新建)

from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


class CheckpointType(str, Enum):
    SILENT = "silent"
    PROGRESS = "progress"
    DECISION = "decision"


class DecisionOption(BaseModel):
    """决策选项。"""
    id: str                    # 选项 ID (A/B/C/D)
    label: str                 # 选项标题
    description: str           # 选项说明


class Checkpoint(BaseModel):
    """Checkpoint 数据模型。"""
    id: str                    # checkpoint ID (e.g., "cp_001")
    discussion_id: str
    type: CheckpointType
    round_num: int             # 产出此 checkpoint 的轮次
    section_id: str | None = None  # 关联的章节 ID

    # PROGRESS 专用
    title: str = ""            # 进展标题（如"达成战斗系统核心循环共识"）
    summary: str = ""          # 进展摘要
    key_points: list[str] = Field(default_factory=list)

    # DECISION 专用
    question: str = ""         # 需要回答的问题
    context: str = ""          # 决策背景（为何需要制作人决策）
    options: list[DecisionOption] = Field(default_factory=list)  # 2-4 个选项
    allow_free_input: bool = True  # 是否允许自由输入

    # 决策响应
    response: str | None = None          # 用户选择的选项 ID 或自由输入
    response_text: str | None = None     # 用户的补充说明
    responded_at: str | None = None

    # 元数据
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    announced: bool = False    # 决策是否已被主策划公开宣布
```

**Checkpoint 生成 Prompt（主策划）**：

在每轮讨论结束后（替代原有 section summary 的位置），主策划根据当前讨论进展判断 Checkpoint 类型：

```python
# lead_planner.py 新增方法
class LeadPlanner:
    def create_checkpoint_prompt(
        self,
        round_num: int,
        section: "SectionPlan",
        recent_messages: list[str],     # 本轮所有 agent 的发言
        discussion_context: str,         # 已有讨论摘要
        briefing: str,                   # 制作人的 briefing
        pending_decisions: list[str],    # 已有未回答的决策
    ) -> str:
        """创建 Checkpoint 生成 prompt。

        主策划在每轮结束后调用，自主判断是否需要通知制作人。

        输出格式:
        ```checkpoint
        type: SILENT | PROGRESS | DECISION
        # PROGRESS 时:
        title: "进展标题"
        summary: "进展摘要"
        key_points:
          - "关键点 1"
          - "关键点 2"
        # DECISION 时:
        question: "需要制作人回答的问题"
        context: "为何需要此决策的背景说明"
        options:
          - id: A
            label: "选项标题"
            description: "选项说明"
          - id: B
            label: "选项标题"
            description: "选项说明"
        allow_free_input: true
        ```
        """
```

**Checkpoint 处理流程**：

```
每轮讨论结束
  │
  ├─ 调用 _generate_checkpoint(round_num, section, messages)
  │
  ├─ 解析 Checkpoint 类型
  │   │
  │   ├─ SILENT → 不产出任何事件，继续下一轮
  │   │
  │   ├─ PROGRESS → 广播 checkpoint_progress 事件
  │   │   ├─ 前端在决策日志中显示进展卡片
  │   │   ├─ 前端在聊天流中显示非阻塞通知气泡
  │   │   └─ 持久化到讨论记录
  │   │   └─ 继续下一轮（不阻塞）
  │   │
  │   └─ DECISION → 广播 checkpoint_decision 事件
  │       ├─ 前端在决策日志中显示决策卡片（置顶）
  │       ├─ 前端在聊天流中显示阻塞式决策卡片
  │       ├─ 讨论进入 WAITING_DECISION 状态
  │       ├─ 等待用户回答...
  │       │
  │       ├─ [用户回答] → API: POST /{discussion_id}/checkpoint/{cp_id}/respond
  │       │   ├─ 记录用户响应
  │       │   ├─ 广播 checkpoint_responded 事件
  │       │   │
  │       │   └─ 主策划公开宣布决策
  │       │       ├─ 生成宣布消息（作为 lead_planner 的发言出现在聊天流）
  │       │       ├─ 广播宣布消息
  │       │       └─ 讨论恢复为 RUNNING 状态，继续下一轮
  │       │
  │       └─ 持久化到讨论记录
```

**讨论状态扩展**：

```python
class DiscussionStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_DECISION = "waiting_decision"  # [新增] 等待用户决策
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"
```

**决策卡片前端交互（类 Claude 风格）**：

```
┌──────────────────────────────────────────────────────┐
│  ⚡ 需要你的决策                                       │
│                                                       │
│  战斗系统是走技能导向还是走装备导向？                        │
│                                                       │
│  团队讨论中出现了两种截然不同的设计思路，                    │
│  系统策划倾向技能导向，数值策划倾向装备导向。                 │
│  需要制作人定夺核心方向。                                  │
│                                                       │
│  ┌─────────────────────────────────────────────────┐  │
│  │ (A) 技能导向                                      │  │
│  │     以技能搭配为核心，装备提供基础属性               │  │
│  └─────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────┐  │
│  │ (B) 装备导向                                      │  │
│  │     以装备搭配为核心，技能作为辅助手段               │  │
│  └─────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────┐  │
│  │ (C) 混合模式                                      │  │
│  │     技能和装备同等重要，互相增强                     │  │
│  └─────────────────────────────────────────────────┘  │
│                                                       │
│  ┌─────────────────────────────────────────────────┐  │
│  │ 或者输入你的想法...                                 │  │
│  └─────────────────────────────────────────────────┘  │
│                                                       │
│                                    [提交决策]          │
└──────────────────────────────────────────────────────┘
```

**决策响应 API**：

```
POST /api/discussions/{discussion_id}/checkpoint/{checkpoint_id}/respond

Request:
{
  "option_id": "A",           // 选中的选项 ID（可选）
  "free_input": "补充说明...", // 自由输入（可选）
}

Response:
{
  "checkpoint_id": "cp_001",
  "status": "responded",
  "message": "决策已记录，主策划将宣布并继续讨论"
}
```

**决策宣布 Prompt**：

```python
class LeadPlanner:
    def create_decision_announcement_prompt(
        self,
        checkpoint: "Checkpoint",
        user_response: str,
    ) -> str:
        """创建决策宣布 prompt。

        主策划需要：
        1. 公开宣布制作人的决策
        2. 解释决策对后续讨论的影响
        3. 给出下一步讨论方向
        """
```

##### 3. 用户即时发言简化 (F-65)

**现状分析**：

当前用户发言需要：(1) 手动点击暂停按钮 → (2) 在输入框输入消息 → (3) 发送后手动恢复。`UserInputBox` 组件通过 `/api/discussions/{id}/pause` → `/inject` → `/resume` 三步完成。这个流程过于繁琐。

**改造方案**：

简化为单步操作：用户直接在聊天框输入消息发送。系统自动处理暂停和恢复：

```
用户发送消息
  │
  ├─ 前端立即在聊天流显示用户消息（乐观更新）
  │
  ├─ API: POST /{discussion_id}/producer-message
  │   │
  │   ├─ 标记 pending_producer_message = true
  │   ├─ 等待当前 agent 发言完毕（不中断正在说话的 agent）
  │   ├─ 自动暂停讨论
  │   │
  │   ├─ 主策划消化用户消息
  │   │   ├─ 调用 _lead_planner_digest_producer_message()
  │   │   ├─ 输出：(1) 理解确认 (2) 方向调整建议 或 (3) 追问
  │   │   └─ 广播 producer_digest 事件
  │   │
  │   └─ 根据消化结果：
  │       ├─ 直接调整方向 → 自动恢复讨论，主策划引导新方向
  │       └─ 需要追问 → 生成 DECISION checkpoint 追问制作人
  │
  └─ 前端展示主策划的消化结果
```

**API 变更**：

```
POST /api/discussions/{discussion_id}/producer-message

Request:
{
  "content": "用户消息内容"
}

Response:
{
  "status": "received",
  "message": "消息已收到，主策划将在当前发言结束后处理"
}
```

**前端变更（UserInputBox.vue → ProducerInput.vue）**：

将 `UserInputBox` 重命名为 `ProducerInput`（制作人输入），简化交互：

- 移除暂停/恢复按钮
- 输入框始终可用（讨论进行中时）
- 发送消息即触发完整的暂停-消化-恢复流程
- placeholder 改为 "制作人发言..."

**讨论状态扩展**：

```python
# discussion_crew.py 中新增状态
class PendingProducerMessage:
    """制作人待处理消息队列。"""
    messages: list[dict]  # [{content, timestamp}]
    pending: bool = False
```

##### 4. 决策日志面板 (F-66 ~ F-67)

**现状分析**：

当前右侧面板 `RightPanel.vue` 包含两个 Tab：
- **文档大纲** (`DocOutline`): 展示 DocPlan 结构
- **轮次总结** (`StageSummaryPanel`): 展示每轮的 round summary

轮次总结面板问题：每轮都生成总结，大量低价值信息堆积，真正重要的决策和共识被淹没。

**改造方案**：

将"轮次总结"Tab 替换为"决策日志"Tab。决策日志只记录有意义的节点：

```
┌──────────────────────────────────────────────────┐
│  [文档大纲]   [决策日志]                             │
├──────────────────────────────────────────────────┤
│                                                   │
│  ⚠️ 待决策 (置顶)                                  │
│  ┌────────────────────────────────────────────┐   │
│  │ 决策 #3: 付费模式选择                        │   │
│  │ 战斗通行证 vs 抽卡 vs 买断制                 │   │
│  │ 3 个选项 · 等待回答                          │   │
│  │                              [去回答 →]      │   │
│  └────────────────────────────────────────────┘   │
│                                                   │
│  ─── 决策时间线 ───                                │
│                                                   │
│  ✅ 决策 #2: 战斗系统方向        轮次 8            │
│     → 选择 A: 技能导向                             │
│     "以技能搭配为核心..."                           │
│                                                   │
│  📌 共识: 核心战斗循环确认       轮次 5            │
│     "技能释放→冷却→资源管理→连招"                   │
│                                                   │
│  🎯 里程碑: 系统概述完成        轮次 3             │
│     "系统策划和数值策划达成一致..."                  │
│                                                   │
│  ✅ 决策 #1: 战斗节奏偏好        轮次 2            │
│     → 选择 B: 中速回合制                           │
│     "制作人倾向于有策略深度的..."                    │
│                                                   │
└──────────────────────────────────────────────────┘
```

**决策日志数据模型**：

```typescript
// frontend/src/types/index.ts 新增

type DecisionLogEntryType = 'decision' | 'consensus' | 'milestone';

interface DecisionLogEntry {
  id: string;
  type: DecisionLogEntryType;
  checkpoint_id: string;       // 关联的 Checkpoint ID
  round_num: number;           // 产出轮次
  title: string;               // 标题
  summary: string;             // 摘要
  // decision 特有
  question?: string;           // 决策问题
  options?: DecisionOption[];  // 选项列表
  response?: string;           // 用户选择
  response_text?: string;      // 补充说明
  announced?: boolean;         // 是否已宣布
  // 元数据
  created_at: string;
  responded_at?: string;
}
```

**前端组件变更**：

| 组件 | 变更类型 | 说明 |
|------|----------|------|
| `RightPanel.vue` | 改造 | "轮次总结" Tab 替换为 "决策日志" Tab |
| `DecisionLogPanel.vue` | 新建 | 决策日志面板组件 |
| `DecisionCard.vue` | 新建 | 聊天流中的决策请求卡片（类 Claude 交互风格） |
| `ProgressNotice.vue` | 新建 | 聊天流中的进展通报气泡 |
| `ProducerInput.vue` | 新建 | 制作人输入框（替代 UserInputBox） |
| `StageSummaryPanel.vue` | 保留 | 保留组件但从 RightPanel 默认 Tab 移除，可从设置中恢复 |

##### 5. 制作人通道 (F-68)

**概述**：

建立制作人（用户）与主策划之间的双向对话通道。不同于普通的观众发言（被所有 Agent 看到），制作人通道是一个**私密通道**，仅主策划可见。主策划消化后决定哪些信息需要公开给团队。

**通道消息类型**：

| 方向 | 消息类型 | 示例 |
|------|----------|------|
| 制作人 → 主策划 | 指令 | "这个方向不对，请转向轻量化设计" |
| 制作人 → 主策划 | 反馈 | "数值策划的观点很好，请深入展开" |
| 制作人 → 主策划 | 追问 | "为什么不考虑 PvP 模式？" |
| 主策划 → 制作人 | 确认 | "收到，将调整讨论方向" |
| 主策划 → 制作人 | 追问 | "轻量化设计的边界是什么？" |
| 主策划 → 制作人 | 通报 | "团队已达成初步共识，但有一点分歧..." |

**通道实现方式**：

制作人通道复用 `ProducerInput` 组件和 `producer-message` API。主策划的回复通过 Checkpoint（PROGRESS 或 DECISION）传达。

```
制作人消息 ─→ producer-message API ─→ 主策划消化
                                        │
                                        ├→ 直接调整 → PROGRESS checkpoint + 继续讨论
                                        ├→ 需确认   → DECISION checkpoint（追问制作人）
                                        └→ 已理解   → SILENT（直接融入后续讨论）
```

##### 6. run_document_centric 改造

**与 2.9 的关系**：

本模块的 Checkpoint 驱动模型需要与 2.9 中的议题驱动、干预消化等机制协调。核心变更点：

1. **替代 section summary**：原有的 `_lead_planner_section_summary` 调用替换为 `_generate_checkpoint`
2. **保留 DocWriter 更新**：Checkpoint 生成不影响 DocWriter 的 section 内容更新机制
3. **融合干预消化**：用户即时发言的消化流程与 2.9 的 `_lead_planner_digest_intervention` 合并为统一的 `_lead_planner_digest_producer_message`

**改造后主循环伪代码（增量变更）**：

```python
def run_document_centric(self, topic, max_rounds, attachment, auto_pause_interval,
                          briefing=""):
    self._init_discussion(topic)

    # 构建完整上下文（含 briefing）
    context = self._build_briefing_context(topic, briefing, attachment)

    # Phase 0a: 生成文档计划（已有）
    doc_plan = self._generate_doc_plan(topic, context)
    self._doc_writer.create_skeleton(doc_plan)
    self._broadcast_doc_plan_event(doc_plan)

    # Phase 0b: 生成初始议程（来自 2.9）
    agenda = self._generate_initial_agenda(topic, context)
    self._broadcast_agenda_event("agenda_init", agenda.to_dict())

    # Phase 1-N: 逐章节讨论
    for round_num in range(1, max_rounds + 1):
        file_plan, section = self._pick_next_section(doc_plan)
        if file_plan is None:
            break

        opening = self._lead_planner_section_opening(section, ...)
        round_responses = self._run_agents_parallel_sync(...)

        # [变更] 替代 section summary → 生成 Checkpoint
        checkpoint = self._generate_checkpoint(
            round_num, section, round_responses,
            briefing=briefing,
        )

        if checkpoint.type == CheckpointType.SILENT:
            # 静默继续，不做任何通知
            pass
        elif checkpoint.type == CheckpointType.PROGRESS:
            # 非阻塞进展通报
            self._broadcast_checkpoint_event(checkpoint)
            self._persist_checkpoint(checkpoint)
        elif checkpoint.type == CheckpointType.DECISION:
            # 阻塞式决策请求
            self._broadcast_checkpoint_event(checkpoint)
            self._persist_checkpoint(checkpoint)
            self._set_discussion_status(DiscussionStatus.WAITING_DECISION)

            # 等待用户回答
            response = self._wait_for_decision_response(checkpoint.id)
            checkpoint.response = response.option_id
            checkpoint.response_text = response.free_input
            checkpoint.responded_at = datetime.utcnow().isoformat()

            # 主策划宣布决策
            announcement = self._lead_planner_announce_decision(checkpoint)
            self._broadcast_announcement(announcement)
            checkpoint.announced = True
            self._persist_checkpoint(checkpoint)

            self._set_discussion_status(DiscussionStatus.RUNNING)

        # DocWriter 更新章节内容（保留已有机制）
        self._doc_writer.update_section(...)

        # [来自 2.9] 解析议题/结构变更指令
        self._process_agenda_directives(checkpoint, section)
        self._process_doc_restructure(checkpoint, doc_plan, section)

        # 检查制作人消息（替代原有的 pause-inject-resume 机制）
        producer_messages = self._check_producer_messages()
        if producer_messages:
            # 主策划消化制作人消息
            digest = self._lead_planner_digest_producer_message(
                producer_messages, section, doc_plan
            )
            self._broadcast_event("producer_digest", digest)

            # 根据消化结果：可能生成追加的 DECISION checkpoint
            if digest.needs_decision:
                follow_up_cp = self._generate_follow_up_decision(digest)
                self._broadcast_checkpoint_event(follow_up_cp)
                # ... 等待回答流程同上 ...

        # 广播更新后的状态
        self._broadcast_doc_plan_event(doc_plan)

    # [来自 2.9] Phase Final: 整体审视
    self._lead_planner_holistic_review(doc_plan, agenda)
    self._finalize_discussion(doc_plan, agenda)
```

#### WebSocket 新增事件

```typescript
// Checkpoint 进展通报
{
  type: "checkpoint",
  data: {
    event_type: "progress",
    checkpoint: {
      id: string,
      discussion_id: string,
      type: "progress",
      round_num: number,
      section_id: string | null,
      title: string,
      summary: string,
      key_points: string[],
      created_at: string
    }
  }
}

// Checkpoint 决策请求
{
  type: "checkpoint",
  data: {
    event_type: "decision_request",
    checkpoint: {
      id: string,
      discussion_id: string,
      type: "decision",
      round_num: number,
      section_id: string | null,
      question: string,
      context: string,
      options: Array<{id: string, label: string, description: string}>,
      allow_free_input: boolean,
      created_at: string
    }
  }
}

// Checkpoint 决策响应（用户已回答）
{
  type: "checkpoint",
  data: {
    event_type: "decision_responded",
    checkpoint_id: string,
    response: string | null,      // 选项 ID
    response_text: string | null, // 自由输入
    responded_at: string
  }
}

// 决策宣布（主策划公开宣布决策）
{
  type: "checkpoint",
  data: {
    event_type: "decision_announced",
    checkpoint_id: string,
    announcement: string          // 主策划的宣布内容
  }
}

// 讨论状态变更为 waiting_decision
{
  type: "status",
  data: {
    discussion_id: string,
    status: "waiting_decision",
    checkpoint_id: string         // 等待回答的 checkpoint
  }
}

// 制作人消息消化结果
{
  type: "producer_digest",
  data: {
    discussion_id: string,
    digest_summary: string,
    action: "adjust" | "follow_up_decision" | "acknowledged",
    guidance: string              // 后续讨论引导
  }
}
```

#### API 接口变更

##### 获取讨论的 Checkpoint 列表

```
GET /api/discussions/{discussion_id}/checkpoints

Response:
{
  "checkpoints": [
    {
      "id": "cp_003",
      "type": "decision",
      "round_num": 8,
      "question": "付费模式选择",
      "options": [...],
      "response": null,
      "created_at": "..."
    },
    {
      "id": "cp_002",
      "type": "progress",
      "round_num": 5,
      "title": "核心战斗循环确认",
      "summary": "...",
      "created_at": "..."
    }
  ]
}
```

##### 回答决策 Checkpoint

```
POST /api/discussions/{discussion_id}/checkpoint/{checkpoint_id}/respond

Request:
{
  "option_id": "A",
  "free_input": "补充说明..."
}

Response:
{
  "checkpoint_id": "cp_003",
  "status": "responded",
  "message": "决策已记录"
}
```

##### 发送制作人消息

```
POST /api/discussions/{discussion_id}/producer-message

Request:
{
  "content": "制作人消息内容"
}

Response:
{
  "status": "received",
  "message": "消息已收到，等待主策划处理"
}
```

##### 获取决策日志

```
GET /api/discussions/{discussion_id}/decision-log

Response:
{
  "entries": [
    {
      "id": "dl_001",
      "type": "decision",
      "checkpoint_id": "cp_003",
      "round_num": 8,
      "title": "付费模式选择",
      "question": "...",
      "response": "A",
      "response_text": "...",
      "announced": true,
      "created_at": "..."
    },
    {
      "id": "dl_002",
      "type": "consensus",
      "checkpoint_id": "cp_002",
      "round_num": 5,
      "title": "核心战斗循环确认",
      "summary": "...",
      "created_at": "..."
    }
  ],
  "pending_decisions": [...]  // 待回答的决策（置顶）
}
```

#### 代码改动范围

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `backend/src/models/checkpoint.py` | 新建 | Checkpoint/DecisionOption/CheckpointType 数据模型 |
| `backend/src/api/routes/discussion.py` | 扩展 | CreateCurrentDiscussionRequest 新增 briefing 字段; DiscussionState 新增 briefing; DiscussionStatus 新增 WAITING_DECISION |
| `backend/src/api/routes/checkpoint.py` | 新建 | Checkpoint CRUD API: 获取列表、响应决策、获取决策日志 |
| `backend/src/api/routes/producer.py` | 新建 | 制作人消息 API: POST producer-message |
| `backend/src/agents/lead_planner.py` | 扩展 | 新增 create_checkpoint_prompt、create_decision_announcement_prompt、create_producer_digest_prompt |
| `backend/src/crew/discussion_crew.py` | 核心改动 | _generate_checkpoint 替代 section summary; _wait_for_decision_response 阻塞等待; _lead_planner_announce_decision; _check_producer_messages; _lead_planner_digest_producer_message |
| `backend/src/api/websocket/events.py` | 扩展 | 新增 checkpoint_progress/checkpoint_decision/checkpoint_responded/decision_announced/producer_digest 事件 |
| `backend/src/memory/discussion_memory.py` | 扩展 | Discussion 模型新增 checkpoints 字段; 持久化 Checkpoint 数据 |
| `frontend/src/types/index.ts` | 扩展 | Checkpoint/DecisionOption/DecisionLogEntry/CheckpointType 类型定义 |
| `frontend/src/views/HomeView.vue` | 改造 | 新建讨论表单增加 briefing 多行文本框 |
| `frontend/src/components/discussion/RightPanel.vue` | 改造 | "轮次总结" Tab 替换为 "决策日志" Tab |
| `frontend/src/components/discussion/DecisionLogPanel.vue` | 新建 | 决策日志面板 |
| `frontend/src/components/discussion/DecisionCard.vue` | 新建 | 聊天流中的决策卡片组件 |
| `frontend/src/components/discussion/ProgressNotice.vue` | 新建 | 聊天流中的进展通报组件 |
| `frontend/src/components/discussion/ProducerInput.vue` | 新建 | 制作人输入框（替代 UserInputBox） |
| `frontend/src/composables/useDiscussion.ts` | 扩展 | 处理 checkpoint WebSocket 事件; 决策响应 API 调用; 制作人消息发送 |
| `frontend/src/stores/discussion.ts` | 扩展 | checkpoints/decisionLog/pendingDecisions 状态管理 |
| `frontend/src/views/DiscussionView.vue` | 改造 | 集成 DecisionCard/ProgressNotice/ProducerInput; 移除旧的暂停/恢复 UI |
| `frontend/src/components/chat/ChatContainer.vue` | 扩展 | 支持渲染 DecisionCard 和 ProgressNotice 消息类型 |

#### 与现有模块的兼容策略

| 现有模块 | 兼容方案 |
|----------|----------|
| 轮次总结 (round_summaries) | 保留数据结构但不再主动生成，由 PROGRESS checkpoint 替代 |
| section summary | 被 checkpoint 生成替代，但 DocWriter 的 section 内容更新机制保持不变 |
| pause/inject/resume API | 保留但标记为 deprecated，新功能使用 producer-message API |
| auto_pause_interval | 默认值从 5 改为 0（禁用），由 DECISION checkpoint 替代固定暂停 |
| StageSummaryPanel | 组件保留但从 RightPanel 默认 Tab 移除 |
| InterventionDigestCard | 与 producer_digest 事件合并，复用展示逻辑 |
| HolisticReviewCard | 保留，整体审视可通过 PROGRESS checkpoint 展示 |

#### 验收标准

- [ ] AC-56: 新建讨论表单包含 topic（标题）和 briefing（多行简报）两个输入区域
- [ ] AC-57: briefing 内容正确注入到主策划的 system prompt 和讨论上下文中
- [ ] AC-58: 每轮讨论结束后主策划生成 Checkpoint（SILENT/PROGRESS/DECISION 三选一）
- [ ] AC-59: SILENT checkpoint 不产生任何前端通知或事件
- [ ] AC-60: PROGRESS checkpoint 在决策日志面板和聊天流中正确展示为非阻塞通知
- [ ] AC-61: DECISION checkpoint 阻塞讨论，前端展示决策卡片（2-4 个选项 + 自由输入）
- [ ] AC-62: 决策卡片回答后主策划公开宣布决策内容，讨论自动恢复
- [ ] AC-63: 用户可随时通过制作人输入框发送消息，无需手动暂停/恢复
- [ ] AC-64: 制作人消息发送后，当前 agent 发言完毕后自动暂停，主策划优先消化
- [ ] AC-65: 右侧面板的"轮次总结" Tab 替换为"决策日志" Tab
- [ ] AC-66: 决策日志按时间线展示所有 PROGRESS 和 DECISION 类型的 Checkpoint
- [ ] AC-67: 未回答的 DECISION checkpoint 在决策日志面板中置顶显示
- [ ] AC-68: 讨论状态 WAITING_DECISION 正确广播并在前端 UI 中反映
- [ ] AC-69: Checkpoint 数据持久化到讨论记录，支持讨论回溯查看
- [ ] AC-70: 制作人通道消息仅主策划消化处理，不直接暴露给其他 Agent
- [ ] AC-71: 兼容：旧的 pause/inject/resume API 仍然可用（deprecated）

#### 暂不实现

- Checkpoint 类型的自动学习（根据用户行为调整 SILENT/PROGRESS/DECISION 的阈值）
- 决策投票功能（多个用户对同一决策投票）
- 制作人消息的优先级标记（紧急/普通）
- Checkpoint 模板（预定义的常见决策类型）
- 决策回溯/撤销（修改已做出的决策）
- 移动端适配的决策卡片交互

## 3. 技术约束

### 3.1 两层 Agent 架构

本项目存在**两层 Agent**，职责完全不同，必须区分：

| 层 | 位置 | 用途 | 技术 |
|---|------|------|------|
| 开发层 | `.claude/agents/` | 辅助开发本项目（规格生成、计划生成、代码审核） | Claude Code |
| 业务层 | `backend/src/agents/` | 策划团队核心功能（系统策划、数值策划等） | CrewAI |

```
┌─────────────────────────────────────────────────────────────┐
│  开发层 (.claude/agents/)                                   │
│  ├── spec-generator.md    # 生成本文档                      │
│  ├── plan-generator.md    # 生成实施计划                    │
│  ├── code-reviewer.md     # 审核代码                        │
│  └── auto-developer.md    # 自动开发                        │
│                                                             │
│  → 这些是 Claude Code 的 Agent，用于开发本项目              │
└─────────────────────────────────────────────────────────────┘
                            ↓ 开发产出 ↓
┌─────────────────────────────────────────────────────────────┐
│  业务层 (backend/src/agents/)                               │
│  ├── system_designer.py   # 系统策划角色                    │
│  ├── number_designer.py   # 数值策划角色                    │
│  ├── player_advocate.py   # 玩家代言人角色                  │
│  ├── visual_concept.py    # 视觉概念角色 (新增)             │
│  └── ...                                                    │
│                                                             │
│  → 这些是 CrewAI 的 Agent，是本项目的核心功能               │
└─────────────────────────────────────────────────────────────┘
```

**注意**：
- 开发层 Agent 只在开发阶段使用，不随产品部署
- 业务层 Agent 是产品的一部分，随后端部署
- 两层 Agent 的 prompt 设计原则不同（开发层关注代码质量，业务层关注策划专业性）

### 3.2 技术栈

**后端:**
| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 主语言 |
| CrewAI | latest | Agent 编排 |
| FastAPI | latest | Web 框架 |
| SQLite | - | 结构化存储 |
| Chroma | latest | 向量数据库 |
| Langfuse SDK | latest | 监控追踪 |
| httpx/aiohttp | latest | 异步 HTTP 客户端（图像服务调用） |
| python-docx | latest | Word 文档解析 |
| PyMuPDF | latest | PDF 文档解析 |

**前端:**
| 技术 | 版本 | 用途 |
|------|------|------|
| Vite | latest | 构建工具 |
| Vue 3 | latest | UI 框架 |
| TypeScript | latest | 类型安全 |
| TailwindCSS | latest | 样式 |
| WebSocket | - | 实时通信 |

### 3.3 性能要求

| 指标 | 要求 |
|------|------|
| 首次响应时间 | < 3s |
| WebSocket 延迟 | < 500ms |
| 单次讨论 Agent 数 | 支持 5+ |
| 并发讨论数 | 支持 3+ |
| 历史记录存储 | 最近 100 条讨论，超出自动归档到 `archive/` |
| 图像生成超时 | 同步模式 < 30s，异步模式 < 120s |
| GDD 解析时间 | < 30s（10MB 文件） |
| 单模块讨论时间 | < 10min（5 轮讨论） |

### 3.4 兼容性

- 浏览器：Chrome 90+, Firefox 88+, Safari 14+
- 操作系统：macOS, Linux, Windows
- Python 版本：3.11+
- Node.js 版本：18+

### 3.5 数据存储

```
data/
├── projects/{project_id}/
│   ├── discussions/          # 讨论记录
│   ├── drafts/               # 策划案版本
│   ├── images/               # 生成的图片
│   │   ├── img_001.png
│   │   └── metadata.json
│   ├── design/               # 策划案输出 (新增)
│   │   ├── index.md          # 项目策划案索引
│   │   ├── combat-system.md  # 模块策划案
│   │   └── assets/           # 策划案配图
│   ├── gdd/                  # GDD 文档 (新增)
│   │   ├── original/         # 原始上传文件
│   │   └── parsed/           # 解析后的结构化数据
│   ├── checkpoints/          # 讨论断点 (新增)
│   ├── decisions.md          # 决策记录
│   └── config.yaml           # 项目配置
└── knowledge/                # 全局知识库
    ├── templates/            # 模板
    └── references/           # 参考资料
```

## 4. 参考

### 4.1 竞品/参考项目分析

| 项目 | 参考点 | 地址 |
|------|--------|------|
| CrewAI | Agent 编排核心框架 | github.com/crewAIInc/crewAI |
| ChatDev | 前端可视化、多 Agent 对话展示 | github.com/OpenBMB/ChatDev |
| MetaGPT | 角色设计、结构化输出 | github.com/geekan/MetaGPT |
| Langfuse | Agent 监控追踪 | github.com/langfuse/langfuse |
| OpenClaw | 记忆系统设计（内部参考） | - |

### 4.2 设计参考

**前端 UI 参考:**
- ChatDev 的对话可视化界面
- 类聊天应用的消息布局
- Agent 状态卡片设计

**交互参考:**
- 实时消息流推送
- 讨论回放时间线
- 人工介入输入框

### 4.3 图像生成服务参考

| 服务 | API 文档 | 备注 |
|------|----------|------|
| kie.ai | 内部文档 | 通用市场模型 |
| wenwen-ai | 内部文档 | Midjourney 集成 |
| nanobanana/Evolink | 内部文档 | 多功能图像服务 |
| OpenAI DALL-E | platform.openai.com/docs | 标准参考实现 |

## 5. 里程碑规划

### Phase 1: MVP (核心功能)
- 基础 Agent 角色定义 (F-01 ~ F-05)
- 多轮讨论流程 (F-07 ~ F-10)
- 终端输出查看
- Langfuse 接入 (F-23)

### Phase 2: 可视化
- 前端框架搭建
- 实时对话展示 (F-13, F-14)
- Agent 状态面板 (F-15)
- 讨论历史回放 (F-16)

### Phase 3: 记忆系统
- 项目级记忆存储 (F-18)
- 语义检索 (F-21)
- 设计决策追踪 (F-22)
- 知识库管理 (F-20)

### Phase 4: 图像生成系统
- 视觉概念 Agent (F-30)
- Prompt 工程模块 (F-31)
- 多后端图像服务集成 (F-32)
- 风格模板系统 (F-33)
- 主动请求配图 (F-34)
- 图像存储管理 (F-36)
- 异步图像生成 (F-37)

### Phase 5: 项目级策划讨论 (新增)
- GDD 上传与解析 (F-38, F-39)
- 模块自动识别 (F-40)
- 批量模块选择 (F-41)
- 依次自动讨论 (F-42)
- 讨论断点恢复 (F-43)
- 项目级记忆 (F-44)
- 策划案生成 (F-45)
- 策划案汇总 (F-46)
- 讨论进度追踪 (F-47)

### Phase 6: 讨论流程动态化 (新增)
- 议题自动生成与生命周期管理 (F-48, F-49)
- 议题-章节多对多映射 (F-50)
- 文档结构动态重组：拆分/合并/新增 (F-51, F-52, F-53)
- DocWriter 动态追加 (F-54)
- 干预影响评估 (F-55)
- 章节回溯修订 (F-56)
- 文档变更广播 (F-57)
- 干预后主策划优先消化 (F-58)
- 讨论完成前整体审视 (F-59)

### Phase 8: Checkpoint 驱动交互重设计 (新增)
- 讨论简报输入 (F-60)
- Checkpoint 生成引擎 (F-61)
- 进展通报卡片 (F-62)
- 决策请求卡片 (F-63)
- 决策宣布机制 (F-64)
- 用户即时发言简化 (F-65)
- 决策日志面板 (F-66)
- 待决策项置顶 (F-67)
- 制作人-主策划通道 (F-68)
- Checkpoint 历史记录 (F-69)

### Phase 9: 高级功能
- 人工介入节点 (F-11)
- 自动配图 (F-35)
- 多项目并行
- 成本控制

---

## 附录

### A. 术语表

| 术语 | 定义 |
|------|------|
| Agent | 具有特定角色和能力的 AI 代理 |
| Crew | CrewAI 中的 Agent 团队 |
| Task | Agent 需要完成的具体任务 |
| Memory | Agent 的记忆能力 |
| Tool | Agent 可调用的工具 |
| 视觉概念 Agent | 负责图像生成的 Agent，可作为团队成员或服务 |
| Prompt 工程 | 将自然语言描述转化为图像生成 prompt 的过程 |
| 风格模板 | 预定义的图像生成参数集合 |
| GDD | Game Design Document，游戏设计文档 |
| 项目级记忆 | 跨模块共享的上下文记忆，保持讨论一致性 |
| 断点恢复 | 中断后从上次位置继续讨论的能力 |
| 策划案 | 纯策划内容的设计文档，不含技术规格 |
| 议题驱动 | 讨论流程由议程(Agenda)中的议题项驱动推进 |
| 文档重组 | 讨论过程中对 DocPlan 结构的动态调整（拆分/合并/新增） |
| 干预回溯 | 观众注入消息后，评估影响范围并回溯修订已完成章节 |
| 影响评估 | 主策划对观众干预的影响范围进行分析的环节 |
| 干预消化 | 观众干预后主策划先独立思考消化，提取关键诉求并规划处理方案 |
| 整体审视 | 所有章节完成后主策划对全部策划案的全局审视，检查一致性和完整性 |
| section marker | DocWriter 在 .md 文件中用 `<!-- section:sN -->` 标记的章节边界 |
| Checkpoint | 主策划在讨论过程中按需生成的控制节点，分为 SILENT/PROGRESS/DECISION 三种类型 |
| 静默继续 (SILENT) | Checkpoint 类型之一，讨论正常推进，不产出任何通知 |
| 进展通报 (PROGRESS) | Checkpoint 类型之一，非阻塞通知，用于告知制作人达成共识或里程碑 |
| 决策请求 (DECISION) | Checkpoint 类型之一，阻塞式等待制作人回答，用于核心分歧或方向不明时 |
| 决策卡片 | DECISION Checkpoint 在前端的展现形式，带 2-4 个选项和自由输入，类 Claude 交互风格 |
| 决策日志 | 右侧面板中仅记录有意义节点的时间线，替代原有的轮次总结 |
| 制作人 (Producer) | 使用系统的用户角色，拥有最终决策权，通过制作人通道与主策划交互 |
| 制作人通道 | 制作人与主策划之间的双向对话通道，消息仅主策划可见 |
| 讨论简报 (Briefing) | 新建讨论时用户提供的详细背景信息，包含背景、约束、期望产出 |
| 决策宣布 | 用户做出决策后，主策划公开宣布决策内容并指导后续讨论方向 |

### B. 文档版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0 | 2026-02-04 | 初始版本，基于 README.md 生成 |
| 1.1 | 2026-02-04 | 补充"两层 Agent 架构"说明，修正存储上限约束 |
| 1.2 | 2026-02-05 | 新增图像生成系统模块 (2.7)，更新里程碑规划 |
| 1.3 | 2026-02-05 | 新增项目级策划讨论模块 (2.8)，支持 GDD 上传、批量模块讨论、策划案生成 |
| 1.4 | 2026-02-10 | 新增讨论流程动态化改造模块 (2.9)，议题驱动、文档动态重组、干预回溯审视 |
| 1.5 | 2026-02-10 | 补充干预后主策划优先消化机制 (F-58)、讨论完成前整体审视 (F-59)，新增 AC-51~AC-55 |
| 2.0 | 2026-02-11 | 新增 Checkpoint 驱动交互重设计模块 (2.10)：讨论简报输入 (F-60)、Checkpoint 三级模型 (F-61~F-64)、用户即时发言简化 (F-65)、决策日志面板 (F-66~F-67)、制作人通道 (F-68~F-69)，新增 AC-56~AC-71 |
