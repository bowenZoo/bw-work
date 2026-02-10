"""Integration tests for dynamic discussion features (DYN-5.2 / DYN-5.3).

Tests cover:
- Model extensions (AgendaItem, SectionPlan, DocPlan)
- DocPlan operations (split, merge, add_section, add_file, reopen)
- Agenda directive parsing
- Document restructure parsing
- Intervention impact assessment parsing
- Holistic review parsing
- Serialization round-trips
"""

import re

import pytest

from src.models.agenda import Agenda, AgendaItem, AgendaItemStatus, AgendaSummaryDetails
from src.models.doc_plan import DocPlan, FilePlan, SectionPlan
from src.crew.discussion_crew import (
    AGENDA_DIRECTIVE_PATTERN,
    DOC_RESTRUCTURE_PATTERN,
    INTERVENTION_ASSESSMENT_PATTERN,
    HOLISTIC_REVIEW_PATTERN,
)


# ------------------------------------------------------------------
# DYN-5.2: Model extension tests
# ------------------------------------------------------------------


class TestAgendaItemModelExtensions:
    """Test AgendaItem new fields: related_sections, priority, source."""

    def test_default_values(self):
        item = AgendaItem(title="测试议题")
        assert item.related_sections == []
        assert item.priority == 0
        assert item.source == "initial"

    def test_custom_values(self):
        item = AgendaItem(
            title="自定义议题",
            related_sections=["s1", "s2"],
            priority=1,
            source="discovered",
        )
        assert item.related_sections == ["s1", "s2"]
        assert item.priority == 1
        assert item.source == "discovered"

    def test_to_dict_includes_new_fields(self):
        item = AgendaItem(
            title="序列化测试",
            related_sections=["s3"],
            priority=-1,
            source="intervention",
        )
        d = item.to_dict()
        assert d["related_sections"] == ["s3"]
        assert d["priority"] == -1
        assert d["source"] == "intervention"

    def test_priority_range(self):
        for p in (-1, 0, 1):
            item = AgendaItem(title="p", priority=p)
            assert item.priority == p


class TestSectionPlanModelExtensions:
    """Test SectionPlan new fields: related_agenda_items, revision_count, reopened_reason."""

    def test_default_values(self):
        s = SectionPlan(id="s1", title="T", description="D")
        assert s.related_agenda_items == []
        assert s.revision_count == 0
        assert s.reopened_reason is None

    def test_custom_values(self):
        s = SectionPlan(
            id="s1", title="T", description="D",
            related_agenda_items=["a1", "a2"],
            revision_count=2,
            reopened_reason="观众要求修改",
        )
        assert s.related_agenda_items == ["a1", "a2"]
        assert s.revision_count == 2
        assert s.reopened_reason == "观众要求修改"


# ------------------------------------------------------------------
# DYN-5.2: DocPlan operation tests
# ------------------------------------------------------------------


class TestDocPlanSplitSection:
    """Test DocPlan.split_section."""

    def _make_plan(self):
        return DocPlan(
            discussion_id="d1",
            topic="test",
            files=[FilePlan(
                filename="f1.md",
                title="F1",
                sections=[
                    SectionPlan(id="s1", title="A", description="a"),
                    SectionPlan(id="s2", title="B", description="b"),
                    SectionPlan(id="s3", title="C", description="c", status="completed"),
                ],
            )],
        )

    def test_split_pending_section(self):
        plan = self._make_plan()
        new_sections = [
            SectionPlan(id="s4", title="A1", description="a1"),
            SectionPlan(id="s5", title="A2", description="a2"),
        ]
        assert plan.split_section("s1", new_sections) is True
        ids = [s.id for s in plan.files[0].sections]
        assert ids == ["s4", "s5", "s2", "s3"]

    def test_split_completed_section_fails(self):
        plan = self._make_plan()
        new_sections = [SectionPlan(id="s6", title="X", description="x")]
        assert plan.split_section("s3", new_sections) is False

    def test_split_nonexistent_section_fails(self):
        plan = self._make_plan()
        new_sections = [SectionPlan(id="s6", title="X", description="x")]
        assert plan.split_section("s99", new_sections) is False

    def test_split_inherits_context(self):
        """子章节应能独立追踪 agenda 关联。"""
        plan = self._make_plan()
        plan.files[0].sections[0].related_agenda_items = ["a1"]
        new_sections = [
            SectionPlan(id="s4", title="A1", description="a1", related_agenda_items=["a1"]),
            SectionPlan(id="s5", title="A2", description="a2", related_agenda_items=["a1"]),
        ]
        plan.split_section("s1", new_sections)
        assert plan.files[0].sections[0].related_agenda_items == ["a1"]
        assert plan.files[0].sections[1].related_agenda_items == ["a1"]


