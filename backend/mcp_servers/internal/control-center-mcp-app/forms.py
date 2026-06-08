"""Contract → UI form-schema adaptation + connector resolution.

A `JobTypeContract` (or an API form-schema response, or a partial form schema)
goes in; a UI-ready payload comes out:

    {
      "type", "display_name", "description",
      "config_fields", "params_fields",        # FieldSpec dicts, required-annotated
      "required_config", "optional_config",
      "required_params", "optional_params",
      "connector_types", "connector_items",    # contract names + UI dropdown options
      "defaults_config", "defaults_params",    # per-field defaults
    }

This module is the boundary between `control_center.specs` (Pydantic contracts)
and the Prefab UI. It also resolves job-type strings coming in from tool args
(`normalize_job_type`) and merges /job-types list responses
(`job_type_items` — handles list / wrapped / bare-dict shapes).
"""

from __future__ import annotations

import json
from functools import cache
from typing import Any

from control_center.specs import KNOWN_CONTRACTS

from utils import (
    _TEMPLATE_EXPRESSION_RE,
    api_get,
    mark_required_fields,
    normalize_connectors_list,
)


# ── Canonical UI Payload ─────────────────────────────────────────────────────

def build_form_schema_payload(contract_schema: dict) -> dict:
    """Build the canonical UI form-schema payload

    Normalize a JobTypeContract dump or API form-schema response for the UI.
    Accepts both the nested contract-dump shape (`config: {fields, required, optional}`)
    and the flat API form-schema shape (`config_fields`, `required_config`, etc.).
    Output is always the flat UI shape with required flags annotated, connector
    options materialized, and per-section `defaults_*` and `reset_*` slots.
    """

    def _section(schema: dict, section: str, key: str) -> list:
        """Resolve required/optional list from `{key}_{section}` (flat) or `[section][key]` (nested)."""
        direct = schema.get(f"{key}_{section}")
        if direct is not None:
            return list(direct or [])
        return list((schema.get(section) or {}).get(key, []) or [])

    def _section_fields(schema: dict, section: str) -> list[dict]:
        direct = schema.get(f"{section}_fields")
        if direct:
            return mark_required_fields(direct, schema.get(f"required_{section}", []) or [])
        nested = (schema.get(section) or {}).get("fields", {})
        values = list(nested.values()) if isinstance(nested, dict) else list(nested or [])
        return mark_required_fields(values, (schema.get(section) or {}).get("required", []) or [])

    config_fields = _section_fields(contract_schema, "config")
    params_fields = _section_fields(contract_schema, "params")
    connector_types = _extract_connector_types(contract_schema)

    return {
        "type": contract_schema.get("type", ""),
        "display_name": contract_schema.get("display_name") or contract_schema.get("type", ""),
        "description": contract_schema.get("description"),
        "config_fields": config_fields,
        "params_fields": params_fields,
        "required_config": _section(contract_schema, "config", "required"),
        "optional_config": _section(contract_schema, "config", "optional"),
        "required_params": _section(contract_schema, "params", "required"),
        "optional_params": _section(contract_schema, "params", "optional"),
        "connector_types": connector_types,
        "connector_items": _connector_items_for_types(connector_types),
        "defaults_config": _section_defaults(config_fields),
        "defaults_params": _section_defaults(params_fields),
        "reset_config": _section_reset(config_fields),
        "reset_params": _section_reset(params_fields),
    }


def empty_form_schema_payload() -> dict[str, Any]:
    """Return the canonical empty form-schema payload."""
    return build_form_schema_payload({})


# ── Module Entry Points ──────────────────────────────────────────────────────

