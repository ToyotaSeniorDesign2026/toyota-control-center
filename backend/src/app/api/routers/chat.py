from __future__ import annotations

"""Chat router (v2).

The single new endpoint is ``POST /run``: take a prompt + optional job_type,
ensure a Job exists, create a Run, and dispatch via the v2 executor registry.

Legacy endpoints (``/guided``, ``/agent``, etc.) are re-included from
``chat_legacy.py`` so the existing frontend keeps working unchanged. Once
the frontend is migrated to ``/run``, the legacy include can be dropped.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.routers.chat_legacy import router as _legacy_router
from app.core.db import new_id, now_iso
from app.models.job import Job
from app.schemas.run import RunCreate
from app.services.job_type_service import get_job_type_contract
from app.services.run_service_v2 import create_run_and_execute_v2
from control_center.specs import JobTypeContract

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Re-mount legacy endpoints so the frontend keeps working ───────────────────
# Once frontend migrates to /run, remove this include.
router.include_router(_legacy_router)


# ──────────────────────────────────────────────────────────────────────────────
# /run — new V2 entrypoint
# ──────────────────────────────────────────────────────────────────────────────

class ChatTurn(BaseModel):
    """One message in a chat conversation. ``role`` is ``user`` or ``assistant``."""
    role: str
    content: str


class ChatRunRequest(BaseModel):
    """Chat-driven job execution.

    Either supply ``job_id`` to reuse an existing job, or supply ``job_type`` +
    ``config`` to ensure-or-create a job of that type owned by the caller.

    ``prompt`` is the latest user message. ``conversation_history`` (optional)
    carries prior messages so agent jobs can act on the full context — the
    history is folded into the prompt sent to the agent loop. SQL/deterministic
    executors ignore the history.
    """
    prompt: str = Field(min_length=1)
    job_id: str | None = None
    job_type: str | None = None
    job_name: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    target_environment: str = Field(default="dev")
    conversation_history: list[ChatTurn] = Field(default_factory=list)


class ChatRunResponse(BaseModel):
    job_id: str
    job_type: str
    contract_type: str
    executor_type: str
    run: dict[str, Any]


def _classify_job_type(prompt: str) -> str:
    """Pick a job type for the prompt.

    MVP heuristic — not LLM-driven for speed/reliability:
      - SQL-ish keywords → 'sql'
      - everything else  → 'mcp' (agent)

    Deterministic, fast, no API call. Replace with an Instructor classifier
    once the agent stack stabilizes.
    """
    p = prompt.lower()
    sql_signals = (
        "select ", "select\n", "insert ", "update ", "delete ",
        "from ", " where ", "create table", "drop table", "schema",
    )
    if any(sig in p for sig in sql_signals):
        return "sql"
    return "mcp"


def _ensure_job(
    db: Session,
    user,
    *,
    job_type: str,
    contract: JobTypeContract,
    config: dict[str, Any],
    job_name: str | None,
    target_environment: str,
) -> Job:
    """Find an existing job of the requested type owned by the user, or create one.

    Reuse policy: if a non-archived job of the same type and environment is
    owned by the user, reuse it. This keeps the run history grouped under one
    Job per type rather than spawning a fresh row per chat request.
    """
    existing = (
        db.query(Job)
        .filter(
            Job.owner_id == user.id,
            Job.type == job_type,
            Job.environment == target_environment,
            Job.status.in_(["active", "draft", None, ""]),
        )
        .first()
    )
    if existing is not None:
        if config:
            merged = {**(existing.config or {}), **config}
            existing.config = merged
            existing.updated_at = now_iso()
            db.add(existing)
            db.commit()
            db.refresh(existing)
        return existing

    # Pick a connector name from the contract's first MCP_SERVER requirement.
    connector = ""
    if contract.requires:
        first = contract.requires[0]
        if first.names:
            connector = first.names[0]
    if not connector:
        connector = job_type

    name = job_name or f"chat-{job_type}-{new_id('j')[-6:]}"
    ts = now_iso()
    job = Job(
        id=new_id("job"),
        name=name,
        kind="runtime",
        type=job_type,
        connector=connector,
        owner_id=user.id,
        owner_domain=user.domain,
        environment=target_environment,
        status="active",
        data_sensitivity="low",
        config=config or {},
        tags=["chat-created"],
        created_at=ts,
        updated_at=ts,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.post("/run", response_model=ChatRunResponse)
async def chat_run(
    request: ChatRunRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> ChatRunResponse:
    # ── Resolve the contract ──────────────────────────────────────────────────
    if request.job_id:
        job = db.get(Job, request.job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job {request.job_id} not found")
        if user.role != "root" and job.owner_id != user.id and job.owner_domain != user.domain:
            raise HTTPException(status_code=403, detail="Not allowed")
        job_type = job.type
        contract = get_job_type_contract(job_type)
        if contract is None:
            raise HTTPException(
                status_code=422,
                detail=f"No contract registered for job.type={job_type!r}",
            )
    else:
        job_type = (request.job_type or _classify_job_type(request.prompt)).strip().lower()
        contract = get_job_type_contract(job_type)
        if contract is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"No contract registered for job_type={job_type!r}. "
                    "Add to KNOWN_CONTRACTS or pass an existing job_id."
                ),
            )
        job = _ensure_job(
            db,
            user,
            job_type=job_type,
            contract=contract,
            config=request.config,
            job_name=request.job_name,
            target_environment=request.target_environment,
        )

    # ── Persist run-specific defaults onto the job so legacy reruns work ─────
    # Frontend's "Run" button hits POST /jobs/{id}/runs which goes through
    # the legacy execution_service. That path looks for `query`/`prompt` in
    # job.config (not just per-run params). Mirror them here so a re-run from
    # the UI works without supplying params again.
    config_patch: dict[str, Any] = {}
    if request.params.get("query"):
        config_patch["query"] = request.params["query"]
    if request.prompt:
        config_patch["prompt"] = request.prompt
    if config_patch:
        merged = {**(job.config or {}), **config_patch}
        if merged != (job.config or {}):
            job.config = merged
            job.updated_at = now_iso()
            db.add(job)
            db.commit()
            db.refresh(job)

    # ── Compose the prompt with conversation history (agent paths only) ──────
    # Deterministic executors (SQL_QUERY, MCP_TOOL) don't read prompt content,
    # so history fold-in is wasted. Agentic paths benefit greatly — the LLM
    # gets prior turns and can pick up where the conversation left off.
    effective_prompt = request.prompt
    if request.conversation_history and contract.executor_type.value.startswith("mcp_agent"):
        history_lines: list[str] = []
        # Cap at last 10 turns to keep prompts under model context limits.
        for turn in request.conversation_history[-10:]:
            role = (turn.role or "user").strip().upper()
            content = (turn.content or "").strip()
            if not content:
                continue
            history_lines.append(f"{role}: {content}")
        if history_lines:
            history_lines.append(f"USER: {request.prompt}")
            effective_prompt = "\n\n".join(history_lines)

    # ── Build run payload ─────────────────────────────────────────────────────
    payload = RunCreate(
        job_id=job.id,
        action="run",
        target_environment=request.target_environment,
        params=request.params,
        prompt=effective_prompt,
    )

    # ── Dispatch via v2 ───────────────────────────────────────────────────────
    run_out = create_run_and_execute_v2(
        db=db,
        user=user,
        payload=payload,
        trigger_source="chat_v2",
    )

    return ChatRunResponse(
        job_id=job.id,
        job_type=job.type,
        contract_type=contract.type,
        executor_type=contract.executor_type.value,
        run=run_out,
    )