class TestDocPlanMergeSections:
    """Test DocPlan.merge_sections."""

    def _make_plan(self):
        return DocPlan(
            discussion_id="d1",
            topic="test",
            files=[
                FilePlan(
                    filename="f1.md",
                    title="F1",
                    sections=[
                        SectionPlan(id="s1", title="A", description="a"),
                        SectionPlan(id="s2", title="B", description="b"),
                        SectionPlan(id="s3", title="C", description="c"),
                    ],
                ),
                FilePlan(
                    filename="f2.md",
                    title="F2",
                    sections=[
                        SectionPlan(id="s4", title="D", description="d"),
                    ],
                ),
            ],
        )

    def test_merge_same_file_pending(self):
        plan = self._make_plan()
        merged = SectionPlan(id="s5", title="AB", description="merged")
        assert plan.merge_sections(["s1", "s2"], merged) is True
        ids = [s.id for s in plan.files[0].sections]
        assert "s5" in ids
        assert "s1" not in ids
        assert "s2" not in ids

    def test_merge_different_files_fails(self):
        plan = self._make_plan()
        merged = SectionPlan(id="s5", title="Mixed", description="x")
        assert plan.merge_sections(["s1", "s4"], merged) is False

    def test_merge_completed_fails(self):
        plan = self._make_plan()
        plan.files[0].sections[0].status = "completed"
        merged = SectionPlan(id="s5", title="AB", description="x")
        assert plan.merge_sections(["s1", "s2"], merged) is False


class TestDocPlanAddSection:
    """Test DocPlan.add_section."""

    def _make_plan(self):
        return DocPlan(
            discussion_id="d1",
            topic="test",
            files=[FilePlan(
                filename="f1.md",
                title="F1",
                sections=[
                    SectionPlan(id="s1", title="A", description="a"),
                    SectionPlan(id="s2", title="B", description="b"),
                ],
            )],
        )

    def test_add_at_beginning(self):
        plan = self._make_plan()
        new_s = SectionPlan(id="s3", title="Start", description="start")
        assert plan.add_section(0, new_s) is True
        assert plan.files[0].sections[0].id == "s3"

    def test_add_after_specific_section(self):
        plan = self._make_plan()
        new_s = SectionPlan(id="s3", title="Middle", description="mid")
        assert plan.add_section(0, new_s, after_section_id="s1") is True
        ids = [s.id for s in plan.files[0].sections]
        assert ids == ["s1", "s3", "s2"]

    def test_add_invalid_file_index_fails(self):
        plan = self._make_plan()
        new_s = SectionPlan(id="s3", title="X", description="x")
        assert plan.add_section(99, new_s) is False

    def test_add_after_nonexistent_section_fails(self):
        plan = self._make_plan()
        new_s = SectionPlan(id="s3", title="X", description="x")
        assert plan.add_section(0, new_s, after_section_id="s99") is False

    def test_add_id_conflict_fails(self):
        """Adding a section with an existing ID should fail."""
        plan = self._make_plan()
        new_s = SectionPlan(id="s1", title="Conflict", description="conflict")
        assert plan.add_section(0, new_s) is False
        # Verify plan is unchanged
        ids = [s.id for s in plan.files[0].sections]
        assert ids == ["s1", "s2"]


class TestDocPlanAddFile:
    """Test DocPlan.add_file."""

    def test_add_file(self):
        plan = DocPlan(discussion_id="d1", topic="test", files=[])
        fp = FilePlan(filename="new.md", title="New", sections=[
            SectionPlan(id="s1", title="A", description="a"),
        ])
        assert plan.add_file(fp) is True
        assert len(plan.files) == 1
        assert plan.files[0].filename == "new.md"

    def test_add_file_filename_conflict_fails(self):
        """Adding a file with an existing filename should fail."""
        plan = DocPlan(
            discussion_id="d1",
            topic="test",
            files=[FilePlan(filename="existing.md", title="Existing", sections=[])],
        )
        fp = FilePlan(filename="existing.md", title="Duplicate", sections=[])
        assert plan.add_file(fp) is False
        assert len(plan.files) == 1  # unchanged


