"""Unit tests for Agent classes."""

import pytest

from src.agents import NumberDesigner, PlayerAdvocate, SystemDesigner
from src.agents.base import BaseAgent
from src.config.settings import load_role_config


class TestBaseAgent:
    """Tests for the BaseAgent base class."""

    def test_base_agent_requires_role_name(self):
        """BaseAgent subclass must define role_name."""

        class InvalidAgent(BaseAgent):
            role_name = ""

            def get_tools(self):
                return []

        with pytest.raises(ValueError, match="must define role_name"):
            InvalidAgent()

    def test_base_agent_loads_config(self):
        """BaseAgent loads configuration from YAML."""
        agent = SystemDesigner()
        assert agent.role != ""
        assert agent.goal != ""
        assert agent.backstory != ""


class TestSystemDesigner:
    """Tests for the SystemDesigner agent."""

    def test_system_designer_role_name(self):
        """SystemDesigner has correct role name."""
        agent = SystemDesigner()
        assert agent.role_name == "system_designer"

    def test_system_designer_config(self):
        """SystemDesigner loads correct configuration."""
        agent = SystemDesigner()
        assert "系统策划" in agent.role
        assert len(agent.focus_areas) > 0

    def test_system_designer_get_tools(self):
        """SystemDesigner returns tools list."""
        agent = SystemDesigner()
        tools = agent.get_tools()
        assert isinstance(tools, list)

    def test_system_designer_repr(self):
        """SystemDesigner has meaningful repr."""
        agent = SystemDesigner()
        repr_str = repr(agent)
        assert "SystemDesigner" in repr_str
        assert "role=" in repr_str


class TestNumberDesigner:
    """Tests for the NumberDesigner agent."""

    def test_number_designer_role_name(self):
        """NumberDesigner has correct role name."""
        agent = NumberDesigner()
        assert agent.role_name == "number_designer"

    def test_number_designer_config(self):
        """NumberDesigner loads correct configuration."""
        agent = NumberDesigner()
        assert "数值策划" in agent.role
        assert len(agent.focus_areas) > 0

    def test_number_designer_get_tools(self):
        """NumberDesigner returns tools list."""
        agent = NumberDesigner()
        tools = agent.get_tools()
        assert isinstance(tools, list)


class TestPlayerAdvocate:
    """Tests for the PlayerAdvocate agent."""

    def test_player_advocate_role_name(self):
        """PlayerAdvocate has correct role name."""
        agent = PlayerAdvocate()
        assert agent.role_name == "player_advocate"

    def test_player_advocate_config(self):
        """PlayerAdvocate loads correct configuration."""
        agent = PlayerAdvocate()
        assert "玩家代言人" in agent.role
        assert len(agent.focus_areas) > 0

    def test_player_advocate_get_tools(self):
        """PlayerAdvocate returns tools list."""
        agent = PlayerAdvocate()
        tools = agent.get_tools()
        assert isinstance(tools, list)


class TestLoadRoleConfig:
    """Tests for the role configuration loading."""

    def test_load_valid_config(self):
        """Loading a valid config returns dictionary."""
        config = load_role_config("system_designer")
        assert isinstance(config, dict)
        assert "role" in config
        assert "goal" in config
        assert "backstory" in config

    def test_load_invalid_config_raises(self):
        """Loading non-existent config raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_role_config("nonexistent_role")

    def test_all_role_configs_valid(self):
        """All role configs can be loaded and have required fields."""
        roles = ["system_designer", "number_designer", "player_advocate"]
        for role in roles:
            config = load_role_config(role)
            assert "role" in config, f"{role} missing 'role'"
            assert "goal" in config, f"{role} missing 'goal'"
            assert "backstory" in config, f"{role} missing 'backstory'"
            assert "focus_areas" in config, f"{role} missing 'focus_areas'"
