# Plan: 讨论流程动态化改造

> **模块**: dynamic-discussion
> **优先级**: P0
> **对应 Spec**: docs/spec.md#2.9 讨论流程动态化改造 (F-48 ~ F-59)

## 目标

将议题驱动、文档结构动态重组、干预回溯三大能力融入 `run_document_centric` 主循环，使讨论过程具备"自适应"特性。具体包括：

1. 议题(Agenda)真正接入讨论主循环，驱动讨论推进
2. DocPlan 支持运行时结构变更（拆分/合并/新增章节和文件）
3. 观众干预后由主策划优先消化，并支持回溯已完成章节
4. 讨论完成前主策划执行整体审视，确认策划案完整性

## 前置依赖

- plan-discussion-v2-global (Batch 10) — 全局讨论状态管理
- plan-discussion-v2-parallel (Batch 11) — 并行发言机制
- 当前 `run_document_centric` 主循环已实现（已有）

## 技术方案

### 架构设计

```
改造前 run_document_centric:
  Phase 0: _generate_doc_plan → create_skeleton
  Phase 1-N: pick_section → opening → agents_discuss → summary → doc_writer.update
  End: save & cleanup

改造后 run_document_centric:
  Phase 0a: _generate_doc_plan → create_skeleton              (已有)
  Phase 0b: _generate_initial_agenda → establish_mapping       (新增)
  Phase 1-N:
    pick_section → opening → agents_discuss → summary          (已有)
    → _process_agenda_directives(summary)                      (新增)
    → _process_doc_restructure(summary, doc_plan)              (新增)
    → doc_writer.update                                        (已有)
    → 干预检查:
        → _lead_planner_digest_intervention(injected)          (新增)
        → _assess_intervention_impact(digest, doc_plan)        (新增)
        → _execute_assessment_actions(assessment, doc_plan)    (新增)
        → _lead_planner_post_intervention_guidance(digest)     (新增)
  Phase Final: _lead_planner_holistic_review(doc_plan, agenda) (新增)
  End: save & cleanup                                          (已有)
```

### 核心改动文件

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `backend/src/models/agenda.py` | 扩展 | AgendaItem 新增 `related_sections`、`priority`、`source` |
| `backend/src/models/doc_plan.py` | 扩展 | SectionPlan 新增字段; DocPlan 新增结构变更方法 |
| `backend/src/agents/lead_planner.py` | 扩展 | 新增消化/评估/审视 prompt |
| `backend/src/agents/doc_writer.py` | 扩展 | 新增动态文件操作方法 |
| `backend/src/crew/discussion_crew.py` | 核心改动 | 主循环插入新步骤 |
| `backend/src/api/routes/intervention.py` | 扩展 | 新增议题/结构变更 API |
| `backend/src/api/websocket/events.py` | 扩展 | 新增事件类型 |
| `frontend/src/composables/useDiscussion.ts` | 扩展 | 处理新 WebSocket 事件 |
| `frontend/src/types/index.ts` | 扩展 | 新增类型定义 |
| `frontend/src/components/discussion/AgendaPanel.vue` | 扩展 | 展示议题-章节映射 |

## 任务清单

### Layer 1: 议题驱动

---

### Task DYN-1.1: 扩展 AgendaItem 和 SectionPlan 数据模型

**执行**:
- 修改 `backend/src/models/agenda.py` 中的 `AgendaItem`:
  - 新增 `related_sections: list[str] = Field(default_factory=list)` — 关联的 section IDs
  - 新增 `priority: int = Field(default=0)` — -1=low, 0=normal, 1=high
  - 新增 `source: str = Field(default="initial")` — "initial" | "discovered" | "intervention"
  - 更新 `to_dict()` 方法序列化新字段
- 修改 `backend/src/models/doc_plan.py` 中的 `SectionPlan`:
  - 新增 `related_agenda_items: list[str] = field(default_factory=list)` — 关联的 agenda item IDs
  - 新增 `revision_count: int = 0` — 被回溯修订的次数
  - 新增 `reopened_reason: str | None = None` — 重开原因
- 更新 `DocPlan.to_dict()` 和 `DocPlan.from_dict()` 以包含新字段

**验证**:
- `cd backend && python -c "from src.models.agenda import AgendaItem; a = AgendaItem(title='test'); assert hasattr(a, 'related_sections') and hasattr(a, 'priority') and hasattr(a, 'source'); print('OK')"` → exit_code == 0
- `cd backend && python -c "from src.models.doc_plan import SectionPlan; s = SectionPlan(id='s1', title='test', description='d'); assert hasattr(s, 'related_agenda_items') and hasattr(s, 'revision_count'); print('OK')"` → exit_code == 0

