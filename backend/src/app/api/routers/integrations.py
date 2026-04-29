from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db, require_any_user, require_domain_admin
from app.schemas.integrations import (
    GithubActionsWebhookPayload,
    GithubWebhookAck,
    MCPConnectionBundleListResponse,
    MCPServerListResponse,
    OpenAIChatRequest,
    OpenAIChatResponse,
)
from app.services.github_actions_service import handle_github_actions_webhook
from app.services.integration_catalog_service import list_repo_connection_bundles
from app.services.openai_chat_service import request_openai_chat

router = APIRouter()


@router.post("/github/actions/webhook", response_model=GithubWebhookAck, include_in_schema=False)
def github_actions_webhook(
    payload: GithubActionsWebhookPayload,
    db=Depends(get_db),
    admin=Depends(require_domain_admin),
):
    # For the skeleton, we protect this route with admin auth.
    # Later, replace with GitHub webhook signature verification.
    return handle_github_actions_webhook(db, payload)


@router.post("/openai/chat", response_model=OpenAIChatResponse)
def openai_chat(
    payload: OpenAIChatRequest,
    user=Depends(require_any_user),
):
    return request_openai_chat(payload)


@router.get("/mcp/servers", response_model=MCPServerListResponse)
def list_mcp_servers(user=Depends(require_any_user)):
    try:
        from control_center.registry import RegistryManager
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load MCP registry: {exc}") from exc

    manager = RegistryManager()
    items = [
        {
            "name": name,
            "display_name": server.display_name or name,
            "description": server.description,
            "tags": server.tags,
            "allowed_environments": server.allowed_environments,
            "active": server.active,
        }
        for name, server in manager.get_available_servers().items()
    ]
    return {"items": sorted(items, key=lambda item: item["name"])}


@router.get("/mcp/repo-bundles", response_model=MCPConnectionBundleListResponse)
def list_mcp_repo_bundles(
    environment: str = "dev",
    user=Depends(require_any_user),
):
    return list_repo_connection_bundles(environment=environment)
