"""Prompt engineering module for image generation.

This module transforms user descriptions into optimized image generation
prompts, applying style templates and optional LLM enhancement.
"""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EnhancedPrompt:
    """Result of prompt enhancement.

    Attributes:
        original: The original user description.
        enhanced: The enhanced/transformed prompt.
        style_id: The style template applied.
        negative_prompt: Optional negative prompt for avoiding issues.
        metadata: Additional metadata about the enhancement.
    """

    original: str
    enhanced: str
    style_id: str | None = None
    negative_prompt: str | None = None
    metadata: dict[str, Any] | None = None


class PromptEngineer:
    """Transforms user descriptions into optimized image generation prompts.

    The enhancement process:
    1. Clean and normalize the input description
    2. Optionally enhance using LLM (if enabled)
    3. Apply style template (prefix + suffix)
    4. Generate negative prompt if needed

    Usage:
        engineer = PromptEngineer()
        result = await engineer.enhance(
            description="A warrior character",
            style={"prompt_prefix": "game art,", "prompt_suffix": "detailed"}
        )
        print(result.enhanced)  # "game art, A warrior character, detailed"
    """

    # Default negative prompt elements to avoid common issues
    DEFAULT_NEGATIVE_ELEMENTS = [
        "blurry",
        "low quality",
        "distorted",
        "deformed",
        "bad anatomy",
        "watermark",
        "text",
        "signature",
    ]

    def __init__(
        self,
        enable_llm_enhancement: bool = False,
        llm_client: Any | None = None,
        llm_model: str = "gpt-4",
    ) -> None:
        """Initialize the prompt engineer.

        Args:
            enable_llm_enhancement: Whether to use LLM for prompt enhancement.
            llm_client: Optional LLM client for enhancement. If None and
                       enhancement is enabled, will use OpenAI.
            llm_model: Model to use for LLM enhancement.
        """
        self.enable_llm_enhancement = enable_llm_enhancement
        self.llm_client = llm_client
        self.llm_model = llm_model

    def _clean_description(self, description: str) -> str:
        """Clean and normalize the input description.

        Args:
            description: Raw user description.

        Returns:
            Cleaned description.
        """
        # Remove extra whitespace
        cleaned = " ".join(description.split())

        # Remove trailing punctuation that might interfere
        cleaned = cleaned.rstrip(".,;:")

        return cleaned

    def _apply_style(
        self,
        description: str,
        style: dict[str, Any] | None,
    ) -> str:
        """Apply style template to the description.

        Args:
            description: The description to enhance.
            style: Style configuration with prompt_prefix and prompt_suffix.

        Returns:
            Description with style applied.
        """
        if style is None:
            return description

        prefix = style.get("prompt_prefix", "")
        suffix = style.get("prompt_suffix", "")

        parts = []
        if prefix:
            parts.append(prefix.strip())
        parts.append(description)
        if suffix:
            parts.append(suffix.strip())

        return " ".join(parts)

    def _generate_negative_prompt(
        self,
        style: dict[str, Any] | None,
    ) -> str | None:
        """Generate a negative prompt based on style and defaults.

        Args:
            style: Style configuration that may include negative_prompt.

        Returns:
            Negative prompt string or None.
        """
        negative_elements = list(self.DEFAULT_NEGATIVE_ELEMENTS)

        # Add style-specific negative elements
        if style and "negative_prompt" in style:
            style_negative = style["negative_prompt"]
            if isinstance(style_negative, list):
                negative_elements.extend(style_negative)
            elif isinstance(style_negative, str):
                negative_elements.append(style_negative)

        if negative_elements:
            return ", ".join(negative_elements)

        return None

    async def _llm_enhance(self, description: str, style_name: str | None = None) -> str:
        """Enhance description using LLM.

        Args:
            description: The original description.
            style_name: Optional style name for context.

        Returns:
            LLM-enhanced description.
        """
        if not self.enable_llm_enhancement:
            return description

        if self.llm_client is None:
            logger.warning("LLM enhancement enabled but no client configured")
            return description

        try:
            style_context = f" in {style_name} style" if style_name else ""
            prompt = f"""Transform this game design description into an effective image generation prompt{style_context}.

Original description: {description}

Create a detailed, visual prompt that:
1. Describes the visual elements clearly
2. Includes composition and perspective hints
3. Specifies art style and quality markers
4. Is suitable for image generation AI

Return ONLY the enhanced prompt, no explanation."""

            # This is a placeholder for actual LLM call
            # In production, this would call the configured LLM client
            response = await self.llm_client.generate(prompt)
            enhanced = response.strip()

            if enhanced:
                return enhanced

        except Exception as e:
            logger.warning(f"LLM enhancement failed, using original: {e}")

        return description

    async def enhance(
        self,
        description: str,
        style: dict[str, Any] | None = None,
        style_id: str | None = None,
    ) -> EnhancedPrompt:
        """Enhance a description into an optimized image prompt.

        Args:
            description: The original user description.
            style: Style configuration dictionary with prompt_prefix/suffix.
            style_id: Optional style identifier for tracking.

        Returns:
            EnhancedPrompt with the transformed prompt.
        """
        # Clean the input
        cleaned = self._clean_description(description)

        # Apply LLM enhancement if enabled
        if self.enable_llm_enhancement:
            style_name = style.get("name") if style else None
            enhanced = await self._llm_enhance(cleaned, style_name)
        else:
            enhanced = cleaned

        # Apply style template
        final_prompt = self._apply_style(enhanced, style)

        # Generate negative prompt
        negative_prompt = self._generate_negative_prompt(style)

        return EnhancedPrompt(
            original=description,
            enhanced=final_prompt,
            style_id=style_id,
            negative_prompt=negative_prompt,
            metadata={
                "llm_enhanced": self.enable_llm_enhancement,
                "style_applied": style is not None,
            },
        )

    def enhance_sync(
        self,
        description: str,
        style: dict[str, Any] | None = None,
        style_id: str | None = None,
    ) -> EnhancedPrompt:
        """Synchronous version of enhance (without LLM enhancement).

        Args:
            description: The original user description.
            style: Style configuration dictionary.
            style_id: Optional style identifier.

        Returns:
            EnhancedPrompt with the transformed prompt.
        """
        # Clean the input
        cleaned = self._clean_description(description)

        # Apply style template (no LLM in sync mode)
        final_prompt = self._apply_style(cleaned, style)

        # Generate negative prompt
        negative_prompt = self._generate_negative_prompt(style)

        return EnhancedPrompt(
            original=description,
            enhanced=final_prompt,
            style_id=style_id,
            negative_prompt=negative_prompt,
            metadata={
                "llm_enhanced": False,
                "style_applied": style is not None,
            },
        )
