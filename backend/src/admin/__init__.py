"""
Admin module for management dashboard.

This module provides:
- Admin authentication (JWT Token)
- LLM API Key encrypted management with hot reload
- Langfuse monitoring configuration
- Image service configuration
- Configuration hot reload
- Operation audit logging
- Admin security policies (CSP, session revocation, login lockout)
"""

# Lazy imports to avoid circular dependencies
# Use direct imports when needed:
#   from src.admin.database import AdminDatabase
#   from src.admin.crypto import encrypt_value, decrypt_value
#   from src.admin.auth import hash_password, verify_password, create_access_token, verify_token
#   from src.admin.config_store import ConfigStore
#   from src.admin.audit_log import AuditLogger

__all__ = [
    "AdminDatabase",
    "encrypt_value",
    "decrypt_value",
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "ConfigStore",
    "AuditLogger",
]


def __getattr__(name: str):
    """Lazy loading of module components."""
    if name == "AdminDatabase":
        from .database import AdminDatabase
        return AdminDatabase
    elif name in ("encrypt_value", "decrypt_value"):
        from . import crypto
        return getattr(crypto, name)
    elif name in ("hash_password", "verify_password", "create_access_token", "create_refresh_token", "verify_token"):
        from . import auth
        return getattr(auth, name)
    elif name == "ConfigStore":
        from .config_store import ConfigStore
        return ConfigStore
    elif name == "AuditLogger":
        from .audit_log import AuditLogger
        return AuditLogger
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
