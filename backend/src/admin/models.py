"""
Pydantic models for Admin module.
"""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


# =============================================================================
# Authentication Models
# =============================================================================


class LoginRequest(BaseModel):
    """Login request model."""

    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class LoginResponse(BaseModel):
    """Login response model."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token expiration in seconds")


class RefreshRequest(BaseModel):
    """Refresh token request model."""

    refresh_token: str


class RefreshResponse(BaseModel):
    """Refresh token response model."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class AdminUserInfo(BaseModel):
    """Admin user information model."""

    id: int
    username: str
    created_at: datetime
    last_login: Optional[datetime] = None


class BootstrapSetupRequest(BaseModel):
    """Bootstrap setup request model."""

    bootstrap_token: str
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)


# =============================================================================
# Configuration Models
# =============================================================================

ConfigCategory = Literal["llm", "langfuse", "image", "general"]


class ConfigItem(BaseModel):
    """Configuration item model."""

    category: ConfigCategory
    key: str
    value: str
    encrypted: bool = False
    masked_value: Optional[str] = None  # For display purposes


class ConfigUpdateRequest(BaseModel):
    """Configuration update request model."""

    value: str
    encrypted: bool = False


class ConfigTestRequest(BaseModel):
    """Configuration test request model."""

    category: ConfigCategory


class ConfigTestResponse(BaseModel):
    """Configuration test response model."""

    success: bool
    message: str
    latency_ms: Optional[float] = None


class ConfigStatusResponse(BaseModel):
    """Configuration status response model."""

    llm_configured: bool = False
    langfuse_configured: bool = False
    langfuse_enabled: bool = False
    image_configured: bool = False
    default_image_provider: Optional[str] = None


# =============================================================================
# Audit Log Models
# =============================================================================

AuditAction = Literal[
    "login",
    "login_failed",
    "logout",
    "config_update",
    "config_delete",
    "bootstrap_setup",
]


class AuditLogEntry(BaseModel):
    """Audit log entry model."""

    id: int
    timestamp: datetime
    action: AuditAction
    username: str
    target: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    before_value: Optional[str] = None  # Masked
    after_value: Optional[str] = None  # Masked
    details: Optional[str] = None


class AuditLogQuery(BaseModel):
    """Audit log query parameters."""

    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    action: Optional[AuditAction] = None
    username: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class AuditLogResponse(BaseModel):
    """Audit log response model."""

    items: list[AuditLogEntry]
    total: int
    page: int
    page_size: int
    total_pages: int


# =============================================================================
# Error Models
# =============================================================================


class ErrorResponse(BaseModel):
    """Error response model."""

    detail: str
    error_code: Optional[str] = None


class LoginLockoutResponse(BaseModel):
    """Login lockout response model."""

    detail: str
    locked_until: datetime
    remaining_seconds: int
