"""Stage and Document API routes for the refactored project pipeline."""

import json
import logging
from pathlib import Path
from typing import Optional

# Data directory relative to this file: backend/src/api/routes/ → ×4 parents → backend/
_DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "projects"

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from .auth import get_current_user
from ...admin.database import AdminDatabase

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["stages"])


# === Models ===

class StageResponse(BaseModel):
    id: str
    project_id: str
    template_id: str
    name: str
    description: str = ""
    sort_order: int
    status: str  # locked / active / completed
    prerequisites: list[str] = []
    document_count: int = 0

class StageListResponse(BaseModel):
    stages: list[StageResponse]

class UpdateStageRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class DocumentResponse(BaseModel):
    id: str
    project_id: str
    stage_id: str
    title: str
    content: str = ""
    current_version: int = 1
    created_by: Optional[int] = None
    created_at: str = ""
    updated_at: str = ""

class CreateDocumentRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = ""

class UpdateDocumentRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None

class DocumentVersionResponse(BaseModel):
    id: str
    document_id: str
    version: int
    content: str
    diff_summary: str = ""
    source_type: str = "manual"
    source_id: Optional[str] = None
    created_by: Optional[int] = None
    created_at: str = ""

class DiscussionOutputResponse(BaseModel):
    id: str
    discussion_id: str
    title: str
    content: str
    output_type: str
    status: str
    adopted_document_id: Optional[str] = None
    adopted_version: Optional[int] = None
    created_at: str = ""

class AdoptOutputRequest(BaseModel):
    action: str = Field(..., description="new_doc or merge")
    document_id: Optional[str] = None  # required for merge
    title: Optional[str] = None  # required for new_doc

class ArchiveDiscussionRequest(BaseModel):
    project_id: str
    stage_id: str
    outputs: list[dict] = []  # [{output_id, action, target_doc_id?}]

class HallItemResponse(BaseModel):
    type: str
    is_public: bool = False
    user_role: Optional[str] = None
    id: str
    name: str
    description: str = ""
    owner_name: Optional[str] = None
    updated_at: str = ""
    extra: dict = {}

class HallResponse(BaseModel):
    items: list[HallItemResponse]

class ProjectDetailResponse(BaseModel):
    id: int
    slug: str
    name: str
    description: str = ""
    is_public: bool = False
    user_role: Optional[str] = None
    access_denied: bool = False
    stages: list[StageResponse] = []
    # documents grouped by stage returned separately


# === Hall (Homepage) ===


def _check_access(project_id: str, user: dict, required_role: str = "viewer"):
    """Check project access. Raises 403 if denied. Returns user_role."""
    if user.get("role") == "superadmin":
        return "admin"
    db = AdminDatabase()
    is_public = db.get_project_visibility(project_id)
    user_role = db.get_user_project_role(project_id, user.get("id"))
    ROLE_LEVEL = {"admin": 3, "editor": 2, "viewer": 1, "member": 1}
    
    if required_role == "viewer":
        if is_public or user_role:
            return user_role or "viewer"
        raise HTTPException(status_code=403, detail="无权访问该私密项目")
    
    # editor or admin required
    if not user_role or ROLE_LEVEL.get(user_role, 0) < ROLE_LEVEL.get(required_role, 0):
        raise HTTPException(status_code=403, detail="需要编辑权限")
    return user_role

