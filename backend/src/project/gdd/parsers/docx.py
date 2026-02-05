"""Word document parser using python-docx."""

import re
from pathlib import Path
from typing import Optional

from src.project.models import ParsedText, Section
from src.project.gdd.parsers.base import GDDFormatParser, ParseError


class DocxParser(GDDFormatParser):
    """Parser for Word (.docx) documents.

    Uses python-docx library to extract text and structure from
    Microsoft Word documents.
    """

    VERSION = "1.0.0"
    SUPPORTED_EXTENSIONS = {".docx"}

    def supports(self, file_extension: str) -> bool:
        """Check if this parser supports the given file extension."""
        return file_extension.lower() in self.SUPPORTED_EXTENSIONS

    def parse(self, file_path: Path) -> ParsedText:
        """Parse a Word document.

        Args:
            file_path: Path to the Word file.

        Returns:
            ParsedText with document content and section structure.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ParseError: If parsing fails.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            from docx import Document
            from docx.opc.exceptions import PackageNotFoundError
        except ImportError:
            raise ParseError("python-docx is required for Word parsing. Install with: pip install python-docx")

        try:
            doc = Document(str(file_path))
        except PackageNotFoundError:
            raise ParseError(f"Invalid or corrupted Word document: {file_path}")
        except Exception as e:
            raise ParseError(f"Failed to open Word document: {e}")

        # Extract text and structure
        content_lines = []
        sections = []
        current_section: Optional[dict] = None
        line_num = 0

        for para in doc.paragraphs:
            text = para.text.strip()
            line_num += 1

            if not text:
                if current_section:
                    current_section["content_lines"].append("")
                content_lines.append("")
                continue

            # Check if this is a heading
            is_heading = False
            level = 1

            # Check paragraph style for heading
            style_name = para.style.name.lower() if para.style else ""

            if "heading" in style_name:
                is_heading = True
                # Extract level from style name (e.g., "Heading 1", "Heading 2")
                level_match = re.search(r"(\d+)", style_name)
                if level_match:
                    level = int(level_match.group(1))
            elif "title" in style_name:
                is_heading = True
                level = 1

            if is_heading:
                # Close previous section
                if current_section:
                    current_section["end_line"] = line_num - 1
                    sections.append(self._create_section(current_section))

                current_section = {
                    "title": text,
                    "level": level,
                    "start_line": line_num,
                    "content_lines": [],
                }
            elif current_section:
                current_section["content_lines"].append(text)

            content_lines.append(text)

        # Close final section
        if current_section:
            current_section["end_line"] = line_num
            sections.append(self._create_section(current_section))

        full_content = "\n".join(content_lines)

        # Extract metadata
        metadata = self._extract_metadata(doc)

        # Extract title
        title = self._extract_title(full_content, metadata, sections)

        return ParsedText(
            title=title,
            content=full_content,
            sections=sections,
            metadata=metadata,
        )

    def _extract_metadata(self, doc) -> dict:
        """Extract metadata from Word document properties.

        Args:
            doc: python-docx Document object.

        Returns:
            Dictionary of metadata.
        """
        metadata = {}
        core = doc.core_properties

        if core.title:
            metadata["title"] = core.title
        if core.author:
            metadata["author"] = core.author
        if core.subject:
            metadata["subject"] = core.subject
        if core.keywords:
            metadata["keywords"] = core.keywords
        if core.created:
            metadata["created"] = core.created.isoformat() if core.created else None
        if core.modified:
            metadata["modified"] = core.modified.isoformat() if core.modified else None
        if core.last_modified_by:
            metadata["last_modified_by"] = core.last_modified_by

        return metadata

    def _create_section(self, section_data: dict) -> Section:
        """Create a Section object from parsed data."""
        content = "\n".join(section_data.get("content_lines", []))
        return Section(
            title=section_data["title"],
            level=section_data["level"],
            content=content.strip(),
            start_line=section_data["start_line"],
            end_line=section_data["end_line"],
        )

    def _extract_title(self, content: str, metadata: dict, sections: list[Section]) -> str:
        """Extract the document title.

        Priority:
        1. Document metadata title
        2. First heading section
        3. First non-empty line

        Args:
            content: Full document content.
            metadata: Extracted metadata.
            sections: Extracted sections.

        Returns:
            Document title.
        """
        # Try document metadata
        if metadata.get("title"):
            return metadata["title"]

        # Try first section
        if sections:
            return sections[0].title

        # Fall back to first non-empty line
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped:
                return stripped[:100]

        return "Untitled Document"