**输出文件**:
- `backend/src/models/agenda.py` (更新)
- `backend/src/models/doc_plan.py` (更新)

---

### Task DYN-1.2: 实现议题初始生成与讨论主循环接入

**执行**:
- 在 `backend/src/crew/discussion_crew.py` 中新增 `_generate_initial_agenda(topic, attachment)` 方法:
  - 调用 `self._lead_planner.create_agenda_prompt(topic, attachment)` 获取 prompt
  - 调用 LLM 生成议程
  - 解析输出为 `AgendaItem` 列表
  - 调用 `self._init_agenda(items_data)` 初始化 Agenda
  - 广播 `agenda_init` 事件
- 在 `run_document_centric` 的 Phase 0 中，在 `create_skeleton` 之后插入:
  ```python
  # Phase 0b: 生成初始议程
  agenda = self._generate_initial_agenda(topic, attachment)
  ```
- 新增 `_establish_agenda_section_mapping(agenda, doc_plan)` 方法:
  - 根据议题标题与章节标题的关键词匹配建立初始映射
  - 设置 `AgendaItem.related_sections` 和 `SectionPlan.related_agenda_items`
  - 广播 `agenda_mapping_update` 事件

**验证**:
- `cd backend && python -c "from src.crew.discussion_crew import DiscussionCrew; assert hasattr(DiscussionCrew, '_generate_initial_agenda'); print('OK')"` → exit_code == 0

**输出文件**:
- `backend/src/crew/discussion_crew.py` (更新)

---

### Task DYN-1.3: 实现议题管理指令解析

**执行**:
- 在 `backend/src/crew/discussion_crew.py` 中新增 `_process_agenda_directives(summary, section)` 方法:
  - 使用正则解析 summary 中的 ` ```agenda_update ``` ` 代码块
  - 支持三种指令:
    - `complete: <agenda_item_id>` — 标记议题完结
    - `add: [新议题标题] - 描述` — 新增议题（source="discovered"）
    - `priority: <agenda_item_id> high|low` — 调整优先级
  - 对每条指令执行操作并广播对应 agenda 事件
- 修改 `backend/src/agents/lead_planner.py` 的 `create_section_summary_prompt`:
  - 在 prompt 末尾追加议题管理指令格式说明
  - 提示主策划在 summary 中输出议题状态更新

**指令解析格式**:
```python
AGENDA_DIRECTIVE_PATTERN = re.compile(
    r"```agenda_update\s*\n(.*?)```", re.DOTALL
)
COMPLETE_PATTERN = re.compile(r"complete:\s*(.+)")
ADD_PATTERN = re.compile(r"add:\s*\[(.+?)\]\s*-\s*(.+)")
PRIORITY_PATTERN = re.compile(r"priority:\s*(\S+)\s+(high|low)")
```

**验证**:
- `cd backend && python -c "
from src.crew.discussion_crew import DiscussionCrew
assert hasattr(DiscussionCrew, '_process_agenda_directives')
print('OK')
"` → exit_code == 0

**输出文件**:
- `backend/src/crew/discussion_crew.py` (更新)
- `backend/src/agents/lead_planner.py` (更新)

---

### Task DYN-1.4: 新增 Agenda WebSocket 映射事件和前端处理

**执行**:
- 在 `backend/src/api/websocket/events.py` 中:
  - 在 `AgendaEventType` 枚举中新增 `MAPPING_UPDATE = "mapping_update"`
  - 在 `AgendaEventData` 中新增 `mappings` 字段（可选）
- 在 `frontend/src/composables/useDiscussion.ts` 中:
  - 处理 `agenda` 事件的 `mapping_update` 子类型
  - 在本地 agenda 状态中更新 `related_sections` 映射
- 在 `frontend/src/components/discussion/AgendaPanel.vue` 中:
  - 每个议题项下方展示关联的章节标签
  - 使用不同颜色标签区分议题来源（initial/discovered/intervention）
  - 展示议题优先级（high 显示红色标记，low 灰色）

**数据来源**:
- WebSocket 事件: `{ type: "agenda", data: { event_type: "mapping_update", mappings: [...] } }`

**验证**:
- `cd frontend && npx tsc --noEmit` → exit_code == 0

**输出文件**:
- `backend/src/api/websocket/events.py` (更新)
- `frontend/src/composables/useDiscussion.ts` (更新)
- `frontend/src/components/discussion/AgendaPanel.vue` (更新)

---

### Layer 2: 文档结构动态重组

---

### Task DYN-2.1: DocPlan 结构变更方法实现

