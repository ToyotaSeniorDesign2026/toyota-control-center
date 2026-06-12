"""Control Center Job Designer MCP App.

Interactive Prefab app for authoring Control Center jobs. The form is
contract-driven: built-in types come from `control_center.specs.KNOWN_CONTRACTS`,
and API-discovered types fall back to the backend's form-schema endpoint. The
config/params section renders dynamically from each contract's `FieldSpec`
list (text/number/boolean/select/secret).

Three authoring paths feed the same draft:
    - Manual edits in the iframe form.
    - `patch_draft_snapshot` from the host model (partial JSON patches).
    - `generate_full_job_draft` — the "Generate full draft" button — runs a
      two-step Instructor flow (pick JobType, then fill contract-shaped fields)
      via `job_generation.generate_job_draft_from_intent`.

Module layout (4 files total):
    server.py        — this file. Prefab UI tree, MCP tools, draft↔UI plumbing,
                       action factories. Edit this when iterating on UI/tools.
    form_schema.py   — JobTypeContract ↔ UI form-payload translation, connector
                       resolution, /job-types response parsing. Stable surface.
    utils.py         — stateless helpers: shared httpx.Client, JSON-ish/template
                       shape coercion (patch_list/patch_dict), secret masking,
                       JS handler trim. No domain knowledge.
    job_generation.py — two-step Instructor flow that backs `generate_full_job_draft`.

Backend wiring (HTTP, via utils.api_get / utils.api_post):
    GET  /job-types                         list/discover dynamic types
    GET  /job-types/{type}/form-schema      schema fallback for dynamic types
    GET  /connectors                        list registered connectors
    POST /jobs                              create a job
    POST /jobs/{job_id}/runs                trigger a run

Environment variables (loaded from backend/.env on import; shell env wins):
    CC_API_BASE_URL                         Control Center API base (default http://localhost:8000)
    CC_SERVICE_TOKEN                        Bearer token for the Control Center API
    GOOGLE_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY
                                            Provider key for the Generate-draft Instructor call
    CONTROL_CENTER_MCP_INSTRUCTOR_MODEL     Override the default `google/gemini-3.1-flash-lite`
"""

from __future__ import annotations

import json
import logging
from typing import Any
from textwrap import dedent, indent
from datetime import datetime, timezone

from fastmcp import FastMCP
from fastmcp.apps import AppConfig, ResourceCSP
from fastmcp.apps.approval import Approval
from prefab_ui import PrefabApp
from prefab_ui.app import ResolvedTool
from prefab_ui.actions import PopState, SetState, ShowToast, CallHandler, CloseOverlay
from prefab_ui.actions.mcp import CallTool, RequestDisplayMode, SendMessage, UpdateContext
from prefab_ui.rx import ERROR, EVENT, Rx
from prefab_ui.themes import Theme
from prefab_ui.components import (
    Accordion,
    AccordionItem,
    Alert,
    AlertDescription,
    AlertTitle,
    Badge,
    Button,
    Card,
    CardContent,
    CardDescription,
    CardFooter,
    CardHeader,
    CardTitle,
    Checkbox,
    ChoiceCard,
    Code,
    Column,
    Combobox,
    ComboboxOption,
    Dialog,
    Div,
    Elif,
    Else,
    Field,
    FieldContent,
    FieldDescription,
    FieldTitle,
    ForEach,
    Grid,
    HoverCard,
    H1,
    Icon,
    If,
    Input,
    Label,
    Loader,
    Muted,
    P,
    Popover,
    Progress,
    RESULT,
    Row,
    STATE,
    Select,
    SelectOption,
    Small,
    Span,
    Text,
    Textarea,
)

import utils
import forms

utils.load_backend_env()

from job_generation import generate_job_draft_from_intent

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# -----------------------------------------------------------------------------
# Setup & Utilities
# -----------------------------------------------------------------------------

SERVER_NAME = "control-center-job-creator"
SERVER_DESCRIPTION = (
    "Interactive Control Center job designer — pick a job type, choose a "
    "connector, fill the contract-driven form, and create or trigger jobs."
)
APP_RESOURCE_URI = "ui://control-center/job-designer.html"
APP_RESOURCE_DOMAIN = "https://control-center-job-creator.local"

# Shared JavaScript helpers injected into handlers that run in isolated scopes.
# Schema-dependent reset values are computed server-side in form_schema._section_reset
# and exposed through `schema.reset_config` and `schema.reset_params`.
_JS_HELPERS = utils.js_handler("""
    const asArray = (v) => Array.isArray(v) ? v : [];
    const asObject = (v) => v && typeof v === "object" && !Array.isArray(v) ? v : {};

    const resetDesignerSections = (schema) => ({
        config: asObject(schema.reset_config),
        params: asObject(schema.reset_params),
        selectedConnectors: [],
        connectorPickerValue: "",
        connectorText: "",
        runPrompt: "",
        createdJob: null,
        lastRun: null,
        lastDraftCapturedAt: "",
    });
""")


def _js_handler_with_helpers(body: str) -> str:
    """Build a JS handler with `_JS_HELPERS` available in its local scope."""
    return utils.js_handler(f"(ctx) => {{\n{indent(_JS_HELPERS, '    ')}\n{indent(dedent(body).strip(), '    ')}\n}}")


JS_ACTIONS = {
    # Capture the designer state needed to generate or restore a draft.
    "buildDraftCapture": _js_handler_with_helpers("""
        const s = ctx.state || {};
        return {
            intent: s.intent || "",
            selectedJobType: s.selectedJobType || "",
            selectedConnectors: asArray(s.selectedConnectors),
            connectorText: s.connectorText || "",
            environment: s.environment || "dev",
            dataSensitivity: s.dataSensitivity || "low",
            jobName: s.jobName || "",
            tagsText: s.tagsText || "",
            config: asObject(s.config),
            params: asObject(s.params),
            runPrompt: s.runPrompt || "",
            formSchema: asObject(s.formSchema),
            availableConnectors: asArray(s.availableConnectors),
        };
    """),

    # Move the Combobox's transient selection (never serialized in draft) into
    # the canonical connector list, avoiding duplicates, then clear the combobox.
    "pushConnectorToList": _js_handler_with_helpers("""
        const s = ctx.state || {};
        const picked = s.connectorPickerValue || "";
        if (!picked) return {};
        const current = asArray(s.selectedConnectors);
        if (current.includes(picked)) return { connectorPickerValue: "" };
        return { selectedConnectors: [...current, picked], connectorPickerValue: "" };
    """),

    # Restore the entire designer to its initial schema-derived state.
    "resetDesignerForm": _js_handler_with_helpers("""
        const s = ctx.state || {};
        return {
            ...resetDesignerSections(s.formSchema || {}),
            jobName: "",
            intent: "",
            tagsText: "",
        };
    """),

    # Apply the new job-type schema and reset all state whose shape depends on it.
    "applySchemaChange": _js_handler_with_helpers("""
        const s = ctx.state || {};
        const schema = (ctx.arguments || {}).schema || {};
        return {
            selectedJobType: schema.type || s.selectedJobType || "",
            formSchema: schema,
            availableConnectors: asArray(schema.connector_items),
            ...resetDesignerSections(schema),
        };
    """),

    # Apply only selected AI suggestions, merging config and params with existing values.
    "applySelectedAiSuggestions": _js_handler_with_helpers("""
        const s = ctx.state || {};
        const changes = asArray(s.pendingAiSuggestions);
        const output = {};
        const mergeSection = (section, updates) => {
            output[section] = {
                ...asObject(output[section] !== undefined ? output[section] : s[section]),
                ...asObject(updates),
            };
        };
        for (const change of changes) {
            if (!change || !change.selected) continue;
            for (const [key, value] of Object.entries(asObject(change.updates))) {
                if (key === "config" || key === "params") mergeSection(key, value);
                else output[key] = value;
            }
        }
        return { ...output, suggestionsPending: false, pendingAiSuggestions: [], loading: false };
    """),
}


def _resource_csp_for(app: PrefabApp) -> ResourceCSP:
    """Convert a Prefab app's CSP into MCP resource metadata."""
    csp = app.csp()
    known_keys = {"connect_domains", "style_domains", "script_domains", "resource_domains"}
    unknown = csp.keys() - known_keys
    if unknown:
        raise RuntimeError(f"Unsupported Prefab CSP keys: {sorted(unknown)}")

    resource_domains = sorted({
        domain
        for key in ("resource_domains", "style_domains", "script_domains")
        for domain in csp.get(key, [])
    })

    return ResourceCSP(
        connect_domains=csp.get("connect_domains") or None,
        resource_domains=resource_domains or None,
    )


def _resolve_prefab_tool(tool_ref: Any) -> ResolvedTool:
    """Resolve a Prefab tool reference to its registered FastMCP name."""
    # TODO: Resolve FastMCP metadata, test if `unwrap_result` is still apt to expose structuredContent as `$result`."""
    name = tool_ref if isinstance(tool_ref, str) else getattr(tool_ref, "__name__", str(tool_ref))
    return ResolvedTool(name=name, unwrap_result=True)


# -----------------------------------------------------------------------------
# Draft State Lifecycle
# -----------------------------------------------------------------------------

_REQUIRED_UI_STATE_KEYS = {"environment", "config", "params", "formSchema"}
_ENVIRONMENT_OPTIONS: list[tuple[str, str]] = [
    ("dev", "Development"),
    ("semi-prod", "Semi-Prod"),
    ("prod", "Production"),
]
_DATA_SENSITIVITY_OPTIONS: list[tuple[str, str]] = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
]

# ── Draft <-> UI State Adapter ────────────────────────────────────────────────
# camelCase UI state is the source of truth for job creation. snake_case drafts
# are the AI-facing representation used for snapshots, suggestions, and patches.
#
# AI tools submit partial draft patches. `_apply_designer_patch` resolves field
# aliases and maps those changes back into UI state. Secrets are redacted only
# when a draft crosses the app boundary; iframe state retains original values.
#
# `_SCALAR_FIELDS` defines all scalar UI <-> draft mappings. Container fields (config, params,
# connectors, formSchema) remain explicit, as each requires its own conversion and patch behavior.

