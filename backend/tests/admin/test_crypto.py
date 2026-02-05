"""Tests for crypto module."""

import os
import pytest
import base64
import secrets
from pathlib import Path
import tempfile

from src.admin.crypto import (
    encrypt_value,
    decrypt_value,
    generate_key,
    mask_value,
    CryptoError,
    get_encryption_key,
)


class TestEncryption:
    """Test encryption and decryption."""

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encrypt/decrypt returns original value."""
        plaintext = "test-secret-value"
        encrypted = encrypt_value(plaintext)
        decrypted = decrypt_value(encrypted)
        assert decrypted == plaintext

    def test_encrypt_produces_different_output(self):
        """Test that same plaintext produces different ciphertext (due to random nonce)."""
        plaintext = "test-value"
        encrypted1 = encrypt_value(plaintext)
        encrypted2 = encrypt_value(plaintext)
        assert encrypted1 != encrypted2

    def test_encrypt_decrypt_with_custom_key(self):
        """Test encryption with custom key."""
        key = secrets.token_bytes(32)
        plaintext = "custom-key-test"
        encrypted = encrypt_value(plaintext, key=key)
        decrypted = decrypt_value(encrypted, key=key)
        assert decrypted == plaintext

    def test_decrypt_with_wrong_key_fails(self):
        """Test that decryption with wrong key fails."""
        key1 = secrets.token_bytes(32)
        key2 = secrets.token_bytes(32)
        plaintext = "test"
        encrypted = encrypt_value(plaintext, key=key1)
        with pytest.raises(CryptoError):
            decrypt_value(encrypted, key=key2)

    def test_invalid_key_length_raises_error(self):
        """Test that invalid key length raises error."""
        invalid_key = b"too-short"
        with pytest.raises(CryptoError):
            encrypt_value("test", key=invalid_key)

    def test_encrypt_empty_string(self):
        """Test encrypting empty string."""
        encrypted = encrypt_value("")
        decrypted = decrypt_value(encrypted)
        assert decrypted == ""

    def test_encrypt_unicode(self):
        """Test encrypting unicode characters."""
        plaintext = "Hello, 世界! 🔐"
        encrypted = encrypt_value(plaintext)
        decrypted = decrypt_value(encrypted)
        assert decrypted == plaintext

    def test_encrypt_long_string(self):
        """Test encrypting long string."""
        plaintext = "x" * 10000
        encrypted = encrypt_value(plaintext)
        decrypted = decrypt_value(encrypted)
        assert decrypted == plaintext


class TestGenerateKey:
    """Test key generation."""

    def test_generate_key_length(self):
        """Test that generated key is correct length."""
        key_b64 = generate_key()
        key = base64.b64decode(key_b64)
        assert len(key) == 32

    def test_generate_key_unique(self):
        """Test that generated keys are unique."""
        key1 = generate_key()
        key2 = generate_key()
        assert key1 != key2


class TestMaskValue:
    """Test value masking."""

    def test_mask_value_default(self):
        """Test masking with default visible chars."""
        masked = mask_value("sk-1234567890")
        # 12 chars - 4 visible = 8 asterisks
        assert masked.endswith("7890")
        assert "*" in masked

    def test_mask_value_custom_visible(self):
        """Test masking with custom visible chars."""
        masked = mask_value("secret123", visible_chars=2)
        assert masked == "*******23"

    def test_mask_short_value(self):
        """Test masking value shorter than visible chars."""
        masked = mask_value("abc", visible_chars=4)
        assert masked == "***"

    def test_mask_empty_value(self):
        """Test masking empty value."""
        masked = mask_value("")
        assert masked == ""


class TestGetEncryptionKey:
    """Test encryption key retrieval."""

    def test_get_key_from_environment(self):
        """Test getting key from environment variable."""
        test_key = base64.b64encode(secrets.token_bytes(32)).decode()
        os.environ["ADMIN_ENCRYPTION_KEY"] = test_key
        try:
            key = get_encryption_key()
            assert len(key) == 32
        finally:
            del os.environ["ADMIN_ENCRYPTION_KEY"]

    def test_invalid_env_key_raises_error(self):
        """Test that invalid environment key raises error."""
        os.environ["ADMIN_ENCRYPTION_KEY"] = "invalid-key"
        try:
            with pytest.raises(CryptoError):
                get_encryption_key()
        finally:
            del os.environ["ADMIN_ENCRYPTION_KEY"]
