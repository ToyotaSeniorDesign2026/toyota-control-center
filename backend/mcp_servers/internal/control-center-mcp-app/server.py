"""Control Center Job Designer MCP App.

Interactive Prefab app for creating Control Center jobs. Reactive to the
selected job type's contract: built-in types are loaded from
`control_center.specs.KNOWN_CONTRACTS`, then API-discovered types may fall
back to the backend form-schema endpoint. The UI renders a dynamic form
(text/number/boolean/select/secret) keyed off `FieldSpec`.

Backend wiring (HTTP):
    GET  /job-types                         refresh/discover additional types
    GET  /job-types/{type}/form-schema      fallback for API-discovered types
    GET  /connectors
    POST /jobs
    POST /jobs/{job_id}/runs
    GET  /integrations/mcp/servers

Required environment variables:
    CC_API_BASE_URL    Base URL of the Control Center API (default http://localhost:8000)
    CC_SERVICE_TOKEN   Bearer token matching CC_INTERNAL_SERVICE_TOKEN on the API
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any
from textwrap import dedent, indent

from dotenv import load_dotenv

# Load the backend's .env at import time so launchers that don't propagate the
# shell env (e.g. `fastmcp dev apps`, ChatGPT's MCP connector hitting the HTTP
# transport) still see GOOGLE_API_KEY / OPENAI_API_KEY / CC_SERVICE_TOKEN etc.
# Walks up from this file until it finds a `backend/.env`; safe no-op when run
# from elsewhere because `load_dotenv` accepts a missing path silently.
for _candidate in (Path(__file__).resolve().parents[i] / ".env" for i in range(2, 6)):
    if _candidate.exists():
        load_dotenv(_candidate, override=False)
        break

from pydantic import BaseModel, Field as PydanticField
from datetime import datetime, timezone
from collections.abc import Iterable

import httpx
from fastmcp import FastMCP
from fastmcp.apps import AppConfig, ResourceCSP
from fastmcp.apps.approval import Approval
from fastmcp.server.middleware import Middleware
from prefab_ui import PrefabApp
from prefab_ui.app import ResolvedTool
from prefab_ui.actions import PopState, SetState, ShowToast, CallHandler, CloseOverlay
from prefab_ui.actions.mcp import CallTool, RequestDisplayMode, SendMessage, UpdateContext
from prefab_ui.components import (
    Accordion,
    AccordionItem,
    Alert,
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
from prefab_ui.rx import ERROR, EVENT, Rx
from prefab_ui.themes import Theme

from control_center.specs import KNOWN_CONTRACTS

from job_generation import generate_job_draft_from_intent

logger = logging.getLogger(__name__)

SERVER_NAME = "control-center-job-creator"
SERVER_DESCRIPTION = (
    "Interactive Control Center job designer — pick a job type, choose a "
    "connector, fill the contract-driven form, and create or trigger jobs."
)
APP_RESOURCE_URI = "ui://control-center/job-designer.html"
APP_RESOURCE_DOMAIN = "https://control-center-job-creator.local"

_API_BASE = os.environ.get("CC_API_BASE_URL", "http://localhost:8000").rstrip("/")
_API_TOKEN = os.environ.get("CC_SERVICE_TOKEN", "")
_HTTP_TIMEOUT = 30

_TEMPLATE_EXPR_RE = re.compile(r"^\s*\{\{.*}}\s*$")
_REQUIRED_UI_STATE_KEYS = {"environment", "config", "params", "formSchema"}


def js_handler(body: str) -> str:
    return dedent(body).strip()


JS_DESIGNER_RESET_HELPERS = js_handler("""
    const asArray = (value) => Array.isArray(value) ? value : [];

    const asObject = (value) =>
        value && typeof value === "object" && !Array.isArray(value)
            ? value
            : {};

    const hasDefault = (field, defaults) => {
        if (!field || !field.name) return false;

        return (
            Object.prototype.hasOwnProperty.call(defaults, field.name) ||
            (field.default !== undefined && field.default !== null)
        );
    };

    const defaultValueForField = (field, defaults) => {
        if (Object.prototype.hasOwnProperty.call(defaults, field.name)) {
            return defaults[field.name];
        }

        return field.default;
    };

    const emptyValueForField = (field) => {
        if (!field) return "";

        if (field.sensitive || field.write_only || field.format === "secret") {
            return "";
        }

        switch (field.type) {
            case "boolean":
                return false;
            case "integer":
            case "number":
            case "array":
            case "object":
                return "";
            default:
                return "";
        }
    };

    // Build the section from scratch (no key carry-over from previous schema).
    // Defaults from the schema win; otherwise empty per field type.
    const resetSection = (fields, defaults) => {
        const out = {};
        const safeDefaults = asObject(defaults);

        for (const field of Array.isArray(fields) ? fields : []) {
            if (!field || !field.name) continue;

            if (hasDefault(field, safeDefaults)) {
                out[field.name] = defaultValueForField(field, safeDefaults);
                continue;
            }

            out[field.name] = emptyValueForField(field);
        }

        return out;
    };

    const resetDesignerSections = (schema) => ({
        config: resetSection(schema.config_fields, schema.defaults_config),
        params: resetSection(schema.params_fields, schema.defaults_params),
        selectedConnector: "",
        selectedConnectors: [],
        connectorText: "",
        runPrompt: "",
        createdJob: null,
        lastRun: null,
        lastDraftCapturedAt: "",
    });