_SCALAR_FIELDS: tuple[tuple[str, str, str, tuple[str, ...], str], ...] = (
    # ui_key, draft_key, label, patch_aliases, default
    ("intent",           "intent",            "Intent",             ("intent",),                                                   ""),
    ("selectedJobType",  "selected_job_type", "Job type",           ("selectedJobType", "selected_job_type", "job_type", "type"), ""),
    ("environment",      "environment",       "Environment",        ("environment",),                                              "dev"),
    ("dataSensitivity",  "data_sensitivity",  "Data sensitivity",   ("dataSensitivity", "data_sensitivity"),                       "low"),
    ("jobName",          "job_name",          "Job name",           ("jobName", "job_name", "name"),                               ""),
    ("tagsText",         "tags_text",         "Tags",               ("tagsText", "tags_text", "tags"),                             ""),
    ("connectorText",    "manual_connector",  "Manual connector",   ("connectorText", "connector_text", "manual_connector"),      ""),
    ("runPrompt",        "run_prompt",        "Run prompt",         ("runPrompt", "run_prompt", "prompt"),                         ""),
)

# Container fields handled explicitly by each state adapter and sync path. Keep this list
# aligned with `_ui_state_to_draft`, `_draft_to_ui_state`, and `_sync_ui_result_to_form_actions`.
_CONTAINER_FIELDS: tuple[str, ...] = ("selectedConnectors", "availableConnectors", "config", "params", "formSchema")


def _initial_state(
    *,
    job_types: list[dict] | None = None,
    selected_type: str = "",
    environment: str = "dev",
) -> dict[str, Any]:
    available_job_types = job_types or forms.static_job_types()
    selected_schema = forms.resolve_job_type_schema_or_empty(selected_type)

    resolved_selected_type = (selected_schema.get("type") or forms.normalize_job_type(selected_type) or "")

    if selected_schema.get("type"):
        available_job_types = forms.merge_job_type_summaries(available_job_types, [forms.job_type_summary(selected_schema)])

    return {
        "availableJobTypes": available_job_types,
        "availableConnectors": selected_schema.get("connector_items", []),
        "selectedJobType": resolved_selected_type,
        "connectorPickerValue": "",  # Transient UI staging slot for the connector Combobox; never serialized into draft
        "selectedConnectors": [],
        "connectorText": "",
        "intent": "",
        "environment": environment,
        "dataSensitivity": "low",
        "jobName": "",
        "tagsText": "",
        "config": selected_schema.get("defaults_config", {}),
        "params": selected_schema.get("defaults_params", {}),
        "runPrompt": "",
        "formSchema": selected_schema,

        # UI / Status Metadata
        "loading": False,
        "lastDraftCapturedAt": "",
        "pendingAiSuggestions": [],
        "rawAiPatchText": "",
        "suggestionsPending": False,
        "createdJob": None,
        "lastRun": None,
    }


def _ui_state_to_draft(state: dict[str, Any] | None) -> dict[str, Any]:
    """Project Prefab/UI state into the AI-visible draft snapshot shape."""
    state = state or {}
    form_schema = utils.patch_dict(state.get("formSchema")) or forms.empty_form_schema_payload()

    draft: dict[str, Any] = {
        draft_key: str(state.get(ui_key) or default)
        for ui_key, draft_key, _, _, default in _SCALAR_FIELDS
    }
    draft["selected_job_type"] = forms.normalize_job_type(state.get("selectedJobType")) or str(
        form_schema.get("type") or ""
    )
    draft.update({
        "selected_connectors": utils.patch_list(state.get("selectedConnectors")) or [],
        "available_connectors": utils.patch_list(state.get("availableConnectors")) or [],
        "config": utils.patch_dict(state.get("config")) or {},
        "params": utils.patch_dict(state.get("params")) or {},
        "form_schema": form_schema,
    })
    return draft


def _draft_to_ui_state(draft: dict[str, Any] | None) -> dict[str, Any]:
    """Project an AI-visible draft snapshot back into Prefab/UI state shape."""
    draft = draft or {}

    state: dict[str, Any] = {
        ui_key: draft.get(draft_key, default)
        for ui_key, draft_key, _, _, default in _SCALAR_FIELDS
    }
    state.update({
        "selectedConnectors": draft.get("selected_connectors", []),
        "availableConnectors": draft.get("available_connectors", []),
        "config": draft.get("config", {}),
        "params": draft.get("params", {}),
        "formSchema": draft.get("form_schema", forms.empty_form_schema_payload()),
    })
    return state


def _capture_draft_snapshot(current_state: dict[str, Any] | None) -> dict[str, Any]:
    """Capture Prefab/UI state as the latest AI-visible draft snapshot.

    The stored draft holds FULL values (including secrets). Redaction runs at
    MCP tool return time so the iframe sync path keeps real values while
    AI/print surfaces see masks. See `_redact_snapshot`.
    """
    draft = _ui_state_to_draft(current_state)
    return {
        "status": "captured",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "draft": draft,
        "draft_json": json.dumps(draft, indent=2, sort_keys=True),
    }


def _apply_designer_patch(
    current_state: dict[str, Any] | None,
    patch: dict[str, Any] | None,
) -> dict[str, Any]:
    """Apply a partial patch to UI-shaped designer state.

    Contract:
      • `current_state` is Prefab/UI-shaped state.
      • `patch` may use either UI-style or AI/draft-style aliases.
      • Omitted fields are preserved.
      • `config`/`params` merge into existing values.
      • `replace_config`/`replace_params` replace the whole object.
      • A `selectedJobType` change reloads the schema and resets connectors.
      • Return value is UI-shaped so Prefab can `SetState` directly.
    """
    if current_state is not None and not isinstance(current_state, dict):
        raise ValueError("current_state must be an object.")
    if patch is not None and not isinstance(patch, dict):
        raise ValueError("patch must be an object.")

    current_state = current_state or {}
    patch = patch or {}
    applied: list[str] = []

    # Round-trip current state through the draft adapter first so all values
    # have parsed dict/list defaults.
    state = _draft_to_ui_state(_ui_state_to_draft(current_state))

    scalars: dict[str, Any] = {ui_key: state[ui_key] for ui_key, *_ in _SCALAR_FIELDS}
    selected_connectors = state["selectedConnectors"]
    available_connectors = state["availableConnectors"]
    config = state["config"]
    params = state["params"]
    form_schema = state["formSchema"]

    schema_replaced = False

    # ── Job type / schema swap ──────────────────────────────────────────
    # selectedJobType is special: a change reloads the schema and resets
    # connectors. The scalar loop below skips it.
    next_type = utils.patch_value(patch, "selectedJobType", "selected_job_type", "job_type", "type")
    if next_type is not None:
        normalized_next_type = forms.normalize_job_type(next_type)
        if normalized_next_type and normalized_next_type != scalars["selectedJobType"]:
            scalars["selectedJobType"] = normalized_next_type
            form_schema = forms.resolve_job_type_schema(normalized_next_type, allow_api_fallback=True)
            available_connectors = form_schema.get("connector_items", [])
            schema_replaced = True
            applied.extend(["selectedJobType", "formSchema", "availableConnectors"])

    next_schema = utils.patch_value(patch, "formSchema", "form_schema")
    if isinstance(next_schema, dict):
        form_schema = forms.build_form_schema_payload(next_schema)
        scalars["selectedJobType"] = forms.normalize_job_type(form_schema.get("type")) or scalars["selectedJobType"]
        available_connectors = form_schema.get("connector_items", [])
        schema_replaced = True
        applied.extend(["formSchema", "availableConnectors"])

    # ── Scalars ─────────────────────────────────────────────────────────
    for ui_key, _draft_key, _label, aliases, _default in _SCALAR_FIELDS:
        if ui_key == "selectedJobType":
            continue
        value = utils.patch_value(patch, *aliases)
        if value is None:
            continue
        if ui_key == "tagsText":
            scalars[ui_key] = ", ".join(value) if isinstance(value, list) else str(value)
        else:
            scalars[ui_key] = str(value)
        applied.append(ui_key)

    # ── Connector lists ─────────────────────────────────────────────────
    next_selected = utils.patch_list(utils.patch_value(patch, "selectedConnectors", "selected_connectors", "connectors"))
    if next_selected is not None:
        selected_connectors = next_selected
        applied.append("selectedConnectors")

    next_available = utils.patch_list(utils.patch_value(patch, "availableConnectors", "available_connectors"))
    if next_available is not None:
        available_connectors = next_available
        applied.append("availableConnectors")

    # ── Config / params ─────────────────────────────────────────────────
    # replace_X wins; otherwise merge. On a schema swap, the merge base is
    # the contract's defaults so AI-filled values *override* them but absent
    # AI keys still inherit (e.g. a contract-supplied `timezone: UTC` should
    # not disappear just because the AI did not restate it).
    def _resolve_section(
        section: str,
        current_value: dict[str, Any],
        merge_aliases: tuple[str, ...],
        defaults_key: str,
    ) -> dict[str, Any]:
        replace = utils.patch_dict(utils.patch_value(patch, f"replace_{section}"))
        update = utils.patch_dict(utils.patch_value(patch, *merge_aliases))
        if replace is not None:
            applied.append(section)
            return replace
        if update is not None:
            base = form_schema.get(defaults_key, {}) if schema_replaced else current_value
            applied.append(section)
            return {**base, **update}
        if schema_replaced:
            return form_schema.get(defaults_key, {})
        return current_value

    config = _resolve_section("config", config, ("config", "config_updates"), "defaults_config")
    params = _resolve_section("params", params, ("params", "run_params", "params_updates"), "defaults_params")

    # ── UI-shaped result ────────────────────────────────────────────────
    unique_applied = list(dict.fromkeys(applied))
    message = (
        f"Applied changes: {', '.join(unique_applied)}."
        if unique_applied
        else "No changes were applied."
    )

    return {
        "status": "applied",
        "message": message,
        "applied": unique_applied,
        **scalars,
        "selectedConnectors": selected_connectors,
        "availableConnectors": available_connectors,
        "config": config,
        "params": params,
        "formSchema": form_schema,
    }


def _redact_draft(draft: dict[str, Any] | None) -> dict[str, Any]:
    """Copy of `draft` with config/params secret values masked."""
    if not isinstance(draft, dict):
        return {}
    schema = draft.get("form_schema") or {}
    return {
        **draft,
        "config": utils.mask_secrets(draft.get("config"), utils.secret_field_names(schema.get("config_fields"))),
        "params": utils.mask_secrets(draft.get("params"), utils.secret_field_names(schema.get("params_fields"))),
    }


