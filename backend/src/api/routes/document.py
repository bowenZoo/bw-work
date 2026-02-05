"""Document API routes for planning document generation and management."""

from datetime import datetime

from crewai import Crew, Process
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.agents import DocumentGenerator
from src.api.routes.discussion import DiscussionStatus, _discussions
from src.memory.base import Discussion, Message
from src.memory.discussion_memory import DiscussionMemory

router = APIRouter(prefix="/api", tags=["documents"])

# Memory storage
_discussion_memory = DiscussionMemory(data_dir="data/projects")

# Document generator instance
_doc_generator = DocumentGenerator(data_dir="data/projects")


def _extract_discussion_id(content: str) -> str | None:
    """Extract discussion_id from document metadata header."""
    for line in content.splitlines()[:20]:
        if line.lower().startswith("> source discussion:"):
            return line.split(":", 1)[1].strip()
    return None


class GenerateDocRequest(BaseModel):
    """Request body for generating a document."""

    project_name: str | None = Field(
        default=None, description="Optional project name override"
    )


class DocumentResponse(BaseModel):
    """Response containing a generated document."""

    discussion_id: str
    project_id: str
    title: str
    version: str
    content: str
    file_path: str
    generated_at: str


class VersionInfo(BaseModel):
    """Information about a document version."""

    version: str
    file_path: str
    project_id: str
    created_at: str


class VersionListResponse(BaseModel):
    """Response containing list of document versions."""

    discussion_id: str
    versions: list[VersionInfo]


@router.post("/discussions/{discussion_id}/generate-doc", response_model=DocumentResponse)
async def generate_document(
    discussion_id: str,
    request: GenerateDocRequest | None = None,
) -> DocumentResponse:
    """Generate a planning document from a completed discussion.

    The discussion must be in COMPLETED state. The generated document
    is saved to data/projects/{project_id}/drafts/ with version naming.
    """
    discussion = _discussions.get(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    if discussion.status != DiscussionStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Discussion cannot generate document: current status is {discussion.status}",
        )

    # Try to load discussion from memory for full message history
    stored_discussion = _discussion_memory.load(discussion_id)

    if stored_discussion and stored_discussion.messages:
        disc = stored_discussion
    else:
        # Create discussion object from API state
        messages = []
        if discussion.result:
            messages = [
                Message(
                    id="result",
                    agent_id="discussion",
                    agent_role="Discussion",
                    content=discussion.result,
                    timestamp=datetime.now(),
                )
            ]

        disc = Discussion(
            id=discussion_id,
            project_id="default",
            topic=discussion.topic,
            messages=messages,
            created_at=datetime.fromisoformat(discussion.created_at.replace("Z", "+00:00"))
            if discussion.created_at
            else datetime.now(),
        )

    # Generate document using document generator
    project_name = request.project_name if request else None

    task = _doc_generator.create_document_task(disc, project_name or "")

    crew = Crew(
        agents=[_doc_generator.build_agent()],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )

    result = crew.kickoff()
    content = str(result)

    # Save document
    doc = _doc_generator.save_document(content, disc, project_name or "")

    return DocumentResponse(
        discussion_id=doc.discussion_id,
        project_id=doc.project_id,
        title=doc.title,
        version=doc.version,
        content=doc.content,
        file_path=doc.file_path,
        generated_at=doc.generated_at.isoformat(),
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str) -> DocumentResponse:
    """Get a document by its version ID.

    The document_id is the version string (e.g., disc1234-20240115-1430).
    Searches all project directories for the matching document.
    """
    # Search in all projects
    from pathlib import Path

    data_dir = Path("data/projects")
    if not data_dir.exists():
        raise HTTPException(status_code=404, detail="Document not found")

    # Search for document in all project draft directories
    for project_dir in data_dir.iterdir():
        if not project_dir.is_dir():
            continue

        drafts_dir = project_dir / "drafts"
        if not drafts_dir.exists():
            continue

        doc_path = drafts_dir / f"{document_id}.md"
        if doc_path.exists():
            content = _doc_generator.load_document(str(doc_path))
            if content is None:
                continue

            discussion_id = _extract_discussion_id(content)

            return DocumentResponse(
                discussion_id=discussion_id or document_id,
                project_id=project_dir.name,
                title=f"{project_dir.name} - Planning Document",
                version=document_id,
                content=content,
                file_path=str(doc_path),
                generated_at=datetime.fromtimestamp(doc_path.stat().st_mtime).isoformat(),
            )

    raise HTTPException(status_code=404, detail="Document not found")


@router.get("/documents/{document_id}/versions", response_model=VersionListResponse)
async def get_document_versions(document_id: str) -> VersionListResponse:
    """Get all versions of documents for a discussion.

    The document_id should be a discussion ID (or prefix).
    Returns all document versions generated from that discussion.
    """
    # Search all projects for versions
    from pathlib import Path

    data_dir = Path("data/projects")
    all_versions: list[VersionInfo] = []

    if data_dir.exists():
        for project_dir in data_dir.iterdir():
            if not project_dir.is_dir():
                continue

            versions = _doc_generator.list_versions(project_dir.name, document_id)
            for v in versions:
                all_versions.append(
                    VersionInfo(
                        version=v["version"],
                        file_path=v["file_path"],
                        project_id=v["project_id"],
                        created_at=v["created_at"],
                    )
                )

    # Sort by creation time
    all_versions.sort(key=lambda x: x.created_at, reverse=True)

    return VersionListResponse(
        discussion_id=document_id,
        versions=all_versions,
    )


@router.get("/projects/{project_id}/documents", response_model=list[VersionInfo])
async def list_project_documents(project_id: str) -> list[VersionInfo]:
    """List all documents for a project.

    Returns all document versions in the project's drafts directory.
    """
    versions = _doc_generator.list_versions(project_id)

    return [
        VersionInfo(
            version=v["version"],
            file_path=v["file_path"],
            project_id=v["project_id"],
            created_at=v["created_at"],
        )
        for v in versions
    ]
