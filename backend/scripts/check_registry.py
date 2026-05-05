
"""Validate the MCP registry and exercise per-server config loading.

Usage:
    uv run scripts/check_registry.py
    uv run scripts/check_registry.py --server github
    uv run scripts/check_registry.py --environment prod
    uv run scripts/check_registry.py --show
    uv run scripts/check_registry.py --server github --connect

Run after editing:
    backend/src/control_center/registry/registry.json
    backend/mcp_servers/configs/*.json

Exit code 0 = all checks passed. Non-zero = at least one failure.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import traceback
from typing import Any

from control_center.registry import RegistryManager


# ── Output helpers ────────────────────────────────────────────────────────────

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
RESET = "\033[0m"


def ok(msg: str) -> None:
    print(f"{GREEN}✓{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"{RED}✗{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}!{RESET} {msg}")


def info(msg: str) -> None:
    print(f"{DIM}{msg}{RESET}")


# ── Checks ────────────────────────────────────────────────────────────────────

def load_registry(environment: str | None) -> RegistryManager:
    """Step 1: registry.json parses + cross-references resolve."""
    print(f"\n{DIM}── Loading registry ──{RESET}")
    try:
        manager = RegistryManager(environment=environment)
    except Exception as exc:
        fail(f"failed to load registry: {exc}")
        traceback.print_exc()
        sys.exit(1)
    env_label = environment or "<all>"
    ok(f"registry loaded (environment={env_label})")
    return manager


def list_servers(manager: RegistryManager) -> list[str]:
    """Step 2: enumerate active servers in scope."""
    print(f"\n{DIM}── Available servers ──{RESET}")
    servers = manager.get_available_servers()
    if not servers:
        warn("no active servers in this environment")
        return []
    for name, server in sorted(servers.items()):
        envs = ",".join(sorted(server.allowed_environments))
        tags = f" [{','.join(server.tags)}]" if server.tags else ""
        ok(f"{name:<30} envs={envs}{tags}")
    return list(servers)


def check_server_config(manager: RegistryManager, name: str) -> dict[str, Any] | None:
    """Step 3: resolve and load this server's config file."""
    try:
        config = manager.get_server_config(name)
    except Exception as exc:
        fail(f"{name}: {exc}")
        return None
    ok(f"{name}: config resolved ({len(config)} top-level keys)")
    return config


def show_config(name: str, config: dict[str, Any]) -> None:
    """Pretty-print a resolved config (env vars expanded, overrides applied)."""
    print(f"\n{DIM}── Resolved config: {name} ──{RESET}")
    print(json.dumps(config, indent=2, default=str))


# ── MCP connection probe (optional) ───────────────────────────────────────────

DEFAULT_TOOL_CAP = 15


async def probe_mcp_connection(name: str, config: dict[str, Any], *, full_tool_list: bool) -> bool:
    """Connect to the MCP server and list its tools. Verifies the server actually starts."""
    try:
        from control_center.mcp import LLMClient
    except ImportError:
        fail("mcp package not installed — skip --connect")
        return False

    print(f"\n{DIM}── Connecting to {name} ──{RESET}")
    client = LLMClient()
    try:
        await client.connect_to_server(name, config)
        tools = await client.list_tools(name)
        ok(f"{name}: connected, {len(tools)} tools exposed")

        cap = len(tools) if full_tool_list else DEFAULT_TOOL_CAP
        for tool in tools[:cap]:
            tool_name = getattr(tool, "name", str(tool))
            print(f"    - {tool_name}")
        if len(tools) > cap:
            info(f"    ... and {len(tools) - cap} more (use --full-tool-list to see all)")
        return True
    except Exception as exc:
        fail(f"{name}: connection failed: {exc}")
        return False
    finally:
        try:
            await client.cleanup()
        except Exception:
            pass


# ── Entry ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the MCP registry and per-server configs."
    )
    parser.add_argument(
        "--environment", "-e",
        choices=["dev", "semi-prod", "prod"],
        default=None,
        help="Filter to one environment (default: show all environments).",
    )
    parser.add_argument(
        "--server", "-s",
        help="Check only this server (default: all active in scope).",
    )
    parser.add_argument(
        "--show", action="store_true",
        help="Print each server's resolved config.",
    )
    parser.add_argument(
        "--connect", action="store_true",
        help="Actually start each MCP server and list its tools (slower).",
    )
    parser.add_argument(
        "--full-tool-list", action="store_true",
        help=f"List every tool exposed by each server (default: cap at {DEFAULT_TOOL_CAP}).",
    )
    args = parser.parse_args()

    manager = load_registry(args.environment)

    # Pick targets
    if args.server:
        if args.server not in manager.get_available_servers():
            fail(f"server '{args.server}' not active in this environment")
            return 1
        targets = [args.server]
    else:
        targets = list_servers(manager)
        if not targets:
            return 1

    # Resolve configs
    print(f"\n{DIM}── Resolving configs ──{RESET}")
    failed = 0
    resolved: dict[str, dict[str, Any]] = {}
    for name in targets:
        config = check_server_config(manager, name)
        if config is None:
            failed += 1
            continue
        resolved[name] = config
        if args.show:
            show_config(name, config)

    # Optional connection probe
    if args.connect and resolved:
        results = asyncio.run(_probe_all(resolved, full_tool_list=args.full_tool_list))
        failed += sum(1 for ok_ in results if not ok_)

    # Summary
    print(f"\n{DIM}── Summary ──{RESET}")
    total = len(targets)
    passed = total - failed
    if failed == 0:
        ok(f"{passed}/{total} servers passed")
        return 0
    fail(f"{failed}/{total} servers failed")
    return 1


async def _probe_all(
    resolved: dict[str, dict[str, Any]],
    *,
    full_tool_list: bool,
) -> list[bool]:
    return [
        await probe_mcp_connection(name, cfg, full_tool_list=full_tool_list)
        for name, cfg in resolved.items()
    ]


if __name__ == "__main__":
    sys.exit(main())