def resolve_job_type_schema(job_type: str, *, allow_api_fallback: bool = False) -> dict[str, Any]:
    """Resolve the canonical UI form-schema payload for a job-type.

    Resolution order:
    1. Use the matching entry in `KNOWN_CONTRACTS`, when available.
    2. If `allow_api_fallback`, fetch `/job-types/{type}/form-schema` and merge in derived job-type metadata.
    3. Otherwise, return the canonical empty form-schema payload.

    Raises:
         RuntimeError: If API-backed schema resolution or normalization fails.
    Callers that want to swallow those errors should use `resolve_job_type_schema_or_empty(...)`
    """
    normalized_job_type = normalize_job_type(job_type)
    if not normalized_job_type:
        return empty_form_schema_payload()

    contract = KNOWN_CONTRACTS.get(normalized_job_type)
    if contract is not None:
        return build_form_schema_payload(contract.model_dump(mode="json"))

    if not allow_api_fallback:
        return empty_form_schema_payload()

    try:

        raw_schema = api_get(f"/job-types/{normalized_job_type}/form-schema")
        if not isinstance(raw_schema, dict):
            raise TypeError("Expected the form-schema endpoint to return an object, got {type(raw_schema).__name__}")

        # Derived metadata takes precedence over matching fields returned by the API form-schema endpoint.
        resolved_schema = {**raw_schema, **_job_type_metadata_for(raw_schema)}
        return build_form_schema_payload(resolved_schema)

    except Exception as exc:
        raise RuntimeError(f"Failed to resolve form schema for job-type '{normalized_job_type}'") from exc


def resolve_job_type_schema_or_empty(job_type: str) -> dict[str, Any]:
    """Resolve a job-type form schema, returning an empty payload on failure."""
    try:
        return resolve_job_type_schema(job_type, allow_api_fallback=True)
    except Exception:
        # TODO: Add logging here to surface resolution failures without breaking the UI contract.
        return empty_form_schema_payload()


def resolve_connector_types(
    *,
    job_type: str = "",
    connector_types: Any = None,
    connector_type: str = "",
) -> list[str]:
    """Resolve allowed connector types: job contract first, explicit list second.

    Prefab action arguments can serialize arrays as reactive template strings,
    so UI actions pass `job_type` and let the server derive connector names
    from `KNOWN_CONTRACTS`. Explicit `connector_types` remains for direct MCP
    callers.
    """
    if job_type:
        schema = resolve_job_type_schema(job_type, allow_api_fallback=True)
        resolved_types = _extract_connector_types(schema)
        if resolved_types:
            return resolved_types

    explicit_val = (connector_types if connector_types is not None else connector_type)
    return normalize_connectors_list(explicit_val)


@cache
def static_job_types() -> list[dict[str, Any]]:
    """Summaries for every KNOWN_CONTRACTS entry. Cached; contracts are import-time immutable."""
    return [
        job_type_summary(contract.model_dump(mode="json"))
        for contract in KNOWN_CONTRACTS.values()
    ]


