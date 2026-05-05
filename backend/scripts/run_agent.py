
"""Run an MCP agent against a prompt, with visibility into tool usage.

Usage:
    # Quick — auto-select connectors based on prompt
    uv run scripts/run_agent.py "Find recent papers on RAG"

    # Specific connectors
    uv run scripts/run_agent.py --server filesystem --server github "List the README files"

    # Use all available connectors in this environment
    uv run scripts/run_agent.py --all "What tools do you have?"

    # Interactive REPL (multi-turn within one agent session)
    uv run scripts/run_agent.py --interactive --server filesystem

    # Different environment, different model, more tool rounds
    uv run scripts/run_agent.py --environment semi-prod --model gemini-2.5-pro --max-rounds 10 "..."

    # Pipe a prompt
    cat prompt.txt | uv run scripts/run_agent.py --stdin

Exit code:
    0 = run completed (tool failures within the loop don't fail the script)
    1 = setup error (no connectors selected, model unavailable, etc.)
    2 = agent error (unhandled exception during run)
"""

from __future__ import annotations

# Load .env before anything that reads env vars
from pathlib import Path
from dotenv import load_dotenv

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_BACKEND_ROOT / ".env", override=False)

import argparse
import asyncio
import json
import sys
from typing import Any

from control_center.agent import MCPAgent, build_agent_from_registry
from control_center.registry import RegistryManager


# ── Output helpers ────────────────────────────────────────────────────────────

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def hr(label: str) -> None:
    print(f"\n{DIM}── {label} ──{RESET}")


