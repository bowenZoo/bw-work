"""
AES-256-GCM encryption utilities for Admin module.
"""

import os
import base64
import secrets
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CryptoError(Exception):
    """Custom exception for crypto operations."""

    pass


def _get_keys_dir() -> Path:
    """Get the keys directory path."""
    keys_dir = Path(__file__).parent.parent.parent.parent / "data" / "admin" / ".keys"
    return keys_dir


def _is_production() -> bool:
    """Check if running in production mode."""
    return os.environ.get("ENV", "development").lower() in ("production", "prod")


def _validate_key(key: bytes) -> None:
    """Validate that the key is exactly 32 bytes."""
    if len(key) != 32:
        raise CryptoError(
            f"Encryption key must be exactly 32 bytes, got {len(key)} bytes. "
            "Key should be a 32-byte value encoded as Base64."
        )


def get_encryption_key() -> bytes:
    """
    Get the encryption key from environment or auto-generate in development.

    In production:
        - MUST be set via ADMIN_ENCRYPTION_KEY environment variable
        - Raises CryptoError if not set

    In development:
        - If ADMIN_ENCRYPTION_KEY is set, use it
        - Otherwise, auto-generate and save to data/admin/.keys/admin_encryption.key
    """
    # Try environment variable first
    env_key = os.environ.get("ADMIN_ENCRYPTION_KEY")
    if env_key:
        try:
            key = base64.b64decode(env_key)
            _validate_key(key)
            return key
        except Exception as e:
            raise CryptoError(
                f"Invalid ADMIN_ENCRYPTION_KEY: {e}. "
                "Key must be a 32-byte value encoded as Base64."
            )

    # Production requires environment variable
    if _is_production():
        raise CryptoError(
            "ADMIN_ENCRYPTION_KEY environment variable is required in production. "
            "Generate a key with: python -c \"import secrets; import base64; print(base64.b64encode(secrets.token_bytes(32)).decode())\""
        )

    # Development: try to load or generate key
    keys_dir = _get_keys_dir()
    key_file = keys_dir / "admin_encryption.key"

    if key_file.exists():
        try:
            key_b64 = key_file.read_text().strip()
            key = base64.b64decode(key_b64)
            _validate_key(key)
            return key
        except Exception as e:
            raise CryptoError(f"Failed to load encryption key from {key_file}: {e}")

    # Generate new key
    key = secrets.token_bytes(32)
    key_b64 = base64.b64encode(key).decode()

    # Ensure directory exists
    keys_dir.mkdir(parents=True, exist_ok=True)

    # Write key file with restricted permissions
    key_file.write_text(key_b64)
    os.chmod(key_file, 0o600)

    return key


def encrypt_value(plaintext: str, key: Optional[bytes] = None) -> str:
    """
    Encrypt a string value using AES-256-GCM.

    Args:
        plaintext: The string to encrypt
        key: Optional encryption key. If not provided, uses get_encryption_key()

    Returns:
        Base64-encoded ciphertext in format: nonce(12 bytes) + ciphertext + tag(16 bytes)
    """
    if key is None:
        key = get_encryption_key()

    _validate_key(key)

    # Generate random 12-byte nonce for each encryption
    nonce = secrets.token_bytes(12)

    # Create AESGCM cipher
    aesgcm = AESGCM(key)

    # Encrypt (AESGCM automatically appends 16-byte auth tag)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

    # Combine nonce + ciphertext and encode as base64
    encrypted = base64.b64encode(nonce + ciphertext).decode("utf-8")
    return encrypted


def decrypt_value(encrypted: str, key: Optional[bytes] = None) -> str:
    """
    Decrypt a string value that was encrypted with encrypt_value.

    Args:
        encrypted: Base64-encoded ciphertext from encrypt_value
        key: Optional encryption key. If not provided, uses get_encryption_key()

    Returns:
        The original plaintext string
    """
    if key is None:
        key = get_encryption_key()

    _validate_key(key)

    try:
        # Decode from base64
        data = base64.b64decode(encrypted)

        # Extract nonce (first 12 bytes) and ciphertext
        nonce = data[:12]
        ciphertext = data[12:]

        # Create AESGCM cipher
        aesgcm = AESGCM(key)

        # Decrypt
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
    except Exception as e:
        raise CryptoError(f"Failed to decrypt value: {e}")


def generate_key() -> str:
    """
    Generate a new encryption key.

    Returns:
        Base64-encoded 32-byte key
    """
    key = secrets.token_bytes(32)
    return base64.b64encode(key).decode("utf-8")


def mask_value(value: str, visible_chars: int = 4) -> str:
    """
    Mask a sensitive value, showing only the last N characters.

    Args:
        value: The value to mask
        visible_chars: Number of characters to show at the end

    Returns:
        Masked string like "****xxxx"
    """
    if not value:
        return ""
    if len(value) <= visible_chars:
        return "*" * len(value)
    return "*" * (len(value) - visible_chars) + value[-visible_chars:]
