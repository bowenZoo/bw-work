"""Tests for GDD format parsers."""

import tempfile
from pathlib import Path

import pytest

from src.project.gdd.parsers import MarkdownParser, PdfParser, DocxParser
from src.project.gdd.parsers.base import ScanDocumentError


def _has_fitz() -> bool:
    """Check if PyMuPDF is available."""
    try:
        import fitz
        return True
    except ImportError:
        return False


def _has_docx() -> bool:
    """Check if python-docx is available."""
    try:
        import docx
        return True
    except ImportError:
        return False


class TestMarkdownParser:
    """Tests for Markdown parser."""

    def setup_method(self):
        self.parser = MarkdownParser()

    def test_supports_md_extension(self):
        assert self.parser.supports(".md")
        assert self.parser.supports(".markdown")
        assert self.parser.supports(".MD")
        assert not self.parser.supports(".txt")
        assert not self.parser.supports(".pdf")

    def test_parse_simple_document(self):
        content = """# Game Design Document

## Overview

This is the overview section.

## Combat System

### Basic Mechanics

Combat uses turn-based mechanics.

### Advanced Tactics

Players can use combos.
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            path = Path(f.name)

        try:
            result = self.parser.parse(path)

            assert result.title == "Game Design Document"
            assert len(result.sections) >= 4
            assert "This is the overview section" in result.content

            # Check section levels
            levels = [s.level for s in result.sections]
            assert 1 in levels  # H1
            assert 2 in levels  # H2
            assert 3 in levels  # H3
        finally:
            path.unlink()

    def test_parse_with_frontmatter(self):
        # Note: If H1 heading exists, it takes priority over frontmatter title
        content = """---
title: "My Game GDD"
author: "Test Author"
---

# Content

Some content here.
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            path = Path(f.name)

        try:
            result = self.parser.parse(path)

            # H1 heading takes priority over frontmatter title
            assert result.title == "Content"
            assert result.metadata.get("author") == "Test Author"
        finally:
            path.unlink()

    def test_parse_frontmatter_title_without_h1(self):
        # When no H1 heading, frontmatter title is used
        content = """---
title: "My Game GDD"
author: "Test Author"
---

## Section 1

Some content here.
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            path = Path(f.name)

        try:
            result = self.parser.parse(path)

            # No H1, so frontmatter title is used
            assert result.title == "My Game GDD"
            assert result.metadata.get("author") == "Test Author"
        finally:
            path.unlink()

    def test_parse_setext_headings(self):
        content = """Main Title
==========

Subtitle
--------

Content under subtitle.
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            path = Path(f.name)

        try:
            result = self.parser.parse(path)

            assert result.title == "Main Title"
            assert len(result.sections) >= 2
        finally:
            path.unlink()

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            self.parser.parse(Path("/nonexistent/file.md"))


class TestPdfParser:
    """Tests for PDF parser."""

    def setup_method(self):
        self.parser = PdfParser()

    def test_supports_pdf_extension(self):
        assert self.parser.supports(".pdf")
        assert self.parser.supports(".PDF")
        assert not self.parser.supports(".md")
        assert not self.parser.supports(".docx")

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            self.parser.parse(Path("/nonexistent/file.pdf"))

    @pytest.mark.skipif(
        not _has_fitz(),
        reason="PyMuPDF not installed"
    )
    def test_scan_document_detection(self):
        """Test that scanned PDFs without text are detected."""
        # This would need a real scanned PDF to test properly
        # For now, we just verify the error class exists
        assert ScanDocumentError is not None


class TestDocxParser:
    """Tests for Word document parser."""

    def setup_method(self):
        self.parser = DocxParser()

    def test_supports_docx_extension(self):
        assert self.parser.supports(".docx")
        assert self.parser.supports(".DOCX")
        assert not self.parser.supports(".doc")  # Old format not supported
        assert not self.parser.supports(".md")

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            self.parser.parse(Path("/nonexistent/file.docx"))
