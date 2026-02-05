"""Design document generator for module discussions."""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Generator version
GENERATOR_VERSION = "1.0.0"


@dataclass
class DesignDocContent:
    """Content sections for a design document."""

    design_goals: str = ""
    core_experience: str = ""
    system_relations: str = ""
    basic_gameplay: str = ""
    advanced_gameplay: str = ""
    gameplay_examples: str = ""
    main_ui: str = ""
    operation_flow: str = ""
    ui_navigation: str = ""
    core_formulas: str = ""
    parameter_tables: str = ""
    balance_goals: str = ""
    edge_cases: str = ""
    anti_cheat: str = ""
    error_handling: str = ""
    discussion_summary: str = ""
    design_decisions: str = ""
    open_questions: str = ""


@dataclass
class DiscussionMessage:
    """A message from a discussion."""

    speaker: str
    content: str
    timestamp: datetime


@dataclass
class DiscussionData:
    """Data from a module discussion for document generation."""

    module_id: str
    module_name: str
    discussion_id: str
    gdd_filename: str
    messages: list[DiscussionMessage] = field(default_factory=list)
    key_decisions: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)


class DesignDocGenerator:
    """Generates structured design documents from discussion content.

    Uses LLM to organize discussion content into the standard
    design document format.
    """

    def __init__(
        self,
        data_dir: str = "data/projects",
        model: str = "gpt-4",
    ):
        """Initialize the generator.

        Args:
            data_dir: Base directory for project data.
            model: LLM model to use for content generation.
        """
        self.data_dir = Path(data_dir)
        self.model = model
        self._template = self._load_template()

    def _load_template(self) -> str:
        """Load the design document template."""
        template_path = Path(__file__).parent / "templates" / "design_doc.md"
        if template_path.exists():
            return template_path.read_text(encoding="utf-8")
        return self._get_fallback_template()

    def _get_fallback_template(self) -> str:
        """Return a fallback template if file not found."""
        return """# {module_name} 策划案

> **版本**: {version}
> **生成时间**: {timestamp}
> **讨论 ID**: {discussion_id}

## 功能概述

{design_goals}

## 玩法描述

{basic_gameplay}

## 数值框架

{core_formulas}

## 设计决策

{design_decisions}

## 待确认事项

{open_questions}
"""

    def _get_output_path(self, project_id: str, module_id: str) -> Path:
        """Get the output path for a design document.

        Args:
            project_id: Project identifier.
            module_id: Module identifier.

        Returns:
            Path to the output file.
        """
        design_dir = self.data_dir / project_id / "design"
        design_dir.mkdir(parents=True, exist_ok=True)
        return design_dir / f"{module_id}-system.md"

    def _format_messages(self, messages: list[DiscussionMessage]) -> str:
        """Format discussion messages as a summary.

        Args:
            messages: List of discussion messages.

        Returns:
            Formatted message summary.
        """
        if not messages:
            return "No discussion messages recorded."

        lines = []
        for msg in messages[:20]:  # Limit to recent messages
            lines.append(f"**{msg.speaker}**: {msg.content[:200]}...")
        return "\n\n".join(lines)

    def _format_decisions(self, decisions: list[str]) -> str:
        """Format key decisions as a list.

        Args:
            decisions: List of decision strings.

        Returns:
            Formatted decision list.
        """
        if not decisions:
            return "No key decisions recorded."

        return "\n".join(f"- {d}" for d in decisions)

    def _format_questions(self, questions: list[str]) -> str:
        """Format open questions as a list.

        Args:
            questions: List of questions.

        Returns:
            Formatted question list.
        """
        if not questions:
            return "No open questions."

        return "\n".join(f"- [ ] {q}" for q in questions)

    async def generate_async(
        self,
        project_id: str,
        discussion_data: DiscussionData,
    ) -> Path:
        """Generate a design document asynchronously using LLM.

        Args:
            project_id: Project identifier.
            discussion_data: Data from the module discussion.

        Returns:
            Path to the generated document.
        """
        # Prepare content using LLM
        content = await self._generate_content_async(discussion_data)

        # Generate document
        doc = self._format_document(discussion_data, content)

        # Save document
        output_path = self._get_output_path(project_id, discussion_data.module_id)
        output_path.write_text(doc, encoding="utf-8")

        logger.info(f"Generated design document: {output_path}")
        return output_path

    def generate_sync(
        self,
        project_id: str,
        discussion_data: DiscussionData,
    ) -> Path:
        """Generate a design document synchronously.

        Uses a simplified approach without LLM for immediate generation.

        Args:
            project_id: Project identifier.
            discussion_data: Data from the module discussion.

        Returns:
            Path to the generated document.
        """
        # Generate content from discussion data directly
        content = self._generate_content_from_data(discussion_data)

        # Format document
        doc = self._format_document(discussion_data, content)

        # Save document
        output_path = self._get_output_path(project_id, discussion_data.module_id)
        output_path.write_text(doc, encoding="utf-8")

        logger.info(f"Generated design document: {output_path}")
        return output_path

    def _generate_content_from_data(self, data: DiscussionData) -> DesignDocContent:
        """Generate content directly from discussion data.

        This is a simplified approach that structures available data
        without LLM processing.

        Args:
            data: Discussion data.

        Returns:
            DesignDocContent with populated sections.
        """
        content = DesignDocContent()

        # Extract content from messages if available
        if data.messages:
            content.discussion_summary = self._format_messages(data.messages)

            # Try to extract sections from message content
            all_content = " ".join(m.content for m in data.messages)
            content.design_goals = self._extract_section(all_content, ["目标", "goal", "objective"])
            content.basic_gameplay = self._extract_section(all_content, ["玩法", "gameplay", "mechanic"])
            content.core_formulas = self._extract_section(all_content, ["公式", "数值", "formula", "balance"])

        # Add decisions and questions
        content.design_decisions = self._format_decisions(data.key_decisions)
        content.open_questions = self._format_questions(data.open_questions)

        # Fill in placeholder content for empty sections
        content = self._fill_placeholders(content, data.module_name)

        return content

    def _extract_section(self, text: str, keywords: list[str]) -> str:
        """Try to extract content related to keywords.

        Args:
            text: Full text to search.
            keywords: Keywords to look for.

        Returns:
            Extracted content or empty string.
        """
        for keyword in keywords:
            # Find sentences containing the keyword
            pattern = rf"[^.。]*{keyword}[^.。]*[.。]"
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                return " ".join(matches[:3])  # Return up to 3 relevant sentences
        return ""

    def _fill_placeholders(self, content: DesignDocContent, module_name: str) -> DesignDocContent:
        """Fill empty sections with placeholder text.

        Args:
            content: Content object to fill.
            module_name: Module name for context.

        Returns:
            Updated content object.
        """
        if not content.design_goals:
            content.design_goals = f"本模块（{module_name}）的具体设计目标待讨论确定。"

        if not content.core_experience:
            content.core_experience = "核心体验待补充。"

        if not content.system_relations:
            content.system_relations = "与其他系统的关联待分析。"

        if not content.basic_gameplay:
            content.basic_gameplay = "基础玩法待设计。"

        if not content.advanced_gameplay:
            content.advanced_gameplay = "进阶玩法待设计。"

        if not content.gameplay_examples:
            content.gameplay_examples = "具体玩法示例待补充。"

        if not content.main_ui:
            content.main_ui = "界面设计待补充。"

        if not content.operation_flow:
            content.operation_flow = "操作流程待设计。"

        if not content.ui_navigation:
            content.ui_navigation = "界面跳转逻辑待设计。"

        if not content.core_formulas:
            content.core_formulas = "数值公式待设计。"

        if not content.parameter_tables:
            content.parameter_tables = "参数表待补充。"

        if not content.balance_goals:
            content.balance_goals = "平衡目标待确定。"

        if not content.edge_cases:
            content.edge_cases = "异常情况处理待设计。"

        if not content.anti_cheat:
            content.anti_cheat = "防作弊机制待设计。"

        if not content.error_handling:
            content.error_handling = "容错机制待设计。"

        return content

    async def _generate_content_async(self, data: DiscussionData) -> DesignDocContent:
        """Generate content sections using LLM.

        Args:
            data: Discussion data.

        Returns:
            DesignDocContent with LLM-generated sections.
        """
        # For now, use the sync approach
        # Full LLM integration would parse messages and generate each section
        return self._generate_content_from_data(data)

    def _format_document(
        self,
        data: DiscussionData,
        content: DesignDocContent,
    ) -> str:
        """Format the final document from template and content.

        Args:
            data: Discussion data.
            content: Generated content sections.

        Returns:
            Formatted document string.
        """
        now = datetime.utcnow()

        return self._template.format(
            module_name=data.module_name,
            version=GENERATOR_VERSION,
            timestamp=now.strftime("%Y-%m-%d %H:%M:%S UTC"),
            discussion_id=data.discussion_id,
            gdd_filename=data.gdd_filename,
            design_goals=content.design_goals,
            core_experience=content.core_experience,
            system_relations=content.system_relations,
            basic_gameplay=content.basic_gameplay,
            advanced_gameplay=content.advanced_gameplay,
            gameplay_examples=content.gameplay_examples,
            main_ui=content.main_ui,
            operation_flow=content.operation_flow,
            ui_navigation=content.ui_navigation,
            core_formulas=content.core_formulas,
            parameter_tables=content.parameter_tables,
            balance_goals=content.balance_goals,
            edge_cases=content.edge_cases,
            anti_cheat=content.anti_cheat,
            error_handling=content.error_handling,
            discussion_summary=content.discussion_summary,
            design_decisions=content.design_decisions,
            open_questions=content.open_questions,
        )

    def get_document(self, project_id: str, module_id: str) -> Optional[str]:
        """Get an existing design document.

        Args:
            project_id: Project identifier.
            module_id: Module identifier.

        Returns:
            Document content or None if not found.
        """
        path = self._get_output_path(project_id, module_id)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def list_documents(self, project_id: str) -> list[tuple[str, Path]]:
        """List all design documents for a project.

        Args:
            project_id: Project identifier.

        Returns:
            List of (module_id, path) tuples.
        """
        design_dir = self.data_dir / project_id / "design"
        if not design_dir.exists():
            return []

        docs = []
        for path in design_dir.glob("*-system.md"):
            module_id = path.stem.replace("-system", "")
            docs.append((module_id, path))

        return docs
