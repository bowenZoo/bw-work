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

    # ------------------------------------------------------------------
    # 动态文档结构操作方法
    # ------------------------------------------------------------------

    def add_section_marker(
        self,
        filename: str,
        section_id: str,
        title: str,
        description: str,
        after_section_id: str | None = None,
    ) -> str:
        """在指定文件中追加新 section marker。

        如果提供 after_section_id，则新 section 会插入在该 section 结束标记之后；
        否则追加到文件末尾。

        Args:
            filename: 目标文件名。
            section_id: 新 section 的 ID，格式如 "s5"。
            title: 章节标题。
            description: 章节描述（斜体占位文本）。
            after_section_id: 在此 section 之后插入。None 表示追加到末尾。

        Returns:
            更新后的文件全文。
        """
        content = self.read_file(filename)
        if content is None:
            logger.warning("File not found: %s", filename)
            return ""

        new_block = (
            f"\n<!-- section:{section_id} -->\n"
            f"## {title}\n"
            f"*{description}*\n"
            f"\n<!-- /section:{section_id} -->\n"
        )

        if after_section_id:
            end_marker = f"<!-- /section:{after_section_id} -->"
            idx = content.find(end_marker)
            if idx != -1:
                insert_pos = idx + len(end_marker)
                updated = content[:insert_pos] + "\n" + new_block + content[insert_pos:]
            else:
                logger.warning(
                    "after_section_id %s not found in %s, appending to end",
                    after_section_id, filename,
                )
                updated = content + "\n" + new_block
        else:
            updated = content + "\n" + new_block

        filepath = self._docs_dir / filename
        filepath.write_text(updated, encoding="utf-8")
        logger.info("Added section %s in %s", section_id, filename)
        return updated

    def split_section_content(
        self,
        filename: str,
        old_section_id: str,
        new_sections: list[dict[str, str]],
    ) -> str:
        """将一个 section 拆分为多个新 section。

        读取原 section 的内容，调用 LLM 将其拆分到新 section 中，
        然后用新的 marker 替换旧的。

        Args:
            filename: 目标文件名。
            old_section_id: 要拆分的原 section ID。
            new_sections: 新 section 列表，每项包含 "id", "title", "description"。

        Returns:
            更新后的文件全文。
        """
        content = self.read_file(filename)
        if content is None:
            logger.warning("File not found: %s", filename)
            return ""

        old_content = self.read_section(filename, old_section_id)

        sections_desc = "\n".join(
            f"- {s['id']}: {s['title']} — {s['description']}"
            for s in new_sections
        )

        prompt = f"""你是专业的游戏策划文档编辑。

以下是一个章节的现有内容，需要拆分成多个新章节：

原有内容：
{old_content if old_content else "(空)"}

请将上述内容拆分到以下新章节中：
{sections_desc}

输出格式要求（严格遵守）：
对每个新章节，输出如下块：
===SECTION:{new_sections[0]['id']}===
（该章节的内容，纯 Markdown，不含标题 ##）
===END===

按上述格式逐个输出所有章节。如果原内容不足以覆盖某章节，写一句占位说明即可。"""

        try:
            response = self._llm.invoke(prompt)
            llm_output = response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            logger.error("LLM call failed for split_section_content: %s", e)
            return content

        # Parse LLM output and build replacement blocks
        replacement_blocks: list[str] = []
        for sec in new_sections:
            sec_id = sec["id"]
            sec_title = sec["title"]
            pattern = rf"===SECTION:{re.escape(sec_id)}===(.*?)===END==="
            match = re.search(pattern, llm_output, re.DOTALL)
            sec_content = match.group(1).strip() if match else f"*{sec.get('description', '待填充')}*"
            block = (
                f"<!-- section:{sec_id} -->\n"
                f"## {sec_title}\n\n"
                f"{sec_content}\n\n"
                f"<!-- /section:{sec_id} -->"
            )
            replacement_blocks.append(block)

        combined_replacement = "\n\n".join(replacement_blocks)

        # Replace old section marker with new blocks
        old_pattern = rf"<!-- section:{re.escape(old_section_id)} -->.*?<!-- /section:{re.escape(old_section_id)} -->"
        updated = re.sub(old_pattern, combined_replacement, content, flags=re.DOTALL)

        filepath = self._docs_dir / filename
        filepath.write_text(updated, encoding="utf-8")
        logger.info("Split section %s into %d sections in %s",
                     old_section_id, len(new_sections), filename)
        return updated

    def merge_section_content(
        self,
        filename: str,
        section_ids: list[str],
        merged_section_id: str,
        merged_title: str,
    ) -> str:
        """将多个 section 合并为一个。

        读取所有待合并 section 的内容，调用 LLM 合并，用新的 marker 替换。

        Args:
            filename: 目标文件名。
            section_ids: 要合并的 section ID 列表（按顺序）。
            merged_section_id: 合并后的 section ID。
            merged_title: 合并后的章节标题。

        Returns:
            更新后的文件全文。
        """
        content = self.read_file(filename)
        if content is None:
            logger.warning("File not found: %s", filename)
            return ""

        sections_text = []
        for sid in section_ids:
            sec_content = self.read_section(filename, sid)
            sections_text.append(f"### {sid}\n{sec_content if sec_content else '(空)'}")

        prompt = f"""你是专业的游戏策划文档编辑。

以下多个章节需要合并为一个章节，标题为「{merged_title}」：

{chr(10).join(sections_text)}

请将以上内容合并整理为一个连贯的章节。要求：
1. 保留所有关键信息，去除重复
2. 结构清晰，逻辑通顺
3. 输出纯 Markdown 格式（不含章节标题 ##）
4. 不要输出解释性文字，只输出合并后的内容

直接输出合并后的内容："""

        try:
            response = self._llm.invoke(prompt)
            merged_content = response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            logger.error("LLM call failed for merge_section_content: %s", e)
            return content

        merged_block = (
            f"<!-- section:{merged_section_id} -->\n"
            f"## {merged_title}\n\n"
            f"{merged_content.strip()}\n\n"
            f"<!-- /section:{merged_section_id} -->"
        )

        # Replace the first section with the merged block
        first_id = section_ids[0]
        first_pattern = rf"<!-- section:{re.escape(first_id)} -->.*?<!-- /section:{re.escape(first_id)} -->"
        updated = re.sub(first_pattern, merged_block, content, flags=re.DOTALL)

        # Remove remaining sections
        for sid in section_ids[1:]:
            remove_pattern = rf"\n*<!-- section:{re.escape(sid)} -->.*?<!-- /section:{re.escape(sid)} -->\n*"
            updated = re.sub(remove_pattern, "\n", updated, flags=re.DOTALL)

        filepath = self._docs_dir / filename
        filepath.write_text(updated, encoding="utf-8")
        logger.info("Merged sections %s into %s in %s",
                     section_ids, merged_section_id, filename)
        return updated

    def create_new_file(self, file_plan) -> None:
        """创建新的骨架 .md 文件。

        与 create_skeleton 中单文件逻辑一致。

        Args:
            file_plan: 文件规划对象，需包含 title, filename, sections 属性。
                       每个 section 需包含 id, title, description。
        """
        lines = [f"# {file_plan.title}\n"]
        for section in file_plan.sections:
            lines.append(f"\n<!-- section:{section.id} -->\n")
            lines.append(f"## {section.title}\n")
            lines.append(f"*{section.description}*\n")
            lines.append(f"\n<!-- /section:{section.id} -->\n")

        filepath = self._docs_dir / file_plan.filename
        filepath.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Created new file: %s", filepath)
