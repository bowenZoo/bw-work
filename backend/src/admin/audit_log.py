"""
Audit logging service for Admin module.
"""

import logging
from datetime import datetime
from typing import Optional, Literal

from .database import AdminDatabase
from .crypto import mask_value

logger = logging.getLogger(__name__)

AuditAction = Literal[
    "login",
    "login_failed",
    "logout",
    "config_update",
    "config_delete",
    "bootstrap_setup",
]


class AuditLogger:
    """Audit logger for admin operations."""

    def __init__(self, db: Optional[AdminDatabase] = None):
        """Initialize audit logger."""
        self.db = db or AdminDatabase()
        self.db.init_db()

    def log(
        self,
        action: AuditAction,
        username: str,
        target: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        before_value: Optional[str] = None,
        after_value: Optional[str] = None,
        details: Optional[str] = None,
        mask_values: bool = True,
    ) -> int:
        """
        Log an audit event.

        Args:
            action: Type of action
            username: User who performed the action
            target: Target of the action (e.g., config key)
            ip_address: Client IP address
            user_agent: Client user agent
            before_value: Value before change (will be masked if mask_values=True)
            after_value: Value after change (will be masked if mask_values=True)
            details: Additional details
            mask_values: Whether to mask sensitive values

        Returns:
            Audit log entry ID
        """
        # Mask sensitive values
        masked_before = None
        masked_after = None

        if before_value and mask_values:
            masked_before = self._mask_sensitive_value(before_value)
        elif before_value:
            masked_before = before_value

        if after_value and mask_values:
            masked_after = self._mask_sensitive_value(after_value)
        elif after_value:
            masked_after = after_value

        log_id = self.db.add_audit_log(
            action=action,
            username=username,
            target=target,
            ip_address=ip_address,
            user_agent=user_agent,
            before_value=masked_before,
            after_value=masked_after,
            details=details,
        )

        # Also log to standard logger for observability
        logger.info(
            f"Audit: {action} by {username}"
            + (f" on {target}" if target else "")
            + (f" from {ip_address}" if ip_address else "")
        )

        return log_id

    def _mask_sensitive_value(self, value: str) -> str:
        """Mask sensitive value for audit log."""
        # Check for common sensitive patterns
        sensitive_patterns = [
            "api_key",
            "secret",
            "password",
            "token",
            "key",
        ]

        # If value looks like it might be sensitive, mask it
        if len(value) > 8:
            return mask_value(value, visible_chars=4)
        return mask_value(value, visible_chars=2)

    def query(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        action: Optional[AuditAction] = None,
        username: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """
        Query audit logs with filtering and pagination.

        Args:
            start_time: Filter by start time
            end_time: Filter by end time
            action: Filter by action type
            username: Filter by username
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Dict with items, total, page, page_size, total_pages
        """
        offset = (page - 1) * page_size
        items, total = self.db.get_audit_logs(
            start_time=start_time,
            end_time=end_time,
            action=action,
            username=username,
            limit=page_size,
            offset=offset,
        )

        total_pages = (total + page_size - 1) // page_size

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    def cleanup_old_logs(self, days: int = 90) -> int:
        """
        Clean up audit logs older than specified days.

        Args:
            days: Number of days to keep logs

        Returns:
            Number of logs deleted
        """
        count = self.db.cleanup_old_audit_logs(days)
        if count > 0:
            logger.info(f"Cleaned up {count} audit logs older than {days} days")
        return count

    def get_recent(self, limit: int = 10) -> list[dict]:
        """
        Get recent audit logs.

        Args:
            limit: Maximum number of logs to return

        Returns:
            List of recent audit log entries
        """
        items, _ = self.db.get_audit_logs(limit=limit, offset=0)
        return items
