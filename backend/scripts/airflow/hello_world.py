"""Sample Airflow-style Python task for testing the AIRFLOW_PYTHON executor.

The executor runs this with: `python hello_world.py --params '<json>'`
The script prints a single JSON line as its final output, which the
executor surfaces in run.resolved_job_spec_json.executor_state.final_payload.

This is a proof-of-concept for real Airflow PythonOperator code, which typically looks like this —
 a callable that takes a `kwargs` dict (rendered context). We approximate that here by reading
`--params <json>` and exposing it as a context dict.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone


def run(context: dict) -> dict:
    """The real task body. Edit this for new pipelines.

    Args:
        context: Merged job.config + run.params. Same dict you'd get from
                 Airflow's `**kwargs` if this were a PythonOperator.

    Returns:
        Dict that gets serialized to JSON for the executor to capture.
    """
    name = context.get("name") or "world"
    multiplier = int(context.get("multiplier") or 1)
    greeting = " ".join([f"hello {name}!"] * multiplier)

    return {
        "greeting": greeting,
        "received_keys": sorted(context.keys()),
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Airflow-style sample task.")
    parser.add_argument("--params", default="{}", help="JSON-encoded run context")
    args = parser.parse_args()

    try:
        context = json.loads(args.params)
        if not isinstance(context, dict):
            context = {}
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"invalid --params JSON: {exc}"}), file=sys.stderr)
        return 2

    try:
        result = run(context)
    except Exception as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1

    # Print as the LAST stdout line so the executor parses it as final_payload.
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