def merge_job_type_summaries(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge several summary lists; first occurrence of each `type` wins."""
    merged: dict[str, dict[str, Any]] = {}
    for group in groups:
        for item in group:
            if not isinstance(item, dict):
                continue
            job_type = item.get("type")
            if job_type and job_type not in merged:
                merged[job_type] = item
    return list(merged.values())


def _coerce_field_value(value: Any, field_type: str | None) -> Any:
    """Best-effort coerce a value according to a form-field type.

    Returns the original value when it cannot be safely coerced.
    """
    try:
        match field_type:
            case "integer":
                if isinstance(value, bool):
                    return value
                if isinstance(value, int):
                    return value
                return int(value)
            case "number":
                if isinstance(value, bool):
                    return value
                if isinstance(value, int | float):
                    return value
                return float(value)
            case "boolean":
                if isinstance(value, bool):
                    return value
                normalized = str(value).strip().lower()
                if normalized in {"true", "1", "yes", "on"}:
                    return True
                if normalized in {"false", "0", "no", "off"}:
                    return False
                return value
            case "array" if isinstance(value, str):
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else value
            case "object" if isinstance(value, str):
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else value
            case _:
                return value
    except (TypeError, ValueError):
        return value


def coerce_field_values(fields: list[dict], data: dict) -> dict:
    """Best-effort coerce submitted values using their form-field types.

    Unknown fields and values that cannot be safely coerced are preserved.
    Empty strings and `None` are omitted.
    """
    fields_by_name = {
        field["name"]: field
        for field in fields
        if isinstance(field.get("name"), str)
    }

    return {
        key: _coerce_field_value(value, fields_by_name.get(key, {}).get("type"))
        for key, value in data.items() if value not in ("", None)
    }


# ── Form Schema Serialization ────────────────────────────────────────────────

def _section_defaults(fields: list[dict]) -> dict:
    """Per-field schema defaults: explicit `default` wins; booleans default to False."""
    out: dict[str, Any] = {}
    for f in fields:
        if f.get("default") is not None:
            out[f["name"]] = f["default"]
        elif f.get("type") == "boolean":
            out[f["name"]] = False
    return out


def _section_reset(fields: list[dict]) -> dict:
    """Full per-field reset map: every field present, defaults win, else type-empty.

    Used by the `resetDesignerForm` / `applySchemaChange` Prefab handlers so the
    UI doesn't have to recompute empties from FieldSpec metadata client-side.
    """
    out: dict[str, Any] = {}
    for f in fields:
        name = f.get("name")
        if not name:
            continue
        if f.get("default") is not None:
            out[name] = f["default"]
        elif f.get("type") == "boolean":
            out[name] = False
        else:
            out[name] = ""
    return out


# ── Job-type String Helpers ──────────────────────────────────────────────────

def normalize_job_type(value: Any) -> str:
    """Coerce tool/renderer job-type inputs into known contract keys.

    Tolerates double-quoted JSON strings (FastMCP dev passes args through text
    boundaries) and returns "" for unresolved `{{ ... }}` templates so callers
    don't trigger the API fallback with template text.
    """
    if value is None:
        return ""
    text = str(value).strip()
    if not text or _TEMPLATE_EXPRESSION_RE.match(text):
        return ""
    try:
        decoded = json.loads(text)
        if isinstance(decoded, str):
            text = decoded.strip()
    except json.JSONDecodeError:
        pass
    while len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1:-1].strip()
    if not text or _TEMPLATE_EXPRESSION_RE.match(text):
        return ""
    return text.lower()


# ── Job-type List Helpers ────────────────────────────────────────────────────

def job_type_summary(contract: dict) -> dict[str, Any]:
    """Compact summary `{type, display_name, description, connector_types}`."""
    return {
        "type": contract.get("type"),
        "display_name": contract.get("display_name") or contract.get("type"),
        "description": contract.get("description"),
        "connector_types": _extract_connector_types(contract),
    }


def job_type_items(response: Any) -> list[dict[str, Any]]:
    """Parse `/job-types` responses across all three legal shapes.

    Tolerates: a bare list, a dict with `items`/`job_types`/`available_job_types`
    keys, and a bare dict keyed by job-type name (current backend shape).
    """
    if isinstance(response, list):
        return [item for item in response if isinstance(item, dict)]
    if isinstance(response, dict):
        for key in ("items", "job_types", "available_job_types"):
            value = response.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        keyed_contracts: list[dict[str, Any]] = []
        for key, value in response.items():
            if not isinstance(value, dict):
                continue
            if not value.get("type"):
                value = {**value, "type": key}
            keyed_contracts.append(value)
        return keyed_contracts
    return []


def _job_type_metadata_for(form_schema: dict) -> dict[str, Any]:
    """Recover `connector_types` for an API-fetched form schema when missing.

    Some `/job-types/{type}/form-schema` responses do not include connector
    metadata. Fall back to scanning `/job-types` for a matching contract.
    """
    connector_types = _extract_connector_types(form_schema)
    if connector_types:
        return {"connector_types": connector_types}

    job_type = form_schema.get("type")
    fallback = {"connector_types": connector_types}
    if not job_type:
        return fallback

    try:
        contracts = job_type_items(api_get("/job-types"))
    except Exception:
        return fallback
    for c in contracts:
        if c.get("type") == job_type:
            return {"connector_types": job_type_summary(c)["connector_types"]}
    return fallback


# ── Connector Extraction & Option Building ───────────────────────────────────


def merge_connector_items(
    items: list[dict[str, Any]],
    allowed_connector_names: list[str],
    environment: str,
) -> list[dict[str, Any]]:
    """Merge registered `/connectors` rows with contract-declared MCP server names.

    `/connectors` stores user-registered connection records with coarse
    connector_type values. Job contracts (especially `mcp`) declare approved
    MCP server names. When no row exists for a server name, synthesize an
    option whose id is the server name so job creation can still send the
    correct connector value.
    """
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in items:
        if not isinstance(item, dict):
            continue
        aliases = {
            str(value).strip()
            for value in (item.get("id"), item.get("name"), item.get("connector_type"))
            if value
        }
        if not aliases or aliases & seen:
            continue
        seen.update(aliases)
        merged.append(item)

    for name in allowed_connector_names:
        if name in seen:
            continue
        seen.add(name)
        merged.append({
            "id": name,
            "name": name,
            "connector_type": name,
            "value": name,
            "environment": environment or None,
            "status": "available",
            "is_shared": True,
        })

    return merged


def connector_value(connector: dict[str, Any]) -> str:
    """Value to persist as `Job.connector`.

    Execution resolves `Job.connector` as an MCP server name, so registered
    connector row ids (e.g. `"conn-..."`) are UI metadata, not valid job values.
    Prefer a contract/server name carried on the item, then fall back to common
    connector row fields.
    """
    for key in ("value", "server_name", "connector_type", "name", "id"):
        value = connector.get(key)
        if value:
            return str(value)
    return ""


def connector_display_label(connector: dict[str, Any]) -> str:
    """Build the picker label `(name or id) · connector_type · environment`.

    Consecutive duplicate segments collapse so synthesized rows render compactly
    (`"filesystem · dev"` not `"filesystem · filesystem · dev"`).
    """
    parts: list[str] = []
    for raw in (
        connector.get("name") or connector.get("id"),
        connector.get("connector_type"),
        connector.get("environment"),
    ):
        if not raw:
            continue
        text = str(raw)
        if not parts or parts[-1] != text:
            parts.append(text)
    return " · ".join(parts)


def _connector_items_for_types(
    connector_types: list[str],
    environment: str = "",
) -> list[dict[str, Any]]:
    """Seed `availableConnectors` for the initial render from contract names.

    After Refresh, `list_connectors` produces the same `{label, value}` shape
    so the dropdown labels stay consistent across both code paths.
    """
    return [
        {
            "label": connector_display_label(c),
            "value": connector_value(c),
        }
        for c in merge_connector_items([], connector_types, environment)
    ]


def _extract_connector_types(contract: dict) -> list[str]:
    """Flatten `JobTypeContract.requires[*].names`, deduped, order preserved.

    Handles current list-of-ExecutionRequirement shape, the pre-list single-dict
    shape, and the legacy top-level `connector_types` field on API-discovered
    contracts.
    """
    requires = contract.get("requires")
    if isinstance(requires, dict):
        return (
            normalize_connectors_list(requires.get("names"))
            or normalize_connectors_list(requires.get("connector_types"))
        )

    out: list[str] = []
    seen: set[str] = set()
    if isinstance(requires, list):
        for req in requires:
            if not isinstance(req, dict):
                continue
            for name in normalize_connectors_list(req.get("names")):
                if name not in seen:
                    seen.add(name)
                    out.append(name)
    return out or normalize_connectors_list(contract.get("connector_types"))
