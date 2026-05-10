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
from fastmcp.apps.approval import Approval
from prefab_ui import PrefabApp
from prefab_ui.app import ResolvedTool
from prefab_ui.actions import AppendState, PopState, SetState, ShowToast
from prefab_ui.actions.mcp import CallTool, RequestDisplayMode, SendMessage, UpdateContext
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
    Combobox,
    ComboboxOption,
    Div,
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
    Loader,
    Muted,
    P,
    RESULT,
    Row,
    STATE,
    Select,
    SelectOption,
    Small,
    Text,
    Textarea,
)
from prefab_ui.rx import ERROR, EVENT, Rx
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

def _rx_path(value: Any) -> str:
    text = str(value).strip()
    if text.startswith("{{") and text.endswith("}}"):
        return text[2:-2].strip()
    return text


def _render_enum_select(state_root: str, field: Any, option_count: int) -> None:
    enum_path = _rx_path(field.enum)
    with Select(name=f"{state_root}.{field.name}"):
        for i in range(option_count):
            option = f"{{{{ {enum_path}.{i} }}}}"
            SelectOption(option, value=option)


def _render_enum_select_for_field(state_root: str, field: Any) -> None:
    """Render enum select options as direct SelectOption children.

    Select does not reliably materialize SelectOption children nested under a
    ForEach when the enum list belongs to a loop-scoped field object.
    """
    with If(field.enum.length() == 1):
        _render_enum_select(state_root, field, 1)
    for count in range(2, MAX_ENUM_OPTIONS + 1):
        with Elif(field.enum.length() == count):
            _render_enum_select(state_root, field, count)
    with Elif(field.enum.length() > MAX_ENUM_OPTIONS):
        _render_enum_select(state_root, field, MAX_ENUM_OPTIONS)


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
    """Render a connector Combobox whose direct option count matches state length.

    Combobox does not materialize options produced by ForEach/If children. The
    Condition must wrap the whole Combobox, not individual options.
    """
    with If(STATE.availableConnectors.length() == 1):
        _render_connector_combobox(1)
    for count in range(2, MAX_CONNECTOR_OPTIONS + 1):
        with Elif(STATE.availableConnectors.length() == count):
            _render_connector_combobox(count)
    with Elif(STATE.availableConnectors.length() > MAX_CONNECTOR_OPTIONS):
        _render_connector_combobox(MAX_CONNECTOR_OPTIONS)
        Alert(
            variant="warning",
            title="Connector list truncated",
            description=f"Showing the first {MAX_CONNECTOR_OPTIONS} connector options.",
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
    """Fetch the form schema for the given job type, then refresh connectors.

    `job_type_expr` is whatever the renderer should pass in — typically `EVENT`
    (for a Select on_change) or a selectedJobType state reference (for a button).
    Connector options are populated from the schema payload here; explicit
    connector refreshes still call the backend connector API.
    """
    return CallTool(
        "get_form_schema",
        arguments={"job_type": job_type_expr},
        on_success=[
            SetState("formSchema", RESULT),
            SetState("config", RESULT.defaults_config),
            SetState("params", RESULT.defaults_params),
            SetState("selectedConnector", ""),
            SetState("selectedConnectors", []),
            SetState("connectorText", ""),
            SetState("availableConnectors", RESULT.connector_items),
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


def _ai_context_payload(environment_expr: Any) -> dict[str, Any]:
    return {
        "control_center_job_designer": {
            "selected_job_type": "{{ selectedJobType | '' }}",
            "environment": environment_expr,
            "job_name": "{{ jobName | '' }}",
            "data_sensitivity": "{{ dataSensitivity | 'unknown' }}",
            "tags": "{{ tagsText | '' }}",
            "selected_connectors": "{{ selectedConnectors | [] }}",
            "manual_connector": "{{ connectorText | '' }}",
            "config": "{{ config | {} }}",
            "run_params": "{{ params | {} }}",
            "schema": {
                "type": "{{ formSchema.type | '' }}",
                "display_name": "{{ formSchema.display_name | '' }}",
                "required_config": "{{ formSchema.required_config | [] }}",
                "required_params": "{{ formSchema.required_params | [] }}",
                "connector_types": "{{ formSchema.connector_types | [] }}",
            },
        }
    }


def _capture_current_draft_action(
    environment_expr: Any,
    *,
    on_success: list[Any] | None = None,
) -> CallTool:
    return CallTool(
        "capture_current_draft",
        arguments={"current_state": _current_designer_state_payload(environment_expr)},
        on_success=on_success,
        on_error=ShowToast(ERROR, variant="error"),
    )


def _update_ai_context_action(environment_expr: Any) -> list[Any]:
    return [
        _capture_current_draft_action(environment_expr),
        UpdateContext(structured_content=_ai_context_payload(environment_expr)),
        ShowToast("AI context updated.", variant="success"),
    ]


def _review_setup_action(environment_expr: Any) -> list[Any]:
    return [
        _capture_current_draft_action(
            environment_expr,
            on_success=[
                UpdateContext(structured_content={"control_center_job_designer": RESULT.draft}),
                SendMessage(
                    "Please review the current Control Center job setup. Check connectors, "
                    "required config, and missing fields before I create it.\n\n"
                    "Current draft JSON:\n```json\n{{ $result.draft_json }}\n```"
                ),
            ],
        ),
    ]


def _current_designer_state_payload(environment_expr: Any) -> dict[str, Any]:
    return {
        "selectedJobType": "{{ selectedJobType | '' }}",
        "selectedConnector": "{{ selectedConnector | '' }}",
        "selectedConnectors": "{{ selectedConnectors | [] }}",
        "connectorText": "{{ connectorText | '' }}",
        "environment": environment_expr,
        "dataSensitivity": "{{ dataSensitivity | 'low' }}",
        "jobName": "{{ jobName | '' }}",
        "tagsText": "{{ tagsText | '' }}",
        "config": "{{ config | {} }}",
        "params": "{{ params | {} }}",
        "runPrompt": "{{ runPrompt | '' }}",
        "formSchema": STATE.formSchema,
        "availableConnectors": "{{ availableConnectors | [] }}",
    }


def _patch_value(patch: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in patch:
            return patch[key]
    return None


def _patch_list(value: Any) -> list[Any] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            return [part.strip() for part in text.split(",") if part.strip()]
        if isinstance(decoded, list):
            return decoded
        return [decoded]
    if isinstance(value, (tuple, set)):
        return list(value)
    return [value]


def _patch_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None
    return None


def _draft_snapshot_from_state(current_state: dict[str, Any] | None) -> dict[str, Any]:
    current = current_state or {}
    form_schema = _patch_dict(current.get("formSchema")) or _form_schema_payload({})
    selected_connectors = _patch_list(current.get("selectedConnectors")) or []
    available_connectors = _patch_list(current.get("availableConnectors")) or []
    config = _patch_dict(current.get("config")) or {}
    params = _patch_dict(current.get("params")) or {}
    selected_job_type = _normalize_job_type(current.get("selectedJobType")) or str(
        form_schema.get("type") or ""
    )
    environment = _normalize_environment(current.get("environment"), default="dev") or "dev"
    draft = {
        "selected_job_type": selected_job_type,
        "environment": environment,
        "job_name": str(current.get("jobName") or ""),
        "data_sensitivity": str(current.get("dataSensitivity") or "low"),
        "tags_text": str(current.get("tagsText") or ""),
        "selected_connector": str(current.get("selectedConnector") or ""),
        "selected_connectors": selected_connectors,
        "manual_connector": str(current.get("connectorText") or ""),
        "config": config,
        "params": params,
        "run_prompt": str(current.get("runPrompt") or ""),
        "available_connectors": available_connectors,
        "form_schema": form_schema,
    }
    return {
        "status": "captured",
        "draft": draft,
        "draft_json": json.dumps(draft, indent=2, sort_keys=True),
    }


def _apply_designer_patch(current_state: dict[str, Any] | None, patch: dict[str, Any] | None) -> dict[str, Any]:
    current = current_state or {}
    patch = patch or {}
    applied: list[str] = []

    selected_type = str(current.get("selectedJobType") or "")
    environment = _normalize_environment(current.get("environment"), default="dev") or "dev"
    data_sensitivity = str(current.get("dataSensitivity") or "low")
    job_name = str(current.get("jobName") or "")
    tags_text = str(current.get("tagsText") or "")
    selected_connector = str(current.get("selectedConnector") or "")
    connector_text = str(current.get("connectorText") or "")
    run_prompt = str(current.get("runPrompt") or "")
    selected_connectors = _patch_list(current.get("selectedConnectors")) or []
    available_connectors = _patch_list(current.get("availableConnectors")) or []
    config = _patch_dict(current.get("config")) or {}
    params = _patch_dict(current.get("params")) or {}
    form_schema = _patch_dict(current.get("formSchema")) or _form_schema_payload({})

    next_type = _patch_value(patch, "selectedJobType", "selected_job_type", "job_type", "type")
    if next_type is not None:
        selected_type = _normalize_job_type(next_type)
        applied.append("selectedJobType")

    next_schema = _patch_value(patch, "formSchema", "form_schema")
    schema_replaced = False
    if isinstance(next_schema, dict):
        form_schema = _form_schema_payload(next_schema)
        selected_type = form_schema.get("type") or selected_type
        available_connectors = form_schema.get("connector_items", [])
        schema_replaced = True
        applied.extend(["formSchema", "availableConnectors"])
    elif selected_type and selected_type != current.get("selectedJobType"):
        form_schema = _schema_for_job_type(selected_type, allow_api_fallback=True)
        available_connectors = form_schema.get("connector_items", [])
        schema_replaced = True
        applied.extend(["formSchema", "availableConnectors"])

    for patch_key, attr_name in (
        (("environment",), "environment"),
        (("dataSensitivity", "data_sensitivity"), "data_sensitivity"),
        (("jobName", "job_name", "name"), "job_name"),
        (("tagsText", "tags_text", "tags"), "tags_text"),
        (("selectedConnector", "selected_connector"), "selected_connector"),
        (("connectorText", "connector_text", "manual_connector"), "connector_text"),
        (("runPrompt", "run_prompt"), "run_prompt"),
    ):
        value = _patch_value(patch, *patch_key)
        if value is None:
            continue
        if attr_name == "environment":
            environment = _normalize_environment(value, default=environment) or environment
        elif attr_name == "data_sensitivity":
            data_sensitivity = str(value)
        elif attr_name == "job_name":
            job_name = str(value)
        elif attr_name == "tags_text":
            tags_text = ", ".join(value) if isinstance(value, list) else str(value)
        elif attr_name == "selected_connector":
            selected_connector = str(value)
        elif attr_name == "connector_text":
            connector_text = str(value)
        elif attr_name == "run_prompt":
            run_prompt = str(value)
        applied.append(attr_name)

    next_selected_connectors = _patch_list(
        _patch_value(patch, "selectedConnectors", "selected_connectors", "connectors")
    )
    if next_selected_connectors is not None:
        selected_connectors = next_selected_connectors
        applied.append("selectedConnectors")

    next_available_connectors = _patch_list(
        _patch_value(patch, "availableConnectors", "available_connectors")
    )
    if next_available_connectors is not None:
        available_connectors = next_available_connectors
        applied.append("availableConnectors")

    replace_config = _patch_dict(_patch_value(patch, "replace_config"))
    config_update = _patch_dict(_patch_value(patch, "config", "config_updates"))
    if replace_config is not None:
        config = replace_config
        applied.append("config")
    elif config_update is not None:
        config = {**({} if schema_replaced else config), **config_update}
        applied.append("config")
    elif schema_replaced:
        config = form_schema.get("defaults_config", {})

    replace_params = _patch_dict(_patch_value(patch, "replace_params"))
    params_update = _patch_dict(_patch_value(patch, "params", "run_params", "params_updates"))
    if replace_params is not None:
        params = replace_params
        applied.append("params")
    elif params_update is not None:
        params = {**({} if schema_replaced else params), **params_update}
        applied.append("params")
    elif schema_replaced:
        params = form_schema.get("defaults_params", {})

    return {
        "status": "applied",
        "message": (
            f"Applied AI changes: {', '.join(dict.fromkeys(applied))}."
            if applied
            else "No AI changes were pending."
        ),
        "applied": list(dict.fromkeys(applied)),
        "selected_job_type": selected_type,
        "selected_connector": selected_connector,
        "selected_connectors": selected_connectors,
        "connector_text": connector_text,
        "available_connectors": available_connectors,
        "environment": environment,
        "data_sensitivity": data_sensitivity,
        "job_name": job_name,
        "tags_text": tags_text,
        "config": config,
        "params": params,
        "run_prompt": run_prompt,
        "form_schema": form_schema,
    }


def _apply_ai_changes_action(environment_expr: Any) -> CallTool:
    return CallTool(
        "apply_pending_designer_patch",
        arguments={"current_state": _current_designer_state_payload(environment_expr)},
        on_success=[
            SetState("selectedJobType", RESULT.selected_job_type),
            SetState("selectedConnector", RESULT.selected_connector),
            SetState("selectedConnectors", RESULT.selected_connectors),
            SetState("connectorText", RESULT.connector_text),
            SetState("availableConnectors", RESULT.available_connectors),
            SetState("environment", RESULT.environment),
            SetState("dataSensitivity", RESULT.data_sensitivity),
            SetState("jobName", RESULT.job_name),
            SetState("tagsText", RESULT.tags_text),
            SetState("config", RESULT.config),
            SetState("params", RESULT.params),
            SetState("runPrompt", RESULT.run_prompt),
            SetState("formSchema", RESULT.form_schema),
            SetState("loading", False),
            ShowToast(RESULT.message, variant="success"),
        ],
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
    update_ai_context_action = _update_ai_context_action(environment_ref)
    review_setup_action = _review_setup_action(environment_ref)
    apply_ai_changes_action = _apply_ai_changes_action(environment_ref)
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
                    Muted(
                        "Pick a job type and connector. Form fields adapt to the "
                        "selected contract."
                    )
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
                            variant="success",
                            on_click=update_ai_context_action,
                        )
                        Button(
                            "Refresh data",
                            variant="outline",
                            on_click=[
                                SetState("loading", True),
                                refresh_types_action,
                                refresh_connectors_action,
                            ],
                        )
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
                                        on_click=[
                                            AppendState("selectedConnectors", STATE.selectedConnector),
                                            SetState("selectedConnector", ""),
                                        ],
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
                            description=(
                                "No registered connectors match this job type and environment. "
                                "Use the manual connector field below or register a connector first."
                            ),
                        )
                    with Div(css_class="border-t border-emerald-200/10 pt-4"):
                        with Field():
                            FieldDescription("Manual fallback for a connector that is not listed above.")
                            with FieldContent():
                                Input(
                                    name="connectorText",
                                    placeholder="github / sql-mcp / control-center",
                                )

        # ── Job basics ───────────────────────────────────────────────────────
        with Card(css_class="glass-card"):
            with CardHeader():
                CardTitle("Job basics")
            with CardContent():
                with Column(gap=5):
                    with Grid(columns={"md": 2}, gap=5):
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
                        "Get AI feedback",
                        variant="outline",
                        on_click=review_setup_action,
                    )
                    _async_btn("Apply AI changes", action=apply_ai_changes_action, variant="outline")
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
                            SetState("selectedConnector", ""),
                            SetState("selectedConnectors", []),
                            SetState("connectorText", ""),
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
    selected_type: str = "",
    environment: str = "dev",
) -> dict[str, Any]:
    available_job_types = job_types or _static_job_types()
    selected_schema = _static_form_schema(selected_type) or {}

    states = {
        "availableJobTypes": available_job_types,
        "apiJobTypes": [],
        "availableConnectors": selected_schema.get("connector_items", []),
        "selectedJobType": selected_type or "",
        "selectedConnector": "",
        "selectedConnectors": [],
        "connectorText": "",
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
    return states


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


def _normalize_environment(value: Any, *, default: str = "") -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        value = str(value)
    text = value.strip()
    if not text:
        return default
    if _TEMPLATE_EXPR_RE.match(text):
        return ""
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        decoded = text
    if isinstance(decoded, str):
        text = decoded.strip()
    if not text:
        return default
    if _TEMPLATE_EXPR_RE.match(text):
        return ""
    return text


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

    bootstrap_types = _static_job_types()
    logger.info("Bootstrapped %d job types into the designer", len(bootstrap_types))
    current_initial_state = _initial_state(job_types=bootstrap_types)
    pending_designer_patch: dict[str, Any] | None = None
    current_draft_snapshot: dict[str, Any] = _draft_snapshot_from_state(current_initial_state)
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
        # Route the host to our resource HTML (carrying stylesheets= and the
        # baked-in initial wire data) instead of the shared Prefab renderer
        # iframe — `app=True` would skip our HTML and our custom CSS with it.
        app=AppConfig(
            resource_uri=APP_RESOURCE_URI,
            prefers_border=True,
        ),
    )
    def open_job_designer(
        job_type: str = "",
        environment: str = "dev",
    ) -> dict[str, Any]:
        nonlocal current_draft_snapshot, current_initial_state
        normalized_job_type = _normalize_job_type(job_type)
        normalized_environment = _normalize_environment(environment, default="dev") or "dev"
        current_initial_state = _initial_state(
            job_types=bootstrap_types,
            selected_type=normalized_job_type,
            environment=normalized_environment,
        )
        current_draft_snapshot = _draft_snapshot_from_state(current_initial_state)
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
        normalized_environment = _normalize_environment(environment)
        if not allowed_connector_types:
            return {"items": []}
        params: dict[str, str] = {}
        if len(allowed_connector_types) == 1:
            params["connector_type"] = allowed_connector_types[0]
        if normalized_environment:
            params["env"] = normalized_environment
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
        items = _merge_connector_items(items, allowed_connector_types, normalized_environment)
        return {
            "items": [
                {
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "connector_type": c.get("connector_type"),
                    "environment": c.get("environment"),
                    "status": c.get("status"),
                    "is_shared": c.get("is_shared", False),
                    "label": _connector_label(c),
                    "value": _connector_value(c),
                }
                for c in items
            ]
        }

    @mcp.tool(
        name="capture_current_draft",
        description=(
            "Capture the current Control Center job designer draft from the app UI. "
            "This is called by app buttons before updating AI context or asking for feedback."
        ),
    )
    def capture_current_draft(current_state: dict[str, Any]) -> dict[str, Any]:
        nonlocal current_draft_snapshot
        current_draft_snapshot = _draft_snapshot_from_state(current_state)
        return current_draft_snapshot

    @mcp.tool(
        name="get_current_draft",
        description=(
            "Return the latest captured Control Center job designer draft. Use this "
            "when the client does not support UpdateContext or when you need to inspect "
            "the current app state before proposing changes."
        ),
    )
    def get_current_draft() -> dict[str, Any]:
        return current_draft_snapshot

    @mcp.tool(
        name="queue_designer_patch",
        description=(
            "Queue AI-proposed changes for the open Control Center job designer. "
            "Use this for normal field changes (config, params, connectors, name, "
            "environment) or for a full form_schema replacement. The browser UI "
            "will not change until the user clicks Apply AI changes."
        ),
    )
    def queue_designer_patch(
        patch: dict[str, Any],
        summary: str = "",
    ) -> dict[str, Any]:
        nonlocal pending_designer_patch
        if not isinstance(patch, dict):
            raise ValueError("patch must be an object.")
        pending_designer_patch = patch
        return {
            "status": "queued",
            "message": "AI changes queued. Click Apply AI changes in the app to update the form.",
            "summary": summary,
            "patch": patch,
        }

    @mcp.tool(
        name="get_pending_designer_patch",
        description="Return the currently queued AI patch for the Control Center job designer.",
    )
    def get_pending_designer_patch() -> dict[str, Any]:
        return {
            "has_patch": pending_designer_patch is not None,
            "patch": pending_designer_patch or {},
        }

    @mcp.tool(
        name="clear_pending_designer_patch",
        description="Clear the queued AI patch without applying it to the app.",
    )
    def clear_pending_designer_patch() -> dict[str, Any]:
        nonlocal pending_designer_patch
        pending_designer_patch = None
        return {"status": "cleared"}

    @mcp.tool(
        name="apply_pending_designer_patch",
        description=(
            "Apply the queued AI patch to the current app state and return concrete "
            "Prefab state values for the UI to write with SetState."
        ),
    )
    def apply_pending_designer_patch(current_state: dict[str, Any] | None = None) -> dict[str, Any]:
        nonlocal current_draft_snapshot, pending_designer_patch
        result = _apply_designer_patch(current_state, pending_designer_patch)
        pending_designer_patch = None
        current_draft_snapshot = {
            "status": "captured",
            "draft": {
                "selected_job_type": result["selected_job_type"],
                "environment": result["environment"],
                "job_name": result["job_name"],
                "data_sensitivity": result["data_sensitivity"],
                "tags_text": result["tags_text"],
                "selected_connector": result["selected_connector"],
                "selected_connectors": result["selected_connectors"],
                "manual_connector": result["connector_text"],
                "config": result["config"],
                "params": result["params"],
                "run_prompt": result["run_prompt"],
                "available_connectors": result["available_connectors"],
                "form_schema": result["form_schema"],
            },
        }
        return result

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
        normalized_environment = _normalize_environment(environment, default="dev")
        if not normalized_environment:
            raise ValueError("Environment is required — pick one from the environment selector.")

        merged_tags = list(tags or []) + _split_tags(tags_text)

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
            "target_environment": _normalize_environment(target_environment, default="dev"),
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


def _connector_label(connector: dict[str, Any]) -> str:
    parts = [
        connector.get("name") or connector.get("id"),
        connector.get("connector_type"),
        connector.get("environment"),
    ]
    return " · ".join(str(part) for part in parts if part)


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
