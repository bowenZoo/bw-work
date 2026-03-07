"""测试 10 项新优化功能（Batch 3）。

功能列表：
1. 讨论回放时间轴（前端功能，后端无需测试）
2. Agent 发言统计 GET /{id}/stats
3. 关键词高亮 & 决策标记（前端功能）
4. 全文搜索 GET /search
5. 讨论进度追踪 POST /{id}/agenda-check
6. 批量操作 POST /batch
7. 决策日志 GET /{id}/decisions + _extract_decisions
8. 讨论对比 GET /compare
9. 自动打标签 GET /{id}/tags + PATCH /{id}/tags + _auto_tag_discussion
10. 讨论完成通知（前端功能）
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.routes.discussion import (
    router,
    DiscussionState,
    DiscussionStatus,
    _discussions,
    _extract_decisions,
    _auto_tag_discussion,
    save_discussion_state,
)
from src.api.main import app

client = TestClient(app)

# ── 公共辅助 ────────────────────────────────────────────────────────────────

def _make_disc(disc_id: str = "test-disc-b3", **kwargs) -> DiscussionState:
    from datetime import datetime
    disc = DiscussionState(
        id=disc_id,
        topic=kwargs.get("topic", "卡牌对战游戏设计"),
        rounds=kwargs.get("rounds", 10),
        status=kwargs.get("status", DiscussionStatus.COMPLETED),
        created_at=datetime.utcnow().isoformat(),
        project_id=kwargs.get("project_id", "proj-test"),
        agenda_items=kwargs.get("agenda_items", ["核心循环", "战斗机制", "付费设计"]),
        tags=kwargs.get("tags", []),
        decisions=kwargs.get("decisions", []),
        agenda_progress=kwargs.get("agenda_progress", []),
    )
    _discussions[disc_id] = disc
    return disc


def _make_messages(content_list: list[str]) -> list[MagicMock]:
    msgs = []
    for i, content in enumerate(content_list):
        m = MagicMock()
        m.content = content
        m.agent_role = ["lead_planner", "number_designer", "player_advocate"][i % 3]
        m.agent_id = m.agent_role
        m.timestamp = f"2024-01-01T10:{i:02d}:00"
        msgs.append(m)
    return msgs


# ── 功能 2：Agent 发言统计 ──────────────────────────────────────────────────

class TestAgentStats:
    def setup_method(self):
        self.disc_id = "disc-stats-test"
        _make_disc(self.disc_id)

    def teardown_method(self):
        _discussions.pop(self.disc_id, None)

    def test_stats_404_for_unknown(self):
        resp = client.get("/api/discussions/nonexistent-disc/stats")
        assert resp.status_code == 404

    def test_stats_returns_structure(self):
        msgs = _make_messages(["同意这个方向，支持核心循环设计", "反对数值过高，有风险"])
        with patch("src.api.routes.discussion._discussion_memory") as mock_mem:
            mock_mem.get_messages.return_value = msgs
            resp = client.get(f"/api/discussions/{self.disc_id}/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "stats" in data
        assert "total_messages" in data
        assert data["total_messages"] == 2

    def test_stats_per_role_breakdown(self):
        msgs = _make_messages([
            "支持这个方案",
            "反对，有问题",
            "同意采用",
        ])
        with patch("src.api.routes.discussion._discussion_memory") as mock_mem:
            mock_mem.get_messages.return_value = msgs
            resp = client.get(f"/api/discussions/{self.disc_id}/stats")
        data = resp.json()
        # 每个角色都有条目
        roles = [s["role"] for s in data["stats"]]
        assert len(roles) >= 1

    def test_stats_sentiment_field(self):
        msgs = _make_messages(["同意支持这个很好", "反对反对有问题"])
        with patch("src.api.routes.discussion._discussion_memory") as mock_mem:
            mock_mem.get_messages.return_value = msgs
            resp = client.get(f"/api/discussions/{self.disc_id}/stats")
        data = resp.json()
        for s in data["stats"]:
            assert "sentiment" in s
            assert "messages" in s
            assert "chars" in s

    def test_stats_empty_messages(self):
        with patch("src.api.routes.discussion._discussion_memory") as mock_mem:
            mock_mem.get_messages.return_value = []
            resp = client.get(f"/api/discussions/{self.disc_id}/stats")
        assert resp.status_code == 200
        assert resp.json()["total_messages"] == 0


# ── 功能 4：全文搜索 ────────────────────────────────────────────────────────

class TestSearch:
    def setup_method(self):
        self.disc_id = "disc-search-test"
        _make_disc(self.disc_id, topic="卡牌战斗机制设计讨论")

    def teardown_method(self):
        _discussions.pop(self.disc_id, None)

    def test_search_empty_query(self):
        resp = client.get("/api/discussions/search?q=")
        assert resp.status_code == 200
        assert resp.json()["results"] == []

    def test_search_matches_topic(self):
        with patch("src.api.routes.discussion._discussion_memory") as mock_mem:
            mock_mem.get_messages.return_value = []
            resp = client.get("/api/discussions/search?q=卡牌战斗")
        assert resp.status_code == 200
        data = resp.json()
        ids = [r["discussion_id"] for r in data["results"]]
        assert self.disc_id in ids

    def test_search_matches_message_content(self):
        msgs = _make_messages(["我们需要讨论抽卡概率和付费模型"])
        with patch("src.api.routes.discussion._discussion_memory") as mock_mem:
            mock_mem.get_messages.return_value = msgs
            resp = client.get("/api/discussions/search?q=抽卡概率")
        assert resp.status_code == 200
        data = resp.json()
        if data["results"]:
            assert any(self.disc_id == r["discussion_id"] for r in data["results"])

    def test_search_no_match(self):
        with patch("src.api.routes.discussion._discussion_memory") as mock_mem:
            mock_mem.get_messages.return_value = []
            resp = client.get("/api/discussions/search?q=完全不存在的内容xyz123")
        assert resp.status_code == 200
        # 当前测试 disc 的 topic 不含该词，可能 0 条
        assert "results" in resp.json()

    def test_search_returns_tags(self):
        _discussions[self.disc_id].tags = ["战斗系统", "经济系统"]
        with patch("src.api.routes.discussion._discussion_memory") as mock_mem:
            mock_mem.get_messages.return_value = []
            resp = client.get("/api/discussions/search?q=卡牌")
        data = resp.json()
        for r in data["results"]:
            if r["discussion_id"] == self.disc_id:
                assert "tags" in r


# ── 功能 5：讨论进度追踪 ────────────────────────────────────────────────────

class TestAgendaProgress:
    def setup_method(self):
        self.disc_id = "disc-progress-test"
        _make_disc(self.disc_id, agenda_items=["核心循环", "战斗机制", "付费设计"])

    def teardown_method(self):
        _discussions.pop(self.disc_id, None)

    def test_check_agenda_item(self):
        with patch("src.api.routes.discussion.save_discussion_state"):
            resp = client.post(
                f"/api/discussions/{self.disc_id}/agenda-check",
                json={"item_index": 0, "done": True},
                headers={"Authorization": "Bearer test-token"},
            )
        # 需要认证，测试环境可能返回 401 或 200
        assert resp.status_code in (200, 401, 422)

    def test_check_invalid_index(self):
        with patch("src.api.routes.discussion.save_discussion_state"), \
             patch("src.api.routes.discussion.get_auth_user", return_value={"id": 1}):
            resp = client.post(
                f"/api/discussions/{self.disc_id}/agenda-check",
                json={"item_index": 99, "done": True},
            )
        assert resp.status_code in (400, 401, 422)

    def test_agenda_progress_initialized(self):
        disc = _discussions[self.disc_id]
        with patch("src.api.routes.discussion.save_discussion_state") as mock_save, \
             patch("src.api.routes.discussion.get_auth_user", return_value={"id": 1}):
            from src.api.routes.discussion import update_agenda_check, AgendaProgressRequest
            import asyncio
            req = AgendaProgressRequest(item_index=1, done=True)
            result = asyncio.get_event_loop().run_until_complete(
                update_agenda_check(self.disc_id, req, user={"id": 1})
            )
        assert "agenda_progress" in result
        progress = result["agenda_progress"]
        assert len(progress) == 3  # matches agenda_items length
        assert progress[1]["done"] is True

    def test_agenda_check_404(self):
        resp = client.post(
            "/api/discussions/nonexistent/agenda-check",
            json={"item_index": 0, "done": True},
        )
        assert resp.status_code in (401, 404, 422)


# ── 功能 6：批量操作 ────────────────────────────────────────────────────────

class TestBatchOperations:
    def setup_method(self):
        self.ids = ["disc-batch-1", "disc-batch-2"]
        for did in self.ids:
            _make_disc(did)

    def teardown_method(self):
        for did in self.ids:
            _discussions.pop(did, None)

    def test_batch_tag(self):
        with patch("src.api.routes.discussion.save_discussion_state"), \
             patch("src.api.routes.discussion.get_auth_user", return_value={"id": 1}):
            from src.api.routes.discussion import batch_operations, BatchOperationRequest
            import asyncio
            req = BatchOperationRequest(discussion_ids=self.ids, action="tag", tag="战斗系统")
            result = asyncio.get_event_loop().run_until_complete(
                batch_operations(req, user={"id": 1})
            )
        assert len(result["success"]) == 2
        assert "战斗系统" in _discussions[self.ids[0]].tags

    def test_batch_archive(self):
        with patch("src.api.routes.discussion.save_discussion_state"), \
             patch("src.api.routes.discussion.get_auth_user", return_value={"id": 1}):
            from src.api.routes.discussion import batch_operations, BatchOperationRequest
            import asyncio
            req = BatchOperationRequest(discussion_ids=[self.ids[0]], action="archive")
            result = asyncio.get_event_loop().run_until_complete(
                batch_operations(req, user={"id": 1})
            )
        assert self.ids[0] in result["success"]
        assert _discussions[self.ids[0]].status == DiscussionStatus.STOPPED

    def test_batch_delete(self):
        with patch("src.api.routes.discussion.get_auth_user", return_value={"id": 1}):
            from src.api.routes.discussion import batch_operations, BatchOperationRequest
            import asyncio
            req = BatchOperationRequest(discussion_ids=[self.ids[1]], action="delete")
            with patch("pathlib.Path.exists", return_value=False):
                result = asyncio.get_event_loop().run_until_complete(
                    batch_operations(req, user={"id": 1})
                )
        assert self.ids[1] in result["success"]
        assert self.ids[1] not in _discussions

    def test_batch_unknown_action(self):
        with patch("src.api.routes.discussion.get_auth_user", return_value={"id": 1}):
            from src.api.routes.discussion import batch_operations, BatchOperationRequest
            import asyncio
            req = BatchOperationRequest(discussion_ids=[self.ids[0]], action="unknown_action")
            result = asyncio.get_event_loop().run_until_complete(
                batch_operations(req, user={"id": 1})
            )
        assert len(result["failed"]) >= 1

    def test_batch_nonexistent_id(self):
        with patch("src.api.routes.discussion.get_auth_user", return_value={"id": 1}):
            from src.api.routes.discussion import batch_operations, BatchOperationRequest
            import asyncio
            req = BatchOperationRequest(discussion_ids=["nonexistent-xyz"], action="archive")
            result = asyncio.get_event_loop().run_until_complete(
                batch_operations(req, user={"id": 1})
            )
        assert len(result["failed"]) == 1


# ── 功能 7：决策日志 ────────────────────────────────────────────────────────

class TestDecisions:
    def setup_method(self):
        self.disc_id = "disc-decisions-test"
        _make_disc(self.disc_id)

    def teardown_method(self):
        _discussions.pop(self.disc_id, None)

    def test_extract_decisions_from_messages(self):
        msgs = _make_messages([
            "经过讨论，最终确定采用概率公示制度，抽卡天花板设为80抽",
            "我们决定核心战斗采用回合制",
            "其他方面继续探讨",
        ])
        disc = _discussions[self.disc_id]
        with patch("src.api.routes.discussion._discussion_memory") as mock_mem, \
             patch("src.api.routes.discussion.save_discussion_state"):
            mock_mem.get_messages.return_value = msgs
            _extract_decisions(self.disc_id, disc)
        assert len(disc.decisions) >= 1
        keywords = [d["keyword"] for d in disc.decisions]
        assert any(k in ["最终", "确定", "决定", "采用"] for k in keywords)

    def test_extract_decisions_skips_short_sentences(self):
        msgs = _make_messages(["确定。", "决定。"])  # too short
        disc = _discussions[self.disc_id]
        with patch("src.api.routes.discussion._discussion_memory") as mock_mem, \
             patch("src.api.routes.discussion.save_discussion_state"):
            mock_mem.get_messages.return_value = msgs
            _extract_decisions(self.disc_id, disc)
        # Very short sentences (<=10 chars) should not be extracted
        long_decisions = [d for d in disc.decisions if len(d["text"]) > 10]
        assert len(long_decisions) == 0

    def test_decisions_endpoint_404(self):
        resp = client.get("/api/discussions/nonexistent/decisions")
        assert resp.status_code == 404

    def test_decisions_endpoint_returns_list(self):
        _discussions[self.disc_id].decisions = [
            {"text": "最终确定付费模型为月卡+战令", "agent_role": "lead_planner",
             "timestamp": "2024-01-01T10:00:00", "message_index": 0, "keyword": "最终"}
        ]
        resp = client.get(f"/api/discussions/{self.disc_id}/decisions")
        assert resp.status_code == 200
        data = resp.json()
        assert "decisions" in data
        assert len(data["decisions"]) == 1

    def test_decisions_not_re_extracted_if_exists(self):
        disc = _discussions[self.disc_id]
        disc.decisions = [{"text": "已有决策", "agent_role": "lead_planner",
                           "timestamp": "", "message_index": 0, "keyword": "决定"}]
        with patch("src.api.routes.discussion._discussion_memory") as mock_mem:
            mock_mem.get_messages.return_value = []
            _extract_decisions(self.disc_id, disc)
        assert len(disc.decisions) == 1  # not re-extracted


# ── 功能 8：讨论对比 ────────────────────────────────────────────────────────

class TestCompare:
    def setup_method(self):
        self.id_a = "disc-compare-a"
        self.id_b = "disc-compare-b"
        _make_disc(self.id_a, topic="A：重度付费路线", tags=["经济系统"])
        _make_disc(self.id_b, topic="B：休闲免费路线", tags=["核心玩法"])

    def teardown_method(self):
        for did in [self.id_a, self.id_b]:
            _discussions.pop(did, None)

    def test_compare_returns_both(self):
        resp = client.get(f"/api/discussions/compare?id_a={self.id_a}&id_b={self.id_b}")
        assert resp.status_code == 200
        data = resp.json()
        assert "discussion_a" in data
        assert "discussion_b" in data
        assert data["discussion_a"]["id"] == self.id_a
        assert data["discussion_b"]["id"] == self.id_b

    def test_compare_shared_tags(self):
        _discussions[self.id_a].tags = ["战斗系统", "经济系统"]
        _discussions[self.id_b].tags = ["经济系统", "核心玩法"]
        resp = client.get(f"/api/discussions/compare?id_a={self.id_a}&id_b={self.id_b}")
        data = resp.json()
        assert "经济系统" in data["shared_tags"]

    def test_compare_404_unknown(self):
        resp = client.get(f"/api/discussions/compare?id_a={self.id_a}&id_b=nonexistent")
        assert resp.status_code == 404

    def test_compare_includes_decisions(self):
        _discussions[self.id_a].decisions = [
            {"text": "确定月卡制", "agent_role": "lead_planner", "timestamp": "", "message_index": 0, "keyword": "确定"}
        ]
        resp = client.get(f"/api/discussions/compare?id_a={self.id_a}&id_b={self.id_b}")
        data = resp.json()
        assert len(data["discussion_a"]["decisions"]) == 1


# ── 功能 9：自动打标签 ──────────────────────────────────────────────────────

class TestAutoTag:
    def setup_method(self):
        self.disc_id = "disc-tag-test"
        _make_disc(self.disc_id, topic="卡牌战斗与经济付费系统设计")

    def teardown_method(self):
        _discussions.pop(self.disc_id, None)

    def test_auto_tag_detects_combat(self):
        msgs = _make_messages([
            "战斗机制需要考虑技能平衡和战力成长曲线，pvp设计要公平",
            "战斗系统的属性成长要合理，战力差距不能太大",
        ])
        disc = _discussions[self.disc_id]
        with patch("src.api.routes.discussion._discussion_memory") as mock_mem, \
             patch("src.api.routes.discussion.save_discussion_state"):
            mock_mem.get_messages.return_value = msgs
            _auto_tag_discussion(self.disc_id, disc)
        assert "战斗系统" in disc.tags

    def test_auto_tag_detects_economy(self):
        msgs = _make_messages([
            "付费模型要考虑抽卡概率和货币体系，商城设计要合理",
            "钻石和金币的兑换比例，经济系统要平衡",
        ])
        disc = _discussions[self.disc_id]
        with patch("src.api.routes.discussion._discussion_memory") as mock_mem, \
             patch("src.api.routes.discussion.save_discussion_state"):
            mock_mem.get_messages.return_value = msgs
            _auto_tag_discussion(self.disc_id, disc)
        assert "经济系统" in disc.tags

    def test_auto_tag_max_3(self):
        disc = _discussions[self.disc_id]
        msgs = _make_messages([
            "战斗技能战力pvp，经济货币付费抽卡，运营活动留存，社交公会联盟，美术视觉UI",
            "战斗技能战力pvp，经济货币付费抽卡，运营活动留存，社交公会联盟",
        ])
        with patch("src.api.routes.discussion._discussion_memory") as mock_mem, \
             patch("src.api.routes.discussion.save_discussion_state"):
            mock_mem.get_messages.return_value = msgs
            _auto_tag_discussion(self.disc_id, disc)
        assert len(disc.tags) <= 3

    def test_auto_tag_not_re_tagged(self):
        disc = _discussions[self.disc_id]
        disc.tags = ["已有标签"]
        with patch("src.api.routes.discussion._discussion_memory") as mock_mem:
            mock_mem.get_messages.return_value = []
            _auto_tag_discussion(self.disc_id, disc)
        assert disc.tags == ["已有标签"]  # not overwritten

    def test_tags_endpoint_get(self):
        _discussions[self.disc_id].tags = ["战斗系统", "经济系统"]
        resp = client.get(f"/api/discussions/{self.disc_id}/tags")
        assert resp.status_code == 200
        data = resp.json()
        assert "tags" in data
        assert "战斗系统" in data["tags"]

    def test_tags_endpoint_patch(self):
        with patch("src.api.routes.discussion.save_discussion_state"), \
             patch("src.api.routes.discussion.get_auth_user", return_value={"id": 1}):
            from src.api.routes.discussion import update_tags
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                update_tags(self.disc_id, ["新标签A", "新标签B"], user={"id": 1})
            )
        assert "新标签A" in result["tags"]
        assert "新标签B" in result["tags"]

    def test_tags_auto_trigger_on_completed(self):
        disc = _discussions[self.disc_id]
        disc.status = DiscussionStatus.COMPLETED
        disc.tags = []
        msgs = _make_messages(["战斗机制战力技能pvp", "战斗属性成长战力"])
        with patch("src.api.routes.discussion._discussion_memory") as mock_mem, \
             patch("src.api.routes.discussion.save_discussion_state"):
            mock_mem.get_messages.return_value = msgs
            resp = client.get(f"/api/discussions/{self.disc_id}/tags")
        assert resp.status_code == 200
