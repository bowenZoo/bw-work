"""
Admin audit log API routes.
"""

from datetime import datetime
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Query

from ..audit_log import AuditLogger
from ..models import AuditLogResponse, AuditLogEntry
from .auth import get_current_user

router = APIRouter(prefix="/logs", tags=["logs"])


def get_audit_logger() -> AuditLogger:
    """Get audit logger instance."""
    return AuditLogger()


@router.get(
    "",
    response_model=AuditLogResponse,
)
async def get_audit_logs(
    start_time: Optional[datetime] = Query(None, description="Filter by start time"),
    end_time: Optional[datetime] = Query(None, description="Filter by end time"),
    action: Optional[
        Literal["login", "login_failed", "logout", "config_update", "config_delete", "bootstrap_setup"]
    ] = Query(None, description="Filter by action type"),
    username: Optional[str] = Query(None, description="Filter by username"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(get_current_user),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> AuditLogResponse:
    """
    Query audit logs with filtering and pagination.

    - **start_time**: Optional start time filter
    - **end_time**: Optional end time filter
    - **action**: Optional action type filter
    - **username**: Optional username filter
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 20, max: 100)
    """
    result = audit_logger.query(
        start_time=start_time,
        end_time=end_time,
        action=action,
        username=username,
        page=page,
        page_size=page_size,
    )

    # Convert items to AuditLogEntry models
    items = []
    for item in result["items"]:
        items.append(
            AuditLogEntry(
                id=item["id"],
                timestamp=datetime.fromisoformat(item["timestamp"])
                if isinstance(item["timestamp"], str)
                else item["timestamp"],
                action=item["action"],
                username=item["username"],
                target=item.get("target"),
                ip_address=item.get("ip_address"),
                user_agent=item.get("user_agent"),
                before_value=item.get("before_value"),
                after_value=item.get("after_value"),
                details=item.get("details"),
            )
        )

    return AuditLogResponse(
        items=items,
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
    )


@router.get(
    "/recent",
    response_model=list[AuditLogEntry],
)
async def get_recent_logs(
    limit: int = Query(10, ge=1, le=50, description="Number of logs to return"),
    current_user: dict = Depends(get_current_user),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> list[AuditLogEntry]:
    """
    Get recent audit logs.

    - **limit**: Number of logs to return (default: 10, max: 50)
    """
    items = audit_logger.get_recent(limit=limit)

    return [
        AuditLogEntry(
            id=item["id"],
            timestamp=datetime.fromisoformat(item["timestamp"])
            if isinstance(item["timestamp"], str)
            else item["timestamp"],
            action=item["action"],
            username=item["username"],
            target=item.get("target"),
            ip_address=item.get("ip_address"),
            user_agent=item.get("user_agent"),
            before_value=item.get("before_value"),
            after_value=item.get("after_value"),
            details=item.get("details"),
        )
        for item in items
    ]
