"""
Configuration storage service with encryption support.
"""

import json
from typing import Optional, Literal

from .database import AdminDatabase
from .crypto import encrypt_value, decrypt_value, mask_value


ConfigCategory = Literal["llm", "langfuse", "image", "general", "discussion"]


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
        # OpenAI 兼容接口配置
        openai_api_key = self.get_masked("image", "openai_api_key")
        openai_config = {
            "base_url": self.get("image", "openai_base_url"),
            "api_key": openai_api_key,
            "model": self.get("image", "openai_model", "gemini-2.5-flash-image"),
            "enabled": self.get("image", "openai_enabled", "false") == "true",
            "configured": openai_api_key is not None,
        }

        # MJ 接口配置
        mj_api_key = self.get_masked("image", "mj_api_key")
        mj_config = {
            "base_url": self.get("image", "mj_base_url"),
            "api_key": mj_api_key,
            "mode": self.get("image", "mj_mode", "RELAX"),
            "enabled": self.get("image", "mj_enabled", "false") == "true",
            "configured": mj_api_key is not None,
        }

        return {
            "openai": openai_config,
            "mj": mj_config,
            "default_provider": self.get("image", "default_provider", "openai"),
        }

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

    # =========================================================================
    # LLM Profile management
    # =========================================================================

    def _migrate_legacy_llm_config(self) -> None:
        """Migrate old-format LLM config to profile format.

        If active_profile doesn't exist but openai_api_key does,
        migrate existing config into profile_default.
        """
        if self.exists("llm", "active_profile"):
            return  # Already migrated

        api_key = self.get("llm", "openai_api_key")
        if not api_key:
            return  # Nothing to migrate

        base_url = self.get("llm", "openai_base_url") or ""
        model = self.get("llm", "openai_model") or "gpt-4"

        profile_data = json.dumps({
            "name": "默认配置",
            "base_url": base_url,
            "model": model,
        }, ensure_ascii=False)

        self.set("llm", "profile_default", profile_data)
        self.set("llm", "profile_default_api_key", api_key, encrypted=True)
        self.set("llm", "active_profile", "default")

    def get_llm_profiles(self) -> list[dict]:
        """Get all LLM configuration profiles.

        Returns:
            List of profile dicts: [{id, name, base_url, model, has_api_key, is_active}]
        """
        self._migrate_legacy_llm_config()

        active_id = self.get("llm", "active_profile")
        configs = self.db.get_configs_by_category("llm")

        profiles = []
        for config in configs:
            key = config["key"]
            # Match profile data keys (not api_key keys)
            if key.startswith("profile_") and not key.endswith("_api_key") and key != "active_profile":
                profile_id = key[len("profile_"):]
                try:
                    data = json.loads(config["value"])
                except (json.JSONDecodeError, TypeError):
                    continue

                has_api_key = self.exists("llm", f"profile_{profile_id}_api_key")
                profiles.append({
                    "id": profile_id,
                    "name": data.get("name", profile_id),
                    "base_url": data.get("base_url", ""),
                    "model": data.get("model", "gpt-4"),
                    "has_api_key": has_api_key,
                    "is_active": profile_id == active_id,
                })

        return profiles

    def get_llm_profile(self, profile_id: str) -> dict | None:
        """Get a single LLM profile with decrypted api_key.

        Args:
            profile_id: The profile identifier.

        Returns:
            Profile dict with api_key, or None if not found.
        """
        self._migrate_legacy_llm_config()

        raw = self.get("llm", f"profile_{profile_id}")
        if not raw:
            return None

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

        api_key = self.get("llm", f"profile_{profile_id}_api_key")
        active_id = self.get("llm", "active_profile")

        return {
            "id": profile_id,
            "name": data.get("name", profile_id),
            "base_url": data.get("base_url", ""),
            "model": data.get("model", "gpt-4"),
            "api_key": api_key or "",
            "has_api_key": api_key is not None and api_key != "",
            "is_active": profile_id == active_id,
        }

    def save_llm_profile(
        self,
        profile_id: str,
        name: str,
        base_url: str,
        model: str,
        api_key: str | None = None,
    ) -> None:
        """Save an LLM profile. api_key=None means don't update the key.

        Args:
            profile_id: Profile identifier (e.g. 'default', 'deepseek').
            name: Display name.
            base_url: API base URL.
            model: Model name.
            api_key: API key (None to keep existing).
        """
        profile_data = json.dumps({
            "name": name,
            "base_url": base_url,
            "model": model,
        }, ensure_ascii=False)

        self.set("llm", f"profile_{profile_id}", profile_data)

        if api_key is not None:
            self.set("llm", f"profile_{profile_id}_api_key", api_key, encrypted=True)

    def delete_llm_profile(self, profile_id: str) -> bool:
        """Delete an LLM profile. Cannot delete the active profile.

        Args:
            profile_id: Profile to delete.

        Returns:
            True if deleted, False if not found or is active.
        """
        active_id = self.get("llm", "active_profile")
        if profile_id == active_id:
            return False

        deleted = self.delete("llm", f"profile_{profile_id}")
        self.delete("llm", f"profile_{profile_id}_api_key")
        return deleted

    def set_active_llm_profile(self, profile_id: str) -> bool:
        """Set the active LLM profile.

        Args:
            profile_id: Profile to activate.

        Returns:
            True if set, False if profile doesn't exist.
        """
        if not self.exists("llm", f"profile_{profile_id}"):
            return False

        self.set("llm", "active_profile", profile_id)
        return True

    def get_active_llm_config(self) -> dict | None:
        """Get the active profile's full config (for consumption by LLM creation).

        Returns:
            Dict with api_key, base_url, model, name, profile_id
            or None if no active profile.
        """
        self._migrate_legacy_llm_config()

        active_id = self.get("llm", "active_profile")
        if not active_id:
            return None

        return self.get_llm_profile(active_id)

    # =========================================================================
    # Stage moderator config
    # =========================================================================

    # Default leader for each stage template
    STAGE_MODERATOR_DEFAULTS: dict = {
        "concept":        "creative_director",
        "core-gameplay":  "lead_planner",
        "art-style":      "visual_concept",
        "tech-prototype": "tech_director",
        "system-design":  "system_designer",
        "numbers":        "number_designer",
        "ui-ux":          "visual_concept",
        "level-content":  "lead_planner",
        "art-assets":     "visual_concept",
        "default":        "lead_planner",
    }

    def get_stage_moderators(self) -> dict:
        """Get moderator role for each stage template.

        Returns default if not configured.
        """
        result = dict(self.STAGE_MODERATOR_DEFAULTS)
        # Override with admin-configured values
        for template_id in list(result.keys()):
            stored = self.get("discussion", f"stage_moderator_{template_id}")
            if stored:
                result[template_id] = stored
        return result

    def set_stage_moderator(self, template_id: str, role: str) -> None:
        """Set moderator role for a stage template.

        Args:
            template_id: Stage template ID (e.g. 'concept', 'system-design').
            role: Agent role name (e.g. 'creative_director').
        """
        self.set("discussion", f"stage_moderator_{template_id}", role)

    def get_stage_moderator(self, template_id: str) -> str:
        """Get moderator role for a stage template.

        Args:
            template_id: Stage template ID.

        Returns:
            Role name string.
        """
        stored = self.get("discussion", f"stage_moderator_{template_id}")
        if stored:
            return stored
        return self.STAGE_MODERATOR_DEFAULTS.get(template_id, "lead_planner")
