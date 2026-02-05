"""Project summary generator for consolidating module design documents."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ModuleSummary:
    """Summary information for a module."""

    module_id: str
    module_name: str
    design_doc_path: str
    status: str  # completed, skipped, failed
    discussion_rounds: int
    key_decisions: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)


@dataclass
class ModuleRelation:
    """Dependency relationship between modules."""

    from_module: str
    to_module: str
    relation_type: str = "depends_on"


@dataclass
class ProjectSummaryData:
    """Data for generating project summary."""

    project_name: str
    gdd_filename: str
    total_duration_minutes: float
    modules: list[ModuleSummary] = field(default_factory=list)
    relations: list[ModuleRelation] = field(default_factory=list)


class ProjectSummaryGenerator:
    """Generates project-level summary documents.

    Creates an index document that consolidates all module design documents,
    including a module relationship diagram and decision summary.
    """

    def __init__(self, data_dir: str = "data/projects"):
        """Initialize the generator.

        Args:
            data_dir: Base directory for project data.
        """
        self.data_dir = Path(data_dir)
        self._template = self._load_template()

    def _load_template(self) -> str:
        """Load the index template."""
        template_path = Path(__file__).parent / "templates" / "index.md"
        if template_path.exists():
            return template_path.read_text(encoding="utf-8")
        return self._get_fallback_template()

    def _get_fallback_template(self) -> str:
        """Return a fallback template."""
        return """# {project_name} 策划案索引

> **生成时间**: {timestamp}
> **GDD 来源**: {gdd_filename}
> **讨论时长**: {total_duration}

## 模块列表

{module_table}

## 关键决策汇总