def _redact_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Snapshot with both `draft` and `draft_json` redacted.

    The server-side store keeps the full snapshot; this builds the safe-for-AI
    view at tool return time.
    """
    if not isinstance(snapshot, dict):
        return {}
    redacted = _redact_draft(snapshot.get("draft", {}))
    return {
        **snapshot,
        "draft": redacted,
        "draft_json": json.dumps(redacted, indent=2, sort_keys=True),
    }


# -----------------------------------------------------------------------------
# AI Draft Diff Formatting
# -----------------------------------------------------------------------------

_MISSING = object()


def _display_value(value: Any, *, limit: int | None = 180) -> str:
    """Render a draft value for the diff UI.

    `—` for missing/empty, JSON for dicts/lists, `str()` otherwise; truncated
    with an ellipsis past `limit` chars.
    """
    if value is _MISSING or value is None or value == "":
        return "—"
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value)
    if limit is None:
        return text
    return text[:limit] + ("…" if len(text) > limit else "")


def _get_diff_items(current: dict, proposed: dict):
    """Yield `(item_id, label, ui_key, field_key, before, after)` for visible
    draft fields.

    Scalars come from `_SCALAR_FIELDS`; `selected_connectors` is the only list
    surfaced. `available_connectors` is intentionally excluded — UI plumbing,
    not user intent.
    """
    diff_fields: list[tuple[str, str, str]] = [
        (draft_key, ui_key, label)
        for ui_key, draft_key, label, *_ in _SCALAR_FIELDS
    ]
    diff_fields.append(("selected_connectors", "selectedConnectors", "Selected connectors"))

    for draft_key, ui_key, label in diff_fields:
        yield (
            draft_key,
            label,
            ui_key,
            None,
            current.get(draft_key, _MISSING),
            proposed.get(draft_key, _MISSING),
        )

    for section in ("config", "params"):
        before_section = utils.patch_dict(current.get(section)) or {}
        after_section = utils.patch_dict(proposed.get(section)) or {}
        for field_key, after in after_section.items():
            yield (
                f"{section}.{field_key}",
                f"{section.title()}: {field_key.replace('_', ' ').title()}",
                section,
                field_key,
                before_section.get(field_key, _MISSING),
                after,
            )


def _flatten_draft_changes(
    current_draft: dict[str, Any],
    proposed_draft: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build the UI-ready list of proposed changes for the preview overlay."""
    changes: list[dict[str, Any]] = []

    for item_id, label, ui_key, field_key, before, after in _get_diff_items(
        current_draft,
        proposed_draft,
    ):
        if after is _MISSING or before == after:
            continue

        updates = (
            {ui_key: {field_key: after}}
            if field_key is not None
            else {ui_key: after}
        )

        is_addition = before in (_MISSING, None, "", [], {})
        is_deletion = after in (_MISSING, None, "", [], {})
        before_css = "text-muted-foreground opacity-40" if is_addition else "text-red-400/80 line-through decoration-red-500/50"
        after_css = "text-muted-foreground opacity-40" if is_deletion else "text-emerald-400 font-medium"

        before_text = _display_value(before)
        after_text = _display_value(after)
        is_long = len(before_text) > 35 or len(after_text) > 35

        changes.append({
            "id": item_id,
            "label": label,
            "before": before_text,
            "after": after_text,
            "before_css": before_css,
            "after_css": after_css,
            "is_long": is_long,
            "selected": True,
            "updates": updates,
        })

    return changes


# -----------------------------------------------------------------------------
# Prefab Action Factories
# -----------------------------------------------------------------------------

# `_call()` centralizes the common loading cleanup and error toast so each
# action factory only defines its tool arguments and success-specific steps.
# Actions with nested `CallHandler` or `CallTool` branches remain explicit/inline.
_ERR = ShowToast(ERROR, variant="error")


def _call(
    tool: str,
    *,
    arguments: dict[str, Any] | None = None,
    on_success: list[Any] | None = None,
    set_loading: bool = True,
) -> CallTool:
    """Build a `CallTool` with standard success and error handling."""
    success = list(on_success or [])
    error: list[Any] = [_ERR]
    if set_loading:
        success.append(SetState("loading", False))
        error.insert(0, SetState("loading", False))
    kwargs: dict[str, Any] = {"on_success": success, "on_error": error}
    if arguments is not None:
        kwargs["arguments"] = arguments
    return CallTool(tool, **kwargs)


def _sync_ui_result_to_form_actions(*, silent: bool = False) -> list[Any]:
    """Sync a UI-shaped tool result into live Prefab state. `silent` drops the toast
    (used by the iframe's on_mount auto-sync so reopens don't chatter)."""
    actions: list[Any] = [
        *[SetState(k, getattr(RESULT, k)) for k, *_ in _SCALAR_FIELDS],
        *[SetState(k, getattr(RESULT, k)) for k in _CONTAINER_FIELDS],
        SetState("loading", False),
    ]
    if not silent:
        actions.append(ShowToast(RESULT.message, variant="success"))
    return actions


def _sync_ai_draft_to_form_action(*, silent: bool = False) -> CallTool:
    """Pull the latest server-side draft into the iframe via SetState.

    `silent=True` suppresses both the success toast and the error toast so the
    on_mount auto-sync runs invisibly on a clean designer with nothing to
    surface; the user-driven Sync button keeps its toasts.
    """
    on_error: list[Any] = [SetState("loading", False)]
    if not silent:
        on_error.append(ShowToast(ERROR, variant="error"))
    return CallTool(
        "get_current_draft_ui_state",
        on_success=_sync_ui_result_to_form_actions(silent=silent),
        on_error=on_error,
    )


def _refresh_job_types_action(*, set_loading: bool = True) -> CallTool:
    return _call(
        "list_job_types",
        on_success=[SetState("availableJobTypes", RESULT.items)],
        set_loading=set_loading,
    )


def _refresh_connectors_action(
    *,
    job_type_expr: Any | None = None,
    environment_expr: Any | None = None,
    set_loading: bool = True,
) -> CallTool:
    return _call(
        "list_connectors",
        arguments={
            "job_type": job_type_expr if job_type_expr is not None else STATE.selectedJobType,
            "environment": environment_expr if environment_expr is not None else STATE.environment,
        },
        on_success=[SetState("availableConnectors", RESULT.items)],
        set_loading=set_loading,
    )


def _load_schema_action(job_type_expr: Any) -> CallTool:
    return _call(
        "get_form_schema",
        arguments={"job_type": job_type_expr},
        on_success=[
            CallHandler(
                "applySchemaChange",
                arguments={"schema": RESULT},
                on_error=[SetState("loading", False), _ERR],
            ),
        ],
    )


def _create_job_action(*, environment_expr: Any | None = None) -> CallTool:
    return _call(
        "create_job",
        arguments={
            "name": STATE.jobName,
            "type": STATE.selectedJobType,
            "connector": "{{ selectedConnectors.0 || connectorText }}",
            "environment": environment_expr if environment_expr is not None else STATE.environment,
            "config": STATE.config,
            "data_sensitivity": STATE.dataSensitivity,
            "tags_text": STATE.tagsText,
        },
        on_success=[
            SetState("createdJob", RESULT),
            ShowToast("Job registered.", variant="success"),
            RequestDisplayMode("fullscreen"),
        ],
    )


def _trigger_run_action(*, environment_expr: Any | None = None) -> CallTool:
    return _call(
        "trigger_run",
        arguments={
            "job_id": STATE.createdJob.id,
            "action": "run",
            "target_environment": environment_expr if environment_expr is not None else STATE.environment,
            "params": STATE.params,
            "prompt": STATE.runPrompt,
        },
        on_success=[
            SetState("lastRun", RESULT),
            ShowToast("Run queued.", variant="success"),
        ],
    )


def _capture_current_draft_action(
    *,
    on_success: list[Any] | None = None,
) -> CallHandler:
    return CallHandler(
        "buildDraftCapture",
        on_success=CallTool(
            "capture_current_draft",
            arguments={"current_state": RESULT},
            on_success=on_success or [],
            on_error=[ShowToast(ERROR, variant="error")],
        ),
        on_error=[ShowToast(ERROR, variant="error")],
    )


#
def _capture_and_update_context(*after_update: Any) -> list[Any]:
    """Capture the live draft, publish it to model's context, then run any additional actions."""
    return [
        _capture_current_draft_action(
            on_success=[
                SetState("lastDraftCapturedAt", RESULT.captured_at),
                UpdateContext(structured_content={"control_center_job_designer": RESULT.draft}),
                *after_update,
            ],
        ),
    ]


def _update_ai_context_action() -> list[Any]:
    return _capture_and_update_context(ShowToast("AI context updated.", variant="success"))


def _preview_ai_suggested_changes_action() -> CallHandler:
    return CallHandler(
        "buildDraftCapture",
        on_success=CallTool(
            "preview_ai_suggested_changes",
            arguments={"current_state": RESULT},
            on_success=[
                SetState("pendingAiSuggestions", RESULT.changes),
                SetState("rawAiPatchText", RESULT.raw_changes_text),
                SetState("suggestionsPending", True),
                SetState("loading", False),
            ],
            on_error=[
                SetState("loading", False),
                ShowToast(ERROR, variant="error"),
            ],
        ),
        on_error=[
            SetState("loading", False),
            ShowToast(ERROR, variant="error"),
        ],
    )


def _review_draft_action() -> list[Any]:
    return _capture_and_update_context(
        SendMessage(
            "Review the current configured job for readiness. Check its connectors, "
            "required config and params, and any missing or inconsistent fields.\n\n"
            "If changes are warranted, call `patch_draft_snapshot` with a finalized patch "
            "containing only the fields that should change. Do not resend unchanged state."
            "\nCurrent job draft JSON:\n```json\n{{ $result.draft_json }}\n```"
        ),
    )


# -----------------------------------------------------------------------------
# Dynamic Form Rendering
# -----------------------------------------------------------------------------

MAX_CONNECTOR_OPTIONS = 24
MAX_ENUM_OPTIONS = 12


def _render_enum_select(state_root: str, field: Any, option_count: int) -> None:
    enum_text = str(field.enum).strip()
    enum_path = enum_text[2:-2].strip() if enum_text.startswith("{{") and enum_text.endswith("}}") else enum_text
    with Select(name=f"{state_root}.{field.name}"):
        for i in range(option_count):
            option = f"{{{{ {enum_path}.{i} }}}}"
            SelectOption(option, value=option)


def _render_length_unrolled(length_expr: Any, max_n: int, build_with_count) -> None:
    """Unroll a `len(list) == N` ladder so a parent component renders N direct children.

    Prefab `Select` / `Combobox` only materialize options that are direct
    children — `ForEach` inside them is not expanded by the client renderer.
    Workaround: pre-build N static option slots that each bind to
    `array.{i}.value` via template literals, and pick the right N at render
    time via `If`/`Elif` against the runtime list length.

    `build_with_count(n)` is invoked inside each branch with the option count.
    """
    with If(length_expr == 1):
        build_with_count(1)
    for count in range(2, max_n + 1):
        with Elif(length_expr == count):
            build_with_count(count)
    with Elif(length_expr > max_n):
        build_with_count(max_n)


