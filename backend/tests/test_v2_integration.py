"""Comprehensive integration tests for Discussion V2 API.

Tests all V2 endpoints:
- Global discussion (current) API
- Agenda management API
- Discussion chain API
- Continue discussion API
- Mention parser
- WebSocket events
- Concurrent operations
"""
import threading
import time

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes.discussion import (
    AttachmentInfo,
    DiscussionState,
    DiscussionStatus,
    _discussion_agendas,
    _discussions,
    get_current_discussion,
    get_discussion_agenda,
    get_discussion_state,
    save_discussion_state,
    set_current_discussion,
    set_discussion_agenda,
)
from src.api.websocket.events import (
    AgentStatus,
    create_agenda_event,
    create_agenda_init_event,
    create_agenda_item_add_event,
    create_agenda_item_complete_event,
    create_agenda_item_skip_event,
    create_agenda_item_start_event,
    create_error_event,
    create_message_event,
    create_status_event,
)
from src.crew.mention_parser import get_all_roles, parse_mentioned_roles
from src.models.agenda import Agenda, AgendaItem, AgendaItemStatus, AgendaSummaryDetails


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset all global state before/after each test."""
    set_current_discussion(None)
    _discussion_agendas.clear()
    # Clean up test discussions from _discussions dict
    test_ids = [k for k in _discussions if k.startswith("test-")]
    for k in test_ids:
        del _discussions[k]
    yield
    set_current_discussion(None)
    _discussion_agendas.clear()
    test_ids = [k for k in _discussions if k.startswith("test-")]
    for k in test_ids:
        del _discussions[k]


def _make_discussion(
    id: str = "test-001",
    topic: str = "测试话题",
    status: DiscussionStatus = DiscussionStatus.RUNNING,
    **kwargs,
) -> DiscussionState:
    """Helper to create a DiscussionState."""
    return DiscussionState(
        id=id,
        topic=topic,
        rounds=3,
        status=status,
        created_at="2026-02-06T00:00:00",
        **kwargs,
    )


# ==============================================================================
# 1. Global Discussion API Tests
# ==============================================================================


class TestGlobalDiscussionAPI:
    """Tests for GET/POST /api/discussions/current."""

    def test_get_current_none(self, client):
        """无活跃讨论时返回 null。"""
        resp = client.get("/api/discussions/current")
        assert resp.status_code == 200
        assert resp.json() is None

    def test_get_current_with_discussion(self, client):
        """有活跃讨论时返回正确数据。"""
        disc = _make_discussion(topic="全局讨论测试")
        set_current_discussion(disc)

        resp = client.get("/api/discussions/current")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "test-001"
        assert data["topic"] == "全局讨论测试"
        assert data["status"] == "running"
        assert data["is_continuation"] is False

    def test_get_current_with_attachment(self, client):
        """带附件的讨论返回附件信息。"""
        disc = _make_discussion(
            attachment=AttachmentInfo(filename="gdd.md", content="# GDD\n内容"),
        )
        set_current_discussion(disc)

        resp = client.get("/api/discussions/current")
        data = resp.json()
        assert data["attachment"]["filename"] == "gdd.md"
        assert "GDD" in data["attachment"]["content"]

    def test_get_current_continuation(self, client):
        """续前讨论返回 is_continuation=True。"""
        disc = _make_discussion(continued_from="original-001")
        set_current_discussion(disc)

        resp = client.get("/api/discussions/current")
        data = resp.json()
        assert data["continued_from"] == "original-001"
        assert data["is_continuation"] is True


class TestJoinDiscussion:
    """Tests for POST /api/discussions/current/join."""

    def test_join_no_discussion(self, client):
        """无活跃讨论时 join 返回空数据。"""
        resp = client.post("/api/discussions/current/join")
        assert resp.status_code == 200
        data = resp.json()
        assert data["discussion"] is None
        assert data["messages"] == []

    def test_join_with_discussion(self, client):
        """有活跃讨论时 join 返回讨论状态。"""
        disc = _make_discussion(id="test-join")
        set_current_discussion(disc)

        resp = client.post("/api/discussions/current/join")
        assert resp.status_code == 200
        data = resp.json()
        assert data["discussion"]["id"] == "test-join"
        assert isinstance(data["messages"], list)


# ==============================================================================
# 2. Agenda API Tests
# ==============================================================================


class TestAgendaAPI:
    """Tests for /api/discussions/current/agenda endpoints."""

    def test_get_agenda_no_discussion(self, client):
        """无活跃讨论时获取议程返回 404。"""
        resp = client.get("/api/discussions/current/agenda")
        assert resp.status_code == 404

    def test_get_agenda_empty(self, client):
        """有讨论但无议程时返回空列表。"""
        set_current_discussion(_make_discussion())
        resp = client.get("/api/discussions/current/agenda")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["current_index"] == 0

    def test_get_agenda_with_items(self, client):
        """返回完整议程列表。"""
        disc = _make_discussion()
        set_current_discussion(disc)

        agenda = Agenda()
        agenda.add_item("核心玩法", "定义核心循环")
        agenda.add_item("付费模式", "商业化方案")
        agenda.add_item("数值平衡", "经济系统")
        set_discussion_agenda(disc.id, agenda)

        resp = client.get("/api/discussions/current/agenda")
        data = resp.json()
        assert len(data["items"]) == 3
        assert data["items"][0]["title"] == "核心玩法"
        assert data["items"][0]["status"] == "pending"
        assert data["items"][1]["title"] == "付费模式"
        assert data["items"][2]["title"] == "数值平衡"

    def test_add_agenda_item(self, client):
        """添加新议题。"""
        disc = _make_discussion()
        set_current_discussion(disc)

        resp = client.post(
            "/api/discussions/current/agenda/items",
            json={"title": "新手引导", "description": "引导流程设计"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["item"]["title"] == "新手引导"
        assert data["item"]["description"] == "引导流程设计"
        assert data["item"]["status"] == "pending"
        assert "已添加议题" in data["message"]

        # 验证议程中确实有了
        resp2 = client.get("/api/discussions/current/agenda")
        assert len(resp2.json()["items"]) == 1

    def test_add_agenda_item_no_discussion(self, client):
        """无活跃讨论时添加议题返回 404。"""
        resp = client.post(
            "/api/discussions/current/agenda/items",
            json={"title": "测试"},
        )
        assert resp.status_code == 404

    def test_add_agenda_item_validation(self, client):
        """议题标题为空时返回验证错误。"""
        set_current_discussion(_make_discussion())
        resp = client.post(
            "/api/discussions/current/agenda/items",
            json={"title": ""},
        )
        assert resp.status_code == 422  # Validation error

    def test_skip_agenda_item(self, client):
        """跳过议题。"""
        disc = _make_discussion()
        set_current_discussion(disc)

        agenda = Agenda()
        item = agenda.add_item("跳过测试")
        set_discussion_agenda(disc.id, agenda)

        resp = client.post(f"/api/discussions/current/agenda/items/{item.id}/skip")
        assert resp.status_code == 200
        assert resp.json()["status"] == "skipped"

    def test_skip_nonexistent_item(self, client):
        """跳过不存在的议题返回 404。"""
        disc = _make_discussion()
        set_current_discussion(disc)
        agenda = Agenda()
        set_discussion_agenda(disc.id, agenda)

        resp = client.post("/api/discussions/current/agenda/items/nonexistent/skip")
        assert resp.status_code == 404

    def test_skip_completed_item(self, client):
        """跳过已完成议题返回 404。"""
        disc = _make_discussion()
        set_current_discussion(disc)

        agenda = Agenda()
        item = agenda.add_item("已完成")
        item.complete("小结")
        set_discussion_agenda(disc.id, agenda)

        resp = client.post(f"/api/discussions/current/agenda/items/{item.id}/skip")
        assert resp.status_code == 404

    def test_get_item_summary_completed(self, client):
        """获取已完成议题的小结。"""
        disc = _make_discussion()
        set_current_discussion(disc)

        agenda = Agenda()
        item = agenda.add_item("小结测试")
        details = AgendaSummaryDetails(
            conclusions=["采用方案A"],
            viewpoints={"系统策划": "技术可行"},
            open_questions=["需要进一步验证"],
            next_steps=["制作原型"],
        )
        item.complete("完整小结内容", details)
        set_discussion_agenda(disc.id, agenda)

        resp = client.get(f"/api/discussions/current/agenda/items/{item.id}/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "小结测试"
        assert data["summary"] == "完整小结内容"
        assert "采用方案A" in data["summary_details"]["conclusions"]
        assert "系统策划" in data["summary_details"]["viewpoints"]

    def test_get_item_summary_not_completed(self, client):
        """获取未完成议题小结返回 400。"""
        disc = _make_discussion()
        set_current_discussion(disc)

        agenda = Agenda()
        item = agenda.add_item("未完成")
        set_discussion_agenda(disc.id, agenda)

        resp = client.get(f"/api/discussions/current/agenda/items/{item.id}/summary")
        assert resp.status_code == 400


# ==============================================================================
# 3. Discussion List & Messages API Tests
# ==============================================================================


class TestDiscussionListAPI:
    """Tests for GET /api/discussions."""

    def test_list_empty(self, client):
        """空列表返回。"""
        resp = client.get("/api/discussions")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["items"], list)
        assert data["hasMore"] is False

    def test_list_with_in_memory_discussions(self, client):
        """内存中的讨论可以列出。"""
        for i in range(3):
            disc = _make_discussion(
                id=f"test-list-{i}",
                topic=f"话题{i}",
                status=DiscussionStatus.COMPLETED,
                completed_at="2026-02-06T01:00:00",
                result="讨论结果",
            )
            save_discussion_state(disc)

        resp = client.get("/api/discussions")
        assert resp.status_code == 200
        # May include in-memory items from _discussions dict


class TestDiscussionGetAPI:
    """Tests for GET /api/discussions/{id}."""

    def test_get_existing(self, client):
        """获取已存在的讨论。"""
        disc = _make_discussion(id="test-get-1", topic="获取测试")
        save_discussion_state(disc)

        resp = client.get("/api/discussions/test-get-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "test-get-1"
        assert data["topic"] == "获取测试"

    def test_get_nonexistent(self, client):
        """获取不存在的讨论返回 404。"""
        resp = client.get("/api/discussions/nonexistent")
        assert resp.status_code == 404

    def test_get_with_continuation_fields(self, client):
        """续前讨论返回 continued_from 和 is_continuation。"""
        disc = _make_discussion(
            id="test-get-cont",
            continued_from="test-original",
        )
        save_discussion_state(disc)

        resp = client.get("/api/discussions/test-get-cont")
        data = resp.json()
        assert data["continued_from"] == "test-original"
        assert data["is_continuation"] is True


class TestDiscussionMessagesAPI:
    """Tests for GET /api/discussions/{id}/messages."""

    def test_get_messages_nonexistent(self, client):
        """不存在的讨论返回 404。"""
        resp = client.get("/api/discussions/nonexistent/messages")
        assert resp.status_code == 404

    def test_get_messages_with_result(self, client):
        """有结果的讨论返回结果作为消息。"""
        disc = _make_discussion(
            id="test-msg-1",
            status=DiscussionStatus.COMPLETED,
            result="讨论结果内容",
            completed_at="2026-02-06T01:00:00",
        )
        save_discussion_state(disc)

        resp = client.get("/api/discussions/test-msg-1/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert data["discussion"]["topic"] == "测试话题"
        assert len(data["messages"]) == 1
        assert data["messages"][0]["content"] == "讨论结果内容"

    def test_get_messages_no_result(self, client):
        """无结果的讨论返回空消息列表。"""
        disc = _make_discussion(id="test-msg-2", status=DiscussionStatus.RUNNING)
        save_discussion_state(disc)

        resp = client.get("/api/discussions/test-msg-2/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert data["messages"] == []


# ==============================================================================
# 4. Discussion Chain API Tests
# ==============================================================================


class TestDiscussionChainAPI:
    """Tests for GET /api/discussions/{id}/chain."""

    def test_chain_single_discussion(self, client):
        """单个讨论的链只有自己。"""
        disc = _make_discussion(id="test-chain-1")
        save_discussion_state(disc)

        resp = client.get("/api/discussions/test-chain-1/chain")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["chain"]) == 1
        assert data["chain"][0]["id"] == "test-chain-1"
        assert data["chain"][0]["is_origin"] is True
        assert data["current_index"] == 0

    def test_chain_two_levels(self, client):
        """两级讨论链。"""
        original = _make_discussion(
            id="test-chain-orig",
            topic="原始讨论",
            status=DiscussionStatus.COMPLETED,
        )
        save_discussion_state(original)

        continuation = _make_discussion(
            id="test-chain-cont",
            topic="续前讨论",
            continued_from="test-chain-orig",
        )
        save_discussion_state(continuation)

        resp = client.get("/api/discussions/test-chain-cont/chain")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["chain"]) == 2
        assert data["chain"][0]["id"] == "test-chain-orig"
        assert data["chain"][0]["is_origin"] is True
        assert data["chain"][1]["id"] == "test-chain-cont"
        assert data["chain"][1]["is_origin"] is False
        assert data["current_index"] == 1

    def test_chain_three_levels(self, client):
        """三级讨论链。"""
        d1 = _make_discussion(id="test-ch-1", topic="第1次", status=DiscussionStatus.COMPLETED)
        save_discussion_state(d1)

        d2 = _make_discussion(
            id="test-ch-2", topic="第2次", status=DiscussionStatus.COMPLETED,
            continued_from="test-ch-1",
        )
        save_discussion_state(d2)

        d3 = _make_discussion(
            id="test-ch-3", topic="第3次", continued_from="test-ch-2",
        )
        save_discussion_state(d3)

        resp = client.get("/api/discussions/test-ch-3/chain")
        data = resp.json()
        assert len(data["chain"]) == 3
        assert data["chain"][0]["id"] == "test-ch-1"
        assert data["chain"][2]["id"] == "test-ch-3"
        assert data["current_index"] == 2

    def test_chain_nonexistent(self, client):
        """不存在的讨论返回 404。"""
        resp = client.get("/api/discussions/nonexistent/chain")
        assert resp.status_code == 404


# ==============================================================================
# 5. Continue Discussion API Tests
# ==============================================================================


class TestContinueDiscussionAPI:
    """Tests for POST /api/discussions/{id}/continue."""

    def test_continue_nonexistent(self, client):
        """续前不存在的讨论返回 404。"""
        resp = client.post(
            "/api/discussions/nonexistent/continue",
            json={"follow_up": "继续讨论"},
        )
        assert resp.status_code == 404

    def test_continue_running_discussion(self, client):
        """续前运行中的讨论返回 400。"""
        disc = _make_discussion(id="test-cont-running", status=DiscussionStatus.RUNNING)
        save_discussion_state(disc)

        resp = client.post(
            "/api/discussions/test-cont-running/continue",
            json={"follow_up": "继续"},
        )
        assert resp.status_code == 400

    def test_continue_validation(self, client):
        """空的 follow_up 返回验证错误。"""
        disc = _make_discussion(id="test-cont-val", status=DiscussionStatus.COMPLETED)
        save_discussion_state(disc)

        resp = client.post(
            "/api/discussions/test-cont-val/continue",
            json={"follow_up": ""},
        )
        assert resp.status_code == 422


# ==============================================================================
# 6. Mention Parser Tests
# ==============================================================================


class TestMentionParserIntegration:
    """Integration tests for mention parser."""

    def test_all_roles_defined(self):
        """所有角色都有定义。"""
        roles = get_all_roles()
        assert "系统策划" in roles
        assert "数值策划" in roles
        assert "玩家代言人" in roles

    def test_parse_lead_planner_output(self):
        """解析主策划的实际输出。"""
        text = "好的，关于核心玩法的问题，我想请系统策划和数值策划分别从技术可行性和数值平衡两个角度来分析一下。"
        roles = parse_mentioned_roles(text)
        assert "系统策划" in roles
        assert "数值策划" in roles
        assert "玩家代言人" not in roles

    def test_parse_all_three(self):
        """同时提到三个角色。"""
        text = "这个问题涉及面很广，请系统策划、数值策划和玩家代言人都发表一下看法。"
        roles = parse_mentioned_roles(text)
        assert len(roles) == 3

    def test_parse_alias(self):
        """使用别名识别。"""
        text = "架构方面的问题交给系统来分析，平衡性问题请数值看看。"
        roles = parse_mentioned_roles(text)
        assert "系统策划" in roles
        assert "数值策划" in roles

    def test_parse_no_mention(self):
        """无点名返回空列表。"""
        text = "这是一个很好的问题，我先总结一下。"
        roles = parse_mentioned_roles(text)
        assert len(roles) == 0

    def test_parse_empty_string(self):
        """空字符串返回空列表。"""
        assert len(parse_mentioned_roles("")) == 0

    def test_parse_user_perspective(self):
        """玩家视角的别名。"""
        text = "从用户体验的角度来看，需要玩家代言人给出评估。"
        roles = parse_mentioned_roles(text)
        assert "玩家代言人" in roles


# ==============================================================================
# 7. WebSocket Events Tests
# ==============================================================================


class TestWebSocketEvents:
    """Tests for WebSocket event creation."""

    def test_create_message_event(self):
        """消息事件包含正确字段。"""
        event = create_message_event(
            discussion_id="test-ws-1",
            agent_id="system_designer",
            agent_role="系统策划",
            content="技术上可行",
            sequence=5,
        )
        d = event.to_dict()
        assert d["type"] == "message"
        assert d["data"]["agent_id"] == "system_designer"
        assert d["data"]["agent_role"] == "系统策划"
        assert d["data"]["content"] == "技术上可行"
        assert d["data"]["sequence"] == 5

    def test_create_message_event_without_sequence(self):
        """不带序号的消息事件。"""
        event = create_message_event(
            discussion_id="test-ws-2",
            agent_id="lead_planner",
            agent_role="主策划",
            content="开始讨论",
        )
        d = event.to_dict()
        assert d["type"] == "message"
        assert d["data"].get("sequence") is None

    def test_create_status_event(self):
        """状态事件。"""
        event = create_status_event(
            discussion_id="test-ws-3",
            agent_id="system_designer",
            agent_role="系统策划",
            status=AgentStatus.THINKING,
        )
        d = event.to_dict()
        assert d["type"] == "status"
        assert d["data"]["agent_id"] == "system_designer"
        assert d["data"]["status"] == "thinking"

    def test_create_error_event(self):
        """错误事件。"""
        event = create_error_event(
            discussion_id="test-ws-4",
            content="连接失败",
        )
        d = event.to_dict()
        assert d["type"] == "error"
        assert "连接失败" in d["data"]["content"]

    def test_create_agenda_init_event(self):
        """议程初始化事件。"""
        agenda_data = {
            "items": [
                {"id": "1", "title": "核心玩法", "status": "pending"},
                {"id": "2", "title": "付费模式", "status": "pending"},
            ],
            "current_index": 0,
        }
        event = create_agenda_init_event(
            discussion_id="test-ws-5",
            agenda=agenda_data,
        )
        d = event.to_dict()
        assert d["type"] == "agenda"
        assert d["data"]["event_type"] == "agenda_init"

    def test_create_agenda_item_start_event(self):
        """议题开始事件。"""
        event = create_agenda_item_start_event(
            discussion_id="test-ws-6",
            item_id="item-1",
            title="核心玩法",
            current_index=0,
        )
        d = event.to_dict()
        assert d["type"] == "agenda"
        assert d["data"]["event_type"] == "item_start"
        assert d["data"]["item_id"] == "item-1"

    def test_create_agenda_item_complete_event(self):
        """议题完成事件。"""
        event = create_agenda_item_complete_event(
            discussion_id="test-ws-7",
            item_id="item-1",
            title="核心玩法",
            summary="达成共识",
            current_index=1,
        )
        d = event.to_dict()
        assert d["type"] == "agenda"
        assert d["data"]["event_type"] == "item_complete"
        assert d["data"]["summary"] == "达成共识"

    def test_create_agenda_item_skip_event(self):
        """议题跳过事件。"""
        event = create_agenda_item_skip_event(
            discussion_id="test-ws-8",
            item_id="item-2",
            title="付费模式",
            current_index=2,
        )
        d = event.to_dict()
        assert d["type"] == "agenda"
        assert d["data"]["event_type"] == "item_skip"

    def test_create_agenda_item_add_event(self):
        """议题添加事件。"""
        event = create_agenda_item_add_event(
            discussion_id="test-ws-9",
            item_id="item-3",
            title="新议题",
        )
        d = event.to_dict()
        assert d["type"] == "agenda"
        assert d["data"]["event_type"] == "item_add"
        assert d["data"]["title"] == "新议题"


# ==============================================================================
# 8. Agenda Model Tests
# ==============================================================================


class TestAgendaModel:
    """Tests for Agenda data model."""

    def test_create_agenda(self):
        """创建空议程。"""
        agenda = Agenda()
        assert len(agenda.items) == 0
        assert agenda.current_index == 0
        assert agenda.is_completed is True  # Empty agenda is "completed"

    def test_add_items(self):
        """添加议题。"""
        agenda = Agenda()
        item1 = agenda.add_item("核心玩法", "核心循环")
        item2 = agenda.add_item("付费模式")

        assert len(agenda.items) == 2
        assert item1.title == "核心玩法"
        assert item1.description == "核心循环"
        assert item2.title == "付费模式"
        assert item2.description is None

    def test_start_current(self):
        """开始当前议题。"""
        agenda = Agenda()
        agenda.add_item("核心玩法")
        item = agenda.start_current()

        assert item is not None
        assert item.status == AgendaItemStatus.IN_PROGRESS
        assert item.started_at is not None

    def test_complete_current(self):
        """完成当前议题并推进。"""
        agenda = Agenda()
        agenda.add_item("第一个")
        agenda.add_item("第二个")

        agenda.start_current()
        completed = agenda.complete_current("小结内容")

        assert completed is not None
        assert completed.status == AgendaItemStatus.COMPLETED
        assert completed.summary == "小结内容"
        assert agenda.current_index == 1

    def test_complete_with_details(self):
        """带详细信息完成。"""
        agenda = Agenda()
        agenda.add_item("测试")

        details = AgendaSummaryDetails(
            conclusions=["结论1"],
            viewpoints={"A": "观点A"},
            open_questions=["问题1"],
            next_steps=["步骤1"],
        )
        agenda.start_current()
        completed = agenda.complete_current("小结", details)

        assert completed.summary_details is not None
        assert completed.summary_details.conclusions == ["结论1"]

    def test_skip_item(self):
        """跳过议题。"""
        agenda = Agenda()
        item1 = agenda.add_item("会跳过")
        agenda.add_item("不会跳过")

        skipped = agenda.skip_item(item1.id)
        assert skipped is not None
        assert skipped.status == AgendaItemStatus.SKIPPED

    def test_progress(self):
        """进度统计。"""
        agenda = Agenda()
        agenda.add_item("完成")
        agenda.add_item("跳过")
        agenda.add_item("待定")

        agenda.start_current()
        agenda.complete_current("小结")  # index -> 1
        agenda.items[1].skip()  # Skip second

        completed, total = agenda.progress
        assert completed == 2
        assert total == 3

    def test_from_items_list(self):
        """从字典列表创建议程。"""
        items_data = [
            {"title": "核心玩法", "description": "核心循环"},
            {"title": "付费模式"},
        ]
        agenda = Agenda.from_items_list(items_data)

        assert len(agenda.items) == 2
        assert agenda.items[0].title == "核心玩法"
        assert agenda.items[1].description is None

    def test_to_dict(self):
        """序列化为字典。"""
        agenda = Agenda()
        agenda.add_item("测试")
        d = agenda.to_dict()

        assert "items" in d
        assert "current_index" in d
        assert len(d["items"]) == 1
        assert d["items"][0]["title"] == "测试"

    def test_get_item_by_id(self):
        """通过 ID 获取议题。"""
        agenda = Agenda()
        item = agenda.add_item("查找")

        found = agenda.get_item_by_id(item.id)
        assert found is not None
        assert found.title == "查找"

        not_found = agenda.get_item_by_id("nonexistent")
        assert not_found is None


# ==============================================================================
# 9. Deadlock / Concurrency Tests
# ==============================================================================


class TestConcurrency:
    """Tests for thread-safety of global state."""

    def test_rlock_no_deadlock(self):
        """验证 RLock 不会死锁（之前是 Lock 会死锁）。"""
        # Simulate what create_current_discussion does:
        # acquire lock -> call get_current_discussion (which also acquires lock)
        from src.api.routes.discussion import _current_discussion_lock

        result = {"deadlocked": True}

        def test_reentrant():
            with _current_discussion_lock:
                # This should NOT deadlock with RLock
                with _current_discussion_lock:
                    result["deadlocked"] = False

        t = threading.Thread(target=test_reentrant)
        t.start()
        t.join(timeout=2.0)  # 2 second timeout

        assert not result["deadlocked"], "RLock should allow re-entrant acquisition"

    def test_concurrent_set_get_discussion(self):
        """并发设置和读取讨论状态。"""
        errors = []

        def setter():
            try:
                for i in range(50):
                    disc = _make_discussion(id=f"test-conc-{i}")
                    set_current_discussion(disc)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def getter():
            try:
                for _ in range(50):
                    get_current_discussion()
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=setter),
            threading.Thread(target=getter),
            threading.Thread(target=getter),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert len(errors) == 0, f"Concurrent access errors: {errors}"


# ==============================================================================
# 10. Route Conflict Tests
# ==============================================================================


class TestRouteConflicts:
    """Tests to verify routes don't conflict."""

    def test_current_vs_discussion_id(self, client):
        """确保 /current 不会被当成 /{discussion_id}。"""
        # /current should NOT 404 (it returns null when no discussion)
        resp = client.get("/api/discussions/current")
        assert resp.status_code == 200

    def test_current_agenda_route(self, client):
        """确保 /current/agenda 路由可达。"""
        set_current_discussion(_make_discussion())
        resp = client.get("/api/discussions/current/agenda")
        assert resp.status_code == 200

    def test_real_discussion_id_route(self, client):
        """确保真实 discussion_id 路由可用。"""
        disc = _make_discussion(id="test-real-id")
        save_discussion_state(disc)

        resp = client.get("/api/discussions/test-real-id")
        assert resp.status_code == 200
        assert resp.json()["id"] == "test-real-id"

    def test_discussion_chain_route(self, client):
        """确保 /{id}/chain 路由可达。"""
        disc = _make_discussion(id="test-chain-route")
        save_discussion_state(disc)

        resp = client.get("/api/discussions/test-chain-route/chain")
        assert resp.status_code == 200

    def test_discussion_messages_route(self, client):
        """确保 /{id}/messages 路由可达。"""
        disc = _make_discussion(id="test-msg-route", result="result")
        save_discussion_state(disc)

        resp = client.get("/api/discussions/test-msg-route/messages")
        assert resp.status_code == 200