def ok(msg: str) -> None:
    print(f"{GREEN}✓{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"{RED}✗{RESET} {msg}")


def info(msg: str) -> None:
    print(f"{DIM}{msg}{RESET}")


# ── Connector resolution ──────────────────────────────────────────────────────

def list_available(environment: str | None) -> list[str]:
    manager = RegistryManager(environment=environment)
    return manager.get_available_servers_list()


# ── Tool-call instrumentation ─────────────────────────────────────────────────

def patch_agent_logging(agent: MCPAgent, *, full_output: bool = False) -> None:
    """Wrap the agent's adapter.invoke so we print every tool call.

    Args:
        agent: the agent whose adapter to instrument
        full_output: if True, no truncation of args or results in the trace
    """
    original_invoke = agent._adapter.invoke
    args_cap = None if full_output else 300
    result_cap = None if full_output else 500

    async def traced_invoke(client, *, framework_name: str, arguments: dict[str, Any]):
        args_preview = _truncate(json.dumps(arguments, default=str), args_cap)
        print(f"\n  {BLUE}→ {framework_name}{RESET} {DIM}{args_preview}{RESET}")
        try:
            result = await original_invoke(client, framework_name=framework_name, arguments=arguments)
        except Exception as exc:
            print(f"  {RED}✗ {framework_name} failed: {exc}{RESET}")
            raise
        result_preview = _truncate(str(result), result_cap)
        print(f"  {GREEN}← {framework_name}{RESET} {DIM}{result_preview}{RESET}")
        return result

    agent._adapter.invoke = traced_invoke


def _truncate(s: str, n: int | None) -> str:
    if n is None:
        return s
    return s if len(s) <= n else s[: n - 1] + "…"


# ── Filesystem root discovery ─────────────────────────────────────────────────

async def ensure_capabilities_loaded(agent: MCPAgent) -> bool:
    """Force the adapter to populate `_bindings` before any introspection.

    Capabilities are normally loaded lazily inside `agent.run()`. Anything
    that wants to see tools beforehand (per-server reports, fs root
    discovery) needs this first. Returns True on success.
    """
    try:
        await agent.refresh_capabilities()
        return True
    except Exception as exc:
        info(f"capability refresh failed: {exc}")
        return False


def report_connected_servers(agent: MCPAgent) -> None:
    """Print one line per connected MCP server with its tool count."""
    try:
        bindings = agent._adapter._bindings
    except Exception:
        return
    if not bindings:
        info("no tools bound (capabilities may not have loaded)")
        return

    counts: dict[str, int] = {}
    for binding in bindings.values():
        server = getattr(binding, "server_name", "<unknown>")
        counts[server] = counts.get(server, 0) + 1

    for server in sorted(counts):
        ok(f"{server}: connected, {counts[server]} tool(s)")


async def discover_filesystem_roots(agent: MCPAgent) -> list[str]:
    """Probe the filesystem MCP server for its allowed directories.

    Returns an empty list if no filesystem server is connected, the tool isn't
    exposed, or the call fails. Never raises — discovery is best-effort.

    Assumes capabilities are already loaded (call `ensure_capabilities_loaded`
    first).
    """
    binding_name = _find_binding(agent, "list_allowed_directories")
    if binding_name is None:
        try:
            names = list(agent._adapter._bindings.keys())
        except Exception:
            names = []
        info(f"no list_allowed_directories binding found among {len(names)} tool(s)")
        # Hint at filesystem-prefixed tools to debug the actual name
        fs_like = [n for n in names if "filesystem" in n.lower() or "allowed" in n.lower()]
        if fs_like:
            info(f"filesystem-related tools present: {fs_like[:10]}")
        return []

    try:
        result = await agent._adapter.invoke(
            agent._client,
            framework_name=binding_name,
            arguments={},
        )
    except Exception as exc:
        info(f"discovery call to {binding_name} failed: {exc}")
        return []

    text = _extract_text(result)
    if not text:
        info(f"{binding_name} returned no text content")
        return []

    # Server returns lines like "Allowed directories:\n/abs/path\n/abs/path"
    roots = [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("/")
    ]
    if not roots:
        info(f"{binding_name} returned text but no absolute paths: {text[:200]!r}")
    return roots


def _find_binding(agent: MCPAgent, suffix: str) -> str | None:
    """Find a bound tool whose framework name ends with the given suffix.

    Iterates `_bindings` (the source of truth for framework_name → BoundCapability).
    `all_capabilities` returns framework-specific shapes (OpenAI dicts, Google
    objects) that don't have a uniform `.name` attribute.
    """
    try:
        bindings = agent._adapter._bindings
    except Exception:
        return None
    for framework_name in bindings:
        if framework_name.endswith(suffix):
            return framework_name
    return None


def _extract_text(result: Any) -> str:
    """Pull the text content out of a CallToolResult-like object."""
    content = getattr(result, "content", None)
    if not content:
        return str(result)
    parts: list[str] = []
    for block in content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


def prepend_filesystem_context(prompt: str, roots: list[str]) -> str:
    """Add filesystem-scope context to the front of the user prompt."""
    if not roots:
        return prompt
    if len(roots) == 1:
        scope = f"the directory: {roots[0]}"
    else:
        scope = "one of these directories:\n  - " + "\n  - ".join(roots)
    preface = (
        f"[Filesystem context: filesystem tools are restricted to {scope}. "
        f"All file paths must be absolute paths inside this scope; "
        f"do not use relative paths.]\n\n"
    )
    return preface + prompt


# ── Agent build ───────────────────────────────────────────────────────────────

async def build(
    *,
    environment: str | None,
    explicit_servers: list[str] | None,
    selection_prompt: str | None,
    use_all: bool,
    model: str | None,
    instructor_model: str | None,
    max_rounds: int,
    verbose: bool,
) -> MCPAgent:
    available = list_available(environment)
    if not available:
        fail(f"no connectors available in environment={environment!r}")
        sys.exit(1)

    if explicit_servers:
        unknown = [s for s in explicit_servers if s not in available]
        if unknown:
            fail(f"unknown servers: {unknown}. available: {available}")
            sys.exit(1)
        target_servers = explicit_servers
        sel_prompt = None
    elif use_all:
        target_servers = available
        sel_prompt = None
    elif selection_prompt:
        target_servers = None
        sel_prompt = selection_prompt
    else:
        fail("specify one of: --server, --all, or pass a prompt for auto-selection")
        sys.exit(1)

    hr("Building agent")
    if target_servers:
        info(f"environment: {environment or '<all>'}")
        info(f"connectors:  {', '.join(target_servers)}")
    else:
        info(f"environment: {environment or '<all>'}")
        info("connectors:  <auto-select via prompt>")
    info(f"model:       {model or '<default>'}")
    info(f"max rounds:  {max_rounds}")

    agent = await build_agent_from_registry(
        environment=environment,
        server_names=target_servers,
        selection_prompt=sel_prompt,
        model=model,
        instructor_model=instructor_model,
        max_tool_rounds=max_rounds,
        verbose=verbose,
    )
    ok("agent built")
    return agent


# ── Run modes ─────────────────────────────────────────────────────────────────

async def run_one_shot(
    agent: MCPAgent,
    prompt: str,
    fs_roots: list[str],
    *,
    show_prompt: bool = False,
) -> int:
    full_prompt = prepend_filesystem_context(prompt, fs_roots)

    hr("Prompt")
    if show_prompt and full_prompt != prompt:
        # Show exactly what the agent receives
        print(full_prompt)
    else:
        print(prompt)
        if fs_roots and full_prompt != prompt:
            info("(prepended filesystem context: 1 root(s) — use --show-prompt to view)")

    hr("Tool trace")
    try:
        response = await agent.run(full_prompt)
    except Exception as exc:
        fail(f"agent error: {exc}")
        import traceback
        traceback.print_exc()
        return 2

    hr("Final response")
    print(f"{BOLD}{response.final_text}{RESET}")

    hr("Summary")
    info(f"{len(response.tool_executions)} tool execution(s)")
    for ex in response.tool_executions:
        info(f"  - {ex.framework_name} (server={ex.server_name})")
    return 0


async def run_interactive(
    agent: MCPAgent,
    fs_roots: list[str],
    *,
    show_prompt: bool = False,
) -> int:
    hr("Interactive mode")
    info("Type a prompt and press Enter. Empty line or Ctrl-D to exit.")
    if fs_roots:
        info(f"filesystem scope: {', '.join(fs_roots)}")

    turn = 1
    while True:
        try:
            print(f"\n{CYAN}[{turn}] >{RESET} ", end="", flush=True)
            line = sys.stdin.readline()
        except KeyboardInterrupt:
            break
        if not line:
            break
        prompt = line.rstrip("\n").strip()
        if not prompt:
            break

        full_prompt = prepend_filesystem_context(prompt, fs_roots)
        if show_prompt and full_prompt != prompt:
            hr("Sent prompt")
            print(full_prompt)

        hr("Tool trace")
        try:
            response = await agent.run(full_prompt)
        except Exception as exc:
            fail(f"turn {turn} error: {exc}")
            continue

        hr(f"Response (turn {turn})")
        print(f"{BOLD}{response.final_text}{RESET}")
        turn += 1

    info("\ngoodbye")
    return 0


# ── Entry ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run an MCP agent against a prompt, with tool-call visibility.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "prompt", nargs="?",
        help="The prompt to run. Omit when using --interactive or --stdin.",
    )
    parser.add_argument(
        "--server", "-s", action="append", dest="servers", default=[],
        help="Limit to this connector. Repeat to use several. "
             "Default: auto-select from prompt.",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Connect every available connector in the environment.",
    )
    parser.add_argument(
        "--environment", "-e", default="dev",
        choices=["dev", "semi-prod", "prod"],
        help="Registry environment scope (default: dev).",
    )
    parser.add_argument(
        "--model", "-m",
        help="Override the LLM model. Default: registry's default.",
    )
    parser.add_argument(
        "--instructor-model",
        help="Override the model used for connector selection.",
    )
    parser.add_argument(
        "--max-rounds", type=int, default=10,
        help="Maximum tool-calling rounds the agent can take (default: 10).",
    )
    parser.add_argument(
        "--interactive", "-i", action="store_true",
        help="Multi-turn REPL after agent is built. Connectors stay live across turns.",
    )
    parser.add_argument(
        "--stdin", action="store_true",
        help="Read the prompt from stdin instead of an argument.",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Pass verbose=True to the agent loop (extra internal logs).",
    )
    parser.add_argument(
        "--no-trace", action="store_true",
        help="Suppress the per-tool-call trace output.",
    )
    parser.add_argument(
        "--full-output", action="store_true",
        help="Disable truncation of tool args/results in the trace.",
    )
    parser.add_argument(
        "--show-prompt", action="store_true",
        help="Print the full prompt sent to the agent, including any prepended context.",
    )

    args = parser.parse_args()

    # Resolve prompt source
    if args.stdin:
        prompt = sys.stdin.read().strip()
        if not prompt:
            fail("no prompt on stdin")
            return 1
    else:
        prompt = args.prompt

    if not args.interactive and not prompt:
        fail("provide a prompt or use --interactive / --stdin")
        return 1

    # If no explicit servers and no --all, the prompt is used for auto-selection
    selection_prompt = None
    if not args.servers and not args.all:
        selection_prompt = prompt

    return asyncio.run(_run(args, prompt, selection_prompt))


async def _run(args, prompt: str | None, selection_prompt: str | None) -> int:
    agent = await build(
        environment=args.environment,
        explicit_servers=args.servers or None,
        selection_prompt=selection_prompt,
        use_all=args.all,
        model=args.model,
        instructor_model=args.instructor_model,
        max_rounds=args.max_rounds,
        verbose=args.verbose,
    )

    # Load capabilities once so per-server report and fs discovery
    # both work, and so neither pollutes the visible tool trace.
    if await ensure_capabilities_loaded(agent):
        report_connected_servers(agent)

    fs_roots = await discover_filesystem_roots(agent)
    if fs_roots:
        ok(f"filesystem scope discovered: {', '.join(fs_roots)}")

    if not args.no_trace:
        patch_agent_logging(agent, full_output=args.full_output)

    try:
        if args.interactive:
            return await run_interactive(agent, fs_roots, show_prompt=args.show_prompt)
        return await run_one_shot(agent, prompt, fs_roots, show_prompt=args.show_prompt)
    finally:
        with _suppress():
            await agent.cleanup()


from contextlib import contextmanager


@contextmanager
def _suppress():
    try:
        yield
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
