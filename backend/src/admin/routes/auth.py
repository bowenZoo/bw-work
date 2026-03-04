"""
Admin authentication API routes.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..database import AdminDatabase
from ..auth import (
    hash_password,
    verify_password,
    create_tokens,
    refresh_tokens,
    revoke_refresh_token,
    revoke_all_user_tokens,
    verify_token,
)
from ..models import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    AdminUserInfo,
    BootstrapSetupRequest,
    ErrorResponse,
    LoginLockoutResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# HTTP Bearer security scheme
security = HTTPBearer(auto_error=False)

# Lockout configuration
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def get_db() -> AdminDatabase:
    """Get database instance."""
    db = AdminDatabase()
    db.init_db()
    return db


def get_client_ip(request: Request) -> Optional[str]:
    """Get client IP from request."""
    # Check for forwarded headers first
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def get_user_agent(request: Request) -> Optional[str]:
    """Get user agent from request."""
    return request.headers.get("User-Agent")


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AdminDatabase = Depends(get_db),
) -> dict:
    """Get current authenticated user."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database (check admin_users first, then normal users with superadmin role)
    username = payload.get("sub")
    user = db.get_admin_user(username)
    if not user:
        # Fallback: check normal users table for superadmin
        normal_user = db.get_user(username)
        if normal_user and normal_user.get("role") == "superadmin":
            user = {
                "id": normal_user["id"],
                "username": normal_user["username"],
                "is_active": True,
            }

    if not user or not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def check_lockout(db: AdminDatabase, username: str) -> Optional[datetime]:
    """Check if user is locked out."""
    lockout_until = db.get_lockout_info(username)
    if lockout_until and lockout_until > datetime.now(timezone.utc):
        return lockout_until
    return None


def record_failed_attempt(
    db: AdminDatabase,
    username: str,
    ip_address: Optional[str],
) -> Optional[datetime]:
    """Record a failed login attempt and check for lockout."""
    # Count recent failures
    recent_failures = db.get_recent_failed_attempts(username, LOCKOUT_MINUTES)

    locked_until = None
    if recent_failures + 1 >= MAX_FAILED_ATTEMPTS:
        # Lock the account
        locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)

    db.record_login_attempt(
        username=username,
        success=False,
        ip_address=ip_address,
        locked_until=locked_until,
    )

    return locked_until


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        423: {"model": LoginLockoutResponse, "description": "Account locked"},
    },
)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: AdminDatabase = Depends(get_db),
) -> LoginResponse:
    """
    Authenticate admin user and return tokens.

    - **username**: Admin username
    - **password**: Admin password
    """
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)

    # Check if user is locked out
    lockout_until = check_lockout(db, login_data.username)
    if lockout_until:
        remaining = int((lockout_until - datetime.now(timezone.utc)).total_seconds())
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account is locked due to too many failed attempts",
            headers={"Retry-After": str(remaining)},
        )

    # Get user
    user = db.get_admin_user(login_data.username)
    if not user:
        # Still record attempt for non-existent users (prevent enumeration)
        record_failed_attempt(db, login_data.username, ip_address)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Verify password
    if not verify_password(login_data.password, user["password_hash"]):
        locked_until = record_failed_attempt(db, login_data.username, ip_address)

        # Log failed attempt
        db.add_audit_log(
            action="login_failed",
            username=login_data.username,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if locked_until:
            remaining = int((locked_until - datetime.now(timezone.utc)).total_seconds())
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account is locked due to too many failed attempts",
                headers={"Retry-After": str(remaining)},
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Check if user is active
    if not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
        )

    # Successful login - clear failed attempts
    db.clear_login_attempts(login_data.username)

    # Update last login
    db.update_last_login(login_data.username)

    # Create tokens
    tokens = create_tokens(user["username"], user["id"], db)

    # Log successful login
    db.add_audit_log(
        action="login",
        username=login_data.username,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return LoginResponse(**tokens)


@router.post("/logout")
async def logout(
    request: Request,
    refresh_data: RefreshRequest,
    current_user: dict = Depends(get_current_user),
    db: AdminDatabase = Depends(get_db),
) -> dict:
    """
    Logout and revoke refresh token.

    - **refresh_token**: The refresh token to revoke
    """
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)

    # Revoke the refresh token
    revoke_refresh_token(refresh_data.refresh_token, db)

    # Log logout
    db.add_audit_log(
        action="logout",
        username=current_user["username"],
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return {"message": "Successfully logged out"}


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    responses={401: {"model": ErrorResponse, "description": "Invalid refresh token"}},
)
async def refresh(
    refresh_data: RefreshRequest,
    db: AdminDatabase = Depends(get_db),
) -> RefreshResponse:
    """
    Refresh access token using refresh token.

    - **refresh_token**: Valid refresh token
    """
    result = refresh_tokens(refresh_data.refresh_token, db)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    return RefreshResponse(**result)


@router.get(
    "/me",
    response_model=AdminUserInfo,
    responses={401: {"model": ErrorResponse, "description": "Not authenticated"}},
)
async def get_current_user_info(
    current_user: dict = Depends(get_current_user),
) -> AdminUserInfo:
    """Get current authenticated user information."""
    return AdminUserInfo(
        id=current_user["id"],
        username=current_user["username"],
        created_at=datetime.fromisoformat(current_user["created_at"])
        if isinstance(current_user["created_at"], str)
        else current_user["created_at"],
        last_login=datetime.fromisoformat(current_user["last_login"])
        if current_user.get("last_login")
        and isinstance(current_user["last_login"], str)
        else current_user.get("last_login"),
    )


@router.post("/logout-all")
async def logout_all(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AdminDatabase = Depends(get_db),
) -> dict:
    """
    Logout from all sessions by revoking all refresh tokens.
    """
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)

    count = revoke_all_user_tokens(current_user["id"], db)

    # Log logout all
    db.add_audit_log(
        action="logout",
        username=current_user["username"],
        ip_address=ip_address,
        user_agent=user_agent,
        details=f"Revoked all {count} sessions",
    )

    return {"message": f"Successfully logged out from {count} sessions"}


@router.post("/bootstrap")
async def bootstrap_setup(
    request: Request,
    setup_data: BootstrapSetupRequest,
    db: AdminDatabase = Depends(get_db),
) -> dict:
    """
    Setup initial admin user using bootstrap token.

    This endpoint is only available when no admin users exist
    and a bootstrap token has been generated.
    """
    # Check if any admin exists
    if db.get_admin_user_count() > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin user already exists",
        )

    # Verify bootstrap token
    if not db.verify_bootstrap_token(setup_data.bootstrap_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bootstrap token",
        )

    # Create admin user
    password_hash = hash_password(setup_data.password)
    user_id = db.create_admin_user(setup_data.username, password_hash)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create admin user",
        )

    # Consume bootstrap token
    db.consume_bootstrap_token()

    # Log setup
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    db.add_audit_log(
        action="bootstrap_setup",
        username=setup_data.username,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return {"message": f"Admin user '{setup_data.username}' created successfully"}
