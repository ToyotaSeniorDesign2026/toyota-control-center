"""Sample Airflow-style task: compute daily collections metrics.

In a real deployment this would query SQL, aggregate, and write back.
As a proof-of-concept for using the Control Center to execute an existing
Airflow workflow, we synthesize plausible numbers so the run produces a
satisfying final_payload visible in the run-detail UI.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date, datetime, timezone


def run(context: dict) -> dict:
    region = context.get("region") or "ALL"
    seed = int(context.get("seed") or 42)
    random.seed(seed)

    accounts = random.randint(1200, 1800)
    delinquent = random.randint(80, 220)
    avg_balance = round(random.uniform(2400, 5800), 2)
    recovery_rate = round(random.uniform(0.62, 0.84), 3)

    return {
        "as_of": date.today().isoformat(),
        "region": region,
        "metrics": {
            "active_accounts": accounts,
            "delinquent_accounts": delinquent,
            "delinquency_rate": round(delinquent / accounts, 4),
            "avg_balance_usd": avg_balance,
            "recovery_rate": recovery_rate,
        },
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