""")

JS_ACTIONS = {
    "buildDraftCapture": js_handler("""
        (ctx) => {
            const s = ctx.state || {};

            const asArray = (value) => Array.isArray(value) ? value : [];
            const asObject = (value) => {
                return value && typeof value === "object" && !Array.isArray(value)
                    ? value
                    : {};
            };

            return {
                intent: s.intent || "",
                selectedJobType: s.selectedJobType || "",
                selectedConnector: s.selectedConnector || "",
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
        }
    """),

    "addSelectedConnector": js_handler("""
        (ctx) => {
            const s = ctx.state || {};
            const selected = s.selectedConnector || "";

            if (!selected) {
                return {};
            }

            const current = Array.isArray(s.selectedConnectors)
                ? s.selectedConnectors
                : [];

            if (current.includes(selected)) {
                return {
                    selectedConnector: "",
                };
            }

            return {
                selectedConnectors: [...current, selected],
                selectedConnector: "",
            };
        }
    """),

    "resetDesignerForm": js_handler(f"""
        (ctx) => {{
            const s = ctx.state || {{}};
            const schema = s.formSchema || {{}};

{indent(JS_DESIGNER_RESET_HELPERS, "            ")}

            return {{
                ...resetDesignerSections(schema),
                jobName: "",
                tagsText: "",
            }};
        }}
    """),

    "applySchemaChange": js_handler(f"""
        (ctx) => {{
            const s = ctx.state || {{}};
            const args = ctx.arguments || {{}};
            const schema = args.schema || {{}};

{indent(JS_DESIGNER_RESET_HELPERS, "            ")}

            return {{
                selectedJobType: schema.type || s.selectedJobType || "",
                formSchema: schema,
                availableConnectors: asArray(schema.connector_items),
                ...resetDesignerSections(schema),
            }};
        }}
    """),

    "applySelectedAiSuggestions": js_handler("""
        (ctx) => {
            const s = ctx.state || {};
            const changes = Array.isArray(s.pendingAiSuggestions)
                ? s.pendingAiSuggestions
                : [];
    
            const asObject = (value) =>
                value && typeof value === "object" && !Array.isArray(value)
                    ? value
                    : {};
    
            const output = {};
    
            const mergeSection = (section, updates) => {
                output[section] = {
                    ...asObject(output[section] !== undefined ? output[section] : s[section]),
                    ...asObject(updates),
                };
            };
    
            for (const change of changes) {
                if (!change || !change.selected) continue;
    
                const updates = asObject(change.updates);
    
                for (const [key, value] of Object.entries(updates)) {
                    if (key === "config" || key === "params") {
                        mergeSection(key, value);
                    } else {
                        output[key] = value;
                    }
                }
            }
    
            return {
                ...output,
                suggestionsPending: false,
                pendingAiSuggestions: [],
                loading: false,
            };
        }
    """),
}


# ── Backend HTTP helpers ─────────────────────────────────────────────────────


def _headers() -> dict[str, str]:
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    if _API_TOKEN:
        h["Authorization"] = f"Bearer {_API_TOKEN}"
    return h


def _api_get(path: str, params: dict | None = None) -> Any:
    with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
        resp = client.get(f"{_API_BASE}{path}", headers=_headers(), params=params)
        resp.raise_for_status()
        return resp.json()


def _api_post(path: str, body: dict) -> Any:
    with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
        resp = client.post(f"{_API_BASE}{path}", headers=_headers(), content=json.dumps(body))
        resp.raise_for_status()
        return resp.json()


# ── Draft <-> UI State Helpers ───────────────────────────────────────────────
# Key Style: UI state is camelCase; draft snapshots are snake_case.
# Key Source of Truth: The live Prefab UI state is authoritative for create_job().
# Key Boundary: The AI cannot read iframe state directly; it only sees exported draft snapshots.
# Key Flow: AI patches the latest draft snapshot, then the user syncs it back into the UI.

# Scalar field registry. Single source of truth for the field name, draft key,
# diff label, and patch-alias set. Used by:
#   _ui_state_to_draft, _draft_to_ui_state, _get_diff_items,
#   _apply_designer_patch (scalar branch), _sync_ui_result_to_form_actions.
# Containers (config / params / connectors / formSchema) stay explicit because
# each has bespoke patch semantics (replace_X, schema reload, list filtering).
_SCALAR_FIELDS: tuple[tuple[str, str, str, tuple[str, ...], str], ...] = (
    # ui_key, draft_key, label, patch_aliases, default
    ("intent",           "intent",            "Intent",             ("intent",),                                                   ""),
    ("selectedJobType",  "selected_job_type", "Job type",           ("selectedJobType", "selected_job_type", "job_type", "type"), ""),
    ("environment",      "environment",       "Environment",        ("environment",),                                              "dev"),
    ("dataSensitivity",  "data_sensitivity",  "Data sensitivity",   ("dataSensitivity", "data_sensitivity"),                       "low"),
    ("jobName",          "job_name",          "Job name",           ("jobName", "job_name", "name"),                               ""),
    ("tagsText",         "tags_text",         "Tags",               ("tagsText", "tags_text", "tags"),                             ""),
    ("selectedConnector","selected_connector","Selected connector", ("selectedConnector", "selected_connector"),                   ""),
    ("connectorText",    "manual_connector",  "Manual connector",   ("connectorText", "connector_text", "manual_connector"),      ""),
    ("runPrompt",        "run_prompt",        "Run prompt",         ("runPrompt", "run_prompt", "prompt"),                         ""),
)


# ── Pydantic schema for AI structured output ────────────────────────────────
#
# This is the type a backend caller can pass to an LLM as `response_model=`
# (Instructor / Anthropic / OpenAI structured-output / FastMCP `ctx.sample(...,
# result_type=JobDraft)`). Get a JobDraft back, dump it with .model_dump(),
# and feed it straight into `patch_draft_snapshot` — the draft_key names line
# up with what _apply_designer_patch accepts.
#
# Container fields (config/params/selected_connectors) stay loose dicts/lists
# because their shapes are JobTypeContract-dependent. Add a per-contract
# Pydantic sub-model later if you want validated structured output for those.


class JobDraft(BaseModel):
    """Mirror of the AI-visible draft shape. Single source of truth for LLM
    structured output that targets `patch_draft_snapshot`.
    """

    intent: str = PydanticField(
        default="",
        description="Plain-English statement of what this job should accomplish. "
                    "Drives downstream auto-fill: pick JobType, connectors, config.",
    )
    selected_job_type: str = ""
    environment: str = "dev"
    data_sensitivity: str = "low"
    job_name: str = ""
    tags_text: str = ""
    selected_connector: str = ""
    selected_connectors: list[str] = PydanticField(default_factory=list)
    manual_connector: str = ""
    run_prompt: str = ""
    config: dict[str, Any] = PydanticField(default_factory=dict)
    params: dict[str, Any] = PydanticField(default_factory=dict)


def _ui_state_to_draft(state: dict[str, Any] | None) -> dict[str, Any]:
    """Convert Prefab/UI state shape into the AI-visible draft snapshot shape."""
    state = state or {}

    form_schema = _patch_dict(state.get("formSchema")) or _form_schema_payload({})

    draft: dict[str, Any] = {
        draft_key: str(state.get(ui_key) or default)
        for ui_key, draft_key, _, _, default in _SCALAR_FIELDS
    }
    # Job type has a form-schema fallback when the UI doesn't carry it.
    draft["selected_job_type"] = _normalize_job_type(state.get("selectedJobType")) or str(
        form_schema.get("type") or ""
    )
    draft.update({
        "selected_connectors": _patch_list(state.get("selectedConnectors")) or [],
        "available_connectors": _patch_list(state.get("availableConnectors")) or [],
        "config": _patch_dict(state.get("config")) or {},
        "params": _patch_dict(state.get("params")) or {},
        "form_schema": form_schema,
    })
    return draft


def _draft_to_ui_state(draft: dict[str, Any] | None) -> dict[str, Any]:
    """Convert AI-visible draft snapshot shape back into Prefab/UI state shape."""
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
        "formSchema": draft.get("form_schema", _form_schema_payload({})),
    })
    return state


def _capture_draft_snapshot(current_state: dict[str, Any] | None) -> dict[str, Any]:
    """Capture Prefab/UI state as the latest AI-visible draft snapshot.

    The stored draft holds FULL values (including secrets). Redaction is
    applied at MCP tool return time so the iframe sync path keeps real
    values while AI/print surfaces see masks. See `_redact_snapshot`.
    """
    draft = _ui_state_to_draft(current_state)
    return {
        "status": "captured",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "draft": draft,
        "draft_json": json.dumps(draft, indent=2, sort_keys=True),
    }


# ── Secret redaction for AI-visible / printed snapshots ──────────────────────

SECRET_MARKER = "•••"


def _secret_field_names(fields: Any) -> set[str]:
    """Field names flagged sensitive / write-only / format=secret in a FieldSpec list."""
    if not isinstance(fields, list):
        return set()
    return {
        f["name"]
        for f in fields
        if isinstance(f, dict)
        and f.get("name")
        and (f.get("sensitive") or f.get("write_only") or f.get("format") == "secret")
    }


def _mask_secrets(values: Any, secret_names: set[str]) -> dict[str, Any]:
    """Return a copy of `values` with secret entries replaced by SECRET_MARKER."""
    if not isinstance(values, dict):
        return {}
    return {
        k: (SECRET_MARKER if k in secret_names and v not in ("", None) else v)
        for k, v in values.items()
    }


def _redact_draft(draft: dict[str, Any] | None) -> dict[str, Any]:
    """Return a copy of `draft` with secret config/params values masked."""
    if not isinstance(draft, dict):
        return {}
    schema = draft.get("form_schema") or {}
    return {
        **draft,
        "config": _mask_secrets(draft.get("config"), _secret_field_names(schema.get("config_fields"))),
        "params": _mask_secrets(draft.get("params"), _secret_field_names(schema.get("params_fields"))),
    }


def _redact_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Return a snapshot with both `draft` and `draft_json` redacted.

    The server-side store keeps the full snapshot; this function builds the
    safe-for-AI view at tool return time.
    """
    if not isinstance(snapshot, dict):
        return {}
    redacted = _redact_draft(snapshot.get("draft", {}))
    return {
        **snapshot,
        "draft": redacted,
        "draft_json": json.dumps(redacted, indent=2, sort_keys=True),
    }


def _sync_ui_result_to_form_actions() -> list[Any]:
    """Prefab actions for syncing a UI-shaped tool result into the live form."""
    return [
        *[SetState(ui_key, getattr(RESULT, ui_key)) for ui_key, *_ in _SCALAR_FIELDS],
        SetState("selectedConnectors", RESULT.selectedConnectors),
        SetState("availableConnectors", RESULT.availableConnectors),
        SetState("config", RESULT.config),
        SetState("params", RESULT.params),
        SetState("formSchema", RESULT.formSchema),
        SetState("loading", False),
        ShowToast(RESULT.message, variant="success"),
    ]


# ── Styling ──────────────────────────────────────────────────────────────────

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

_ENVIRONMENT_OPTIONS: list[tuple[str, str]] = [
    ("dev", "Development"),
    ("semi-prod", "Semi-Prod"),
    ("prod", "Production"),
]

_SENSITIVITY_OPTIONS: list[tuple[str, str]] = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
]

