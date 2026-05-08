from __future__ import annotations

"""AIRFLOW_PYTHON executor — run a Python file (Airflow DAG-style or plain).

Two modes (chosen by config.run_mode):

  - "subprocess" (default): treat `executor` as the script identifier
    (looked up in scripts/airflow/<executor>.py inside the container).
    Runs the script directly via `python <path> --params <json>`. Suited for
    Airflow-flavored Python tasks during development without requiring an
    Airflow scheduler/webserver to be live.

  - "trigger_dag": treat `executor` as a DAG ID, POST to Airflow's REST API
    to trigger a dag_run, poll for completion. Requires `config.airflow_url`
    and `config.airflow_token`. Not yet implemented.

Reads:
    contract.executor       — script identifier (subprocess) or DAG ID (trigger_dag)
    job.config              — defaults; merged with payload.params at exec time
    payload.params          — per-run overrides (forwarded to the script as JSON)
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from app.services.execution_service_v2 import ExecutionRequestV2

from .base import V2Executor

logger = logging.getLogger(__name__)


# Where Airflow-style scripts live inside the container. Override for tests.
_DEFAULT_SCRIPT_ROOT = Path(os.getenv("AIRFLOW_SCRIPT_ROOT", "/app/scripts/airflow")).resolve()


def _merged_inputs(request: ExecutionRequestV2) -> dict[str, Any]:
    job_config = getattr(request.job, "config", None) or {}
    if not isinstance(job_config, dict):
        job_config = {}
    params = request.payload.params or {}
    return {**job_config, **params}


def _resolve_script_path(executor: str) -> Path:
    """Map the contract's `executor` string to an absolute script path.

    Accepts:
      - bare name like "hello_world" → scripts/airflow/hello_world.py
      - relative path "subdir/script.py" → scripts/airflow/subdir/script.py
      - absolute path "/app/.../script.py" → used as-is
    """
    if executor.startswith("/"):
        return Path(executor).resolve()
    name = executor if executor.endswith(".py") else f"{executor}.py"
    return (_DEFAULT_SCRIPT_ROOT / name).resolve()


class AirflowPythonExecutor(V2Executor):
    """Run a Python file (Airflow-style)."""

    async def execute_async(self, request: ExecutionRequestV2) -> dict[str, Any]:
        merged = _merged_inputs(request)
        run_mode = (merged.get("run_mode") or "subprocess").strip().lower()

        if run_mode == "subprocess":
            return await self._run_subprocess(request, merged)
        elif run_mode == "trigger_dag":
            return {
                "status": "failed",
                "result": None,
                "error": (
                    "Traceback  (most recent call last):\n"
                    "       elif run_mode == 'trigger_dag':\n"
                    "--->       raise NotImplementedError(\n"
                    "NotImplementedError: run_mode='trigger_dag' is not implemented yet. "
                    "Currently, only run_mode='subprocess' is supported. "
                    "To support run_mode='trigger_dag', implement DAG execution via the Airflow REST API."
                ),
                "metadata": {"executor_type": "airflow_python", "run_mode": run_mode},
            }
        else:
            return {
                "status": "failed",
                "result": None,
                "error": f"unknown run_mode {run_mode!r}; expected 'subprocess' or 'trigger_dag'",
                "metadata": {"executor_type": "airflow_python", "run_mode": run_mode},
            }

    async def _run_subprocess(
        self,
        request: ExecutionRequestV2,
        merged: dict[str, Any],
    ) -> dict[str, Any]:
        contract = request.contract
        script_path = _resolve_script_path(contract.executor)

        if not script_path.exists():
            return {
                "status": "failed",
                "result": None,
                "error": f"script not found: {script_path}",
                "metadata": {
                    "executor_type": "airflow_python",
                    "run_mode": "subprocess",
                    "script_path": str(script_path),
                    "script_root": str(_DEFAULT_SCRIPT_ROOT),
                },
            }

        # Forward all merged config+params to the script as JSON so the script
        # can pick what it needs.
        payload_json = json.dumps(merged, default=str)
        timeout_s = max(1, contract.features.max_runtime_seconds)

        proc: asyncio.subprocess.Process | None = None
        try:
            proc = await asyncio.create_subprocess_exec(
                "python",
                str(script_path),
                "--params",
                payload_json,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError:
            if proc is not None:
                with contextlib_suppress():
                    proc.kill()
                    await proc.wait()
            return {
                "status": "failed",
                "result": None,
                "error": f"script timed out after {timeout_s}s",
                "metadata": {
                    "executor_type": "airflow_python",
                    "run_mode": "subprocess",
                    "script_path": str(script_path),
                    "timeout_seconds": timeout_s,
                },
            }
        except Exception as exc:
            logger.exception("AIRFLOW_PYTHON subprocess failed to start")
            return {
                "status": "failed",
                "result": None,
                "error": f"failed to start script: {exc}",
                "metadata": {
                    "executor_type": "airflow_python",
                    "run_mode": "subprocess",
                    "script_path": str(script_path),
                },
            }

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        exit_code = proc.returncode if proc.returncode is not None else -1

        # If the script printed a final JSON line, surface it as the result.
        # Otherwise, expose stdout tail.
        result_payload: Any = stdout.strip().splitlines()[-1] if stdout.strip() else ""
        try:
            parsed = json.loads(result_payload)
            result_payload = parsed
        except (ValueError, TypeError):
            # Not JSON — leave as the last stdout line (already a string).
            pass

        return {
            "status": "succeeded" if exit_code == 0 else "failed",
            "result": {
                "exit_code": exit_code,
                "stdout_tail": stdout[-2000:],
                "stderr_tail": stderr[-2000:],
                "final_payload": result_payload,
            },
            "error": None if exit_code == 0 else f"script exited with code {exit_code}",
            "metadata": {
                "executor_type": "airflow_python",
                "run_mode": "subprocess",
                "script_path": str(script_path),
                "exit_code": exit_code,
            },
        }


# Tiny inline contextlib_suppress to avoid importing contextlib for single use.
class contextlib_suppress:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return True
