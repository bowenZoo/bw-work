"""Integration tests for the DiscussionCrew."""

import os

import pytest

from src.crew.discussion_crew import DiscussionCrew


# Check if we have API key configured
HAS_OPENAI_KEY = bool(os.environ.get("OPENAI_API_KEY"))


class TestDiscussionCrew:
    """Tests for the DiscussionCrew class."""

    def test_crew_initialization(self):
        """DiscussionCrew initializes with all agents (including lead planner)."""
        crew = DiscussionCrew()
        assert len(crew.agents) >= 4  # lead + system + number + player (+ optional visual)

    def test_crew_agents_are_correct_types(self):
        """DiscussionCrew has the correct agent types."""
        crew = DiscussionCrew()
        agent_types = [type(agent).__name__ for agent in crew.agents]
        assert "LeadPlanner" in agent_types
        assert "SystemDesigner" in agent_types
        assert "NumberDesigner" in agent_types
        assert "PlayerAdvocate" in agent_types

    @pytest.mark.skipif(not HAS_OPENAI_KEY, reason="OPENAI_API_KEY not configured")
    def test_create_discussion_tasks(self):
        """Creating discussion tasks returns list of tasks."""
        crew = DiscussionCrew()
        tasks = crew.create_discussion_tasks("测试话题", rounds=1)

        # Should have 3 agents * 1 round + 1 summary = 4 tasks
        assert len(tasks) == 4

    @pytest.mark.skipif(not HAS_OPENAI_KEY, reason="OPENAI_API_KEY not configured")
    def test_create_discussion_tasks_multiple_rounds(self):
        """Creating tasks with multiple rounds works correctly."""
        crew = DiscussionCrew()
        tasks = crew.create_discussion_tasks("测试话题", rounds=2)

        # Should have 3 agents * 2 rounds + 1 summary = 7 tasks
        assert len(tasks) == 7

    @pytest.mark.skipif(not HAS_OPENAI_KEY, reason="OPENAI_API_KEY not configured")
    def test_create_discussion_tasks_has_correct_topic(self):
        """Discussion tasks contain the specified topic."""
        crew = DiscussionCrew()
        topic = "设计一个背包系统"
        tasks = crew.create_discussion_tasks(topic, rounds=1)

        # At least the first task should mention the topic
        first_task = tasks[0]
        assert topic in first_task.description

    def test_crew_with_custom_llm(self):
        """DiscussionCrew can be initialized with custom LLM."""
        # This test verifies the interface, not actual LLM functionality
        crew = DiscussionCrew(llm=None)
        assert crew is not None

    def test_crew_with_callback(self):
        """DiscussionCrew can be initialized with callback."""
        messages = []

        def callback(role: str, message: str) -> None:
            messages.append((role, message))

        crew = DiscussionCrew(callback=callback)
        assert crew is not None


class TestDiscussionCrewTaskContent:
    """Tests for the content of discussion tasks.

    These tests require OPENAI_API_KEY as they call build_agent().
    """

    @pytest.mark.skipif(not HAS_OPENAI_KEY, reason="OPENAI_API_KEY not configured")
    def test_first_task_is_initial_statement(self):
        """First task asks for initial statement on topic."""
        crew = DiscussionCrew()
        tasks = crew.create_discussion_tasks("测试", rounds=1)

        first_task = tasks[0]
        assert "初步看法" in first_task.description or "设计建议" in first_task.description

    @pytest.mark.skipif(not HAS_OPENAI_KEY, reason="OPENAI_API_KEY not configured")
    def test_subsequent_tasks_respond_to_previous(self):
        """Subsequent tasks ask to respond to previous discussion."""
        crew = DiscussionCrew()
        tasks = crew.create_discussion_tasks("测试", rounds=2)

        # Second round tasks should reference previous discussion
        second_round_task = tasks[3]  # First task of second round
        assert "之前" in second_round_task.description or "回应" in second_round_task.description

    @pytest.mark.skipif(not HAS_OPENAI_KEY, reason="OPENAI_API_KEY not configured")
    def test_summary_task_is_last(self):
        """Last task is a summary task."""
        crew = DiscussionCrew()
        tasks = crew.create_discussion_tasks("测试", rounds=1)

        last_task = tasks[-1]
        assert "总结" in last_task.description


class TestDiscussionCrewAgentConfig:
    """Tests for agent configuration that don't require LLM."""

    def test_system_designer_config_loaded(self):
        """System designer agent config is loaded correctly."""
        crew = DiscussionCrew()
        agent = crew._system_designer
        assert agent.role == "系统策划"
        assert len(agent.focus_areas) > 0

    def test_number_designer_config_loaded(self):
        """Number designer agent config is loaded correctly."""
        crew = DiscussionCrew()
        agent = crew._number_designer
        assert agent.role == "数值策划"
        assert len(agent.focus_areas) > 0

    def test_player_advocate_config_loaded(self):
        """Player advocate agent config is loaded correctly."""
        crew = DiscussionCrew()
        agent = crew._player_advocate
        assert agent.role == "玩家代言人"
        assert len(agent.focus_areas) > 0

    def test_all_agents_have_backstory(self):
        """All agents have non-empty backstory."""
        crew = DiscussionCrew()
        for agent in crew.agents:
            assert agent.backstory, f"{type(agent).__name__} missing backstory"

    def test_all_agents_have_goal(self):
        """All agents have non-empty goal."""
        crew = DiscussionCrew()
        for agent in crew.agents:
            assert agent.goal, f"{type(agent).__name__} missing goal"
