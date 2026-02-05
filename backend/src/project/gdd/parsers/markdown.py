"""Markdown document parser using markdown-it-py."""

import re
from pathlib import Path
from typing import Optional

from src.project.models import ParsedText, Section
from src.project.gdd.parsers.base import GDDFormatParser, ParseError


class MarkdownParser(GDDFormatParser):
    """Parser for Markdown (.md) documents.

    Uses regex-based parsing for heading extraction and structure detection.
    This approach is simpler and more reliable for GDD-style documents than
    full AST parsing.
    """

    VERSION = "1.0.0"
    SUPPORTED_EXTENSIONS = {".md", ".markdown", ".mdown"}

    def supports(self, file_extension: str) -> bool:
        """Check if this parser supports the given file extension."""
        return file_extension.lower() in self.SUPPORTED_EXTENSIONS

    def parse(self, file_path: Path) -> ParsedText:
        """Parse a Markdown document.

        Args:
            file_path: Path to the Markdown file.

        Returns:
            ParsedText with document content and section structure.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ParseError: If parsing fails.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Try with different encodings
            try:
                content = file_path.read_text(encoding="gbk")
            except UnicodeDecodeError:
                content = file_path.read_text(encoding="latin-1")

        return self._parse_content(content)

    def _parse_content(self, content: str) -> ParsedText:
        """Parse Markdown content string.

        Args:
            content: Raw Markdown content.

        Returns:
            ParsedText with document structure.
        """
        lines = content.split("\n")
        sections = self._extract_sections(lines)
        title = self._extract_title(content, sections)
        metadata = self._extract_metadata(content)

        return ParsedText(
            title=title,
            content=content,
            sections=sections,
            metadata=metadata,
        )

    def _extract_sections(self, lines: list[str]) -> list[Section]:
        """Extract section structure from Markdown lines.

        Args:
            lines: List of document lines.

        Returns:
            List of Section objects representing the document structure.
        """
        sections = []
        current_section: Optional[dict] = None

        # Regex for ATX-style headings (# Heading)
        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$")
        # Regex for Setext-style headings (underlined)
        setext_h1_pattern = re.compile(r"^=+\s*$")
        setext_h2_pattern = re.compile(r"^-+\s*$")

        for i, line in enumerate(lines):
            line_num = i + 1  # 1-indexed

            # Check for ATX heading
            match = heading_pattern.match(line)
            if match:
                # Close previous section
                if current_section:
                    current_section["end_line"] = line_num - 1
                    sections.append(self._create_section(current_section))

                level = len(match.group(1))
                title = match.group(2).strip()

                current_section = {
                    "title": title,
                    "level": level,
                    "start_line": line_num,
                    "content_lines": [],
                }
                continue

            # Check for Setext heading (previous line is title)
            if i > 0:
                prev_line = lines[i - 1].strip()
                if prev_line and setext_h1_pattern.match(line):
                    # H1 setext
                    if current_section:
                        current_section["end_line"] = line_num - 2
                        sections.append(self._create_section(current_section))

                    current_section = {
                        "title": prev_line,
                        "level": 1,
                        "start_line": line_num - 1,
                        "content_lines": [],
                    }
                    continue
                elif prev_line and setext_h2_pattern.match(line) and len(line.strip()) >= 3:
                    # H2 setext
                    if current_section:
                        current_section["end_line"] = line_num - 2
                        sections.append(self._create_section(current_section))

                    current_section = {
                        "title": prev_line,
                        "level": 2,
                        "start_line": line_num - 1,
                        "content_lines": [],
                    }
                    continue

            # Add line to current section content
            if current_section:
                current_section["content_lines"].append(line)

        # Close final section
        if current_section:
            current_section["end_line"] = len(lines)
            sections.append(self._create_section(current_section))

        return sections

    def _create_section(self, section_data: dict) -> Section:
        """Create a Section object from parsed data.

        Args:
            section_data: Dictionary with section data.

        Returns:
            Section object.
        """
        content = "\n".join(section_data.get("content_lines", []))
        return Section(
            title=section_data["title"],
            level=section_data["level"],
            content=content.strip(),
            start_line=section_data["start_line"],
            end_line=section_data["end_line"],
        )

    def _extract_title(self, content: str, sections: list[Section]) -> str:
        """Extract the document title.

        Priority:
        1. First H1 heading
        2. YAML frontmatter title
        3. First non-empty line

        Args:
            content: Full document content.
            sections: Extracted sections.

        Returns:
            Document title.
        """
        # Try to find first H1
        for section in sections:
            if section.level == 1:
                return section.title

        # Try YAML frontmatter
        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if frontmatter_match:
            fm_content = frontmatter_match.group(1)
            title_match = re.search(r"^title:\s*(.+)$", fm_content, re.MULTILINE)
            if title_match:
                title = title_match.group(1).strip()
                # Remove quotes if present
                if (title.startswith('"') and title.endswith('"')) or (
                    title.startswith("'") and title.endswith("'")
                ):
                    title = title[1:-1]
                return title

        # Fall back to first non-empty line
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                return stripped[:100]

        return "Untitled Document"

    def _extract_metadata(self, content: str) -> dict:
        """Extract metadata from YAML frontmatter.

        Args:
            content: Full document content.

        Returns:
            Dictionary of metadata key-value pairs.
        """
        metadata = {}

        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if frontmatter_match:
            fm_content = frontmatter_match.group(1)
            for line in fm_content.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip().lower()
                    value = value.strip()
                    # Remove quotes
                    if (value.startswith('"') and value.endswith('"')) or (
                        value.startswith("'") and value.endswith("'")
                    ):
                        value = value[1:-1]
                    metadata[key] = value

        return metadata
