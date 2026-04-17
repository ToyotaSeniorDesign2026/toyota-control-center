"""Chat API router for handling AI chat messages."""

import logging
import os
import re
import base64
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
SQL_CONNECT_REQUEST_PATTERN = re.compile(
    r"\b(sql|database|postgres|postgresql|mysql|snowflake|redshift|bigquery)\b.*\b(connect|connection|query|run|execute|select|insert|update|delete)\b|\b(connect|connection|query|run|execute|select|insert|update|delete)\b.*\b(sql|database|postgres|postgresql|mysql|snowflake|redshift|bigquery)\b",
    re.IGNORECASE,
)
ENV_VAR_NAME_PATTERN = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")
REPO_ENV_DISCOVERY_FILES = [
    ".env.example",
    ".env",
    "backend/.env.example",
    "backend/.env",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "README.md",
]
SQL_SESSION_ENV_FIELDS = [
    {
        "key": "SQL_DB_HOST",
        "label": "Database host",
        "placeholder": "localhost",
        "secret": False,
        "required": True,
        "group": "sql_connection_string",
    },
    {
        "key": "SQL_DB_PORT",
        "label": "Database port",
        "placeholder": "5432",
        "secret": False,
        "required": True,
        "group": "sql_connection_string",
    },
    {
        "key": "SQL_DB_DATABASE",
        "label": "Database name",
        "placeholder": "control_center",
        "secret": False,
        "required": True,
        "group": "sql_connection_string",
    },
    {
        "key": "SQL_DB_USERNAME",
        "label": "Database username",
        "placeholder": "postgres",
        "secret": False,
        "required": True,
        "group": "sql_connection_string",
    },
    {
        "key": "SQL_DB_PASSWORD",
        "label": "Database password",
        "placeholder": "Password",
        "secret": True,
        "required": True,
        "group": "sql_connection_string",
    },
    {
        "key": "SQL_CONNECTION_ID",
        "label": "Connection ID",
        "placeholder": "postgres",
        "secret": False,
        "required": False,
    },
]
SQL_REQUIRED_JOB_FIELDS = [
    ("job_name", "job/resource name"),
    ("owner", "owner"),
    ("target_environment", "target environment"),
    ("run_type", "run type"),
]


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
                "query": "SELECT * FROM runs;",
            }
        )

    if "manual" in message and SQL_RUN_REQUEST_PATTERN.search(message) is not None:
        fields["run_type"] = "manual"

    if "create" in message and SQL_RUN_REQUEST_PATTERN.search(message) is not None:
        fields["creation_requested"] = True
        fields["run_after_create"] = True
        fields["action"] = "run"

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
    session_env: Optional[dict[str, str]] = None


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


class ConfigRequestField(BaseModel):
    key: str
    label: str
    placeholder: str | None = None
    secret: bool = False
    required: bool = True
    group: str | None = None


class ConfigRequest(BaseModel):
    kind: str
    prompt: str
    submit_label: Optional[str] = None
    fields: list[ConfigRequestField]
    repository_hints: Optional[list[str]] = None


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
    config_request: Optional[ConfigRequest] = None


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


def _looks_like_sql_connect_request(request: "ChatRequest") -> bool:
    message = request.message or ""
    draft = request.current_draft_data or {}
    draft_type = str(draft.get("job_type") or draft.get("type") or "").strip().lower()
    if draft_type == "sql":
        return True
    return SQL_CONNECT_REQUEST_PATTERN.search(message) is not None


def _effective_session_env(request: "ChatRequest") -> dict[str, str]:
    session_env = request.session_env or {}
    return {str(key): str(value) for key, value in session_env.items() if str(value).strip()}


def _build_sql_connection_string(session_env: dict[str, str]) -> str | None:
    host = session_env.get("SQL_DB_HOST")
    port = session_env.get("SQL_DB_PORT")
    database = session_env.get("SQL_DB_DATABASE")
    username = session_env.get("SQL_DB_USERNAME")
    password = session_env.get("SQL_DB_PASSWORD")
    if not all([host, port, database, username, password]):
        return None
    return f"Host={host};Port={port};Database={database};Username={username};Password={password}"


def _missing_sql_session_env(session_env: dict[str, str]) -> list[ConfigRequestField]:
    missing: list[ConfigRequestField] = []
    derived_connection_string = _build_sql_connection_string(session_env)
    for field in SQL_SESSION_ENV_FIELDS:
        key = field["key"]
        if session_env.get(key):
            continue
        if field.get("group") == "sql_connection_string" and derived_connection_string:
            continue
        missing.append(ConfigRequestField(**field))
    return missing


