"""
Admin configuration API routes.
"""

import time
from typing import Literal, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from ..config_store import ConfigStore
from ..crypto import mask_value
from ..database import AdminDatabase
from .auth import get_current_user, get_client_ip, get_user_agent
from ..models import (
    ConfigUpdateRequest,
    ConfigTestResponse,
    ConfigStatusResponse,
    ErrorResponse,
)
from src.config.settings import reload_config

router = APIRouter(prefix="/config", tags=["config"])

# Allowed domains for SSRF protection in test endpoints
ALLOWED_TEST_DOMAINS = [
    # OpenAI
    "api.openai.com",
    # Moonshot (Kimi)
    "api.moonshot.ai",
    "api.moonshot.cn",
    # DeepSeek
    "api.deepseek.com",
    # 智谱 AI (GLM)
    "open.bigmodel.cn",
    # 通义千问 (Qwen/DashScope)
    "dashscope.aliyuncs.com",
    "dashscope-intl.aliyuncs.com",
    # MiniMax
    "api.minimaxi.com",
    # 问问 AI
    "api.wenwen-ai.com",
    # Langfuse
    "cloud.langfuse.com",
    "us.cloud.langfuse.com",
    "eu.cloud.langfuse.com",
]


def get_config_store() -> ConfigStore:
    """Get config store instance."""
    return ConfigStore()


def get_db() -> AdminDatabase:
    """Get database instance."""
    db = AdminDatabase()
    db.init_db()
    return db


def validate_domain(url: str) -> bool:
    """Validate URL domain is in allowed list."""
    try:
        parsed = urlparse(url)
        return parsed.netloc in ALLOWED_TEST_DOMAINS
    except Exception:
        return False


# =========================================================================
# Pydantic models
# =========================================================================


class LlmProfileRequest(BaseModel):
    """Request body for creating/updating an LLM profile."""

    id: str = Field("", description="Profile ID (auto-generated if empty on create)")
    name: str = Field(..., min_length=1, description="Display name")
    base_url: str = Field("", description="API base URL")
    model: str = Field("gpt-4", description="Model name")
    api_key: str | None = Field(None, description="API key (None = keep existing)")


# =========================================================================
# Generic config endpoints
# =========================================================================


@router.get(
    "",
    response_model=list[dict],
)
async def get_all_configs(
    category: Optional[Literal["llm", "langfuse", "image", "general", "discussion"]] = None,
    current_user: dict = Depends(get_current_user),
    store: ConfigStore = Depends(get_config_store),
) -> list[dict]:
    """
    Get all configurations (masked for sensitive values).

    - **category**: Optional filter by category
    """
    return store.get_all(category)


@router.get(
    "/status",
    response_model=ConfigStatusResponse,
)
async def get_config_status(
    current_user: dict = Depends(get_current_user),
    store: ConfigStore = Depends(get_config_store),
) -> ConfigStatusResponse:
    """Get configuration status overview."""
    llm_config = store.get_llm_config()
    langfuse_config = store.get_langfuse_config()
    image_config = store.get_image_config()

    # Check image configuration - providers are at top level (openai, mj)
    image_configured = (
        image_config.get("openai", {}).get("configured", False)
        or image_config.get("mj", {}).get("configured", False)
    )

    return ConfigStatusResponse(
        llm_configured=llm_config.get("configured", False),
        langfuse_configured=langfuse_config.get("configured", False),
        langfuse_enabled=langfuse_config.get("enabled", False),
        image_configured=image_configured,
        default_image_provider=image_config.get("default_provider"),
    )


# =========================================================================
# LLM Profile API (must be registered BEFORE /{category} catch-all)
# =========================================================================


@router.get("/llm/profiles")
async def list_llm_profiles(
    current_user: dict = Depends(get_current_user),
    store: ConfigStore = Depends(get_config_store),
) -> list[dict]:
    """List all LLM configuration profiles."""
    return store.get_llm_profiles()


@router.post("/llm/profiles")
async def create_llm_profile(
    request: Request,
    data: LlmProfileRequest,
    current_user: dict = Depends(get_current_user),
    store: ConfigStore = Depends(get_config_store),
    db: AdminDatabase = Depends(get_db),
) -> dict:
    """Create a new LLM profile."""
    import re

    profile_id = data.id.strip() if data.id else ""
    if not profile_id:
        # Auto-generate from name (slugify)
        profile_id = re.sub(r"[^a-zA-Z0-9_-]", "_", data.name.lower()).strip("_")
        if not profile_id:
            import uuid
            profile_id = uuid.uuid4().hex[:8]

    # Check if already exists
    if store.exists("llm", f"profile_{profile_id}"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Profile '{profile_id}' already exists",
        )

    store.save_llm_profile(
        profile_id=profile_id,
        name=data.name,
        base_url=data.base_url,
        model=data.model,
        api_key=data.api_key,
    )

    # If this is the first profile, auto-activate it
    profiles = store.get_llm_profiles()
    if len(profiles) == 1:
        store.set_active_llm_profile(profile_id)

    # Audit log
    db.add_audit_log(
        action="llm_profile_create",
        username=current_user["username"],
        target=f"llm/profile/{profile_id}",
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        after_value=data.name,
    )

    reload_config("llm")

    return store.get_llm_profile(profile_id) or {"id": profile_id}


