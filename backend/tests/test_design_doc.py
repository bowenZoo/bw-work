"""Tests for design document generator."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.project.output.design_doc import (
    DesignDocGenerator,
    DesignDocContent,
    DiscussionData,
    DiscussionMessage,
)


class TestDesignDocGenerator:
    """Tests for DesignDocGenerator."""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.generator = DesignDocGenerator(data_dir=self.temp_dir)

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_discussion_data(self) -> DiscussionData:
        """Create sample discussion data."""
        return DiscussionData(
            module_id="combat",
            module_name="Combat System",
            discussion_id="disc_001",
            gdd_filename="game-gdd.md",
            messages=[
                DiscussionMessage(
                    speaker="System Designer",
                    content="The combat system should focus on strategic turn-based gameplay. Players need to consider position and timing.",
                    timestamp=datetime.utcnow(),
                ),
                DiscussionMessage(
                    speaker="Number Designer",
                    content="For balance, we should use a damage formula: base_damage * (1 + attribute_bonus) * skill_multiplier. Target HP around 1000 at max level.",
                    timestamp=datetime.utcnow(),
                ),
            ],
            key_decisions=[
                "Use turn-based combat system",
                "Position affects damage output",
                "Combo system for advanced play",
            ],
            open_questions=[
                "Should we support PvP combat?",
                "What is the maximum party size?",
            ],
        )

    def test_generate_sync(self):
        """Test synchronous document generation."""
        data = self._create_discussion_data()
        path = self.generator.generate_sync("test-project", data)

        assert path.exists()
        content = path.read_text(encoding="utf-8")

        # Check basic structure
        assert "Combat System" in content
        assert "disc_001" in content
        assert "game-gdd.md" in content

        # Check decisions are included
        assert "Use turn-based combat system" in content
        assert "Position affects damage output" in content

        # Check open questions
        assert "Should we support PvP combat?" in content

    def test_get_document(self):
        """Test retrieving a generated document."""
        data = self._create_discussion_data()
        self.generator.generate_sync("test-project", data)

        content = self.generator.get_document("test-project", "combat")
        assert content is not None
        assert "Combat System" in content

    def test_get_document_not_found(self):
        """Test retrieving non-existent document."""
        content = self.generator.get_document("test-project", "nonexistent")
        assert content is None

    def test_list_documents(self):
        """Test listing generated documents."""
        # Generate two documents
        data1 = self._create_discussion_data()
        data2 = DiscussionData(
            module_id="equipment",
            module_name="Equipment System",
            discussion_id="disc_002",
            gdd_filename="game-gdd.md",
        )

        self.generator.generate_sync("test-project", data1)
        self.generator.generate_sync("test-project", data2)

        docs = self.generator.list_documents("test-project")
        assert len(docs) == 2
        module_ids = [d[0] for d in docs]
        assert "combat" in module_ids
        assert "equipment" in module_ids

    def test_output_path(self):
        """Test correct output path generation."""
        path = self.generator._get_output_path("test-project", "combat")
        expected = Path(self.temp_dir) / "test-project" / "design" / "combat-system.md"
        assert path == expected

    def test_content_extraction(self):
        """Test content extraction from messages."""
        data = self._create_discussion_data()
        content = self.generator._generate_content_from_data(data)

        # Check that discussion summary includes messages
        assert "System Designer" in content.discussion_summary or content.discussion_summary

        # Check decisions are formatted
        assert "turn-based" in content.design_decisions.lower()

    def test_empty_discussion_data(self):
        """Test handling of empty discussion data."""
        data = DiscussionData(
            module_id="empty",
            module_name="Empty Module",
            discussion_id="disc_empty",
            gdd_filename="test.md",
        )

        path = self.generator.generate_sync("test-project", data)
        assert path.exists()

        content = path.read_text(encoding="utf-8")
        # Should have placeholder content
        assert "待" in content  # Chinese for "to be..."

    def test_document_sections(self):
        """Test that all sections are present in output."""
        data = self._create_discussion_data()
        path = self.generator.generate_sync("test-project", data)
        content = path.read_text(encoding="utf-8")

        # Check major sections
        assert "功能概述" in content
        assert "设计目标" in content
        assert "玩法描述" in content
        assert "数值框架" in content
        assert "边界处理" in content
        assert "附录" in content
