"""Tech Director Agent - 技术总监，主导技术原型阶段讨论。"""

from src.agents.lead_planner import LeadPlanner


class TechDirector(LeadPlanner):
    """Tech Director agent that moderates tech-prototype stage discussions.

    Focuses on technical feasibility, tech stack decisions, prototype scope
    definition, and risk identification.
    """

    role_name = "tech_director"
