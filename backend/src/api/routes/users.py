"""User management routes (superadmin only)."""

import logging
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.admin.auth import hash_password
from src.admin.database import AdminDatabase
from src.api.routes.auth import require_superadmin, UserResponse, _user_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])


class UpdateUserRequest(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    display_name: Optional[str] = None


class ResetPasswordResponse(BaseModel):
    new_password: str


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    limit: int


def _get_db() -> AdminDatabase:
    return AdminDatabase()


@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    _admin: dict = Depends(require_superadmin),
):
    db = _get_db()
    users, total = db.list_users(page=page, limit=limit, search=search)
    return UserListResponse(
        items=[_user_response(u) for u in users],
        total=total, page=page, limit=limit,
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    req: UpdateUserRequest,
    admin: dict = Depends(require_superadmin),
):
    db = _get_db()
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")

    updates = {}
    if req.role is not None:
        if req.role not in ("superadmin", "user"):
            raise HTTPException(400, "Invalid role")
        updates["role"] = req.role
    if req.is_active is not None:
        updates["is_active"] = req.is_active
    if req.display_name is not None:
        updates["display_name"] = req.display_name

    if updates:
        db.update_user(user_id, **updates)

    updated = db.get_user_by_id(user_id)
    return _user_response(updated)


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    admin: dict = Depends(require_superadmin),
):
    db = _get_db()
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user["id"] == admin["id"]:
        raise HTTPException(400, "Cannot delete yourself")
    db.delete_user(user_id)
    return {"ok": True}


@router.post("/{user_id}/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    user_id: int,
    _admin: dict = Depends(require_superadmin),
):
    db = _get_db()
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    new_pw = secrets.token_urlsafe(12)
    db.update_user(user_id, password_hash=hash_password(new_pw))
    return ResetPasswordResponse(new_password=new_pw)
