"""Provider registry for image generation backends.

This module handles loading provider configurations from YAML
and instantiating the appropriate backend instances.
"""

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from src.image.backends.base import ImageBackend
from src.image.backends.openai import OpenAiBackend
from src.image.backends.openai_compatible import OpenAiCompatibleBackend
from src.image.backends.task_polling import TaskPollingBackend

logger = logging.getLogger(__name__)

# Backend type to class mapping
BACKEND_CLASSES: dict[str, type[ImageBackend]] = {
    "openai": OpenAiBackend,
    "openai_compatible": OpenAiCompatibleBackend,
    "task_polling": TaskPollingBackend,
}


class ProviderNotFoundError(Exception):
    """Raised when a requested provider is not found."""

    pass


class ProviderConfigError(Exception):
    """Raised when there's an error in provider configuration."""

    pass


class ProviderRegistry:
    """Registry for image generation providers.

    Loads provider configurations from YAML and creates backend instances.
    Supports environment variable injection for API keys.

    Usage:
        registry = ProviderRegistry()
        backend = registry.get_backend("openai_default")
        result = await backend.generate("A cute cat", {})
    """

    def __init__(
        self,
        config_path: str | Path | None = None,
        config_dict: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the provider registry.

        Args:
            config_path: Path to the providers YAML file.
                        Defaults to config/image_providers.yaml.
            config_dict: Optional dictionary to use instead of loading from file.
        """
        self._backends: dict[str, ImageBackend] = {}
        self._config: dict[str, Any] = {}
        self._default_provider: str = ""

        if config_dict is not None:
            self._config = config_dict
            self._default_provider = config_dict.get("default_provider", "")
        else:
            self._load_config(config_path)

    def _load_config(self, config_path: str | Path | None = None) -> None:
        """Load provider configuration from YAML file.

        Args:
            config_path: Path to the YAML file.

        Raises:
            ProviderConfigError: If the config file cannot be loaded.
        """
        if config_path is None:
            # Default to config/image_providers.yaml relative to this file's location
            config_path = Path(__file__).parent.parent / "config" / "image_providers.yaml"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            logger.warning(f"Provider config not found at {config_path}, using defaults")
            self._config = {"providers": {}}
            return

        try:
            with open(config_path, encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
                self._default_provider = self._config.get("default_provider", "")
        except yaml.YAMLError as e:
            raise ProviderConfigError(f"Failed to parse provider config: {e}") from e
        except OSError as e:
            raise ProviderConfigError(f"Failed to read provider config: {e}") from e

    def _resolve_api_key(self, provider_config: dict[str, Any]) -> str:
        """Resolve API key from config or environment variable.

        Args:
            provider_config: Provider configuration dictionary.

        Returns:
            The resolved API key, or empty string if not found.
        """
        # First check for direct api_key
        if "api_key" in provider_config:
            return provider_config["api_key"]

        # Then check for environment variable reference
        env_var = provider_config.get("api_key_env")
        if env_var:
            api_key = os.environ.get(env_var, "")
            if not api_key:
                logger.warning(
                    f"API key environment variable '{env_var}' is not set"
                )
            return api_key

        return ""

    def _create_backend(self, provider_id: str, provider_config: dict[str, Any]) -> ImageBackend:
        """Create a backend instance from provider configuration.

        Args:
            provider_id: The provider identifier.
            provider_config: Provider configuration dictionary.

        Returns:
            Configured ImageBackend instance.

        Raises:
            ProviderConfigError: If the backend type is unknown.
        """
        backend_type = provider_config.get("backend", "openai")
        backend_class = BACKEND_CLASSES.get(backend_type)

        if backend_class is None:
            raise ProviderConfigError(
                f"Unknown backend type '{backend_type}' for provider '{provider_id}'"
            )

        # Build the config for the backend
        config = dict(provider_config)
        config["api_key"] = self._resolve_api_key(provider_config)

        return backend_class(provider_id=provider_id, config=config)

    def get_backend(self, provider_id: str | None = None) -> ImageBackend:
        """Get an image backend for the specified provider.

        Args:
            provider_id: The provider identifier. If None, uses the default provider.

        Returns:
            ImageBackend instance for the provider.

        Raises:
            ProviderNotFoundError: If the provider is not found.
            ProviderConfigError: If the provider configuration is invalid.
        """
        if provider_id is None:
            provider_id = self._default_provider

        if not provider_id:
            raise ProviderNotFoundError("No provider specified and no default configured")

        # Check cache first
        if provider_id in self._backends:
            return self._backends[provider_id]

        # Look up provider config
        providers = self._config.get("providers", {})
        if provider_id not in providers:
            available = list(providers.keys())
            raise ProviderNotFoundError(
                f"Provider '{provider_id}' not found. Available providers: {available}"
            )

        provider_config = providers[provider_id]
        backend = self._create_backend(provider_id, provider_config)

        # Cache the backend
        self._backends[provider_id] = backend

        return backend

    def list_providers(self) -> list[str]:
        """List all available provider IDs.

        Returns:
            List of provider identifiers.
        """
        return list(self._config.get("providers", {}).keys())

    def get_provider_info(self, provider_id: str) -> dict[str, Any]:
        """Get information about a provider.

        Args:
            provider_id: The provider identifier.

        Returns:
            Dictionary with provider information (backend type, supports_sync, etc.).

        Raises:
            ProviderNotFoundError: If the provider is not found.
        """
        providers = self._config.get("providers", {})
        if provider_id not in providers:
            raise ProviderNotFoundError(f"Provider '{provider_id}' not found")

        config = providers[provider_id]
        backend_type = config.get("backend", "openai")

        return {
            "provider_id": provider_id,
            "backend_type": backend_type,
            "api_base": config.get("api_base", ""),
            "model": config.get("model", ""),
            "default_size": config.get("default_size", "1024x1024"),
        }

    @property
    def default_provider(self) -> str:
        """Get the default provider ID."""
        return self._default_provider

    def reload(self, config_path: str | Path | None = None) -> None:
        """Reload provider configuration from file.

        This clears the backend cache and reloads the config.

        Args:
            config_path: Path to the YAML file.
        """
        self._backends.clear()
        self._load_config(config_path)


# Global registry instance
_registry: ProviderRegistry | None = None


def _get_config_from_admin_store() -> dict[str, Any] | None:
    """Get image provider config from admin config store.

    Returns:
        Config dict if available, None otherwise.
    """
    try:
        from src.admin.config_store import ConfigStore

        store = ConfigStore()
        image_config = store.get_image_config()

        providers = {}
        default_provider = image_config.get("default_provider", "openai")

        # OpenAI compatible provider
        openai_config = image_config.get("openai", {})
        if openai_config.get("enabled") and openai_config.get("configured"):
            api_key = store.get_raw("image", "openai_api_key")
            if api_key:
                providers["openai"] = {
                    "backend": "openai_compatible",
                    "api_base": openai_config.get("base_url") or "https://api.openai.com/v1",
                    "api_key": api_key,
                    "model": openai_config.get("model") or "dall-e-3",
                    "default_size": "1024x1024",
                }

        # MJ provider
        mj_config = image_config.get("mj", {})
        if mj_config.get("enabled") and mj_config.get("configured"):
            api_key = store.get_raw("image", "mj_api_key")
            if api_key:
                providers["mj"] = {
                    "backend": "task_polling",
                    "api_base": mj_config.get("base_url"),
                    "api_key": api_key,
                    "mode": mj_config.get("mode") or "RELAX",
                }

        if providers:
            return {
                "default_provider": default_provider if default_provider in providers else list(providers.keys())[0],
                "providers": providers,
            }

        return None
    except Exception as e:
        logger.debug(f"Failed to get image config from admin store: {e}")
        return None


def get_provider_registry() -> ProviderRegistry:
    """Get the global provider registry instance.

    Returns:
        The global ProviderRegistry instance.
    """
    global _registry
    if _registry is None:
        # Try to get config from admin store first
        admin_config = _get_config_from_admin_store()
        if admin_config:
            logger.info("Using image provider config from admin store")
            _registry = ProviderRegistry(config_dict=admin_config)
        else:
            logger.info("Using image provider config from YAML file")
            _registry = ProviderRegistry()
    return _registry


def reset_provider_registry() -> None:
    """Reset the global provider registry.

    Useful for testing or when configuration changes.
    """
    global _registry
    _registry = None
