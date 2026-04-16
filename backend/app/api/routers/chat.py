"""Chat API router for handling AI chat messages."""

import logging
import re
from typing import Optional, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.api.deps import get_db
from app.services.chat_service import get_chat_service
from app.services.field_extraction_service import get_field_extraction_service
from app.services.chat_job_service import maybe_run_sql_job_from_chat, run_resource_by_id
from app.services.chat_mcp_service import run_prompt_native_mcp, should_run_prompt_native_mcp

router = APIRouter()
logger = logging.getLogger(__name__)
SQL_RUN_REQUEST_PATTERN = re.compile(r"\b(run|execute|launch|trigger|start)\b", re.IGNORECASE)
RUN_JOB_MARKER_PATTERN = re.compile(r'\[RUN_JOB:([a-zA-Z0-9\-_]+)\]')
SQL_RUN_CONTEXT_PATTERN = re.compile(r"\b(job|sql|query|resource)\b", re.IGNORECASE)
AFFIRMATIVE_RUN_RESPONSE_PATTERN = re.compile(r"^(yes|yep|yeah|sure|please do|go ahead|run it|run now|do it)[\s.!?]*$", re.IGNORECASE)


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
            mcp_result = await run_prompt_native_mcp(
                message=request.message,
                environment=str((request.current_draft_data or {}).get("target_environment") or (request.current_draft_data or {}).get("environment") or "dev"),
                model=request.model,
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
        extracted_fields = _deterministic_sql_fields(request)
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