@router.get("/hall", response_model=HallResponse)
async def get_hall(user: dict = Depends(get_current_user)):
    """Get hall: free discussions + projects mixed, sorted by activity."""
    db = AdminDatabase()
    items = []

    # Get projects from file registry
    try:
        with open(_DATA_DIR / "_index.json") as _f:
            _index = json.load(_f)
    except Exception as _e:
        logger.warning(f"Failed to load project index: {_e}")
        _index = {}

    # Import in-memory discussion states to determine running/completed status
    try:
        from src.api.routes.discussion import _discussions as _mem_discussions
    except Exception:
        _mem_discussions = {}

    for slug, info in _index.items():
        if not isinstance(info, dict) or slug == "lobby":
            continue
        stages = db.get_project_stages(slug)
        completed = sum(1 for s in stages if s["status"] == "completed")
        total = len(stages)
        _is_public = db.get_project_visibility(slug)
        _user_role = db.get_user_project_role(slug, user.get("id")) if user.get("role") != "superadmin" else "admin"
        # Derive project status from stages
        if total > 0 and completed == total:
            proj_status = "completed"
        elif any(s["status"] == "active" for s in stages):
            proj_status = "active"
        else:
            proj_status = ""
        proj_extra: dict = {"stage_progress": f"{completed}/{total}", "total_stages": total, "completed_stages": completed}
        if proj_status:
            proj_extra["status"] = proj_status
        items.append(HallItemResponse(
            type="project",
            id=slug,
            name=info.get("name", slug),
            description=info.get("description", ""),
            updated_at="",
            is_public=_is_public,
            user_role=_user_role,
            extra=proj_extra,
        ))

    # Get free discussions (project_id is null) from .index.db
    try:
        import sqlite3
        idx_db = sqlite3.connect(str(_DATA_DIR / ".index.db"))
        idx_db.row_factory = sqlite3.Row
        rows = idx_db.execute(
            "SELECT * FROM discussions WHERE project_id IS NULL OR project_id = '' OR project_id = 'lobby' ORDER BY updated_at DESC LIMIT 50"
        ).fetchall()
        for r in rows:
            r = dict(r)
            disc_id = r["id"]
            if r.get("archived"):
                disc_status = "archived"
            elif disc_id in _mem_discussions:
                disc_status = _mem_discussions[disc_id].status.value
            else:
                disc_status = "completed"
            items.append(HallItemResponse(
                type="discussion",
                id=disc_id,
                name=r["topic"],
                description=r.get("summary", "") or "",
                updated_at=r.get("updated_at", ""),
                extra={"message_count": r.get("message_count", 0), "owner_id": r.get("owner_id"), "status": disc_status},
            ))
        idx_db.close()
    except Exception as e:
        logger.warning(f"Failed to load hall discussions: {e}")

    # Sort all items by updated_at desc
    items.sort(key=lambda x: x.updated_at or "", reverse=True)
    return HallResponse(items=items)




# === Access Request ===
class AccessRequestBody(BaseModel):
    role: str = "viewer"  # viewer or editor

@router.post("/projects/{project_id}/access-request")
async def request_project_access(project_id: str, request: AccessRequestBody, user: dict = Depends(get_current_user)):
    """Request access to a private project. Creates a pending membership."""
    if not project_id or project_id == "undefined":
        raise HTTPException(status_code=400, detail="无效的项目ID")
    db = AdminDatabase()
    # Check if already a member
    existing_role = db.get_user_project_role(project_id, user.get("id"))
    if existing_role and not existing_role.startswith("pending_"):
        raise HTTPException(status_code=400, detail="你已经是该项目成员")
    # Create pending access request in project_members with role="pending_viewer" or "pending_editor"
    pending_role = f"pending_{request.role}"
    with db.get_cursor() as cursor:
        cursor.execute(
            "INSERT OR REPLACE INTO project_members (project_id, user_id, role) VALUES (?, ?, ?)",
            (project_id, user.get("id"), pending_role)
        )
    return {"ok": True, "message": "申请已发送"}


# === Access Request Management (Admin) ===

@router.get("/projects/{project_id}/access-requests")
async def list_access_requests(project_id: str, user: dict = Depends(get_current_user)):
    """List pending access requests. Only project admin or superadmin can view."""
    _check_access(project_id, user, "admin")
    db = AdminDatabase()
    with db.get_cursor() as cursor:
        cursor.execute(
            "SELECT pm.user_id, pm.role, pm.joined_at, u.username, u.display_name "
            "FROM project_members pm LEFT JOIN users u ON pm.user_id = u.id "
            "WHERE pm.project_id = ? AND pm.role LIKE 'pending_%'",
            (project_id,)
        )
        rows = cursor.fetchall()
        return [{"user_id": r[0], "requested_role": r[1].replace("pending_", ""), "requested_at": r[2], "username": r[3], "display_name": r[4]} for r in rows]


