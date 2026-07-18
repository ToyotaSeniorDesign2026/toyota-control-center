#!/usr/bin/env python
"""Mutation + performance harness for the Control Center Job Designer MCP App.

Two independent audits, both runnable from one script:

  • PERF  — micro-benchmarks the hot MCP operations (resource HTML render, draft
            patch, snapshot read, capture round-trip, schema resolve, generate
            pipeline) through the real in-memory FastMCP client. Reports
            min/median/mean/p95/max so regressions in the request path are
            visible without a profiler.

  • MUTATE — the "were these tests written just to pass?" check. Each mutation
            injects one realistic bug into a *source* file, runs the test(s)
            that claim to cover that behavior, and asserts at least one FAILS
            (the mutant is "killed"). A mutant that SURVIVES a green suite is a
            genuine coverage gap — the suite would not notice that bug in prod.
            Source files are always restored, even on error/KeyboardInterrupt.

Usage (from anywhere — paths are resolved relative to this file):

    python tests/mutation_and_perf.py            # perf + mutations
    python tests/mutation_and_perf.py --perf      # perf only
    python tests/mutation_and_perf.py --mutate    # mutations only
    python tests/mutation_and_perf.py --full      # run the WHOLE suite per mutant
    python tests/mutation_and_perf.py --iterations 200

Run it with the backend venv so imports resolve:

    backend/.venv/bin/python \
      backend/mcp_servers/internal/control-center-mcp-app/tests/mutation_and_perf.py
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

# ── Path wiring (mirror conftest so we can import the app in-process) ──────────
TESTS_DIR = Path(__file__).resolve().parent
APP_DIR = TESTS_DIR.parent
SRC_ROOT = APP_DIR.parents[3] / "src"          # …/backend/src
BACKEND_DIR = APP_DIR.parents[2]               # …/backend
VENV_PY = BACKEND_DIR / ".venv" / "bin" / "python"

for candidate in (str(APP_DIR), str(SRC_ROOT), str(TESTS_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)


# ── ANSI helpers ──────────────────────────────────────────────────────────────
def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text


GREEN = lambda s: _c("32", s)
RED = lambda s: _c("31", s)
YELLOW = lambda s: _c("33", s)
BOLD = lambda s: _c("1", s)
DIM = lambda s: _c("2", s)


# ══════════════════════════════════════════════════════════════════════════════
# PERFORMANCE
# ══════════════════════════════════════════════════════════════════════════════

async def _time_async(label: str, fn: Callable[[], Awaitable[None]], iterations: int) -> "Timing":
    # One warm-up call (import/JIT/first-touch) excluded from the sample.
    await fn()
    samples: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        await fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return Timing(label, samples)


def _time_sync(label: str, fn: Callable[[], None], iterations: int) -> "Timing":
    fn()  # warm-up
    samples: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return Timing(label, samples)


@dataclass
class Timing:
    label: str
    samples: list[float]

    @property
    def p95(self) -> float:
        ordered = sorted(self.samples)
        idx = max(0, int(round(0.95 * (len(ordered) - 1))))
        return ordered[idx]

    def row(self) -> str:
        return (
            f"  {self.label:<38} "
            f"min {min(self.samples):7.2f}  "
            f"med {statistics.median(self.samples):7.2f}  "
            f"mean {statistics.mean(self.samples):7.2f}  "
            f"p95 {self.p95:7.2f}  "
            f"max {max(self.samples):7.2f}   " + DIM("(ms)")
        )


async def run_perf(iterations: int) -> None:
    print(BOLD("\n═══ PERFORMANCE ═══"))
    print(DIM(f"  {iterations} iterations per op (+1 warm-up), in-memory FastMCP client\n"))

    # Imported here so --mutate-only runs don't pay the import cost.
    from unittest import mock
    import server as server_module
    from _harness import mcp_client, structured

    timings: list[Timing] = []

    # 1. Resource HTML render — runs on every resources/read; heaviest pure-CPU op.
    boot_state = server_module._initial_state(job_types=server_module.forms.static_job_types())
    timings.append(_time_sync(
        "build_app + html render",
        lambda: server_module._build_app(boot_state).html(tool_resolver=server_module._resolve_prefab_tool),
        iterations,
    ))

    # 2. Schema resolution (offline, KNOWN_CONTRACTS path).
    timings.append(_time_sync(
        "resolve sql form schema",
        lambda: server_module.forms.resolve_job_type_schema("sql", allow_api_fallback=True),
        iterations,
    ))

    # 3–7. Tool round-trips through the real MCP wire.
    srv = server_module.build_server()
    async with mcp_client(srv) as client:
        await client.call_tool("open_job_designer", {"job_type": "sql", "reset": True})

        async def _patch() -> None:
            await client.call_tool("patch_draft_snapshot", {"patch": {"config": {"database": "analytics"}}})

        async def _snapshot() -> None:
            await client.call_tool("get_draft_snapshot", {})

        async def _ui_state() -> None:
            await client.call_tool("get_current_draft_ui_state", {})

        async def _form_schema() -> None:
            await client.call_tool("get_form_schema", {"job_type": "airflow_python"})

        timings.append(await _time_async("patch_draft_snapshot (tool)", _patch, iterations))
        timings.append(await _time_async("get_draft_snapshot (tool)", _snapshot, iterations))
        timings.append(await _time_async("get_current_draft_ui_state (tool)", _ui_state, iterations))
        timings.append(await _time_async("get_form_schema (tool)", _form_schema, iterations))

        # 8. generate_full_job_draft pipeline with the LLM boundary faked out —
        # times only the server-side patch/merge/redact work.
        async def _fake_gen(**kwargs):
            return {
                "selected_job_type": "sql", "job_name": "Perf", "intent": kwargs["intent"],
                "config": {"query": "SELECT 1"}, "params": {"host": "h"},
                "meta": {"job_type_reasoning": "r", "job_type": "sql"},
            }

        with mock.patch.object(server_module, "generate_job_draft_from_intent", _fake_gen):
            async def _generate() -> None:
                await client.call_tool("generate_full_job_draft", {"intent": "do sql stuff"})
            timings.append(await _time_async("generate_full_job_draft (pipeline)", _generate, iterations))

    for t in timings:
        print(t.row())

    slowest = max(timings, key=lambda t: statistics.median(t.samples))
    print(DIM(f"\n  slowest median: {slowest.label} @ {statistics.median(slowest.samples):.2f} ms"))


# ══════════════════════════════════════════════════════════════════════════════
# MUTATION TESTING
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Mutation:
    name: str
    rel_path: str          # file to mutate, relative to APP_DIR
    old: str               # exact source substring (must be unique)
    new: str               # replacement that introduces the bug
    target: str            # test path (relative to APP_DIR) expected to kill it
    behavior: str          # what real-world guarantee this protects

    @property
    def path(self) -> Path:
        return APP_DIR / self.rel_path


MUTATIONS: list[Mutation] = [
    Mutation(
        "secret-marker-disabled",
        "utils.py",
        'k: (SECRET_MARKER if k in secret_names and v not in ("", None) else v)',
        "k: v",
        "tests/test_secret_redaction_e2e.py",
        "secret fields are masked on AI-facing surfaces",
    ),
    Mutation(
        "empty-secret-gets-masked",
        "utils.py",
        'SECRET_MARKER if k in secret_names and v not in ("", None) else v',
        "SECRET_MARKER if k in secret_names else v",
        "tests/test_secret_redaction_e2e.py",
        "an empty secret field stays empty (no fake '•••')",
    ),
    Mutation(
        "patch-return-leaks-secret",
        "server.py",
        '"params": redacted["draft"]["params"],',
        '"params": result["params"],',
        "tests/test_secret_redaction_e2e.py::PatchReturnRedactionTests",
        "patch_draft_snapshot return masks top-level secrets (the leak we fixed)",
    ),
    Mutation(
        "no-job-type-lowercase",
        "forms.py",
        "    return text.lower()",
        "    return text",
        "tests/test_designer_draft_e2e.py",
        "job types normalize case ('SQL' → 'sql')",
    ),
    Mutation(
        "int-coercion-noop",
        "forms.py",
        "                return int(value)",
        "                return value",
        "tests/test_job_lifecycle_e2e.py",
        "numeric params are coerced to int ('5432' → 5432)",
    ),
    Mutation(
        "config-merge-drops-base",
        "server.py",
        "            return {**base, **update}",
        "            return {**update}",
        "tests/test_designer_draft_e2e.py",
        "config/params patches MERGE (don't clobber prior keys)",
    ),
    Mutation(
        "risk-high-becomes-low",
        "server.py",
        '        band = "high"',
        '        band = "low"',
        "tests/test_connector_risk_profile_e2e.py",
        "destructive+external tools classify as high risk",
    ),
    Mutation(
        "create-env-not-lowercased",
        "server.py",
        'normalized_environment = environment.strip().lower() if environment else "dev"',
        'normalized_environment = environment.strip() if environment else "dev"',
        "tests/test_job_lifecycle_e2e.py",
        "create_job lowercases the environment ('PROD' → 'prod')",
    ),
    Mutation(
        "create-tags-unsorted-dupes",
        "server.py",
        '"tags": sorted({t for t in merged_tags if t}),',
        '"tags": [t for t in merged_tags if t],',
        "tests/test_job_lifecycle_e2e.py",
        "create_job de-dupes + sorts merged tags",
    ),
    Mutation(
        "required-flag-always-false",
        "utils.py",
        '"required": bool(name and name in required_names)',
        '"required": False',
        "tests/test_designer_draft_e2e.py",
        "form-schema fields carry a correct 'required' flag",
    ),
    Mutation(
        "jobgen-type-not-pinned",
        "job_generation.py",
        "    pinned_job_type = _literal_of([contract.type])",
        "    pinned_job_type = str",
        "tests/test_job_generation.py",
        "generated draft pins selected_job_type to the chosen contract",
    ),
    Mutation(
        "jobgen-connectors-unconstrained",
        "job_generation.py",
        "        connectors_type: Any = list[_literal_of(approved_connectors)]",
        "        connectors_type: Any = list[str]",
        "tests/test_job_generation.py",
        "generated connectors are constrained to the approved list",
    ),
]


def _clear_pycache() -> None:
    for d in (APP_DIR, TESTS_DIR):
        pc = d / "__pycache__"
        if pc.is_dir():
            shutil.rmtree(pc, ignore_errors=True)


def _run_pytest(target: str) -> tuple[bool, str]:
    """Return (all_passed, failed_test_ids). all_passed True ⇒ mutant survived."""
    _clear_pycache()
    proc = subprocess.run(
        [str(VENV_PY), "-m", "pytest", str(APP_DIR / target), "-q", "--tb=no", "-rf", "-p", "no:cacheprovider"],
        cwd=str(APP_DIR),
        capture_output=True,
        text=True,
    )
    passed = proc.returncode == 0
    failed_ids = [
        line.split("FAILED", 1)[1].strip().split(" ")[0]
        for line in proc.stdout.splitlines()
        if line.startswith("FAILED")
    ]
    if proc.returncode not in (0, 1):  # collection/other error, not a test failure
        return passed, f"pytest error (rc={proc.returncode}): {proc.stdout.strip().splitlines()[-1] if proc.stdout else proc.stderr.strip()[:200]}"
    return passed, ", ".join(failed_ids[:3]) + (" …" if len(failed_ids) > 3 else "")


def _verify_baseline(target: str) -> bool:
    passed, detail = _run_pytest(target)
    return passed


def run_mutations(full_suite: bool) -> int:
    print(BOLD("\n═══ MUTATION TESTING ═══"))
    scope = "tests" if full_suite else "the targeted test file"
    print(DIM(f"  Each mutant injects one bug; running {scope}; a SURVIVOR is a gap.\n"))

    survivors: list[Mutation] = []
    killed = 0

    for i, m in enumerate(MUTATIONS, 1):
        original = m.path.read_text()
        count = original.count(m.old)
        prefix = f"  [{i:>2}/{len(MUTATIONS)}] {m.name:<32}"

        if count != 1:
            print(f"{prefix} {YELLOW('SKIP')}  anchor found {count}× (source drift) in {m.rel_path}")
            continue

        target = "tests" if full_suite else m.target
        try:
            m.path.write_text(original.replace(m.old, m.new, 1))
            passed, detail = _run_pytest(target)
        finally:
            m.path.write_text(original)  # always restore, even on Ctrl-C/error
            _clear_pycache()

        if passed:
            survivors.append(m)
            print(f"{prefix} {RED('SURVIVED')}  ← gap: {m.behavior}")
        else:
            killed += 1
            print(f"{prefix} {GREEN('killed')}    {DIM('by ' + detail)}")

    print()
    total = killed + len(survivors)
    if survivors:
        print(RED(BOLD(f"  {len(survivors)}/{total} mutants SURVIVED — those behaviors are not protected:")))
        for m in survivors:
            print(RED(f"    • {m.name}: {m.behavior}"))
            print(DIM(f"        expected killer: {m.target}"))
    else:
        print(GREEN(BOLD(f"  All {total} mutants killed — the suite catches each injected bug.")))

    return 1 if survivors else 0


# ══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--perf", action="store_true", help="run only the performance benchmarks")
    ap.add_argument("--mutate", action="store_true", help="run only the mutation battery")
    ap.add_argument("--full", action="store_true", help="run the whole suite per mutant (slower, catches cross-coverage)")
    ap.add_argument("--iterations", type=int, default=100, help="perf iterations per op (default 100)")
    args = ap.parse_args()

    if not VENV_PY.exists():
        print(RED(f"backend venv python not found at {VENV_PY}"))
        return 2

    do_perf = args.perf or not args.mutate
    do_mutate = args.mutate or not args.perf

    rc = 0
    if do_perf:
        asyncio.run(run_perf(args.iterations))
    if do_mutate:
        rc = run_mutations(full_suite=args.full)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
