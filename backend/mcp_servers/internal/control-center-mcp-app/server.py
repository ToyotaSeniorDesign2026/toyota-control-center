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
from typing import Any, Literal

import httpx
from fastmcp import FastMCP
from fastmcp.apps import AppConfig, ResourceCSP
from prefab_ui import PrefabApp
from prefab_ui.app import ResolvedTool
from prefab_ui.actions import SetState, ShowToast
from prefab_ui.actions.mcp import CallTool, RequestDisplayMode
from prefab_ui.components import (
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
    Column,
    Elif,
    Else,
    Field,
    FieldContent,
    FieldDescription,
    FieldTitle,
    ForEach,
    Grid,
    H1,
    If,
    Input,
    Label,
    Loader,
    Muted,
    P,
    Page,
    RESULT,
    Row,
    STATE,
    Select,
    SelectOption,
    Small,
    Text,
    Textarea,
)
from prefab_ui.rx import ERROR, EVENT
from prefab_ui.themes import Theme

from control_center.specs import KNOWN_CONTRACTS

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
_TEMPLATE_EXPR_RE = re.compile(r"^\s*\{\{.*\}\}\s*$")


# ── Backend HTTP helpers ─────────────────────────────────────────────────────


def _headers() -> dict[str, str]:
    h = {"Content-Type": "application/json"}
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


# ── Styling ──────────────────────────────────────────────────────────────────

