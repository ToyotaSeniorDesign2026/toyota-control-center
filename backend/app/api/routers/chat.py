"""Chat API router for handling AI chat messages."""

import logging
import os
import re
from typing import Optional, Any
from fastapi import APIRouter, HTTPException, Depends
import httpx
from pydantic import BaseModel

from app.api.deps import get_db
from app.services.chat_service import get_chat_service
from app.services.field_extraction_service import get_field_extraction_service
from app.services.chat_job_service import maybe_run_sql_job_from_chat, run_resource_by_id
from app.services.chat_mcp_service import (
    needs_github_personal_access_token,
    run_prompt_native_mcp,
    should_run_prompt_native_mcp,
)

router = APIRouter()
logger = logging.getLogger(__name__)
SQL_RUN_REQUEST_PATTERN = re.compile(r"\b(run|execute|launch|trigger|start)\b", re.IGNORECASE)
RUN_JOB_MARKER_PATTERN = re.compile(r'\[RUN_JOB:([a-zA-Z0-9\-_]+)\]')
SQL_RUN_CONTEXT_PATTERN = re.compile(r"\b(job|sql|query|resource)\b", re.IGNORECASE)
AFFIRMATIVE_RUN_RESPONSE_PATTERN = re.compile(r"^(yes|yep|yeah|sure|please do|go ahead|run it|run now|do it)[\s.!?]*$", re.IGNORECASE)
REPO_CONNECTION_REQUEST_PATTERN = re.compile(r"\b(connect|link|attach|add)\b.*\b(github|repo|repository)\b|\b(github|repo|repository)\b.*\b(connect|link|attach|add)\b", re.IGNORECASE)
REPO_SLUG_PATTERN = re.compile(r"(?:github\.com[/:])?([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?(?=$|[\s/#?])", re.IGNORECASE)
REPO_REF_PATTERN = re.compile(r"\b(?:branch|ref)\s+([A-Za-z0-9._/-]+)\b", re.IGNORECASE)
REPO_PATH_PATTERN = re.compile(r"\b(?:path|folder|directory)\s+([^\s,]+)", re.IGNORECASE)
GITHUB_REPO_OPTIONS_LIMIT = 12


def _should_extract_fields(request: "ChatRequest", job_creation_intent: bool) -> bool:
    if not job_creation_intent:
        return True

    message = (request.message or "").lower()
    draft = request.current_draft_data or {}
    draft_type = str(draft.get("job_type", "")).strip().lower()

    sql_keywords = ("sql", "query", "run", "execute", "launch", "trigger")
    if draft_type == "sql":
        return True
    if any(keyword in message for keyword in sql_keywords):
        return True
    return False


def _has_sql_draft(request: "ChatRequest") -> bool:
    draft = request.current_draft_data or {}
    draft_type = str(draft.get("job_type", "")).strip().lower()
    return draft_type == "sql"


def _is_explicit_sql_run_request(request: "ChatRequest") -> bool:
    message = request.message or ""
    draft = request.current_draft_data or {}
    if not _has_sql_draft(request):
        return False
    if draft.get("resource_id") and AFFIRMATIVE_RUN_RESPONSE_PATTERN.search(message.strip()):
        return True
    return bool(SQL_RUN_REQUEST_PATTERN.search(message) and SQL_RUN_CONTEXT_PATTERN.search(message))


def _deterministic_sql_fields(request: "ChatRequest") -> dict[str, Any]:
    message = (request.message or "").strip().lower()
    draft = request.current_draft_data or {}
    if str(draft.get("job_type", "")).strip().lower() != "sql":
        return {}

    fields: dict[str, Any] = {}

    if message in {"looks good", "that looks good", "yes", "yes looks good", "use it", "that works"}:
        previous_query = (
            draft.get("query")
            or (draft.get("config") if isinstance(draft.get("config"), dict) else {}).get("query")
            or (draft.get("params") if isinstance(draft.get("params"), dict) else {}).get("query")
        )
        if previous_query:
            fields["query"] = previous_query

    if "runs" in message and ("database" in message or "control-center" in message or "control center" in message):
        fields.update(
            {
                "job_type": "SQL",
                "connector": "sql-dab",
                "connection_id": "postgres",
                "query": "SELECT * FROM runs;",
            }
        )

    if "manual" in message and SQL_RUN_REQUEST_PATTERN.search(message) is not None:
        fields["run_type"] = "manual"

    if "create" in message and "job" in message:
        fields["creation_requested"] = True

    return fields


def _deterministic_repo_connection_fields(request: "ChatRequest") -> dict[str, Any]:
    message = (request.message or "").strip()
    if not message:
        return {}

    if REPO_CONNECTION_REQUEST_PATTERN.search(message) is None:
        return {}

    repo_match = REPO_SLUG_PATTERN.search(message)
    if repo_match is None:
        return {"connection_intent": "connect_repo", "connector": "github", "provider": "github"}

    repo = repo_match.group(1).rstrip("/")
    ref_match = REPO_REF_PATTERN.search(message)
    path_match = REPO_PATH_PATTERN.search(message)
    repo_name = repo.split("/")[-1]

    fields: dict[str, Any] = {
        "connection_intent": "connect_repo",
        "name": repo_name,
        "kind": "runtime",
        "type": "repo_connection",
        "connector": "github",
        "repo": repo,
        "provider": "github",
        "server_names": ["github"],
    }
    if ref_match is not None:
        fields["ref"] = ref_match.group(1)
    if path_match is not None:
        fields["path"] = path_match.group(1)
    return fields


