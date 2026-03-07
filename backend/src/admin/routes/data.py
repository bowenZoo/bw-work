"""
Admin data management routes — list and delete discussions/projects.
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from ..database import AdminDatabase
from .auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/data", tags=["admin-data"])

_DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "projects"


def get_db() -> AdminDatabase:
    return AdminDatabase()


# =============================================================================
# Discussions
# =============================================================================

@router.get("/discussions")
async def list_discussions(
    current_user: dict = Depends(get_current_user),
    page: int = 1,
    page_size: int = 50,
):
    """List lobby discussions only (admin only)."""
    import sqlite3

    idx_path = _DATA_DIR / ".index.db"
    if not idx_path.exists():
        return {"items": [], "total": 0}

    try:
        db = sqlite3.connect(str(idx_path))
        db.row_factory = sqlite3.Row
        offset = (page - 1) * page_size
        rows = db.execute(
            "SELECT id, topic, summary, owner_id, updated_at, archived, project_id "
            "FROM discussions WHERE project_id IN ('lobby', 'default') "
            "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (page_size, offset),
        ).fetchall()
        total_row = db.execute(
            "SELECT COUNT(*) FROM discussions WHERE project_id IN ('lobby', 'default')"
        ).fetchone()
        db.close()
    except Exception as exc:
        logger.error("Failed to list discussions: %s", exc)
        return {"items": [], "total": 0}

    admin_db = get_db()
    items = []
    for r in rows:
        r = dict(r)
        owner_name = None
        if r.get("owner_id"):
            try:
                with admin_db.get_cursor() as cur:
                    cur.execute(
                        "SELECT username, display_name FROM users WHERE id = ?",
                        (r["owner_id"],),
                    )
                    urow = cur.fetchone()
                    if urow:
                        owner_name = urow["display_name"] or urow["username"]
            except Exception:
                pass
        items.append({
            "id": r["id"],
            "topic": r["topic"],
            "summary": r.get("summary") or "",
            "owner_name": owner_name,
            "updated_at": r.get("updated_at") or "",
            "archived": bool(r.get("archived")),
            "project_id": r.get("project_id"),
        })

    return {"items": items, "total": total_row[0] if total_row else 0}


@router.delete("/discussions/{discussion_id}")
async def delete_discussion(
    discussion_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a discussion (admin only)."""
    from src.memory.discussion_memory import DiscussionMemory
    from src.api.routes.discussion import _running_crews

    # Stop if still running
    crew = _running_crews.get(discussion_id)
    if crew is not None:
        try:
            from src.crew.discussion_state import set_discussion_state, DiscussionState
            set_discussion_state(discussion_id, DiscussionState.FINISHED)
        except Exception as exc:
            logger.warning("Could not stop running discussion %s: %s", discussion_id, exc)

    mem = DiscussionMemory()
    success = mem.delete(discussion_id)
    if not success:
        raise HTTPException(status_code=404, detail="Discussion not found")

    logger.info("Admin %s deleted discussion %s", current_user.get("username"), discussion_id)
    return {"ok": True}


# =============================================================================
# Projects
# =============================================================================

@router.get("/projects")
async def list_projects(
    current_user: dict = Depends(get_current_user),
):
    """List all projects with discussion counts (admin only)."""
    import sqlite3

    index_path = _DATA_DIR / "_index.json"
    if not index_path.exists():
        return {"items": []}

    try:
        with open(index_path) as f:
            _index = json.load(f)
    except Exception as exc:
        logger.error("Failed to load project index: %s", exc)
        return {"items": []}

    # Build discussion count map from index db
    disc_counts: dict[str, int] = {}
    idx_path = _DATA_DIR / ".index.db"
    if idx_path.exists():
        try:
            db = sqlite3.connect(str(idx_path))
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT project_id, COUNT(*) as cnt FROM discussions GROUP BY project_id"
            ).fetchall()
            db.close()
            for r in rows:
                disc_counts[r["project_id"]] = r["cnt"]
        except Exception as exc:
            logger.warning("Could not count discussions: %s", exc)

    admin_db = get_db()
    items = []
    for slug, info in _index.items():
        if not isinstance(info, dict) or slug == "lobby":
            continue

        # Get creator from project.json first, then fallback to project_members
        owner_name = None
        project_json_path = _DATA_DIR / slug / "project.json"
        if project_json_path.exists():
            try:
                with open(project_json_path) as f:
                    proj_data = json.load(f)
                owner_id = proj_data.get("owner_id")
                if owner_id:
                    with admin_db.get_cursor() as cur:
                        cur.execute(
                            "SELECT username, display_name FROM users WHERE id = ?",
                            (owner_id,),
                        )
                        urow = cur.fetchone()
                        if urow:
                            owner_name = urow["display_name"] or urow["username"]
            except Exception:
                pass

        if owner_name is None:
            try:
                with admin_db.get_cursor() as cur:
                    cur.execute(
                        "SELECT u.username, u.display_name "
                        "FROM project_members pm JOIN users u ON pm.user_id = u.id "
                        "WHERE pm.project_id = ? AND pm.role IN ('admin','editor','viewer') "
                        "ORDER BY pm.joined_at ASC LIMIT 1",
                        (slug,),
                    )
                    crow = cur.fetchone()
                    if crow:
                        owner_name = crow["display_name"] or crow["username"]
            except Exception:
                pass

        items.append({
            "id": slug,
            "name": info.get("name", slug),
            "description": info.get("description", ""),
            "is_public": admin_db.get_project_visibility(slug),
            "owner_name": owner_name,
            "created_at": info.get("created_at", ""),
            "discussion_count": disc_counts.get(slug, 0),
        })

    return {"items": items}


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a project and all its data (admin only)."""
    admin_db = get_db()

    # Hard delete from DB
    try:
        with admin_db.get_cursor() as cursor:
            cursor.execute(
                "SELECT id FROM projects WHERE id = ? OR slug = ?",
                (project_id, project_id),
            )
            row = cursor.fetchone()
            db_id = row["id"] if row else None

            if db_id:
                cursor.execute(
                    "DELETE FROM document_versions WHERE document_id IN "
                    "(SELECT id FROM documents WHERE project_id = ?)",
                    (db_id,),
                )
                cursor.execute("DELETE FROM documents WHERE project_id = ?", (db_id,))
                cursor.execute("DELETE FROM project_stages WHERE project_id = ?", (db_id,))
            cursor.execute(
                "DELETE FROM project_members WHERE project_id = ?", (project_id,)
            )
            if db_id:
                cursor.execute("DELETE FROM projects WHERE id = ?", (db_id,))
    except Exception as exc:
        logger.error("DB delete failed for project %s: %s", project_id, exc)

    # Remove from file registry
    index_path = _DATA_DIR / "_index.json"
    try:
        with open(index_path) as f:
            _index = json.load(f)
        if project_id in _index:
            del _index[project_id]
            with open(index_path, "w") as f:
                json.dump(_index, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning("Could not remove project from index: %s", exc)

    logger.info("Admin %s deleted project %s", current_user.get("username"), project_id)
    return {"ok": True}
