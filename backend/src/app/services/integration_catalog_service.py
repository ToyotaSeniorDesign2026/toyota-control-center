from __future__ import annotations

from control_center.registry import RegistryManager


def list_repo_connection_bundles(environment: str = "dev") -> dict[str, list[dict]]:
    manager = RegistryManager(environment=environment)
    available_server_names = set(manager.get_available_servers_list())

    items: list[dict] = []

    if "github" in available_server_names:
        companion_servers = [
            server_name
            for server_name in ("filesystem", "fastmcp-docs", "fetch")
            if server_name in available_server_names
        ]
        items.append(
            {
                "id": "github-repo-workspace",
                "title": "GitHub Repo Workspace",
                "summary": (
                    "Connect a GitHub repository once, then reuse that repo context across "
                    "chat-driven MCP workflows and future multi-server tasks like dbt model work."
                ),
                "primary_server": "github",
                "server_names": ["github", *companion_servers],
                "companion_servers": companion_servers,
                "manual_connection_supported": True,
                "chat_connection_supported": True,
                "resource_type": "repo_connection",
                "required_config_fields": ["repo", "provider"],
                "optional_config_fields": [
                    "ref",
                    "path",
                    "default_branch",
                    "installation_owner",
                    "server_names",
                    "primary_server",
                    "companion_servers",
                    "connection_mode",
                    "description",
                ],
                "recommended_use_cases": [
                    "Inspect repository structure and files from chat",
                    "Prepare multi-MCP repository workflows for dbt model edits",
                    "Pair repo context with docs or filesystem servers for implementation tasks",
                ],
            }
        )

    return {"items": items}
