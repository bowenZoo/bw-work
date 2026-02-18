"""Document Organizer Agent - Splits discussion results into structured design documents."""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from crewai import Agent, Crew, Process, Task

from src.memory.base import Discussion, Message

logger = logging.getLogger(__name__)


@dataclass
class OrganizedDoc:
    """A single organized design document."""

    filename: str
    title: str
    content: str


@dataclass
class OrganizeResult:
    """Result of organizing discussion into documents."""

    discussion_id: str
    project_id: str
    topic: str
    files: list[OrganizedDoc]
    index_path: str
    created_at: datetime = field(default_factory=datetime.now)


class DocOrganizer:
    """Organizes discussion content into multiple structured design documents.

    Uses LLM to analyze discussion content and decide how to split it
    into separate planning documents per topic/feature.
    """

    def __init__(self, llm: Any | None = None, data_dir: str = "data/projects") -> None:
        self._llm = llm
        self._data_dir = data_dir
        self._agent: Agent | None = None

    def _build_agent(self) -> Agent:
        if self._agent is None:
            agent_kwargs: dict[str, Any] = {
                "role": "Game Design Document Organizer",
                "goal": "Analyze game design discussions and organize them into well-structured, separate planning documents",
                "backstory": (
                    "你是一位资深的游戏策划文档专家，擅长将复杂的设计讨论整理成清晰、"
                    "可执行的策划文档。你能准确判断哪些内容应该独立成文档，"
                    "哪些内容可以合并，确保每个文档都聚焦于一个明确的设计主题。"
                ),
                "tools": [],
                "verbose": False,
                "allow_delegation": False,
                "max_iter": 10,
            }
            if self._llm is not None:
                agent_kwargs["llm"] = self._llm
            self._agent = Agent(**agent_kwargs)
        return self._agent

    def create_organize_task(self, discussion: Discussion) -> Task:
        """Create a CrewAI Task to analyze and split discussion content.

        The LLM will output a JSON array of documents to create.
        """
        messages_text = "\n\n".join(
            f"**{msg.agent_role}**: {msg.content}" for msg in discussion.messages
        )

        # Include summary if available
        summary_section = ""
        if discussion.summary:
            summary_section = f"\n**讨论总结**:\n{discussion.summary}\n"

        description = f"""分析以下游戏策划讨论内容，将有价值的设计信息整理成独立的策划文档。

**讨论主题**: {discussion.topic}
{summary_section}
**讨论内容**:
{messages_text}

请你判断讨论中涉及了哪些独立的设计主题或功能模块，然后为每个主题生成一个独立的策划文档。

规则：
1. 每个文档应聚焦一个明确的设计主题（如"战斗系统"、"数值平衡"、"UI流程"等）
2. 小的、相关的内容可以合并到一个文档中
3. 大的、独立的功能应该各自一个文档
4. 每个文档内容要完整、可读，不要只是罗列要点
5. 文件名使用中文，用下划线连接，以 .md 结尾
6. 如果整个讨论就一个主题，生成一个文档即可

请严格以如下 JSON 格式输出（不要有其他文字，只输出 JSON）：

```json
[
  {{
    "filename": "战斗系统设计.md",
    "title": "战斗系统设计方案",
    "content": "# 战斗系统设计方案\\n\\n## 概述\\n...完整的 Markdown 内容..."
  }},
  {{
    "filename": "数值平衡方案.md",
    "title": "数值平衡方案",
    "content": "# 数值平衡方案\\n\\n## 概述\\n...完整的 Markdown 内容..."
  }}
]
```"""

        expected_output = "A JSON array of document objects, each with filename, title, and content fields."

        return Task(
            name=f"organize-{discussion.id}",
            description=description,
            expected_output=expected_output,
            agent=self._build_agent(),
        )

    def parse_result(self, raw_result: str) -> list[OrganizedDoc]:
        """Parse LLM output into a list of OrganizedDoc objects.

        Handles various LLM output formats (with/without code fences).
        """
        text = raw_result.strip()

        # Extract JSON from code fences if present
        code_block = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
        if code_block:
            text = code_block.group(1).strip()

        # Try to find JSON array
        bracket_start = text.find("[")
        bracket_end = text.rfind("]")
        if bracket_start != -1 and bracket_end != -1:
            text = text[bracket_start : bracket_end + 1]

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM output as JSON: %s", e)
            logger.debug("Raw output: %s", raw_result[:500])
            return []

        if not isinstance(data, list):
            logger.error("LLM output is not a JSON array")
            return []

        docs = []
        for item in data:
            if not isinstance(item, dict):
                continue
            filename = item.get("filename", "").strip()
            title = item.get("title", "").strip()
            content = item.get("content", "").strip()
            if not filename or not content:
                continue
            # Sanitize filename
            filename = self._sanitize_filename(filename)
            if not filename:
                continue
            docs.append(OrganizedDoc(filename=filename, title=title or filename, content=content))

        return docs

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent path traversal and invalid chars."""
        # Reject if contains path separators (don't just strip them)
        if "/" in filename or "\\" in filename:
            return ""
        # Remove dangerous patterns
        filename = filename.lstrip(".")
        # Ensure .md extension
        if not filename.endswith(".md"):
            filename += ".md"
        # Validate remaining chars (allow Chinese, alphanumeric, underscore, hyphen, dot)
        if not re.match(r'^[\w\u4e00-\u9fff\-\.]+$', filename):
            return ""
        return filename

    def _get_docs_dir(self, project_id: str, discussion_id: str) -> Path:
        return Path(self._data_dir) / project_id / "design_docs" / discussion_id

    def save_documents(
        self,
        discussion_id: str,
        project_id: str,
        topic: str,
        docs: list[OrganizedDoc],
    ) -> OrganizeResult:
        """Save organized documents to disk.

        Creates directory structure and writes all files + index.
        """
        docs_dir = self._get_docs_dir(project_id, discussion_id)
        docs_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now()
        file_infos = []

        for doc in docs:
            file_path = docs_dir / doc.filename
            file_path.write_text(doc.content, encoding="utf-8")
            file_infos.append({
                "filename": doc.filename,
                "title": doc.title,
                "size": len(doc.content.encode("utf-8")),
                "created_at": now.isoformat(),
            })

        # Write index
        index = {
            "discussion_id": discussion_id,
            "project_id": project_id,
            "topic": topic,
            "created_at": now.isoformat(),
            "files": file_infos,
        }
        index_path = docs_dir / "_index.json"
        index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

        return OrganizeResult(
            discussion_id=discussion_id,
            project_id=project_id,
            topic=topic,
            files=docs,
            index_path=str(index_path),
            created_at=now,
        )

    def load_index(self, project_id: str, discussion_id: str) -> dict | None:
        """Load the index file for a discussion's design docs."""
        index_path = self._get_docs_dir(project_id, discussion_id) / "_index.json"
        if not index_path.exists():
            return None
        try:
            return json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def load_document(self, project_id: str, discussion_id: str, filename: str) -> str | None:
        """Load a single design document's content."""
        sanitized = self._sanitize_filename(filename)
        if not sanitized:
            return None
        file_path = self._get_docs_dir(project_id, discussion_id) / sanitized
        if not file_path.exists():
            return None
        # Extra safety: ensure file is under the expected directory
        if not file_path.resolve().is_relative_to(self._get_docs_dir(project_id, discussion_id).resolve()):
            return None
        try:
            return file_path.read_text(encoding="utf-8")
        except Exception:
            return None

    def run_organize(self, discussion: Discussion) -> OrganizeResult:
        """Run the full organize pipeline synchronously.

        Creates a CrewAI crew, runs the organize task, parses and saves results.
        """
        task = self.create_organize_task(discussion)
        crew = Crew(
            agents=[self._build_agent()],
            tasks=[task],
            process=Process.sequential,
            verbose=False,
        )

        result = crew.kickoff()
        raw = str(result)

        docs = self.parse_result(raw)
        if not docs:
            logger.warning("DocOrganizer produced no documents for discussion %s", discussion.id)
            # Create a single fallback document from the raw result
            docs = [OrganizedDoc(
                filename="讨论总结.md",
                title=discussion.topic,
                content=f"# {discussion.topic}\n\n{raw}",
            )]

        return self.save_documents(
            discussion_id=discussion.id,
            project_id=discussion.project_id,
            topic=discussion.topic,
            docs=docs,
        )
