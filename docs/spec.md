# 游戏策划 AI 团队 规格文档

> **版本**: 1.3
> **创建时间**: 2026-02-04
> **更新时间**: 2026-02-05

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

### Phase 6: 高级功能
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

### B. 文档版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0 | 2026-02-04 | 初始版本，基于 README.md 生成 |
| 1.1 | 2026-02-04 | 补充"两层 Agent 架构"说明，修正存储上限约束 |
| 1.2 | 2026-02-05 | 新增图像生成系统模块 (2.7)，更新里程碑规划 |
| 1.3 | 2026-02-05 | 新增项目级策划讨论模块 (2.8)，支持 GDD 上传、批量模块讨论、策划案生成 |