**执行**:
- 在 `backend/src/models/doc_plan.py` 的 `DocPlan` 中新增方法:
  - `split_section(section_id: str, new_sections: list[SectionPlan]) -> bool`:
    - 校验原章节状态不为 "completed"
    - 在原章节位置替换为新子章节列表
    - 复制原章节的 `related_agenda_items` 到所有子章节
    - 返回操作是否成功
  - `merge_sections(section_ids: list[str], merged: SectionPlan) -> bool`:
    - 校验所有目标章节在同一文件内且均未 "completed"
    - 合并 `related_agenda_items`（去重）
    - 在第一个被合并章节的位置插入合并后的章节
    - 移除原始章节
    - 返回操作是否成功
  - `add_section(file_index: int, section: SectionPlan, after_section_id: str | None = None) -> bool`:
    - 校验 file_index 有效且 section.id 不冲突
    - 在 after_section_id 之后（或末尾）插入新章节
    - 返回操作是否成功
  - `add_file(file_plan: FilePlan) -> None`:
    - 校验 filename 不冲突
    - 追加到 files 列表
  - `reopen_section(section_id: str, reason: str) -> bool`:
    - 将 status 从 "completed" 改为 "pending"
    - 设置 reopened_reason
    - revision_count += 1
    - 返回操作是否成功
  - `get_completed_sections() -> list[tuple[FilePlan, SectionPlan]]`:
    - 返回所有 status="completed" 的 (file_plan, section) 对
  - `get_reopened_sections() -> list[tuple[FilePlan, SectionPlan]]`:
    - 返回所有 reopened_reason 非空的 (file_plan, section) 对

**状态机**:
- section.status: pending → in_progress → completed → (reopen) → pending → in_progress → completed

**验证**:
- `cd backend && python -c "
from src.models.doc_plan import DocPlan, FilePlan, SectionPlan
dp = DocPlan(discussion_id='d1', topic='t')
fp = FilePlan(filename='f.md', title='F', sections=[SectionPlan(id='s1', title='S1', description='d')])
dp.files.append(fp)
assert dp.add_section(0, SectionPlan(id='s2', title='S2', description='d'), after_section_id='s1')
assert len(dp.files[0].sections) == 2
assert dp.files[0].sections[1].id == 's2'
print('OK')
"` → exit_code == 0

**输出文件**:
- `backend/src/models/doc_plan.py` (更新)

---

### Task DYN-2.2: DocWriter 动态文件操作方法实现

**执行**:
- 在 `backend/src/agents/doc_writer.py` 中新增方法:
  - `add_section_marker(filename: str, section_id: str, title: str, description: str, after_section_id: str | None = None) -> str`:
    - 在指定文件中、指定 section 之后追加新的 section marker
    - 如果 after_section_id 为 None，追加到文件末尾
    - 使用与 `create_skeleton` 相同的 marker 格式: `<!-- section:sN -->`
    - 返回更新后的文件内容
  - `split_section_content(filename: str, old_section_id: str, new_sections: list[dict]) -> str`:
    - 读取原 section 内容
    - 调用 LLM 将内容拆分到 new_sections（每个含 id, title, description）
    - 替换原 section marker 为多个新 section marker
    - 返回更新后的文件内容
  - `merge_section_content(filename: str, section_ids: list[str], merged_section_id: str, merged_title: str) -> str`:
    - 读取所有待合并 section 的内容
    - 调用 LLM 合并内容
    - 移除原 section marker，在第一个位置插入合并后的 marker
    - 返回更新后的文件内容
  - `create_new_file(file_plan) -> None`:
    - 与 `create_skeleton` 中的单文件逻辑一致
    - 创建新的骨架 .md 文件

**验证**:
- `cd backend && python -c "
from src.agents.doc_writer import DocWriter
assert hasattr(DocWriter, 'add_section_marker')
assert hasattr(DocWriter, 'split_section_content')
assert hasattr(DocWriter, 'merge_section_content')
assert hasattr(DocWriter, 'create_new_file')
print('OK')
"` → exit_code == 0

**输出文件**:
- `backend/src/agents/doc_writer.py` (更新)

---

### Task DYN-2.3: 文档结构变更指令解析与执行

**执行**:
- 在 `backend/src/crew/discussion_crew.py` 中新增 `_process_doc_restructure(summary, doc_plan, section)` 方法:
  - 使用正则解析 summary 中的 ` ```doc_restructure ``` ` 代码块
  - 支持四种操作:
    - `split: sN -> [sNa: "标题A", sNb: "标题B"]`
    - `merge: [s5, s6] -> s5_6: "合并标题"`
    - `add_section: file=0, after=s2, id=s2b, title="标题", desc="描述"`
    - `add_file: filename="文件名.md", title="文件标题", sections=[{id, title, desc}]`
  - 对每种操作:
    1. 校验合法性（章节状态、ID 冲突等）
    2. 执行 DocPlan 变更（调用 Task DYN-2.1 的方法）
    3. 执行 DocWriter 文件变更（调用 Task DYN-2.2 的方法）
    4. 更新 Agenda 映射（如有关联）
    5. 广播 `doc_restructure` 事件 + `section_update` 事件
