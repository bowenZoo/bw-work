"""Tests for parallel discussion functionality."""

import pytest

from src.crew.mention_parser import parse_mentioned_roles


class TestMentionParser:
    """Tests for mention parser in parallel discussion context."""

    def test_single_mention(self):
        """Test parsing when a single role is mentioned."""
        text = "系统策划，你觉得这个技术方案可行吗？"
        roles = parse_mentioned_roles(text)
        assert roles == ["系统策划"]

    def test_multiple_mentions(self):
        """Test parsing when multiple roles are mentioned."""
        text = "系统策划和数值策划，请分别从你们的角度分析一下"
        roles = parse_mentioned_roles(text)
        assert set(roles) == {"系统策划", "数值策划"}

    def test_alias_mention(self):
        """Test parsing using role aliases."""
        text = "从玩家角度来看，这个设计体验如何？"
        roles = parse_mentioned_roles(text)
        assert "玩家代言人" in roles

    def test_no_mention(self):
        """Test parsing when no specific role is mentioned."""
        text = "大家觉得这个方案怎么样？"
        roles = parse_mentioned_roles(text)
        assert roles == []  # Empty means all agents should respond


class TestMessageSequence:
    """Tests for message sequence functionality."""

    def test_sequence_increments(self):
        """Test that message sequence auto-increments."""
        from src.crew.discussion_crew import DiscussionCrew

        crew = DiscussionCrew(discussion_id="test-seq")
        assert crew._message_sequence == 0

        seq1 = crew._next_sequence()
        assert seq1 == 1

        seq2 = crew._next_sequence()
        assert seq2 == 2

        seq3 = crew._next_sequence()
        assert seq3 == 3

    def test_message_event_has_sequence(self):
        """Test that message events include sequence number."""
        from src.api.websocket.events import create_message_event

        event = create_message_event(
            discussion_id="test",
            agent_id="system_designer",
            agent_role="系统策划",
            content="Test message",
            sequence=42,
        )

        assert event.data.sequence == 42

    def test_message_event_without_sequence(self):
        """Test that message events work without sequence number."""
        from src.api.websocket.events import create_message_event

        event = create_message_event(
            discussion_id="test",
            agent_id="system_designer",
            agent_role="系统策划",
            content="Test message",
        )

        assert event.data.sequence is None


class TestDiscussionCrewParallel:
    """Tests for DiscussionCrew parallel functionality."""

    def test_discussion_agents_exist(self):
        """Test that discussion agents are initialized."""
        from src.crew.discussion_crew import DiscussionCrew

        crew = DiscussionCrew(discussion_id="test-agents")

        # Should have 6 discussion agents (excluding lead planner)
        assert len(crew._discussion_agents) == 6

        # Check core agent roles are present
        roles = [agent.role for agent in crew._discussion_agents]
        assert "系统策划" in roles
        assert "数值策划" in roles
        assert "玩家代言人" in roles

    def test_lead_planner_separate(self):
        """Test that lead planner is separate from discussion agents."""
        from src.crew.discussion_crew import DiscussionCrew

        crew = DiscussionCrew(discussion_id="test-lead")

        # Lead planner should not be in discussion agents
        lead_role = crew._lead_planner.role
        discussion_roles = [agent.role for agent in crew._discussion_agents]

        assert lead_role not in discussion_roles

    def test_all_agents_includes_lead(self):
        """Test that _agents includes all agents including lead planner."""
        from src.crew.discussion_crew import DiscussionCrew

        crew = DiscussionCrew(discussion_id="test-all")

        # All agents should include lead planner + discussion agents
        assert len(crew._agents) >= 4  # At least 4: lead + 3 discussion


class TestParallelResponses:
    """Tests for parallel response functionality."""

    def test_filter_agents_by_role(self):
        """Test that agents are correctly filtered by mentioned roles."""
        from src.crew.discussion_crew import DiscussionCrew

        crew = DiscussionCrew(discussion_id="test-filter")

        # Get agent roles
        all_roles = [agent.role for agent in crew._discussion_agents]

        # Test filtering (simulated)
        mentioned_roles = ["系统策划"]
        filtered = [
            agent for agent in crew._discussion_agents
            if agent.role in mentioned_roles
        ]

        assert len(filtered) == 1
        assert filtered[0].role == "系统策划"

    def test_empty_mention_uses_all(self):
        """Test that empty mention list means all agents respond."""
        from src.crew.discussion_crew import DiscussionCrew

        crew = DiscussionCrew(discussion_id="test-all-respond")

        # When no roles mentioned, all should respond
        mentioned_roles: list[str] = []
        agents_to_call = [
            agent for agent in crew._discussion_agents
            if agent.role in mentioned_roles
        ]

        # Empty filter, so fallback to all
        if not agents_to_call:
            agents_to_call = crew._discussion_agents

        assert len(agents_to_call) == 6


class TestEventSequencing:
    """Tests for event sequencing in messages."""

    def test_event_to_dict_includes_sequence(self):
        """Test that event.to_dict() includes sequence field."""
        from src.api.websocket.events import create_message_event

        event = create_message_event(
            discussion_id="test",
            agent_id="test_agent",
            agent_role="Test",
            content="Hello",
            sequence=10,
        )

        event_dict = event.to_dict()
        assert event_dict["data"]["sequence"] == 10

    def test_message_data_model(self):
        """Test MessageData model with sequence."""
        from src.api.websocket.events import MessageData

        data = MessageData(
            discussion_id="test",
            agent_id="test_agent",
            agent_role="Test",
            content="Hello",
            sequence=5,
        )

        assert data.sequence == 5
        assert data.discussion_id == "test"
