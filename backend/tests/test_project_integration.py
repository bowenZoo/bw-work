"""Integration tests for project-level discussion system."""

import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Test fixtures path
FIXTURES_PATH = Path(__file__).parent / "fixtures"


class TestProjectIntegration:
    """Integration tests for the complete project discussion workflow."""

    @pytest.fixture
    def temp_data_dir(self):
        """Create a temporary data directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def sample_gdd_content(self):
        """Load sample GDD content."""
        gdd_path = FIXTURES_PATH / "sample-gdd.md"
        if gdd_path.exists():
            return gdd_path.read_text(encoding="utf-8")
        return """# Sample GDD
## 1. Combat System
Basic combat mechanics.
## 2. Item System
Inventory and items.
"""


class TestGddParsing(TestProjectIntegration):
    """Test GDD parsing functionality."""

    def test_markdown_parser_extracts_content(self, temp_data_dir, sample_gdd_content):
        """Test that markdown parser extracts text content."""
        from src.project.gdd.parsers.markdown import MarkdownParser

        # Write sample content to a file
        test_file = temp_data_dir / "sample.md"
        test_file.write_text(sample_gdd_content, encoding="utf-8")

        parser = MarkdownParser()
        result = parser.parse(test_file)

        assert result is not None
        assert result.content is not None
        # Check that content was parsed
        assert len(result.content) > 0

    def test_unified_parser_handles_markdown(self, temp_data_dir, sample_gdd_content):
        """Test that unified parser handles markdown files."""
        from src.project.gdd.parser import GDDParser

        # Create test project directory structure
        project_id = "test-project"
        parser = GDDParser(data_dir=str(temp_data_dir))

        # Save a GDD file
        gdd_id, file_path = parser.save_upload(
            project_id=project_id,
            filename="test.md",
            file_content=sample_gdd_content.encode("utf-8"),
        )

        # Parse it
        doc = parser.parse(project_id, gdd_id, file_path, "test.md")

        assert doc is not None
        assert doc.id == gdd_id
        assert doc.project_id == project_id

    def test_parser_validates_file_extension(self, temp_data_dir):
        """Test that parser validates file extensions."""
        from src.project.gdd.parser import GDDParser

        parser = GDDParser(data_dir=str(temp_data_dir))

        # Try to validate unsupported format
        with pytest.raises(ValueError, match="Unsupported"):
            parser.validate_file(filename="test.txt")


class TestModuleDetection(TestProjectIntegration):
    """Test module detection functionality."""

    def test_module_detector_initialization(self, temp_data_dir):
        """Test module detector can be initialized."""
        from src.project.gdd.module_detector import ModuleDetector

        detector = ModuleDetector(cache_dir=str(temp_data_dir / "cache"))
        assert detector.cache_dir == temp_data_dir / "cache"

    def test_suggest_order_respects_dependencies(self):
        """Test that suggest_order respects module dependencies."""
        from src.project.gdd.module_detector import ModuleDetector
        from src.project.models import GDDModule

        detector = ModuleDetector()

        modules = [
            GDDModule(
                id="combat",
                name="Combat",
                description="",
                source_section="",
                dependencies=["character"],
                estimated_rounds=3,
            ),
            GDDModule(
                id="character",
                name="Character",
                description="",
                source_section="",
                dependencies=[],
                estimated_rounds=2,
            ),
        ]

        order = detector.suggest_order(modules)

        # character should come before combat
        char_idx = order.index("character")
        combat_idx = order.index("combat")
        assert char_idx < combat_idx

    def test_validate_order_detects_violations(self):
        """Test that validate_order detects dependency violations."""
        from src.project.gdd.module_detector import ModuleDetector
        from src.project.models import GDDModule

        detector = ModuleDetector()

        modules = [
            GDDModule(
                id="combat",
                name="Combat",
                description="",
                source_section="",
                dependencies=["character"],
                estimated_rounds=3,
            ),
            GDDModule(
                id="character",
                name="Character",
                description="",
                source_section="",
                dependencies=[],
                estimated_rounds=2,
            ),
        ]

        # Invalid order: combat before character
        is_valid, violations = detector.validate_order(modules, ["combat", "character"])
        assert not is_valid
        assert len(violations) > 0


class TestProjectMemory(TestProjectIntegration):
    """Test project memory functionality."""

    def test_memory_initialization(self, temp_data_dir):
        """Test project memory can be initialized and loaded."""
        from src.project.discussion.project_memory import ProjectMemory

        memory = ProjectMemory(data_dir=str(temp_data_dir))
        state = memory.load("test-project")

        assert state is not None
        assert state.project_id == "test-project"

    def test_memory_add_decision(self, temp_data_dir):
        """Test adding decisions to project memory."""
        from src.project.discussion.project_memory import ProjectMemory

        memory = ProjectMemory(data_dir=str(temp_data_dir))
        memory.load("test-project")

        memory.add_decision(
            module_id="combat",
            module_name="Combat System",
            decision="Use turn-based combat",
            rationale="Better for mobile",
        )

        decisions = memory.get_all_decisions()
        assert len(decisions) == 1
        assert decisions[0].decision == "Use turn-based combat"

    def test_memory_add_term(self, temp_data_dir):
        """Test adding terms to glossary."""
        from src.project.discussion.project_memory import ProjectMemory

        memory = ProjectMemory(data_dir=str(temp_data_dir))
        memory.load("test-project")

        memory.add_term("HP", "Hit Points - character health")

        glossary = memory.get_glossary()
        assert "HP" in glossary
        assert glossary["HP"] == "Hit Points - character health"

    def test_memory_persistence(self, temp_data_dir):
        """Test that memory persists to disk."""
        from src.project.discussion.project_memory import ProjectMemory

        # First instance
        memory1 = ProjectMemory(data_dir=str(temp_data_dir))
        memory1.load("test-project")
        memory1.add_term("HP", "Hit Points")

        # Second instance (loads from disk)
        memory2 = ProjectMemory(data_dir=str(temp_data_dir))
        memory2.load("test-project")

        glossary = memory2.get_glossary()
        assert "HP" in glossary


class TestCheckpoint(TestProjectIntegration):
    """Test checkpoint management functionality."""

    def test_checkpoint_save_and_load(self, temp_data_dir):
        """Test checkpoint save and load."""
        from src.project.discussion.checkpoint import CheckpointManager
        from src.project.models import DiscussionCheckpoint

        manager = CheckpointManager(data_dir=str(temp_data_dir))

        # Create checkpoint
        checkpoint = DiscussionCheckpoint(
            project_id="test-project",
            gdd_id="gdd-001",
            discussion_id="disc-001",
            selected_modules=["combat", "item"],
            current_module_index=1,
            completed_modules=[],
        )

        # Save it
        path = manager.save(checkpoint)
        assert path.exists()

        # Load it
        loaded = manager.load("test-project", "disc-001")
        assert loaded is not None
        assert loaded.discussion_id == "disc-001"
        assert loaded.current_module_index == 1

    def test_checkpoint_exists(self, temp_data_dir):
        """Test checking checkpoint existence."""
        from src.project.discussion.checkpoint import CheckpointManager
        from src.project.models import DiscussionCheckpoint

        manager = CheckpointManager(data_dir=str(temp_data_dir))

        # Before saving
        assert not manager.exists("test-project", "disc-001")

        # Save checkpoint
        checkpoint = DiscussionCheckpoint(
            project_id="test-project",
            gdd_id="gdd-001",
            discussion_id="disc-001",
            selected_modules=["combat"],
            current_module_index=0,
            completed_modules=[],
        )
        manager.save(checkpoint)

        # After saving
        assert manager.exists("test-project", "disc-001")

    def test_checkpoint_list_discussions(self, temp_data_dir):
        """Test listing discussions with checkpoints."""
        from src.project.discussion.checkpoint import CheckpointManager
        from src.project.models import DiscussionCheckpoint

        manager = CheckpointManager(data_dir=str(temp_data_dir))

        # Save multiple checkpoints
        for disc_id in ["disc-001", "disc-002"]:
            checkpoint = DiscussionCheckpoint(
                project_id="test-project",
                gdd_id="gdd-001",
                discussion_id=disc_id,
                selected_modules=["combat"],
                current_module_index=0,
                completed_modules=[],
            )
            manager.save(checkpoint)

        # List discussions
        discussions = manager.list_discussions_with_checkpoints("test-project")
        assert len(discussions) == 2
        assert "disc-001" in discussions
        assert "disc-002" in discussions


class TestBatchRunner(TestProjectIntegration):
    """Test batch discussion runner functionality."""

    def test_batch_runner_initialization(self, temp_data_dir):
        """Test batch runner initialization."""
        from src.project.discussion.batch_runner import BatchDiscussionRunner
        from src.project.models import GDDModule

        modules = [
            GDDModule(
                id="combat",
                name="Combat",
                description="",
                source_section="",
                estimated_rounds=3,
            ),
        ]

        runner = BatchDiscussionRunner(
            project_id="test-project",
            gdd_id="gdd-001",
            modules=modules,
            module_order=["combat"],
            data_dir=str(temp_data_dir),
        )

        assert runner.project_id == "test-project"
        assert len(runner.modules) == 1

    def test_batch_runner_get_discussion(self, temp_data_dir):
        """Test getting discussion state from runner."""
        from src.project.discussion.batch_runner import BatchDiscussionRunner
        from src.project.models import GDDModule

        modules = [
            GDDModule(
                id="combat",
                name="Combat",
                description="",
                source_section="",
                estimated_rounds=3,
            ),
        ]

        runner = BatchDiscussionRunner(
            project_id="test-project",
            gdd_id="gdd-001",
            modules=modules,
            module_order=["combat"],
            data_dir=str(temp_data_dir),
        )

        discussion = runner.get_discussion()
        assert discussion.project_id == "test-project"
        assert discussion.progress.total_modules == 1

    def test_batch_runner_pause_request(self, temp_data_dir):
        """Test requesting pause on batch runner."""
        from src.project.discussion.batch_runner import BatchDiscussionRunner
        from src.project.models import GDDModule

        modules = [
            GDDModule(
                id="combat",
                name="Combat",
                description="",
                source_section="",
                estimated_rounds=3,
            ),
        ]

        runner = BatchDiscussionRunner(
            project_id="test-project",
            gdd_id="gdd-001",
            modules=modules,
            module_order=["combat"],
            data_dir=str(temp_data_dir),
        )

        runner.request_pause()
        assert runner._pause_requested is True


class TestDesignDocGeneration(TestProjectIntegration):
    """Test design document generation functionality."""

    def test_design_doc_generator_initialization(self, temp_data_dir):
        """Test design doc generator initialization."""
        from src.project.output.design_doc import DesignDocGenerator

        generator = DesignDocGenerator(data_dir=str(temp_data_dir))
        assert generator.data_dir == temp_data_dir

    def test_design_doc_sync_generation(self, temp_data_dir):
        """Test synchronous design document generation."""
        from src.project.output.design_doc import (
            DesignDocGenerator,
            DiscussionData,
            DiscussionMessage,
        )
        from datetime import datetime

        generator = DesignDocGenerator(data_dir=str(temp_data_dir))

        discussion_data = DiscussionData(
            module_id="combat",
            module_name="Combat System",
            discussion_id="disc-001",
            gdd_filename="test.md",
            messages=[
                DiscussionMessage(
                    speaker="System Designer",
                    content="Turn-based combat is best for mobile",
                    timestamp=datetime.utcnow(),
                )
            ],
            key_decisions=["Use turn-based combat"],
        )

        doc_path = generator.generate_sync("test-project", discussion_data)

        assert doc_path.exists()
        content = doc_path.read_text(encoding="utf-8")
        assert "Combat System" in content

    def test_design_doc_list_documents(self, temp_data_dir):
        """Test listing design documents."""
        from src.project.output.design_doc import (
            DesignDocGenerator,
            DiscussionData,
        )

        generator = DesignDocGenerator(data_dir=str(temp_data_dir))

        # Generate a document
        discussion_data = DiscussionData(
            module_id="combat",
            module_name="Combat System",
            discussion_id="disc-001",
            gdd_filename="test.md",
        )
        generator.generate_sync("test-project", discussion_data)

        # List documents
        docs = generator.list_documents("test-project")
        assert len(docs) == 1
        assert docs[0][0] == "combat"


class TestSummaryGeneration(TestProjectIntegration):
    """Test project summary generation functionality."""

    def test_summary_generator_initialization(self, temp_data_dir):
        """Test summary generator initialization."""
        from src.project.output.summary import ProjectSummaryGenerator

        generator = ProjectSummaryGenerator(data_dir=str(temp_data_dir))
        assert generator.data_dir == temp_data_dir

    def test_summary_generation(self, temp_data_dir):
        """Test project summary generation."""
        from src.project.output.summary import (
            ProjectSummaryGenerator,
            ProjectSummaryData,
            ModuleSummary,
        )

        generator = ProjectSummaryGenerator(data_dir=str(temp_data_dir))

        data = ProjectSummaryData(
            project_name="Test Project",
            gdd_filename="test.md",
            total_duration_minutes=30.5,
            modules=[
                ModuleSummary(
                    module_id="combat",
                    module_name="Combat System",
                    design_doc_path="combat-system.md",
                    status="completed",
                    discussion_rounds=5,
                    key_decisions=["Use turn-based"],
                )
            ],
        )

        summary_path = generator.generate("test-project", data)

        assert summary_path.exists()
        content = summary_path.read_text(encoding="utf-8")
        assert "Test Project" in content
        assert "Combat System" in content


class TestWebSocketEvents(TestProjectIntegration):
    """Test WebSocket event definitions."""

    def test_project_discussion_event_creation(self):
        """Test creating project discussion events."""
        from src.api.websocket.events import (
            create_module_discussion_progress_event,
            create_project_discussion_start_event,
        )

        # Test project start event
        start_event = create_project_discussion_start_event(
            project_id="proj-001",
            discussion_id="disc-001",
            total_modules=4,
            module_order=["m1", "m2", "m3", "m4"],
        )

        assert start_event.type.value == "project_discussion_start"
        assert start_event.data.project_id == "proj-001"
        assert start_event.data.total_modules == 4

        # Test progress event
        progress_event = create_module_discussion_progress_event(
            project_id="proj-001",
            discussion_id="disc-001",
            module_id="combat",
            round=2,
            speaker="System Designer",
            summary="Discussing combat mechanics",
        )

        assert progress_event.type.value == "module_discussion_progress"
        assert progress_event.data.speaker == "System Designer"

    def test_event_serialization(self):
        """Test event serialization to dict."""
        from src.api.websocket.events import create_gdd_parsing_progress_event

        event = create_gdd_parsing_progress_event(
            project_id="proj-001",
            gdd_id="gdd-001",
            status="parsing",
            message="Parsing document...",
        )

        data = event.to_dict()
        assert isinstance(data, dict)
        assert data["type"] == "gdd_parsing_progress"
        assert data["data"]["project_id"] == "proj-001"

    def test_module_discussion_complete_event(self):
        """Test module discussion complete event."""
        from src.api.websocket.events import create_module_discussion_complete_event

        event = create_module_discussion_complete_event(
            project_id="proj-001",
            discussion_id="disc-001",
            module_id="combat",
            design_doc_path="combat-system.md",
            key_decisions=["Use turn-based", "3 action points per turn"],
        )

        assert event.type.value == "module_discussion_complete"
        data = event.to_dict()
        assert data["data"]["module_id"] == "combat"
        assert len(data["data"]["key_decisions"]) == 2


class TestEndToEndWorkflow:
    """End-to-end workflow tests (with extensive mocking)."""

    @pytest.fixture
    def temp_data_dir(self):
        """Create a temporary data directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_complete_workflow_mock(self, temp_data_dir):
        """Test complete workflow with mocked components."""
        from src.project.gdd.parser import GDDParser
        from src.project.gdd.module_detector import ModuleDetector
        from src.project.discussion.project_memory import ProjectMemory
        from src.project.discussion.checkpoint import CheckpointManager
        from src.project.output.design_doc import DesignDocGenerator, DiscussionData
        from src.project.models import GDDModule

        project_id = "test-project"
        gdd_content = """# Test GDD
## 1. Combat System
Turn-based combat.
## 2. Item System
Inventory management.
"""

        # 1. Parse GDD
        parser = GDDParser(data_dir=str(temp_data_dir))
        gdd_id, file_path = parser.save_upload(
            project_id=project_id,
            filename="test.md",
            file_content=gdd_content.encode("utf-8"),
        )
        doc = parser.parse(project_id, gdd_id, file_path, "test.md")
        assert doc is not None

        # 2. Test module detection (suggest_order with mock modules)
        detector = ModuleDetector(cache_dir=str(temp_data_dir / "cache"))
        mock_modules = [
            GDDModule(
                id="combat",
                name="Combat System",
                description="Combat mechanics",
                source_section="## 1. Combat System",
                dependencies=[],
                estimated_rounds=3,
            ),
            GDDModule(
                id="item",
                name="Item System",
                description="Item management",
                source_section="## 2. Item System",
                dependencies=["combat"],
                estimated_rounds=2,
            ),
        ]
        order = detector.suggest_order(mock_modules)
        assert "combat" in order
        assert order.index("combat") < order.index("item")

        # 3. Initialize project memory
        memory = ProjectMemory(data_dir=str(temp_data_dir))
        memory.load(project_id)
        memory.add_decision(
            module_id="combat",
            module_name="Combat System",
            decision="Use turn-based combat",
            rationale="Better for mobile gameplay",
        )

        # 4. Create checkpoint
        checkpoint_mgr = CheckpointManager(data_dir=str(temp_data_dir))
        from src.project.models import DiscussionCheckpoint

        checkpoint = DiscussionCheckpoint(
            project_id=project_id,
            gdd_id=gdd_id,
            discussion_id="disc-001",
            selected_modules=["combat", "item"],
            current_module_index=0,
            completed_modules=[],
        )
        checkpoint_mgr.save(checkpoint)

        # 5. Generate design doc
        doc_generator = DesignDocGenerator(data_dir=str(temp_data_dir))
        discussion_data = DiscussionData(
            module_id="combat",
            module_name="Combat System",
            discussion_id="disc-001",
            gdd_filename="test.md",
            key_decisions=["Use turn-based combat"],
        )
        doc_path = doc_generator.generate_sync(project_id, discussion_data)

        # Verify results
        assert doc_path.exists()
        loaded_checkpoint = checkpoint_mgr.load(project_id, "disc-001")
        assert loaded_checkpoint is not None
        decisions = memory.get_all_decisions()
        assert len(decisions) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