- 修改 `backend/src/agents/lead_planner.py` 的 `create_section_summary_prompt`:
  - 在 prompt 中追加文档结构调整指令格式说明
  - 提示主策划可在 summary 中输出结构变更指令

**指令解析格式**:
```python
DOC_RESTRUCTURE_PATTERN = re.compile(
    r"```doc_restructure\s*\n(.*?)```", re.DOTALL
)
SPLIT_PATTERN = re.compile(r"split:\s*(\S+)\s*->\s*\[(.+?)\]")
MERGE_PATTERN = re.compile(r"merge:\s*\[(.+?)\]\s*->\s*(\S+):\s*\"(.+?)\"")
ADD_SECTION_PATTERN = re.compile(
    r"add_section:\s*file=(\d+),\s*after=(\S+),\s*id=(\S+),\s*title=\"(.+?)\",\s*desc=\"(.+?)\""
)
ADD_FILE_PATTERN = re.compile(r"add_file:\s*filename=\"(.+?)\"")
```

**验证**:
- `cd backend && python -c "from src.crew.discussion_crew import DiscussionCrew; assert hasattr(DiscussionCrew, '_process_doc_restructure'); print('OK')"` → exit_code == 0

**输出文件**:
- `backend/src/crew/discussion_crew.py` (更新)
- `backend/src/agents/lead_planner.py` (更新)

---

### Task DYN-2.4: 新增文档重组 WebSocket 事件和前端处理

**执行**:
- 在 `backend/src/api/websocket/events.py` 中新增:
  - `DocRestructureEvent` 模型:
    ```python
    class DocRestructureEvent(BaseModel):
        type: str = "doc_restructure"
        data: dict  # { discussion_id, operation, details, updated_doc_plan }
    ```
  - `SectionReopenedEvent` 模型:
    ```python
    class SectionReopenedEvent(BaseModel):
        type: str = "section_reopened"
        data: dict  # { discussion_id, section_id, section_title, filename, reason }
    ```
- 在 `frontend/src/types/index.ts` 中新增:
  - `DocRestructureEventData` 接口
  - `SectionReopenedEventData` 接口
- 在 `frontend/src/composables/useDiscussion.ts` 中:
  - 处理 `doc_restructure` 事件: 用 `updated_doc_plan` 替换本地 docPlan 状态
  - 处理 `section_reopened` 事件: 更新对应 section 的 status 显示，显示 toast 通知

**验证**:
- `cd frontend && npx tsc --noEmit` → exit_code == 0

**输出文件**:
- `backend/src/api/websocket/events.py` (更新)
- `frontend/src/types/index.ts` (更新)
- `frontend/src/composables/useDiscussion.ts` (更新)

---

### Layer 3: 干预回溯与主策划消化

---

### Task DYN-3.1: 主策划干预消化 Prompt 实现

**执行**:
- 在 `backend/src/agents/lead_planner.py` 中新增方法:
  - `create_intervention_digest_prompt(user_messages: list[str], current_section: str, discussion_context: str) -> str`:
    - 输入: 用户消息列表、当前章节标题和内容、讨论上下文摘要
    - 要求主策划独立消化观众意见，输出:
      - 观点理解: 提炼用户的核心诉求
      - 关键诉求: 列出需要回应的关键点
      - 与当前讨论的关联分析
      - 后续讨论引导方向
    - 输出格式要求清晰的 Markdown 结构
  - `create_intervention_assessment_prompt(digest_summary: str, current_section: str, completed_sections: list[dict], doc_plan_summary: str) -> str`:
    - 输入: 消化总结、当前章节、已完成章节列表（含 id/title/content_summary）、DocPlan 概要
    - 要求主策划评估影响范围，输出格式:
      ```
      ```intervention_assessment
      impact_level: CURRENT_ONLY | REOPEN | NEW_TOPIC
      affected_sections: [s1, s3]
      reason: "..."
      action_plan:
        - reopen s1: "修改原因"
        - current s3: "当前章节处理方案"
        - add_agenda: "新议题标题" - "描述"
      ```
      ```
    - 约束: 每次回溯最多重开 3 个章节

