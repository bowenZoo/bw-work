"""Tests for the prompt engineering module."""

import pytest

from src.image.prompt_engineer import EnhancedPrompt, PromptEngineer


class TestPromptEngineer:
    """Tests for the PromptEngineer class."""

    @pytest.fixture
    def engineer(self):
        """Create a test engineer instance."""
        return PromptEngineer(enable_llm_enhancement=False)

    def test_clean_description(self, engineer):
        """Test description cleaning."""
        assert engineer._clean_description("  hello   world  ") == "hello world"
        assert engineer._clean_description("text...") == "text"
        assert engineer._clean_description("text,") == "text"

    def test_apply_style_with_prefix_and_suffix(self, engineer):
        """Test applying style with both prefix and suffix."""
        style = {
            "prompt_prefix": "game art,",
            "prompt_suffix": "detailed, 4k",
        }
        result = engineer._apply_style("a warrior", style)
        assert result == "game art, a warrior detailed, 4k"

    def test_apply_style_with_prefix_only(self, engineer):
        """Test applying style with prefix only."""
        style = {"prompt_prefix": "anime style,"}
        result = engineer._apply_style("a character", style)
        assert result == "anime style, a character"

    def test_apply_style_with_suffix_only(self, engineer):
        """Test applying style with suffix only."""
        style = {"prompt_suffix": "professional quality"}
        result = engineer._apply_style("a landscape", style)
        assert result == "a landscape professional quality"

    def test_apply_style_none(self, engineer):
        """Test applying no style."""
        result = engineer._apply_style("a scene", None)
        assert result == "a scene"

    def test_generate_negative_prompt_defaults(self, engineer):
        """Test negative prompt generation with defaults."""
        result = engineer._generate_negative_prompt(None)
        assert result is not None
        assert "blurry" in result
        assert "low quality" in result

    def test_generate_negative_prompt_with_style(self, engineer):
        """Test negative prompt generation with style additions."""
        style = {"negative_prompt": "oversaturated"}
        result = engineer._generate_negative_prompt(style)
        assert "oversaturated" in result
        assert "blurry" in result  # Still includes defaults

    def test_generate_negative_prompt_with_style_list(self, engineer):
        """Test negative prompt generation with style list."""
        style = {"negative_prompt": ["ugly", "bad hands"]}
        result = engineer._generate_negative_prompt(style)
        assert "ugly" in result
        assert "bad hands" in result

    def test_enhance_sync_basic(self, engineer):
        """Test synchronous enhancement without style."""
        result = engineer.enhance_sync("A cute cat")
        assert isinstance(result, EnhancedPrompt)
        assert result.original == "A cute cat"
        assert result.enhanced == "A cute cat"
        assert result.negative_prompt is not None

    def test_enhance_sync_with_style(self, engineer):
        """Test synchronous enhancement with style."""
        style = {
            "name": "Concept Art",
            "prompt_prefix": "concept art,",
            "prompt_suffix": "detailed design",
        }
        result = engineer.enhance_sync("A warrior character", style, style_id="concept_character")

        assert result.original == "A warrior character"
        assert "concept art," in result.enhanced
        assert "detailed design" in result.enhanced
        assert "A warrior character" in result.enhanced
        assert result.style_id == "concept_character"
        assert result.metadata["style_applied"] is True
        assert result.metadata["llm_enhanced"] is False

    @pytest.mark.asyncio
    async def test_enhance_async_basic(self, engineer):
        """Test asynchronous enhancement without style."""
        result = await engineer.enhance("A beautiful landscape")
        assert isinstance(result, EnhancedPrompt)
        assert result.original == "A beautiful landscape"
        assert result.enhanced == "A beautiful landscape"

    @pytest.mark.asyncio
    async def test_enhance_async_with_style(self, engineer):
        """Test asynchronous enhancement with style."""
        style = {
            "prompt_prefix": "game environment,",
            "prompt_suffix": "atmospheric lighting",
        }
        result = await engineer.enhance("A forest scene", style)

        assert "game environment," in result.enhanced
        assert "atmospheric lighting" in result.enhanced
        assert "A forest scene" in result.enhanced

    def test_enhance_sync_cleans_input(self, engineer):
        """Test that enhance_sync cleans the input description."""
        result = engineer.enhance_sync("  A messy   description...  ")
        assert result.enhanced == "A messy description"

    @pytest.mark.asyncio
    async def test_enhance_async_cleans_input(self, engineer):
        """Test that enhance cleans the input description."""
        result = await engineer.enhance("  Another messy   input,,,  ")
        assert result.enhanced == "Another messy input"


class TestEnhancedPrompt:
    """Tests for the EnhancedPrompt dataclass."""

    def test_enhanced_prompt_creation(self):
        """Test creating an EnhancedPrompt."""
        prompt = EnhancedPrompt(
            original="test",
            enhanced="enhanced test",
            style_id="style1",
            negative_prompt="blurry",
            metadata={"key": "value"},
        )
        assert prompt.original == "test"
        assert prompt.enhanced == "enhanced test"
        assert prompt.style_id == "style1"
        assert prompt.negative_prompt == "blurry"
        assert prompt.metadata["key"] == "value"

    def test_enhanced_prompt_defaults(self):
        """Test EnhancedPrompt default values."""
        prompt = EnhancedPrompt(
            original="test",
            enhanced="test",
        )
        assert prompt.style_id is None
        assert prompt.negative_prompt is None
        assert prompt.metadata is None
