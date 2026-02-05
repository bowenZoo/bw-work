"""Unified GDD parser with format detection and file management."""

import hashlib
import json
import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Optional, Union

from src.project.models import GDDDocument, GDDStatus, ParsedText
from src.project.gdd.parsers import MarkdownParser, PdfParser, DocxParser
from src.project.gdd.parsers.base import GDDFormatParser, ParseError, UnsupportedFormatError

logger = logging.getLogger(__name__)

# Maximum file size: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024

# Supported file extensions
SUPPORTED_EXTENSIONS = {".md", ".markdown", ".mdown", ".pdf", ".docx"}

# Parser version for cache invalidation
PARSER_VERSION = "1.0.0"


class GDDParser:
    """Unified entry point for GDD document parsing.

    Handles:
    - Format detection based on file extension
    - File storage and organization
    - Caching based on content hash
    - Error handling and status management
    """

    def __init__(self, data_dir: str = "data/projects"):
        """Initialize the GDD parser.

        Args:
            data_dir: Base directory for project data storage.
        """
        self.data_dir = Path(data_dir)
        self._parsers: list[GDDFormatParser] = [
            MarkdownParser(),
            PdfParser(),
            DocxParser(),
        ]

    def _get_parser(self, extension: str) -> GDDFormatParser:
        """Get the appropriate parser for a file extension.

        Args:
            extension: File extension (e.g., ".md").

        Returns:
            Parser instance for the format.

        Raises:
            UnsupportedFormatError: If no parser supports the format.
        """
        for parser in self._parsers:
            if parser.supports(extension):
                return parser

        raise UnsupportedFormatError(
            f"Unsupported file format: {extension}. "
            f"Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    def _get_project_gdd_dir(self, project_id: str) -> Path:
        """Get the GDD directory for a project.

        Args:
            project_id: Project identifier.

        Returns:
            Path to the project's GDD directory.
        """
        return self.data_dir / project_id / "gdd"

    def _calculate_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of a file.

        Args:
            file_path: Path to the file.

        Returns:
            Hexadecimal hash string.
        """
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def validate_file(
        self,
        file_path: Optional[Path] = None,
        file_size: Optional[int] = None,
        filename: Optional[str] = None,
    ) -> None:
        """Validate a file before processing.

        Args:
            file_path: Path to the file (optional, for local files).
            file_size: File size in bytes (optional, for uploads).
            filename: Original filename (optional, for extension check).

        Raises:
            ValueError: If validation fails.
        """
        # Check file size
        if file_size is not None and file_size > MAX_FILE_SIZE:
            raise ValueError(
                f"File size ({file_size / 1024 / 1024:.1f}MB) exceeds "
                f"maximum allowed size ({MAX_FILE_SIZE / 1024 / 1024:.0f}MB)"
            )

        if file_path is not None and file_path.exists():
            actual_size = file_path.stat().st_size
            if actual_size > MAX_FILE_SIZE:
                raise ValueError(
                    f"File size ({actual_size / 1024 / 1024:.1f}MB) exceeds "
                    f"maximum allowed size ({MAX_FILE_SIZE / 1024 / 1024:.0f}MB)"
                )

        # Check file extension
        if filename:
            ext = Path(filename).suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                raise ValueError(
                    f"Unsupported file format: {ext}. "
                    f"Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}"
                )
        elif file_path:
            ext = file_path.suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                raise ValueError(
                    f"Unsupported file format: {ext}. "
                    f"Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}"
                )

    def save_upload(
        self,
        project_id: str,
        filename: str,
        file_content: Union[bytes, BinaryIO],
    ) -> tuple[str, Path]:
        """Save an uploaded file to the project directory.

        Args:
            project_id: Project identifier.
            filename: Original filename.
            file_content: File content as bytes or file-like object.

        Returns:
            Tuple of (gdd_id, saved_file_path).

        Raises:
            ValueError: If file validation fails.
        """
        # Generate GDD ID
        gdd_id = f"gdd_{uuid.uuid4().hex[:12]}"

        # Ensure directories exist
        gdd_dir = self._get_project_gdd_dir(project_id)
        original_dir = gdd_dir / "original"
        original_dir.mkdir(parents=True, exist_ok=True)

        # Determine save path
        ext = Path(filename).suffix.lower()
        save_filename = f"{gdd_id}{ext}"
        save_path = original_dir / save_filename

        # Save file
        if isinstance(file_content, bytes):
            save_path.write_bytes(file_content)
        else:
            with open(save_path, "wb") as f:
                shutil.copyfileobj(file_content, f)

        # Validate after saving
        try:
            self.validate_file(file_path=save_path, filename=filename)
        except ValueError:
            # Clean up on validation failure
            save_path.unlink(missing_ok=True)
            raise

        return gdd_id, save_path

    def parse(
        self,
        project_id: str,
        gdd_id: str,
        file_path: Path,
        filename: str,
    ) -> GDDDocument:
        """Parse a GDD file and save the results.

        Args:
            project_id: Project identifier.
            gdd_id: GDD document identifier.
            file_path: Path to the file to parse.
            filename: Original filename.

        Returns:
            GDDDocument with parsing results.
        """
        now = datetime.utcnow()
        content_hash = self._calculate_hash(file_path)

        # Setup paths
        gdd_dir = self._get_project_gdd_dir(project_id)
        parsed_dir = gdd_dir / "parsed"
        parsed_dir.mkdir(parents=True, exist_ok=True)
        parsed_path = parsed_dir / f"{gdd_id}.json"

        # Check cache
        if parsed_path.exists():
            try:
                with open(parsed_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if (
                    cached.get("content_hash") == content_hash
                    and cached.get("parser_version") == PARSER_VERSION
                ):
                    logger.info(f"Using cached parse result for {gdd_id}")
                    return GDDDocument.from_dict(cached)
            except (json.JSONDecodeError, KeyError):
                pass  # Cache invalid, re-parse

        # Create initial document record
        doc = GDDDocument(
            id=gdd_id,
            project_id=project_id,
            filename=filename,
            upload_time=now,
            raw_content_path=str(file_path),
            parsed_content_path=str(parsed_path),
            content_hash=content_hash,
            parser_version=PARSER_VERSION,
            status=GDDStatus.PARSING,
        )

        try:
            # Get appropriate parser
            ext = file_path.suffix.lower()
            parser = self._get_parser(ext)

            # Parse the file
            parsed_text = parser.parse(file_path)

            # Update document with success
            doc.status = GDDStatus.READY

            # Save parsed result
            result = doc.to_dict()
            result["parsed_text"] = {
                "title": parsed_text.title,
                "content": parsed_text.content,
                "sections": [
                    {
                        "title": s.title,
                        "level": s.level,
                        "content": s.content,
                        "start_line": s.start_line,
                        "end_line": s.end_line,
                    }
                    for s in parsed_text.sections
                ],
                "metadata": parsed_text.metadata,
            }

            # Atomic write
            temp_path = parsed_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            temp_path.replace(parsed_path)

            logger.info(f"Successfully parsed GDD {gdd_id}")
            return doc

        except ParseError as e:
            doc.status = GDDStatus.ERROR
            doc.error = str(e)
            logger.error(f"Parse error for GDD {gdd_id}: {e}")

            # Save error state
            with open(parsed_path, "w", encoding="utf-8") as f:
                json.dump(doc.to_dict(), f, ensure_ascii=False, indent=2)

            return doc

        except Exception as e:
            doc.status = GDDStatus.ERROR
            doc.error = f"Unexpected error: {str(e)}"
            logger.exception(f"Unexpected error parsing GDD {gdd_id}")

            # Save error state
            with open(parsed_path, "w", encoding="utf-8") as f:
                json.dump(doc.to_dict(), f, ensure_ascii=False, indent=2)

            return doc

    def get_document(self, project_id: str, gdd_id: str) -> Optional[GDDDocument]:
        """Get a GDD document by ID.

        Args:
            project_id: Project identifier.
            gdd_id: GDD document identifier.

        Returns:
            GDDDocument if found, None otherwise.
        """
        gdd_dir = self._get_project_gdd_dir(project_id)
        parsed_path = gdd_dir / "parsed" / f"{gdd_id}.json"

        if not parsed_path.exists():
            return None

        try:
            with open(parsed_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return GDDDocument.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def get_parsed_text(self, project_id: str, gdd_id: str) -> Optional[ParsedText]:
        """Get the parsed text content for a GDD.

        Args:
            project_id: Project identifier.
            gdd_id: GDD document identifier.

        Returns:
            ParsedText if available, None otherwise.
        """
        gdd_dir = self._get_project_gdd_dir(project_id)
        parsed_path = gdd_dir / "parsed" / f"{gdd_id}.json"

        if not parsed_path.exists():
            return None

        try:
            with open(parsed_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            parsed_text_data = data.get("parsed_text")
            if not parsed_text_data:
                return None

            from src.project.models import Section

            return ParsedText(
                title=parsed_text_data["title"],
                content=parsed_text_data["content"],
                sections=[
                    Section(
                        title=s["title"],
                        level=s["level"],
                        content=s["content"],
                        start_line=s["start_line"],
                        end_line=s["end_line"],
                    )
                    for s in parsed_text_data.get("sections", [])
                ],
                metadata=parsed_text_data.get("metadata", {}),
            )
        except (json.JSONDecodeError, KeyError):
            return None

    def list_documents(self, project_id: str) -> list[GDDDocument]:
        """List all GDD documents for a project.

        Args:
            project_id: Project identifier.

        Returns:
            List of GDDDocument objects.
        """
        gdd_dir = self._get_project_gdd_dir(project_id)
        parsed_dir = gdd_dir / "parsed"

        if not parsed_dir.exists():
            return []

        documents = []
        for path in parsed_dir.glob("gdd_*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                documents.append(GDDDocument.from_dict(data))
            except (json.JSONDecodeError, KeyError):
                continue

        # Sort by upload time descending
        documents.sort(key=lambda d: d.upload_time, reverse=True)
        return documents
