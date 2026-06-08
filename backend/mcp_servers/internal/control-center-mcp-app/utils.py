"""Pure helpers for control-center-mcp-app/server.py.

No Prefab coupling. Domain-agnostic shape coercion, secret masking,
template-expression filtering, form-schema field annotation, and the
shared HTTP client for the Control Center backend API.
"""

from __future__ import annotations

import atexit
import httpx
import json
import os
import re
from collections.abc import Iterable
from dotenv import load_dotenv
from pathlib import Path
from textwrap import dedent
from typing import Any


# ── Backend HTTP Client ───────────────────────────────────────────────────────
# Lazily-created process-local HTTP client reused by backend API helpers.

_api_client: httpx.Client | None = None


def load_backend_env(*, start: Path | None = None, filename: str = ".env", override: bool = False) -> Path | None:
    """Load the nearest .env above this file. Returns the loaded path, or None if no .env file exists."""
    start = (start or Path(__file__)).resolve()
    for parent in start.parents:
        for env_path in (
            parent / "backend" / filename,
            parent / filename,
        ):
            if env_path.is_file():
                load_dotenv(env_path, override=override)
                return env_path
    return None


def _api_base_url() -> str:
    return os.environ.get("CC_API_BASE_URL", "http://localhost:8000").rstrip("/")


def _api_headers() -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    token = os.environ.get("CC_SERVICE_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    return headers


def _get_api_client() -> httpx.Client:
    global _api_client
    if _api_client is None or _api_client.is_closed:
        _api_client = httpx.Client(
            base_url=_api_base_url(),
            headers=_api_headers(),
            timeout=30.0,
        )
    return _api_client


def _close_api_client() -> None:
    global _api_client
    if _api_client is not None and not _api_client.is_closed:
        _api_client.close()
    _api_client = None


atexit.register(_close_api_client)  # Ensure the client is closed when the process exits.


def api_get(path: str, params: dict[str, Any] | None = None) -> Any:
    resp = _get_api_client().get(path, params=params)
    resp.raise_for_status()
    return resp.json()


def api_post(path: str, body: dict[str, Any]) -> Any:
    resp = _get_api_client().post(path, json=body)
    resp.raise_for_status()
    return resp.json()


# ── Javascript Helpers ────────────────────────────────────────────────────────

def js_handler(body: str) -> str:
    """Dedent and strip a multi-line JS snippet for Prefab inline handlers."""
    return dedent(body).strip()


# ── Template / JSON String Normalization ──────────────────────────────────────

_TEMPLATE_EXPRESSION_RE = re.compile(r"^\s*\{\{[^{}]*\}\}\s*$")


def _is_template_expr(value: Any) -> bool:
    """True if value is an unresolved Prefab `{{ ... }}` template expression."""
    return isinstance(value, str) and _TEMPLATE_EXPRESSION_RE.fullmatch(value) is not None


def _parse_jsonish_string(value: str) -> Any:
    """Attempt to parse JSON. If it looks like JSON but is malformed, raise an error."""
    text = value.strip()
    if not text:
        return ""
    if text.startswith(("{", "[")):  # Strictly enforce JSON for clear json-ish strings
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}")  # Fail loudly to prevent silent bugs from malformed JSON
    return text  # Return all bare strings as-is


def _filter_template_items(items: Iterable[Any]) -> tuple[list[Any], bool]:
    """Drop unresolved template items; return (filtered, removed_any)."""
    result: list[Any] = []
    removed_any = False
    for item in items:
        if _is_template_expr(item):
            removed_any = True
            continue
        result.append(item)
    return result, removed_any


def patch_value(patch: dict[str, Any], *keys: str) -> Any:
    """First-present value across aliased keys; None if no key present."""
    for key in keys:
        if key in patch:
            return patch[key]
    return None


def patch_list(value: Any) -> list[Any] | None:
    """Normalize a patch/UI value into a list.

    Returns None when unusable (unresolved template, all-template list) so
    callers can preserve the existing value instead of overwriting with garbage.
    Strings are JSON-decoded; bare strings split on commas.
    """
    if value is None or _is_template_expr(value):
        return None

    if isinstance(value, str):
        decoded = _parse_jsonish_string(value)
        if decoded == "":
            return []
        if _is_template_expr(decoded):
            return None
        if isinstance(decoded, str):
            return [part.strip() for part in decoded.split(",") if part.strip()]
        value = decoded

    if isinstance(value, (list, tuple, set)):
        result, removed_any = _filter_template_items(value)
        return None if removed_any and not result else result

    return [value]


def patch_dict(value: Any) -> dict[str, Any] | None:
    """Normalize a patch/UI value into a dict.

    Returns None when unusable so callers preserve the existing value.
    """
    if value is None or _is_template_expr(value):
        return None

    if isinstance(value, str):
        decoded = _parse_jsonish_string(value)
        if decoded == "":
            return {}
        if _is_template_expr(decoded):
            return None
        value = decoded

    if isinstance(value, dict):
        result: dict[str, Any] = {}
        removed_any = False
        for key, item in value.items():
            if not isinstance(key, str):
                removed_any = True
                continue
            if _is_template_expr(key) or _is_template_expr(item):
                removed_any = True
                continue
            result[key] = item
        return None if removed_any and not result else result

    return None


# ── Secret Redaction ──────────────────────────────────────────────────────────

SECRET_MARKER = "•••"


def secret_field_names(fields: Any) -> set[str]:
    """Names of FieldSpec entries flagged sensitive / write_only / format=secret."""
    if not isinstance(fields, list):
        return set()
    return {
        f["name"]
        for f in fields
        if isinstance(f, dict)
        and f.get("name")
        and (f.get("sensitive") or f.get("write_only") or f.get("format") == "secret")
    }


def mask_secrets(values: Any, secret_names: set[str]) -> dict[str, Any]:
    """Copy of values with secret entries replaced by SECRET_MARKER."""
    if not isinstance(values, dict):
        return {}
    return {
        k: (SECRET_MARKER if k in secret_names and v not in ("", None) else v)
        for k, v in values.items()
    }


# ── Schema Field Annotation ───────────────────────────────────────────────────

def mark_required_fields(fields: list[dict], required: list[str]) -> list[dict]:
    """Annotate each field dict with `required: bool` derived from `required`."""
    required_names = set(required)
    normalized: list[dict] = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        name = field.get("name")
        normalized.append({**field, "required": bool(name and name in required_names)})
    return normalized


# ── Connectors List Normalization ─────────────────────────────────────────────

def normalize_connectors_list(value: Any) -> list[str]:
    """Coerce contract / API / Prefab inputs into a de-duped list of connector names.

    Builds on _patch_list (shape coercion + template filtering) then str-casts
    each item, drops blanks/templates, and de-dupes in order.
    """
    items = patch_list(value) or []
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item is None:
            continue
        name = str(item).strip()
        if not name or _is_template_expr(name) or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out