@router.put("/llm/profiles/{profile_id}")
async def update_llm_profile(
    request: Request,
    profile_id: str,
    data: LlmProfileRequest,
    current_user: dict = Depends(get_current_user),
    store: ConfigStore = Depends(get_config_store),
    db: AdminDatabase = Depends(get_db),
) -> dict:
    """Update an existing LLM profile."""
    if not store.exists("llm", f"profile_{profile_id}"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile '{profile_id}' not found",
        )

    store.save_llm_profile(
        profile_id=profile_id,
        name=data.name,
        base_url=data.base_url,
        model=data.model,
        api_key=data.api_key if data.api_key else None,
    )

    # Audit log
    db.add_audit_log(
        action="llm_profile_update",
        username=current_user["username"],
        target=f"llm/profile/{profile_id}",
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        after_value=data.name,
    )

    reload_config("llm")

    return store.get_llm_profile(profile_id) or {"id": profile_id}


@router.delete("/llm/profiles/{profile_id}")
async def delete_llm_profile(
    request: Request,
    profile_id: str,
    current_user: dict = Depends(get_current_user),
    store: ConfigStore = Depends(get_config_store),
    db: AdminDatabase = Depends(get_db),
) -> dict:
    """Delete an LLM profile. Cannot delete the active profile."""
    if not store.delete_llm_profile(profile_id):
        active_id = store.get("llm", "active_profile")
        if profile_id == active_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能删除当前激活的配置方案，请先切换到其他方案",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile '{profile_id}' not found",
        )

    db.add_audit_log(
        action="llm_profile_delete",
        username=current_user["username"],
        target=f"llm/profile/{profile_id}",
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )

    reload_config("llm")

    return {"message": f"Profile '{profile_id}' deleted"}


@router.post("/llm/profiles/{profile_id}/activate")
async def activate_llm_profile(
    request: Request,
    profile_id: str,
    current_user: dict = Depends(get_current_user),
    store: ConfigStore = Depends(get_config_store),
    db: AdminDatabase = Depends(get_db),
) -> dict:
    """Activate an LLM profile."""
    if not store.set_active_llm_profile(profile_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile '{profile_id}' not found",
        )

    db.add_audit_log(
        action="llm_profile_activate",
        username=current_user["username"],
        target=f"llm/profile/{profile_id}",
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )

    reload_config("llm")

    return {"message": f"Profile '{profile_id}' activated", "active_profile": profile_id}


# =========================================================================
# Test endpoints (profile-specific BEFORE generic catch-all)
# =========================================================================


@router.post("/test/llm/{profile_id}", response_model=ConfigTestResponse)
async def test_llm_profile(
    profile_id: str,
    current_user: dict = Depends(get_current_user),
    store: ConfigStore = Depends(get_config_store),
) -> ConfigTestResponse:
    """Test connection for a specific LLM profile."""
    profile = store.get_llm_profile(profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile '{profile_id}' not found",
        )

    return await _test_llm_profile_config(profile, time.time())


@router.post(
    "/test/{category}",
    response_model=ConfigTestResponse,
    responses={400: {"model": ErrorResponse}},
)
async def test_config(
    category: Literal["llm", "langfuse"],
    current_user: dict = Depends(get_current_user),
    store: ConfigStore = Depends(get_config_store),
) -> ConfigTestResponse:
    """
    Test configuration connection.

    - **category**: Configuration category to test (llm or langfuse)

    Note: This endpoint only tests against allowed domains for SSRF protection.
    """
    start_time = time.time()

    try:
        if category == "llm":
            return await _test_llm_config(store, start_time)
        elif category == "langfuse":
            return await _test_langfuse_config(store, start_time)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot test category: {category}",
        )
    except HTTPException:
        raise
    except Exception as e:
        latency = (time.time() - start_time) * 1000
        return ConfigTestResponse(
            success=False,
            message=f"Test failed: {str(e)}",
            latency_ms=latency,
        )


# =========================================================================
# Generic category config endpoints (catch-all, must be LAST)
# =========================================================================


