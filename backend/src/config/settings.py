"""Application settings and configuration."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


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
