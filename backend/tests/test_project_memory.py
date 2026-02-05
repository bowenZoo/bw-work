"""Tests for project memory."""

import tempfile
from pathlib import Path

import pytest

from src.project.discussion.project_memory import ProjectMemory


class TestProjectMemory:
    """Tests for ProjectMemory."""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.memory = ProjectMemory(data_dir=self.temp_dir)

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_creates_new_state(self):
        """Test loading creates new state for new project."""
        state = self.memory.load("test-project")

        assert state.project_id == "test-project"
        assert state.gdd_context == ""
        assert len(state.terms) == 0
        assert len(state.decisions) == 0

    def test_save_and_load(self):
        """Test saving and loading memory."""
        # Setup
        self.memory.load("test-project")
        self.memory.set_gdd_context("Test GDD content", "Test summary")
        self.memory.add_term("HP", "Hit Points")
        self.memory.add_decision("combat", "Combat", "Use turn-based", "Strategic gameplay")

        # Reload
        memory2 = ProjectMemory(data_dir=self.temp_dir)
        state = memory2.load("test-project")

        assert state.gdd_context == "Test GDD content"
        assert state.gdd_summary == "Test summary"
        assert len(state.terms) == 1
        assert state.terms[0].term == "HP"
        assert len(state.decisions) == 1
        assert state.decisions[0].decision == "Use turn-based"

    def test_add_term_updates_existing(self):
        """Test adding term updates if exists."""
        self.memory.load("test-project")
        self.memory.add_term("HP", "Hit Points")
        self.memory.add_term("HP", "Health Points")  # Update

        terms = self.memory._state.terms
        assert len(terms) == 1
        assert terms[0].definition == "Health Points"

    def test_add_decision(self):
        """Test adding decisions."""
        self.memory.load("test-project")
        self.memory.add_decision("combat", "Combat", "Use combo system", "Engaging gameplay")
        self.memory.add_decision("combat", "Combat", "Real-time action", "Fast-paced")

        decisions = self.memory.get_decisions_for_module("combat")
        assert len(decisions) == 2

    def test_add_constraint(self):
        """Test adding constraints."""
        self.memory.load("test-project")
        self.memory.add_constraint("technical", "Max 1000 concurrent players")
        self.memory.add_constraint("resource", "3 month development time")

        assert len(self.memory._state.constraints) == 2

    def test_get_context_for_module(self):
        """Test context generation for module."""
        self.memory.load("test-project")
        self.memory.set_gdd_context("Full GDD", "This is an RPG game")
        self.memory.add_term("EXP", "Experience points")
        self.memory.add_decision("combat", "Combat System", "Turn-based", "Strategic")
        self.memory.add_constraint("technical", "Mobile platform")

        context = self.memory.get_context_for_module("equipment", ["combat"])

        assert "This is an RPG game" in context
        assert "Combat System" in context
        assert "Turn-based" in context
        assert "EXP" in context
        assert "Mobile platform" in context

    def test_check_consistency_no_conflict(self):
        """Test consistency check with no conflicts."""
        self.memory.load("test-project")
        self.memory.add_decision("combat", "Combat", "Turn-based combat", "Strategic")

        conflicts = self.memory.check_consistency("Add equipment slots", "equipment")
        assert len(conflicts) == 0

    def test_check_consistency_with_conflict(self):
        """Test consistency check detects conflicts."""
        self.memory.load("test-project")
        self.memory.add_decision("combat", "Combat", "Turn-based combat", "Strategic")

        conflicts = self.memory.check_consistency("Real-time action combat", "equipment")
        assert len(conflicts) > 0
        assert "conflict" in conflicts[0].lower() or "Potential" in conflicts[0]

    def test_get_glossary(self):
        """Test glossary retrieval."""
        self.memory.load("test-project")
        self.memory.add_term("HP", "Hit Points")
        self.memory.add_term("MP", "Magic Points")

        glossary = self.memory.get_glossary()
        assert glossary["HP"] == "Hit Points"
        assert glossary["MP"] == "Magic Points"

    def test_clear(self):
        """Test clearing memory."""
        self.memory.load("test-project")
        self.memory.set_gdd_context("GDD content", "Summary")
        self.memory.add_term("HP", "Hit Points")
        self.memory.add_decision("combat", "Combat", "Decision", "Reason")

        self.memory.clear()

        assert self.memory._state.gdd_context == "GDD content"  # Preserved
        assert len(self.memory._state.terms) == 0
        assert len(self.memory._state.decisions) == 0