@router.get(
    "/{category}",
    response_model=dict,
)
async def get_category_config(
    category: Literal["llm", "langfuse", "image"],
    current_user: dict = Depends(get_current_user),
    store: ConfigStore = Depends(get_config_store),
) -> dict:
    """
    Get configuration for a specific category.

    - **category**: Configuration category (llm, langfuse, image)
    """
    if category == "llm":
        # Return active profile info for backward compatibility
        active = store.get_active_llm_config()
        if active:
            return {
                "openai_api_key": mask_value(active["api_key"]) if active.get("api_key") else None,
                "openai_base_url": active.get("base_url"),
                "openai_model": active.get("model", "gpt-4"),
                "configured": active.get("has_api_key", False),
                "active_profile": active.get("id"),
                "active_profile_name": active.get("name"),
            }
        return store.get_llm_config()
    elif category == "langfuse":
        return store.get_langfuse_config()
    elif category == "image":
        return store.get_image_config()

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unknown category: {category}",
    )


@router.put(
    "/{category}/{key}",
    responses={400: {"model": ErrorResponse}},
)
async def update_config(
    request: Request,
    category: Literal["llm", "langfuse", "image", "general", "discussion"],
    key: str,
    data: ConfigUpdateRequest,
    current_user: dict = Depends(get_current_user),
    store: ConfigStore = Depends(get_config_store),
    db: AdminDatabase = Depends(get_db),
) -> dict:
    """
    Update a configuration value.

    - **category**: Configuration category
    - **key**: Configuration key
    - **value**: New value
    - **encrypted**: Whether to encrypt the value
    """
    # Get old value for audit log
    old_value = store.get_masked(category, key)

    # Set new value
    store.set(category, key, data.value, encrypted=data.encrypted)

    # Reload config for hot update
    reload_config(category)

    # Reset discussion semaphore if discussion config changed
    if category == "discussion":
        try:
            from src.api.routes.discussion import reset_discussion_semaphore
            reset_discussion_semaphore()
        except Exception:
            pass

    # Log the change
    new_masked = mask_value(data.value) if data.encrypted else data.value
    db.add_audit_log(
        action="config_update",
        username=current_user["username"],
        target=f"{category}/{key}",
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        before_value=old_value,
        after_value=new_masked,
    )

    return {"message": f"Configuration {category}/{key} updated"}


@router.delete(
    "/{category}/{key}",
    responses={404: {"model": ErrorResponse}},
)
async def delete_config(
    request: Request,
    category: Literal["llm", "langfuse", "image", "general", "discussion"],
    key: str,
    current_user: dict = Depends(get_current_user),
    store: ConfigStore = Depends(get_config_store),
    db: AdminDatabase = Depends(get_db),
) -> dict:
    """
    Delete a configuration.

    - **category**: Configuration category
    - **key**: Configuration key
    """
    # Get old value for audit log
    old_value = store.get_masked(category, key)

    if not store.delete(category, key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration {category}/{key} not found",
        )

    # Reload config for hot update
    reload_config(category)

    # Log the deletion
    db.add_audit_log(
        action="config_delete",
        username=current_user["username"],
        target=f"{category}/{key}",
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        before_value=old_value,
    )

    return {"message": f"Configuration {category}/{key} deleted"}


# =========================================================================
# Internal test helpers
# =========================================================================


async def _test_llm_config(store: ConfigStore, start_time: float) -> ConfigTestResponse:
    """Test LLM (OpenAI) configuration."""
    import httpx

    api_key = store.get_raw("llm", "openai_api_key")
    if not api_key:
        return ConfigTestResponse(
            success=False,
            message="OpenAI API key not configured",
            latency_ms=0,
        )

    base_url = store.get_raw("llm", "openai_base_url") or "https://api.openai.com/v1"

    # Validate domain for SSRF protection
    if not validate_domain(base_url):
        return ConfigTestResponse(
            success=False,
            message=f"Domain not allowed for testing: {base_url}",
            latency_ms=0,
        )

    # Normalize base_url: remove trailing slash, user should provide full path (e.g., .../v1)
    base_url = base_url.rstrip("/")
    models_url = f"{base_url}/models"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                models_url,
                headers={"Authorization": f"Bearer {api_key}"},
            )

        latency = (time.time() - start_time) * 1000

        if response.status_code == 200:
            return ConfigTestResponse(
                success=True,
                message="OpenAI API connection successful",
                latency_ms=latency,
            )
        elif response.status_code == 401:
            return ConfigTestResponse(
                success=False,
                message="Invalid API key",
                latency_ms=latency,
            )
        else:
            return ConfigTestResponse(
                success=False,
                message=f"API returned status {response.status_code}",
                latency_ms=latency,
            )
    except httpx.TimeoutException:
        latency = (time.time() - start_time) * 1000
        return ConfigTestResponse(
            success=False,
            message="Connection timeout",
            latency_ms=latency,
        )