@router.post("/projects/{project_id}/access-requests/{user_id}/approve")
async def approve_access_request(project_id: str, user_id: int, user: dict = Depends(get_current_user)):
    """Approve a pending access request."""
    _check_access(project_id, user, "admin")
    db = AdminDatabase()
    with db.get_cursor() as cursor:
        cursor.execute("SELECT role FROM project_members WHERE project_id = ? AND user_id = ?", (project_id, user_id))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="未找到申请记录")
        role_str = row[0] if isinstance(row, tuple) else row["role"]
        if not role_str.startswith("pending_"):
            raise HTTPException(status_code=400, detail="该用户已是正式成员")
        new_role = role_str.replace("pending_", "")
        cursor.execute("UPDATE project_members SET role = ? WHERE project_id = ? AND user_id = ?", (new_role, project_id, user_id))
    return {"ok": True, "message": "已批准", "new_role": new_role}


@router.post("/projects/{project_id}/access-requests/{user_id}/reject")
async def reject_access_request(project_id: str, user_id: int, user: dict = Depends(get_current_user)):
    """Reject and delete a pending access request."""
    _check_access(project_id, user, "admin")
    db = AdminDatabase()
    with db.get_cursor() as cursor:
        cursor.execute("DELETE FROM project_members WHERE project_id = ? AND user_id = ? AND role LIKE 'pending_%'", (project_id, user_id))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="未找到待审批的申请")
    return {"ok": True, "message": "已拒绝"}


# === Project Detail (with stages) ===

@router.get("/projects/{project_id}/detail")
async def get_project_detail(project_id: str, user: dict = Depends(get_current_user)):
    """Get full project detail: info + stages + documents + discussions per stage."""
    # Check access but don't raise 403 for detail view — return limited info instead
    if user.get("role") == "superadmin":
        user_role = "admin"
        access_denied = False
    else:
        db_tmp = AdminDatabase()
        is_pub = db_tmp.get_project_visibility(project_id)
        user_role = db_tmp.get_user_project_role(project_id, user.get("id"))
        access_denied = not is_pub and (not user_role or str(user_role).startswith("pending_"))
    # Load project from file registry (not admin DB)
    import json, os
    index_path = str(_DATA_DIR / "_index.json")
    try:
        with open(index_path) as f:
            index = json.load(f)
    except:
        raise HTTPException(status_code=500, detail="Project index not found")
    if project_id not in index:
        raise HTTPException(status_code=404, detail="Project not found")
    db = AdminDatabase()
    _is_pub = db.get_project_visibility(project_id)
    project = {"id": project_id, "name": index[project_id].get("name", project_id), "description": index[project_id].get("description", ""), "is_public": _is_pub, "user_role": user_role, "access_denied": access_denied, "created_at": "", "updated_at": ""}
    if access_denied:
        return {"project": project, "stages": [], "discussions_by_stage": {}}

    stages = db.get_project_stages(project_id)

    # Get documents per stage
    all_docs = db.get_project_documents(project_id)
    docs_by_stage = {}
    for d in all_docs:
        sid = d["stage_id"]
        if sid not in docs_by_stage:
            docs_by_stage[sid] = []
        docs_by_stage[sid].append(d)

    # Get discussions per stage from state files (covers pending + running + completed)
    discussions_by_stage: dict = {}
    try:
        _state_dir = _DATA_DIR / ".discussion_state"
        _state_dir_env = os.environ.get("DISCUSSION_STATUS_DIR")
        if _state_dir_env:
            _state_dir = Path(_state_dir_env)
        if _state_dir.exists():
            for state_file in _state_dir.glob("*.json"):
                try:
                    data = json.loads(state_file.read_text(encoding="utf-8"))
                    if data.get("project_id") == project_id:
                        sid = data.get("target_id") or "unassigned"
                        if sid not in discussions_by_stage:
                            discussions_by_stage[sid] = []
                        discussions_by_stage[sid].append(data)
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"Failed to load project discussions: {e}")

    # Get outputs for discussions in this project
    outputs_by_stage = {}
    for sid, discs in discussions_by_stage.items():
        for disc in discs:
            disc_outputs = db.get_discussion_outputs(disc["id"])
            for o in disc_outputs:
                o["discussion_topic"] = disc.get("topic", "")
                outputs_by_stage.setdefault(sid, []).append(o)

    stage_list = []
    for s in stages:
        s_docs = docs_by_stage.get(s["id"], [])
        stage_list.append({
            **s,
            "document_count": len(s_docs),
            "documents": s_docs,
            "discussions": discussions_by_stage.get(s["id"], []),
            "outputs": outputs_by_stage.get(s["id"], []),
        })

    return {
        "project": project,
        "stages": stage_list,
    }


