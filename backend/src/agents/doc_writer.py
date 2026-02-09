import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DocWriter:
    """文档写入工具 -- 直接 LLM 调用，不通过 CrewAI。"""

    def __init__(self, llm: Any, docs_dir: Path):
        self._llm = llm
        self._docs_dir = docs_dir
        self._docs_dir.mkdir(parents=True, exist_ok=True)

    def create_skeleton(self, doc_plan) -> None:
        """从 DocPlan 创建骨架 .md 文件。每个章节用 <!-- section:sN --> 标记。"""
        for file_plan in doc_plan.files:
            lines = [f"# {file_plan.title}\n"]
            for section in file_plan.sections:
                lines.append(f"\n<!-- section:{section.id} -->\n")
                lines.append(f"## {section.title}\n")
                lines.append(f"*{section.description}*\n")
                lines.append(f"\n<!-- /section:{section.id} -->\n")

            filepath = self._docs_dir / file_plan.filename
            filepath.write_text("\n".join(lines), encoding="utf-8")
            logger.info("Created skeleton: %s", filepath)

    def read_file(self, filename: str) -> str | None:
        filepath = self._docs_dir / filename
        if not filepath.exists():
            return None
        return filepath.read_text(encoding="utf-8")

    def read_section(self, filename: str, section_id: str) -> str:
        content = self.read_file(filename)
        if content is None:
            return ""
        pattern = rf"(<!-- section:{re.escape(section_id)} -->)(.*?)(<!-- /section:{re.escape(section_id)} -->)"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(2).strip()
        return ""

    def update_section(self, filename: str, section_id: str,
                       discussion_content: str, section_title: str) -> str:
        """用 LLM 更新指定章节，返回更新后的全文。"""
        current_content = self.read_file(filename)
        if current_content is None:
            logger.warning("File not found: %s", filename)
            return ""

        current_section = self.read_section(filename, section_id)

        prompt = f"""你是一个专业的游戏策划文档撰写者。

当前章节标题: {section_title}
当前章节内容:
{current_section if current_section else "(空 -- 待填充)"}

以下是团队讨论的内容摘要:
{discussion_content}

请根据讨论内容，撰写/更新这个章节。要求:
1. 如果章节已有内容，在其基础上增补和完善（不要推翻已有结论）
2. 如果章节为空，从零开始撰写
3. 输出纯 Markdown 格式（不要包含章节标题 ##，我会自动加）
4. 内容要专业、结构化，使用列表、表格等格式
5. 不要输出任何解释性文字，只输出章节正文内容

直接输出章节内容:"""

        try:
            response = self._llm.invoke(prompt)
            new_section_content = response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            logger.error("LLM call failed for section %s: %s", section_id, e)
            return current_content

        # Replace section content in file
        section_block = f"<!-- section:{section_id} -->\n## {section_title}\n\n{new_section_content}\n\n<!-- /section:{section_id} -->"
        pattern = rf"<!-- section:{re.escape(section_id)} -->.*?<!-- /section:{re.escape(section_id)} -->"
        updated_content = re.sub(pattern, section_block, current_content, flags=re.DOTALL)

        filepath = self._docs_dir / filename
        filepath.write_text(updated_content, encoding="utf-8")
        logger.info("Updated section %s in %s", section_id, filename)

        return updated_content

    def list_files(self) -> list[dict]:
        """列出所有 .md 文件信息。"""
        result = []
        for path in sorted(self._docs_dir.glob("*.md")):
            content = path.read_text(encoding="utf-8")
            # Extract title from first # heading
            title_match = re.match(r"^#\s+(.+)", content)
            title = title_match.group(1) if title_match else path.stem
            result.append({
                "filename": path.name,
                "title": title,
                "size": len(content.encode("utf-8")),
            })
        return result
