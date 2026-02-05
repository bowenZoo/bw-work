"""Tests for config_store module."""

import os
import pytest
import tempfile

from src.admin.config_store import ConfigStore
from src.admin.database import AdminDatabase


@pytest.fixture
def test_store():
    """Create a test config store with temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Reset singleton and create new instance
    AdminDatabase.reset_instance()
    db = AdminDatabase(db_path)
    db.init_db()
    store = ConfigStore(db)

    yield store

    # Cleanup
    db.close()
    AdminDatabase.reset_instance()
    os.unlink(db_path)


class TestConfigStore:
    """Test ConfigStore functionality."""

    def test_set_and_get_plaintext(self, test_store):
        """Test setting and getting plaintext config."""
        test_store.set("general", "app_name", "Test App")
        value = test_store.get("general", "app_name")
        assert value == "Test App"

    def test_set_and_get_encrypted(self, test_store):
        """Test setting and getting encrypted config."""
        test_store.set("llm", "api_key", "sk-test1234", encrypted=True)
        value = test_store.get("llm", "api_key")
        assert value == "sk-test1234"

    def test_get_nonexistent_returns_default(self, test_store):
        """Test getting nonexistent key returns default."""
        value = test_store.get("llm", "nonexistent", default="default-value")
        assert value == "default-value"

    def test_get_nonexistent_returns_none(self, test_store):
        """Test getting nonexistent key returns None when no default."""
        value = test_store.get("llm", "nonexistent")
        assert value is None

    def test_delete_config(self, test_store):
        """Test deleting config."""
        test_store.set("general", "to_delete", "value")
        assert test_store.get("general", "to_delete") == "value"

        result = test_store.delete("general", "to_delete")
        assert result is True
        assert test_store.get("general", "to_delete") is None

    def test_delete_nonexistent(self, test_store):
        """Test deleting nonexistent config."""
        result = test_store.delete("general", "nonexistent")
        assert result is False

    def test_exists(self, test_store):
        """Test exists check."""
        test_store.set("general", "exists", "value")
        assert test_store.exists("general", "exists") is True
        assert test_store.exists("general", "not_exists") is False

    def test_get_masked(self, test_store):
        """Test getting masked value."""
        test_store.set("llm", "secret", "my-super-secret-key", encrypted=True)
        masked = test_store.get_masked("llm", "secret")
        assert masked is not None
        assert "****" in masked
        assert masked.endswith("-key")

    def test_get_all_by_category(self, test_store):
        """Test getting all configs by category."""
        test_store.set("llm", "key1", "value1")
        test_store.set("llm", "key2", "value2")
        test_store.set("langfuse", "key3", "value3")

        llm_configs = test_store.get_all("llm")
        assert len(llm_configs) == 2

    def test_get_all(self, test_store):
        """Test getting all configs."""
        test_store.set("llm", "key1", "value1")
        test_store.set("langfuse", "key2", "value2")

        all_configs = test_store.get_all()
        assert len(all_configs) >= 2

    def test_update_existing_config(self, test_store):
        """Test updating existing config."""
        test_store.set("general", "key", "value1")
        test_store.set("general", "key", "value2")
        assert test_store.get("general", "key") == "value2"


class TestCategoryHelpers:
    """Test category-specific helper methods."""

    def test_get_llm_config(self, test_store):
        """Test getting LLM config."""
        test_store.set("llm", "openai_api_key", "sk-test", encrypted=True)
        test_store.set("llm", "openai_model", "gpt-4")

        config = test_store.get_llm_config()
        assert config["configured"] is True
        assert config["openai_model"] == "gpt-4"
        # API key should be masked (contains asterisks)
        assert "*" in config["openai_api_key"]

    def test_get_langfuse_config(self, test_store):
        """Test getting Langfuse config."""
        test_store.set("langfuse", "public_key", "pk-test", encrypted=True)
        test_store.set("langfuse", "secret_key", "sk-test", encrypted=True)
        test_store.set("langfuse", "enabled", "true")

        config = test_store.get_langfuse_config()
        assert config["configured"] is True
        assert config["enabled"] is True

    def test_get_langfuse_config_not_configured(self, test_store):
        """Test getting unconfigured Langfuse config."""
        config = test_store.get_langfuse_config()
        assert config["configured"] is False
        assert config["enabled"] is False

    def test_get_image_config(self, test_store):
        """Test getting image service config."""
        test_store.set("image", "default_provider", "dall_e")
        test_store.set("image", "dall_e_api_key", "key", encrypted=True)
        test_store.set("image", "dall_e_enabled", "true")

        config = test_store.get_image_config()
        assert config["default_provider"] == "dall_e"
        assert "dall_e" in config["providers"]
        assert config["providers"]["dall_e"]["enabled"] is True
