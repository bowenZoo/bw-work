"""Tests for auth module."""

import os
import pytest
import tempfile
from datetime import timedelta

from src.admin.auth import (
    hash_password,
    verify_password,
    create_access_token,
    verify_token,
    create_refresh_token,
    verify_refresh_token,
    rotate_refresh_token,
    revoke_refresh_token,
    revoke_all_user_tokens,
    create_tokens,
    refresh_tokens,
)
from src.admin.database import AdminDatabase


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Reset singleton and create new instance
    AdminDatabase.reset_instance()
    db = AdminDatabase(db_path)
    db.init_db()

    yield db

    # Cleanup
    db.close()
    AdminDatabase.reset_instance()
    os.unlink(db_path)


class TestPasswordHashing:
    """Test password hashing functions."""

    def test_hash_password_returns_different_hash(self):
        """Test that hashing same password returns different hashes (salted)."""
        password = "test-password"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2

    def test_verify_password_correct(self):
        """Test verifying correct password."""
        password = "my-secure-password"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test verifying incorrect password."""
        hashed = hash_password("correct-password")
        assert verify_password("wrong-password", hashed) is False

    def test_hash_password_bcrypt_format(self):
        """Test that hash is in bcrypt format."""
        hashed = hash_password("test")
        assert hashed.startswith("$2")


class TestAccessToken:
    """Test JWT access token functions."""

    def test_create_access_token(self):
        """Test creating access token."""
        token = create_access_token("testuser")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_valid_token(self):
        """Test verifying valid token."""
        token = create_access_token("testuser", user_id=1)
        payload = verify_token(token)
        assert payload is not None
        assert payload["sub"] == "testuser"
        assert payload["user_id"] == 1
        assert payload["type"] == "access"

    def test_verify_invalid_token(self):
        """Test verifying invalid token."""
        payload = verify_token("invalid-token")
        assert payload is None

    def test_verify_expired_token(self):
        """Test verifying expired token."""
        token = create_access_token("testuser", expires_delta=timedelta(seconds=-1))
        payload = verify_token(token)
        assert payload is None

    def test_create_token_with_custom_expiry(self):
        """Test creating token with custom expiration."""
        token = create_access_token("testuser", expires_delta=timedelta(hours=1))
        payload = verify_token(token)
        assert payload is not None


class TestRefreshToken:
    """Test refresh token functions."""

    def test_create_refresh_token(self, test_db):
        """Test creating refresh token."""
        # Create test user
        test_db.create_admin_user("testuser", hash_password("test"))
        user = test_db.get_admin_user("testuser")

        token, expires_at = create_refresh_token(user["id"], test_db)
        assert isinstance(token, str)
        assert len(token) > 0
        assert expires_at is not None

    def test_verify_refresh_token(self, test_db):
        """Test verifying refresh token."""
        test_db.create_admin_user("testuser", hash_password("test"))
        user = test_db.get_admin_user("testuser")

        token, _ = create_refresh_token(user["id"], test_db)
        record = verify_refresh_token(token, test_db)

        assert record is not None
        assert record["user_id"] == user["id"]

    def test_verify_invalid_refresh_token(self, test_db):
        """Test verifying invalid refresh token."""
        record = verify_refresh_token("invalid-token", test_db)
        assert record is None

    def test_revoke_refresh_token(self, test_db):
        """Test revoking refresh token."""
        test_db.create_admin_user("testuser", hash_password("test"))
        user = test_db.get_admin_user("testuser")

        token, _ = create_refresh_token(user["id"], test_db)

        # Revoke
        result = revoke_refresh_token(token, test_db)
        assert result is True

        # Verify it's revoked
        record = verify_refresh_token(token, test_db)
        assert record is None

    def test_rotate_refresh_token(self, test_db):
        """Test rotating refresh token."""
        test_db.create_admin_user("testuser", hash_password("test"))
        user = test_db.get_admin_user("testuser")

        old_token, _ = create_refresh_token(user["id"], test_db)

        # Rotate
        result = rotate_refresh_token(old_token, user["id"], test_db)
        assert result is not None

        new_token, _ = result

        # Old token should be invalid
        old_record = verify_refresh_token(old_token, test_db)
        assert old_record is None

        # New token should be valid
        new_record = verify_refresh_token(new_token, test_db)
        assert new_record is not None

    def test_revoke_all_user_tokens(self, test_db):
        """Test revoking all user tokens."""
        test_db.create_admin_user("testuser", hash_password("test"))
        user = test_db.get_admin_user("testuser")

        # Create multiple tokens
        token1, _ = create_refresh_token(user["id"], test_db)
        token2, _ = create_refresh_token(user["id"], test_db)

        # Revoke all
        count = revoke_all_user_tokens(user["id"], test_db)
        assert count == 2

        # All should be invalid
        assert verify_refresh_token(token1, test_db) is None
        assert verify_refresh_token(token2, test_db) is None


class TestCombinedTokens:
    """Test combined token functions."""

    def test_create_tokens(self, test_db):
        """Test creating both tokens."""
        test_db.create_admin_user("testuser", hash_password("test"))
        user = test_db.get_admin_user("testuser")

        tokens = create_tokens(user["username"], user["id"], test_db)

        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert "token_type" in tokens
        assert tokens["token_type"] == "bearer"
        assert "expires_in" in tokens

    def test_refresh_tokens(self, test_db):
        """Test refreshing tokens."""
        test_db.create_admin_user("testuser", hash_password("test"))
        user = test_db.get_admin_user("testuser")

        # Create initial tokens
        initial_tokens = create_tokens(user["username"], user["id"], test_db)

        # Refresh
        new_tokens = refresh_tokens(initial_tokens["refresh_token"], test_db)

        assert new_tokens is not None
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens
        # New refresh token should be different
        assert new_tokens["refresh_token"] != initial_tokens["refresh_token"]

    def test_refresh_with_invalid_token(self, test_db):
        """Test refreshing with invalid token."""
        result = refresh_tokens("invalid-token", test_db)
        assert result is None
