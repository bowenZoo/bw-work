"""User authentication routes."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field

from src.admin.auth import (
    hash_password,
    verify_password,
    create_access_token,
    verify_token,
    create_refresh_token,
    verify_refresh_token,
    revoke_all_user_tokens,
    rotate_refresh_token,
    _get_jwt_expire_hours,
)
from src.admin.database import AdminDatabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# =============================================================================
# Request / Response Models
# =============================================================================

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=32)
    password: str = Field(..., min_length=6, max_length=128)
    display_name: Optional[str] = None
    email: Optional[str] = None
    avatar: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None
    avatar: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6, max_length=128)


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    avatar: Optional[str] = None
    role: str
    is_active: bool
    created_at: str
    last_login: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


# =============================================================================
# Dependencies
# =============================================================================

def _get_db() -> AdminDatabase:
    return AdminDatabase()


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """Extract and verify the current user from Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    token = authorization[7:]
    payload = verify_token(token)
    if not payload:
        raise HTTPException(401, "Invalid or expired token")
    db = _get_db()
    user = db.get_user_by_id(payload.get("user_id"))
    if not user:
        raise HTTPException(401, "User not found")
    if not user.get("is_active"):
        raise HTTPException(403, "Account is disabled")
    return user


async def get_optional_user(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    """Like get_current_user but returns None instead of raising."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    payload = verify_token(token)
    if not payload:
        return None
    db = _get_db()
    user = db.get_user_by_id(payload.get("user_id"))
    if not user or not user.get("is_active"):
        return None
    return user


async def require_superadmin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "superadmin":
        raise HTTPException(403, "Forbidden")
    return user


def _user_response(user: dict) -> UserResponse:
    return UserResponse(
        id=user["id"],
        username=user["username"],
        display_name=user.get("display_name"),
        email=user.get("email"),
        role=user.get("role", "user"),
        avatar=user.get("avatar", ""),
        is_active=user.get("is_active", True),
        created_at=str(user.get("created_at", "")),
        last_login=str(user["last_login"]) if user.get("last_login") else None,
    )


def _create_user_refresh_token(user_id: int, db: AdminDatabase):
    """Create refresh token in user_refresh_tokens table (no FK to admin_users)."""
    import secrets as _secrets
    import hashlib as _hashlib
    token = _secrets.token_urlsafe(64)
    token_hash = _hashlib.sha256(token.encode()).hexdigest()
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    expires_at = _dt.now(_tz.utc) + _td(days=30)
    db.store_user_refresh_token(user_id, token_hash, expires_at)
    return token, expires_at


def _verify_user_refresh_token(token: str, db: AdminDatabase):
    """Verify refresh token from user_refresh_tokens table."""
    import hashlib as _hashlib
    from datetime import datetime as _dt, timezone as _tz
    token_hash = _hashlib.sha256(token.encode()).hexdigest()
    record = db.get_user_refresh_token(token_hash)
    if not record:
        return None
    expires_at = record.get("expires_at")
    if expires_at:
        if isinstance(expires_at, str):
            from datetime import datetime
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=_tz.utc)
        if expires_at < _dt.now(_tz.utc):
            return None
    return record


def _create_token_response(user: dict, db: AdminDatabase) -> TokenResponse:
    access_token = create_access_token(
        subject=user["username"],
        user_id=user["id"],
        role=user.get("role", "user"),
    )
    refresh_token, _ = _create_user_refresh_token(user["id"], db)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=_get_jwt_expire_hours() * 3600,
        user=_user_response(user),
    )


# =============================================================================
# Routes
# =============================================================================

@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest):
    db = _get_db()
    if db.get_user(req.username):
        raise HTTPException(400, "Username already taken")
    if req.email:
        existing_email = db.get_user_by_email(req.email)
        if existing_email:
            raise HTTPException(400, "Email already registered")
    pw_hash = hash_password(req.password)
    user_id = db.create_user(
        username=req.username, password_hash=pw_hash,
        display_name=req.display_name, email=req.email,
        avatar=req.avatar or "",
    )
    if not user_id:
        raise HTTPException(500, "Failed to create user")
    user = db.get_user_by_id(user_id)
    logger.info(f"User registered: {req.username}")
    return _create_token_response(user, db)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    db = _get_db()
    user = db.get_user(req.username)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(401, "Invalid username or password")
    if not user.get("is_active"):
        raise HTTPException(403, "Account is disabled")
    db.update_user_last_login(user["id"])
    logger.info(f"User logged in: {req.username}")
    return _create_token_response(user, db)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest):
    db = _get_db()
    record = _verify_user_refresh_token(req.refresh_token, db)
    if not record:
        raise HTTPException(401, "Invalid or expired refresh token")
    user = db.get_user_by_id(record["user_id"])
    if not user or not user.get("is_active"):
        raise HTTPException(401, "User not found or disabled")
    import hashlib as _hl
    old_hash = _hl.sha256(req.refresh_token.encode()).hexdigest()
    db.revoke_user_refresh_token(old_hash)
    new_refresh_token, _ = _create_user_refresh_token(user["id"], db)
    access_token = create_access_token(
        subject=user["username"], user_id=user["id"],
        role=user.get("role", "user"),
    )
    return TokenResponse(
        access_token=access_token, refresh_token=new_refresh_token,
        expires_in=_get_jwt_expire_hours() * 3600,
        user=_user_response(user),
    )


@router.post("/logout")
async def logout(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        return {"ok": True}
    token = authorization[7:]
    payload = verify_token(token)
    if payload and payload.get("user_id"):
        db = _get_db()
        revoke_all_user_tokens(payload["user_id"], db)
    return {"ok": True}


@router.get("/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    return _user_response(user)


@router.put("/me", response_model=UserResponse)
async def update_me(req: UpdateProfileRequest, user: dict = Depends(get_current_user)):
    db = _get_db()
    updates = {}
    if req.display_name is not None:
        updates["display_name"] = req.display_name
    if req.avatar is not None:
        updates["avatar"] = req.avatar
    if req.email is not None:
        if req.email:
            existing = db.get_user_by_email(req.email)
            if existing and existing["id"] != user["id"]:
                raise HTTPException(400, "Email already registered")
        updates["email"] = req.email
    if updates:
        db.update_user(user["id"], **updates)
    updated = db.get_user_by_id(user["id"])
    return _user_response(updated)


@router.put("/password")
async def change_password(req: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    if not verify_password(req.old_password, user["password_hash"]):
        raise HTTPException(400, "Current password is incorrect")
    db = _get_db()
    db.update_user(user["id"], password_hash=hash_password(req.new_password))
    revoke_all_user_tokens(user["id"], db)
    return {"ok": True, "message": "Password changed successfully"}
