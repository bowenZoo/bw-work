"""Moderator subclasses — agents that can lead a discussion as host.

Each class extends LeadPlanner to inherit all moderator prompt methods,
but loads its own role YAML so the LLM identity matches the agent role.
"""

from src.agents.lead_planner import LeadPlanner


class SystemDesignerModerator(LeadPlanner):
    """系统策划担任主持人。"""
    role_name = "system_designer"


class NumberDesignerModerator(LeadPlanner):
    """数值策划担任主持人。"""
    role_name = "number_designer"


class VisualConceptModerator(LeadPlanner):
    """视觉概念设计师担任主持人。"""
    role_name = "visual_concept"


class MarketDirectorModerator(LeadPlanner):
    """市场总监担任主持人。"""
    role_name = "market_director"


class OperationsAnalystModerator(LeadPlanner):
    """运营策划担任主持人。"""
    role_name = "operations_analyst"


class PlayerAdvocateModerator(LeadPlanner):
    """玩家代言人担任主持人。"""
    role_name = "player_advocate"