class ChatMessage(BaseModel):
    """A single chat message."""
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """Request to send a chat message."""
    message: str
    conversation_history: Optional[list[ChatMessage]] = None
    model: Optional[str] = None
    current_draft_data: Optional[dict[str, Any]] = None  # Current job draft state
    available_resources: Optional[list[dict[str, Any]]] = None
    github_personal_access_token: Optional[str] = None


class SecretRequest(BaseModel):
    kind: str
    prompt: str
    submit_label: Optional[str] = None


class RepositoryOption(BaseModel):
    full_name: str
    owner: str
    name: str
    default_branch: str | None = None
    private: bool = False


class ChatResponse(BaseModel):
    """Response from chat API."""
    response: str
    job_creation_intent: Optional[bool] = None  # True if user wants to create a job
    extracted_fields: Optional[dict[str, Any]] = None  # Extracted job fields from message
    resource_id: Optional[str] = None
    run_id: Optional[str] = None
    run_status: Optional[str] = None
    sql_job_executed: Optional[bool] = None
    mcp_tool_executed: Optional[bool] = None
    mcp_servers: Optional[list[str]] = None
    mcp_tool_executions: Optional[list[dict[str, Any]]] = None
    secret_request: Optional[SecretRequest] = None
    repository_options: Optional[list[RepositoryOption]] = None


