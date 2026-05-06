
"""Validate the MCP registry and exercise per-server config loading.

Usage:
    uv run scripts/check_registry.py
    uv run scripts/check_registry.py --server github
    uv run scripts/check_registry.py --environment prod
    uv run scripts/check_registry.py --show
    uv run scripts/check_registry.py --server github --connect

Metadata dumps:
    uv run scripts/check_registry.py --dump-fields
    uv run scripts/check_registry.py --server playwright --dump-server
    uv run scripts/check_registry.py --server playwright --dump-tools
    uv run scripts/check_registry.py --server playwright --dump-tools --tool browser_navigate
    uv run scripts/check_registry.py --server playwright --dump-prompts --dump-resources
    uv run scripts/check_registry.py --dump-client                # aggregate across all
    uv run scripts/check_registry.py --server playwright --dump-all

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


# ── Metadata dumps ────────────────────────────────────────────────────────────

def _to_jsonable(obj: Any) -> Any:
    """Best-effort conversion to a JSON-serializable shape.

    Pydantic models -> dict via model_dump(mode="json"). Containers recursed.
    Anything else falls back to str().
    """
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        try:
            return dump(mode="json", exclude_none=False)
        except TypeError:
            return dump()  # older pydantic
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_to_jsonable(x) for x in obj]
    return str(obj)


def dump_mcp_type_fields() -> dict[str, Any]:
    """Walk mcp.types and return a {ModelName: {field: type_repr}} map.

    No connection required. Useful to know what fields the MCP spec
    actually exposes on Tool / Prompt / Resource / ToolAnnotations / etc.
    """
    try:
        import pydantic
        from mcp import types as mcp_types
    except ImportError as exc:
        return {"_error": f"missing dependency: {exc}"}

    catalog: dict[str, Any] = {}
    for attr_name in sorted(vars(mcp_types)):
        obj = getattr(mcp_types, attr_name)
        if not isinstance(obj, type):
            continue
        if not issubclass(obj, pydantic.BaseModel) or obj is pydantic.BaseModel:
            continue

        fields: dict[str, str] = {}
        for field_name, field_info in obj.model_fields.items():
            annotation = field_info.annotation
            ann_repr = getattr(annotation, "__name__", None) or str(annotation)
            required = "required" if field_info.is_required() else "optional"
            default = field_info.default
            default_repr = "" if default is pydantic.fields.PydanticUndefined else f" default={default!r}"
            fields[field_name] = f"{ann_repr} ({required}){default_repr}"

        catalog[attr_name] = {
            "doc": (obj.__doc__ or "").strip().split("\n")[0],
            "fields": fields,
        }
    return catalog


async def dump_server_block(client: Any, server_name: str) -> dict[str, Any]:
    """Per-server metadata: serverInfo, capabilities, instructions, counts."""
    init_result = client.get_server_info(server_name) if hasattr(client, "get_server_info") else None

    tools = await _safe_list(client.list_tools, server_name)
    prompts = await _safe_list(client.list_prompts, server_name)
    resources = await _safe_list(client.list_resources, server_name)

    return {
        "server": server_name,
        "initialize_result": _to_jsonable(init_result),
        "counts": {
            "tools": len(tools),
            "prompts": len(prompts),
            "resources": len(resources),
        },
    }


async def dump_tools_block(
    client: Any, server_name: str, *, only: str | None = None
) -> list[dict[str, Any]]:
    """Full Tool dumps (name, title, description, inputSchema, outputSchema, annotations, _meta)."""
    tools = await _safe_list(client.list_tools, server_name)
    if only:
        tools = [t for t in tools if getattr(t, "name", None) == only]
    return [_to_jsonable(t) for t in tools]


async def dump_prompts_block(client: Any, server_name: str) -> list[dict[str, Any]]:
    prompts = await _safe_list(client.list_prompts, server_name)
    return [_to_jsonable(p) for p in prompts]


async def dump_resources_block(client: Any, server_name: str) -> list[dict[str, Any]]:
    resources = await _safe_list(client.list_resources, server_name)
    return [_to_jsonable(r) for r in resources]


async def dump_client_aggregate(client: Any, server_names: list[str]) -> dict[str, Any]:
    """Cross-server aggregate: totals, advertised capability flags, per-server summary."""
    totals = {"tools": 0, "prompts": 0, "resources": 0}
    capability_flags: set[str] = set()
    by_server: list[dict[str, Any]] = []

    for name in server_names:
        tools = await _safe_list(client.list_tools, name)
        prompts = await _safe_list(client.list_prompts, name)
        resources = await _safe_list(client.list_resources, name)
        totals["tools"] += len(tools)
        totals["prompts"] += len(prompts)
        totals["resources"] += len(resources)

        init_result = client.get_server_info(name) if hasattr(client, "get_server_info") else None
        caps = _to_jsonable(getattr(init_result, "capabilities", None)) or {}
        if isinstance(caps, dict):
            for flag, value in caps.items():
                if value:
                    capability_flags.add(flag)

        server_info = _to_jsonable(getattr(init_result, "serverInfo", None)) or {}
        by_server.append({
            "server": name,
            "tools": len(tools),
            "prompts": len(prompts),
            "resources": len(resources),
            "name": server_info.get("name") if isinstance(server_info, dict) else None,
            "version": server_info.get("version") if isinstance(server_info, dict) else None,
            "protocol_version": getattr(init_result, "protocolVersion", None),
        })

    return {
        "connected_servers": server_names,
        "totals": totals,
        "advertised_capability_flags": sorted(capability_flags),
        "by_server": by_server,
    }


async def _safe_list(coro_fn, server_name: str) -> list[Any]:
    try:
        return list(await coro_fn(server_name) or [])
    except Exception:
        return []


def _emit(label: str, payload: Any) -> None:
    print(f"\n{DIM}── {label} ──{RESET}")
    print(json.dumps(payload, indent=2, default=str))


# ── MCP connection probe ──────────────────────────────────────────────────────

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

    # Dump flags. --dump-fields is offline; the rest imply --connect.
    parser.add_argument(
        "--dump-fields", action="store_true",
        help="Dump every mcp.types pydantic model and its fields. No connection needed.",
    )
    parser.add_argument(
        "--dump-server", action="store_true",
        help="Dump per-server InitializeResult (serverInfo, capabilities, instructions, counts). Implies --connect.",
    )
    parser.add_argument(
        "--dump-tools", action="store_true",
        help="Dump every Tool from each target server in full (name, title, description, inputSchema, outputSchema, annotations, _meta). Implies --connect.",
    )
    parser.add_argument(
        "--dump-prompts", action="store_true",
        help="Dump every Prompt from each target server. Implies --connect.",
    )
    parser.add_argument(
        "--dump-resources", action="store_true",
        help="Dump every Resource from each target server. Implies --connect.",
    )
    parser.add_argument(
        "--dump-client", action="store_true",
        help="Aggregate dump across all target servers (totals, advertised capability flags). Implies --connect.",
    )
    parser.add_argument(
        "--dump-all", action="store_true",
        help="Combine --dump-fields, --dump-server, --dump-tools, --dump-prompts, --dump-resources, --dump-client.",
    )
    parser.add_argument(
        "--tool",
        help="When dumping tools, restrict to this tool name.",
    )

    args = parser.parse_args()
    if args.dump_all:
        args.dump_fields = True
        args.dump_server = True
        args.dump_tools = True
        args.dump_prompts = True
        args.dump_resources = True
        args.dump_client = True

    needs_connection = any([
        args.connect,
        args.dump_server,
        args.dump_tools,
        args.dump_prompts,
        args.dump_resources,
        args.dump_client,
    ])
    if needs_connection:
        args.connect = True

    # Offline dump first — no registry/connection needed.
    if args.dump_fields:
        _emit("MCP type catalogue (mcp.types)", dump_mcp_type_fields())

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

    # Optional connection probe + live dumps (single client, all servers).
    if args.connect and resolved:
        results = asyncio.run(_probe_and_dump(resolved, args=args))
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


async def _probe_and_dump(
    resolved: dict[str, dict[str, Any]],
    *,
    args: argparse.Namespace,
) -> list[bool]:
    """Open one LLMClient, connect every target server, probe + dump, clean up.

    A single client lets `--dump-client` aggregate across all servers in one
    pass, and avoids re-paying connection cost per scope.
    """
    try:
        from control_center.mcp import LLMClient
    except ImportError:
        fail("mcp package not installed — skip --connect")
        return [False] * len(resolved)

    results: list[bool] = []
    connected: list[str] = []
    client = LLMClient()
    try:
        for name, cfg in resolved.items():
            print(f"\n{DIM}── Connecting to {name} ──{RESET}")
            try:
                await client.connect_to_server(name, cfg)
            except Exception as exc:
                fail(f"{name}: connection failed: {exc}")
                results.append(False)
                continue

            try:
                tools = await client.list_tools(name)
            except Exception as exc:
                fail(f"{name}: list_tools failed: {exc}")
                results.append(False)
                continue

            ok(f"{name}: connected, {len(tools)} tools exposed")
            cap = len(tools) if args.full_tool_list else DEFAULT_TOOL_CAP
            for tool in tools[:cap]:
                print(f"    - {getattr(tool, 'name', str(tool))}")
            if len(tools) > cap:
                info(f"    ... and {len(tools) - cap} more (use --full-tool-list to see all)")

            connected.append(name)
            results.append(True)

            if args.dump_server:
                _emit(f"{name} — server metadata", await dump_server_block(client, name))
            if args.dump_tools:
                _emit(
                    f"{name} — tools" + (f" [{args.tool}]" if args.tool else ""),
                    await dump_tools_block(client, name, only=args.tool),
                )
            if args.dump_prompts:
                _emit(f"{name} — prompts", await dump_prompts_block(client, name))
            if args.dump_resources:
                _emit(f"{name} — resources", await dump_resources_block(client, name))

        if args.dump_client and connected:
            _emit("Client aggregate", await dump_client_aggregate(client, connected))
    finally:
        try:
            await client.cleanup()
        except Exception:
            pass
    return results


if __name__ == "__main__":
    sys.exit(main())