APP_STYLES = """
:root { color-scheme: dark; }

body {
  background:
    radial-gradient(circle at 12% 12%, rgba(54, 255, 181, 0.22), transparent 26%),
    radial-gradient(circle at 88% 10%, rgba(86, 191, 255, 0.24), transparent 24%),
    linear-gradient(180deg, #07110f 0%, #0c1717 36%, #111b1e 100%);
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

.designer-hero {
  background:
    radial-gradient(circle at top left, rgba(82, 255, 173, 0.18), transparent 28%),
    radial-gradient(circle at bottom right, rgba(93, 162, 255, 0.16), transparent 34%),
    linear-gradient(135deg, rgba(8, 18, 19, 0.96) 0%, rgba(15, 31, 30, 0.96) 52%, rgba(22, 46, 39, 0.96) 100%);
  border: 1px solid rgba(112, 244, 191, 0.18);
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.38);
}

.glass-card {
  background: linear-gradient(180deg, rgba(11, 24, 24, 0.88) 0%, rgba(14, 29, 29, 0.92) 100%);
  border: 1px solid rgba(120, 245, 194, 0.14);
  box-shadow: 0 14px 32px rgba(0, 0, 0, 0.22);
  backdrop-filter: blur(14px);
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

_KIND_OPTIONS: list[tuple[str, str]] = [
    ("runtime", "Runtime"),
    ("artifact", "Artifact"),
]


# ── Dynamic form rendering ───────────────────────────────────────────────────


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
                    with Select(name=f"{state_root}.{field.name}"):
                        with ForEach(field.enum) as opt:
                            SelectOption(opt, value=opt)
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


def _select_field(
    label: str,
    name: str,
    options: list[tuple[str, str]],
    *,
    selected_value: str = "",
) -> None:
    with Field():
        FieldTitle(label)
        with FieldContent():
            with Select(name=name, value=selected_value or None):
                for value, opt_label in options:
                    SelectOption(opt_label, value=value, selected=value == selected_value)


# ── Action factories ─────────────────────────────────────────────────────────


def _refresh_job_types_action() -> CallTool:
    return CallTool(
        "list_job_types",
        on_success=[
            SetState("availableJobTypes", RESULT.items),
            SetState("apiJobTypes", RESULT.dynamic_items),
            SetState("loading", False),
        ],
        on_error=[SetState("loading", False), ShowToast(ERROR, variant="error")],
    )


def _refresh_connectors_action() -> CallTool:
    return CallTool(
        "list_connectors",
        arguments={
            "connector_type": STATE.selectedConnectorType,
            "environment": STATE.environment,
        },
        on_success=[
            SetState("availableConnectors", RESULT.items),
            SetState("loading", False),
        ],
        on_error=[SetState("loading", False), ShowToast(ERROR, variant="error")],
    )


def _create_job_action() -> CallTool:
    return CallTool(
        "create_job",
        arguments={
            "name": STATE.jobName,
            "kind": STATE.kind,
            "type": STATE.selectedJobType,
            "connector": STATE.selectedConnector,
            "environment": STATE.environment,
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


def _trigger_run_action() -> CallTool:
    return CallTool(
        "trigger_run",
        arguments={
            "job_id": STATE.createdJob.id,
            "action": "run",
            "target_environment": STATE.environment,
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


# ── App builder ──────────────────────────────────────────────────────────────


def _build_app(initial_state: dict[str, Any]) -> PrefabApp:
    job_type_action: CallTool | None = None
    refresh_types_action = _refresh_job_types_action()
    refresh_connectors_action = _refresh_connectors_action()
    create_action = _create_job_action()
    run_action = _trigger_run_action()
    selected_job_type = initial_state.get("selectedJobType") or ""
    selected_environment = initial_state.get("environment") or "dev"
    static_job_types = list(initial_state.get("availableJobTypes") or [])

    def _async_btn(label: str, *, action: object, variant: str = "secondary") -> None:
        Button(
            label,
            variant=variant,
            on_click=[SetState("loading", True), action],
        )

    with Column(gap=5) as view:
        Page("Control Center Job Designer")

        # ── Hero ─────────────────────────────────────────────────────────────
        with Card(css_class="designer-hero"):
            with CardHeader():
                with Column(gap=2):
                    Badge("Control Center", variant="outline")
                    H1("Create a job")
                    Muted(
                        "Pick a job type and connector. Form fields adapt to the "
                        "selected contract."
                    )
            with CardContent():
                with Grid(columns={"md": 3}, gap=4):
                    with Field():
                        FieldTitle("Job type")
                        with FieldContent():
                            with Select(
                                name="selectedJobType",
                                value=selected_job_type,
                                on_change=[
                                    SetState("loading", True),
                                    CallTool(
                                        "open_job_designer",
                                        arguments={
                                            "job_type": EVENT,
                                            "environment": STATE.environment,
                                        },
                                    ),
                                ],
                            ) as job_type_select:
                                job_type_action = CallTool(
                                    "open_job_designer",
                                    arguments={
                                        "job_type": job_type_select.rx,
                                        "environment": STATE.environment,
                                    },
                                )
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
                    _select_field(
                        "Kind",
                        "kind",
                        _KIND_OPTIONS,
                        selected_value=initial_state.get("kind", ""),
                    )
                    with Field():
                        FieldTitle("Environment")
                        with FieldContent():
                            with Select(
                                name="environment",
                                value=selected_environment,
                                on_change=[
                                    SetState("loading", True),
                                    CallTool(
                                        "open_job_designer",
                                        arguments={
                                            "job_type": STATE.selectedJobType,
                                            "environment": EVENT,
                                        },
                                    ),
                                ],
                            ):
                                for value, opt_label in _ENVIRONMENT_OPTIONS:
                                    SelectOption(
                                        opt_label,
                                        value=value,
                                        selected=value == selected_environment,
                                    )
                with Row(gap=2, css_class="flex-wrap"):
                    Button(
                        "Load schema",
                        variant="success",
                        on_click=job_type_action,
                    )
                    _async_btn("Refresh job types", action=refresh_types_action, variant="outline")
                    _async_btn("Refresh connectors", action=refresh_connectors_action, variant="outline")
                    with If(STATE.loading):
                        with Row(gap=2, align="center"):
                            Loader(variant="spin", size="sm")
                            Muted("Working…")

        # ── Job type contract summary ────────────────────────────────────────
        with If(STATE.formSchema.type):
            with Card(css_class="glass-card"):
                with CardHeader():
                    CardTitle(STATE.formSchema.display_name)
                    with If(STATE.formSchema.description):
                        CardDescription(STATE.formSchema.description)
                with CardContent():
                    with Column(gap=2):
                        Small("Required config")
                        Muted(STATE.formSchema.required_config.join(", ").default("—"))
                        Small("Required params")
                        Muted(STATE.formSchema.required_params.join(", ").default("—"))
                        Small("Allowed connector types")
                        Muted(STATE.formSchema.connector_types.join(", ").default("any"))

        # ── Connector picker ─────────────────────────────────────────────────
        with Card(css_class="glass-card"):
            with CardHeader():
                CardTitle("Connector")
                CardDescription(
                    "Existing connectors filtered by the selected job type's required connector type."
                )
            with CardContent():
                with Column(gap=3):
                    with If(STATE.availableConnectors.length() > 0):
                        with Field():
                            FieldTitle("Use existing connector")
                            with FieldContent():
                                with Select(name="selectedConnector"):
                                    with ForEach("availableConnectors") as conn:
                                        SelectOption(
                                            conn.name + " · " + conn.connector_type + " · " + conn.environment,
                                            value=conn.id,
                                        )
                    with Else():
                        Alert(
                            variant="info",
                            title="No connectors found",
                            description=(
                                "No connectors match the selected type/environment. "
                                "Enter a connector name below to use as a free-form label, "
                                "or register one via /connectors first."
                            ),
                        )
                    with Field():
                        FieldTitle("Or enter connector identifier")
                        FieldDescription("Free-form fallback when no registered connector matches.")
                        with FieldContent():
                            Input(
                                name="selectedConnector",
                                placeholder="github / sql-mcp / control-center",
                            )

        # ── Job basics ───────────────────────────────────────────────────────
        with Card(css_class="glass-card"):
            with CardHeader():
                CardTitle("Job basics")
            with CardContent():
                with Grid(columns={"md": 2}, gap=4):
                    with Field():
                        FieldTitle("Name")
                        with FieldContent():
                            Input(name="jobName", placeholder="Daily users export")
                    _select_field(
                        "Data sensitivity",
                        "dataSensitivity",
                        _SENSITIVITY_OPTIONS,
                        selected_value=initial_state.get("dataSensitivity", "low"),
                    )
                with Field():
                    FieldTitle("Tags")
                    FieldDescription("Comma-separated labels.")
                    with FieldContent():
                        Input(name="tagsText", placeholder="finance, daily")

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
                        "Reset form",
                        variant="outline",
                        on_click=[
                            SetState("config", {}),
                            SetState("params", {}),
                            SetState("createdJob", None),
                            SetState("lastRun", None),
                            SetState("runPrompt", ""),
                            SetState("jobName", ""),
                            SetState("tagsText", ""),
                        ],
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
        title="Control Center Job Designer",
        state=initial_state,
        css_class="max-w-5xl px-4 py-6 md:px-6",
        stylesheets=[APP_STYLES],
        theme=Theme(mode="dark", gradient=False),
        view=view,
    )


def _initial_state(
    *,
    job_types: list[dict] | None = None,
    selected_type: str = "mcp",
    environment: str = "dev",
) -> dict[str, Any]:
    available_job_types = job_types or _static_job_types()
    selected_schema = _static_form_schema(selected_type)
    if not selected_schema.get("type") and available_job_types:
        selected_type = available_job_types[0].get("type") or ""
        selected_schema = _static_form_schema(selected_type)

    return {
        "availableJobTypes": available_job_types,
        "apiJobTypes": [],
        "availableConnectors": [],
        "selectedJobType": selected_type,
        "selectedConnectorType": (selected_schema.get("connector_types") or [selected_type])[0],
        "selectedConnector": "",
        "kind": selected_schema.get("kind", "runtime"),
        "environment": environment,
        "dataSensitivity": "low",
        "jobName": "",
        "tagsText": "",
        "config": selected_schema.get("defaults_config", {}),
        "params": selected_schema.get("defaults_params", {}),
        "runPrompt": "",
        "formSchema": selected_schema,
        "createdJob": None,
        "lastRun": None,
        "loading": False,
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
        "kind": contract_schema.get("kind") or ("artifact" if contract_schema.get("artifact") else "runtime"),
        "config_fields": config_fields,
        "params_fields": params_fields,
        "required_config": _required(contract_schema, "config"),
        "optional_config": _optional(contract_schema, "config"),
        "required_params": _required(contract_schema, "params"),
        "optional_params": _optional(contract_schema, "params"),
        "connector_types": _extract_connector_types(contract_schema),
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


def _split_tags(tags_text: str | None) -> list[str]:
    if not tags_text:
        return []
    return [t.strip() for t in tags_text.split(",") if t.strip()]


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


def _contract_payload(job_type: str) -> dict[str, Any]:
    contract = KNOWN_CONTRACTS.get(_normalize_job_type(job_type))
    if contract is None:
        return {}
    return contract.model_dump(mode="json")


def _static_form_schema(job_type: str) -> dict[str, Any]:
    payload = _contract_payload(job_type)
    return _form_schema_payload(payload) if payload else _form_schema_payload({})


def _schema_for_job_type(job_type: str, *, allow_api_fallback: bool = False) -> dict[str, Any]:
    normalized = _normalize_job_type(job_type)
    if not normalized:
        return _form_schema_payload({})
    static_schema = _static_form_schema(normalized)
    if static_schema.get("type"):
        return static_schema

    if not allow_api_fallback:
        return _form_schema_payload({})

    try:
        raw = _api_get(f"/job-types/{normalized}/form-schema")
        return _form_schema_payload({**raw, **_job_type_metadata_for(raw)})
    except Exception as exc:
        logger.warning("Failed to fetch dynamic form schema for %s: %s", normalized, exc)
        raise


def _static_job_types() -> list[dict[str, Any]]:
    return [_job_type_summary(contract.model_dump(mode="json")) for contract in KNOWN_CONTRACTS.values()]


def _dynamic_job_type_summaries(api_job_types: list[dict[str, Any]]) -> list[dict[str, Any]]:
    static_types = set(KNOWN_CONTRACTS)
    return [
        item
        for item in api_job_types
        if isinstance(item, dict)
        and item.get("type")
        and str(item["type"]).strip().lower() not in static_types
    ]


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


def _api_job_type_summaries() -> list[dict[str, Any]]:
    return [_job_type_summary(c) for c in _job_type_items(_api_get("/job-types"))]


# ── Server build ─────────────────────────────────────────────────────────────


def _prefetch_job_types() -> list[dict]:
    """Static initial job types; API refresh happens through list_job_types."""
    return _static_job_types()


def build_server() -> FastMCP:
    mcp = FastMCP(SERVER_NAME, instructions=SERVER_DESCRIPTION)

    bootstrap_types = _prefetch_job_types()
    logger.info("Bootstrapped %d job types into the designer", len(bootstrap_types))
    current_initial_state = _initial_state(job_types=bootstrap_types)
    blank_app = _build_app(current_initial_state)

    @mcp.resource(
        APP_RESOURCE_URI,
        name="control_center_job_designer",
        description=(
            "Open the Control Center job designer — pick a job type, configure "
            "fields driven by the type's contract, and create or trigger jobs."
        ),
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
        description=(
            "Open the interactive Control Center job designer. Optionally "
            "preselects a job type."
        ),
        app=True,
    )
    def open_job_designer(
        job_type: str = "",
        environment: Literal["dev", "semi-prod", "prod"] = "dev",
    ) -> PrefabApp:
        nonlocal current_initial_state
        normalized_job_type = _normalize_job_type(job_type) or "mcp"
        current_initial_state = _initial_state(
            job_types=bootstrap_types,
            selected_type=normalized_job_type,
            environment=environment,
        )
        return _build_app(current_initial_state)

    @mcp.tool(
        name="list_job_types",
        description="List all known JobTypeContracts available to this Control Center deployment.",
    )
    def list_job_types() -> dict[str, Any]:
        try:
            items = _api_job_type_summaries()
        except Exception as exc:
            logger.warning("list_job_types failed: %s", exc)
            items = []
        return {
            "items": _merge_job_type_summaries(_static_job_types(), items),
            "dynamic_items": _dynamic_job_type_summaries(items),
        }

    @mcp.tool(
        name="get_form_schema",
        description=(
            "Fetch the dynamic form schema for a job type. Returns config/params "
            "FieldSpec lists, defaults, required-field lists, and allowed connector types."
        ),
    )
    def get_form_schema(job_type: str) -> dict[str, Any]:
        normalized = _normalize_job_type(job_type)
        if not normalized:
            return _form_schema_payload({})
        return _schema_for_job_type(normalized, allow_api_fallback=True)

    @mcp.tool(
        name="list_connectors",
        description=(
            "List existing connectors. Optionally filter by connector_type "
            "(e.g. 'sql-mcp', 'github') and/or environment."
        ),
    )
    def list_connectors(
        connector_type: str = "",
        environment: str = "",
    ) -> dict[str, Any]:
        params: dict[str, str] = {}
        if connector_type.strip():
            params["connector_type"] = connector_type.strip()
        if environment.strip():
            params["env"] = environment.strip()
        try:
            response = _api_get("/connectors", params=params or None)
        except Exception as exc:
            logger.warning("list_connectors failed: %s", exc)
            response = {"items": []}

        items = response.get("items", []) if isinstance(response, dict) else (response or [])
        return {
            "items": [
                {
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "connector_type": c.get("connector_type"),
                    "environment": c.get("environment"),
                    "status": c.get("status"),
                    "is_shared": c.get("is_shared", False),
                }
                for c in items
            ]
        }

    @mcp.tool(
        name="create_job",
        description=(
            "Register a new Control Center job. Config is coerced from the "
            "selected JobTypeContract before API-side validation."
        ),
    )
    def create_job(
        name: str,
        type: str,
        connector: str,
        kind: Literal["runtime", "artifact"] = "runtime",
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

        merged_tags = list(tags or []) + _split_tags(tags_text)

        try:
            schema = _schema_for_job_type(normalized_type, allow_api_fallback=True)
            config = _coerce_field_values(schema["config_fields"], config or {})
        except Exception as exc:
            logger.warning("create_job: schema coercion skipped, sending raw config: %s", exc)
            config = config or {}

        body = {
            "name": name.strip(),
            "kind": kind,
            "type": normalized_type,
            "connector": connector.strip(),
            "environment": environment,
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
        if prompt and prompt.strip():
            body["prompt"] = prompt.strip()
        return _api_post(f"/jobs/{job_id}/runs", body)

    return mcp


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
    embedded = contract.get("connector_types")
    if embedded:
        return list(embedded)

    requires = contract.get("requires")
    if not requires:
        return []
    # Old shape (single ExecutionRequirement dict) — extract names directly.
    if isinstance(requires, dict):
        return list(requires.get("names") or requires.get("connector_types") or [])
    # New shape (list of ExecutionRequirement dicts).
    out: list[str] = []
    seen: set[str] = set()
    for req in requires:
        if not isinstance(req, dict):
            continue
        for name in (req.get("names") or []):
            if name and name not in seen:
                seen.add(name)
                out.append(name)
    return out


def _job_type_summary(contract: dict) -> dict[str, Any]:
    return {
        "type": contract.get("type"),
        "display_name": contract.get("display_name") or contract.get("type"),
        "description": contract.get("description"),
        "kind": contract.get("kind") or ("artifact" if contract.get("artifact") else "runtime"),
        "connector_types": _extract_connector_types(contract),
    }


def _connector_types_for(form_schema: dict) -> list[str]:
    """Derive connector types for a fallback API form-schema payload."""
    return _job_type_metadata_for(form_schema).get("connector_types", [])


def _job_type_metadata_for(form_schema: dict) -> dict[str, Any]:
    embedded_connectors = form_schema.get("connector_types")
    embedded_kind = form_schema.get("kind")
    if embedded_connectors is not None and embedded_kind:
        return {"connector_types": list(embedded_connectors or []), "kind": embedded_kind}

    job_type = form_schema.get("type")
    fallback = {
        "connector_types": list(embedded_connectors or []),
        "kind": embedded_kind or ("artifact" if form_schema.get("artifact") else "runtime"),
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
                "kind": summary["kind"],
            }
    return fallback


mcp = build_server()


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8001)