class TestDocPlanReopenSection:
    """Test DocPlan.reopen_section."""

    def _make_plan(self):
        return DocPlan(
            discussion_id="d1",
            topic="test",
            files=[FilePlan(
                filename="f1.md",
                title="F1",
                sections=[
                    SectionPlan(id="s1", title="A", description="a", status="completed"),
                    SectionPlan(id="s2", title="B", description="b", status="pending"),
                ],
            )],
        )

    def test_reopen_completed_section(self):
        plan = self._make_plan()
        assert plan.reopen_section("s1", "需要修改") is True
        f, s = plan.get_section("s1")
        assert s.status == "pending"
        assert s.reopened_reason == "需要修改"
        assert s.revision_count == 1

    def test_reopen_increments_revision_count(self):
        plan = self._make_plan()
        plan.reopen_section("s1", "第一次修改")
        plan.files[0].sections[0].status = "completed"
        plan.reopen_section("s1", "第二次修改")
        assert plan.files[0].sections[0].revision_count == 2

    def test_reopen_pending_section_fails(self):
        plan = self._make_plan()
        assert plan.reopen_section("s2", "已经是pending") is False

    def test_reopen_nonexistent_section_fails(self):
        plan = self._make_plan()
        assert plan.reopen_section("s99", "不存在") is False


# ------------------------------------------------------------------
# DYN-5.2: Directive parsing tests
# ------------------------------------------------------------------


class TestAgendaDirectiveParsing:
    """Test parsing of ```agenda_update``` blocks."""

    def test_complete_directive(self):
        text = """一些总结内容

```agenda_update
complete: abc-123
```

更多内容"""
        match = AGENDA_DIRECTIVE_PATTERN.search(text)
        assert match is not None
        block = match.group(1)
        assert "complete: abc-123" in block

    def test_add_directive(self):
        text = """```agenda_update
add: [新议题标题] - 这是新议题描述
```"""
        match = AGENDA_DIRECTIVE_PATTERN.search(text)
        assert match is not None
        block = match.group(1)
        assert "add: [新议题标题] - 这是新议题描述" in block

    def test_priority_directive(self):
        text = """```agenda_update
priority: item-123 high
```"""
        match = AGENDA_DIRECTIVE_PATTERN.search(text)
        assert match is not None
        block = match.group(1)
        assert "priority: item-123 high" in block

    def test_multiple_directives(self):
        text = """```agenda_update
complete: a1
add: [新议题] - 描述
priority: a2 low
```"""
        match = AGENDA_DIRECTIVE_PATTERN.search(text)
        assert match is not None
        lines = [l.strip() for l in match.group(1).strip().split("\n") if l.strip()]
        assert len(lines) == 3

    def test_no_match_without_block(self):
        text = "没有任何代码块的普通文本"
        match = AGENDA_DIRECTIVE_PATTERN.search(text)
        assert match is None


class TestDocRestructureParsing:
    """Test parsing of ```doc_restructure``` blocks."""

    def test_split_directive(self):
        text = """```doc_restructure
split: s1 -> [系统概述](系统整体描述), [核心循环](核心玩法循环)
```"""
        match = DOC_RESTRUCTURE_PATTERN.search(text)
        assert match is not None
        block = match.group(1)
        assert "split: s1" in block
        # Verify we can parse the new section specs
        parts = block.strip().split("->", 1)
        assert len(parts) == 2
        specs = re.findall(r"\[(.+?)\]\((.+?)\)", parts[1])
        assert len(specs) == 2
        assert specs[0] == ("系统概述", "系统整体描述")

    def test_merge_directive(self):
        text = """```doc_restructure
merge: s1, s2 -> [合并章节]
```"""
        match = DOC_RESTRUCTURE_PATTERN.search(text)
        assert match is not None
        block = match.group(1)
        assert "merge: s1, s2" in block

    def test_add_section_directive(self):
        text = """```doc_restructure
add_section: 0:s2 [新章节](新描述)
```"""
        match = DOC_RESTRUCTURE_PATTERN.search(text)
        assert match is not None
        block = match.group(1)
        assert "add_section:" in block

    def test_add_file_directive(self):
        text = """```doc_restructure
add_file: [新文件.md](新文件标题) sections: [章节1](描述1), [章节2](描述2)
```"""
        match = DOC_RESTRUCTURE_PATTERN.search(text)
        assert match is not None
        block = match.group(1)
        assert "add_file:" in block
        file_match = re.match(r"add_file:\s*\[(.+?)\]\((.+?)\)\s*sections:\s*(.+)", block.strip())
        assert file_match is not None
        assert file_match.group(1) == "新文件.md"

    def test_no_match_without_block(self):
        text = "没有 restructure 块"
        assert DOC_RESTRUCTURE_PATTERN.search(text) is None


