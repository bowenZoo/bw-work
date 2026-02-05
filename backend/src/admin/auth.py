"""
JWT authentication and password hashing for Admin module.
"""

import os
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext

from .database import AdminDatabase


# Password hashing context with bcrypt (cost factor >= 12)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def _get_jwt_secret() -> str:
    """Get JWT secret from environment or generate for development."""
    secret = os.environ.get("ADMIN_JWT_SECRET")
    if secret:
        return secret

    # Development mode: use a deterministic but unique secret per machine
    # This is NOT secure for production
    if os.environ.get("ENV", "development").lower() in ("production", "prod"):
        raise ValueError(
            "ADMIN_JWT_SECRET environment variable is required in production"
        )

    # Generate a development secret based on hostname
    import socket
    hostname = socket.gethostname()
    return hashlib.sha256(f"dev-jwt-secret-{hostname}".encode()).hexdigest()


def _get_jwt_expire_hours() -> int:
    """Get JWT expiration hours from environment."""
    return int(os.environ.get("ADMIN_JWT_EXPIRE_HOURS", "24"))


def _get_refresh_token_days() -> int:
    """Get refresh token expiration days."""
    return int(os.environ.get("ADMIN_REFRESH_TOKEN_DAYS", "7"))


# JWT configuration
JWT_SECRET = None  # Lazy loaded
JWT_ALGORITHM = "HS256"


def _ensure_jwt_secret() -> str:
    """Ensure JWT secret is loaded."""
    global JWT_SECRET
    if JWT_SECRET is None:
        JWT_SECRET = _get_jwt_secret()
    return JWT_SECRET


# =============================================================================
# Password Functions
# =============================================================================


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


# =============================================================================
# Access Token Functions
# =============================================================================


def create_access_token(
    subject: str,
    user_id: Optional[int] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        subject: The subject (usually username)
        user_id: Optional user ID to include in token
        expires_delta: Optional custom expiration time

    Returns:
        JWT token string
    """
    if expires_delta is None:
        expires_delta = timedelta(hours=_get_jwt_expire_hours())

    expire = datetime.now(timezone.utc) + expires_delta

    payload = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }

    if user_id is not None:
        payload["user_id"] = user_id

    return jwt.encode(payload, _ensure_jwt_secret(), algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    """
    Verify and decode a JWT access token.

    Args:
        token: JWT token string

    Returns:
        Decoded payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token, _ensure_jwt_secret(), algorithms=[JWT_ALGORITHM]
        )
        # Verify it's an access token
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


# =============================================================================
# Refresh Token Functions
# =============================================================================


def _hash_refresh_token(token: str) -> str:
    """Hash a refresh token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_refresh_token(
    user_id: int,
    db: Optional[AdminDatabase] = None,
) -> tuple[str, datetime]:
    """
    Create a new refresh token and store it in the database.

    Args:
        user_id: The user ID
        db: Optional database instance

    Returns:
        Tuple of (token string, expiration datetime)
    """
    if db is None:
        db = AdminDatabase()

    # Generate a secure random token
    token = secrets.token_urlsafe(64)
    token_hash = _hash_refresh_token(token)

    # Calculate expiration
    expires_at = datetime.now(timezone.utc) + timedelta(days=_get_refresh_token_days())

    # Store in database
    db.store_refresh_token(user_id, token_hash, expires_at)

    return token, expires_at


def verify_refresh_token(
    token: str,
    db: Optional[AdminDatabase] = None,
) -> Optional[dict]:
    """
    Verify a refresh token.

    Args:
        token: The refresh token string
        db: Optional database instance

    Returns:
        Token record if valid, None otherwise
    """
    if db is None:
        db = AdminDatabase()

    token_hash = _hash_refresh_token(token)
    record = db.get_refresh_token(token_hash)

    if not record:
        return None

    # Check if revoked
    if record.get("revoked"):
        return None

    # Check if expired
    expires_at = record.get("expires_at")
    if expires_at:
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            return None

    return record


def rotate_refresh_token(
    old_token: str,
    user_id: int,
    db: Optional[AdminDatabase] = None,
) -> Optional[tuple[str, datetime]]:
    """
    Rotate a refresh token - revoke old one and create new one.

    Args:
        old_token: The current refresh token to rotate
        user_id: The user ID
        db: Optional database instance

    Returns:
        Tuple of (new token, expiration) if successful, None otherwise
    """
    if db is None:
        db = AdminDatabase()

    # Verify the old token first
    old_record = verify_refresh_token(old_token, db)
    if not old_record:
        return None

    # Create new token
    new_token, expires_at = create_refresh_token(user_id, db)
    new_token_hash = _hash_refresh_token(new_token)

    # Revoke old token
    old_token_hash = _hash_refresh_token(old_token)
    db.revoke_refresh_token(old_token_hash, replaced_by=new_token_hash)

    return new_token, expires_at


def revoke_refresh_token(
    token: str,
    db: Optional[AdminDatabase] = None,
) -> bool:
    """
    Revoke a refresh token.

    Args:
        token: The refresh token to revoke
        db: Optional database instance

    Returns:
        True if revoked, False if not found
    """
    if db is None:
        db = AdminDatabase()

    token_hash = _hash_refresh_token(token)
    return db.revoke_refresh_token(token_hash)


def revoke_all_user_tokens(
    user_id: int,
    db: Optional[AdminDatabase] = None,
) -> int:
    """
    Revoke all refresh tokens for a user.

    Args:
        user_id: The user ID
        db: Optional database instance

    Returns:
        Number of tokens revoked
    """
    if db is None:
        db = AdminDatabase()

    return db.revoke_all_user_tokens(user_id)


# =============================================================================
# Combined Token Functions
# =============================================================================


def create_tokens(
    username: str,
    user_id: int,
    db: Optional[AdminDatabase] = None,
) -> dict:
    """
    Create both access and refresh tokens.

    Args:
        username: The username
        user_id: The user ID
        db: Optional database instance

    Returns:
        Dict with access_token, refresh_token, and expires_in
    """
    access_token = create_access_token(username, user_id)
    refresh_token, _ = create_refresh_token(user_id, db)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": _get_jwt_expire_hours() * 3600,
    }


def refresh_tokens(
    refresh_token: str,
    db: Optional[AdminDatabase] = None,
) -> Optional[dict]:
    """
    Refresh tokens using a valid refresh token.

    Args:
        refresh_token: The current refresh token
        db: Optional database instance

    Returns:
        New tokens dict if successful, None otherwise
    """
    if db is None:
        db = AdminDatabase()

    # Verify the refresh token
    record = verify_refresh_token(refresh_token, db)
    if not record:
        return None

    user_id = record["user_id"]

    # Get user info
    user = db.get_admin_user_by_id(user_id)
    if not user or not user.get("is_active"):
        return None

    # Rotate refresh token
    result = rotate_refresh_token(refresh_token, user_id, db)
    if not result:
        return None

    new_refresh_token, _ = result

    # Create new access token
    access_token = create_access_token(user["username"], user_id)

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": _get_jwt_expire_hours() * 3600,
    }
