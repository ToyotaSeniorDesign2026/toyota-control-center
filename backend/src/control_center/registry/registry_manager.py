from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Annotated, Any, Iterable, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


class ConfigTypeDef(BaseModel):
    """Definition for a supported config type. Includes optional `description` and the name of its `parser` file."""
    description: str | None = None
    parser: str


class EnvironmentDef(BaseModel):
    """Definition for a named deployment/runtime environment."""
    description: str | None = None


class ApprovedServerDef(BaseModel):
    """
    Approved MCP server entry from the registry.

    Example:
        {
            "description": "...",
            "allowed_environments": ["dev", "semi-prod"],
            "config_path": "configs/filesystem.json",
            "config_type": "standard",
            "version": "1.0",
            "tags": ["filesystem", "local"],
            "active": true,
            "notes": "...",
            "environment_overrides": {
                "dev": {"timeout": 60}
            },
            "job_type": "repo_connection",
            "required_fields": ["repo"],
            "optional_fields": ["ref", "path"]
        }
    """

    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    display_name: str | None = None
    allowed_environments: Annotated[list[str], Field(min_length=1)]
    config_path: str
    config_type: str = "standard"
    version: str | None = None
    tags: list[str] = Field(default_factory=list)
    active: bool
    notes: str | None = None
    environment_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    job_type: str | None = None
    required_fields: list[str] = Field(default_factory=list)
    optional_fields: list[str] = Field(default_factory=list)
    drivers: dict[str, Any] | None = None

    @field_validator("config_type", mode="before")
    def normalize_config_type(cls, value: str | None) -> str:
        if value is None:
            return "standard"
        return str(value).strip().lower() or "standard"

    @field_validator("allowed_environments", mode="before")
    def normalize_allowed_environments(cls, value: list[str]) -> list[str]:
        if not isinstance(value, list):
            raise ValueError("allowed_environments must be a list of strings")
        return list({str(item).strip().lower() for item in value if str(item).strip()})

    @field_validator("environment_overrides", mode="before")
    def normalize_environment_override_keys(cls, value: dict[str, Any]) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("environment_overrides must be a dictionary")
        return {str(key).strip().lower(): val for key, val in value.items()}

    @field_validator("tags", mode="before")
    def normalize_tags(cls, value: list[str]) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("tags must be a list of strings")
        return list({str(item).strip().lower() for item in value if str(item).strip()})