def _merge_sql_fields(
    extracted_fields: dict[str, Any] | None,
    current_draft: dict[str, Any] | None,
) -> dict[str, Any]:
    draft = current_draft or {}
    merged: dict[str, Any] = {
        **draft,
        **(extracted_fields or {}),
    }
    draft_config = draft.get("config") if isinstance(draft.get("config"), dict) else {}
    extracted_config = extracted_fields.get("config") if isinstance((extracted_fields or {}).get("config"), dict) else {}
    merged["config"] = {
        **draft_config,
        **extracted_config,
    }
    draft_params = draft.get("params") if isinstance(draft.get("params"), dict) else {}
    extracted_params = extracted_fields.get("params") if isinstance((extracted_fields or {}).get("params"), dict) else {}
    merged["params"] = {
        **draft_params,
        **extracted_params,
    }
    return merged


def _missing_sql_job_fields(
    extracted_fields: dict[str, Any],
    current_draft: dict[str, Any] | None,
) -> list[str]:
    merged = _merge_sql_fields(extracted_fields, current_draft)
    config = merged.get("config") if isinstance(merged.get("config"), dict) else {}

    missing: list[str] = []
    job_name = str(merged.get("job_name") or merged.get("name") or "").strip()
    owner = str(merged.get("owner") or "").strip()
    target_environment = str(
        merged.get("target_environment") or merged.get("environment") or config.get("target_environment") or ""
    ).strip()
    run_type = str(merged.get("run_type") or "").strip().lower()
    schedule = str(merged.get("schedule") or config.get("schedule") or "").strip()

    if not job_name:
        missing.append("job_name")
    if not owner:
        missing.append("owner")
    if not target_environment:
        missing.append("target_environment")
    if not run_type:
        missing.append("run_type")
    if run_type == "scheduled" and not schedule:
        missing.append("schedule")
    return missing


def _sql_followup_response(
    request: "ChatRequest",
    extracted_fields: dict[str, Any],
    session_env: dict[str, str],
) -> str | None:
    if not _looks_like_sql_connect_request(request) or not session_env:
        return None

    derived_connection_string = _build_sql_connection_string(session_env)
    if not derived_connection_string:
        return None

    merged = _merge_sql_fields(extracted_fields, request.current_draft_data)
    query = (
        str(merged.get("query") or "").strip()
        or str((merged.get("config") or {}).get("query") or "").strip()
        or str((merged.get("params") or {}).get("query") or "").strip()
    )
    connection_id = str(merged.get("connection_id") or session_env.get("SQL_CONNECTION_ID") or "").strip()

    if query:
        missing_job_fields = _missing_sql_job_fields(extracted_fields, request.current_draft_data)
        if missing_job_fields:
            next_field = missing_job_fields[0]
            if next_field == "job_name":
                return (
                    "I have the database connection details and the SQL query for this session using `sql-dab`. "
                    f"{'I also have connection ID `' + connection_id + '`. ' if connection_id else ''}"
                    "Next I need the job/resource name you want to save and run this SQL job as."
                )
            if next_field == "owner":
                return (
                    "I have the SQL connection details, query, and job name. "
                    "Next I need the owner for this SQL job."
                )
            if next_field == "target_environment":
                return (
                    "I have the SQL connection details, query, job name, and owner. "
                    "Next I need the target environment for this job, like `dev`, `staging`, or `prod`."
                )
            if next_field == "run_type":
                return (
                    "I have the SQL connection details, query, job name, owner, and target environment. "
                    "Should this run type be `manual`, `scheduled`, or `triggered`?"
                )
            if next_field == "schedule":
                return (
                    "This SQL job is marked as scheduled, so I also need the schedule expression or natural-language timing."
                )

        return (
            "I have the database connection details for this session and will use the `sql-dab` connector. "
            f"{'I also have connection ID `' + connection_id + '`. ' if connection_id else ''}"
            "I also have the query and required job fields. Do you want me to create the job and run it now?"
        )

    return (
        "I have the database connection details for this session and will use the `sql-dab` connector. "
        f"{'I also have connection ID `' + connection_id + '`. ' if connection_id else ''}"
        "The next thing I need is the SQL query you want to run."
    )


async def _read_github_repo_file(
    *,
    repo: str,
    path: str,
    ref: str | None,
    personal_access_token: str,
) -> str | None:
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {personal_access_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    params = {"ref": ref} if ref else None
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"https://api.github.com/repos/{repo}/contents/{path}",
            headers=headers,
            params=params,
        )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("type") != "file":
        return None
    encoded = payload.get("content")
    if not isinstance(encoded, str) or not encoded.strip():
        return None
    try:
        return base64.b64decode(encoded).decode("utf-8", errors="ignore")
    except Exception:
        return None


