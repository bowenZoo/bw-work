"""Tests for discussion API routes."""
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes.discussion import (
    DiscussionState,
    DiscussionStatus,
    get_current_discussion,
    get_discussion_agenda,
    set_current_discussion,
    set_discussion_agenda,
)
from src.models.agenda import Agenda, AgendaItem, AgendaItemStatus


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_global_discussion():
    """Reset global discussion state before each test."""
    set_current_discussion(None)
    yield
    set_current_discussion(None)


class TestGlobalDiscussionState:
    """Tests for global discussion state management."""

    def test_get_current_discussion_none(self):
        """Test getting current discussion when none exists."""
        result = get_current_discussion()
        assert result is None

    def test_set_and_get_current_discussion(self):
        """Test setting and getting current discussion."""
        discussion = DiscussionState(
            id="test-123",
            topic="Test topic",
            rounds=3,
            status=DiscussionStatus.RUNNING,
            created_at="2024-01-01T00:00:00",
        )
        set_current_discussion(discussion)

        result = get_current_discussion()
        assert result is not None
        assert result.id == "test-123"
        assert result.topic == "Test topic"
        assert result.status == DiscussionStatus.RUNNING

    def test_clear_current_discussion(self):
        """Test clearing current discussion."""
        discussion = DiscussionState(
            id="test-123",
            topic="Test topic",
            rounds=3,
            status=DiscussionStatus.RUNNING,
            created_at="2024-01-01T00:00:00",
        )
        set_current_discussion(discussion)
        assert get_current_discussion() is not None

        set_current_discussion(None)
        assert get_current_discussion() is None


class TestCurrentDiscussionAPI:
    """Tests for current discussion API endpoints."""

    def test_get_current_no_discussion(self, client):
        """Test GET /api/discussions/current when no discussion exists."""
        response = client.get("/api/discussions/current")
        assert response.status_code == 200
        assert response.json() is None

    def test_get_current_with_discussion(self, client):
        """Test GET /api/discussions/current with an active discussion."""
        discussion = DiscussionState(
            id="test-456",
            topic="Active discussion",
            rounds=2,
            status=DiscussionStatus.RUNNING,
            created_at="2024-01-01T00:00:00",
            started_at="2024-01-01T00:00:01",
        )
        set_current_discussion(discussion)

        response = client.get("/api/discussions/current")
        assert response.status_code == 200
        data = response.json()
        assert data is not None
        assert data["id"] == "test-456"
        assert data["topic"] == "Active discussion"
        assert data["status"] == "running"

    def test_join_current_no_discussion(self, client):
        """Test POST /api/discussions/current/join when no discussion exists."""
        response = client.post("/api/discussions/current/join")
        assert response.status_code == 200
        data = response.json()
        assert data["discussion"] is None
        assert data["messages"] == []

    def test_join_current_with_discussion(self, client):
        """Test POST /api/discussions/current/join with an active discussion."""
        discussion = DiscussionState(
            id="test-789",
            topic="Join test discussion",
            rounds=3,
            status=DiscussionStatus.RUNNING,
            created_at="2024-01-01T00:00:00",
            started_at="2024-01-01T00:00:01",
        )
        set_current_discussion(discussion)

        response = client.post("/api/discussions/current/join")
        assert response.status_code == 200
        data = response.json()
        assert data["discussion"] is not None
        assert data["discussion"]["id"] == "test-789"
        assert data["discussion"]["topic"] == "Join test discussion"
        # Messages should be empty since we didn't create any
        assert data["messages"] == []


