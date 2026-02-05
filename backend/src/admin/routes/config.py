"""
Admin configuration API routes.
"""

import time
from typing import Literal, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, status

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


@router.get(
    "",
    response_model=list[dict],
)
async def get_all_configs(
    category: Optional[Literal["llm", "langfuse", "image", "general"]] = None,
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

    return ConfigStatusResponse(
        llm_configured=llm_config.get("configured", False),
        langfuse_configured=langfuse_config.get("configured", False),
        langfuse_enabled=langfuse_config.get("enabled", False),
        image_configured=any(
            p.get("configured") for p in image_config.get("providers", {}).values()
        ),
        default_image_provider=image_config.get("default_provider"),
    )


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
    category: Literal["llm", "langfuse", "image", "general"],
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
    category: Literal["llm", "langfuse", "image", "general"],
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
            response = await client.get(
                f"{host}/api/public/health",
                headers={"Authorization": f"Basic {credentials}"},
            )

        latency = (time.time() - start_time) * 1000

        if response.status_code == 200:
            return ConfigTestResponse(
                success=True,
                message="Langfuse connection successful",
                latency_ms=latency,
            )
        elif response.status_code == 401:
            return ConfigTestResponse(
                success=False,
                message="Invalid Langfuse credentials",
                latency_ms=latency,
            )
        else:
            return ConfigTestResponse(
                success=False,
                message=f"Langfuse returned status {response.status_code}",
                latency_ms=latency,
            )
    except httpx.TimeoutException:
        latency = (time.time() - start_time) * 1000
        return ConfigTestResponse(
            success=False,
            message="Connection timeout",
            latency_ms=latency,
        )