**验证**:
- `cd backend && python -c "
from src.agents.lead_planner import LeadPlanner
assert hasattr(LeadPlanner, 'create_intervention_digest_prompt')
assert hasattr(LeadPlanner, 'create_intervention_assessment_prompt')
print('OK')
"` → exit_code == 0

**输出文件**:
- `backend/src/agents/lead_planner.py` (更新)

---

### Task DYN-3.2: 干预消化与影响评估主循环集成

**执行**:
- 在 `backend/src/crew/discussion_crew.py` 中新增以下方法:
  - `_lead_planner_digest_intervention(injected_messages: list[dict], section: SectionPlan) -> dict`:
    - 提取用户消息文本
    - 构建当前讨论上下文（含章节内容和最近摘要）
    - 调用 `lead_planner.create_intervention_digest_prompt()` 生成 prompt
    - 调用 LLM 获取消化总结
    - 广播 `lead_planner_digest` 事件（含 digest_summary、key_points、guidance）
    - 将消化总结写入讨论 memory
    - 返回消化结果 dict
  - `_assess_intervention_impact(digest: dict, doc_plan: DocPlan, section: SectionPlan) -> dict`:
    - 构建已完成章节摘要列表
    - 调用 `lead_planner.create_intervention_assessment_prompt()` 生成 prompt
    - 调用 LLM 获取评估结果
    - 解析 `intervention_assessment` 代码块
    - 广播 `intervention_assessment` 事件
    - 返回评估结果 dict（impact_level, affected_sections, reason, action_plan）
  - `_execute_assessment_actions(assessment: dict, doc_plan: DocPlan) -> None`:
    - 根据 impact_level 执行操作:
      - `CURRENT_ONLY`: 无额外操作
      - `REOPEN`: 调用 `doc_plan.reopen_section()` 重开章节（最多 3 个），广播 `section_reopened` 事件
      - `NEW_TOPIC`: 新增 Agenda item（source="intervention"）和/或新增 DocPlan section
    - 广播 doc_plan 更新事件
  - `_lead_planner_post_intervention_guidance(digest: dict, assessment: dict) -> None`:
    - 基于消化结果和评估结论，由主策划输出下一步讨论引导
    - 广播为主策划消息，供其他 agent 参考
- 修改 `run_document_centric` 干预处理部分:
  ```python
  # 原代码:
  if injected:
      self._inject_user_messages(injected)

  # 改为:
  if injected:
      self._inject_user_messages(injected)
      digest = self._lead_planner_digest_intervention(injected, section)
      assessment = self._assess_intervention_impact(digest, doc_plan, section)
      self._execute_assessment_actions(assessment, doc_plan)
      self._lead_planner_post_intervention_guidance(digest, assessment)
  ```

**状态机** (干预后流程):
```
用户注入消息 → inject_user_messages (已有)
  → 主策划消化 (THINKING) → 广播 digest
  → 影响评估 (THINKING) → 广播 assessment
  → 执行决策 (REOPEN/NEW_TOPIC/无操作)
  → 主策划引导 (SPEAKING) → 广播引导消息
  → 恢复正常讨论
```

**验证**:
- `cd backend && python -c "
from src.crew.discussion_crew import DiscussionCrew
assert hasattr(DiscussionCrew, '_lead_planner_digest_intervention')
assert hasattr(DiscussionCrew, '_assess_intervention_impact')
assert hasattr(DiscussionCrew, '_execute_assessment_actions')
assert hasattr(DiscussionCrew, '_lead_planner_post_intervention_guidance')
print('OK')
"` → exit_code == 0

**输出文件**:
- `backend/src/crew/discussion_crew.py` (更新)

---

### Task DYN-3.3: 干预消化 WebSocket 事件和前端展示

**执行**:
- 在 `backend/src/api/websocket/events.py` 中新增:
  - `LeadPlannerDigestEvent` 模型:
    ```python
    class LeadPlannerDigestEvent(BaseModel):
        type: str = "lead_planner_digest"
        data: dict  # { discussion_id, digest_summary, key_points, guidance }
    ```
  - `InterventionAssessmentEvent` 模型:
    ```python
    class InterventionAssessmentEvent(BaseModel):
        type: str = "intervention_assessment"
        data: dict  # { discussion_id, impact_level, affected_sections, reason, action_plan }
    ```
- 在 `frontend/src/types/index.ts` 中新增对应接口
- 在 `frontend/src/composables/useDiscussion.ts` 中:
  - 处理 `lead_planner_digest` 事件: 在消息流中展示主策划的消化思考过程（特殊样式卡片）
  - 处理 `intervention_assessment` 事件:
    - 展示影响评估结果卡片（impact_level、受影响章节、处理方案）
    - 如果 impact_level 为 "REOPEN"，在 docPlan 面板中高亮被重开的章节
