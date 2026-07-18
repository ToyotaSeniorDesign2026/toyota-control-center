"""Pytest path wiring for the Control Center Job Designer MCP App test suite.

The app ships as flat modules (`server`, `forms`, `utils`, `job_generation`)
that import each other by bare name and rely on the script's own directory being
on ``sys.path`` — that's how ``python server.py`` runs it. ``control_center.specs``
(imported transitively by `server`/`forms`) lives under ``backend/src``.

These are the only two roots the suite actually imports from, so they are the
only two added. The file does nothing but adjust ``sys.path``; all shared test
machinery lives in ``_harness.py``, out of the production import path.

Equivalent alternative if you prefer config over code: a pytest ``pythonpath``
setting (pytest >= 7) pointing at the same two dirs.
"""

from __future__ import annotations

import sys
from pathlib import Path

# tests/ -> control-center-mcp-app (flat app modules: server, forms, utils, …)
APP_DIR = Path(__file__).resolve().parents[1]
# tests/ -> … -> backend/src (control_center.specs)
SRC_ROOT = Path(__file__).resolve().parents[4] / "src"

for candidate in (APP_DIR, SRC_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)
