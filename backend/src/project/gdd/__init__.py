"""GDD (Game Design Document) processing module.

This module provides functionality for:
- Parsing GDD files in various formats (Markdown, PDF, Word)
- Detecting functional modules within GDDs using AI
"""

from src.project.gdd.parsers import MarkdownParser, PdfParser, DocxParser

__all__ = ["MarkdownParser", "PdfParser", "DocxParser"]