async def _test_langfuse_config(
    store: ConfigStore, start_time: float
) -> ConfigTestResponse:
    """Test Langfuse configuration."""
    import httpx
    import base64

    public_key = store.get_raw("langfuse", "public_key")
    secret_key = store.get_raw("langfuse", "secret_key")
    host = store.get_raw("langfuse", "host") or "https://cloud.langfuse.com"

    if not public_key or not secret_key:
        return ConfigTestResponse(
            success=False,
            message="Langfuse keys not configured",
            latency_ms=0,
        )

    # Validate domain for SSRF protection
    if not validate_domain(host):
        return ConfigTestResponse(
            success=False,
            message=f"Domain not allowed for testing: {host}",
            latency_ms=0,
        )

    try:
        # Create basic auth header
        credentials = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()

        async with httpx.AsyncClient(timeout=10.0) as client:
            # Use /api/public/sessions endpoint which requires authentication
            # /api/public/health doesn't require auth and always returns 200
            response = await client.get(
                f"{host}/api/public/sessions",
                headers={"Authorization": f"Basic {credentials}"},
                params={"limit": 1},  # Minimal query to reduce load
            )

        latency = (time.time() - start_time) * 1000

        if response.status_code == 200:
            return ConfigTestResponse(
                success=True,
                message="Langfuse 连接成功，凭证有效",
                latency_ms=latency,
            )
        elif response.status_code == 401:
            return ConfigTestResponse(
                success=False,
                message="Langfuse 凭证无效，请检查密钥是否与所选区域匹配",
                latency_ms=latency,
            )
        elif response.status_code == 403:
            return ConfigTestResponse(
                success=False,
                message="Langfuse 凭证无权限，请检查 API 密钥权限",
                latency_ms=latency,
            )
        else:
            return ConfigTestResponse(
                success=False,
                message=f"Langfuse 返回状态码 {response.status_code}",
                latency_ms=latency,
            )
    except httpx.TimeoutException:
        latency = (time.time() - start_time) * 1000
        return ConfigTestResponse(
            success=False,
            message="Connection timeout",
            latency_ms=latency,
        )


async def _test_llm_profile_config(
    profile: dict, start_time: float
) -> ConfigTestResponse:
    """Test LLM connection using a profile's config."""
    import httpx

    api_key = profile.get("api_key")
    if not api_key:
        return ConfigTestResponse(
            success=False,
            message="API Key 未配置",
            latency_ms=0,
        )

    base_url = profile.get("base_url") or "https://api.openai.com/v1"

    if not validate_domain(base_url):
        return ConfigTestResponse(
            success=False,
            message=f"Domain not allowed for testing: {base_url}",
            latency_ms=0,
        )

    base_url = base_url.rstrip("/")
    models_url = f"{base_url}/models"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                models_url,
                headers={"Authorization": f"Bearer {api_key}"},
            )

        latency = (time.time() - start_time) * 1000

        if response.status_code == 200:
            return ConfigTestResponse(
                success=True,
                message=f"连接成功 ({profile.get('name', '')})",
                latency_ms=latency,
            )
        elif response.status_code == 401:
            return ConfigTestResponse(
                success=False,
                message="API Key 无效",
                latency_ms=latency,
            )
        else:
            return ConfigTestResponse(
                success=False,
                message=f"API 返回状态码 {response.status_code}",
                latency_ms=latency,
            )
    except httpx.TimeoutException:
        latency = (time.time() - start_time) * 1000
        return ConfigTestResponse(
            success=False,
            message="连接超时",
            latency_ms=latency,
        )


# ===========================================================================
# Stage moderator config
# ===========================================================================

VALID_MODERATOR_ROLES = {
    "lead_planner", "creative_director", "system_designer", "number_designer",
    "visual_concept", "market_director", "operations_analyst", "player_advocate",
    "tech_director",
}


class StageModeratorsResponse(BaseModel):
    moderators: dict  # template_id -> role_name


class SetStageModeratorRequest(BaseModel):
    role: str


@router.get("/stage-moderators", response_model=StageModeratorsResponse)
async def get_stage_moderators(
    config_store: ConfigStore = Depends(get_config_store),
    user: dict = Depends(get_current_user),
):
    """Get moderator role for each stage template."""
    return StageModeratorsResponse(moderators=config_store.get_stage_moderators())


@router.put("/stage-moderators/{template_id}")
async def set_stage_moderator(
    template_id: str,
    body: SetStageModeratorRequest,
    request: Request,
    config_store: ConfigStore = Depends(get_config_store),
    user: dict = Depends(get_current_user),
):
    """Set moderator role for a stage template."""
    if body.role not in VALID_MODERATOR_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Valid: {sorted(VALID_MODERATOR_ROLES)}")
    config_store.set_stage_moderator(template_id, body.role)
    return {"ok": True, "template_id": template_id, "role": body.role}