def _render_enum_select_for_field(state_root: str, field: Any) -> None:
    _render_length_unrolled(
        field.enum.length(),
        MAX_ENUM_OPTIONS,
        lambda n: _render_enum_select(state_root, field, n),
    )


def _render_field_loop(state_root: str, fields_path: str) -> None:
    """Render a list of FieldSpec entries as a dynamic form.

    `state_root` is the state object the inputs write into (e.g. "config" or "params").
    `fields_path` is the state path of the FieldSpec list (e.g. "formSchema.config_fields").
    """
    with ForEach(fields_path) as field:
        with Field():
            with Row(gap=2, align="center", css_class="flex-wrap"):
                FieldTitle(field.name)
                with If(field.required):
                    Badge("required", variant="outline")
                with If(field.sensitive | field.write_only):
                    Badge("sensitive", variant="outline")
            with If(field.description):
                FieldDescription(field.description)
            with FieldContent():
                # 1. enum -> select
                with If(field.enum):
                    _render_enum_select_for_field(state_root, field)
                # 2. boolean -> checkbox
                with Elif(field.type == "boolean"):
                    Checkbox(name=f"{state_root}.{field.name}", label=field.name)
                # 3. secret -> password input
                with Elif(field.format == "secret"):
                    Input(
                        name=f"{state_root}.{field.name}",
                        input_type="password",
                        placeholder=field.placeholder,
                    )
                # 4. numeric
                with Elif((field.type == "integer") | (field.type == "number")):
                    Input(
                        name=f"{state_root}.{field.name}",
                        input_type="number",
                        placeholder=field.placeholder,
                    )
                # 5. array / object -> JSON textarea
                with Elif((field.type == "array") | (field.type == "object")):
                    Textarea(
                        name=f"{state_root}.{field.name}",
                        placeholder="JSON value",
                        rows=4,
                    )
                # 6. fallback -> plain text
                with Else():
                    Input(
                        name=f"{state_root}.{field.name}",
                        placeholder=field.placeholder,
                    )
    # TODO: support nested FieldSpecs with dotted name paths (e.g. `config.db_password`)
    # to render arbitrary-depth JSON sub-trees as their own form sections.


def _render_connector_combobox(option_count: int) -> None:
    """One Combobox with `option_count` static ComboboxOption children.

    Each option binds to `availableConnectors.{i}` via a template literal so
    the picker stays reactive as the array updates. See `_render_length_unrolled`
    for why options can't be a `ForEach` child of `Combobox`.
    """
    with Combobox(name="connectorPickerValue", placeholder="Add a connector..."):
        for i in range(option_count):
            ComboboxOption(
                label=f"{{{{ availableConnectors.{i}.label }}}}",
                value=f"{{{{ availableConnectors.{i}.value }}}}",
            )


def _render_connectors_combobox() -> None:
    """Reactive connector picker over `availableConnectors` (capped at MAX)."""
    _render_length_unrolled(
        STATE.availableConnectors.length(),
        MAX_CONNECTOR_OPTIONS,
        _render_connector_combobox,
    )
    with If(STATE.availableConnectors.length() > MAX_CONNECTOR_OPTIONS):
        Alert(
            variant="warning",
            title="Connector list truncated",
            description=f"Showing the first {MAX_CONNECTOR_OPTIONS} connector options.",
        )


# -----------------------------------------------------------------------------
# Custom App Styling
# -----------------------------------------------------------------------------

APP_STYLES = """
:root { color-scheme: dark; }

html, body, #root {
  background:
    radial-gradient(circle at 12% 12%, rgba(54, 255, 181, 0.22), transparent 26%),
    radial-gradient(circle at 88% 10%, rgba(86, 191, 255, 0.24), transparent 24%),
    linear-gradient(180deg, #07110f 0%, #0c1717 36%, #111b1e 100%) !important;
  color: #edf7f2;
}

.pf-app-root {
  color: #edf7f2 !important;
  font-family: "Avenir Next", "Inter", "Segoe UI", sans-serif;
}

.pf-app-root input,
.pf-app-root textarea,
.pf-app-root select,
.pf-app-root [role="combobox"],
.pf-app-root [role="textbox"] {
  color: #f5fffb !important;
  background: rgba(9, 20, 20, 0.82) !important;
  border: 1px solid rgba(109, 247, 187, 0.18) !important;
}

.pf-app-root input::placeholder,
.pf-app-root textarea::placeholder { color: #93a7a0 !important; }
.pf-app-root select option { color: #081111 !important; }

.pf-app-root .designer-hero,
.pf-app-root.designer-hero,
.designer-hero.pf-card,
.designer-hero {
  background:
    radial-gradient(circle at top left, rgba(82, 255, 173, 0.18), transparent 28%),
    radial-gradient(circle at bottom right, rgba(93, 162, 255, 0.16), transparent 34%),
    linear-gradient(135deg, rgba(8, 18, 19, 0.96) 0%, rgba(15, 31, 30, 0.96) 52%, rgba(22, 46, 39, 0.96) 100%) !important;
  border: 1px solid rgba(112, 244, 191, 0.28) !important;
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.38) !important;
  color: #edf7f2 !important;
}

.pf-app-root .glass-card,
.glass-card.pf-card,
.glass-card {
  background: linear-gradient(180deg, rgba(11, 24, 24, 0.92) 0%, rgba(14, 29, 29, 0.94) 100%) !important;
  border: 1px solid rgba(120, 245, 194, 0.18) !important;
  box-shadow: 0 14px 32px rgba(0, 0, 0, 0.28) !important;
  backdrop-filter: blur(14px);
  color: #edf7f2 !important;
}
"""


# -----------------------------------------------------------------------------
# MCP App Assembly & Server Setup
# -----------------------------------------------------------------------------