- 在 `frontend/src/components/discussion/` 中:
  - 新建 `InterventionDigestCard.vue` 组件:
    - 展示主策划的消化总结
    - 显示提取的关键诉求
    - 显示后续讨论引导方向
    - 使用与普通消息不同的视觉样式（如蓝色边框卡片）
  - 在 `DiscussionView.vue` 中集成新组件

**验证**:
- `cd frontend && npx tsc --noEmit` → exit_code == 0

**输出文件**:
- `backend/src/api/websocket/events.py` (更新)
- `frontend/src/types/index.ts` (更新)
- `frontend/src/composables/useDiscussion.ts` (更新)
- `frontend/src/components/discussion/InterventionDigestCard.vue` (新增)
- `frontend/src/views/DiscussionView.vue` (更新)

---

### Layer 4: 整体审视

---

### Task DYN-4.1: 主策划整体审视 Prompt 实现

**执行**:
- 在 `backend/src/agents/lead_planner.py` 中新增方法:
  - `create_holistic_review_prompt(all_file_contents: list[dict], doc_plan_summary: str, pending_agenda_items: list[str], discussion_summary: str) -> str`:
    - 输入:
      - `all_file_contents`: 所有文件内容 `[{filename, content}]`
      - `doc_plan_summary`: DocPlan 结构概要
      - `pending_agenda_items`: 未完成的议题标题列表
      - `discussion_summary`: 讨论过程摘要
    - 审视维度:
      1. 跨章节一致性: 各章节之间是否存在矛盾或不协调
      2. 完整性检查: 是否覆盖了所有议题，有无遗漏的关键设计点
      3. 观众意见回应: 是否充分回应了观众的所有干预意见
      4. 整体质量: 策划案整体是否达到可交付标准
    - 输出格式:
      ```
      ```holistic_review
      conclusion: APPROVED | NEEDS_REVISION | NEEDS_NEW_TOPIC
      review_dimensions:
        consistency: "..."
        completeness: "..."
        audience_response: "..."
        quality: "..."
      revision_needed:
        - section: s2
          reason: "..."
      new_topics:
        - title: "..."
          description: "..."
      ```
      ```

**验证**:
- `cd backend && python -c "from src.agents.lead_planner import LeadPlanner; assert hasattr(LeadPlanner, 'create_holistic_review_prompt'); print('OK')"` → exit_code == 0

**输出文件**:
- `backend/src/agents/lead_planner.py` (更新)

---

### Task DYN-4.2: 整体审视主循环集成

**执行**:
- 在 `backend/src/crew/discussion_crew.py` 中新增方法:
  - `_lead_planner_holistic_review(doc_plan: DocPlan, agenda: Agenda) -> dict`:
    - 读取所有文件内容（通过 DocWriter.read_file）
    - 构建 doc_plan_summary 和 discussion_summary
    - 获取未完成的议题列表
    - 调用 `lead_planner.create_holistic_review_prompt()` 生成 prompt
    - 调用 LLM 获取审视结果
    - 解析 `holistic_review` 代码块
    - 广播 `holistic_review` 事件
    - 返回审视结果 dict
  - `_execute_review_actions(review: dict, doc_plan: DocPlan, agenda: Agenda) -> None`:
    - 如果 conclusion == "NEEDS_REVISION":
      - 对 revision_needed 中的每个章节调用 `doc_plan.reopen_section()`
      - 广播 `section_reopened` 事件
    - 如果 conclusion == "NEEDS_NEW_TOPIC":
      - 新增 Agenda items
      - 新增 DocPlan sections（如需要）
      - 广播更新事件
  - `_force_complete_with_notes(review: dict) -> None`:
    - 在讨论结果中注明待改进项
    - 广播强制完成事件（附带审视报告）
- 修改 `run_document_centric` 在主循环结束后、finalize 之前插入:
  ```python
  # Phase Final: 整体审视
  holistic_review_count = 0
  max_holistic_reviews = 2

  while holistic_review_count < max_holistic_reviews:
      review = self._lead_planner_holistic_review(doc_plan, self._agenda)
      holistic_review_count += 1

      if review["conclusion"] == "APPROVED":
          break
      elif review["conclusion"] in ("NEEDS_REVISION", "NEEDS_NEW_TOPIC"):
          self._execute_review_actions(review, doc_plan, self._agenda)
          # 回到讨论循环处理新增/重开的章节
          for extra_round in range(max_rounds):
              file_plan, section = self._pick_next_section(doc_plan)
              if file_plan is None:
                  break
              # ... 正常讨论流程 ...
      else:
          break

  if holistic_review_count >= max_holistic_reviews and review.get("conclusion") != "APPROVED":
      self._force_complete_with_notes(review)
  ```

