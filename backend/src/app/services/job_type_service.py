from __future__ import annotations

"""Job-type discovery and validation derived from the connector registry.

Known job types (sql, repo_connection, mcp) are defined as full JobTypeContract
instances in control_center.specs.known_contracts. Registry entries that map to
a known type return that contract directly. Unknown types get an auto-generated
contract with minimal metadata.
"""

from fastapi import HTTPException, status

from control_center.registry import RegistryManager
from control_center.specs import KNOWN_CONTRACTS
from control_center.specs.job_type import (
    CapabilityRequirement,
    GovernancePolicy,
    InputSchema,
    JobTypeContract,
    RunFeatures,
)

_VALID_KINDS = {"runtime", "artifact"}


def _auto_contract(
    job_type: str,
    *,
    display_name: str | None = None,
    description: str | None = None,
    required: list[str] | None = None,
    optional: list[str] | None = None,
    connector_types: list[str] | None = None,
) -> JobTypeContract:
    """Build a minimal contract for registry entries without a known definition."""
    kind_actions = ["activate", "pause", "archive"]
    return JobTypeContract(
        type=job_type,
        display_name=display_name or job_type.replace("_", " ").title(),
        description=description,
        kind="runtime",
        supported_actions=kind_actions,
        executor="mcp",
        requires=CapabilityRequirement(connector_types=connector_types or []),
        features=RunFeatures(),
        policy=GovernancePolicy(),
        source="system",
        config=InputSchema(
            required=required or [],
            optional=optional or [],
        ),
    )


def list_job_type_contracts(environment: str | None = None) -> list[JobTypeContract]:
    """Return available job type contracts derived from the connector registry."""
    manager = RegistryManager(environment=environment)
    seen: dict[str, JobTypeContract] = {}

    for server_name, server in manager.get_available_servers().items():
        if not server.job_type:
            continue
        jt = server.job_type.lower()
        if jt in seen:
            continue

        if jt in KNOWN_CONTRACTS:
            seen[jt] = KNOWN_CONTRACTS[jt]
        else:
            seen[jt] = _auto_contract(
                jt,
                display_name=server.display_name,
                description=server.description,
                required=list(server.required_fields),
                optional=list(server.optional_fields),
                connector_types=[server_name],
            )

    if "mcp" not in seen:
        seen["mcp"] = KNOWN_CONTRACTS["mcp"]

    return list(seen.values())


def get_job_type_contract(job_type: str, environment: str | None = None) -> JobTypeContract | None:
    jt = job_type.strip().lower()
    for contract in list_job_type_contracts(environment=environment):
        if contract.type == jt:
            return contract
    return None


def validate_job_contract(kind: str, job_type: str, config: dict) -> JobTypeContract:
    if kind not in _VALID_KINDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid kind '{kind}'. Must be one of: {sorted(_VALID_KINDS)}",
        )

    contract = get_job_type_contract(job_type)
    if contract and contract.kind != kind:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Type '{job_type}' requires kind '{contract.kind}'",
        )

    if contract:
        required = set(contract.config.required)
        cfg = config or {}
        missing = sorted(k for k in required if k not in cfg or cfg.get(k) in {None, ""})
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Missing required config fields for '{job_type}': {', '.join(missing)}",
            )

    return contract or _auto_contract(job_type, connector_types=[job_type])