class Registry(BaseModel):
    """
    Full registry model representing the entire registry.json file.

    Cross-reference validation is handled at the top level so that:
    - each server's `config_type` must exist in `config_types`
    - each server's `allowed_environments` must exist in `environments`
    - each environment override key must exist in `environments`
    - each environment override key must also be listed in the server's `allowed_environments`
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    config_types: dict[str, ConfigTypeDef]
    environments: dict[str, EnvironmentDef]
    approved_servers: dict[str, ApprovedServerDef]
    universal_job_fields: dict[str, Any] | None = None

    @field_validator("config_types", mode="before")
    def normalize_config_type_keys(cls, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("config_types must be a dictionary")
        return {str(key).strip().lower(): val for key, val in value.items()}

    @field_validator("environments", mode="before")
    def normalize_environment_keys(cls, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("environments must be a dictionary")
        return {str(key).strip().lower(): val for key, val in value.items()}

    @field_validator("approved_servers", mode="before")
    def normalize_approved_servers_keys(cls, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("approved_servers must be a dictionary")
        return {str(key).strip().lower(): val for key, val in value.items()}

    @model_validator(mode="after")
    def validate_cross_references(self) -> Self:
        valid_config_types = set(self.config_types.keys())
        valid_env_types = set(self.environments.keys())

        if "standard" not in valid_config_types:
            raise ValueError("config_types must define a 'standard' entry")

        for name, server in self.approved_servers.items():

            # Validate config_type exists in global config_types
            if server.config_type not in valid_config_types:
                raise ValueError(
                    f"Server '{name}' uses unknown config_type: '{server.config_type}'; "
                    f"expected one of {valid_config_types}"
                )

            # Expand wildcard ["*"] to all valid environments
            if server.allowed_environments == ["*"]:
                server.allowed_environments = list(valid_env_types)
            else:
                # Validate allowed_environments exist in global environments
                invalid_envs = [env for env in server.allowed_environments if env not in valid_env_types]
                if invalid_envs:
                    raise ValueError(
                        f"Server '{name}' references undefined environment(s): {invalid_envs}; "
                        f"expected one of {valid_env_types}"
                    )

            # Validate environment_overrides keys exist in global environments
            override_envs = list(server.environment_overrides.keys())
            invalid_override_envs = [env for env in override_envs if env not in valid_env_types]
            if invalid_override_envs:
                raise ValueError(
                    f"Server '{name}' references undefined override environment(s): {invalid_override_envs}; "
                    f"expected one of {valid_env_types}"
                )
            # Validate environment_overrides keys exist in allowed_environments
            disallowed_override_envs = [env for env in override_envs if env not in server.allowed_environments]
            if disallowed_override_envs:
                raise ValueError(
                    f"Server '{name}' has environment_overrides for disallowed environment(s): "
                    f"{disallowed_override_envs}; allowed_environments are {server.allowed_environments}"
                )

        return self

    @classmethod
    def load(cls, path: str | Path) -> Self:
        """Load and parse the registry from a JSON file."""
        file_path = Path(path)
        try:
            with file_path.open("r", encoding="utf-8") as f:
                return cls.model_validate(json.load(f))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in registry file: {file_path}") from exc
        except ValidationError as exc:
            raise ValueError(f"Invalid registry data in file: {file_path}") from exc
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Registry file not found: {file_path}") from exc
        except OSError as exc:
            raise ValueError(f"Failed to read registry file: {file_path}") from exc

    def get_server(self, name: str) -> ApprovedServerDef:
        """Return an approved server by name."""
        try:
            return self.approved_servers[name.strip().lower()]
        except KeyError as exc:
            raise KeyError(f"Unknown or unapproved server: {name!r}") from exc


class RegistryManager:
    """
    Manager class to handle registry access and environment scoping.

    This class provides methods to retrieve available servers based on the current environment
    and to get the config for a specific server, applying any environment-specific overrides.
    """

    def __init__(self, environment: str | None = None):

        self._registry = self._load_registry()
        self.environment = environment.lower().strip() if environment else None

        # Validate that the environment exists if one was provided
        if self.environment and self.environment not in self._registry.environments:
            valid = list(self._registry.environments.keys())
            raise ValueError(f"Environment '{self.environment}' not defined in registry. Valid: {valid}")

    @staticmethod
    def _load_registry() -> Registry:
        """Internal method to load the registry from the default file path."""
        return Registry.load(Path(__file__).resolve().parent / "registry.json")

    @staticmethod
    def _get_project_root() -> Path:
        """Helper method to get the project root directory."""
        return Path(__file__).resolve().parents[4]

    @staticmethod
    def _get_mcp_servers_dir() -> Path:
        override = os.getenv("CONTROL_CENTER_MCP_CONFIG_DIR")
        if override:
            return Path(override).resolve()
        return Path(__file__).resolve().parents[3] / "mcp_servers"

    def get_available_servers(self) -> dict[str, ApprovedServerDef]:
        """Returns all servers active and allowed in the current environment."""
        servers = self._registry.approved_servers

        if self.environment:
            return {
                name: server for name, server in servers.items()
                if self.environment in server.allowed_environments and server.active
            }

        return {name: server for name, server in servers.items() if server.active}

    def get_available_servers_list(self) -> list[str]:
        """Returns all servers active and allowed in the current environment."""
        servers = self._registry.approved_servers

        if self.environment:
            return [
                name for name, server in servers.items()
                if self.environment in server.allowed_environments and server.active
            ]

        return [name for name, server in servers.items() if server.active]

    @staticmethod
    def _merge_dicts(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
        merged = deepcopy(base)
        for key, value in overrides.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = RegistryManager._merge_dicts(merged[key], value)
            else:
                merged[key] = deepcopy(value)
        return merged

    @staticmethod
    def _expand_env_vars(value: Any) -> Any:

        if isinstance(value, str):
            backend_root = str(Path(__file__).resolve().parents[3])
            repo_root = str(Path(__file__).resolve().parents[4])
            expanded = (
                value  # Inject special placeholders for important paths, allowing configs to be portable across envs
                .replace("${BACKEND_ROOT}", backend_root)
                .replace("${REPO_ROOT}", repo_root)
            )
            expanded = os.path.expandvars(expanded)  # Standard OS env var expansion ($VAR and ${VAR})
            expanded = re.sub(
                r"\$\{([^}]+)\}",  # Catch any ${VAR} that os.path.expandvars missed
                lambda match: os.getenv(match.group(1), match.group(0)),
                expanded,
            )
            if "${" in expanded:  # Fail loud on unresolved placeholders, which likely indicates a missing env var
                raise ValueError(
                    f"unresolved env var in registry config: {expanded!r}. "
                    f"Set the variable in the environment or add it to .env."
                )
            return expanded

        if isinstance(value, list):
            return [RegistryManager._expand_env_vars(item) for item in value]

        if isinstance(value, dict):
            return {key: RegistryManager._expand_env_vars(item) for key, item in value.items()}

        return value

    def _resolve_config_path(self, config_path: str) -> Path:
        candidate = Path(config_path)
        if candidate.is_absolute():
            return candidate

        if config_path.startswith("configs/"):
            return self._get_mcp_servers_dir() / config_path

        return (self._get_project_root() / config_path).resolve()

    def _load_raw_server_config(self, server_name: str, server: ApprovedServerDef) -> dict[str, Any]:
        config_path = self._resolve_config_path(server.config_path)

        try:
            with config_path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Config file not found for server '{server_name}': {config_path}") from exc
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in config file for server '{server_name}': {config_path}") from exc

        if not isinstance(payload, dict):
            raise ValueError(
                f"Config file for server '{server_name}' must contain a JSON object: {config_path}"
            )

        if "mcpServers" in payload:
            mcp_servers = payload.get("mcpServers")
            if not isinstance(mcp_servers, dict):
                raise ValueError(
                    f"Config file for server '{server_name}' has invalid 'mcpServers' payload: {config_path}"
                )

            if server_name in mcp_servers:
                resolved = mcp_servers[server_name]
            elif len(mcp_servers) == 1:
                resolved = next(iter(mcp_servers.values()))
            else:
                raise KeyError(
                    f"Config file '{config_path}' defines multiple MCP servers and does not include '{server_name}'."
                )
        else:
            resolved = payload

        if not isinstance(resolved, dict):
            raise ValueError(f"Resolved config for server '{server_name}' must be a JSON object.")

        return deepcopy(resolved)

    def _should_set_mcp_servers_cwd(self, config: dict[str, Any]) -> bool:
        if config.get("cwd"):
            return False

        args = config.get("args", [])
        if not isinstance(args, list):
            return False

        for arg in args:
            if not isinstance(arg, str):
                continue
            normalized = arg.strip()
            if not normalized or Path(normalized).is_absolute():
                continue
            if normalized.startswith("internal/") or normalized.startswith("./internal/"):
                return True
            if normalized.endswith(".py"):
                return True

        return False

    def _apply_runtime_defaults(self, config: dict[str, Any]) -> dict[str, Any]:
        normalized = self._expand_env_vars(deepcopy(config))
        if self._should_set_mcp_servers_cwd(normalized):
            normalized["cwd"] = str(self._get_mcp_servers_dir())
        return normalized

    def get_server_config(self, server_name: str) -> dict[str, Any]:
        """Retrieves the base config and merges any environment-specific overrides."""
        server = self._registry.get_server(server_name)

        # Check environment access if scoped
        if self.environment and self.environment not in server.allowed_environments:
            raise PermissionError(f"Server '{server_name}' is not allowed in {self.environment}")
        if not server.active:
            raise PermissionError(f"Server '{server_name}' is not active")

        config = self._load_raw_server_config(server_name, server)
        if self.environment:
            overrides = server.environment_overrides.get(self.environment, {})
            config = self._merge_dicts(config, overrides)

        return self._apply_runtime_defaults(config)

    def get_server_configs(self, server_names: Iterable[str] | None = None) -> dict[str, dict[str, Any]]:
        """Resolve and normalize configs for one or more approved servers."""
        names = list(server_names) if server_names is not None else self.get_available_servers_list()
        return {name: self.get_server_config(name) for name in names}

    def get_server_bundle(self, server_names: Iterable[str] | None = None) -> dict[str, dict[str, dict[str, Any]]]:
        """Return configs in MCP bundle shape."""
        return {"mcpServers": self.get_server_configs(server_names)}
