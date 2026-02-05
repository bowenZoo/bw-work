"""PDF document parser using PyMuPDF (fitz)."""

import re
from pathlib import Path
from typing import Optional

from src.project.models import ParsedText, Section
from src.project.gdd.parsers.base import GDDFormatParser, ParseError, ScanDocumentError


# Minimum character count to consider PDF as having extractable text
MIN_TEXT_CHARS = 500


class PdfParser(GDDFormatParser):
    """Parser for PDF documents.

    Uses PyMuPDF (fitz) for fast text extraction. Note that scanned PDFs
    (image-only) are not supported and will raise ScanDocumentError.
    """

    VERSION = "1.0.0"
    SUPPORTED_EXTENSIONS = {".pdf"}

    def supports(self, file_extension: str) -> bool:
        """Check if this parser supports the given file extension."""
        return file_extension.lower() in self.SUPPORTED_EXTENSIONS

    def parse(self, file_path: Path) -> ParsedText:
        """Parse a PDF document.

        Args:
            file_path: Path to the PDF file.

        Returns:
            ParsedText with document content and section structure.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ScanDocumentError: If PDF appears to be scanned (no extractable text).
            ParseError: If parsing fails.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ParseError("PyMuPDF (fitz) is required for PDF parsing. Install with: pip install PyMuPDF")

        try:
            doc = fitz.open(str(file_path))
        except Exception as e:
            raise ParseError(f"Failed to open PDF: {e}")

        try:
            # Extract text from all pages
            full_text = ""
            page_texts = []

            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                page_texts.append(text)
                full_text += text + "\n"

            # Check if this is a scanned document
            if len(full_text.strip()) < MIN_TEXT_CHARS:
                raise ScanDocumentError(
                    f"PDF contains very little extractable text ({len(full_text.strip())} chars). "
                    "This may be a scanned document. OCR is not currently supported."
                )

            # Extract metadata
            metadata = self._extract_metadata(doc)

            # Extract sections by analyzing text structure
            sections = self._extract_sections(full_text)

            # Extract title
            title = self._extract_title(full_text, metadata, sections)

            return ParsedText(
                title=title,
                content=full_text,
                sections=sections,
                metadata=metadata,
            )
        finally:
            doc.close()

    def _extract_metadata(self, doc) -> dict:
        """Extract metadata from PDF document properties.

        Args:
            doc: PyMuPDF document object.

        Returns:
            Dictionary of metadata.
        """
        metadata = {}
        pdf_meta = doc.metadata

        if pdf_meta:
            if pdf_meta.get("title"):
                metadata["title"] = pdf_meta["title"]
            if pdf_meta.get("author"):
                metadata["author"] = pdf_meta["author"]
            if pdf_meta.get("subject"):
                metadata["subject"] = pdf_meta["subject"]
            if pdf_meta.get("keywords"):
                metadata["keywords"] = pdf_meta["keywords"]
            if pdf_meta.get("creationDate"):
                metadata["created"] = pdf_meta["creationDate"]
            if pdf_meta.get("modDate"):
                metadata["modified"] = pdf_meta["modDate"]

        metadata["page_count"] = len(doc)

        return metadata

    def _extract_sections(self, content: str) -> list[Section]:
        """Extract section structure from PDF text.

        Uses heuristics to identify headings based on:
        - Numbered sections (1. Title, 1.1 Subtitle)
        - All caps lines
        - Short lines followed by longer content

        Args:
            content: Full text content.

        Returns:
            List of Section objects.
        """
        sections = []
        lines = content.split("\n")
        current_section: Optional[dict] = None

        # Patterns for detecting headings
        numbered_pattern = re.compile(r"^\s*(\d+(?:\.\d+)*)\s+(.+)$")
        caps_pattern = re.compile(r"^[A-Z\s]{5,}$")

        for i, line in enumerate(lines):
            line_num = i + 1
            stripped = line.strip()

            if not stripped:
                if current_section:
                    current_section["content_lines"].append("")
                continue

            is_heading = False
            level = 1
            title = stripped

            # Check for numbered heading
            num_match = numbered_pattern.match(stripped)
            if num_match:
                number = num_match.group(1)
                title = num_match.group(2).strip()
                level = number.count(".") + 1
                is_heading = True
            # Check for all caps (potential heading)
            elif caps_pattern.match(stripped) and len(stripped) < 80:
                is_heading = True
            # Check for short line that could be a title
            elif len(stripped) < 60 and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # If next line is longer or separated, this might be a heading
                if len(next_line) > len(stripped) * 2 or not next_line:
                    # Additional check: doesn't end with punctuation typical of sentences
                    if not stripped[-1] in ".,:;!?":
                        is_heading = True

            if is_heading:
                # Close previous section
                if current_section:
                    current_section["end_line"] = line_num - 1
                    sections.append(self._create_section(current_section))

                current_section = {
                    "title": title,
                    "level": level,
                    "start_line": line_num,
                    "content_lines": [],
                }
            elif current_section:
                current_section["content_lines"].append(stripped)

        # Close final section
        if current_section:
            current_section["end_line"] = len(lines)
            sections.append(self._create_section(current_section))

        return sections

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
        1. PDF metadata title
        2. First section title
        3. First non-empty line

        Args:
            content: Full document content.
            metadata: Extracted metadata.
            sections: Extracted sections.

        Returns:
            Document title.
        """
        # Try PDF metadata
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
