"""Tests for design documents feature.

Covers: DocOrganizer parsing, file saving, API endpoints, security checks.
"""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.agents.doc_organizer import DocOrganizer, OrganizedDoc
from src.api.main import app
from src.api.routes.discussion import (
    DiscussionState,
    DiscussionStatus,
    save_discussion_state,
    set_current_discussion,
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset global discussion state before/after each test."""
    set_current_discussion(None)
    yield
    set_current_discussion(None)


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for file tests."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


# ============================================================
# 1. DocOrganizer parse_result Tests
# ============================================================


class TestParseResult:
    """Test LLM output parsing logic."""

    def test_parse_valid_json_array(self):
        organizer = DocOrganizer()
        raw = json.dumps([
            {"filename": "战斗系统.md", "title": "战斗系统设计", "content": "# 战斗系统\n\n内容..."},
            {"filename": "数值平衡.md", "title": "数值平衡方案", "content": "# 数值\n\n内容..."},
        ])
        docs = organizer.parse_result(raw)
        assert len(docs) == 2
        assert docs[0].filename == "战斗系统.md"
        assert docs[1].title == "数值平衡方案"

    def test_parse_json_with_code_fences(self):
        organizer = DocOrganizer()
        raw = '```json\n[{"filename": "test.md", "title": "Test", "content": "# Test"}]\n```'
        docs = organizer.parse_result(raw)
        assert len(docs) == 1
        assert docs[0].filename == "test.md"

    def test_parse_json_with_surrounding_text(self):
        organizer = DocOrganizer()
        raw = 'Here are the documents:\n[{"filename": "a.md", "title": "A", "content": "content"}]\nDone.'
        docs = organizer.parse_result(raw)
        assert len(docs) == 1

    def test_parse_invalid_json(self):
        organizer = DocOrganizer()
        raw = "This is not JSON at all"
        docs = organizer.parse_result(raw)
        assert len(docs) == 0

    def test_parse_empty_array(self):
        organizer = DocOrganizer()
        raw = "[]"
        docs = organizer.parse_result(raw)
        assert len(docs) == 0

    def test_parse_skips_items_without_filename(self):
        organizer = DocOrganizer()
        raw = json.dumps([
            {"title": "No filename", "content": "content"},
            {"filename": "valid.md", "title": "Valid", "content": "content"},
        ])
        docs = organizer.parse_result(raw)
        assert len(docs) == 1
        assert docs[0].filename == "valid.md"

    def test_parse_skips_items_without_content(self):
        organizer = DocOrganizer()
        raw = json.dumps([
            {"filename": "empty.md", "title": "Empty", "content": ""},
            {"filename": "valid.md", "title": "Valid", "content": "content"},
        ])
        docs = organizer.parse_result(raw)
        assert len(docs) == 1


# ============================================================
# 2. Filename Sanitization Tests
# ============================================================


class TestFilenameSanitization:
    """Test filename safety checks."""

    def test_valid_chinese_filename(self):
        organizer = DocOrganizer()
        assert organizer._sanitize_filename("战斗系统.md") == "战斗系统.md"

    def test_valid_english_filename(self):
        organizer = DocOrganizer()
        assert organizer._sanitize_filename("combat-system.md") == "combat-system.md"

    def test_adds_md_extension(self):
        organizer = DocOrganizer()
        assert organizer._sanitize_filename("战斗系统") == "战斗系统.md"

    def test_rejects_path_traversal(self):
        organizer = DocOrganizer()
        assert organizer._sanitize_filename("../../etc/passwd") == ""

    def test_rejects_absolute_path(self):
        organizer = DocOrganizer()
        assert organizer._sanitize_filename("/etc/passwd.md") == ""

    def test_strips_leading_dots(self):
        organizer = DocOrganizer()
        result = organizer._sanitize_filename("..hidden.md")
        assert not result.startswith(".")

    def test_rejects_spaces(self):
        organizer = DocOrganizer()
        # Spaces are not allowed (may cause issues)
        assert organizer._sanitize_filename("file name.md") == ""


# ============================================================
# 3. File Save Tests
# ============================================================


class TestSaveDocuments:
    """Test document saving to disk."""

    def test_save_creates_files(self, temp_data_dir):
        organizer = DocOrganizer(data_dir=temp_data_dir)
        docs = [
            OrganizedDoc(filename="系统设计.md", title="系统设计", content="# 系统设计\n\n内容"),
            OrganizedDoc(filename="数值方案.md", title="数值方案", content="# 数值\n\n数据"),
        ]
        result = organizer.save_documents(
            discussion_id="test-123",
            project_id="default",
            topic="测试讨论",
            docs=docs,
        )
        assert result.discussion_id == "test-123"
        assert len(result.files) == 2

        # Verify files exist
        docs_dir = Path(temp_data_dir) / "default" / "design_docs" / "test-123"
        assert (docs_dir / "系统设计.md").exists()
        assert (docs_dir / "数值方案.md").exists()
        assert (docs_dir / "_index.json").exists()

        # Verify index content
        index = json.loads((docs_dir / "_index.json").read_text(encoding="utf-8"))
        assert index["discussion_id"] == "test-123"
        assert len(index["files"]) == 2

    def test_save_utf8_content(self, temp_data_dir):
        organizer = DocOrganizer(data_dir=temp_data_dir)
        docs = [
            OrganizedDoc(
                filename="中文文档.md",
                title="中文标题",
                content="# 中文内容\n\n这是中文策划案"
            ),
        ]
        result = organizer.save_documents(
            discussion_id="utf8-test",
            project_id="default",
            topic="中文测试",
            docs=docs,
        )
        docs_dir = Path(temp_data_dir) / "default" / "design_docs" / "utf8-test"
        content = (docs_dir / "中文文档.md").read_text(encoding="utf-8")
        assert "中文内容" in content

    def test_load_index(self, temp_data_dir):
        organizer = DocOrganizer(data_dir=temp_data_dir)
        docs = [OrganizedDoc(filename="test.md", title="Test", content="content")]
        organizer.save_documents("disc-1", "default", "Topic", docs)

        index = organizer.load_index("default", "disc-1")
        assert index is not None
        assert index["discussion_id"] == "disc-1"
        assert len(index["files"]) == 1

    def test_load_index_not_found(self, temp_data_dir):
        organizer = DocOrganizer(data_dir=temp_data_dir)
        index = organizer.load_index("default", "nonexistent")
        assert index is None

    def test_load_document(self, temp_data_dir):
        organizer = DocOrganizer(data_dir=temp_data_dir)
        docs = [OrganizedDoc(filename="test.md", title="Test", content="# Test Content")]
        organizer.save_documents("disc-1", "default", "Topic", docs)

        content = organizer.load_document("default", "disc-1", "test.md")
        assert content == "# Test Content"

    def test_load_document_traversal_blocked(self, temp_data_dir):
        organizer = DocOrganizer(data_dir=temp_data_dir)
        content = organizer.load_document("default", "disc-1", "../../etc/passwd")
        assert content is None


# ============================================================
# 4. API Endpoint Tests
# ============================================================


class TestDesignDocsAPI:
    """Test design docs API endpoints."""

    def test_list_docs_no_discussion(self, client):
        """GET design-docs returns 404 for nonexistent discussion."""
        response = client.get("/api/discussions/nonexistent/design-docs")
        assert response.status_code == 404

    def test_list_docs_empty(self, client):
        """GET design-docs returns empty list when no docs exist."""
        # Create a completed discussion
        discussion = DiscussionState(
            id="docs-test-1",
            topic="Test",
            rounds=1,
            status=DiscussionStatus.COMPLETED,
            created_at="2024-01-01T00:00:00",
            completed_at="2024-01-01T01:00:00",
        )
        save_discussion_state(discussion)

        response = client.get("/api/discussions/docs-test-1/design-docs")
        assert response.status_code == 200
        data = response.json()
        assert data["discussion_id"] == "docs-test-1"
        assert data["files"] == []

    def test_get_doc_no_discussion(self, client):
        """GET single doc returns 404 for nonexistent discussion."""
        response = client.get("/api/discussions/nonexistent/design-docs/test.md")
        assert response.status_code == 404

    def test_get_doc_not_found(self, client):
        """GET single doc returns 404 when file doesn't exist."""
        discussion = DiscussionState(
            id="docs-test-2",
            topic="Test",
            rounds=1,
            status=DiscussionStatus.COMPLETED,
            created_at="2024-01-01T00:00:00",
            completed_at="2024-01-01T01:00:00",
        )
        save_discussion_state(discussion)

        response = client.get("/api/discussions/docs-test-2/design-docs/nonexistent.md")
        assert response.status_code == 404

    def test_organize_requires_completed(self, client):
        """POST organize returns 400 for running discussion."""
        discussion = DiscussionState(
            id="docs-test-3",
            topic="Running test",
            rounds=1,
            status=DiscussionStatus.RUNNING,
            created_at="2024-01-01T00:00:00",
        )
        save_discussion_state(discussion)

        response = client.post("/api/discussions/docs-test-3/organize")
        assert response.status_code == 400

    def test_organize_requires_existing(self, client):
        """POST organize returns 404 for nonexistent discussion."""
        response = client.post("/api/discussions/nonexistent-org/organize")
        assert response.status_code == 404


# ============================================================
# 5. Route Ordering Tests (design-docs vs discussion /{id})
# ============================================================


class TestRouteOrdering:
    """Ensure design-docs routes don't conflict with discussion routes."""

    def test_design_docs_path_recognized(self, client):
        """The /design-docs path should be recognized, not treated as {discussion_id}."""
        # This should hit the design_docs router, not the discussion detail endpoint
        discussion = DiscussionState(
            id="route-test",
            topic="Route test",
            rounds=1,
            status=DiscussionStatus.COMPLETED,
            created_at="2024-01-01T00:00:00",
        )
        save_discussion_state(discussion)

        response = client.get("/api/discussions/route-test/design-docs")
        assert response.status_code == 200
        # Should return design docs list, not discussion detail
        data = response.json()
        assert "files" in data
