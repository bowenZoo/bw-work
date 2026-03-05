"""Project API routes for managing game design projects."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from .auth import get_current_user, get_optional_user
from ...admin.database import AdminDatabase

from src.project.registry import ProjectRegistry
from src.project.gdd.parser import GDDParser, MAX_FILE_SIZE, SUPPORTED_EXTENSIONS
from src.project.gdd.module_detector import ModuleDetector
from src.project.gdd.parsers.base import ParseError, ScanDocumentError
from src.project.models import GDDStatus

logger = logging.getLogger(__name__)

def _get_disc_count(project_id: str) -> int:
    """Get discussion count for a project from discussion memory DB."""
    try:
        from ...memory.discussion_memory import DiscussionMemory
        dm = DiscussionMemory()
        return dm.count_by_project(project_id)
    except Exception:
        return 0

router = APIRouter(prefix="/api/projects", tags=["projects"])

# Global instances
_registry = ProjectRegistry()
_gdd_parser = GDDParser()
_module_detector = ModuleDetector(cache_dir="data/cache/modules")


# Request/Response Models


class CreateProjectRequest(BaseModel):
    """Request body for creating a project."""

    name: str = Field(..., min_length=1, max_length=200, description="Project name")
    description: Optional[str] = Field(None, max_length=2000, description="Project description")
    is_public: bool = False


class UpdateProjectRequest(BaseModel):
    """Request body for updating a project."""

    name: Optional[str] = Field(None, min_length=1, max_length=200, description="New project name")
    description: Optional[str] = Field(None, max_length=2000, description="New project description")


class ProjectResponse(BaseModel):
    """Response containing project details."""

    id: str = Field(..., description="Project ID")
    name: str = Field(..., description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    created_at: str = Field(..., description="Creation timestamp (ISO format)")
    updated_at: str = Field(..., description="Last update timestamp (ISO format)")
    owner_id: Optional[int] = None
    is_public: bool = False
    discussion_count: int = 0


class ProjectListResponse(BaseModel):
    """Response containing a list of projects."""

    projects: list[ProjectResponse] = Field(..., description="List of projects")
    total: int = Field(..., description="Total number of projects")
    limit: int = Field(..., description="Maximum items per page")
    offset: int = Field(..., description="Number of items skipped")


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str = Field(..., description="Response message")


# GDD Models


class GDDUploadResponse(BaseModel):
    """Response for GDD upload."""

    gdd_id: str = Field(..., description="GDD document ID")
    filename: str = Field(..., description="Original filename")
    status: str = Field(..., description="Processing status")
    message: str = Field(..., description="Status message")


class GDDStatusResponse(BaseModel):
    """Response for GDD status check."""

    gdd_id: str = Field(..., description="GDD document ID")
    filename: str = Field(..., description="Original filename")
    status: str = Field(..., description="Processing status")
    error: Optional[str] = Field(None, description="Error message if failed")
    upload_time: str = Field(..., description="Upload timestamp")


class GDDModuleResponse(BaseModel):
    """Response for a detected module."""

    id: str = Field(..., description="Module ID")
    name: str = Field(..., description="Module name")
    description: str = Field(..., description="Module description")
    keywords: list[str] = Field(default_factory=list, description="Keywords")
    dependencies: list[str] = Field(default_factory=list, description="Dependency IDs")
    estimated_rounds: int = Field(..., description="Estimated discussion rounds")


class GDDModulesResponse(BaseModel):
    """Response for module detection."""

    gdd_id: str = Field(..., description="GDD document ID")
    status: str = Field(..., description="GDD status")
    modules: list[GDDModuleResponse] = Field(default_factory=list, description="Detected modules")
    suggested_order: list[str] = Field(default_factory=list, description="Suggested discussion order")
    title: Optional[str] = Field(None, description="GDD title")
    overview: Optional[str] = Field(None, description="GDD overview")


class GDDListResponse(BaseModel):
    """Response for listing GDD documents."""

    gdds: list[GDDStatusResponse] = Field(..., description="List of GDD documents")


# API Endpoints


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(request: CreateProjectRequest, user: dict = Depends(get_current_user)) -> ProjectResponse:
    """Create a new project.

    Creates a new game design project with the specified name and optional description.
    A unique project ID will be generated based on the name.
    """
    if user.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Only superadmin can create projects")
    try:
        project = _registry.create(
            name=request.name,
            description=request.description,
        )
        # Set owner and save
        project.owner_id = user["id"]
        project.is_public = getattr(request, 'is_public', False)
        import json as _json
        meta_path = _registry._project_meta_path(project.id)
        with open(meta_path, "w", encoding="utf-8") as f:
            _json.dump(project.to_dict(), f, ensure_ascii=False, indent=2)
        # Add creator as admin member (use slug as project_id for members - no FK constraint)
        _db = AdminDatabase()
        with _db.get_cursor() as cursor:
            cursor.execute(
                "INSERT OR IGNORE INTO project_members (project_id, user_id, role) VALUES (?, ?, 'admin')",
                (project.id, user["id"])
            )
        # Insert into admin DB projects table (required for FK constraints on stages)
        with _db.get_cursor() as cursor:
            cursor.execute(
                "INSERT INTO projects (slug, name, description, is_public, created_by) VALUES (?, ?, ?, ?, ?)",
                (project.id, request.name, request.description or '', getattr(request, 'is_public', False), user["id"])
            )
            db_project_id = cursor.lastrowid
        # Initialize default stages using the DB integer id
        _db.init_project_stages(db_project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat(),
    )


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    limit: int = Query(default=20, ge=1, le=100, description="Maximum items per page"),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
    user: dict = Depends(get_current_user),
) -> ProjectListResponse:
    """List all projects.

    Returns a paginated list of projects sorted by creation time (newest first).
    """
    all_projects = _registry.list(limit=1000, offset=0)
    
    # Filter by access
    if user.get("role") == "superadmin":
        accessible = all_projects
    else:
        _db = AdminDatabase()
        with _db.get_cursor() as cursor:
            cursor.execute("SELECT project_id FROM project_members WHERE user_id = ?", (user["id"],))
            member_ids = {row["project_id"] for row in cursor.fetchall()}
        accessible = [p for p in all_projects if p.is_public or p.id in member_ids]
    
    total = len(accessible)
    paged = accessible[offset:offset+limit]

    return ProjectListResponse(
        projects=[
ProjectResponse(
                id=p.id,
                name=p.name,
                description=p.description,
                created_at=p.created_at.isoformat(),
                updated_at=p.updated_at.isoformat(),
                owner_id=getattr(p, 'owner_id', None),
                is_public=getattr(p, 'is_public', False),
                discussion_count=_get_disc_count(p.id),
            )
            for p in paged
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, user: dict = Depends(get_current_user)) -> ProjectResponse:
    """Get a project by ID.

    Returns the project details for the specified project ID.
    """
    project = _registry.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat(),
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, request: UpdateProjectRequest) -> ProjectResponse:
    """Update a project.

    Updates the project name and/or description. Only provided fields will be updated.
    """
    if request.name is None and request.description is None:
        raise HTTPException(status_code=400, detail="At least one field must be provided")

    try:
        project = _registry.update(
            project_id=project_id,
            name=request.name,
            description=request.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat(),
    )


@router.delete("/{project_id}", response_model=MessageResponse)
async def delete_project(project_id: str) -> MessageResponse:
    """Delete a project.

    Performs a soft delete of the project. The project data directory is preserved
    but the project will no longer appear in listings.
    """
    deleted = _registry.delete(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")

    return MessageResponse(message=f"Project {project_id} deleted successfully")


# GDD API Endpoints


async def _process_gdd_async(project_id: str, gdd_id: str, file_path: Path, filename: str) -> None:
    """Background task to process GDD: parse and detect modules.

    Args:
        project_id: Project identifier.
        gdd_id: GDD document identifier.
        file_path: Path to the uploaded file.
        filename: Original filename.
    """
    try:
        # Parse the GDD
        doc = _gdd_parser.parse(project_id, gdd_id, file_path, filename)

        if doc.status == GDDStatus.ERROR:
            logger.error(f"GDD parsing failed for {gdd_id}: {doc.error}")
            return

        # Get parsed text for module detection
        parsed_text = _gdd_parser.get_parsed_text(project_id, gdd_id)
        if not parsed_text:
            logger.error(f"Failed to get parsed text for {gdd_id}")
            return

        # Detect modules
        try:
            parsed_gdd = await _module_detector.detect_async(parsed_text, doc.content_hash)

            # Save detected modules
            import json
            gdd_dir = Path("data/projects") / project_id / "gdd" / "parsed"
            modules_path = gdd_dir / f"{gdd_id}_modules.json"

            modules_data = {
                "gdd_id": gdd_id,
                "title": parsed_gdd.title,
                "overview": parsed_gdd.overview,
                "modules": [
                    {
                        "id": m.id,
                        "name": m.name,
                        "description": m.description,
                        "source_section": m.source_section,
                        "keywords": m.keywords,
                        "dependencies": m.dependencies,
                        "estimated_rounds": m.estimated_rounds,
                    }
                    for m in parsed_gdd.modules
                ],
                "suggested_order": _module_detector.suggest_order(parsed_gdd.modules),
            }

            with open(modules_path, "w", encoding="utf-8") as f:
                json.dump(modules_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Detected {len(parsed_gdd.modules)} modules for GDD {gdd_id}")

        except Exception as e:
            logger.error(f"Module detection failed for {gdd_id}: {e}")
            # Module detection failure doesn't fail the whole process

    except Exception as e:
        logger.exception(f"GDD processing failed for {gdd_id}: {e}")


@router.post("/{project_id}/gdd", response_model=GDDUploadResponse)
async def upload_gdd(
    project_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="GDD document file"),
) -> GDDUploadResponse:
    """Upload a GDD document for a project.

    Uploads and processes a Game Design Document. Supported formats:
    - Markdown (.md, .markdown)
    - PDF (.pdf)
    - Word (.docx)

    Maximum file size: 10MB.

    The document will be parsed asynchronously. Use GET /gdd/{gdd_id} to check status.
    """
    # Verify project exists
    if not _registry.exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate filename
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    filename = file.filename
    ext = Path(filename).suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {ext}. Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    # Check file size
    # Read content to check size and save
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File size ({len(content) / 1024 / 1024:.1f}MB) exceeds maximum ({MAX_FILE_SIZE / 1024 / 1024:.0f}MB)"
        )

    # Save the file
    try:
        gdd_id, file_path = _gdd_parser.save_upload(project_id, filename, content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Start background processing
    background_tasks.add_task(_process_gdd_async, project_id, gdd_id, file_path, filename)

    return GDDUploadResponse(
        gdd_id=gdd_id,
        filename=filename,
        status="parsing",
        message="GDD uploaded successfully. Processing in progress...",
    )


@router.get("/{project_id}/gdd", response_model=GDDListResponse)
async def list_gdds(project_id: str) -> GDDListResponse:
    """List all GDD documents for a project.

    Returns all uploaded GDD documents with their processing status.
    """
    if not _registry.exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    documents = _gdd_parser.list_documents(project_id)

    return GDDListResponse(
        gdds=[
            GDDStatusResponse(
                gdd_id=doc.id,
                filename=doc.filename,
                status=doc.status.value,
                error=doc.error,
                upload_time=doc.upload_time.isoformat(),
            )
            for doc in documents
        ]
    )


@router.get("/{project_id}/gdd/{gdd_id}", response_model=GDDStatusResponse)
async def get_gdd_status(project_id: str, gdd_id: str) -> GDDStatusResponse:
    """Get the status of a GDD document.

    Returns the processing status and any error information.
    """
    if not _registry.exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    doc = _gdd_parser.get_document(project_id, gdd_id)
    if not doc:
        raise HTTPException(status_code=404, detail="GDD not found")

    return GDDStatusResponse(
        gdd_id=doc.id,
        filename=doc.filename,
        status=doc.status.value,
        error=doc.error,
        upload_time=doc.upload_time.isoformat(),
    )


@router.get("/{project_id}/gdd/{gdd_id}/modules", response_model=GDDModulesResponse)
async def get_gdd_modules(project_id: str, gdd_id: str) -> GDDModulesResponse:
    """Get the detected modules for a GDD document.

    Returns the list of functional modules identified in the GDD,
    along with a suggested discussion order based on dependencies.
    """
    if not _registry.exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    doc = _gdd_parser.get_document(project_id, gdd_id)
    if not doc:
        raise HTTPException(status_code=404, detail="GDD not found")

    if doc.status != GDDStatus.READY:
        return GDDModulesResponse(
            gdd_id=gdd_id,
            status=doc.status.value,
            modules=[],
            suggested_order=[],
        )

    # Load detected modules
    import json
    modules_path = Path("data/projects") / project_id / "gdd" / "parsed" / f"{gdd_id}_modules.json"

    if not modules_path.exists():
        # Modules not yet detected
        return GDDModulesResponse(
            gdd_id=gdd_id,
            status="detecting_modules",
            modules=[],
            suggested_order=[],
        )

    try:
        with open(modules_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return GDDModulesResponse(
            gdd_id=gdd_id,
            status="ready",
            title=data.get("title"),
            overview=data.get("overview"),
            modules=[
                GDDModuleResponse(
                    id=m["id"],
                    name=m["name"],
                    description=m["description"],
                    keywords=m.get("keywords", []),
                    dependencies=m.get("dependencies", []),
                    estimated_rounds=m.get("estimated_rounds", 3),
                )
                for m in data.get("modules", [])
            ],
            suggested_order=data.get("suggested_order", []),
        )
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to load modules for {gdd_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load module data")


# Batch Discussion Models


class StartBatchDiscussionRequest(BaseModel):
    """Request to start a batch discussion."""

    gdd_id: str = Field(..., description="GDD document ID")
    modules: list[str] = Field(..., min_length=1, description="Module IDs to discuss")
    order: Optional[list[str]] = Field(None, description="Discussion order (optional, auto-sorted if not provided)")


class StartBatchDiscussionResponse(BaseModel):
    """Response for starting a batch discussion."""

    discussion_id: str = Field(..., description="Batch discussion ID")
    status: str = Field(..., description="Discussion status")
    websocket_url: str = Field(..., description="WebSocket URL for progress updates")


class DiscussionProgressResponse(BaseModel):
    """Response for discussion progress."""

    total_modules: int = Field(..., description="Total modules to discuss")
    completed_modules: int = Field(..., description="Completed modules count")
    current_module: Optional[str] = Field(None, description="Current module ID")
    current_round: int = Field(default=0, description="Current discussion round")


class BatchDiscussionStatusResponse(BaseModel):
    """Response for batch discussion status."""

    discussion_id: str = Field(..., description="Discussion ID")
    project_id: str = Field(..., description="Project ID")
    gdd_id: str = Field(..., description="GDD document ID")
    status: str = Field(..., description="Discussion status")
    progress: DiscussionProgressResponse = Field(..., description="Progress details")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")


class PauseDiscussionResponse(BaseModel):
    """Response for pausing a discussion."""

    status: str = Field(..., description="New status")
    checkpoint_id: str = Field(..., description="Checkpoint ID for resuming")


class ResumeDiscussionResponse(BaseModel):
    """Response for resuming a discussion."""

    status: str = Field(..., description="New status")
    current_module: Optional[str] = Field(None, description="Current module")
    completed_modules: int = Field(..., description="Completed modules count")


class SkipModuleResponse(BaseModel):
    """Response for skipping a module."""

    status: str = Field(..., description="Status")
    skipped_module: str = Field(..., description="Skipped module ID")
    current_module: Optional[str] = Field(None, description="New current module")


class CheckpointResponse(BaseModel):
    """Response for a checkpoint."""

    checkpoint_id: str = Field(..., description="Checkpoint ID")
    discussion_id: str = Field(..., description="Discussion ID")
    current_module_index: int = Field(..., description="Current module index")
    completed_modules: int = Field(..., description="Completed modules count")
    created_at: str = Field(..., description="Checkpoint creation time")


class CheckpointListResponse(BaseModel):
    """Response for listing checkpoints."""

    checkpoints: list[CheckpointResponse] = Field(..., description="List of checkpoints")


# Batch Discussion State (in-memory for now, should use executor in production)
_batch_discussions: dict[str, "BatchDiscussionRunner"] = {}


# Batch Discussion API Endpoints


@router.post("/{project_id}/discussions/batch", response_model=StartBatchDiscussionResponse)
async def start_batch_discussion(
    project_id: str,
    request: StartBatchDiscussionRequest,
    background_tasks: BackgroundTasks,
) -> StartBatchDiscussionResponse:
    """Start a batch discussion for multiple modules.

    Starts sequential discussions for the selected modules. Progress is reported
    via WebSocket at /ws/projects/{project_id}.

    If order is not provided, modules will be automatically sorted based on
    their dependency relationships (topological sort).
    """
    from src.project.discussion.batch_runner import BatchDiscussionRunner, BatchDiscussionConfig
    from src.project.discussion.checkpoint import CheckpointManager
    from src.project.models import GDDModule

    # Verify project exists
    if not _registry.exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    # Load modules from GDD
    modules_path = Path("data/projects") / project_id / "gdd" / "parsed" / f"{request.gdd_id}_modules.json"
    if not modules_path.exists():
        raise HTTPException(status_code=404, detail="GDD modules not found. Ensure GDD is fully processed.")

    try:
        with open(modules_path, "r", encoding="utf-8") as f:
            modules_data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"Failed to load modules: {e}")

    # Build module map
    all_modules = {
        m["id"]: GDDModule(
            id=m["id"],
            name=m["name"],
            description=m["description"],
            source_section=m.get("source_section", ""),
            keywords=m.get("keywords", []),
            dependencies=m.get("dependencies", []),
            estimated_rounds=m.get("estimated_rounds", 3),
        )
        for m in modules_data.get("modules", [])
    }

    # Validate requested modules exist
    for mid in request.modules:
        if mid not in all_modules:
            raise HTTPException(status_code=400, detail=f"Module '{mid}' not found in GDD")

    # Get modules to discuss
    modules = [all_modules[mid] for mid in request.modules]

    # Determine order
    if request.order:
        # Validate order
        if set(request.order) != set(request.modules):
            raise HTTPException(
                status_code=400,
                detail="Order must contain exactly the same modules as the modules list"
            )

        # Validate dependency order
        valid, violations = _module_detector.validate_order(modules, request.order)
        if not valid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid module order: {'; '.join(violations)}"
            )
        module_order = request.order
    else:
        # Auto-sort by dependencies
        module_order = _module_detector.suggest_order(modules)

    # Create batch runner
    runner = BatchDiscussionRunner(
        project_id=project_id,
        gdd_id=request.gdd_id,
        modules=modules,
        module_order=module_order,
        config=BatchDiscussionConfig(),
    )

    # Store runner
    _batch_discussions[runner.discussion_id] = runner

    # Start in background
    async def run_discussion():
        try:
            await runner.run()
        except Exception as e:
            logger.exception(f"Batch discussion failed: {e}")
        finally:
            # Cleanup after completion (keep for a while for status queries)
            pass

    background_tasks.add_task(run_discussion)

    return StartBatchDiscussionResponse(
        discussion_id=runner.discussion_id,
        status="started",
        websocket_url=f"/ws/projects/{project_id}",
    )


@router.get("/{project_id}/discussions/{discussion_id}", response_model=BatchDiscussionStatusResponse)
async def get_batch_discussion_status(project_id: str, discussion_id: str) -> BatchDiscussionStatusResponse:
    """Get the status of a batch discussion.

    Returns the current status and progress of the batch discussion.
    """
    if not _registry.exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    runner = _batch_discussions.get(discussion_id)
    if not runner or runner.project_id != project_id:
        # Try to load from checkpoint
        from src.project.discussion.checkpoint import CheckpointManager
        checkpoint_manager = CheckpointManager()
        checkpoint = checkpoint_manager.load(project_id, discussion_id)

        if not checkpoint:
            raise HTTPException(status_code=404, detail="Discussion not found")

        # Return checkpoint-based status
        return BatchDiscussionStatusResponse(
            discussion_id=discussion_id,
            project_id=project_id,
            gdd_id=checkpoint.gdd_id,
            status="paused",
            progress=DiscussionProgressResponse(
                total_modules=len(checkpoint.selected_modules),
                completed_modules=len(checkpoint.completed_modules),
                current_module=checkpoint.selected_modules[checkpoint.current_module_index]
                if checkpoint.current_module_index < len(checkpoint.selected_modules)
                else None,
                current_round=checkpoint.current_module_state.round
                if checkpoint.current_module_state
                else 0,
            ),
            created_at=checkpoint.created_at.isoformat(),
            updated_at=checkpoint.updated_at.isoformat(),
        )

    discussion = runner.get_discussion()
    return BatchDiscussionStatusResponse(
        discussion_id=discussion.id,
        project_id=discussion.project_id,
        gdd_id=discussion.gdd_id,
        status=discussion.status.value,
        progress=DiscussionProgressResponse(
            total_modules=discussion.progress.total_modules,
            completed_modules=discussion.progress.completed_modules,
            current_module=discussion.progress.current_module,
            current_round=discussion.progress.current_round,
        ),
        created_at=discussion.created_at.isoformat(),
        updated_at=discussion.updated_at.isoformat(),
    )


@router.post("/{project_id}/discussions/{discussion_id}/pause", response_model=PauseDiscussionResponse)
async def pause_batch_discussion(project_id: str, discussion_id: str) -> PauseDiscussionResponse:
    """Pause a running batch discussion.

    The discussion will pause after completing the current module.
    A checkpoint is saved for later resumption.
    """
    if not _registry.exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    runner = _batch_discussions.get(discussion_id)
    if not runner or runner.project_id != project_id:
        raise HTTPException(status_code=404, detail="Discussion not found")

    if runner.state.value not in ("running", "pending"):
        raise HTTPException(status_code=400, detail=f"Cannot pause discussion in state: {runner.state.value}")

    runner.request_pause()

    return PauseDiscussionResponse(
        status="pausing",
        checkpoint_id=f"{discussion_id}_latest",
    )


@router.post("/{project_id}/discussions/{discussion_id}/resume", response_model=ResumeDiscussionResponse)
async def resume_batch_discussion(
    project_id: str,
    discussion_id: str,
    background_tasks: BackgroundTasks,
) -> ResumeDiscussionResponse:
    """Resume a paused batch discussion.

    Continues from the last checkpoint.
    """
    from src.project.discussion.batch_runner import BatchDiscussionRunner, BatchDiscussionConfig
    from src.project.discussion.checkpoint import CheckpointManager
    from src.project.models import GDDModule

    if not _registry.exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    # Load checkpoint
    checkpoint_manager = CheckpointManager()
    checkpoint = checkpoint_manager.load(project_id, discussion_id)

    if not checkpoint:
        raise HTTPException(status_code=404, detail="No checkpoint found for this discussion")

    # Load modules
    modules_path = Path("data/projects") / project_id / "gdd" / "parsed" / f"{checkpoint.gdd_id}_modules.json"
    with open(modules_path, "r", encoding="utf-8") as f:
        modules_data = json.load(f)

    modules = [
        GDDModule(
            id=m["id"],
            name=m["name"],
            description=m["description"],
            source_section=m.get("source_section", ""),
            keywords=m.get("keywords", []),
            dependencies=m.get("dependencies", []),
            estimated_rounds=m.get("estimated_rounds", 3),
        )
        for m in modules_data.get("modules", [])
        if m["id"] in checkpoint.selected_modules
    ]

    # Create new runner
    runner = BatchDiscussionRunner(
        project_id=project_id,
        gdd_id=checkpoint.gdd_id,
        modules=modules,
        module_order=checkpoint.selected_modules,
        config=BatchDiscussionConfig(),
    )

    _batch_discussions[discussion_id] = runner

    # Resume in background
    async def resume_discussion():
        try:
            await runner.resume(checkpoint)
        except Exception as e:
            logger.exception(f"Resume failed: {e}")

    background_tasks.add_task(resume_discussion)

    current_module = (
        checkpoint.selected_modules[checkpoint.current_module_index]
        if checkpoint.current_module_index < len(checkpoint.selected_modules)
        else None
    )

    return ResumeDiscussionResponse(
        status="resumed",
        current_module=current_module,
        completed_modules=len(checkpoint.completed_modules),
    )


@router.post("/{project_id}/discussions/{discussion_id}/skip", response_model=SkipModuleResponse)
async def skip_current_module(project_id: str, discussion_id: str) -> SkipModuleResponse:
    """Skip the current module in a batch discussion.

    Marks the current module as skipped and moves to the next one.
    """
    if not _registry.exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    runner = _batch_discussions.get(discussion_id)
    if not runner or runner.project_id != project_id:
        raise HTTPException(status_code=404, detail="Discussion not found")

    if runner.state.value != "running":
        raise HTTPException(status_code=400, detail=f"Cannot skip in state: {runner.state.value}")

    current_module = runner.module_order[runner.current_module_index]
    runner.request_skip()

    # Determine next module
    next_index = runner.current_module_index + 1
    next_module = runner.module_order[next_index] if next_index < len(runner.module_order) else None

    return SkipModuleResponse(
        status="skipped",
        skipped_module=current_module,
        current_module=next_module,
    )


@router.get("/{project_id}/checkpoints", response_model=CheckpointListResponse)
async def list_checkpoints(project_id: str) -> CheckpointListResponse:
    """List all checkpoints for a project.

    Returns checkpoints that can be used to resume paused discussions.
    """
    from src.project.discussion.checkpoint import CheckpointManager

    if not _registry.exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    checkpoint_manager = CheckpointManager()
    discussion_ids = checkpoint_manager.list_discussions_with_checkpoints(project_id)

    checkpoints = []
    for disc_id in discussion_ids:
        cp = checkpoint_manager.load(project_id, disc_id)
        if cp:
            checkpoints.append(
                CheckpointResponse(
                    checkpoint_id=f"{disc_id}_latest",
                    discussion_id=disc_id,
                    current_module_index=cp.current_module_index,
                    completed_modules=len(cp.completed_modules),
                    created_at=cp.created_at.isoformat(),
                )
            )

    return CheckpointListResponse(checkpoints=checkpoints)


# Design Document Models


class DesignDocResponse(BaseModel):
    """Response for a design document."""

    module_id: str = Field(..., description="Module ID")
    path: str = Field(..., description="Document path")
    content: str = Field(..., description="Document content (Markdown)")


class DesignDocListResponse(BaseModel):
    """Response for listing design documents."""

    project_id: str = Field(..., description="Project ID")
    documents: list[dict] = Field(..., description="List of document info")


class DesignIndexResponse(BaseModel):
    """Response for project design index."""

    project_id: str = Field(..., description="Project ID")
    index_path: str = Field(..., description="Index document path")
    content: str = Field(..., description="Index content (Markdown)")
    modules: list[str] = Field(..., description="List of module IDs with design docs")


# Design Document API Endpoints


@router.get("/{project_id}/design", response_model=DesignIndexResponse)
async def get_design_index(project_id: str) -> DesignIndexResponse:
    """Get the project design document index.

    Returns the consolidated index of all module design documents.
    """
    from src.project.output.design_doc import DesignDocGenerator
    from src.project.output.summary import ProjectSummaryGenerator

    if not _registry.exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    summary_gen = ProjectSummaryGenerator()
    content = summary_gen.get_summary(project_id)

    doc_gen = DesignDocGenerator()
    docs = doc_gen.list_documents(project_id)
    module_ids = [d[0] for d in docs]

    if not content:
        # Generate a basic index if not exists
        content = f"# {project_id} 策划案索引\n\n暂无内容。"

    return DesignIndexResponse(
        project_id=project_id,
        index_path=f"data/projects/{project_id}/design/index.md",
        content=content,
        modules=module_ids,
    )


@router.get("/{project_id}/design/{module_id}", response_model=DesignDocResponse)
async def get_design_document(project_id: str, module_id: str) -> DesignDocResponse:
    """Get a module design document.

    Returns the design document for the specified module.
    """
    from src.project.output.design_doc import DesignDocGenerator

    if not _registry.exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    generator = DesignDocGenerator()
    content = generator.get_document(project_id, module_id)

    if not content:
        raise HTTPException(status_code=404, detail=f"Design document for module '{module_id}' not found")

    return DesignDocResponse(
        module_id=module_id,
        path=f"data/projects/{project_id}/design/{module_id}-system.md",
        content=content,
    )


@router.get("/{project_id}/design/export")
async def export_design_documents(
    project_id: str,
    format: str = Query(default="markdown", description="Export format: markdown or pdf"),
):
    """Export all design documents.

    Returns all design documents in the specified format.
    - markdown: Returns a ZIP file with all Markdown documents
    - pdf: Returns a combined PDF (requires weasyprint)
    """
    from fastapi.responses import FileResponse, StreamingResponse
    import io
    import zipfile

    if not _registry.exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    if format not in ("markdown", "pdf"):
        raise HTTPException(status_code=400, detail="Format must be 'markdown' or 'pdf'")

    from src.project.output.design_doc import DesignDocGenerator
    from src.project.output.summary import ProjectSummaryGenerator

    doc_gen = DesignDocGenerator()
    summary_gen = ProjectSummaryGenerator()

    docs = doc_gen.list_documents(project_id)
    index_content = summary_gen.get_summary(project_id)

    if format == "markdown":
        # Create ZIP file in memory
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add index
            if index_content:
                zf.writestr("index.md", index_content)

            # Add all design docs
            for module_id, path in docs:
                content = doc_gen.get_document(project_id, module_id)
                if content:
                    zf.writestr(f"{module_id}-system.md", content)

        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={project_id}-design-docs.zip"
            },
        )

    else:  # pdf
        # PDF export would require weasyprint or similar
        # For now, return an error suggesting markdown format
        raise HTTPException(
            status_code=501,
            detail="PDF export is not yet implemented. Please use 'markdown' format."
        )


# === Member Management ===

class AddMemberRequest(BaseModel):
    username: str
    role: str = "editor"  # editor, viewer, or admin


@router.get("/{project_id}/members")
async def list_project_members(project_id: str, user: dict = Depends(get_current_user)):
    """List project members."""
    project = _registry.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    _db = AdminDatabase()
    with _db.get_cursor() as cursor:
        cursor.execute("""
            SELECT pm.user_id as id, u.username, u.display_name, pm.role, pm.joined_at
            FROM project_members pm
            JOIN users u ON pm.user_id = u.id
            WHERE pm.project_id = ?
            ORDER BY pm.role DESC, pm.joined_at
        """, (project_id,))
        return {"items": [dict(row) for row in cursor.fetchall()]}


@router.post("/{project_id}/members")
async def add_project_member(project_id: str, request: AddMemberRequest, user: dict = Depends(get_current_user)):
    """Add a member to project. Project owner or superadmin only."""
    project = _registry.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if user.get("role") != "superadmin" and getattr(project, 'owner_id', None) != user["id"]:
        raise HTTPException(status_code=403, detail="Only project owner or superadmin can manage members")
    
    _db = AdminDatabase()
    with _db.get_cursor() as cursor:
        cursor.execute("SELECT id FROM users WHERE username = ?", (request.username,))
        target = cursor.fetchone()
        if not target:
            raise HTTPException(status_code=404, detail=f"User '{request.username}' not found")
        
        try:
            cursor.execute(
                "INSERT INTO project_members (project_id, user_id, role) VALUES (?, ?, ?)",
                (project_id, target["id"], request.role)
            )
        except Exception as e:
            if "UNIQUE" in str(e) or "PRIMARY" in str(e):
                raise HTTPException(status_code=409, detail="User is already a member")
            raise
    
    return {"message": f"Added {request.username} as {request.role}"}


@router.delete("/{project_id}/members/{member_user_id}")
async def remove_project_member(project_id: str, member_user_id: int, user: dict = Depends(get_current_user)):
    """Remove a member from project."""
    project = _registry.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if user.get("role") != "superadmin" and getattr(project, 'owner_id', None) != user["id"]:
        raise HTTPException(status_code=403, detail="Only project owner or superadmin can manage members")
    
    _db = AdminDatabase()
    with _db.get_cursor() as cursor:
        cursor.execute(
            "DELETE FROM project_members WHERE project_id = ? AND user_id = ?",
            (project_id, member_user_id)
        )
    
    return {"message": "Removed"}