**状态机** (审视流程):
```
所有章节 completed
  → holistic_review (第 1 次)
    → APPROVED → 结束
    → NEEDS_REVISION → reopen sections → 讨论 → holistic_review (第 2 次)
      → APPROVED → 结束
      → NEEDS_REVISION → 强制结束 + 注明待改进项
    → NEEDS_NEW_TOPIC → add sections/agenda → 讨论 → holistic_review (第 2 次)
      → ...
```

**验证**:
- `cd backend && python -c "
from src.crew.discussion_crew import DiscussionCrew
assert hasattr(DiscussionCrew, '_lead_planner_holistic_review')
assert hasattr(DiscussionCrew, '_execute_review_actions')
assert hasattr(DiscussionCrew, '_force_complete_with_notes')
print('OK')
"` → exit_code == 0

**输出文件**:
- `backend/src/crew/discussion_crew.py` (更新)

---

### Task DYN-4.3: 整体审视 WebSocket 事件和前端展示

**执行**:
- 在 `backend/src/api/websocket/events.py` 中新增:
  - `HolisticReviewEvent` 模型:
    ```python
    class HolisticReviewEvent(BaseModel):
        type: str = "holistic_review"
        data: dict  # { discussion_id, review_round, conclusion, review_dimensions, revisions_needed, new_topics }
    ```
- 在 `frontend/src/types/index.ts` 中新增 `HolisticReviewEventData` 接口
- 在 `frontend/src/composables/useDiscussion.ts` 中:
  - 处理 `holistic_review` 事件
  - 在消息流中展示审视报告卡片
  - 如果 conclusion 为 "NEEDS_REVISION"，高亮被重开的章节
- 新建 `frontend/src/components/discussion/HolisticReviewCard.vue`:
  - 展示审视维度（一致性、完整性、观众回应、整体质量）
  - 展示结论（APPROVED 绿色、NEEDS_REVISION 橙色、NEEDS_NEW_TOPIC 蓝色）
  - 展示需修订的章节列表及原因
  - 展示新增议题列表

**验证**:
- `cd frontend && npx tsc --noEmit` → exit_code == 0

**输出文件**:
- `backend/src/api/websocket/events.py` (更新)
- `frontend/src/types/index.ts` (更新)
- `frontend/src/composables/useDiscussion.ts` (更新)
- `frontend/src/components/discussion/HolisticReviewCard.vue` (新增)

---

### Layer 5: API 接口与集成测试

---

### Task DYN-5.1: 新增议题管理和文档重组 API

**执行**:
- 在 `backend/src/api/routes/intervention.py` 中新增:
  - `POST /api/discussions/{discussion_id}/agenda/items/{item_id}/complete`:
    - 手动标记议题完结
    - 校验讨论存在且正在运行
    - 调用 `agenda.get_item_by_id(item_id)` 并标记 completed
    - 广播 agenda 事件
    - 返回 `{ "status": "completed", "item": AgendaItem }`
  - `POST /api/discussions/{discussion_id}/agenda/items/{item_id}/priority`:
    - 请求体: `{ "priority": 1 }` (1=high, 0=normal, -1=low)
    - 校验讨论存在且正在运行
    - 更新议题优先级
    - 广播 agenda 事件
    - 返回 `{ "status": "updated", "item": AgendaItem }`
  - `POST /api/discussions/{discussion_id}/doc-plan/restructure`:
    - 请求体: `{ "operation": "add_section", "params": { ... } }`
    - 支持 add_section / add_file 操作（管理员/调试用）
    - 校验参数合法性
    - 执行 DocPlan 变更 + DocWriter 文件变更
    - 广播事件
    - 返回 `{ "status": "success", "doc_plan": DocPlan }`

**数据结构**:
```python
class AgendaPriorityRequest(BaseModel):
    priority: int = Field(ge=-1, le=1)

class DocRestructureRequest(BaseModel):
    operation: str  # "add_section" | "add_file"
    params: dict
```

**验证**:
- `cd backend && python -c "
from src.api.routes.intervention import router
routes = [r.path for r in router.routes]
assert any('agenda' in r and 'complete' in r for r in routes)
assert any('agenda' in r and 'priority' in r for r in routes)
assert any('doc-plan' in r and 'restructure' in r for r in routes)
print('OK')
"` → exit_code == 0

**输出文件**:
- `backend/src/api/routes/intervention.py` (更新)

---

### Task DYN-5.2: 集成测试 — 议题驱动与文档重组