MAX_CONNECTOR_OPTIONS = 24
MAX_ENUM_OPTIONS = 12


# ── Dynamic form rendering ───────────────────────────────────────────────────

def _render_enum_select(state_root: str, field: Any, option_count: int) -> None:
    enum_text = str(field.enum).strip()
    enum_path = enum_text[2:-2].strip() if enum_text.startswith("{{") and enum_text.endswith("}}") else enum_text
    with Select(name=f"{state_root}.{field.name}"):
        for i in range(option_count):
            option = f"{{{{ {enum_path}.{i} }}}}"
            SelectOption(option, value=option)


def _render_length_unrolled(length_expr: Any, max_n: int, build_with_count) -> None:
    """Unroll a Prefab `len(list) == N` ladder so a parent component can render
    its N children directly. Prefab Select/Combobox do not materialize options
    nested under ForEach when the list is loop-scoped, so callers have to
    enumerate N option counts statically and pick one at render time via
    If/Elif against the runtime list length.

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


def _render_connector_combobox(option_count: int) -> None:
    """Render one Combobox with direct ComboboxOption children only."""
    with Combobox(name="selectedConnector", placeholder="Add a connector..."):
        for i in range(option_count):
            ComboboxOption(
                label=f"{{{{ availableConnectors.{i}.label }}}}",
                value=f"{{{{ availableConnectors.{i}.value }}}}",
            )


def _render_connectors_combobox() -> None:
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


def _select_field(label: str, name: str, options: list[tuple[str, str]], *, selected_value: str = "") -> None:
    with Field():
        FieldTitle(label)
        with FieldContent():
            with Select(name=name, value=selected_value or None):
                for value, opt_label in options:
                    SelectOption(opt_label, value=value, selected=value == selected_value)


# ── Action factories ─────────────────────────────────────────────────────────

def _refresh_job_types_action(*, set_loading: bool = True) -> CallTool:
    on_success: list[Any] = [
        SetState("availableJobTypes", RESULT.items),
        SetState("apiJobTypes", RESULT.dynamic_items),
    ]
    if set_loading:
        on_success.append(SetState("loading", False))
    on_error: list[Any] = [ShowToast(ERROR, variant="error")]
    if set_loading:
        on_error.insert(0, SetState("loading", False))
    return CallTool(
        "list_job_types",
        on_success=on_success,
        on_error=on_error,
    )


def _refresh_connectors_action(
    *,
    job_type_expr: Any | None = None,
    environment_expr: Any | None = None,
    set_loading: bool = True,
) -> CallTool:
    on_success: list[Any] = [SetState("availableConnectors", RESULT.items)]
    if set_loading:
        on_success.append(SetState("loading", False))
    on_error: list[Any] = [ShowToast(ERROR, variant="error")]
    if set_loading:
        on_error.append(SetState("loading", False))
    return CallTool(
        "list_connectors",
        arguments={
            "job_type": job_type_expr if job_type_expr is not None else STATE.selectedJobType,
            "environment": environment_expr if environment_expr is not None else STATE.environment,
        },
        on_success=on_success,
        on_error=on_error,
    )


def _load_schema_action(job_type_expr: Any) -> CallTool:
    return CallTool(
        "get_form_schema",
        arguments={"job_type": job_type_expr},
        on_success=[
            CallHandler(
                "applySchemaChange",
                arguments={"schema": RESULT},
                on_error=[
                    SetState("loading", False),
                    ShowToast(ERROR, variant="error"),
                ],
            ),
            SetState("loading", False),
        ],
        on_error=[SetState("loading", False), ShowToast(ERROR, variant="error")],
    )


def _create_job_action(*, environment_expr: Any | None = None) -> CallTool:
    return CallTool(
        "create_job",
        arguments={
            "name": STATE.jobName,
            "type": STATE.selectedJobType,
            "connector": "{{ selectedConnectors.0 || selectedConnector || connectorText }}",
            "environment": environment_expr if environment_expr is not None else STATE.environment,
            "config": STATE.config,
            "data_sensitivity": STATE.dataSensitivity,
            "tags_text": STATE.tagsText,
        },
        on_success=[
            SetState("createdJob", RESULT),
            SetState("loading", False),
            ShowToast("Job registered.", variant="success"),
            RequestDisplayMode("fullscreen"),
        ],
        on_error=[SetState("loading", False), ShowToast(ERROR, variant="error")],
    )


def _trigger_run_action(*, environment_expr: Any | None = None) -> CallTool:
    return CallTool(
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
            SetState("loading", False),
            ShowToast("Run queued.", variant="success"),
        ],
        on_error=[SetState("loading", False), ShowToast(ERROR, variant="error")],
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


def _capture_then(*extra: Any) -> list[Any]:
    """Build a capture-current-draft action that always updates AI context, then chains `extra`.

    Used by both 'Update AI context' (no extra) and 'Get AI feedback' (adds a SendMessage).
    """
    return [
        _capture_current_draft_action(
            on_success=[
                SetState("lastDraftCapturedAt", RESULT.captured_at),
                UpdateContext(structured_content={"control_center_job_designer": RESULT.draft}),
                *extra,
            ],
        ),
    ]


def _update_ai_context_action() -> list[Any]:
    return _capture_then(ShowToast("AI context updated.", variant="success"))


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


def _review_setup_action() -> list[Any]:
    return _capture_then(
        SendMessage(
            "Please review the current Control Center job setup. Check connectors, "
            "required config, and missing fields before I create it.\n\n"
            "If you recommend concrete edits, call `patch_draft_snapshot` with only "
            "the fields that should change. Do not send the full current state. "
            "Current draft JSON:\n```json\n{{ $result.draft_json }}\n```"
        ),
    )


# ── AI Draft Preview / Diff Helpers ──────────────────────────────────────────

_MISSING = object()


def _display_value(value: Any, *, limit: int | None = 180) -> str:

    if value is _MISSING or value is None or value == "":
        return "—"

    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value)

    if limit is None:
        return text  # Return the whole text if limit is explicitly None

    return text[:limit] + ("…" if len(text) > limit else "")  # Add ellipsis if truncated


def _get_diff_items(current: dict, proposed: dict):
    """Yield (item_id, label, ui_key, field_key, before, after) for visible draft fields.

    Scalars come from `_SCALAR_FIELDS`; `selected_connectors` is the only list
    we surface in the diff. `available_connectors` is intentionally excluded —
    it's UI plumbing, not user intent.
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
        before_section = _patch_dict(current.get(section)) or {}
        after_section = _patch_dict(proposed.get(section)) or {}

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

        # Determine the status of the change
        is_addition = before in (_MISSING, None, "", [], {})
        is_deletion = after in (_MISSING, None, "", [], {})
        before_css = "text-muted-foreground opacity-40" if is_addition else "text-red-400/80 line-through decoration-red-500/50"
        after_css = "text-muted-foreground opacity-40" if is_deletion else "text-emerald-400 font-medium"

        before_text = _display_value(before)
        after_text = _display_value(after)
        is_long = len(before_text) > 35 or len(after_text) > 35

        changes.append(
            {
                "id": item_id,
                "label": label,
                "before": before_text,
                "after": after_text,
                "before_css": before_css,
                "after_css": after_css,
                "is_long": is_long,
                "selected": True,
                "updates": updates,
            }
        )

    return changes


