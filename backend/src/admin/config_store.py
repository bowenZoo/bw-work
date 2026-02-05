"""
Configuration storage service with encryption support.
"""

from typing import Optional, Literal

from .database import AdminDatabase
from .crypto import encrypt_value, decrypt_value, mask_value


ConfigCategory = Literal["llm", "langfuse", "image", "general"]


class ConfigStore:
    """Configuration storage with automatic encryption/decryption."""

    def __init__(self, db: Optional[AdminDatabase] = None):
        """Initialize config store."""
        self.db = db or AdminDatabase()
        self.db.init_db()

    def get(
        self,
        category: ConfigCategory,
        key: str,
        default: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get a configuration value.

        Args:
            category: Configuration category
            key: Configuration key
            default: Default value if not found

        Returns:
            Decrypted value or default
        """
        config = self.db.get_config(category, key)
        if not config:
            return default

        value = config["value"]

        # Decrypt if encrypted
        if config.get("encrypted"):
            try:
                value = decrypt_value(value)
            except Exception:
                # Return None if decryption fails
                return None

        return value

    def set(
        self,
        category: ConfigCategory,
        key: str,
        value: str,
        encrypted: bool = False,
    ) -> None:
        """
        Set a configuration value.

        Args:
            category: Configuration category
            key: Configuration key
            value: Configuration value
            encrypted: Whether to encrypt the value
        """
        stored_value = value
        if encrypted:
            stored_value = encrypt_value(value)

        self.db.set_config(category, key, stored_value, encrypted)

    def delete(self, category: ConfigCategory, key: str) -> bool:
        """
        Delete a configuration.

        Args:
            category: Configuration category
            key: Configuration key

        Returns:
            True if deleted, False if not found
        """
        return self.db.delete_config(category, key)

    def get_all(self, category: Optional[ConfigCategory] = None) -> list[dict]:
        """
        Get all configurations, optionally filtered by category.

        Values are NOT decrypted but masked for display.

        Args:
            category: Optional category filter

        Returns:
            List of config items with masked values
        """
        if category:
            configs = self.db.get_configs_by_category(category)
        else:
            configs = self.db.get_all_configs()

        result = []
        for config in configs:
            item = {
                "category": config["category"],
                "key": config["key"],
                "encrypted": config.get("encrypted", False),
                "updated_at": config.get("updated_at"),
            }

            # Mask sensitive values
            if config.get("encrypted"):
                # Decrypt and mask
                try:
                    decrypted = decrypt_value(config["value"])
                    item["masked_value"] = mask_value(decrypted)
                    item["value"] = item["masked_value"]  # Don't expose raw value
                except Exception:
                    item["masked_value"] = "****"
                    item["value"] = "****"
            else:
                item["value"] = config["value"]
                item["masked_value"] = config["value"]

            result.append(item)

        return result

    def get_masked(
        self,
        category: ConfigCategory,
        key: str,
    ) -> Optional[str]:
        """
        Get a masked version of a configuration value.

        Args:
            category: Configuration category
            key: Configuration key

        Returns:
            Masked value or None if not found
        """
        config = self.db.get_config(category, key)
        if not config:
            return None

        if config.get("encrypted"):
            try:
                decrypted = decrypt_value(config["value"])
                return mask_value(decrypted)
            except Exception:
                return "****"

        return config["value"]

    def exists(self, category: ConfigCategory, key: str) -> bool:
        """
        Check if a configuration exists.

        Args:
            category: Configuration category
            key: Configuration key

        Returns:
            True if exists
        """
        return self.db.get_config(category, key) is not None

    # =========================================================================
    # Category-specific helpers
    # =========================================================================

    def get_llm_config(self) -> dict:
        """Get all LLM configuration."""
        return {
            "openai_api_key": self.get_masked("llm", "openai_api_key"),
            "openai_base_url": self.get("llm", "openai_base_url"),
            "openai_model": self.get("llm", "openai_model", "gpt-4"),
            "configured": self.exists("llm", "openai_api_key"),
        }

    def get_langfuse_config(self) -> dict:
        """Get all Langfuse configuration."""
        return {
            "public_key": self.get_masked("langfuse", "public_key"),
            "secret_key": self.get_masked("langfuse", "secret_key"),
            "host": self.get("langfuse", "host", "https://cloud.langfuse.com"),
            "enabled": self.get("langfuse", "enabled", "false") == "true",
            "configured": self.exists("langfuse", "public_key")
            and self.exists("langfuse", "secret_key"),
        }

    def get_image_config(self) -> dict:
        """Get all image service configuration."""
        providers = ["kie_ai", "wenwen_ai", "nanobanana", "dall_e"]
        result = {
            "default_provider": self.get("image", "default_provider", "dall_e"),
            "providers": {},
        }

        for provider in providers:
            api_key = self.get_masked("image", f"{provider}_api_key")
            enabled = self.get("image", f"{provider}_enabled", "false") == "true"
            result["providers"][provider] = {
                "api_key": api_key,
                "enabled": enabled,
                "configured": api_key is not None,
            }

        return result

    # =========================================================================
    # Raw value access (for internal use)
    # =========================================================================

    def get_raw(
        self,
        category: ConfigCategory,
        key: str,
        default: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get raw (decrypted) configuration value.
        For internal use when actual value is needed.

        Args:
            category: Configuration category
            key: Configuration key
            default: Default value if not found

        Returns:
            Decrypted value or default
        """
        return self.get(category, key, default)