class TestAgendaAPI:
    """Tests for agenda API endpoints."""

    def test_get_agenda_no_discussion(self, client):
        """Test GET /api/discussions/current/agenda when no discussion exists."""
        response = client.get("/api/discussions/current/agenda")
        assert response.status_code == 404
        assert "无活跃讨论" in response.json()["detail"]

    def test_get_agenda_empty(self, client):
        """Test GET /api/discussions/current/agenda with no agenda initialized."""
        discussion = DiscussionState(
            id="test-agenda-1",
            topic="Agenda test",
            rounds=3,
            status=DiscussionStatus.RUNNING,
            created_at="2024-01-01T00:00:00",
        )
        set_current_discussion(discussion)

        response = client.get("/api/discussions/current/agenda")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["current_index"] == 0

    def test_get_agenda_with_items(self, client):
        """Test GET /api/discussions/current/agenda with agenda items."""
        discussion = DiscussionState(
            id="test-agenda-2",
            topic="Agenda test",
            rounds=3,
            status=DiscussionStatus.RUNNING,
            created_at="2024-01-01T00:00:00",
        )
        set_current_discussion(discussion)

        # Create agenda with items
        agenda = Agenda()
        agenda.add_item("核心玩法", "定义游戏核心循环")
        agenda.add_item("付费模式", "讨论商业化方案")
        set_discussion_agenda(discussion.id, agenda)

        response = client.get("/api/discussions/current/agenda")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["items"][0]["title"] == "核心玩法"
        assert data["items"][1]["title"] == "付费模式"
        assert data["current_index"] == 0

    def test_add_agenda_item(self, client):
        """Test POST /api/discussions/current/agenda/items to add a new item."""
        discussion = DiscussionState(
            id="test-agenda-3",
            topic="Agenda test",
            rounds=3,
            status=DiscussionStatus.RUNNING,
            created_at="2024-01-01T00:00:00",
        )
        set_current_discussion(discussion)

        response = client.post(
            "/api/discussions/current/agenda/items",
            json={"title": "新议题", "description": "新的讨论点"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["item"]["title"] == "新议题"
        assert data["item"]["description"] == "新的讨论点"
        assert data["item"]["status"] == "pending"

    def test_skip_agenda_item(self, client):
        """Test POST /api/discussions/current/agenda/items/{item_id}/skip."""
        discussion = DiscussionState(
            id="test-agenda-4",
            topic="Agenda test",
            rounds=3,
            status=DiscussionStatus.RUNNING,
            created_at="2024-01-01T00:00:00",
        )
        set_current_discussion(discussion)

        # Create agenda with items
        agenda = Agenda()
        item = agenda.add_item("跳过测试", "会被跳过的议题")
        set_discussion_agenda(discussion.id, agenda)

        response = client.post(f"/api/discussions/current/agenda/items/{item.id}/skip")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "skipped"

    def test_get_agenda_item_summary_not_completed(self, client):
        """Test GET summary for a non-completed item returns error."""
        discussion = DiscussionState(
            id="test-agenda-5",
            topic="Agenda test",
            rounds=3,
            status=DiscussionStatus.RUNNING,
            created_at="2024-01-01T00:00:00",
        )
        set_current_discussion(discussion)

        # Create agenda with items
        agenda = Agenda()
        item = agenda.add_item("小结测试", "测试小结获取")
        set_discussion_agenda(discussion.id, agenda)

        response = client.get(f"/api/discussions/current/agenda/items/{item.id}/summary")
        assert response.status_code == 400
        assert "议题尚未完成" in response.json()["detail"]

    def test_get_agenda_item_summary_completed(self, client):
        """Test GET summary for a completed item."""
        discussion = DiscussionState(
            id="test-agenda-6",
            topic="Agenda test",
            rounds=3,
            status=DiscussionStatus.RUNNING,
            created_at="2024-01-01T00:00:00",
        )
        set_current_discussion(discussion)

        # Create agenda with completed item
        agenda = Agenda()
        item = agenda.add_item("完成测试", "已完成的议题")
        item.complete("这是议题小结")
        set_discussion_agenda(discussion.id, agenda)

        response = client.get(f"/api/discussions/current/agenda/items/{item.id}/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "完成测试"
        assert data["summary"] == "这是议题小结"


class TestAgendaSummaryParsing:
    """Tests for agenda summary parsing in DiscussionCrew."""

    def test_parse_agenda_summary_full(self):
        """Test parsing a complete agenda summary."""
        from src.crew.discussion_crew import DiscussionCrew

        crew = DiscussionCrew()

        summary_text = """# 议题小结：核心玩法设计

## 讨论结论
- 采用三消+RPG的混合玩法
- 核心循环为：关卡挑战 -> 获取资源 -> 角色养成

## 各方观点
- 系统策划：技术上可行，建议控制关卡复杂度
- 数值策划：需要平衡资源产出和消耗
- 玩家代言人：玩家可能更喜欢快节奏战斗

## 遗留问题
- 多人联机功能暂不考虑
- 需要进一步测试体力系统

## 下一步行动
- 制作核心玩法原型
- 进行小规模用户测试
"""

        details = crew._parse_agenda_summary(summary_text)

        assert len(details.conclusions) == 2
        assert "三消+RPG" in details.conclusions[0]

        assert "系统策划" in details.viewpoints
        assert "技术上可行" in details.viewpoints["系统策划"]

        assert len(details.open_questions) == 2
        assert "多人联机" in details.open_questions[0]

        assert len(details.next_steps) == 2
        assert "原型" in details.next_steps[0]

    def test_parse_agenda_summary_partial(self):
        """Test parsing a partial agenda summary."""
        from src.crew.discussion_crew import DiscussionCrew

        crew = DiscussionCrew()

        summary_text = """# 议题小结

## 讨论结论
- 达成共识

## 各方观点
- 主策划：同意方案
"""

        details = crew._parse_agenda_summary(summary_text)

        assert len(details.conclusions) == 1
        assert "主策划" in details.viewpoints
        assert len(details.open_questions) == 0
        assert len(details.next_steps) == 0
