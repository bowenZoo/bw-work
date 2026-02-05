"""Style template management for image generation.

This module handles loading and managing style templates from YAML
configuration, providing style-based prompt modifiers and backend
recommendations.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class Style:
    """Image generation style template.

    Attributes:
        id: Unique style identifier.
        name: Human-readable name.
        description: Description of the style.
        prompt_prefix: Text to prepend to prompts.
        prompt_suffix: Text to append to prompts.
        negative_prompt: Elements to avoid.
        recommended_backends: Preferred backend providers.
        default_params: Default generation parameters.
    """

    id: str
    name: str
    description: str = ""
    prompt_prefix: str = ""
    prompt_suffix: str = ""
    negative_prompt: list[str] = field(default_factory=list)
    recommended_backends: list[str] = field(default_factory=list)
    default_params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses.

        Returns:
            Dictionary representation of the style.
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "prompt_prefix": self.prompt_prefix,
            "prompt_suffix": self.prompt_suffix,
            "negative_prompt": self.negative_prompt,
            "recommended_backends": self.recommended_backends,
            "default_params": self.default_params,
        }

    def get_prompt_config(self) -> dict[str, Any]:
        """Get configuration for PromptEngineer.

        Returns:
            Dictionary suitable for PromptEngineer.enhance().
        """
        config = {
            "name": self.name,
        }
        if self.prompt_prefix:
            config["prompt_prefix"] = self.prompt_prefix
        if self.prompt_suffix:
            config["prompt_suffix"] = self.prompt_suffix
        if self.negative_prompt:
            config["negative_prompt"] = self.negative_prompt
        return config


class StyleNotFoundError(Exception):
    """Raised when a requested style is not found."""

    pass


class StyleConfigError(Exception):
    """Raised when there's an error in style configuration."""

    pass


class StyleManager:
    """Manager for image generation style templates.

    Loads styles from YAML configuration and provides access to
    style templates for prompt enhancement and backend selection.

    Usage:
        manager = StyleManager()
        style = manager.get_style("concept_character")
        print(style.prompt_prefix)
    """

    def __init__(
        self,
        config_path: str | Path | None = None,
        config_dict: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the style manager.

        Args:
            config_path: Path to the styles YAML file.
                        Defaults to config/image_styles.yaml.
            config_dict: Optional dictionary to use instead of loading from file.
        """
        self._styles: dict[str, Style] = {}
        self._default_style: str = ""

        if config_dict is not None:
            self._load_from_dict(config_dict)
        else:
            self._load_config(config_path)

    def _load_config(self, config_path: str | Path | None = None) -> None:
        """Load style configuration from YAML file.

        Args:
            config_path: Path to the YAML file.

        Raises:
            StyleConfigError: If the config file cannot be loaded.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "image_styles.yaml"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            logger.warning(f"Style config not found at {config_path}, using defaults")
            self._create_default_styles()
            return

        try:
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
                self._load_from_dict(config)
        except yaml.YAMLError as e:
            raise StyleConfigError(f"Failed to parse style config: {e}") from e
        except OSError as e:
            raise StyleConfigError(f"Failed to read style config: {e}") from e

    def _load_from_dict(self, config: dict[str, Any]) -> None:
        """Load styles from a configuration dictionary.

        Args:
            config: Configuration dictionary.
        """
        self._default_style = config.get("default_style", "")
        styles_config = config.get("styles", {})

        for style_id, style_config in styles_config.items():
            self._styles[style_id] = self._parse_style(style_id, style_config)

        if not self._styles:
            self._create_default_styles()

    def _parse_style(self, style_id: str, config: dict[str, Any]) -> Style:
        """Parse a style configuration into a Style object.

        Args:
            style_id: The style identifier.
            config: Style configuration dictionary.

        Returns:
            Parsed Style object.
        """
        negative_prompt = config.get("negative_prompt", [])
        if isinstance(negative_prompt, str):
            negative_prompt = [negative_prompt]

        return Style(
            id=style_id,
            name=config.get("name", style_id),
            description=config.get("description", ""),
            prompt_prefix=config.get("prompt_prefix", ""),
            prompt_suffix=config.get("prompt_suffix", ""),
            negative_prompt=negative_prompt,
            recommended_backends=config.get("recommended_backends", []),
            default_params=config.get("default_params", {}),
        )

    def _create_default_styles(self) -> None:
        """Create default style templates when no config is found."""
        self._styles = {
            "default": Style(
                id="default",
                name="Default",
                description="Default style without specific modifiers",
                prompt_prefix="",
                prompt_suffix="professional quality",
                default_params={"size": "1024x1024"},
            ),
            "concept_character": Style(
                id="concept_character",
                name="Game Concept - Character",
                description="For game character concept art",
                prompt_prefix="game character concept art,",
                prompt_suffix="detailed, artstation",
                default_params={"size": "1024x1792"},
            ),
        }
        self._default_style = "default"

    def get_style(self, style_id: str | None = None) -> Style:
        """Get a style by ID.

        Args:
            style_id: The style identifier. If None, returns the default style.

        Returns:
            The requested Style object.

        Raises:
            StyleNotFoundError: If the style is not found.
        """
        if style_id is None:
            style_id = self._default_style

        if not style_id:
            raise StyleNotFoundError("No style specified and no default configured")

        if style_id not in self._styles:
            available = list(self._styles.keys())
            raise StyleNotFoundError(
                f"Style '{style_id}' not found. Available styles: {available}"
            )

        return self._styles[style_id]

    def list_styles(self) -> list[str]:
        """List all available style IDs.

        Returns:
            List of style identifiers.
        """
        return list(self._styles.keys())

    def get_all_styles(self) -> list[Style]:
        """Get all available styles.

        Returns:
            List of all Style objects.
        """
        return list(self._styles.values())

    def get_recommended_backend(
        self,
        style_id: str | None = None,
        available_backends: list[str] | None = None,
    ) -> str | None:
        """Get the recommended backend for a style.

        Args:
            style_id: The style identifier.
            available_backends: List of available backend IDs to choose from.

        Returns:
            Recommended backend ID, or None if no recommendation.
        """
        try:
            style = self.get_style(style_id)
        except StyleNotFoundError:
            return None

        if not style.recommended_backends:
            return None

        # If available_backends is specified, find the first match
        if available_backends:
            for backend in style.recommended_backends:
                if backend in available_backends:
                    return backend
            return None

        # Return the first recommended backend
        return style.recommended_backends[0] if style.recommended_backends else None

    @property
    def default_style(self) -> str:
        """Get the default style ID."""
        return self._default_style

    def reload(self, config_path: str | Path | None = None) -> None:
        """Reload style configuration from file.

        Args:
            config_path: Path to the YAML file.
        """
        self._styles.clear()
        self._load_config(config_path)


# Global style manager instance
_manager: StyleManager | None = None


def get_style_manager() -> StyleManager:
    """Get the global style manager instance.

    Returns:
        The global StyleManager instance.
    """
    global _manager
    if _manager is None:
        _manager = StyleManager()
    return _manager


def reset_style_manager() -> None:
    """Reset the global style manager.

    Useful for testing or when configuration changes.
    """
    global _manager
    _manager = None
