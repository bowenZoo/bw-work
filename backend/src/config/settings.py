"""Application settings and configuration."""

import logging
from pathlib import Path
from typing import Any, Callable, Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# Config change callbacks registry
_config_callbacks: dict[str, list[Callable[[], None]]] = {
    "llm": [],
    "langfuse": [],
    "image": [],
}


def register_config_callback(category: str, callback: Callable[[], None]) -> None:
    """Register a callback to be called when config changes."""
    if category in _config_callbacks:
        _config_callbacks[category].append(callback)


def _notify_config_change(category: str) -> None:
    """Notify all callbacks for a config category."""
    for callback in _config_callbacks.get(category, []):
        try:
            callback()
        except Exception as e:
            logger.error(f"Config callback error for {category}: {e}")


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "BW Work Backend"
    debug: bool = False

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 18000

    # CORS
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:18000",
            "http://127.0.0.1:18000",
            "http://localhost:18001",
            "http://127.0.0.1:18001",
        ],
        alias="CORS_ALLOWED_ORIGINS",
    )
    cors_allow_credentials: bool = Field(
        default=False, alias="CORS_ALLOW_CREDENTIALS"
    )
    cors_allowed_methods: list[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        alias="CORS_ALLOWED_METHODS",
    )
    cors_allowed_headers: list[str] = Field(
        default_factory=lambda: ["*"],
        alias="CORS_ALLOWED_HEADERS",
    )

    # WebSocket
    websocket_allowed_origin_prefixes: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:",
            "http://127.0.0.1:",
            "https://localhost:",
            "https://127.0.0.1:",
        ],
        alias="WEBSOCKET_ALLOWED_ORIGIN_PREFIXES",
    )
    websocket_allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost",
            "https://localhost",
            "http://127.0.0.1",
            "https://127.0.0.1",
        ],
        alias="WEBSOCKET_ALLOWED_ORIGINS",
    )

    # LLM Configuration
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = "gpt-4"

    # Langfuse Configuration
    langfuse_public_key: str = Field(default="", alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(default="", alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com", alias="LANGFUSE_HOST"
    )

    # Paths
    config_dir: Path = Path(__file__).parent
    roles_dir: Path = Path(__file__).parent / "roles"

    # Image Service Configuration
    image_storage_type: str = Field(default="local", alias="IMAGE_STORAGE_TYPE")
    image_storage_path: str = Field(default="data/projects", alias="IMAGE_STORAGE_PATH")
    image_providers_path: str = Field(
        default="config/image_providers.yaml", alias="IMAGE_PROVIDERS_PATH"
    )
    image_styles_path: str = Field(
        default="config/image_styles.yaml", alias="IMAGE_STYLES_PATH"
    )
    image_default_provider: str = Field(
        default="openai_default", alias="IMAGE_DEFAULT_PROVIDER"
    )
    image_generation_timeout: int = Field(
        default=120, alias="IMAGE_GENERATION_TIMEOUT"
    )
    image_enable_prompt_enhancement: bool = Field(
        default=False, alias="IMAGE_ENABLE_PROMPT_ENHANCEMENT"
    )

    # Project Discussion Configuration
    project_data_dir: str = Field(
        default="data/projects", alias="PROJECT_DATA_DIR"
    )
    project_max_gdd_size_mb: int = Field(
        default=10, alias="PROJECT_MAX_GDD_SIZE_MB"
    )
    project_max_rounds_per_module: int = Field(
        default=10, alias="PROJECT_MAX_ROUNDS_PER_MODULE"
    )
    project_checkpoint_interval_seconds: int = Field(
        default=60, alias="PROJECT_CHECKPOINT_INTERVAL_SECONDS"
    )
    project_checkpoint_retention_count: int = Field(
        default=5, alias="PROJECT_CHECKPOINT_RETENTION_COUNT"
    )
    project_checkpoint_max_age_days: int = Field(
        default=30, alias="PROJECT_CHECKPOINT_MAX_AGE_DAYS"
    )
    project_ws_throttle_ms: int = Field(
        default=300, alias="PROJECT_WS_THROTTLE_MS"
    )
    project_module_detection_model: str = Field(
        default="gpt-4", alias="PROJECT_MODULE_DETECTION_MODEL"
    )
    project_design_doc_model: str = Field(
        default="gpt-4", alias="PROJECT_DESIGN_DOC_MODEL"
    )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


def load_role_config(role_name: str, settings: Settings | None = None) -> dict[str, Any]:
    """Load role configuration from YAML file.

    Args:
        role_name: Name of the role (e.g., 'system_designer')
        settings: Optional settings instance, creates new one if not provided

    Returns:
        Dictionary containing role configuration

    Raises:
        FileNotFoundError: If role config file doesn't exist
        yaml.YAMLError: If YAML parsing fails
    """
    if settings is None:
        settings = Settings()

    config_path = settings.roles_dir / f"{role_name}.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Role config not found: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# Global settings instance
settings = Settings()


def reload_config(category: Optional[str] = None) -> None:
    """
    Reload configuration from ConfigStore.

    This function reads config from the admin database and updates
    the settings object, then notifies relevant modules to refresh.

    Args:
        category: Optional specific category to reload (llm, langfuse, image).
                  If None, reloads all categories.
    """
    # Lazy import to avoid circular dependency
    try:
        from src.admin.config_store import ConfigStore

        store = ConfigStore()
    except ImportError:
        logger.warning("ConfigStore not available, skipping reload")
        return

    categories_to_reload = [category] if category else ["llm", "langfuse", "image"]

    for cat in categories_to_reload:
        if cat == "llm":
            _reload_llm_config(store)
        elif cat == "langfuse":
            _reload_langfuse_config(store)
        elif cat == "image":
            _reload_image_config(store)

        # Notify callbacks
        _notify_config_change(cat)


def _reload_llm_config(store) -> None:
    """Reload LLM configuration from active profile."""
    global settings

    config = store.get_active_llm_config()
    if config:
        if config.get("api_key"):
            settings.openai_api_key = config["api_key"]
        if config.get("model"):
            settings.openai_model = config["model"]
        logger.info("LLM config reloaded from active profile: %s", config.get("name", ""))
    else:
        # Fallback to legacy keys
        api_key = store.get_raw("llm", "openai_api_key")
        if api_key:
            settings.openai_api_key = api_key
        model = store.get_raw("llm", "openai_model")
        if model:
            settings.openai_model = model
        logger.info("LLM config reloaded from legacy keys")


def _reload_langfuse_config(store) -> None:
    """Reload Langfuse configuration."""
    global settings

    public_key = store.get_raw("langfuse", "public_key")
    if public_key:
        settings.langfuse_public_key = public_key

    secret_key = store.get_raw("langfuse", "secret_key")
    if secret_key:
        settings.langfuse_secret_key = secret_key

    host = store.get_raw("langfuse", "host")
    if host:
        settings.langfuse_host = host

    # Reset Langfuse client singleton so it reinitializes with new config
    try:
        from src.monitoring.langfuse_client import shutdown_langfuse
        shutdown_langfuse()
        logger.info("Langfuse client reset for new config")
    except ImportError:
        pass

    logger.info("Langfuse config reloaded from ConfigStore")


def _reload_image_config(store) -> None:
    """Reload image service configuration."""
    global settings

    default_provider = store.get_raw("image", "default_provider")
    if default_provider:
        settings.image_default_provider = default_provider

    # Reset image provider registry and service so they reinitialize with new config
    try:
        from src.image.providers import reset_provider_registry
        from src.image.service import reset_image_service
        reset_provider_registry()
        reset_image_service()
        logger.info("Image services reset for new config")
    except ImportError:
        pass

    logger.info("Image config reloaded from ConfigStore")


def get_effective_config(category: str) -> dict:
    """
    Get effective configuration with priority:
    environment variable > database config > default value

    Args:
        category: Configuration category (llm, langfuse, image)

    Returns:
        Dict of effective configuration values
    """
    import os

    try:
        from src.admin.config_store import ConfigStore

        store = ConfigStore()
    except ImportError:
        store = None

    if category == "llm":
        return {
            "openai_api_key": os.environ.get("OPENAI_API_KEY")
            or (store.get_raw("llm", "openai_api_key") if store else None)
            or settings.openai_api_key,
            "openai_model": os.environ.get("OPENAI_MODEL")
            or (store.get_raw("llm", "openai_model") if store else None)
            or settings.openai_model,
        }
    elif category == "langfuse":
        return {
            "public_key": os.environ.get("LANGFUSE_PUBLIC_KEY")
            or (store.get_raw("langfuse", "public_key") if store else None)
            or settings.langfuse_public_key,
            "secret_key": os.environ.get("LANGFUSE_SECRET_KEY")
            or (store.get_raw("langfuse", "secret_key") if store else None)
            or settings.langfuse_secret_key,
            "host": os.environ.get("LANGFUSE_HOST")
            or (store.get_raw("langfuse", "host") if store else None)
            or settings.langfuse_host,
            "enabled": (store.get_raw("langfuse", "enabled") if store else "false")
            == "true",
        }
    elif category == "image":
        return {
            "default_provider": os.environ.get("IMAGE_DEFAULT_PROVIDER")
            or (store.get_raw("image", "default_provider") if store else None)
            or settings.image_default_provider,
        }

    return {}