{decisions_table}
"""

    def _get_output_path(self, project_id: str) -> Path:
        """Get the output path for the index document.

        Args:
            project_id: Project identifier.

        Returns:
            Path to the index file.
        """
        design_dir = self.data_dir / project_id / "design"
        design_dir.mkdir(parents=True, exist_ok=True)
        return design_dir / "index.md"

    def _format_duration(self, minutes: float) -> str:
        """Format duration in a human-readable format.

        Args:
            minutes: Duration in minutes.

        Returns:
            Formatted duration string.
        """
        if minutes < 60:
            return f"{minutes:.0f} 分钟"
        hours = minutes / 60
        if hours < 24:
            return f"{hours:.1f} 小时"
        days = hours / 24
        return f"{days:.1f} 天"

    def _format_module_table(self, modules: list[ModuleSummary]) -> str:
        """Format the module list as a Markdown table.

        Args:
            modules: List of module summaries.

        Returns:
            Markdown table string.
        """
        if not modules:
            return "暂无模块。"

        lines = [
            "| 模块 | 策划案 | 状态 | 讨论轮数 |",
            "|------|--------|------|----------|",
        ]

        status_map = {
            "completed": "已完成",
            "skipped": "已跳过",
            "failed": "失败",
        }

        for m in modules:
            status = status_map.get(m.status, m.status)
            doc_link = f"[{m.module_id}-system.md](./{m.module_id}-system.md)"
            lines.append(f"| {m.module_name} | {doc_link} | {status} | {m.discussion_rounds} |")

        return "\n".join(lines)

    def _format_relations(self, relations: list[ModuleRelation], modules: list[ModuleSummary]) -> str:
        """Format module relations as a diagram.

        Args:
            relations: List of module relations.
            modules: List of modules for name lookup.

        Returns:
            Mermaid diagram or text representation.
        """
        if not relations:
            return "各模块相互独立，无依赖关系。"

        # Create name lookup
        name_map = {m.module_id: m.module_name for m in modules}

        # Generate Mermaid diagram
        lines = ["```mermaid", "graph TD"]

        for r in relations:
            from_name = name_map.get(r.from_module, r.from_module)
            to_name = name_map.get(r.to_module, r.to_module)
            lines.append(f"    {r.from_module}[{from_name}] --> {r.to_module}[{to_name}]")

        lines.append("```")
        return "\n".join(lines)

    def _format_decisions_table(self, modules: list[ModuleSummary]) -> str:
        """Format key decisions as a table.

        Args:
            modules: List of module summaries.

        Returns:
            Markdown table string.
        """
        # Collect all decisions
        decisions = []
        for m in modules:
            for d in m.key_decisions:
                decisions.append((m.module_name, d))

        if not decisions:
            return "暂无记录的关键决策。"

        lines = [
            "| 模块 | 决策 |",
            "|------|------|",
        ]

        for module_name, decision in decisions:
            # Escape pipe characters in decision text
            decision_escaped = decision.replace("|", "\\|")
            lines.append(f"| {module_name} | {decision_escaped} |")

        return "\n".join(lines)

    def _format_open_questions(self, modules: list[ModuleSummary]) -> str:
        """Format open questions from all modules.

        Args:
            modules: List of module summaries.

        Returns:
            Formatted open questions list.
        """
        questions = []
        for m in modules:
            for q in m.open_questions:
                questions.append((m.module_name, q))

        if not questions:
            return "暂无待确认事项。"

        lines = []
        current_module = None
        for module_name, question in questions:
            if module_name != current_module:
                if current_module is not None:
                    lines.append("")
                lines.append(f"**{module_name}**:")
                current_module = module_name
            lines.append(f"- [ ] {question}")

        return "\n".join(lines)

    def generate(self, project_id: str, data: ProjectSummaryData) -> Path:
        """Generate the project summary index document.

        Args:
            project_id: Project identifier.
            data: Project summary data.

        Returns:
            Path to the generated index file.
        """
        now = datetime.utcnow()

        # Format content sections
        module_table = self._format_module_table(data.modules)
        relations = self._format_relations(data.relations, data.modules)
        decisions_table = self._format_decisions_table(data.modules)
        open_questions = self._format_open_questions(data.modules)
        duration = self._format_duration(data.total_duration_minutes)

        # Generate document
        doc = self._template.format(
            project_name=data.project_name,
            timestamp=now.strftime("%Y-%m-%d %H:%M:%S UTC"),
            gdd_filename=data.gdd_filename,
            total_duration=duration,
            module_table=module_table,
            module_relations=relations,
            decisions_table=decisions_table,
            open_questions=open_questions,
        )

        # Save document
        output_path = self._get_output_path(project_id)
        output_path.write_text(doc, encoding="utf-8")

        logger.info(f"Generated project summary: {output_path}")
        return output_path

    def get_summary(self, project_id: str) -> Optional[str]:
        """Get an existing project summary.

        Args:
            project_id: Project identifier.

        Returns:
            Summary content or None if not found.
        """
        path = self._get_output_path(project_id)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def generate_from_results(
        self,
        project_id: str,
        project_name: str,
        gdd_filename: str,
        results: list,  # list[ModuleDiscussionResult]
        module_dependencies: dict[str, list[str]],
    ) -> Path:
        """Generate summary from discussion results.

        A convenience method that builds ProjectSummaryData from
        ModuleDiscussionResult objects.

        Args:
            project_id: Project identifier.
            project_name: Project name.
            gdd_filename: GDD filename.
            results: List of ModuleDiscussionResult objects.
            module_dependencies: Map of module_id to dependency IDs.

        Returns:
            Path to the generated summary.
        """
        from src.project.models import ModuleDiscussionStatus

        # Build module summaries
        modules = []
        total_duration = 0.0

        for r in results:
            status = "completed" if r.status == ModuleDiscussionStatus.COMPLETED else r.status.value
            modules.append(
                ModuleSummary(
                    module_id=r.module_id,
                    module_name=r.module_name,
                    design_doc_path=r.design_doc.path if r.design_doc else "",
                    status=status,
                    discussion_rounds=int(r.duration_minutes / 0.5) if r.duration_minutes else 0,
                    key_decisions=[d.content for d in r.key_decisions],
                    open_questions=[],
                )
            )
            total_duration += r.duration_minutes

        # Build relations from dependencies
        relations = []
        for module_id, deps in module_dependencies.items():
            for dep in deps:
                relations.append(
                    ModuleRelation(
                        from_module=dep,
                        to_module=module_id,
                    )
                )

        # Generate summary
        data = ProjectSummaryData(
            project_name=project_name,
            gdd_filename=gdd_filename,
            total_duration_minutes=total_duration,
            modules=modules,
            relations=relations,
        )

        return self.generate(project_id, data)
