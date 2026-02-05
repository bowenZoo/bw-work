"""Base interface for GDD format parsers."""

from abc import ABC, abstractmethod
from pathlib import Path

from src.project.models import ParsedText


class GDDFormatParser(ABC):
    """Abstract base class for GDD format parsers.

    Each parser implementation handles a specific document format
    and returns a unified ParsedText structure.
    """

    # Parser version for cache invalidation
    VERSION: str = "1.0.0"

    @abstractmethod
    def parse(self, file_path: Path) -> ParsedText:
        """Parse a document file and return structured text.

        Args:
            file_path: Path to the document file.

        Returns:
            ParsedText containing the document content and structure.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the file format is invalid or unsupported.
            RuntimeError: If parsing fails.
        """
        pass

    @abstractmethod
    def supports(self, file_extension: str) -> bool:
        """Check if this parser supports the given file extension.

        Args:
            file_extension: File extension (e.g., ".md", ".pdf").

        Returns:
            True if the extension is supported, False otherwise.
        """
        pass

    @property
    def version(self) -> str:
        """Get the parser version."""
        return self.VERSION


class ParseError(Exception):
    """Exception raised when document parsing fails."""

    pass


class UnsupportedFormatError(ParseError):
    """Exception raised for unsupported file formats."""

    pass


class ScanDocumentError(ParseError):
    """Exception raised when PDF appears to be a scanned document without text.

    This error indicates OCR would be needed to extract text, which is not
    currently supported.
    """

    def __init__(self, message: str = "PDF appears to be a scanned document. OCR is not supported."):
        super().__init__(message)