async def _list_github_repository_options(personal_access_token: str) -> list[RepositoryOption]:
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {personal_access_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    params = {
        "sort": "updated",
        "per_page": str(GITHUB_REPO_OPTIONS_LIMIT),
        "affiliation": "owner,collaborator,organization_member",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get("https://api.github.com/user/repos", headers=headers, params=params)
        response.raise_for_status()
        payload = response.json()

    if not isinstance(payload, list):
        return []

    options: list[RepositoryOption] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        full_name = str(item.get("full_name") or "").strip()
        owner = str((item.get("owner") or {}).get("login") or "").strip()
        name = str(item.get("name") or "").strip()
        if not full_name or not owner or not name:
            continue
        options.append(
            RepositoryOption(
                full_name=full_name,
                owner=owner,
                name=name,
                default_branch=str(item.get("default_branch") or "").strip() or None,
                private=bool(item.get("private", False)),
            )
        )
    return options


@router.post("/send", response_model=ChatResponse)
async def send_chat_message(request: ChatRequest, db=Depends(get_db)) -> ChatResponse:
    """
    Send a message to the AI chat assistant.
    
    Args:
        request: Chat request with message and optional conversation history
        
    Returns:
        AI assistant response with optional job creation intent and extracted fields
    """
    try:
        if not request.message or not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        
        # Detect job creation intent from user message
        job_creation_intent = detect_job_creation_intent(request.message)
        deterministic_repo_fields = _deterministic_repo_connection_fields(request)
        github_token = request.github_personal_access_token or os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")

        if deterministic_repo_fields.get("connection_intent") == "connect_repo" and not github_token:
            return ChatResponse(
                response=(
                    "I can help connect a GitHub repository, but I need a GitHub personal access token "
                    "for this live MCP session first."
                ),
                job_creation_intent=True,
                extracted_fields=None,
                secret_request=SecretRequest(
                    kind="github_personal_access_token",
                    prompt="Enter a GitHub personal access token to browse and connect repositories for this session.",
                    submit_label="Use token",
                ),
            )

        if (
            deterministic_repo_fields.get("connection_intent") == "connect_repo"
            and not deterministic_repo_fields.get("repo")
            and github_token
        ):
            try:
                repository_options = await _list_github_repository_options(github_token)
            except httpx.HTTPError as exc:
                logger.warning("Unable to list GitHub repositories for chat repo connection: %s", exc)
                raise HTTPException(
                    status_code=502,
                    detail="Unable to load repositories from GitHub with the provided token.",
                ) from exc

            return ChatResponse(
                response=(
                    "I found repositories available through that token. Choose one below and I’ll connect it "
                    "as a reusable GitHub repo resource."
                ),
                job_creation_intent=True,
                extracted_fields=None,
                repository_options=repository_options,
            )

        preflight_sql_job_result = None
        if _is_explicit_sql_run_request(request):
            preflight_sql_job_result = maybe_run_sql_job_from_chat(
                db,
                message=request.message,
                extracted_fields=None,
                current_draft=request.current_draft_data,
            )
        if preflight_sql_job_result is not None:
            return ChatResponse(
                response=preflight_sql_job_result.message,
                job_creation_intent=job_creation_intent,
                extracted_fields=None,
                resource_id=preflight_sql_job_result.resource_id,
                run_id=preflight_sql_job_result.run_id,
                run_status=preflight_sql_job_result.run_status,
                sql_job_executed=preflight_sql_job_result.executed,
            )

        if should_run_prompt_native_mcp(request.message, request.current_draft_data):
            if needs_github_personal_access_token(
                request.message,
                request.current_draft_data,
                supplied_token=request.github_personal_access_token,
            ):
                return ChatResponse(
                    response=(
                        "I can do that, but I need a GitHub personal access token for this live "
                        "GitHub MCP session. Enter it in the secure token field and I will use "
                        "it only for this request."
                    ),
                    job_creation_intent=False,
                    extracted_fields=None,
                    secret_request=SecretRequest(
                        kind="github_personal_access_token",
                        prompt="Enter a GitHub personal access token for this live MCP session.",
                        submit_label="Use token",
                    ),
                )

            server_env_overrides = None
            if request.github_personal_access_token:
                server_env_overrides = {
                    "github": {
                        "GITHUB_PERSONAL_ACCESS_TOKEN": request.github_personal_access_token,
                    }
                }
            mcp_result = await run_prompt_native_mcp(
                message=request.message,
                environment=str((request.current_draft_data or {}).get("target_environment") or (request.current_draft_data or {}).get("environment") or "dev"),
                model=request.model,
                server_env_overrides=server_env_overrides,
            )
            return ChatResponse(
                response=mcp_result.response,
                job_creation_intent=False,
                extracted_fields=None,
                mcp_tool_executed=True,
                mcp_servers=mcp_result.server_names,
                mcp_tool_executions=mcp_result.tool_executions,
            )
        
        # Convert conversation history to dict format if provided
        history = None
        if request.conversation_history:
            history = [{"role": msg.role, "content": msg.content} for msg in request.conversation_history]
        
        chat_service = get_chat_service()
        response = await chat_service.send_message(
            message=request.message,
            conversation_history=history,
            model=request.model,
            current_draft=request.current_draft_data,
            available_resources=request.available_resources,
        )
        
        # Handle [RUN_JOB:resource_id] marker emitted by the LLM
        run_marker_match = RUN_JOB_MARKER_PATTERN.search(response)
        if run_marker_match:
            resource_id_to_run = run_marker_match.group(1)
            clean_response = RUN_JOB_MARKER_PATTERN.sub("", response).strip()
            run_result = run_resource_by_id(db, resource_id_to_run)
            final_response = f"{clean_response}\n\n{run_result.message}".strip()
            return ChatResponse(
                response=final_response,
                job_creation_intent=job_creation_intent,
                extracted_fields=None,
                resource_id=run_result.resource_id,
                run_id=run_result.run_id,
                run_status=run_result.run_status,
                sql_job_executed=run_result.executed,
            )

        # Extract job fields unless this is only a generic create-job opener with no
        # concrete details yet. SQL/run-style chat requests still need extraction.
        extracted_fields = {
            **deterministic_repo_fields,
            **_deterministic_sql_fields(request),
        }
        if _should_extract_fields(request, job_creation_intent):
            extraction_service = get_field_extraction_service()
            llm_fields = await extraction_service.extract_fields(
                user_message=request.message,
                conversation_history=history,
                current_draft=request.current_draft_data,
                model=request.model
            )
            extracted_fields = {**(llm_fields or {}), **extracted_fields}
            # Only include extracted_fields if there are any
            if not extracted_fields:
                extracted_fields = None

        sql_job_result = maybe_run_sql_job_from_chat(
            db,
            message=request.message,
            extracted_fields=extracted_fields,
            current_draft=request.current_draft_data,
        )
        if sql_job_result is not None:
            response = f"{response}\n\n{sql_job_result.message}"
        
        return ChatResponse(
            response=response,
            job_creation_intent=job_creation_intent,
            extracted_fields=extracted_fields,
            resource_id=sql_job_result.resource_id if sql_job_result is not None else None,
            run_id=sql_job_result.run_id if sql_job_result is not None else None,
            run_status=sql_job_result.run_status if sql_job_result is not None else None,
            sql_job_executed=sql_job_result.executed if sql_job_result is not None else None,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled chat error")
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


def detect_job_creation_intent(user_message: str) -> bool:
    """
    Detect if user is expressing intent to create a job.
    
    Args:
        user_message: The user's input message
        
    Returns:
        True if job creation intent is detected, False otherwise
    """
    message_lower = user_message.lower().strip()
    
    # Keywords that indicate job creation intent
    creation_keywords = [
        "create",
        "new job",
        "sql job",
        "start a job",
        "build a job",
        "set up a job",
        "make a job",
        "add a job",
        "design a job",
    ]
    
    # Check if message contains creation-related keywords
    for keyword in creation_keywords:
        if keyword in message_lower:
            # Also check that it's about a job
            if "job" in message_lower or "workflow" in message_lower:
                return True
    
    return False