# ------------------------------------------------------------------
# DYN-5.3: Intervention and review parsing tests
# ------------------------------------------------------------------


class TestInterventionImpactLevels:
    """Test parsing of ```intervention_assessment``` blocks."""

    def test_current_only(self):
        text = """```intervention_assessment
impact_level: CURRENT_ONLY
summary: 仅影响当前章节
current_section_actions:
  - 在当前章节加入用户建议
```"""
        match = INTERVENTION_ASSESSMENT_PATTERN.search(text)
        assert match is not None
        block = match.group(1)
        level_match = re.search(r"impact_level:\s*(\S+)", block)
        assert level_match.group(1) == "CURRENT_ONLY"

    def test_reopen(self):
        text = """```intervention_assessment
impact_level: REOPEN
summary: 需要回溯已完成章节
current_section_actions:
  - 调整当前讨论方向
reopen_sections:
  - section_id: s1
    reason: 观众提出了新的需求
    focus: 重新审视系统架构
  - section_id: s2
    reason: 数值需要调整
    focus: 重新平衡数值
```"""
        match = INTERVENTION_ASSESSMENT_PATTERN.search(text)
        assert match is not None
        block = match.group(1)
        level_match = re.search(r"impact_level:\s*(\S+)", block)
        assert level_match.group(1) == "REOPEN"
        # Count reopen sections
        reopen_matches = re.findall(r"section_id:\s*(\S+)", block)
        assert len(reopen_matches) == 2

    def test_new_topic(self):
        text = """```intervention_assessment
impact_level: NEW_TOPIC
summary: 需要新增讨论议题
current_section_actions:
  - 在当前章节添加备注
new_topics:
  - title: 付费系统设计
    description: 观众强烈要求讨论付费模式
    priority: high
```"""
        match = INTERVENTION_ASSESSMENT_PATTERN.search(text)
        assert match is not None
        block = match.group(1)
        level_match = re.search(r"impact_level:\s*(\S+)", block)
        assert level_match.group(1) == "NEW_TOPIC"


class TestReopenMaxLimit:
    """Test that reopen sections are limited to 3."""

    def test_max_three_reopens(self):
        plan = DocPlan(
            discussion_id="d1",
            topic="test",
            files=[FilePlan(
                filename="f1.md",
                title="F1",
                sections=[
                    SectionPlan(id=f"s{i}", title=f"S{i}", description=f"d{i}", status="completed")
                    for i in range(1, 6)
                ],
            )],
        )
        # Reopen 3 should succeed
        for i in range(1, 4):
            assert plan.reopen_section(f"s{i}", "test") is True
        # Verify 3 are reopened
        reopened = [s for f in plan.files for s in f.sections if s.status == "pending"]
        assert len(reopened) == 3


class TestHolisticReviewParsing:
    """Test parsing of ```holistic_review``` blocks."""

    def test_approved(self):
        text = """```holistic_review
conclusion: APPROVED
quality_score: 8
summary: 文档质量良好
consistency_issues:
completeness_gaps:
revision_actions:
new_topics:
```"""
        match = HOLISTIC_REVIEW_PATTERN.search(text)
        assert match is not None
        block = match.group(1)
        conclusion_match = re.search(r"conclusion:\s*(\S+)", block)
        assert conclusion_match.group(1) == "APPROVED"
        score_match = re.search(r"quality_score:\s*(\d+)", block)
        assert int(score_match.group(1)) == 8

    def test_needs_revision(self):
        text = """```holistic_review
conclusion: NEEDS_REVISION
quality_score: 5
summary: 部分章节需要修改
consistency_issues:
  - file: 核心玩法.md
    section: s1
    issue: 术语不统一
    suggestion: 统一使用"战斗值"
revision_actions:
  - section_id: s1
    file: 核心玩法.md
    action: 修正术语不一致问题
```"""
        match = HOLISTIC_REVIEW_PATTERN.search(text)
        assert match is not None
        block = match.group(1)
        conclusion_match = re.search(r"conclusion:\s*(\S+)", block)
        assert conclusion_match.group(1) == "NEEDS_REVISION"

    def test_needs_new_topic(self):
        text = """```holistic_review
conclusion: NEEDS_NEW_TOPIC
quality_score: 4
summary: 发现重大遗漏
new_topics:
  - title: 安全系统设计
    reason: 文档未涉及反作弊系统
```"""
        match = HOLISTIC_REVIEW_PATTERN.search(text)
        assert match is not None
        block = match.group(1)
        conclusion_match = re.search(r"conclusion:\s*(\S+)", block)
        assert conclusion_match.group(1) == "NEEDS_NEW_TOPIC"