async def _discover_repository_env_hints(
    available_resources: list[dict[str, Any]] | None,
    personal_access_token: str | None,
) -> list[str]:
    if not personal_access_token or not available_resources:
        return []

    hints: list[str] = []
    for resource in available_resources:
        if not isinstance(resource, dict):
            continue
        resource_type = str(resource.get("type") or "").strip().lower()
        connector = str(resource.get("connector") or "").strip().lower()
        config = resource.get("config") if isinstance(resource.get("config"), dict) else {}
        repo = str(config.get("repo") or "").strip()
        if not repo or (resource_type != "repo_connection" and connector != "github"):
            continue

        ref = str(config.get("ref") or config.get("default_branch") or "").strip() or None
        candidate_paths = list(REPO_ENV_DISCOVERY_FILES)
        repo_path = str(config.get("path") or "").strip().strip("/")
        if repo_path:
            candidate_paths = [f"{repo_path}/{candidate}" for candidate in REPO_ENV_DISCOVERY_FILES] + candidate_paths

        for candidate_path in candidate_paths[:8]:
            try:
                content = await _read_github_repo_file(
                    repo=repo,
                    path=candidate_path,
                    ref=ref,
                    personal_access_token=personal_access_token,
                )
            except httpx.HTTPError:
                continue
            if not content:
                continue
            env_names = {match.group(0) for match in ENV_VAR_NAME_PATTERN.finditer(content)}
            matched = [
                name
                for name in [
                    "SQL_CONNECTION_STRING",
                    "SQL_DB_HOST",
                    "SQL_DB_PORT",
                    "SQL_DB_DATABASE",
                    "SQL_DB_USERNAME",
                    "SQL_DB_PASSWORD",
                ]
                if name in env_names
            ]
            if matched:
                hints.append(f"{repo}:{' @ ' + ref if ref else ''} {candidate_path} includes {', '.join(matched)}")
                break
        if len(hints) >= 3:
            break

    return hints


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
        session_env = _effective_session_env(request)

        if _looks_like_sql_connect_request(request):
            missing_sql_env = _missing_sql_session_env(session_env)
            if missing_sql_env:
                repo_hints = await _discover_repository_env_hints(request.available_resources, github_token)
                return ChatResponse(
                    response=(
                        "I can help connect to a SQL database and run that query, but I first need the database "
                        "connection details for this live session."
                    ),
                    job_creation_intent=True,
                    extracted_fields=None,
                    config_request=ConfigRequest(
                        kind="sql_session_env",
                        prompt=(
                            "Enter the SQL database connection details for this session. "
                            "The SQL MCP server itself is already configured; I only need the target database details."
                        ),
                        submit_label="Use SQL settings",
                        fields=missing_sql_env,
                        repository_hints=repo_hints or None,
                    ),
                )

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
                server_names=["sql-dab"] if _looks_like_sql_connect_request(request) else None,
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
        sql_flow_active = _has_sql_draft(request) or _looks_like_sql_connect_request(request)
        run_marker_match = RUN_JOB_MARKER_PATTERN.search(response)
        if run_marker_match:
            resource_id_to_run = run_marker_match.group(1)
            clean_response = RUN_JOB_MARKER_PATTERN.sub("", response).strip()
            if not sql_flow_active:
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
            response = clean_response

        # Extract job fields unless this is only a generic create-job opener with no
        # concrete details yet. SQL/run-style chat requests still need extraction.
        extracted_fields = {
            **deterministic_repo_fields,
            **_deterministic_sql_fields(request),
        }
        if _looks_like_sql_connect_request(request) and session_env:
            derived_connection_string = _build_sql_connection_string(session_env)
            database_name = str(session_env.get("SQL_DB_DATABASE") or "").strip()
            database_host = str(session_env.get("SQL_DB_HOST") or "").strip()
            database_port = str(session_env.get("SQL_DB_PORT") or "").strip()
            database_username = str(session_env.get("SQL_DB_USERNAME") or "").strip()
            extracted_fields = {
                **extracted_fields,
                "connector": extracted_fields.get("connector") or "sql-dab",
                "config": {
                    **(extracted_fields.get("config") or {}),
                    "session_env_keys": sorted(session_env.keys()),
                },
            }
            explicit_connection_id = extracted_fields.get("connection_id") or session_env.get("SQL_CONNECTION_ID")
            if explicit_connection_id:
                extracted_fields["connection_id"] = explicit_connection_id
                extracted_fields["config"] = {
                    **(extracted_fields.get("config") or {}),
                    "connection_id": explicit_connection_id,
                }
            if database_name:
                extracted_fields["database"] = database_name
                extracted_fields["config"] = {
                    **(extracted_fields.get("config") or {}),
                    "database": database_name,
                }
            if database_host:
                extracted_fields["config"] = {
                    **(extracted_fields.get("config") or {}),
                    "host": database_host,
                }
            if database_port:
                extracted_fields["config"] = {
                    **(extracted_fields.get("config") or {}),
                    "port": database_port,
                }
            if database_username:
                extracted_fields["config"] = {
                    **(extracted_fields.get("config") or {}),
                    "username": database_username,
                }
            if derived_connection_string:
                extracted_fields["config"] = {
                    **(extracted_fields.get("config") or {}),
                    "sql_connection_string": derived_connection_string,
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

        if extracted_fields:
            sql_followup_response = _sql_followup_response(request, extracted_fields, session_env)
            if sql_followup_response:
                return ChatResponse(
                    response=sql_followup_response,
                    job_creation_intent=True,
                    extracted_fields=extracted_fields,
                )

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
