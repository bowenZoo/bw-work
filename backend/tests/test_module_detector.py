"""Tests for module detection."""

import pytest

from src.project.gdd.module_detector import ModuleDetector
from src.project.models import GDDModule, ParsedText, Section


class TestModuleDetector:
    """Tests for ModuleDetector."""

    def setup_method(self):
        self.detector = ModuleDetector()

    def test_suggest_order_no_dependencies(self):
        """Test order suggestion with no dependencies."""
        modules = [
            GDDModule(
                id="combat",
                name="Combat System",
                description="Combat",
                source_section="",
                estimated_rounds=3,
            ),
            GDDModule(
                id="economy",
                name="Economy System",
                description="Economy",
                source_section="",
                estimated_rounds=5,
            ),
        ]

        order = self.detector.suggest_order(modules)

        # Both should be included
        assert set(order) == {"combat", "economy"}
        # Simpler module (lower rounds) should come first
        assert order[0] == "combat"

    def test_suggest_order_with_dependencies(self):
        """Test order suggestion respects dependencies."""
        modules = [
            GDDModule(
                id="equipment",
                name="Equipment System",
                description="Equipment",
                source_section="",
                dependencies=["combat"],
                estimated_rounds=4,
            ),
            GDDModule(
                id="combat",
                name="Combat System",
                description="Combat",
                source_section="",
                estimated_rounds=3,
            ),
        ]

        order = self.detector.suggest_order(modules)

        # Combat should come before equipment
        assert order.index("combat") < order.index("equipment")

    def test_suggest_order_complex_dependencies(self):
        """Test order with complex dependency chain."""
        modules = [
            GDDModule(
                id="achievement",
                name="Achievement",
                description="",
                source_section="",
                dependencies=["progression", "combat"],
                estimated_rounds=2,
            ),
            GDDModule(
                id="progression",
                name="Progression",
                description="",
                source_section="",
                dependencies=["combat"],
                estimated_rounds=4,
            ),
            GDDModule(
                id="combat",
                name="Combat",
                description="",
                source_section="",
                estimated_rounds=5,
            ),
        ]

        order = self.detector.suggest_order(modules)

        # Combat -> Progression -> Achievement
        assert order.index("combat") < order.index("progression")
        assert order.index("progression") < order.index("achievement")

    def test_validate_order_valid(self):
        """Test validation of valid order."""
        modules = [
            GDDModule(
                id="combat",
                name="Combat",
                description="",
                source_section="",
            ),
            GDDModule(
                id="equipment",
                name="Equipment",
                description="",
                source_section="",
                dependencies=["combat"],
            ),
        ]

        valid, violations = self.detector.validate_order(
            modules, ["combat", "equipment"]
        )

        assert valid
        assert len(violations) == 0

    def test_validate_order_invalid(self):
        """Test validation of invalid order."""
        modules = [
            GDDModule(
                id="combat",
                name="Combat",
                description="",
                source_section="",
            ),
            GDDModule(
                id="equipment",
                name="Equipment",
                description="",
                source_section="",
                dependencies=["combat"],
            ),
        ]

        valid, violations = self.detector.validate_order(
            modules, ["equipment", "combat"]  # Wrong order
        )

        assert not valid
        assert len(violations) == 1
        assert "depends on" in violations[0]

    def test_extract_json_from_code_block(self):
        """Test JSON extraction from markdown code block."""
        text = '''Here is the analysis:

```json
{"title": "Test", "modules": []}
```

That's all.'''

        result = self.detector._extract_json(text)
        assert result["title"] == "Test"

    def test_extract_json_direct(self):
        """Test JSON extraction from direct JSON."""
        text = '{"title": "Test", "modules": []}'

        result = self.detector._extract_json(text)
        assert result["title"] == "Test"

    def test_extract_json_with_surrounding_text(self):
        """Test JSON extraction with surrounding text."""
        text = '''Some intro text
{"title": "Test", "modules": []}
Some trailing text'''

        result = self.detector._extract_json(text)
        assert result["title"] == "Test"

    def test_format_sections(self):
        """Test section formatting for prompt."""
        sections = [
            Section(title="Main", level=1, content="", start_line=1, end_line=5),
            Section(title="Sub1", level=2, content="", start_line=6, end_line=10),
            Section(title="Sub2", level=2, content="", start_line=11, end_line=15),
            Section(title="SubSub", level=3, content="", start_line=16, end_line=20),
        ]

        result = self.detector._format_sections(sections)

        assert "- [1] Main" in result
        assert "  - [2] Sub1" in result
        assert "    - [3] SubSub" in result

    def test_parse_result(self):
        """Test parsing detection result."""
        data = {
            "title": "Test Game",
            "overview": "A test game",
            "modules": [
                {
                    "id": "combat",
                    "name": "Combat System",
                    "description": "Turn-based combat",
                    "source_section": "Combat section content",
                    "keywords": ["battle", "fight"],
                    "dependencies": [],
                    "estimated_rounds": 4,
                },
                {
                    "id": "equipment",
                    "name": "Equipment System",
                    "description": "Weapons and armor",
                    "source_section": "Equipment content",
                    "keywords": ["weapon", "armor"],
                    "dependencies": ["combat"],
                    "estimated_rounds": 3,
                },
            ],
        }

        result = self.detector._parse_result(data)

        assert result.title == "Test Game"
        assert result.overview == "A test game"
        assert len(result.modules) == 2

        combat = next(m for m in result.modules if m.id == "combat")
        assert combat.name == "Combat System"
        assert combat.estimated_rounds == 4
        assert "battle" in combat.keywords

        equipment = next(m for m in result.modules if m.id == "equipment")
        assert "combat" in equipment.dependencies