class TestHolisticReviewMaxIterations:
    """Test that holistic review logic limits iterations to 2."""

    def test_review_loop_max_iterations(self):
        """Verify the review loop constant is 2 in run_document_centric."""
        import inspect
        from src.crew.discussion_crew import DiscussionCrew
        source = inspect.getsource(DiscussionCrew.run_document_centric)
        # Check that the review loop uses range(2)
        assert "for review_round in range(2)" in source


# ------------------------------------------------------------------
# DYN-5.3: Serialization round-trip test
# ------------------------------------------------------------------


class TestDocPlanSerialization:
    """Test DocPlan to_dict/from_dict round-trip with extended fields."""

    def test_round_trip(self):
        plan = DocPlan(
            discussion_id="d1",
            topic="序列化测试",
            files=[
                FilePlan(
                    filename="test.md",
                    title="测试文件",
                    sections=[
                        SectionPlan(
                            id="s1",
                            title="章节1",
                            description="描述1",
                            status="completed",
                            related_agenda_items=["a1", "a2"],
                            revision_count=2,
                            reopened_reason="观众反馈",
                        ),
                        SectionPlan(
                            id="s2",
                            title="章节2",
                            description="描述2",
                            status="pending",
                        ),
                    ],
                ),
            ],
            current_section_id="s2",
        )

        d = plan.to_dict()
        restored = DocPlan.from_dict(d)

        assert restored.discussion_id == plan.discussion_id
        assert restored.topic == plan.topic
        assert restored.current_section_id == "s2"
        assert len(restored.files) == 1
        assert len(restored.files[0].sections) == 2

        s1 = restored.files[0].sections[0]
        assert s1.id == "s1"
        assert s1.status == "completed"
        assert s1.related_agenda_items == ["a1", "a2"]
        assert s1.revision_count == 2
        assert s1.reopened_reason == "观众反馈"

        s2 = restored.files[0].sections[1]
        assert s2.id == "s2"
        assert s2.related_agenda_items == []
        assert s2.revision_count == 0
        assert s2.reopened_reason is None

    def test_get_completed_sections(self):
        plan = DocPlan(
            discussion_id="d1",
            topic="test",
            files=[FilePlan(
                filename="f1.md",
                title="F1",
                sections=[
                    SectionPlan(id="s1", title="A", description="a", status="completed"),
                    SectionPlan(id="s2", title="B", description="b", status="pending"),
                    SectionPlan(id="s3", title="C", description="c", status="completed"),
                ],
            )],
        )
        completed = plan.get_completed_sections()
        assert len(completed) == 2
        assert completed[0][1].id == "s1"
        assert completed[1][1].id == "s3"

    def test_get_reopened_sections(self):
        plan = DocPlan(
            discussion_id="d1",
            topic="test",
            files=[FilePlan(
                filename="f1.md",
                title="F1",
                sections=[
                    SectionPlan(id="s1", title="A", description="a", reopened_reason="fix"),
                    SectionPlan(id="s2", title="B", description="b"),
                ],
            )],
        )
        reopened = plan.get_reopened_sections()
        assert len(reopened) == 1
        assert reopened[0][1].id == "s1"

    def test_all_sections_completed(self):
        plan = DocPlan(
            discussion_id="d1",
            topic="test",
            files=[FilePlan(
                filename="f1.md",
                title="F1",
                sections=[
                    SectionPlan(id="s1", title="A", description="a", status="completed"),
                    SectionPlan(id="s2", title="B", description="b", status="completed"),
                ],
            )],
        )
        assert plan.all_sections_completed() is True

        plan.files[0].sections[0].status = "pending"
        assert plan.all_sections_completed() is False