# === Stage Endpoints ===

@router.get("/projects/{project_id}/stages", response_model=StageListResponse)
async def list_stages(project_id: str, user: dict = Depends(get_current_user)):
    _check_access(project_id, user, "viewer")
    db = AdminDatabase()
    stages = db.get_project_stages(project_id)
    # Add document counts
    all_docs = db.get_project_documents(project_id)
    doc_counts = {}
    for d in all_docs:
        doc_counts[d["stage_id"]] = doc_counts.get(d["stage_id"], 0) + 1
    return StageListResponse(stages=[
        StageResponse(**{**s, "document_count": doc_counts.get(s["id"], 0)}) for s in stages
    ])


@router.put("/projects/{project_id}/stages/{stage_id}")
async def update_stage(project_id: str, stage_id: str, request: UpdateStageRequest,
                       user: dict = Depends(get_current_user)):
    _check_access(project_id, user, "editor")
    db = AdminDatabase()
    kwargs = {k: v for k, v in request.dict(exclude_none=True).items()}
    if not db.update_stage(stage_id, **kwargs):
        raise HTTPException(status_code=404, detail="Stage not found")
    return {"message": "Updated"}


@router.post("/projects/{project_id}/stages/{stage_id}/complete")
async def complete_stage(project_id: str, stage_id: str, user: dict = Depends(get_current_user)):
    _check_access(project_id, user, "editor")
    db = AdminDatabase()
    result = db.complete_stage(stage_id)
    return {"message": "Stage completed", "unlocked": result["unlocked"]}


# === Document Endpoints ===

@router.post("/projects/{project_id}/stages/{stage_id}/documents", response_model=DocumentResponse)
async def create_document(project_id: str, stage_id: str, request: CreateDocumentRequest,
                          user: dict = Depends(get_current_user)):
    _check_access(project_id, user, "editor")
    db = AdminDatabase()
    doc = db.create_document(project_id, stage_id, request.title, request.content, user.get("id"))
    full = db.get_document(doc["id"])
    return DocumentResponse(**full)


