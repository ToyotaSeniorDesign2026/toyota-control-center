"""Sample Airflow-style task: validate a batch of records and report issues.

Proof-of-concept job that simulates a data-quality check. In a real deployment this
would read source rows, apply rule sets, and emit a structured report.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone


CHECKS = [
    "non_null_account_id",
    "valid_email_format",
    "balance_in_range",
    "status_enum_known",
    "created_at_not_future",
]


def run(context: dict) -> dict:
    batch_id = context.get("batch_id") or f"batch-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}"
    seed = int(context.get("seed") or 7)
    rows = int(context.get("rows") or 5000)
    random.seed(seed)

    issues_per_check = {check: random.randint(0, 12) for check in CHECKS}
    total_issues = sum(issues_per_check.values())
    pass_rate = round(1 - (total_issues / max(rows, 1)), 5)
    severity = "ok" if total_issues == 0 else ("warn" if total_issues < 20 else "fail")

    return {
        "batch_id": batch_id,
        "rows_checked": rows,
        "issues_per_check": issues_per_check,
        "total_issues": total_issues,
        "pass_rate": pass_rate,
        "severity": severity,
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--params", default="{}")
    args = parser.parse_args()
    try:
        ctx = json.loads(args.params)
        if not isinstance(ctx, dict):
            ctx = {}
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"invalid --params JSON: {exc}"}), file=sys.stderr)
        return 2

    print(json.dumps(run(ctx)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