# ==============================================================================
# 11. Discussion Crew Agenda Summary Parsing
# ==============================================================================


class TestDiscussionCrewAgendaSummary:
    """Tests for DiscussionCrew._parse_agenda_summary."""

    def test_full_summary(self):
        """解析完整议题小结。"""
        from src.crew.discussion_crew import DiscussionCrew

        crew = DiscussionCrew()
        text = """# 议题小结：付费模式设计

## 讨论结论
- 采用 Battle Pass + 外观商城
- 不做数值付费
- 首周优惠促销

## 各方观点
- 系统策划：技术实现无障碍
- 数值策划：定价需要AB测试
- 玩家代言人：玩家更接受外观付费

## 遗留问题
- 定价策略待定
- 地区差异定价

## 下一步行动
- 竞品分析
- 玩家调研
"""
        details = crew._parse_agenda_summary(text)
        assert len(details.conclusions) == 3
        assert len(details.viewpoints) == 3
        assert len(details.open_questions) == 2
        assert len(details.next_steps) == 2

    def test_empty_summary(self):
        """解析空文本。"""
        from src.crew.discussion_crew import DiscussionCrew

        crew = DiscussionCrew()
        details = crew._parse_agenda_summary("")
        assert len(details.conclusions) == 0
        assert len(details.viewpoints) == 0