@router.get("/docs/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: str, user: dict = Depends(get_current_user)):
    db = AdminDatabase()
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse(**doc)


@router.put("/docs/{doc_id}", response_model=DocumentResponse)
async def update_document(doc_id: str, request: UpdateDocumentRequest,
                          user: dict = Depends(get_current_user)):
    db = AdminDatabase()
    doc = db.update_document(
        doc_id,
        title=request.title,
        content=request.content,
        source_type="manual",
        updated_by=user.get("id"),
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse(**doc)


@router.get("/docs/{doc_id}/versions", response_model=list[DocumentVersionResponse])
async def list_versions(doc_id: str, user: dict = Depends(get_current_user)):
    db = AdminDatabase()
    versions = db.get_document_versions(doc_id)
    return [DocumentVersionResponse(**v) for v in versions]


@router.get("/docs/{doc_id}/versions/{version}", response_model=DocumentVersionResponse)
async def get_version(doc_id: str, version: int, user: dict = Depends(get_current_user)):
    db = AdminDatabase()
    v = db.get_document_version(doc_id, version)
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    return DocumentVersionResponse(**v)


@router.post("/docs/{doc_id}/revert/{version}", response_model=DocumentResponse)
async def revert_document(doc_id: str, version: int, user: dict = Depends(get_current_user)):
    db = AdminDatabase()
    doc = db.revert_document(doc_id, version, user.get("id"))
    if not doc:
        raise HTTPException(status_code=404, detail="Version not found")
    return DocumentResponse(**doc)


# === Discussion Output Endpoints ===

@router.get("/discussions/{discussion_id}/outputs", response_model=list[DiscussionOutputResponse])
async def list_outputs(discussion_id: str, user: dict = Depends(get_current_user)):
    db = AdminDatabase()
    outputs = db.get_discussion_outputs(discussion_id)
    return [DiscussionOutputResponse(**o) for o in outputs]


@router.post("/discussions/{discussion_id}/outputs/{output_id}/adopt")
async def adopt_output(discussion_id: str, output_id: str, request: AdoptOutputRequest,
                       user: dict = Depends(get_current_user)):
    """Adopt a discussion output: create new document or merge into existing."""
    db = AdminDatabase()
    outputs = db.get_discussion_outputs(discussion_id)
    output = next((o for o in outputs if o["id"] == output_id), None)
    if not output:
        raise HTTPException(status_code=404, detail="Output not found")

    if request.action == "new_doc":
        if not request.title:
            request.title = output["title"]
        # Need project_id and stage_id - get from discussion
        # For now, this requires the discussion to be in a project
        import sqlite3
        idx_db = sqlite3.connect("/app/data/projects/.index.db")
        idx_db.row_factory = sqlite3.Row
        disc = idx_db.execute("SELECT * FROM discussions WHERE id = ?", (discussion_id,)).fetchone()
        idx_db.close()
        if not disc or not dict(disc).get("target_id"):
            raise HTTPException(status_code=400, detail="Discussion must be in a project stage to create doc")
        disc = dict(disc)
        # Get project_id from stage
        with db.get_cursor() as cursor:
            cursor.execute("SELECT project_id FROM project_stages WHERE id = ?", (disc["target_id"],))
            stage = cursor.fetchone()
            if not stage:
                raise HTTPException(status_code=400, detail="Stage not found")
            project_id = dict(stage)["project_id"]

        doc = db.create_document(project_id, disc["target_id"], request.title, output["content"], user.get("id"))
        db.adopt_output(output_id, doc["id"], 1)
        return {"message": "Created new document", "document_id": doc["id"]}

    elif request.action == "merge":
        if not request.document_id:
            raise HTTPException(status_code=400, detail="document_id required for merge")
        doc = db.update_document(
            request.document_id,
            content=output["content"],
            source_type="discussion",
            source_id=discussion_id,
            updated_by=user.get("id"),
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Target document not found")
        db.adopt_output(output_id, doc["id"], doc["current_version"])
        return {"message": "Merged into document", "document_id": doc["id"], "version": doc["current_version"]}

    raise HTTPException(status_code=400, detail="action must be 'new_doc' or 'merge'")


# === Discussion Archive ===

@router.post("/discussions/{discussion_id}/archive")
async def archive_discussion(discussion_id: str, request: ArchiveDiscussionRequest,
                             user: dict = Depends(get_current_user)):
    """Archive a hall discussion into a project stage."""
    import sqlite3
    idx_db = sqlite3.connect("/app/data/projects/.index.db")
    idx_db.row_factory = sqlite3.Row
    disc = idx_db.execute("SELECT * FROM discussions WHERE id = ?", (discussion_id,)).fetchone()
    if not disc:
        idx_db.close()
        raise HTTPException(status_code=404, detail="Discussion not found")
    disc = dict(disc)

    # Check ownership
    if disc.get("owner_id") != user.get("id") and user.get("role") != "superadmin":
        idx_db.close()
        raise HTTPException(status_code=403, detail="Only discussion creator can archive")

    # Check project access
    db = AdminDatabase()
    with db.get_cursor() as cursor:
        cursor.execute("SELECT id FROM projects WHERE id = ?", (request.project_id,))
        if not cursor.fetchone():
            idx_db.close()
            raise HTTPException(status_code=404, detail="Project not found")

    # Update discussion
    idx_db.execute(
        "UPDATE discussions SET project_id = ?, target_type = 'stage', target_id = ?, archived_from = id WHERE id = ?",
        (str(request.project_id), request.stage_id, discussion_id)
    )
    idx_db.commit()
    idx_db.close()

    # Process outputs if specified
    for out_spec in request.outputs:
        try:
            if out_spec.get("action") == "new_doc":
                outputs = db.get_discussion_outputs(discussion_id)
                output = next((o for o in outputs if o["id"] == out_spec["output_id"]), None)
                if output:
                    doc = db.create_document(
                        request.project_id, request.stage_id,
                        output["title"], output["content"], user.get("id")
                    )
                    db.adopt_output(out_spec["output_id"], doc["id"], 1)
        except Exception as e:
            logger.warning(f"Failed to process output during archive: {e}")

    return {"message": "Discussion archived to project"}