def _build_app(initial_state: dict[str, Any]) -> PrefabApp:
    selected_job_type = initial_state.get("selectedJobType") or ""
    selected_environment = initial_state.get("environment") or "dev"
    selected_job_type_ref = Rx("selectedJobType")
    environment_ref = f"{{{{ environment | '{selected_environment}' }}}}"
    refresh_types_action = _refresh_job_types_action(set_loading=False)
    refresh_connectors_action = _refresh_connectors_action(
        job_type_expr=selected_job_type_ref,
        environment_expr=environment_ref,
    )
    refresh_connectors_on_environment_change = _refresh_connectors_action(
        job_type_expr=selected_job_type_ref,
        environment_expr=EVENT,
    )
    load_schema_on_change = _load_schema_action(EVENT)
    create_action = _create_job_action(environment_expr=environment_ref)
    run_action = _trigger_run_action(environment_expr=environment_ref)
    update_ai_context_action = _update_ai_context_action()
    review_draft_action = _review_draft_action()
    preview_ai_suggested_changes_action = _preview_ai_suggested_changes_action()
    # Build-time job type list — what we render into SelectOptions. Prefab Select
    # children must be static (see `_render_length_unrolled`), so post-boot
    # `availableJobTypes` state updates won't add new options to this dropdown.
    static_job_types = list(initial_state.get("availableJobTypes") or [])

    # on_mount auto-sync: when the iframe first paints, immediately reconcile its
    # local Prefab state with the server-side latest_draft_snapshot. Makes opening
    # the designer in a fresh tab pick up any draft work already in flight from
    # another tab / earlier session. Silent so a clean designer doesn't toast.
    with Column(gap=4, on_mount=[_sync_ai_draft_to_form_action(silent=True)]) as view:
        # ── Hero ─────────────────────────────────────────────────────────────
        with Card(css_class="designer-hero"):
            with CardHeader():
                with Column(gap=2):
                    Badge("Control Center", variant="outline")
                    H1("Create a job")
                    Muted("Describe what you need, choose how it runs, and let AI help fill in the details.")
            with CardContent():
                with Column(gap=3):
                    with Grid(columns={"md": 3}, gap=4):
                        with Field():
                            FieldTitle("Job type")
                            with FieldContent():
                                with Select(
                                    name="selectedJobType",
                                    value=selected_job_type,
                                    on_change=[
                                        SetState("selectedJobType", EVENT),
                                        # Pre-wipe contract-shaped state so values from the prior
                                        # JobType can't bleed in before applySchemaChange runs.
                                        SetState("config", {}),
                                        SetState("params", {}),
                                        SetState("selectedConnectors", []),
                                        SetState("connectorPickerValue", ""),
                                        SetState("connectorText", ""),
                                        SetState("runPrompt", ""),
                                        SetState("loading", True),
                                        load_schema_on_change,
                                    ],
                                ):
                                    for jt in static_job_types:
                                        job_type = jt.get("type") or ""
                                        if not job_type:
                                            continue
                                        SelectOption(
                                            jt.get("display_name") or job_type,
                                            value=job_type,
                                            selected=job_type == selected_job_type,
                                        )
                        with Field():
                            FieldTitle("Environment")
                            with FieldContent():
                                with Select(
                                    name="environment",
                                    value=selected_environment,
                                    on_change=[
                                        SetState("environment", EVENT),
                                        SetState("loading", True),
                                        refresh_connectors_on_environment_change,
                                    ],
                                ):
                                    for value, opt_label in _ENVIRONMENT_OPTIONS:
                                        SelectOption(
                                            opt_label,
                                            value=value,
                                            selected=value == selected_environment,
                                        )
                    with Row(gap=3, css_class="flex-wrap pt-1"):
                        Button(
                            "Update AI context",
                            icon="speech",
                            variant="success",
                            on_click=update_ai_context_action,
                        )
                        Button(
                            "Refresh data",
                            icon="cloud-sync",
                            variant="outline",
                            on_click=[
                                SetState("loading", True),
                                refresh_types_action,
                                refresh_connectors_action,
                            ],
                        )
                        with Dialog(
                            title="Review AI Suggestions",
                            description="Review and approve the proposed updates to your job draft.",
                            dismissible=False,
                            name="suggestionsPending",
                            css_class="w-full max-w-2xl",
                        ):
                            Button(
                                "Apply AI draft",
                                variant="outline",
                                icon="square-pen",
                                on_click=[
                                    SetState("loading", True),
                                    preview_ai_suggested_changes_action,
                                ],
                            )
                            with Column(gap=3, css_class="max-h-[60vh] overflow-y-auto pr-2"):
                                with If("{{ pendingAiSuggestions.length > 0 }}"):

                                    with ForEach("pendingAiSuggestions") as (i, item):
                                        with ChoiceCard(css_class="hover:bg-emerald-500/5 transition-colors"):
                                            with Row(gap=4, css_class="w-full justify-between items-center"):

                                                with If(item.is_long):
                                                    # LEFT SIDE: Checkbox + Button acting as label (rigid, no squishing or wrapping)
                                                    with Row(gap=2, align="center", css_class="flex-shrink-0 whitespace-nowrap"):
                                                        Checkbox(name=f"pendingAiSuggestions.{i}.selected")
                                                        with HoverCard():
                                                            Button(item.label, variant="ghost", icon="text-wrap", size="sm")
                                                            with Column(gap=3, css_class="p-4 bg-neutral-900 border border-emerald-500/20 rounded-xl max-w-md"):
                                                                Text(content=item.label, css_class="font-bold text-xs uppercase opacity-50")
                                                                Text(content=item.before, css_class=f"{item.before_css} block whitespace-pre-wrap text-xs max-h-40 overflow-y-auto")
                                                                Span("↓", css_class="opacity-30 mx-auto text-xs")
                                                                Text(content=item.after, css_class=f"{item.after_css} block whitespace-pre-wrap text-xs max-h-40 overflow-y-auto")
                                                    # RIGHT SIDE: Truncated Diff (stretch to fill space, push content right)
                                                    with Row(gap=2, align="center", css_class="flex-1 min-w-0 justify-end"):
                                                        Span(item.before, css_class=f"{item.before_css} truncate max-w-[200px] font-mono bg-white/5 px-2 py-0.5 rounded-md text-[11px]")
                                                        Span("→", css_class="opacity-30 text-xs mx-1 flex-shrink-0")
                                                        Span(item.after, css_class=f"{item.after_css} truncate max-w-[200px] font-mono bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-md text-[11px]")

                                                with Else():
                                                    # LEFT SIDE: Standard Checkbox with label (rigid, no squishing or wrapping)
                                                    with Row(align="center", css_class="flex-shrink-0 whitespace-nowrap"):
                                                        Checkbox(name=f"pendingAiSuggestions.{i}.selected", label=item.label)
                                                    # RIGHT SIDE: Un-truncated Diff (stretch to fill space, push content right)
                                                    with Row(gap=2, align="center", css_class="flex-1 min-w-0 justify-end"):
                                                        Span(item.before, css_class=f"{item.before_css} font-mono bg-white/5 px-2 py-0.5 rounded-md text-[11px]")
                                                        Span("→", css_class="opacity-30 text-xs mx-1 flex-shrink-0")
                                                        Span(item.after, css_class=f"{item.after_css} font-mono bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-md text-[11px]")

                                with If("{{ !(pendingAiSuggestions | length) }}"):
                                    Muted("No changes are available to apply.")

                            # Collapsible raw-JSON payload for deeper inspection.
                            with If("{{ pendingAiSuggestions.length > 0 }}"):
                                with Accordion(css_class="mt-2 border-t border-white/10 pt-2 w-full min-w-0"):
                                    with AccordionItem(value="raw_json_patch", title="View Raw JSON Payload"):
                                        with Div(css_class="w-full min-w-0 max-h-64 overflow-auto"):
                                            Code(
                                                content="{{ rawAiPatchText }}", language="json",
                                                css_class="text-xs whitespace-pre block",
                                            )

                            with Row(gap=2, css_class="justify-end"):
                                Button(
                                    "Cancel",
                                    variant="outline",
                                    on_click=[
                                        SetState("suggestionsPending", False),
                                        SetState("pendingAiSuggestions", []),
                                        CloseOverlay(),
                                    ]
                                )
                                Button(
                                    "Apply Changes",
                                    variant="destructive",
                                    disabled="{{ !(pendingAiSuggestions | selectattr:'selected' | length) }}",
                                    on_click=[
                                        CallHandler("applySelectedAiSuggestions"),
                                        CloseOverlay(),
                                        ShowToast("Selected AI changes applied.", variant="success"),
                                    ],
                                )
                        with If(STATE.loading):
                            with Row(gap=2, align="center"):
                                Loader(variant="spin", size="sm")
                                Muted("Working…")
                    with If(STATE.lastDraftCapturedAt):
                        Muted(f"Last AI context update: {STATE.lastDraftCapturedAt.datetime()}")

        # ── Intent-driven seed (Name + Intent, single row) ───────────────────
        # The minimum a beginner needs to start a job: a label and an
        # intent. Everything else can be filled out with the help of an
        # LLM consuming the JobDraft Pydantic model.
        with Card(css_class="glass-card"):
            with CardContent():
                with Grid(columns={"md": 3}, gap=4):
                    # Name — label inline with input.
                    with Row(align="center", gap=3, css_class="w-full"):
                        Label("Name", css_class="shrink-0")
                        with Div(css_class="flex-1 min-w-0"):
                            Input(name="jobName", placeholder="Brief job title")
                    # Intent — same inline layout, label is a clickable Popover
                    # trigger so beginners can drill into "what counts as intent?"
                    # without polluting the row with description text.
                    with Div(css_class="md:col-span-2"):
                        with Row(align="center", gap=3, css_class="w-full"):
                            with Popover(
                                title="What is intent?",
                                description="The plain-English seed an LLM uses to auto-fill the rest of this form.",
                                side="bottom",
                            ):
                                # Popover's first child is the trigger; group the wand icon
                                # and label into one Row so they click as a single affordance.
                                # The wand carries the emerald accent on its own; the label
                                # stays default white to read as a peer of "Name".
                                with Row(
                                    align="center",
                                    gap=2,
                                    css_class="shrink-0 cursor-pointer group",
                                ):
                                    Icon(
                                        "wand-sparkles",
                                        size="sm",
                                        css_class="text-emerald-300 group-hover:text-emerald-200",
                                    )
                                    Label(
                                        "Intent",
                                        css_class="cursor-pointer underline decoration-dotted underline-offset-4 decoration-emerald-400/40 group-hover:decoration-emerald-400",
                                    )
                                with Column(gap=3, css_class="max-w-sm"):
                                    Text(
                                        content=(
                                            "Describe what this job should accomplish in plain English. "
                                            "Connectors, config, and run-time params can all be filled in later "
                                            "from the intent — manually or via an AI draft."
                                        ),
                                        css_class="text-sm leading-relaxed",
                                    )
                                    Muted(
                                        "Example: \"Pull daily Toyota special deals for Dallas and email a summary.\""
                                    )
                                    Button(
                                        "Generate full draft",
                                        icon="wand-sparkles",
                                        variant="success",
                                        disabled="{{ !intent }}",
                                        on_click=[
                                            SetState("loading", True),
                                            CallTool(
                                                "generate_full_job_draft",
                                                arguments={
                                                    # Sole-value Prefab templates pass through as the literal string
                                                    # when the referenced state key is undefined (per Prefab docs:
                                                    # "{{ missing }}" → "{{ missing }}" rather than null/""). The
                                                    # `| default` pipe forces resolution so the server gets a real
                                                    # value, not the template text.

                                                    "intent": "{{ intent }}",
                                                    "job_name": "{{ jobName }}",
                                                    "environment": "{{ environment | 'dev' }}",
                                                },
                                                on_success=[
                                                    *_sync_ui_result_to_form_actions(),
                                                    CloseOverlay(),
                                                    ShowToast(
                                                        "{{ $result.meta.job_type_reasoning }}",
                                                        variant="info",
                                                    ),
                                                ],
                                                on_error=[
                                                    SetState("loading", False),
                                                    ShowToast(ERROR, variant="error"),
                                                ],
                                            ),
                                        ],
                                    )
                            with Div(css_class="flex-1 min-w-0"):
                                Input(
                                    name="intent",
                                    placeholder="What should this job accomplish?",
                                )

        # ── Job type contract summary ────────────────────────────────────────
        with If(STATE.formSchema.type):
            with Card(css_class="glass-card"):
                with CardHeader():
                    CardTitle(STATE.formSchema.display_name)
                    with If(STATE.formSchema.description):
                        CardDescription(STATE.formSchema.description)
                with If(STATE.formSchema.connector_types.length() > 0):
                    with CardContent():
                        with Column(gap=2):
                            Small("Allowed connector types")
                            Muted(STATE.formSchema.connector_types.join(", ").default("any"))

        # ── Connector picker ─────────────────────────────────────────────────
        with Card(css_class="glass-card"):
            with CardHeader():
                CardTitle("Connectors")
                CardDescription(
                    "Add one or more approved connectors for the selected job type and environment."
                )
            with CardContent():
                with Column(gap=5):
                    with If(STATE.availableConnectors.length() > 0):
                        with Field():
                            with FieldContent():
                                with Row(gap=2, align="center", css_class="w-full"):
                                    with Div(css_class="flex-1 min-w-0"):
                                        _render_connectors_combobox()
                                    Button(
                                        "Add",
                                        css_class="shrink-0 min-w-24",
                                        disabled="{{ !connectorPickerValue }}",
                                        on_click=CallHandler("pushConnectorToList"),
                                    )
                        with If(STATE.selectedConnectors.length() > 0):
                            with Column(gap=2, css_class="pt-1"):
                                Small("Selected connectors")
                                with ForEach("selectedConnectors") as connector:
                                    with Row(gap=2, align="center", css_class="justify-between"):
                                        Badge(connector, variant="outline")
                                        Button(
                                            "Remove",
                                            variant="outline",
                                            size="sm",
                                            on_click=PopState("selectedConnectors", index="{{ $index }}"),
                                        )
                    with Else():
                        Alert(
                            variant="info",
                            title="No connectors found",
                            description=("No registered connectors match this job type and environment."),
                        )
                    with Div(css_class="border-t border-emerald-200/10 pt-4"):
                        with Field():
                            FieldDescription("Manual fallback for connectors that are not listed above.")
                            with FieldContent():
                                Input(name="connectorText", placeholder="Comma-separated names, e.g., github, sql, control-center")

        # ── Job basics ───────────────────────────────────────────────────────
        with Card(css_class="glass-card"):
            with CardHeader():
                CardTitle("Job basics")
            with CardContent():
                # Inline-label layout mirroring the Name/Intent card above:
                # short field (1 col) on the left, long field (2 cols) on the right.
                with Grid(columns={"md": 3}, gap=4):
                    with Row(align="center", gap=3, css_class="w-full"):
                        Label("Data sensitivity", css_class="shrink-0")
                        with Div(css_class="flex-1 min-w-0"):
                            initial_sensitivity = initial_state.get("dataSensitivity", "low")
                            with Select(name="dataSensitivity", value=initial_sensitivity or None):
                                for value, opt_label in _DATA_SENSITIVITY_OPTIONS:
                                    SelectOption(opt_label, value=value, selected=value == initial_sensitivity)
                    with Div(css_class="md:col-span-2"):
                        with Row(align="center", gap=3, css_class="w-full"):
                            Label("Tags", css_class="shrink-0")
                            with Div(css_class="flex-1 min-w-0"):
                                Input(name="tagsText", placeholder="finance, daily, mcp, etc.")

        # ── Dynamic config form (driven by the selected JobTypeContract) ─────
        with If(STATE.formSchema.config_fields.length() > 0):
            with Card(css_class="glass-card"):
                with CardHeader():
                    CardTitle("Configuration")
                    CardDescription("Stored on the job. Reused across runs.")
                with CardContent():
                    with Column(gap=4):
                        _render_field_loop("config", "formSchema.config_fields")

        with If((STATE.selectedJobType.length() > 0) & (STATE.formSchema.config_fields.length() == 0)):
            Alert(
                variant="info",
                title="No config fields",
                description="The selected job type has no configurable fields.",
            )

        # ── Run-time params (filled now, forwarded at trigger_run) ───────────
        with If(STATE.formSchema.params_fields.length() > 0):
            with Card(css_class="glass-card"):
                with CardHeader():
                    CardTitle("Run-time parameters")
                    CardDescription(
                        "Per-run values. Sensitive fields (passwords, tokens) "
                        "are passed ephemerally and never stored."
                    )
                with CardContent():
                    with Column(gap=4):
                        _render_field_loop("params", "formSchema.params_fields")
                        with Field():
                            FieldTitle("Run prompt (optional)")
                            FieldDescription("Free-form instruction passed alongside params.")
                            with FieldContent():
                                Textarea(name="runPrompt", placeholder="…", rows=3)

        # ── Submit ───────────────────────────────────────────────────────────
        with Card(css_class="glass-card"):
            with CardFooter():
                with Row(gap=3, css_class="flex-wrap"):
                    Button("Create job", variant="success", on_click=[SetState("loading", True), create_action])
                    with If(STATE.createdJob.id):
                        Button("Trigger run", variant="success", on_click=[SetState("loading", True), run_action])
                    Button(
                        "Get AI feedback",
                        icon="lightbulb",
                        variant="outline",
                        on_click=review_draft_action,
                    )
                    Button(
                        "Reset form",
                        icon="trash-2",
                        variant="outline",
                        on_click=CallHandler("resetDesignerForm"),
                    )

        # ── Created job summary ──────────────────────────────────────────────
        with If(STATE.createdJob.id):
            with Card(css_class="glass-card"):
                with CardHeader():
                    CardTitle("Job registered")
                    CardDescription("Visible to your domain in Control Center.")
                with CardContent():
                    with Column(gap=2):
                        P(Text("Job ID: ") + STATE.createdJob.id)
                        P(Text("Status: ") + STATE.createdJob.status)
                        P(Text("Risk: ") + STATE.createdJob.risk_level.default("low"))
                        P(Text("Connector: ") + STATE.createdJob.connector)

        # ── Last run summary ────────────────────────────────────────────────
        with If(STATE.lastRun.id):
            with Card(css_class="glass-card"):
                with CardHeader():
                    CardTitle("Last run")
                with CardContent():
                    with Column(gap=2):
                        P(Text("Run ID: ") + STATE.lastRun.id)
                        P(Text("Status: ") + STATE.lastRun.status)
                        P(Text("Risk: ") + STATE.lastRun.risk_level)
                        with If(STATE.lastRun.requires_approval):
                            Alert(
                                variant="warning",
                                title="Approval required",
                                description=(
                                    "This run was queued pending approval. Approval "
                                    "ID: " + STATE.lastRun.approval_id.default("—")
                                ),
                            )
                        with If(STATE.lastRun.error):
                            Alert(variant="error", title="Run error", description=STATE.lastRun.error)

    return PrefabApp(
        view=view,
        state=initial_state,
        theme=Theme(mode="dark", gradient=False),
        css_class="max-w-5xl px-4 py-6 md:px-6",
        stylesheets=[APP_STYLES],
        title="Control Center Job Designer",
        js_actions=JS_ACTIONS,
    )