**执行**:
- 创建 `backend/tests/test_dynamic_discussion.py`:
  - `test_agenda_item_model_extensions`: 验证 AgendaItem 新字段（related_sections、priority、source）
  - `test_section_plan_model_extensions`: 验证 SectionPlan 新字段（related_agenda_items、revision_count）
  - `test_doc_plan_split_section`: 验证章节拆分逻辑
    - 拆分 pending 章节 → 成功
    - 拆分 completed 章节 → 失败
    - 子章节继承 related_agenda_items
  - `test_doc_plan_merge_sections`: 验证章节合并逻辑
    - 合并同文件内 pending 章节 → 成功
    - 合并不同文件的章节 → 失败
    - 合并已 completed 章节 → 失败
  - `test_doc_plan_add_section`: 验证章节新增
    - 在指定位置插入 → 正确位置
    - ID 冲突 → 失败
  - `test_doc_plan_add_file`: 验证文件新增
    - filename 冲突 → 失败
  - `test_doc_plan_reopen_section`: 验证章节回溯
    - completed → pending → revision_count 增加
    - 非 completed 状态 → 失败
    - reopened_reason 正确设置
  - `test_agenda_directive_parsing`: 验证议题指令解析
    - complete 指令
    - add 指令（含标题和描述）
    - priority 指令
  - `test_doc_restructure_parsing`: 验证结构变更指令解析
    - split 指令
    - merge 指令
    - add_section 指令
    - add_file 指令

**验证**:
- `cd backend && python -m pytest tests/test_dynamic_discussion.py -v` → exit_code == 0

**输出文件**:
- `backend/tests/test_dynamic_discussion.py` (新增)

---

### Task DYN-5.3: 集成测试 — 干预消化与整体审视

**执行**:
- 在 `backend/tests/test_dynamic_discussion.py` 中追加:
  - `test_intervention_impact_levels`: 验证三种影响级别的解析
    - CURRENT_ONLY → 无额外操作
    - REOPEN → 正确解析 affected_sections
    - NEW_TOPIC → 正确解析新议题
  - `test_reopen_max_limit`: 验证每次回溯最多重开 3 个章节
  - `test_holistic_review_parsing`: 验证审视结果解析
    - APPROVED → 无后续操作
    - NEEDS_REVISION → 正确解析 revision_needed
    - NEEDS_NEW_TOPIC → 正确解析 new_topics
  - `test_holistic_review_max_iterations`: 验证最多 2 次审视
  - `test_doc_plan_serialization`: 验证扩展字段的 to_dict/from_dict 往返

**验证**:
- `cd backend && python -m pytest tests/test_dynamic_discussion.py -v` → exit_code == 0

**输出文件**:
- `backend/tests/test_dynamic_discussion.py` (更新)

---

## 验收标准

- [ ] AC-40: 讨论启动时自动生成议程并展示在前端 AgendaPanel 中 (Spec AC-40)
- [ ] AC-41: 每轮结束后，主策划可通过 summary 中的指令标记议题完结 (Spec AC-41)
- [ ] AC-42: 讨论过程中发现的新议题能自动追加到议程 (Spec AC-42)
- [ ] AC-43: 议题与文档章节的多对多映射在前端可视化展示 (Spec AC-43)
- [ ] AC-44: 主策划可在讨论中途新增文档章节，DocWriter 正确追加 section marker (Spec AC-44)
- [ ] AC-45: 主策划可拆分章节，原内容正确分发到子章节 (Spec AC-45)
- [ ] AC-46: 文档结构变更后，前端实时更新 DocPlan 展示 (Spec AC-46)
- [ ] AC-47: 观众消息注入后，系统执行影响评估并展示评估结果 (Spec AC-47)
- [ ] AC-48: 影响评估判定需要回溯时，已完成章节正确标记回 pending (Spec AC-48)
- [ ] AC-49: 回溯修订的章节保留已有内容，DocWriter 在已有内容基础上增量更新 (Spec AC-49)
- [ ] AC-50: 每次回溯最多重开 3 个章节，超出时提示用户确认 (Spec AC-50)
- [ ] AC-51: 观众干预后，主策划先独立消化评估，产出消化总结后再恢复其他 agent 讨论 (Spec AC-51)
- [ ] AC-52: 主策划消化过程通过 WebSocket 广播，前端展示主策划的思考过程 (Spec AC-52)
- [ ] AC-53: 所有章节完成后，主策划执行整体审视，检查跨章节一致性和完整性 (Spec AC-53)
- [ ] AC-54: 整体审视判定 NEEDS_REVISION 时，正确 reopen 相关章节并继续讨论 (Spec AC-54)
- [ ] AC-55: 整体审视最多 2 次，第 2 次仍有问题则强制结束并注明待改进项 (Spec AC-55)
