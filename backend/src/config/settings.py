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
