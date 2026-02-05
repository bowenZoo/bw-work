"""Project-level memory for maintaining context across module discussions."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TermDefinition:
    """A term in the project glossary."""

    term: str
    definition: str
    module_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ModuleDecision:
    """A key decision made during module discussion."""

    module_id: str
    module_name: str
    decision: str
    rationale: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Constraint:
    """A constraint identified for the project."""

    type: str  # "technical", "resource", "design", etc.
    description: str
    module_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ProjectMemoryState:
    """Serializable state of project memory."""

    project_id: str
    gdd_context: str  # Full GDD content for reference
    gdd_summary: str  # Condensed GDD summary
    terms: list[TermDefinition] = field(default_factory=list)
    decisions: list[ModuleDecision] = field(default_factory=list)
    constraints: list[Constraint] = field(default_factory=list)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "project_id": self.project_id,
            "gdd_context": self.gdd_context,
            "gdd_summary": self.gdd_summary,
            "terms": [
                {
                    "term": t.term,
                    "definition": t.definition,
                    "module_id": t.module_id,
                    "created_at": t.created_at.isoformat(),
                }
                for t in self.terms
            ],
            "decisions": [
                {
                    "module_id": d.module_id,
                    "module_name": d.module_name,
                    "decision": d.decision,
                    "rationale": d.rationale,
                    "timestamp": d.timestamp.isoformat(),
                }
                for d in self.decisions
            ],
            "constraints": [
                {
                    "type": c.type,
                    "description": c.description,
                    "module_id": c.module_id,
                    "created_at": c.created_at.isoformat(),
                }
                for c in self.constraints
            ],
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectMemoryState":
        """Create from dictionary."""
        return cls(
            project_id=data["project_id"],
            gdd_context=data.get("gdd_context", ""),
            gdd_summary=data.get("gdd_summary", ""),
            terms=[
                TermDefinition(
                    term=t["term"],
                    definition=t["definition"],
                    module_id=t.get("module_id"),
                    created_at=datetime.fromisoformat(t["created_at"])
                    if t.get("created_at")
                    else datetime.utcnow(),
                )
                for t in data.get("terms", [])
            ],
            decisions=[
                ModuleDecision(
                    module_id=d["module_id"],
                    module_name=d["module_name"],
                    decision=d["decision"],
                    rationale=d["rationale"],
                    timestamp=datetime.fromisoformat(d["timestamp"])
                    if d.get("timestamp")
                    else datetime.utcnow(),
                )
                for d in data.get("decisions", [])
            ],
            constraints=[
                Constraint(
                    type=c["type"],
                    description=c["description"],
                    module_id=c.get("module_id"),
                    created_at=datetime.fromisoformat(c["created_at"])
                    if c.get("created_at")
                    else datetime.utcnow(),
                )
                for c in data.get("constraints", [])
            ],
            updated_at=datetime.fromisoformat(data["updated_at"])
            if data.get("updated_at")
            else datetime.utcnow(),
        )


class ProjectMemory:
    """Manages project-level memory for cross-module context.

    Memory types:
    - GDD Context: Full GDD content for reference
    - Module Decisions: Key decisions from completed modules
    - Terms/Glossary: Project-specific terminology
    - Constraints: Technical/resource constraints
    """

    def __init__(self, data_dir: str = "data/projects"):
        """Initialize project memory.

        Args:
            data_dir: Base directory for project data.
        """
        self.data_dir = Path(data_dir)
        self._state: Optional[ProjectMemoryState] = None
        self._project_id: Optional[str] = None

    def _memory_path(self, project_id: str) -> Path:
        """Get the path to the memory file."""
        return self.data_dir / project_id / "memory.json"

    def load(self, project_id: str) -> ProjectMemoryState:
        """Load or create project memory.

        Args:
            project_id: Project identifier.

        Returns:
            ProjectMemoryState instance.
        """
        self._project_id = project_id
        path = self._memory_path(project_id)

        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._state = ProjectMemoryState.from_dict(data)
                logger.info(f"Loaded project memory for {project_id}")
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to load memory, creating new: {e}")
                self._state = ProjectMemoryState(project_id=project_id, gdd_context="", gdd_summary="")
        else:
            self._state = ProjectMemoryState(project_id=project_id, gdd_context="", gdd_summary="")

        return self._state

    def save(self) -> None:
        """Save current memory state to disk."""
        if not self._state or not self._project_id:
            return

        self._state.updated_at = datetime.utcnow()
        path = self._memory_path(self._project_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write
        temp_path = path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(self._state.to_dict(), f, ensure_ascii=False, indent=2)
        temp_path.replace(path)

        logger.debug(f"Saved project memory for {self._project_id}")

    def set_gdd_context(self, content: str, summary: Optional[str] = None) -> None:
        """Set the GDD context for the project.

        Args:
            content: Full GDD content.
            summary: Optional condensed summary.
        """
        if not self._state:
            raise RuntimeError("Memory not loaded. Call load() first.")

        self._state.gdd_context = content
        if summary:
            self._state.gdd_summary = summary
        self.save()

    def add_term(self, term: str, definition: str, module_id: Optional[str] = None) -> None:
        """Add or update a term in the glossary.

        Args:
            term: The term to define.
            definition: The definition.
            module_id: Optional module that introduced the term.
        """
        if not self._state:
            raise RuntimeError("Memory not loaded. Call load() first.")

        # Check if term already exists
        existing = next((t for t in self._state.terms if t.term.lower() == term.lower()), None)
        if existing:
            existing.definition = definition
            existing.module_id = module_id or existing.module_id
        else:
            self._state.terms.append(
                TermDefinition(term=term, definition=definition, module_id=module_id)
            )
        self.save()

    def add_decision(
        self, module_id: str, module_name: str, decision: str, rationale: str
    ) -> None:
        """Record a key decision from a module discussion.

        Args:
            module_id: Module identifier.
            module_name: Module display name.
            decision: The decision made.
            rationale: Reasoning behind the decision.
        """
        if not self._state:
            raise RuntimeError("Memory not loaded. Call load() first.")

        self._state.decisions.append(
            ModuleDecision(
                module_id=module_id,
                module_name=module_name,
                decision=decision,
                rationale=rationale,
            )
        )
        self.save()

    def add_constraint(
        self, constraint_type: str, description: str, module_id: Optional[str] = None
    ) -> None:
        """Record a project constraint.

        Args:
            constraint_type: Type of constraint (technical, resource, design).
            description: Description of the constraint.
            module_id: Optional module that identified the constraint.
        """
        if not self._state:
            raise RuntimeError("Memory not loaded. Call load() first.")

        self._state.constraints.append(
            Constraint(type=constraint_type, description=description, module_id=module_id)
        )
        self.save()

    def get_context_for_module(self, module_id: str, module_dependencies: list[str]) -> str:
        """Get relevant context for a module discussion.

        Builds a context string containing:
        - GDD summary or relevant sections
        - Decisions from dependent modules
        - Relevant terms
        - Applicable constraints

        Args:
            module_id: The module being discussed.
            module_dependencies: IDs of modules this one depends on.

        Returns:
            Formatted context string for the agent.
        """
        if not self._state:
            raise RuntimeError("Memory not loaded. Call load() first.")

        sections = []

        # GDD Summary
        if self._state.gdd_summary:
            sections.append(f"## Project Overview\n{self._state.gdd_summary}")

        # Relevant decisions from dependencies
        relevant_decisions = [
            d for d in self._state.decisions if d.module_id in module_dependencies
        ]
        if relevant_decisions:
            decisions_text = "\n".join(
                f"- **{d.module_name}**: {d.decision}\n  原因: {d.rationale}"
                for d in relevant_decisions
            )
            sections.append(f"## Related Module Decisions\n{decisions_text}")

        # All constraints
        if self._state.constraints:
            constraints_text = "\n".join(
                f"- [{c.type}] {c.description}" for c in self._state.constraints
            )
            sections.append(f"## Project Constraints\n{constraints_text}")

        # Relevant terms
        if self._state.terms:
            terms_text = "\n".join(f"- **{t.term}**: {t.definition}" for t in self._state.terms)
            sections.append(f"## Glossary\n{terms_text}")

        return "\n\n".join(sections)

    def get_all_decisions(self) -> list[ModuleDecision]:
        """Get all recorded decisions.

        Returns:
            List of all module decisions.
        """
        if not self._state:
            return []
        return self._state.decisions

    def get_decisions_for_module(self, module_id: str) -> list[ModuleDecision]:
        """Get decisions for a specific module.

        Args:
            module_id: Module identifier.

        Returns:
            List of decisions from the specified module.
        """
        if not self._state:
            return []
        return [d for d in self._state.decisions if d.module_id == module_id]

    def check_consistency(self, new_decision: str, module_id: str) -> list[str]:
        """Check if a new decision conflicts with existing ones.

        This is a simple keyword-based check. For more sophisticated
        conflict detection, an LLM would be needed.

        Args:
            new_decision: The proposed new decision text.
            module_id: The module making the decision.

        Returns:
            List of potential conflict descriptions.
        """
        if not self._state:
            return []

        conflicts = []
        new_lower = new_decision.lower()

        # Simple checks for common contradiction patterns
        contradiction_pairs = [
            ("real-time", "turn-based"),
            ("免费", "付费"),
            ("单人", "多人"),
            ("2d", "3d"),
            ("横版", "竖版"),
        ]

        for d in self._state.decisions:
            if d.module_id == module_id:
                continue  # Skip same module decisions

            decision_lower = d.decision.lower()
            for term1, term2 in contradiction_pairs:
                if (term1 in new_lower and term2 in decision_lower) or (
                    term2 in new_lower and term1 in decision_lower
                ):
                    conflicts.append(
                        f"Potential conflict with {d.module_name}: "
                        f"'{term1}' vs '{term2}' in design approach"
                    )

        return conflicts

    def get_glossary(self) -> dict[str, str]:
        """Get the term glossary as a dictionary.

        Returns:
            Dictionary mapping terms to definitions.
        """
        if not self._state:
            return {}
        return {t.term: t.definition for t in self._state.terms}

    def clear(self) -> None:
        """Clear all memory except GDD context."""
        if not self._state:
            return

        self._state.terms = []
        self._state.decisions = []
        self._state.constraints = []
        self.save()
