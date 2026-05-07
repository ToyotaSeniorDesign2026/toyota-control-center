from __future__ import annotations

"""V2 execution service — dispatches by JobTypeContract.executor_type.

Replaces the hardcoded if-chain in execution_service.resolve_run_spec.
The contract on the job declares which Executor handles it; the registry
maps ExecutorType → Executor class; the executor reads job.config + payload
to figure out what to actually call.

Old path (execution_service.py + executors/mcp_executor.py) is preserved
unchanged for chat_legacy.py compatibility.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict

from app.schemas.run import RunCreate
from app.services.job_type_service import get_job_type_contract
from control_center.specs import JobTypeContract


class ExecutionRequestV2(BaseModel):
    """Slim request shape for v2 dispatch.

    Carries the live ORM Job (or compatible attrs object), the run payload,
    and the resolved JobTypeContract. Executors read what they need from
    these directly — no pre-built run_spec.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: str
    job: Any                            # ORM Job or attr-compatible object
    payload: RunCreate
    contract: JobTypeContract
    target_environment: str
    trigger_source: str = "api"


def build_request(
    *,
    run_id: str,
    job: Any,
    payload: RunCreate,
    trigger_source: str = "api",
) -> ExecutionRequestV2:
    """Resolve the contract for a job and assemble a v2 request."""
    contract = get_job_type_contract(job.type)
    if contract is None:
        raise RuntimeError(
            f"No JobTypeContract registered for job.type={job.type!r}. "
            f"Add it to KNOWN_CONTRACTS or expose it via the registry."
        )
    return ExecutionRequestV2(
        run_id=run_id,
        job=job,
        payload=payload,
        contract=contract,
        target_environment=payload.target_environment,
        trigger_source=trigger_source,
    )


def dispatch(request: ExecutionRequestV2) -> dict[str, Any]:
    """Route a v2 request to the executor registered for its executor_type."""
    # Imported lazily to avoid circular imports at module load.
    from app.services.executors.v2 import EXECUTOR_REGISTRY

    executor_cls = EXECUTOR_REGISTRY.get(request.contract.executor_type)
    if executor_cls is None:
        raise RuntimeError(
            f"No executor registered for executor_type={request.contract.executor_type!r}. "
            f"Registered: {sorted(EXECUTOR_REGISTRY)}"
        )
    return executor_cls().execute(request)
