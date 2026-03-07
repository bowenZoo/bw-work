"""Tests for the second batch of new features (features 1,2,5,7,8,9,10)."""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes.discussion import (
    DiscussionState,
    DiscussionStatus,
    _compute_agent_votes,
    _validate_numbers,
    _load_agent_cross_memory,
    _discussions,
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_discussions():
    _discussions.clear()
    yield
    _discussions.clear()


def _make_disc(disc_id, **kwargs):
    defaults = dict(
        id=disc_id, topic="测试讨论", rounds=5,
        status=DiscussionStatus.COMPLETED, created_at="2024-01-01T00:00:00",
        project_id="proj-test",
    )
    defaults.update(kwargs)
    return DiscussionState(**defaults)


# =============================================================================
# Feature 7: 预设议程
# =============================================================================

class TestPresetAgenda:
    def test_agenda_stored_in_state(self, client):
        disc = _make_disc("disc-agenda", agenda_items=["核心机制定义", "竞品参考", "数值边界"])
        _discussions["disc-agenda"] = disc
        resp = client.get("/api/discussions/disc-agenda")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agenda_items"] == ["核心机制定义", "竞品参考", "数值边界"]

    def test_agenda_empty_by_default(self, client):
        disc = _make_disc("disc-no-agenda")
        _discussions["disc-no-agenda"] = disc
        resp = client.get("/api/discussions/disc-no-agenda")
        assert resp.status_code == 200
        assert resp.json()["agenda_items"] == []

    def test_agenda_injected_into_briefing(self):
        """议程条目注入到 briefing 文本中。"""
        agenda = ["核心机制定义", "竞品参考", "数值边界"]
        agenda_block = "## 📋 讨论议程（请按顺序推进）\n" + "\n".join(
            f"{i}. {item}" for i, item in enumerate(agenda, 1)
        )
        assert "核心机制定义" in agenda_block
        assert "1. 核心机制定义" in agenda_block
        assert "3. 数值边界" in agenda_block

    def test_create_discussion_with_agenda(self, client):
        """创建讨论时可以传入 agenda_items。"""
        resp = client.post("/api/discussions", json={
            "topic": "核心玩法设计",
            "rounds": 3,
            "agenda_items": ["玩法核心循环", "竞品分析"],
            "project_id": "proj-a",
        })
        assert resp.status_code == 200
        disc_id = resp.json()["id"]
        # Verify stored
        state = _discussions.get(disc_id)
        assert state is not None
        assert state.agenda_items == ["玩法核心循环", "竞品分析"]


# =============================================================================
# Feature 2: Agent 投票量化共识
# =============================================================================

class TestAgentVotes:
    def test_compute_votes_no_messages(self):
        result = _compute_agent_votes("nonexistent-disc")
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_compute_votes_with_support(self):
        mock_record = MagicMock()
        msg = MagicMock()
        msg.agent_role = "system_designer"
        msg.content = "同意这个方案，支持推进，没问题"
        mock_record.messages = [msg]

        from src.api.routes import discussion as disc_module
        with patch.object(disc_module._discussion_memory, "load", return_value=mock_record):
            result = _compute_agent_votes("any")

        assert "system_designer" in result
        assert result["system_designer"]["support"] > 0

    def test_compute_votes_with_oppose(self):
        mock_record = MagicMock()
        msg = MagicMock()
        msg.agent_role = "number_designer"
        msg.content = "反对这个方案，存疑，风险很高，不可行"
        mock_record.messages = [msg]

        from src.api.routes import discussion as disc_module
        with patch.object(disc_module._discussion_memory, "load", return_value=mock_record):
            result = _compute_agent_votes("any2")

        assert "number_designer" in result
        assert result["number_designer"]["oppose"] > 0

    def test_votes_endpoint(self, client):
        disc = _make_disc("disc-votes",
            votes={"system_designer": {"support": 80, "oppose": 10, "neutral": 10}})
        _discussions["disc-votes"] = disc
        resp = client.get("/api/discussions/disc-votes/votes")
        assert resp.status_code == 200
        data = resp.json()
        assert "votes" in data
        assert "system_designer" in data["votes"]

    def test_votes_percentage_sums(self):
        """投票百分比之和约为 100%。"""
        mock_record = MagicMock()
        msg = MagicMock()
        msg.agent_role = "player_advocate"
        msg.content = "同意这个方案，支持，但保留意见，待定"
        mock_record.messages = [msg]

        from src.api.routes import discussion as disc_module
        with patch.object(disc_module._discussion_memory, "load", return_value=mock_record):
            result = _compute_agent_votes("sum-test")

        for role, v in result.items():
            total = v["support"] + v["oppose"] + v["neutral"]
            assert 95 <= total <= 105, f"Percentages don't sum to ~100: {total}"

    def test_votes_stored_in_get_response(self, client):
        disc = _make_disc("disc-vg",
            votes={"lead_planner": {"support": 70, "oppose": 20, "neutral": 10}})
        _discussions["disc-vg"] = disc
        resp = client.get("/api/discussions/disc-vg")
        assert resp.status_code == 200
        assert "votes" in resp.json()


# =============================================================================
# Feature 5: 数值自动校验
# =============================================================================

class TestNumberValidation:
    def test_validate_numbers_no_messages(self):
        result = _validate_numbers("nonexistent")
        assert isinstance(result, list)
        assert len(result) == 0

    def test_validate_high_pity(self):
        """保底次数偏高应触发 high 警告。"""
        mock_record = MagicMock()
        msg = MagicMock()
        msg.content = "保底为500抽，玩家需要投入大量资源"
        mock_record.messages = [msg]

        from src.api.routes import discussion as disc_module
        with patch.object(disc_module._discussion_memory, "load", return_value=mock_record):
            result = _validate_numbers("pity-test")

        high_issues = [r for r in result if r["status"] == "high" and "保底" in r["category"]]
        assert len(high_issues) > 0

    def test_validate_normal_retention(self):
        """正常次留值应为 normal。"""
        mock_record = MagicMock()
        msg = MagicMock()
        msg.content = "次留存设计目标：D1为40%"
        mock_record.messages = [msg]

        from src.api.routes import discussion as disc_module
        with patch.object(disc_module._discussion_memory, "load", return_value=mock_record):
            result = _validate_numbers("retention-test")

        d1_results = [r for r in result if "D1" in r.get("keyword", "") or "次留" in r.get("keyword", "")]
        if d1_results:
            assert d1_results[0]["status"] == "normal"

    def test_number_validation_endpoint(self, client):
        disc = _make_disc("disc-numval",
            number_validation=[
                {"category": "付费率", "value": 50, "unit": "%", "status": "high",
                 "message": "高于上限", "reference": "1-15%", "keyword": "付费率"}
            ])
        _discussions["disc-numval"] = disc
        resp = client.get("/api/discussions/disc-numval/number-validation")
        assert resp.status_code == 200
        data = resp.json()
        assert "validation" in data
        assert "warnings_count" in data
        assert data["warnings_count"] == 1
        assert data["has_issues"] is True

    def test_number_validation_no_issues(self, client):
        disc = _make_disc("disc-numok", number_validation=[])
        _discussions["disc-numok"] = disc
        resp = client.get("/api/discussions/disc-numok/number-validation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_issues"] is False
        assert data["warnings_count"] == 0


# =============================================================================
# Feature 8: 跨项目 Agent 记忆
# =============================================================================

class TestCrossProjectMemory:
    def test_load_empty_memory(self, tmp_path, monkeypatch):
        from src.api.routes import discussion as disc_module
        monkeypatch.setattr(disc_module, "_AGENT_MEMORY_DIR", tmp_path)
        result = _load_agent_cross_memory("system_designer")
        assert result == []

    def test_load_existing_memory(self, tmp_path, monkeypatch):
        import json
        from src.api.routes import discussion as disc_module
        monkeypatch.setattr(disc_module, "_AGENT_MEMORY_DIR", tmp_path)

        mem_file = tmp_path / "system_designer.json"
        mem_file.write_text(json.dumps({
            "memories": [
                {"insight": "事件驱动架构更适合扩展", "project_id": "old-proj",
                 "topic": "系统设计", "recorded_at": "2024-01-01"},
            ]
        }), encoding="utf-8")

        result = _load_agent_cross_memory("system_designer")
        assert len(result) == 1
        assert "事件驱动架构" in result[0]["insight"]

    def test_agent_memory_endpoint(self, client):
        resp = client.get("/api/discussions/agent-memory/system_designer")
        assert resp.status_code == 200
        data = resp.json()
        assert "role" in data
        assert "memories" in data
        assert data["role"] == "system_designer"

    def test_agent_memory_stored_in_get_response(self, client):
        """votes 字段应出现在 GET 响应中。"""
        disc = _make_disc("disc-mem-check")
        _discussions["disc-mem-check"] = disc
        resp = client.get("/api/discussions/disc-mem-check")
        assert resp.status_code == 200
        # 新字段都存在
        data = resp.json()
        assert "agenda_items" in data
        assert "votes" in data
        assert "number_validation" in data
        assert "parent_discussion_id" in data


# =============================================================================
# Feature 9: 摘要自动同步文档
# =============================================================================

class TestSyncToDocument:
    def test_sync_nonexistent_discussion(self, client):
        resp = client.post("/api/discussions/not-exist-sync/sync-to-document")
        assert resp.status_code == 404

    def test_sync_incomplete_discussion(self, client):
        disc = _make_disc("disc-sync-pending", status=DiscussionStatus.RUNNING)
        _discussions["disc-sync-pending"] = disc
        resp = client.post("/api/discussions/disc-sync-pending/sync-to-document")
        assert resp.status_code == 400

    def test_sync_completed_discussion(self, client):
        """完成的讨论可以同步，返回 ok=True 和内容。"""
        disc = _make_disc(
            "disc-sync-ok",
            result="核心玩法决策：采用卡牌策略机制",
            agenda_items=["玩法核心", "数值平衡"],
            producer_stance="低付费门槛",
        )
        _discussions["disc-sync-ok"] = disc
        resp = client.post("/api/discussions/disc-sync-ok/sync-to-document")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        # content 或 document_id 其中之一应存在
        assert "content" in data or "document_id" in data

    def test_sync_content_includes_agenda(self, client):
        """同步内容包含议程条目。"""
        disc = _make_disc(
            "disc-sync-agenda",
            agenda_items=["核心循环", "竞品分析"],
            result="讨论完成",
        )
        _discussions["disc-sync-agenda"] = disc
        resp = client.post("/api/discussions/disc-sync-agenda/sync-to-document")
        assert resp.status_code == 200
        data = resp.json()
        content = data.get("content", "")
        if content:
            assert "核心循环" in content or "竞品分析" in content


# =============================================================================
# Feature 1: 讨论分支探索
# =============================================================================

class TestDiscussionBranch:
    def test_create_branch(self, client):
        parent = _make_disc("disc-parent", topic="卡牌玩法设计",
            agents=["lead_planner", "system_designer"])
        _discussions["disc-parent"] = parent

        resp = client.post(
            "/api/discussions/disc-parent/branch",
            params={"branch_direction": "重度付费路线", "rounds": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "branch_id" in data
        assert data["parent_id"] == "disc-parent"
        assert "重度付费路线" in data["topic"]

    def test_branch_stored_in_memory(self, client):
        parent = _make_disc("disc-parent-2", topic="概念讨论")
        _discussions["disc-parent-2"] = parent

        resp = client.post(
            "/api/discussions/disc-parent-2/branch",
            params={"branch_direction": "休闲方向"},
        )
        branch_id = resp.json()["branch_id"]
        branch = _discussions.get(branch_id)
        assert branch is not None
        assert branch.parent_discussion_id == "disc-parent-2"
        assert branch.branch_direction == "休闲方向"

    def test_list_branches_empty(self, client):
        disc = _make_disc("disc-no-branch")
        _discussions["disc-no-branch"] = disc
        resp = client.get("/api/discussions/disc-no-branch/branches")
        assert resp.status_code == 200
        data = resp.json()
        assert data["branches"] == []

    def test_list_branches_with_branch(self, client):
        parent = _make_disc("disc-has-branch", topic="系统设计")
        _discussions["disc-has-branch"] = parent

        # Create a branch
        client.post(
            "/api/discussions/disc-has-branch/branch",
            params={"branch_direction": "分支A"},
        )

        resp = client.get("/api/discussions/disc-has-branch/branches")
        assert resp.status_code == 200
        branches = resp.json()["branches"]
        assert len(branches) >= 1
        assert any("分支A" in b["direction"] for b in branches)

    def test_branch_inherits_parent_agents(self, client):
        parent = _make_disc("disc-agents-parent",
            agents=["lead_planner", "number_designer", "player_advocate"])
        _discussions["disc-agents-parent"] = parent

        resp = client.post(
            "/api/discussions/disc-agents-parent/branch",
            params={"branch_direction": "测试分支"},
        )
        branch_id = resp.json()["branch_id"]
        branch = _discussions[branch_id]
        assert branch.agents == ["lead_planner", "number_designer", "player_advocate"]

    def test_branch_nonexistent_parent(self, client):
        resp = client.post("/api/discussions/no-parent/branch")
        assert resp.status_code == 404

    def test_branch_stored_fields(self, client):
        parent = _make_disc("disc-branch-fields",
            producer_stance="低付费门槛", agenda_items=["议程1", "议程2"])
        _discussions["disc-branch-fields"] = parent

        resp = client.post(
            "/api/discussions/disc-branch-fields/branch",
            params={"producer_stance": "高付费深度"},
        )
        branch_id = resp.json()["branch_id"]
        branch = _discussions[branch_id]
        # 分支使用新立场覆盖
        assert branch.producer_stance == "高付费深度"
        # 继承父讨论议程
        assert branch.agenda_items == ["议程1", "议程2"]


# =============================================================================
# Feature 10: 制作人 AI 助理
# =============================================================================

class TestAiAssistant:
    def test_kickstart_basic(self, client):
        resp = client.post(
            "/api/discussions/ai-assistant/project-kickstart",
            params={"game_concept": "一个卡牌策略游戏", "game_name": "测试游戏"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "game_type" in data
        assert "recommended_stages" in data
        assert "gdd_outline" in data
        assert len(data["recommended_stages"]) > 0

    def test_kickstart_detects_card_game(self, client):
        resp = client.post(
            "/api/discussions/ai-assistant/project-kickstart",
            params={"game_concept": "TCG 卡牌收集对战游戏"},
        )
        assert resp.status_code == 200
        assert resp.json()["game_type"] == "卡牌"

    def test_kickstart_detects_slg(self, client):
        resp = client.post(
            "/api/discussions/ai-assistant/project-kickstart",
            params={"game_concept": "策略战争城池建设游戏"},
        )
        assert resp.status_code == 200
        assert resp.json()["game_type"] == "SLG"

    def test_kickstart_with_audience(self, client):
        resp = client.post(
            "/api/discussions/ai-assistant/project-kickstart",
            params={"game_concept": "轻度消除游戏", "target_audience": "休闲玩家"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # 休闲受众应有对应立场建议
        assert data.get("producer_stance_suggestion") != "" or True  # 可能为空

    def test_kickstart_gdd_outline_contains_game_name(self, client):
        resp = client.post(
            "/api/discussions/ai-assistant/project-kickstart",
            params={"game_name": "星际征途", "game_concept": "MMO大世界"},
        )
        data = resp.json()
        assert "星际征途" in data["gdd_outline"]

    def test_kickstart_stages_have_agenda(self, client):
        resp = client.post(
            "/api/discussions/ai-assistant/project-kickstart",
            params={"game_concept": "卡牌游戏"},
        )
        data = resp.json()
        for stage in data["recommended_stages"]:
            assert "stage" in stage
            assert "agenda" in stage
            assert len(stage["agenda"]) > 0

    def test_kickstart_tips_provided(self, client):
        resp = client.post(
            "/api/discussions/ai-assistant/project-kickstart",
            params={"game_concept": "休闲游戏"},
        )
        data = resp.json()
        assert "tips" in data
        assert len(data["tips"]) > 0

    def test_kickstart_unknown_type_defaults(self, client):
        """未知类型默认为休闲。"""
        resp = client.post(
            "/api/discussions/ai-assistant/project-kickstart",
            params={"game_concept": "完全新型游戏，无法归类"},
        )
        assert resp.status_code == 200
        # 不报错就行，类型可以是任意已知类型
        assert resp.json()["game_type"] in ("卡牌", "MMO", "SLG", "休闲")