def _is_template_expr(value: Any) -> bool:
    return isinstance(value, str) and bool(_TEMPLATE_EXPR_RE.match(value.strip()))


def _decode_jsonish_string(value: str) -> Any:
    text = value.strip()

    if not text:
        return ""

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _filter_template_items(items: Iterable[Any]) -> tuple[list[Any], bool]:
    result: list[Any] = []
    removed_any = False

    for item in items:
        if _is_template_expr(item):
            removed_any = True
            continue

        result.append(item)

    return result, removed_any


def _patch_value(patch: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in patch:
            return patch[key]
    return None


def _patch_list(value: Any) -> list[Any] | None:
    """Normalize patch/UI values into a list.

    Returns None when the value is unusable/unresolved, so callers can preserve
    an existing value instead of accidentally overwriting with bad data.
    """
    if value is None or _is_template_expr(value):
        return None

    if isinstance(value, list):
        result, removed_any = _filter_template_items(value)
        return None if removed_any and not result else result

    if isinstance(value, (tuple, set)):
        result, removed_any = _filter_template_items(value)
        return None if removed_any and not result else result

    if isinstance(value, str):

        decoded = _decode_jsonish_string(value)
        if decoded == "":
            return []
        if _is_template_expr(decoded):
            return None
        if isinstance(decoded, list):
            result, removed_any = _filter_template_items(decoded)
            return None if removed_any and not result else result
        if isinstance(decoded, (tuple, set)):
            result, removed_any = _filter_template_items(decoded)
            return None if removed_any and not result else result
        if isinstance(decoded, str):
            return [part.strip() for part in decoded.split(",") if part.strip()]

        return [decoded]

    return [value]


def _patch_dict(value: Any) -> dict[str, Any] | None:
    """Normalize patch/UI values into a dict.

    Returns None when the value is unusable/unresolved, so callers can preserve
    an existing value instead of accidentally overwriting with bad data.
    """
    if value is None or _is_template_expr(value):
        return None

    if isinstance(value, str):

        decoded = _decode_jsonish_string(value)
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


def _apply_designer_patch(
    current_state: dict[str, Any] | None,
    patch: dict[str, Any] | None,
) -> dict[str, Any]:
    """Apply a partial patch to UI-shaped designer state.

    Contract:
    - current_state is Prefab/UI-shaped state.
    - patch may use either UI-style or AI/draft-style aliases.
    - omitted fields are preserved.
    - config and params merge into existing objects.
    - replace_config and replace_params replace the whole object.
    - return value is UI-shaped so Prefab can SetState directly.
    """
    if current_state is not None and not isinstance(current_state, dict):
        raise ValueError("current_state must be an object.")
    if patch is not None and not isinstance(patch, dict):
        raise ValueError("patch must be an object.")

    current_state = current_state or {}
    patch = patch or {}

    applied: list[str] = []

    # Normalize current state through the draft adapter first so all values have parsed dict/list defaults.
    state = _draft_to_ui_state(_ui_state_to_draft(current_state))

    # All scalar state lives in this dict, keyed by UI key, derived from _SCALAR_FIELDS.
    scalars: dict[str, Any] = {ui_key: state[ui_key] for ui_key, *_ in _SCALAR_FIELDS}
    selected_connectors = state["selectedConnectors"]
    available_connectors = state["availableConnectors"]
    config = state["config"]
    params = state["params"]
    form_schema = state["formSchema"]

    schema_replaced = False

    # -- Job Type / Schema --
    # `selectedJobType` is special: a change reloads the schema and resets the
    # connector list, so the scalar loop below skips it.

    next_type = _patch_value(patch, "selectedJobType", "selected_job_type", "job_type", "type")
    if next_type is not None:
        normalized_next_type = _normalize_job_type(next_type)
        if normalized_next_type and normalized_next_type != scalars["selectedJobType"]:
            scalars["selectedJobType"] = normalized_next_type
            form_schema = _schema_for_job_type(normalized_next_type, allow_api_fallback=True)
            available_connectors = form_schema.get("connector_items", [])
            schema_replaced = True
            applied.extend(["selectedJobType", "formSchema", "availableConnectors"])

    next_schema = _patch_value(patch, "formSchema", "form_schema")
    if isinstance(next_schema, dict):
        form_schema = _form_schema_payload(next_schema)
        scalars["selectedJobType"] = _normalize_job_type(form_schema.get("type")) or scalars["selectedJobType"]
        available_connectors = form_schema.get("connector_items", [])
        schema_replaced = True
        applied.extend(["formSchema", "availableConnectors"])

    # -- Scalars (driven by _SCALAR_FIELDS) --

    for ui_key, _draft_key, _label, aliases, _default in _SCALAR_FIELDS:
        if ui_key == "selectedJobType":  # handled above
            continue
        value = _patch_value(patch, *aliases)
        if value is None:
            continue
        if ui_key == "tagsText":
            scalars[ui_key] = ", ".join(value) if isinstance(value, list) else str(value)
        else:
            scalars[ui_key] = str(value)
        applied.append(ui_key)

    # -- Connector Lists --

    next_selected = _patch_list(_patch_value(patch, "selectedConnectors", "selected_connectors", "connectors"))
    if next_selected is not None:
        selected_connectors = next_selected
        scalars["selectedConnector"] = ""
        applied.append("selectedConnectors")

    next_available = _patch_list(_patch_value(patch, "availableConnectors", "available_connectors"))
    if next_available is not None:
        available_connectors = next_available
        applied.append("availableConnectors")

    # -- Config / Params (replace_X wins; merge otherwise; reset on schema swap) --

    def _resolve_section(
        section: str,
        current_value: dict[str, Any],
        merge_aliases: tuple[str, ...],
        defaults_key: str,
    ) -> dict[str, Any]:
        replace = _patch_dict(_patch_value(patch, f"replace_{section}"))
        update = _patch_dict(_patch_value(patch, *merge_aliases))
        if replace is not None:
            applied.append(section)
            return replace
        if update is not None:
            # On a schema swap, start from the contract's defaults so AI-filled
            # values *override* them but absent AI keys still inherit (e.g. a
            # contract-supplied `timezone: UTC` shouldn't disappear just because
            # the AI didn't restate it). When no swap happened, keep the user's
            # current values as the merge base.
            base = form_schema.get(defaults_key, {}) if schema_replaced else current_value
            applied.append(section)
            return {**base, **update}
        if schema_replaced:
            return form_schema.get(defaults_key, {})
        return current_value

    config = _resolve_section("config", config, ("config", "config_updates"), "defaults_config")
    params = _resolve_section("params", params, ("params", "run_params", "params_updates"), "defaults_params")

    # -- FINAL UI-SHAPED RESULT --

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


def _sync_ai_draft_to_form_action() -> CallTool:
    return CallTool(
        "get_current_draft_ui_state",
        on_success=_sync_ui_result_to_form_actions(),
        on_error=[SetState("loading", False), ShowToast(ERROR, variant="error")],
    )


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
    review_setup_action = _review_setup_action()
    sync_ai_draft_action = _sync_ai_draft_to_form_action()
    preview_ai_suggested_changes_action = _preview_ai_suggested_changes_action()
    static_job_types = list(initial_state.get("availableJobTypes") or [])

    def _async_btn(label: str, *, action: object, variant: str = "secondary") -> None:
        Button(
            label,
            variant=variant,
            on_click=[SetState("loading", True), action],
        )

    with Column(gap=4) as view:
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
                                        # Wipe contract-shaped state up front so stale values from
                                        # the previous JobType can't bleed into matching field names
                                        # before applySchemaChange runs.
                                        SetState("config", {}),
                                        SetState("params", {}),
                                        SetState("selectedConnector", ""),
                                        SetState("selectedConnectors", []),
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
                                    with ForEach("apiJobTypes") as jt:
                                        SelectOption(
                                            jt.display_name.default(jt.type),
                                            value=jt.type,
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

                            # NEW FEATURE: JSON Deep Dive Accordion
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
                                                    # Use Prefab template strings with fallbacks; bare STATE.x Rx
                                                    # refs occasionally serialize as unresolved "{{ x }}" when the
                                                    # bound input never received focus (e.g. environment Select on
                                                    # first render). The existing _create_job_action uses the same
                                                    # pattern at server.py:_create_job_action.
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
                                        disabled="{{ !selectedConnector }}",
                                        on_click=CallHandler("addSelectedConnector"),
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
                                for value, opt_label in _SENSITIVITY_OPTIONS:
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

        # ── Run-time params (only meaningful after job creation) ─────────────
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
                    _async_btn("Create job", action=create_action, variant="success")
                    with If(STATE.createdJob.id):
                        _async_btn("Trigger run", action=run_action, variant="success")
                    Button(
                        "Get AI feedback",
                        icon="lightbulb",
                        variant="outline",
                        on_click=review_setup_action,
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


def _initial_state(
    *,
    job_types: list[dict] | None = None,
    selected_type: str = "",
    environment: str = "dev",
) -> dict[str, Any]:
    available_job_types = job_types or _static_job_types()
    selected_schema = _schema_for_job_type_safe(selected_type)

    resolved_selected_type = (selected_schema.get("type") or _normalize_job_type(selected_type) or "")

    if selected_schema.get("type"):
        available_job_types = _merge_job_type_summaries(available_job_types, [_job_type_summary(selected_schema)])

    return {
        "availableJobTypes": available_job_types,
        "apiJobTypes": [],
        "availableConnectors": selected_schema.get("connector_items", []),
        "selectedJobType": resolved_selected_type,
        "selectedConnector": "",
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


# ── CSP helper (mirrors the prototype) ───────────────────────────────────────

def _resource_csp_for(app: PrefabApp) -> ResourceCSP:
    csp = app.csp()
    known = {"connect_domains", "style_domains", "script_domains", "resource_domains"}
    unknown = set(csp) - known
    if unknown:
        raise RuntimeError(f"Prefab CSP added new keys: {unknown}")
    merged = sorted(
        set(
            (csp.get("style_domains") or [])
            + (csp.get("script_domains") or [])
            + (csp.get("resource_domains") or [])
        )
    ) or None
    return ResourceCSP(
        connect_domains=csp.get("connect_domains") or None,
        resource_domains=merged,
    )


def _resolve_prefab_tool(tool_ref: Any) -> ResolvedTool:
    """Tell Prefab to expose FastMCP structuredContent as `$result`."""
    name = tool_ref if isinstance(tool_ref, str) else getattr(tool_ref, "__name__", str(tool_ref))
    return ResolvedTool(name=name, unwrap_result=True)


# ── Form-schema serialization for the UI ─────────────────────────────────────

def _form_schema_payload(contract_schema: dict) -> dict:
    """Normalize a form-schema or full JobTypeContract response for the UI."""

    def _field_list(schema: dict, section: str) -> list[dict]:
        direct = schema.get(f"{section}_fields")
        if direct:
            return _mark_required_fields(direct, schema.get(f"required_{section}", []) or [])

        input_schema = schema.get(section) or {}
        fields = input_schema.get("fields", {})
        if isinstance(fields, dict):
            values = list(fields.values())
        else:
            values = list(fields or [])
        return _mark_required_fields(values, input_schema.get("required", []) or [])

    def _required(schema: dict, section: str) -> list[str]:
        direct = schema.get(f"required_{section}")
        if direct is not None:
            return list(direct or [])
        return list((schema.get(section) or {}).get("required", []) or [])

    def _optional(schema: dict, section: str) -> list[str]:
        direct = schema.get(f"optional_{section}")
        if direct is not None:
            return list(direct or [])
        return list((schema.get(section) or {}).get("optional", []) or [])

    config_fields = _field_list(contract_schema, "config")
    params_fields = _field_list(contract_schema, "params")
    connector_types = _extract_connector_types(contract_schema)

    def _defaults(fields: list[dict]) -> dict:
        out: dict[str, Any] = {}
        for f in fields:
            if f.get("default") is not None:
                out[f["name"]] = f["default"]
            elif f.get("type") == "boolean":
                out[f["name"]] = False
        return out

    return {
        "type": contract_schema.get("type", ""),
        "display_name": contract_schema.get("display_name") or contract_schema.get("type", ""),
        "description": contract_schema.get("description"),
        "config_fields": config_fields,
        "params_fields": params_fields,
        "required_config": _required(contract_schema, "config"),
        "optional_config": _optional(contract_schema, "config"),
        "required_params": _required(contract_schema, "params"),
        "optional_params": _optional(contract_schema, "params"),
        "connector_types": connector_types,
        "connector_items": _connector_items_for_types(connector_types),
        "defaults_config": _defaults(config_fields),
        "defaults_params": _defaults(params_fields),
    }


def _mark_required_fields(fields: list[dict], required: list[str]) -> list[dict]:
    required_names = set(required)
    normalized: list[dict] = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        name = field.get("name")
        normalized.append({**field, "required": bool(name and name in required_names)})
    return normalized


# ── Tag/JSON normalization helpers for create_job ────────────────────────────

def _coerce_field_values(fields: list[dict], data: dict) -> dict:
    """Best-effort cast textarea/json values into structured types."""
    by_name = {f["name"]: f for f in fields}
    out: dict[str, Any] = {}
    for key, value in data.items():
        spec = by_name.get(key)
        if spec is None:
            out[key] = value
            continue
        ftype = spec.get("type")
        if value in ("", None):
            continue
        try:
            if ftype == "integer" and not isinstance(value, int):
                out[key] = int(value)
            elif ftype == "number" and not isinstance(value, (int, float)):
                out[key] = float(value)
            elif ftype == "boolean" and not isinstance(value, bool):
                out[key] = str(value).strip().lower() in {"true", "1", "yes", "on"}
            elif ftype in ("array", "object") and isinstance(value, str):
                out[key] = json.loads(value)
            else:
                out[key] = value
        except (ValueError, json.JSONDecodeError):
            out[key] = value
    return out


def _normalize_job_type(value: Any) -> str:
    """Normalize tool/renderer job type inputs into known contract keys.

    FastMCP dev and Prefab may pass tool args through JSON/text boundaries, so
    tolerate quoted JSON strings. If a renderer sends an unresolved template
    expression like "{{ selectedJobType }}", return "" so callers do not hit the
    dynamic API fallback with template text.
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    text = value.strip()
    if not text or _TEMPLATE_EXPR_RE.match(text):
        return ""
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        decoded = text
    if isinstance(decoded, str):
        text = decoded.strip()
    while len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1:-1].strip()
    if not text or _TEMPLATE_EXPR_RE.match(text):
        return ""
    return text.lower()


def _schema_for_job_type(job_type: str, *, allow_api_fallback: bool = False) -> dict[str, Any]:
    """Resolve a form schema for the given job type.

    Tries `KNOWN_CONTRACTS` first; if not found and `allow_api_fallback` is
    True, fetches `/job-types/{type}/form-schema` and merges connector_types
    metadata via `_job_type_metadata_for`. Returns an empty schema payload
    when the type is unknown and no fallback is allowed.

    Callers that want the empty schema on *any* failure (e.g. preload during
    iframe boot) should pass `safe=True` to swallow API errors.
    """
    normalized = _normalize_job_type(job_type)
    if not normalized:
        return _form_schema_payload({})

    contract = KNOWN_CONTRACTS.get(normalized)
    if contract is not None:
        return _form_schema_payload(contract.model_dump(mode="json"))

    if not allow_api_fallback:
        return _form_schema_payload({})

    try:
        raw = _api_get(f"/job-types/{normalized}/form-schema")
        return _form_schema_payload({**raw, **_job_type_metadata_for(raw)})
    except Exception as exc:
        logger.warning("Failed to fetch dynamic form schema for %s: %s", normalized, exc)
        raise


def _schema_for_job_type_safe(job_type: str) -> dict[str, Any]:
    """Like `_schema_for_job_type(..., allow_api_fallback=True)` but never raises."""
    try:
        return _schema_for_job_type(job_type, allow_api_fallback=True)
    except Exception:
        return _form_schema_payload({})


def _static_job_types() -> list[dict[str, Any]]:
    return [_job_type_summary(contract.model_dump(mode="json")) for contract in KNOWN_CONTRACTS.values()]


def _merge_job_type_summaries(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for group in groups:
        for item in group:
            if not isinstance(item, dict):
                continue
            job_type = item.get("type")
            if job_type and job_type not in merged:
                merged[job_type] = item
    return list(merged.values())


def _job_type_items(response: Any) -> list[dict[str, Any]]:
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


# ── Server build ─────────────────────────────────────────────────────────────

class _HideInternalToolsMiddleware(Middleware):
    """Hide tools tagged `internal` from tools/list while keeping them callable.

    Prefab's `AppConfig(visibility=["app"])` does the right thing for listing
    but FastMCP 3.2.4 also blocks `tools/call` for those tools, which breaks
    the iframe's AppBridge. Using a tag + middleware preserves the
    "hidden but callable" semantics the Prefab docs describe.
    """

    async def on_list_tools(self, ctx, call_next):
        tools = await call_next(ctx)
        return [t for t in tools if "internal" not in (t.tags or set())]


def build_server() -> FastMCP:
    mcp = FastMCP(SERVER_NAME, instructions=SERVER_DESCRIPTION)

    mcp.add_middleware(_HideInternalToolsMiddleware())
    mcp.add_provider(
        Approval(
            title="Apply AI Changes?",
            approve_text="Approve",
            reject_text="Cancel",
            approve_variant="success",
        )
    )

    bootstrap_types = _static_job_types()
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
    current_initial_state = _initial_state(job_types=bootstrap_types)
    latest_draft_snapshot: dict[str, Any] = _capture_draft_snapshot(current_initial_state)
    blank_app = _build_app(current_initial_state)

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
        return _build_app(current_initial_state).html(tool_resolver=_resolve_prefab_tool)

    @mcp.tool(
        name="open_job_designer",
        description="Open the interactive Control Center job designer.",
        app=AppConfig(resource_uri=APP_RESOURCE_URI, prefers_border=True),
    )
    def open_job_designer(
        job_type: str = "",
        environment: str = "dev",
        
    ) -> dict[str, Any]:
        # Single-session draft store (see breadcrumb at top of build_server).
        # For multi-tenant: swap to ctx.set_state or a session_state_store.
        nonlocal latest_draft_snapshot, current_initial_state

        normalized_job_type = _normalize_job_type(job_type)
        normalized_environment = environment.strip().lower() if environment else "dev"
        current_initial_state = _initial_state(
            job_types=bootstrap_types,
            selected_type=normalized_job_type,
            environment=normalized_environment,
        )
        latest_draft_snapshot = _capture_draft_snapshot(current_initial_state)
        return {
            "status": "opened",
            "selectedJobType": current_initial_state["selectedJobType"],
            "environment": current_initial_state["environment"],
        }

    @mcp.tool(
        name="list_job_types",
        description="List all known JobTypeContracts available to this Control Center deployment.",
    )
    def list_job_types() -> dict[str, Any]:
        try:
            items = [_job_type_summary(c) for c in _job_type_items(_api_get("/job-types"))]
        except Exception as exc:
            logger.warning("list_job_types failed: %s", exc)
            items = []
        static_keys = set(KNOWN_CONTRACTS)
        return {
            "items": _merge_job_type_summaries(_static_job_types(), items),
            "dynamic_items": [
                item for item in items
                if isinstance(item, dict)
                and item.get("type")
                and str(item["type"]).strip().lower() not in static_keys
            ],
        }

    @mcp.tool(
        name="get_form_schema",
        description="Fetch the form schema for a job type (config/params fields, required lists, connector types).",
    )
    def get_form_schema(job_type: str) -> dict[str, Any]:
        normalized = _normalize_job_type(job_type)
        if not normalized:
            return _form_schema_payload({})
        return _schema_for_job_type(normalized, allow_api_fallback=True)

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
        normalized_job_type = _normalize_job_type(job_type)
        allowed_connector_types = _connector_types_for_job_type_or_values(
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
            response = _api_get("/connectors", params=params or None)
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
        items = _merge_connector_items(items, allowed_connector_types, environment)
        return {
            "items": [
                {
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "connector_type": c.get("connector_type"),
                    "environment": c.get("environment"),
                    "status": c.get("status"),
                    "is_shared": c.get("is_shared", False),
                    "label": " · ".join(
                        str(p) for p in (c.get("name") or c.get("id"), c.get("connector_type"), c.get("environment")) if p
                    ),
                    "value": _connector_value(c),
                }
                for c in items
            ]
        }

    @mcp.tool(
        name="capture_current_draft",
        description="Capture iframe form state as the latest draft snapshot.",
        tags={"internal"},
    )
    def capture_current_draft(current_state: dict[str, Any]) -> dict[str, Any]:
        # Single-session draft store (see breadcrumb at top of build_server).
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
        annotations={},
    )
    def patch_draft_snapshot(
        patch: dict[str, Any],
        summary: str = "",
    ) -> dict[str, Any]:
        # Single-session draft store (see breadcrumb at top of build_server).
        nonlocal latest_draft_snapshot

        if not isinstance(patch, dict):
            raise ValueError("patch must be an object.")

        # Drop redaction markers the model may echo back so we don't overwrite
        # real secrets with `•••`.
        for section_key in ("config", "params", "replace_config", "replace_params"):
            section = patch.get(section_key)
            if isinstance(section, dict):
                patch[section_key] = {k: v for k, v in section.items() if v != SECRET_MARKER}

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
        tags={"internal"},
    )
    async def generate_full_job_draft(
        intent: str,
        job_name: str = "",
        environment: str = "dev",
    ) -> dict[str, Any]:
        # Single-session draft store (see breadcrumb at top of build_server).
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
            "note": (
                "Generated a full AI draft. Click Apply AI draft to review the proposed "
                "changes, or Sync AI draft to form to apply them directly."
            ),
        }

    @mcp.tool(
        name="get_current_draft_ui_state",
        description="Return the latest draft as Prefab UI state for iframe sync.",
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
        name="preview_ai_suggested_changes",
        description="Diff iframe form state against the latest AI draft.",
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
        normalized_type = _normalize_job_type(type)
        if not normalized_type:
            raise ValueError("Job type is required — pick one from the job-type selector.")
        if not connector or not connector.strip():
            raise ValueError("Connector is required.")
        normalized_environment = environment.strip().lower() if environment else "dev"
        if not normalized_environment:
            raise ValueError("Environment is required — pick one from the environment selector.")

        merged_tags = list(tags or []) + [t.strip() for t in (tags_text or "").split(",") if t.strip()]

        try:
            schema = _schema_for_job_type(normalized_type, allow_api_fallback=True)
            config = _coerce_field_values(schema["config_fields"], config or {})
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
        return _api_post("/jobs", body)

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
            job = _api_get(f"/jobs/{job_id}")
            schema = _schema_for_job_type(job["type"], allow_api_fallback=True)
            params = _coerce_field_values(schema["params_fields"], params or {})
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
        return _api_post(f"/jobs/{job_id}/runs", body)

    return mcp


def _normalize_connector_type_list(value: Any) -> list[str]:
    """Normalize connector type inputs from contracts, API payloads, or Prefab args."""
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text or _TEMPLATE_EXPR_RE.match(text):
            return []
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            decoded = text
        if isinstance(decoded, list):
            value = decoded
        elif isinstance(decoded, str):
            value = [part.strip() for part in decoded.split(",")]
        else:
            value = [decoded]
    elif not isinstance(value, list):
        value = list(value) if isinstance(value, (tuple, set)) else [value]

    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        if item is None:
            continue
        name = str(item).strip()
        if not name or _TEMPLATE_EXPR_RE.match(name) or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def _connector_types_for_job_type_or_values(
    *,
    job_type: str = "",
    connector_types: Any = None,
    connector_type: str = "",
) -> list[str]:
    """Resolve allowed connector types from the job contract first.

    Prefab action arguments can serialize arrays as reactive template strings,
    so UI actions pass job_type and let the server derive connector names from
    KNOWN_CONTRACTS. Explicit connector_types remains for direct MCP callers.
    """
    normalized_job_type = _normalize_job_type(job_type)
    if normalized_job_type:
        schema = _schema_for_job_type(normalized_job_type, allow_api_fallback=True)
        resolved = _extract_connector_types(schema)
        if resolved:
            return resolved
    if connector_types is not None:
        return _normalize_connector_type_list(connector_types)
    return _normalize_connector_type_list(connector_type)


def _connector_value(connector: dict[str, Any]) -> str:
    """Return the value to persist as Job.connector.

    Execution resolves Job.connector as an MCP server name, so registered
    connector row ids such as "conn-..." are UI metadata, not valid job values.
    Prefer a contract/server name carried on the item, then fall back to common
    connector row fields.
    """
    for key in ("value", "server_name", "connector_type", "name", "id"):
        value = connector.get(key)
        if value:
            return str(value)
    return ""


def _connector_items_for_types(
    connector_types: list[str],
    environment: str = "",
) -> list[dict[str, Any]]:
    """Build UI-ready connector options from contract-declared connector names."""
    return [
        {
            "label": _connector_value(c),
            "value": _connector_value(c),
        }
        for c in _merge_connector_items([], connector_types, environment)
    ]


def _merge_connector_items(
    items: list[dict[str, Any]],
    allowed_connector_names: list[str],
    environment: str,
) -> list[dict[str, Any]]:
    """Merge registered connector rows with contract-declared MCP server names.

    `/connectors` stores user-registered connection records with coarse
    connector_type values. Job contracts, especially `mcp`, declare approved MCP
    server names. When no row exists for a server name, synthesize an option
    whose id is the server name so job creation can still send the correct
    connector value.
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
        merged.append(
            {
                "id": name,
                "name": name,
                "connector_type": name,
                "value": name,
                "environment": environment or None,
                "status": "available",
                "is_shared": True,
            }
        )

    return merged


def _extract_connector_types(contract: dict) -> list[str]:
    """Walk the new JobTypeContract.requires shape and return a flat list of names.

    JobTypeContract.requires is `list[ExecutionRequirement]` where each entry has:
        surface_type:    e.g. "mcp_server", "python_runtime", "http_api"
        names:           e.g. ["sql-mcp"], ["arxiv-research"], []
        required_tools:  list[str]
        required_scopes: list[str]

    For UI purposes "connector type" = the union of `names` across all requirements,
    deduplicated, preserving order.
    """
    requires = contract.get("requires")
    # Old shape (single ExecutionRequirement dict) — extract names directly.
    if isinstance(requires, dict):
        names = _normalize_connector_type_list(requires.get("names"))
        if names:
            return names
        return _normalize_connector_type_list(requires.get("connector_types"))
    # New shape (list of ExecutionRequirement dicts).
    out: list[str] = []
    seen: set[str] = set()
    if isinstance(requires, list):
        for req in requires:
            if not isinstance(req, dict):
                continue
            for name in _normalize_connector_type_list(req.get("names")):
                if name and name not in seen:
                    seen.add(name)
                    out.append(name)
    if out:
        return out
    # Legacy fallback for API-discovered contracts that have not adopted
    # JobTypeContract.requires yet.
    return _normalize_connector_type_list(contract.get("connector_types"))


def _job_type_summary(contract: dict) -> dict[str, Any]:
    return {
        "type": contract.get("type"),
        "display_name": contract.get("display_name") or contract.get("type"),
        "description": contract.get("description"),
        "connector_types": _extract_connector_types(contract),
    }


def _job_type_metadata_for(form_schema: dict) -> dict[str, Any]:
    connector_types = _extract_connector_types(form_schema)
    if connector_types:
        return {"connector_types": connector_types}

    job_type = form_schema.get("type")
    fallback = {
        "connector_types": connector_types,
    }
    if not job_type:
        return fallback

    try:
        contracts = _job_type_items(_api_get("/job-types"))
    except Exception:
        return fallback
    for c in contracts:
        if c.get("type") == job_type:
            summary = _job_type_summary(c)
            return {
                "connector_types": summary["connector_types"],
            }
    return fallback


mcp = build_server()


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8001)