# ==============================================================================
# 12. Continuation Context Building
# ==============================================================================


class TestContinuationContext:
    """Tests for _build_continuation_context."""

    def test_build_context_basic(self):
        """构建基本的续前上下文。"""
        from src.api.routes.discussion import _build_continuation_context
        from src.memory.base import Discussion, Message
        from datetime import datetime

        original = _make_discussion(id="test-ctx-orig", topic="原始话题")
        stored = Discussion(
            id="test-ctx-orig",
            project_id="default",
            topic="原始话题",
            messages=[
                Message(
                    id="m1",
                    agent_id="lead_planner",
                    agent_role="主策划",
                    content="这是主策划的发言",
                    timestamp=datetime.now(),
                ),
                Message(
                    id="m2",
                    agent_id="system_designer",
                    agent_role="系统策划",
                    content="这是系统策划的发言",
                    timestamp=datetime.now(),
                ),
            ],
            summary="讨论总结内容",
            created_at=datetime.now(),
        )

        context = _build_continuation_context(
            original=original,
            stored=stored,
            follow_up="继续探讨实现方案",
        )

        assert "原始话题" in context
        assert "讨论总结内容" in context
        assert "主策划" in context
        assert "系统策划" in context
        assert "继续探讨实现方案" in context

    def test_build_context_no_summary(self):
        """无摘要的续前上下文。"""
        from src.api.routes.discussion import _build_continuation_context
        from src.memory.base import Discussion
        from datetime import datetime

        original = _make_discussion(topic="无摘要话题")
        stored = Discussion(
            id="test",
            project_id="default",
            topic="无摘要话题",
            messages=[],
            created_at=datetime.now(),
        )

        context = _build_continuation_context(
            original=original,
            stored=stored,
            follow_up="新方向",
        )

        assert "无摘要话题" in context
        assert "新方向" in context
