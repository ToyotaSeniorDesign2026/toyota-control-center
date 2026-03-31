from __future__ import annotations

"""Resource-type registry and contract validation for type-safe resource configs/capabilities."""

from fastapi import HTTPException, status


_RESOURCE_TYPE_REGISTRY = [
    {
        "type": "sql",
        "kind": "runtime",
        "required_config_schema": {"required": [], "optional": ["query", "schedule", "connection_id", "repo", "path", "ref"]},
        "supported_resource_actions": ["activate", "pause", "archive"],
        "run_capabilities": {
            "supports_retry": True,
            "supports_cancel": True,
            "supports_schedule": True,
            "supports_heartbeat": False,
        },
        "approval_defaults": {"required_above_risk_score": 60, "always_required_environments": ["prod"]},
    },
    {
        "type": "mcp",
        "kind": "runtime",
        "required_config_schema": {"required": [], "optional": ["prompt", "description", "schedule", "max_results", "connection_id"]},
        "supported_resource_actions": ["activate", "pause", "archive"],
        "run_capabilities": {
            "supports_retry": True,
            "supports_cancel": True,
            "supports_schedule": True,
            "supports_heartbeat": False,
        },
        "approval_defaults": {"required_above_risk_score": 60, "always_required_environments": ["prod"]},
    },
    {
        "type": "excel",
        "kind": "runtime",
        "required_config_schema": {"required": [], "optional": ["brief", "schedule", "connection_id"]},
        "supported_resource_actions": ["activate", "pause", "archive"],
        "run_capabilities": {
            "supports_retry": True,
            "supports_cancel": True,
            "supports_schedule": True,
            "supports_heartbeat": False,
        },
        "approval_defaults": {"required_above_risk_score": 60, "always_required_environments": ["prod"]},
    },
    {
        "type": "powerpoint",
        "kind": "runtime",
        "required_config_schema": {"required": [], "optional": ["brief", "schedule", "connection_id"]},
        "supported_resource_actions": ["activate", "pause", "archive"],
        "run_capabilities": {
            "supports_retry": True,
            "supports_cancel": True,
            "supports_schedule": True,
            "supports_heartbeat": False,
        },
        "approval_defaults": {"required_above_risk_score": 60, "always_required_environments": ["prod"]},
    },
    {
        "type": "research",
        "kind": "runtime",
        "required_config_schema": {"required": ["topic"], "optional": ["max_results", "schedule"]},
        "supported_resource_actions": ["activate", "pause", "archive"],
        "run_capabilities": {
            "supports_retry": True,
            "supports_cancel": True,
            "supports_schedule": True,
            "supports_heartbeat": True,
        },
        "approval_defaults": {"required_above_risk_score": 60, "always_required_environments": ["prod"]},
    },
    {
        "type": "agent",
        "kind": "runtime",
        "required_config_schema": {"required": ["entrypoint"], "optional": ["schedule", "timeout_seconds"]},
        "supported_resource_actions": ["activate", "pause", "archive"],
        "run_capabilities": {
            "supports_retry": True,
            "supports_cancel": True,
            "supports_schedule": True,
            "supports_heartbeat": True,
        },
        "approval_defaults": {"required_above_risk_score": 60, "always_required_environments": ["prod"]},
    },
    {
        "type": "airflow_dag",
        "kind": "runtime",
        "required_config_schema": {"required": ["dag_id", "api_base_url"], "optional": ["schedule"]},
        "supported_resource_actions": ["activate", "pause", "archive"],
        "run_capabilities": {
            "supports_retry": True,
            "supports_cancel": True,
            "supports_schedule": True,
            "supports_heartbeat": True,
        },
        "approval_defaults": {"required_above_risk_score": 60, "always_required_environments": ["prod"]},
    },
    {
        "type": "dbt_job",
        "kind": "runtime",
        "required_config_schema": {"required": ["job_id", "account_id"], "optional": ["schedule"]},
        "supported_resource_actions": ["activate", "pause", "archive"],
        "run_capabilities": {
            "supports_retry": True,
            "supports_cancel": True,
            "supports_schedule": True,
            "supports_heartbeat": True,
        },
        "approval_defaults": {"required_above_risk_score": 60, "always_required_environments": ["prod"]},
    },
    {
        "type": "pipeline",
        "kind": "runtime",
        "required_config_schema": {"required": [], "optional": ["schedule", "pipeline_id"]},
        "supported_resource_actions": ["activate", "pause", "archive"],
        "run_capabilities": {
            "supports_retry": True,
            "supports_cancel": True,
            "supports_schedule": True,
            "supports_heartbeat": True,
        },
        "approval_defaults": {"required_above_risk_score": 60, "always_required_environments": ["prod"]},
    },
    {
        "type": "bi_task",
        "kind": "runtime",
        "required_config_schema": {"required": [], "optional": ["schedule", "workspace_id"]},
        "supported_resource_actions": ["activate", "pause", "archive"],
        "run_capabilities": {
            "supports_retry": True,
            "supports_cancel": True,
            "supports_schedule": True,
            "supports_heartbeat": False,
        },
        "approval_defaults": {"required_above_risk_score": 60, "always_required_environments": ["prod"]},
    },
    {
        "type": "powerbi_report",
        "kind": "artifact",
        "required_config_schema": {"required": ["workspace_id", "dataset_id"], "optional": ["version"]},
        "supported_resource_actions": ["deploy", "publish", "archive"],
        "run_capabilities": {
            "supports_retry": True,
            "supports_cancel": False,
            "supports_schedule": False,
            "supports_heartbeat": False,
        },
        "approval_defaults": {"required_above_risk_score": 70, "always_required_environments": ["prod"]},
    },
    {
        "type": "excel_task",
        "kind": "artifact",
        "required_config_schema": {"required": ["drive_id", "workbook_item_id"], "optional": ["version"]},
        "supported_resource_actions": ["deploy", "publish", "archive"],
        "run_capabilities": {
            "supports_retry": True,
            "supports_cancel": False,
            "supports_schedule": False,
            "supports_heartbeat": False,
        },
        "approval_defaults": {"required_above_risk_score": 70, "always_required_environments": ["prod"]},
    },
    {
        "type": "powerpoint_task",
        "kind": "artifact",
        "required_config_schema": {"required": ["drive_id", "presentation_item_id"], "optional": ["version"]},
        "supported_resource_actions": ["deploy", "publish", "archive"],
        "run_capabilities": {
            "supports_retry": True,
            "supports_cancel": False,
            "supports_schedule": False,
            "supports_heartbeat": False,
        },
        "approval_defaults": {"required_above_risk_score": 70, "always_required_environments": ["prod"]},
    },
    {
        "type": "report",
        "kind": "artifact",
        "required_config_schema": {"required": [], "optional": ["version", "workspace_id", "dataset_id"]},
        "supported_resource_actions": ["deploy", "publish", "archive"],
        "run_capabilities": {
            "supports_retry": True,
            "supports_cancel": False,
            "supports_schedule": False,
            "supports_heartbeat": False,
        },
        "approval_defaults": {"required_above_risk_score": 70, "always_required_environments": ["prod"]},
    },
]


def list_resource_type_contracts():
    return _RESOURCE_TYPE_REGISTRY


def get_resource_type_contract(resource_type: str) -> dict | None:
    resource_type_l = resource_type.lower().strip()
    for contract in _RESOURCE_TYPE_REGISTRY:
        if contract["type"].lower() == resource_type_l:
            return contract
    return None


def validate_resource_contract(kind: str, resource_type: str, config: dict):
    contract = get_resource_type_contract(resource_type)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported resource type '{resource_type}'",
        )

    if contract["kind"] != kind:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Type '{resource_type}' requires kind '{contract['kind']}'",
        )

    schema = contract["required_config_schema"]
    required = set(schema.get("required", []))
    optional = set(schema.get("optional", []))
    allowed = required.union(optional)
    cfg = config or {}

    missing = sorted(k for k in required if k not in cfg or cfg.get(k) in {None, ""})
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing required config keys for '{resource_type}': {', '.join(missing)}",
        )

    internal_keys = {"last_heartbeat_at"}
    extra = sorted(k for k in cfg.keys() if k not in allowed and k not in internal_keys)
    if extra:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported config keys for '{resource_type}': {', '.join(extra)}",
        )

    return contract
