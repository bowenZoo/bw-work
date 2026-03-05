"""Notification API routes — surfaces pending access requests as notifications."""

import logging
from fastapi import APIRouter, Depends
from .auth import get_current_user
from ...admin.database import AdminDatabase

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["notifications"])


def _build_notifications(db: AdminDatabase, user: dict) -> list[dict]:
    """Build notification list for a user from project_members table."""
    notifications = []
    user_id = user.get("id")
    is_admin = user.get("role") == "superadmin"

    with db.get_cursor() as cursor:
        if is_admin:
            cursor.execute(
                "SELECT pm.rowid as rid, pm.project_id, pm.user_id, pm.role, pm.joined_at, "
                "u.username, u.display_name "
                "FROM project_members pm LEFT JOIN users u ON pm.user_id = u.id "
                "WHERE pm.role LIKE 'pending_%'"
            )
        else:
            cursor.execute(
                "SELECT pm.rowid as rid, pm.project_id, pm.user_id, pm.role, pm.joined_at, "
                "u.username, u.display_name "
                "FROM project_members pm LEFT JOIN users u ON pm.user_id = u.id "
                "WHERE pm.role LIKE 'pending_%%' AND pm.project_id IN "
                "(SELECT project_id FROM project_members WHERE user_id = ? AND role = 'admin')",
                (user_id,)
            )
        for r in cursor.fetchall():
            row = dict(r)
            requested_role = row["role"].replace("pending_", "")
            display = row["display_name"] or row["username"] or f"用户{row['user_id']}"
            project_name = str(row["project_id"])
            try:
                import json
                with open("/app/data/projects/_index.json") as f:
                    idx = json.load(f)
                project_name = idx.get(str(row["project_id"]), {}).get("name", str(row["project_id"]))
            except:
                pass
            notifications.append({
                "id": f"pending_{row['project_id']}_{row['user_id']}",
                "type": "access_request",
                "project_id": row["project_id"],
                "project_name": project_name,
                "message": f"{display} 申请了「{project_name}」的{requested_role}权限",
                "read": False,
                "created_at": row["joined_at"] or "",
            })

    return notifications


@router.get("/notifications")
async def get_notifications(user: dict = Depends(get_current_user)):
    db = AdminDatabase()
    return _build_notifications(db, user)


@router.get("/notifications/unread-count")
async def get_unread_count(user: dict = Depends(get_current_user)):
    db = AdminDatabase()
    notifs = _build_notifications(db, user)
    return {"count": len(notifs)}


@router.post("/notifications/{notification_id}/read")
async def mark_read(notification_id: str, user: dict = Depends(get_current_user)):
    return {"ok": True}