def build_server() -> FastMCP:
    mcp = FastMCP(SERVER_NAME, instructions=SERVER_DESCRIPTION)

    mcp.add_provider(
        Approval(
            title="Apply AI Changes?",
            approve_text="Approve",
            reject_text="Cancel",
            approve_variant="success",
        )
    )

    bootstrap_types = forms.static_job_types()
    logger.info("Bootstrapped %d job types into the designer", len(bootstrap_types))

    # ─── Draft state (single-session, single-client) ───────────────────────
    # These are process-global on purpose: this server is intended to run as a
    # personal/single-tenant designer where one user drives one iframe at a
    # time. Concurrent clients would stomp each other's drafts here.
    #
    # To scale to multi-tenant or production:
    #   - swap these for ctx.set_state / ctx.get_state on each tool (session-
    #     keyed, isolated per mcp-session-id), or
    #   - keep the same shape but back it with a distributed store via
    #     FastMCP(..., session_state_store=RedisStore(...)) — see
    #     https://gofastmcp.com/servers/storage-backends
    # Caveat: some hosts (notably ChatGPT today) don't preserve
    # mcp-session-id across calls, so a stable per-document key
    # (e.g. an explicit draft_id tool arg) may be needed regardless.
    iframe_boot_state = _initial_state(job_types=bootstrap_types)
    latest_draft_snapshot: dict[str, Any] = _capture_draft_snapshot(iframe_boot_state)
    blank_app = _build_app(iframe_boot_state)

    @mcp.resource(
        APP_RESOURCE_URI,
        name="control_center_job_designer",
        description="Interactive job designer — pick a type, fill the contract-driven form, create or trigger jobs.",
        app=AppConfig(
            csp=_resource_csp_for(blank_app),
            domain=APP_RESOURCE_DOMAIN,
            prefers_border=True,
        ),
    )
    def control_center_job_designer_resource() -> str:
        return _build_app(iframe_boot_state).html(tool_resolver=_resolve_prefab_tool)

    @mcp.tool(
        name="open_job_designer",
        description="Open the interactive Control Center job designer.",
        app=AppConfig(resource_uri=APP_RESOURCE_URI, prefers_border=True),
    )
    def open_job_designer(
        job_type: str = "",
        environment: str = "dev",
        reset: bool = False,
    ) -> dict[str, Any]:
        nonlocal latest_draft_snapshot, iframe_boot_state

        # Idempotent by default: a second open (e.g. another tab, a re-issued
        # tool call) preserves whatever draft is already in flight so the
        # iframe's on_mount auto-sync can pull it in. Pass reset=True for a
        # fresh start that wipes both vars.
        draft = latest_draft_snapshot.get("draft", {}) if isinstance(latest_draft_snapshot, dict) else {}
        has_work_in_progress = bool(
            draft.get("selected_job_type") or draft.get("intent") or draft.get("job_name")
        )

        if reset or not has_work_in_progress:
            iframe_boot_state = _initial_state(
                job_types=bootstrap_types,
                selected_type=forms.normalize_job_type(job_type),
                environment=(environment or "dev").strip().lower(),
            )
            latest_draft_snapshot = _capture_draft_snapshot(iframe_boot_state)
            status = "opened"
        else:
            status = "reattached"

        return {
            "status": status,
            "selectedJobType": iframe_boot_state["selectedJobType"],
            "environment": iframe_boot_state["environment"],
        }

    @mcp.tool(
        name="list_job_types",
        description="List all known JobTypeContracts available to this Control Center deployment.",
    )
    def list_job_types() -> dict[str, Any]:
        try:
            items = [forms.job_type_summary(c) for c in forms.job_type_items(utils.api_get("/job-types"))]
        except Exception as exc:
            logger.warning("list_job_types failed: %s", exc)
            items = []
        return {"items": forms.merge_job_type_summaries(forms.static_job_types(), items)}

    @mcp.tool(
        name="get_form_schema",
        description="Fetch the form schema for a job type (config/params fields, required lists, connector types).",
    )
    def get_form_schema(job_type: str) -> dict[str, Any]:
        normalized = forms.normalize_job_type(job_type)
        if not normalized:
            return forms.empty_form_schema_payload()
        return forms.resolve_job_type_schema(normalized, allow_api_fallback=True)

    @mcp.tool(
        name="list_connectors",
        description="List connectors. Filter by connector_type (e.g. 'sql-mcp') and/or environment.",
    )
    def list_connectors(
        job_type: str = "",
        connector_type: str = "",
        connector_types: list[str] | None = None,
        environment: str = "",
    ) -> dict[str, Any]:
        normalized_job_type = forms.normalize_job_type(job_type)
        allowed_connector_types = forms.resolve_connector_types(
            job_type=normalized_job_type,
            connector_types=connector_types,
            connector_type=connector_type,
        )
        if not allowed_connector_types:
            return {"items": []}
        params: dict[str, str] = {}
        if len(allowed_connector_types) == 1:
            params["connector_type"] = allowed_connector_types[0]
        if environment:
            params["env"] = environment
        try:
            response = utils.api_get("/connectors", params=params or None)
        except Exception as exc:
            logger.warning("list_connectors failed: %s", exc)
            response = {"items": []}

        items = response.get("items", []) if isinstance(response, dict) else (response or [])
        if len(allowed_connector_types) > 1:
            allowed = set(allowed_connector_types)
            items = [
                c
                for c in items
                if isinstance(c, dict)
                and (
                    c.get("connector_type") in allowed
                    or c.get("id") in allowed
                    or c.get("name") in allowed
                )
            ]
        items = forms.merge_connector_items(items, allowed_connector_types, environment)
        return {
            "items": [
                {
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "connector_type": c.get("connector_type"),
                    "environment": c.get("environment"),
                    "status": c.get("status"),
                    "is_shared": c.get("is_shared", False),
                    "label": forms.connector_display_label(c),
                    "value": forms.connector_value(c),
                }
                for c in items
            ]
        }

    @mcp.tool(
        name="capture_current_draft",
        description="Capture iframe form state as the latest draft snapshot.",
        app=AppConfig(resource_uri=APP_RESOURCE_URI, visibility=["app"]),
        tags={"internal"},
    )
    def capture_current_draft(current_state: dict[str, Any]) -> dict[str, Any]:
        nonlocal latest_draft_snapshot

        if not isinstance(current_state, dict):
            raise ValueError("current_state must be an object supplied by the Prefab UI.")
        if not _REQUIRED_UI_STATE_KEYS.issubset(current_state):
            raise ValueError(
                "capture_current_draft requires a Prefab UI state payload. "
                "Use get_draft_snapshot to read drafts or patch_draft_snapshot to edit them."
            )

        latest_draft_snapshot = _capture_draft_snapshot(current_state)
        # AI sees this via UpdateContext (iframe's _capture_current_draft_action).
        # Server-side store keeps real values; redact only the wire copy.
        return _redact_snapshot(latest_draft_snapshot)

    @mcp.tool(
        name="get_draft_snapshot",
        description="Return the latest captured job designer draft. Reflects the last UI capture, not live browser state.",
    )
    def get_draft_snapshot() -> dict[str, Any]:
        return _redact_snapshot(latest_draft_snapshot)

    @mcp.tool(
        name="patch_draft_snapshot",
        description=(
            "Patch the latest captured draft. Use config/params for merge updates; "
            "replace_config/replace_params for full replacement. Omitted fields are preserved."
        ),
    )
    def patch_draft_snapshot(
        patch: dict[str, Any],
        summary: str = "",
    ) -> dict[str, Any]:
        nonlocal latest_draft_snapshot

        if not isinstance(patch, dict):
            raise ValueError("patch must be an object.")

        # Drop redaction markers the model may echo back so we don't overwrite
        # real secrets with `•••`.
        for section_key in ("config", "params", "replace_config", "replace_params"):
            section = patch.get(section_key)
            if isinstance(section, dict):
                patch[section_key] = {k: v for k, v in section.items() if v != utils.SECRET_MARKER}

        base_draft = latest_draft_snapshot.get("draft", {})
        base_state = _draft_to_ui_state(base_draft)

        result = _apply_designer_patch(base_state, patch)

        if summary:
            result["summary"] = summary

        latest_draft_snapshot = _capture_draft_snapshot(result)
        redacted = _redact_snapshot(latest_draft_snapshot)

        return {
            **result,
            "draft": redacted["draft"],
            "draft_json": redacted["draft_json"],
            "note": (
                "Patched the latest captured draft snapshot. If the browser form changed "
                "since the last capture, click Update AI context before asking for more edits. "
                "Click Sync AI draft to form before creating the job."
            ),
        }

    @mcp.tool(
        name="generate_full_job_draft",
        description="Auto-fill the whole job draft from a plain-English intent via two Instructor calls (pick JobType, then fill contract-shaped fields). Returns a redacted snapshot.",
        app=AppConfig(resource_uri=APP_RESOURCE_URI, visibility=["app"]),
        tags={"internal"},
    )
    async def generate_full_job_draft(
        intent: str,
        job_name: str = "",
        environment: str = "dev",
    ) -> dict[str, Any]:
        nonlocal latest_draft_snapshot

        if not intent or not intent.strip():
            raise ValueError("intent must be a non-empty string.")

        patch = await generate_job_draft_from_intent(
            intent=intent.strip(),
            name=(job_name or "").strip(),
            environment=(environment or "dev").strip().lower(),
        )

        # Reuse the existing patch pipeline: it handles schema reload on type
        # change, config/params merge semantics, and connector list resets.
        base_state = _draft_to_ui_state(latest_draft_snapshot.get("draft", {}))
        result = _apply_designer_patch(base_state, patch)
        latest_draft_snapshot = _capture_draft_snapshot(result)
        redacted = _redact_snapshot(latest_draft_snapshot)
        return {
            **result,
            "draft": redacted["draft"],
            "draft_json": redacted["draft_json"],
            "meta": patch.get("meta"),
        }

    @mcp.tool(
        name="get_current_draft_ui_state",
        description="Return the latest draft as Prefab UI state for iframe sync.",
        app=AppConfig(resource_uri=APP_RESOURCE_URI, visibility=["app"]),
        tags={"internal"},
    )
    def get_current_draft_ui_state() -> dict[str, Any]:
        draft = latest_draft_snapshot.get("draft", {})
        state = _draft_to_ui_state(draft)
        return {
            "status": "loaded",
            "message": "Loaded latest AI draft into the form.",
            "applied": [],
            **state,
        }

    @mcp.tool(
        name="test_tool",
        description="THIS WORK ????.",
        app=AppConfig(resource_uri=APP_RESOURCE_URI, visibility=["app"]),
    )
    def get_current_draft_ui_state() -> dict[str, Any]:
        return {
            "status": "loaded",
            "message": "YUP, IT WORKS.",
        }

    @mcp.tool(
        name="preview_ai_suggested_changes",
        description="Diff iframe form state against the latest AI draft.",
        app=AppConfig(resource_uri=APP_RESOURCE_URI, visibility=["app"]),
        tags={"internal"},
    )
    def preview_ai_suggested_changes(current_state: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(current_state, dict):
            raise ValueError("current_state must be a Prefab UI state object.")

        current_draft = _ui_state_to_draft(current_state)
        proposed_draft = latest_draft_snapshot.get("draft") or {}
        changes = _flatten_draft_changes(current_draft, proposed_draft)

        clean_display_payload = [
            {
                "label": item["label"],
                "current_value": item["before"],
                "proposed_update": item["updates"]
            }
            for item in changes
        ]
        raw_changes_text = json.dumps(clean_display_payload, indent=2)

        return {
            "status": "ready",
            "change_count": len(changes),
            "changes": changes,
            "raw_changes_text": raw_changes_text,
        }

    @mcp.tool(
        name="create_job",
        description="Register a new Control Center job. Config is coerced via the selected JobTypeContract.",
    )
    def create_job(
        name: str,
        type: str,
        connector: str,
        environment: str = "dev",
        config: dict | None = None,
        data_sensitivity: str = "low",
        tags_text: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        if not name or not name.strip():
            raise ValueError("Job name is required.")
        normalized_type = forms.normalize_job_type(type)
        if not normalized_type:
            raise ValueError("Job type is required — pick one from the job-type selector.")
        if not connector or not connector.strip():
            raise ValueError("Connector is required.")
        normalized_environment = environment.strip().lower() if environment else "dev"
        if not normalized_environment:
            raise ValueError("Environment is required — pick one from the environment selector.")

        merged_tags = list(tags or []) + [t.strip() for t in (tags_text or "").split(",") if t.strip()]

        try:
            schema = forms.resolve_job_type_schema(normalized_type, allow_api_fallback=True)
            config = forms.coerce_field_values(schema["config_fields"], config or {})
        except Exception as exc:
            logger.warning("create_job: schema coercion skipped, sending raw config: %s", exc)
            config = config or {}

        body = {
            "name": name.strip(),
            "type": normalized_type,
            "connector": connector.strip(),
            "environment": normalized_environment,
            "config": config,
            "data_sensitivity": data_sensitivity,
            "tags": sorted({t for t in merged_tags if t}),
        }
        return utils.api_post("/jobs", body)

    @mcp.tool(
        name="trigger_run",
        description="Trigger a run for an existing job. Optionally pass per-run params and a prompt.",
    )
    def trigger_run(
        job_id: str,
        action: str = "run",
        target_environment: str = "dev",
        params: dict | None = None,
        prompt: str | None = None,
    ) -> dict[str, Any]:
        if not job_id:
            raise ValueError("job_id is required.")

        try:
            job = utils.api_get(f"/jobs/{job_id}")
            schema = forms.resolve_job_type_schema(job["type"], allow_api_fallback=True)
            params = forms.coerce_field_values(schema["params_fields"], params or {})
        except Exception as exc:
            logger.warning("trigger_run: param coercion skipped: %s", exc)
            params = params or {}

        body: dict[str, Any] = {
            "action": action,
            "target_environment": target_environment,
            "params": params,
        }
        if not body["target_environment"]:
            raise ValueError("Target environment is required.")
        if prompt and prompt.strip():
            body["prompt"] = prompt.strip()
        return utils.api_post(f"/jobs/{job_id}/runs", body)

    @mcp.tool(
        name="show_connector_risk_profile",
        description=(
            "Probe a connector by name and return a visual summary of the risk "
            "profile of every MCP tool it exposes, derived from ToolAnnotations "
            "metadata (read-only / destructive / idempotent / external-world hints)."
        ),
        app=True,
    )
    async def show_connector_risk_profile(connector: str) -> PrefabApp:
        if not connector or not connector.strip():
            raise ValueError("connector name is required.")
        profile = await _fetch_connector_tool_profile(connector.strip())
        return _build_risk_profile_app(profile)

    return mcp

# -----------------------------------------------------------------------------
# EXTENSION: Connector Risk Profile MCP App
# -----------------------------------------------------------------------------


# ── Connector risk profile (MCP tool annotations → visualization) ────────────
# Tool authors set ToolAnnotations hints on each tool. They're advisory — not
# always truthful — but they're the only structured risk signal in the MCP
# spec today. When a hint is None the spec's paranoid defaults apply
# (destructive=True, openWorld=True). Better signal will come from execution-
# time evidence (which scopes a tool actually touches), but that's down the road.

_RISK_BANDS: tuple[tuple[str, str, str, str], ...] = (
    # (band_key, label, badge_variant, left-border css for the tool card)
    ("high",    "High risk",   "destructive", "border-l-4 border-rose-500/70"),
    ("medium",  "Medium risk", "warning",     "border-l-4 border-amber-500/70"),
    ("low",     "Low risk",    "success",     "border-l-4 border-emerald-500/60"),
    ("unknown", "Unannotated", "outline",     "border-l-4 border-zinc-500/40"),
)

_SPEC_HINT_DEFAULTS = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": False,
    "openWorldHint": True,
}


def _classify_tool_risk(tool_annotations: dict[str, Any] | None) -> dict[str, Any]:
    """Bucket an MCP ToolAnnotations dict into a risk band + flag summary."""
    if not isinstance(tool_annotations, dict):
        return {
            "band": "unknown",
            "title": "",
            "flags": ["unannotated"],
            "read_only": False, "destructive": False, "idempotent": False, "open_world": False,
        }
    resolved = {
        k: (tool_annotations[k] if tool_annotations.get(k) is not None else default)
        for k, default in _SPEC_HINT_DEFAULTS.items()
    }
    read_only = bool(resolved["readOnlyHint"])
    destructive = bool(resolved["destructiveHint"])
    idempotent = bool(resolved["idempotentHint"])
    open_world = bool(resolved["openWorldHint"])

    if read_only and not open_world:
        band = "low"
    elif read_only:
        band = "medium"  # reads from external systems — still some risk
    elif destructive and open_world:
        band = "high"
    elif destructive or open_world:
        band = "medium"
    else:
        band = "low"

    flags: list[str] = []
    if read_only:
        flags.append("read-only")
    if destructive:
        flags.append("destructive")
    if idempotent:
        flags.append("idempotent")
    if open_world:
        flags.append("external")

    return {
        "band": band,
        "title": str(tool_annotations.get("title") or ""),
        "read_only": read_only, "destructive": destructive,
        "idempotent": idempotent, "open_world": open_world,
        "flags": flags,
    }


async def _fetch_connector_tool_profile(connector_name: str) -> dict[str, Any]:
    """Probe `connector_name` for tools, classify each by risk, compute aggregates.

    Adapted from `backend/scripts/check_registry.py::_probe_and_dump` — same
    LLMClient connect/cleanup discipline, narrowed to one server's tools.
    """
    try:
        from control_center.mcp import LLMClient
        from control_center.registry import RegistryManager
    except ImportError as exc:
        return _profile_error(connector_name, f"missing dependency: {exc}")

    manager = RegistryManager()
    try:
        cfg = manager.get_server_config(connector_name)
    except Exception as exc:
        return _profile_error(connector_name, f"registry lookup: {exc}")

    client = LLMClient()
    tools_data: list[dict[str, Any]] = []
    try:
        await client.connect_to_server(connector_name, cfg)
        raw_tools = await client.list_tools(connector_name)
        for t in raw_tools:
            dump = t.model_dump(mode="json", exclude_none=False) if hasattr(t, "model_dump") else dict(t)
            input_schema = dump.get("inputSchema") or {}
            props = input_schema.get("properties") or {}
            tools_data.append({
                "name": dump.get("name", "?"),
                "description": (dump.get("description") or "").strip(),
                "param_count": len(props),
                "required_count": len(input_schema.get("required") or []),
                "has_output_schema": bool(dump.get("outputSchema")),
                **_classify_tool_risk(dump.get("annotations")),
            })
    except Exception as exc:
        return _profile_error(connector_name, f"probe failed: {exc}")
    finally:
        try:
            await client.cleanup()
        except Exception:
            pass

    band_order = {"high": 0, "medium": 1, "low": 2, "unknown": 3}
    tools_data.sort(key=lambda t: (band_order.get(t["band"], 4), t["name"]))
    band_counts = {b[0]: 0 for b in _RISK_BANDS}
    for t in tools_data:
        band_counts[t["band"]] = band_counts.get(t["band"], 0) + 1

    return {
        "connector": connector_name,
        "ok": True,
        "error": None,
        "tool_count": len(tools_data),
        "band_counts": band_counts,
        "tools": tools_data,
        "aggregates": _compute_profile_aggregates(tools_data),
    }


def _profile_error(connector: str, error: str) -> dict[str, Any]:
    return {
        "connector": connector, "ok": False, "error": error,
        "tool_count": 0, "band_counts": {b[0]: 0 for b in _RISK_BANDS},
        "tools": [], "aggregates": {},
    }


def _compute_profile_aggregates(tools: list[dict[str, Any]]) -> dict[str, Any]:
    """Roll up tool list into summary stats for the at-launch overview.

    - annotation_coverage: how many tools ship at least one explicit hint
    - families: top tool-name prefixes (everything before the first `_`)
    - param_complexity: 0 / 1-3 / 4+ buckets
    - output_schema_coverage: how many tools declare an outputSchema
    """
    from collections import Counter

    total = len(tools)
    annotated = sum(1 for t in tools if t["band"] != "unknown")

    # Family grouping: 1-token prefix is the default, but if one prefix
    # swallows >70% of the tools (e.g. playwright's all-`browser_*`), fall
    # back to 2-token prefixes for finer-grained signal.
    def _prefix(name: str, depth: int) -> str:
        parts = name.split("_", depth)
        return "_".join(parts[:depth]) if len(parts) > depth else (parts[0] if parts else "?")
    one = Counter(_prefix(t["name"], 1) for t in tools if t.get("name"))
    fams = one
    if total and one and one.most_common(1)[0][1] > 0.7 * total:
        two = Counter(_prefix(t["name"], 2) for t in tools if t.get("name"))
        if len(two) > len(one):
            fams = two
    pc = {"zero": 0, "few": 0, "many": 0}
    for t in tools:
        n = t.get("param_count", 0)
        if n == 0: pc["zero"] += 1
        elif n <= 3: pc["few"] += 1
        else: pc["many"] += 1
    out_schema = sum(1 for t in tools if t.get("has_output_schema"))

    return {
        "annotated": annotated,
        "annotation_pct": round(100 * annotated / total) if total else 0,
        "families": fams.most_common(8),
        # "param_complexity": pc,
        "output_schema_count": out_schema,
        "output_schema_pct": round(100 * out_schema / total) if total else 0,
    }


def _build_risk_profile_app(profile: dict[str, Any]) -> PrefabApp:
    """Render the connector-risk-profile UI."""
    title = f"Risk profile: {profile['connector']}"

    if not profile["ok"]:
        with Column(gap=4, css_class="p-6 max-w-3xl") as view:
            with Alert(variant="error"):
                AlertTitle(f"Cannot probe '{profile['connector']}'")
                AlertDescription(profile.get("error") or "Unknown error.")
        return PrefabApp(
            view=view, theme=Theme(mode="dark", gradient=False),
            stylesheets=[APP_STYLES], title=title,
        )

    agg = profile.get("aggregates") or {}

    with Column(gap=4, css_class="p-6 max-w-4xl") as view:
        # ── Hero ─────────────────────────────────────────────────────────
        with Card(css_class="designer-hero"):
            with CardHeader():
                with Column(gap=2):
                    Badge("Connector risk profile", variant="outline")
                    H1(profile["connector"])
                    Muted(
                        f"{profile['tool_count']} tools exposed. Risk is derived from "
                        "MCP ToolAnnotations: author hints, not always truthful."
                    )

        # ── Risk band counters ───────────────────────────────────────────
        with Grid(columns={"md": 4}, gap=3):
            for key, label, variant, _border in _RISK_BANDS:
                count = profile["band_counts"].get(key, 0)
                with Card(css_class="glass-card text-center"):
                    with CardContent():
                        with Column(gap=1, css_class="items-center"):
                            H1(str(count))
                            Badge(label, variant=variant)

        # ── Aggregate stats (annotation coverage, output schema, param mix) ─
        if profile["tool_count"]:
            with Card(css_class="glass-card"):
                with CardContent():
                    with Grid(columns={"md": 2}, gap=4):
                        # Annotation coverage with progress bar
                        with Column(gap=2):
                            with Row(gap=2, align="center", css_class="justify-between"):
                                Small("Annotated by author")
                                Text(content=f"{agg.get('annotated', 0)} / {profile['tool_count']} ({agg.get('annotation_pct', 0)}%)",
                                     css_class="font-mono text-sm")
                            Progress(
                                value=agg.get("annotation_pct", 0),
                                max=100,
                                variant="success" if agg.get("annotation_pct", 0) >= 80 else ("warning" if agg.get("annotation_pct", 0) >= 50 else "destructive"),
                            )
                        # Output schema coverage
                        with Column(gap=2):
                            with Row(gap=2, align="center", css_class="justify-between"):
                                Small("Output schema declared")
                                Text(content=f"{agg.get('output_schema_count', 0)} / {profile['tool_count']} ({agg.get('output_schema_pct', 0)}%)",
                                     css_class="font-mono text-sm")
                            Progress(
                                value=agg.get("output_schema_pct", 0),
                                max=100,
                                variant="info",
                            )

        # ── Tool families ────────────────────────────────────────────────
        families = agg.get("families") or []
        # Render only when there's actual variety AND at least one cluster — a
        # list of all-singletons (every tool in its own "family") is noise.
        if len(families) > 1 and any(count > 1 for _, count in families):
            with Card(css_class="glass-card"):
                with CardHeader():
                    CardTitle("Tool families")
                    CardDescription("Grouped by name prefix.")
                with CardContent():
                    with Row(gap=2, css_class="flex-wrap"):
                        for prefix, count in families:
                            Badge(f"{prefix} × {count}", variant="outline")

        # ── Tools grouped by risk band, collapsed by default ─────────────
        if not profile["tools"]:
            with Card(css_class="glass-card"):
                with CardContent():
                    Muted("This connector exposes no tools.")
        else:
            with Card(css_class="glass-card"):
                with CardHeader():
                    CardTitle("Tools")
                    CardDescription("Click a risk band to expand. Sorted by name within each band.")
                with CardContent():
                    with Accordion():
                        for band_key, band_label, badge_variant, border_css in _RISK_BANDS:
                            tools_in_band = [t for t in profile["tools"] if t["band"] == band_key]
                            if not tools_in_band:
                                continue
                            with AccordionItem(
                                value=f"band-{band_key}",
                                title=f"{band_label}  ·  {len(tools_in_band)} tool{'s' if len(tools_in_band) != 1 else ''}",
                            ):
                                with Column(gap=2):
                                    for tool in tools_in_band:
                                        _render_tool_row(tool, badge_variant, border_css)

    return PrefabApp(
        view=view, theme=Theme(mode="dark", gradient=False),
        stylesheets=[APP_STYLES], title=title,
    )


def _render_tool_row(tool: dict[str, Any], badge_variant: str, border_css: str) -> None:
    """One compact row inside a risk-band AccordionItem."""
    with Card(css_class=f"glass-card {border_css}"):
        with CardContent():
            with Column(gap=2):
                with Row(gap=2, align="center", css_class="flex-wrap"):
                    Text(content=tool["name"], css_class="font-mono font-semibold")
                    for flag in tool["flags"]:
                        Badge(flag, variant=badge_variant if flag == "destructive" else "outline")
                    # Param signal: e.g. "3 params · 1 required"
                    n = tool.get("param_count", 0)
                    if n:
                        req = tool.get("required_count", 0)
                        param_text = f"{n} param{'s' if n != 1 else ''}"
                        if req:
                            param_text += f" · {req} required"
                        Muted(param_text, css_class="text-xs")
                if tool["description"]:
                    desc = tool["description"]
                    Muted(desc[:280] + ("…" if len(desc) > 280 else ""))


# -----------------------------------------------------------------------------
# Control Center MCP Server Initialization
# -----------------------------------------------------------------------------

mcp = build_server()


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8001)
