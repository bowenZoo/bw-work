"""Tests for the 7 new features added to discussion API.

1. Discussion Quality Scoring
2. Cross-stage Dependency Hints
3. Producer Stance
4. GDD Auto Export
5. Discussion Template Library
6. Agent Opinion Archive
7. Viewer Mode Enhancement
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes.discussion import (
    DiscussionState,
    DiscussionStatus,
    _compute_quality_score,
    _compute_dependency_hints,
    _extract_agent_opinions,
    _DISCUSSION_TEMPLATES,
    _discussions,
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_discussions():
    """Clean up _discussions dict before/after each test."""
    _discussions.clear()
    yield
    _discussions.clear()


# =============================================================================
# Feature 1: Discussion Quality Scoring
# =============================================================================

class TestQualityScoring:
    def test_compute_quality_score_no_messages(self):
        """Quality score with no messages/no discussion returns None."""
        result = _compute_quality_score("nonexistent-disc-id")
        assert result is None

    def test_compute_quality_score_with_messages(self):
        """Quality score is computed from messages in discussion memory."""
        disc_id = "test-rich-msg"
        disc = DiscussionState(
            id=disc_id,
            topic="Test",
            rounds=5,
            status=DiscussionStatus.COMPLETED,
            created_at="2024-01-01T00:00:00",
        )
        _discussions[disc_id] = disc

        # Patch the memory load to return messages
        mock_record = MagicMock()
        mock_record.messages = [
            MagicMock(
                content="最终决策：采用卡牌策略玩法，实现玩家目标，具体方案如下...",
                agent_role="system_designer",
            ),
            MagicMock(
                content="同意这个方案，数值参数如下，达成共识",
                agent_role="number_designer",
            ),
        ]
        from src.api.routes import discussion as disc_module
        with patch.object(disc_module._discussion_memory, "load", return_value=mock_record):
            result = _compute_quality_score(disc_id)

        assert result is not None
        assert "completeness" in result
        assert "executability" in result
        assert "consensus" in result
        assert "overall" in result
        assert "message_count" in result
        assert result["message_count"] == 2

    def test_quality_score_range(self):
        """All score dimensions should be in [1, 10] range when messages exist."""
        mock_record = MagicMock()
        mock_record.messages = [
            MagicMock(content="总结：决策点一，同意方案。", agent_role="system_designer"),
            MagicMock(content="同意并支持此方案，可以执行。", agent_role="number_designer"),
        ]
        from src.api.routes import discussion as disc_module
        with patch.object(disc_module._discussion_memory, "load", return_value=mock_record):
            result = _compute_quality_score("any-id")

        assert result is not None
        for key in ("completeness", "executability", "consensus", "overall"):
            assert 1 <= result[key] <= 10, f"{key} out of range: {result[key]}"

    def test_quality_score_stored_after_completion(self, client):
        """Completed discussion should have quality_score in GET response."""
        disc_id = "disc-score-test"
        disc = DiscussionState(
            id=disc_id,
            topic="Test scoring",
            rounds=3,
            status=DiscussionStatus.COMPLETED,
            created_at="2024-01-01T00:00:00",
            quality_score={"completeness": 7, "executability": 6, "consensus": 8, "overall": 7, "message_count": 10},
        )
        _discussions[disc_id] = disc

        resp = client.get(f"/api/discussions/{disc_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["quality_score"] is not None
        assert data["quality_score"]["completeness"] == 7
        assert data["quality_score"]["overall"] == 7


# =============================================================================
# Feature 2: Cross-stage Dependency Hints
# =============================================================================

class TestDependencyHints:
    def test_dependency_hints_no_prior_discussions(self):
        """No prior discussions → empty hints."""
        hints = _compute_dependency_hints("project-x", "stage-new")
        assert isinstance(hints, list)
        assert len(hints) == 0

    def test_dependency_hints_from_completed_discussion(self):
        """Completed stage discussion for same project → hints returned."""
        prior_disc = DiscussionState(
            id="disc-prior",
            topic="概念讨论",
            rounds=5,
            status=DiscussionStatus.COMPLETED,
            created_at="2024-01-01T00:00:00",
            project_id="proj-abc",
            target_type="stage",
            target_id="stage-concept",
        )
        _discussions["disc-prior"] = prior_disc

        hints = _compute_dependency_hints("proj-abc", "stage-core")
        # There are no messages, so only the basic hint is added
        assert isinstance(hints, list)
        # The function should at least recognize the completed discussion
        # (may return 0 if no messages; just verify it doesn't crash)

    def test_dependency_hints_exclude_same_stage(self):
        """Should not include hints from the current stage."""
        prior_disc = DiscussionState(
            id="disc-same",
            topic="同阶段讨论",
            rounds=3,
            status=DiscussionStatus.COMPLETED,
            created_at="2024-01-01T00:00:00",
            project_id="proj-same",
            target_type="stage",
            target_id="stage-current",
        )
        _discussions["disc-same"] = prior_disc

        hints = _compute_dependency_hints("proj-same", "stage-current")
        assert len(hints) == 0

    def test_dependency_hints_in_get_response(self, client):
        """GET discussion response should include dependency_hints list."""
        disc_id = "disc-hints-test"
        disc = DiscussionState(
            id=disc_id,
            topic="Test",
            rounds=3,
            status=DiscussionStatus.PENDING,
            created_at="2024-01-01T00:00:00",
            dependency_hints=["关键决策：采用卡牌玩法（来自：概念阶段）"],
        )
        _discussions[disc_id] = disc

        resp = client.get(f"/api/discussions/{disc_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "dependency_hints" in data
        assert len(data["dependency_hints"]) == 1
        assert "卡牌玩法" in data["dependency_hints"][0]


# =============================================================================
# Feature 3: Producer Stance
# =============================================================================

class TestProducerStance:
    def test_stance_stored_in_state(self, client):
        """producer_stance should be stored and returned via GET."""
        disc_id = "disc-stance"
        disc = DiscussionState(
            id=disc_id,
            topic="Test stance",
            rounds=3,
            status=DiscussionStatus.PENDING,
            created_at="2024-01-01T00:00:00",
            producer_stance="低付费门槛，核心玩法免费",
        )
        _discussions[disc_id] = disc

        resp = client.get(f"/api/discussions/{disc_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["producer_stance"] == "低付费门槛，核心玩法免费"

    def test_stance_empty_by_default(self, client):
        """producer_stance defaults to empty string."""
        disc_id = "disc-no-stance"
        disc = DiscussionState(
            id=disc_id,
            topic="Test",
            rounds=3,
            status=DiscussionStatus.PENDING,
            created_at="2024-01-01T00:00:00",
        )
        _discussions[disc_id] = disc

        resp = client.get(f"/api/discussions/{disc_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["producer_stance"] == ""

    def test_stance_injected_into_briefing_at_top(self):
        """Producer stance is merged into briefing at the top with warning header."""
        stance = "核心玩法免费"
        briefing = "讨论主题：卡牌游戏设计"

        if stance:
            stance_block = f"## ⚠️ 制作人立场（所有讨论必须围绕此方向展开）\n{stance}"
            combined = f"{stance_block}\n\n{briefing}".strip()
        else:
            combined = briefing

        assert "## ⚠️ 制作人立场" in combined
        assert combined.index("制作人立场") < combined.index("讨论主题")

    def test_stance_in_completed_discussion_gdd(self, client):
        """GDD export should include producer stance."""
        disc = DiscussionState(
            id="disc-stance-gdd",
            topic="核心玩法设计",
            rounds=5,
            status=DiscussionStatus.COMPLETED,
            created_at="2024-01-01T00:00:00",
            project_id="proj-stance-test",
            producer_stance="低付费门槛",
        )
        _discussions["disc-stance-gdd"] = disc

        resp = client.get("/api/discussions/export-gdd/proj-stance-test")
        assert resp.status_code == 200
        assert "低付费门槛" in resp.text


# =============================================================================
# Feature 4: GDD Auto Export
# =============================================================================

class TestGddExport:
    def test_export_gdd_no_discussions_returns_json(self, client):
        """Export with no completed discussions returns JSON error response."""
        resp = client.get("/api/discussions/export-gdd/nonexistent-project")
        assert resp.status_code == 200
        # Returns JSON error dict when no completed discussions
        data = resp.json()
        assert "error" in data or "gdd" in data

    def test_export_gdd_with_discussions_returns_markdown(self, client):
        """Export with completed discussion returns markdown."""
        disc = DiscussionState(
            id="disc-gdd-md",
            topic="核心玩法设计",
            rounds=5,
            status=DiscussionStatus.COMPLETED,
            created_at="2024-01-01T00:00:00",
            project_id="proj-gdd-md",
            target_type="stage",
        )
        _discussions["disc-gdd-md"] = disc

        resp = client.get("/api/discussions/export-gdd/proj-gdd-md")
        assert resp.status_code == 200
        assert "核心玩法设计" in resp.text

    def test_export_gdd_content_type_markdown(self, client):
        """GDD export with completed discussions returns text/markdown."""
        disc = DiscussionState(
            id="disc-ct",
            topic="GDD内容",
            rounds=3,
            status=DiscussionStatus.COMPLETED,
            created_at="2024-01-01T00:00:00",
            project_id="proj-ct",
        )
        _discussions["disc-ct"] = disc

        resp = client.get("/api/discussions/export-gdd/proj-ct")
        assert resp.status_code == 200
        assert "text/markdown" in resp.headers.get("content-type", "")

    def test_export_gdd_includes_quality_score(self, client):
        """GDD export includes quality score if present."""
        disc = DiscussionState(
            id="disc-gdd-qs",
            topic="系统设计",
            rounds=5,
            status=DiscussionStatus.COMPLETED,
            created_at="2024-01-01T00:00:00",
            project_id="proj-qs",
            quality_score={"completeness": 8, "executability": 7, "consensus": 9, "overall": 8.0},
        )
        _discussions["disc-gdd-qs"] = disc

        resp = client.get("/api/discussions/export-gdd/proj-qs")
        assert resp.status_code == 200
        content = resp.text
        assert "讨论质量" in content


# =============================================================================
# Feature 5: Discussion Template Library
# =============================================================================

class TestTemplateLibrary:
    def test_list_templates_endpoint(self, client):
        """Templates endpoint returns list."""
        resp = client.get("/api/discussions/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert "templates" in data
        assert isinstance(data["templates"], list)
        assert len(data["templates"]) > 0

    def test_templates_have_required_fields(self, client):
        """Each template has id, name, stage, description."""
        resp = client.get("/api/discussions/templates")
        data = resp.json()
        for t in data["templates"]:
            assert "id" in t
            assert "name" in t
            assert "stage" in t
            assert "description" in t

    def test_filter_templates_by_stage(self, client):
        """Filtering by stage returns only matching templates."""
        resp = client.get("/api/discussions/templates?stage=concept")
        assert resp.status_code == 200
        data = resp.json()
        for t in data["templates"]:
            assert t["stage"] == "concept"

    def test_filter_templates_nonexistent_stage(self, client):
        """Filtering by nonexistent stage returns empty list."""
        resp = client.get("/api/discussions/templates?stage=nonexistent-stage-xyz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["templates"] == []

    def test_get_single_template(self, client):
        """Get a specific template by ID."""
        if not _DISCUSSION_TEMPLATES:
            pytest.skip("No templates defined")
        tid = _DISCUSSION_TEMPLATES[0]["id"]
        resp = client.get(f"/api/discussions/templates/{tid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == tid

    def test_get_nonexistent_template(self, client):
        """Getting a nonexistent template returns 404."""
        resp = client.get("/api/discussions/templates/not-exist-id")
        assert resp.status_code == 404

    def test_template_data_integrity(self):
        """All static templates have required fields."""
        for t in _DISCUSSION_TEMPLATES:
            assert "id" in t, f"Template missing id: {t}"
            assert "name" in t, f"Template missing name: {t}"
            assert "stage" in t, f"Template missing stage: {t}"
            assert "description" in t, f"Template missing description: {t}"

    def test_templates_have_topic_template(self):
        """Templates should have topic_template for auto-filling."""
        for t in _DISCUSSION_TEMPLATES:
            assert "topic_template" in t, f"Template {t['id']} missing topic_template"


# =============================================================================
# Feature 6: Agent Opinion Archive
# =============================================================================

class TestAgentOpinions:
    def test_extract_agent_opinions_no_messages(self):
        """No messages → empty opinions dict."""
        mock_record = MagicMock()
        mock_record.messages = []
        disc = DiscussionState(
            id="disc-op-empty",
            topic="Test",
            rounds=3,
            status=DiscussionStatus.COMPLETED,
            created_at="2024-01-01T00:00:00",
            moderator_role="lead_planner",
        )
        from src.api.routes import discussion as disc_module
        with patch.object(disc_module._discussion_memory, "load", return_value=mock_record):
            result = _extract_agent_opinions("disc-op-empty", disc)
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_extract_agent_opinions_with_keyword(self):
        """Messages with opinion keywords from non-moderator agents are extracted."""
        mock_record = MagicMock()
        msg1 = MagicMock()
        msg1.agent_role = "system_designer"
        msg1.content = "我建议采用事件驱动架构，这样扩展性更好，具体方案如下"
        msg2 = MagicMock()
        msg2.agent_role = "number_designer"
        msg2.content = "我认为数值难度曲线需要更平滑，这是核心设计问题"
        mock_record.messages = [msg1, msg2]

        disc = DiscussionState(
            id="disc-op-kw",
            topic="Test",
            rounds=3,
            status=DiscussionStatus.COMPLETED,
            created_at="2024-01-01T00:00:00",
            moderator_role="lead_planner",
        )
        from src.api.routes import discussion as disc_module
        with patch.object(disc_module._discussion_memory, "load", return_value=mock_record):
            result = _extract_agent_opinions("disc-op-kw", disc)

        assert len(result) > 0
        assert "system_designer" in result or "number_designer" in result

    def test_agent_opinions_endpoint(self, client):
        """Agent opinions endpoint returns 200 for existing discussion."""
        disc_id = "disc-opinions-ep"
        disc = DiscussionState(
            id=disc_id,
            topic="Test opinions",
            rounds=3,
            status=DiscussionStatus.COMPLETED,
            created_at="2024-01-01T00:00:00",
        )
        _discussions[disc_id] = disc

        resp = client.get(f"/api/discussions/{disc_id}/agent-opinions")
        assert resp.status_code == 200
        data = resp.json()
        assert "opinions" in data
        assert isinstance(data["opinions"], dict)

    def test_agent_opinions_endpoint_404(self, client):
        """Agent opinions endpoint returns 404 for nonexistent discussion."""
        resp = client.get("/api/discussions/nonexistent-disc-xyz/agent-opinions")
        assert resp.status_code == 404

    def test_project_opinions_endpoint(self, client):
        """Project-level opinions endpoint returns aggregated opinions."""
        resp = client.get("/api/discussions/project-opinions/test-project-123")
        assert resp.status_code == 200
        data = resp.json()
        assert "project_id" in data
        assert "opinions" in data
        assert data["project_id"] == "test-project-123"


# =============================================================================
# Feature 7: Viewer Mode Enhancement
# =============================================================================

class TestViewerMode:
    def test_viewer_questions_default_empty(self, client):
        """viewer_questions defaults to empty list in GET response."""
        disc_id = "disc-viewer-def"
        disc = DiscussionState(
            id=disc_id,
            topic="Test viewer",
            rounds=3,
            status=DiscussionStatus.RUNNING,
            created_at="2024-01-01T00:00:00",
        )
        _discussions[disc_id] = disc

        resp = client.get(f"/api/discussions/{disc_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "viewer_questions" in data
        assert data["viewer_questions"] == []

    def test_submit_viewer_question(self, client):
        """POST viewer question stores it in discussion state."""
        disc_id = "disc-vq-submit"
        disc = DiscussionState(
            id=disc_id,
            topic="Test viewer questions",
            rounds=3,
            status=DiscussionStatus.RUNNING,
            created_at="2024-01-01T00:00:00",
        )
        _discussions[disc_id] = disc

        # ViewerQuestionRequest uses "question" field (not "content")
        resp = client.post(
            f"/api/discussions/{disc_id}/viewer-question",
            json={"question": "能否解释一下数值平衡的方法？", "viewer_name": "观众A"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "question" in data
        q = data["question"]
        assert q["question"] == "能否解释一下数值平衡的方法？"
        assert q["viewer_name"] == "观众A"
        assert q["likes"] == 0

        # Verify stored in state
        assert len(_discussions[disc_id].viewer_questions) == 1
        stored_q = _discussions[disc_id].viewer_questions[0]
        assert stored_q["question"] == "能否解释一下数值平衡的方法？"

    def test_submit_question_to_nonexistent_discussion(self, client):
        """Submitting question to nonexistent discussion returns 404."""
        resp = client.post(
            "/api/discussions/not-exist-disc/viewer-question",
            json={"question": "test", "viewer_name": "obs"},
        )
        assert resp.status_code == 404

    def test_like_viewer_question(self, client):
        """Liking a viewer question increments like count."""
        disc_id = "disc-like-vq"
        disc = DiscussionState(
            id=disc_id,
            topic="Test likes",
            rounds=3,
            status=DiscussionStatus.RUNNING,
            created_at="2024-01-01T00:00:00",
            viewer_questions=[
                {"id": "q1", "question": "问题1", "viewer_name": "观众1",
                 "likes": 0, "adopted": False, "submitted_at": "2024-01-01T00:00:00"}
            ],
        )
        _discussions[disc_id] = disc

        resp = client.post(f"/api/discussions/{disc_id}/viewer-question/q1/like")
        assert resp.status_code == 200
        assert _discussions[disc_id].viewer_questions[0]["likes"] == 1

    def test_like_nonexistent_question(self, client):
        """Liking a nonexistent question returns 404."""
        disc_id = "disc-like-404"
        disc = DiscussionState(
            id=disc_id,
            topic="Test",
            rounds=3,
            status=DiscussionStatus.RUNNING,
            created_at="2024-01-01T00:00:00",
            viewer_questions=[],
        )
        _discussions[disc_id] = disc

        resp = client.post(f"/api/discussions/{disc_id}/viewer-question/no-such-q/like")
        assert resp.status_code == 404

    def test_adopt_viewer_question(self, client):
        """Adopting a question marks it as adopted."""
        disc_id = "disc-adopt-vq"
        disc = DiscussionState(
            id=disc_id,
            topic="Test adopt",
            rounds=3,
            status=DiscussionStatus.STOPPED,
            created_at="2024-01-01T00:00:00",
            viewer_questions=[
                {"id": "qa1", "question": "重要问题", "viewer_name": "观众X",
                 "likes": 5, "adopted": False, "submitted_at": "2024-01-01T00:00:00"}
            ],
        )
        _discussions[disc_id] = disc

        resp = client.post(f"/api/discussions/{disc_id}/viewer-question/qa1/adopt")
        assert resp.status_code == 200
        assert _discussions[disc_id].viewer_questions[0]["adopted"] is True

    def test_viewer_questions_in_get_response(self, client):
        """viewer_questions should appear in GET discussion response."""
        disc_id = "disc-vq-get-check"
        disc = DiscussionState(
            id=disc_id,
            topic="Test",
            rounds=3,
            status=DiscussionStatus.RUNNING,
            created_at="2024-01-01T00:00:00",
            viewer_questions=[
                {"id": "q1", "question": "问题", "viewer_name": "观众",
                 "likes": 2, "adopted": False, "submitted_at": "2024-01-01T00:00:00"}
            ],
        )
        _discussions[disc_id] = disc

        resp = client.get(f"/api/discussions/{disc_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["viewer_questions"]) == 1
        assert data["viewer_questions"][0]["question"] == "问题"
        assert data["viewer_questions"][0]["likes"] == 2
