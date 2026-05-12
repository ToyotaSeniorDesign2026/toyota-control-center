"""Two-step Instructor flow that turns a plain-English intent into a full
Control Center job draft.

Step 1: pick the JobType from `KNOWN_CONTRACTS` (dynamic Literal + reasoning).
Step 2: build a contract-specific Pydantic model with `pydantic.create_model`
        — typed config/params sub-models, a Literal-constrained connector list —
        and let Instructor fill it.

The orchestrator returns a flat dict shaped like a `patch_draft_snapshot`
patch so the caller can pipe the result straight through the existing
`_apply_designer_patch` pipeline. No new merge logic; no state side-effects
inside this module.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Literal

from pydantic import BaseModel, Field, create_model

try:
    import instructor  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - optional dependency
    instructor = None

from control_center.specs import KNOWN_CONTRACTS
from control_center.specs.job_type import BASE_TYPE_MAP, FieldSpec, FieldType, JobTypeContract


logger = logging.getLogger(__name__)

DEFAULT_INSTRUCTOR_MODEL = "google/gemini-2.5-flash"


# ── Instructor client plumbing ───────────────────────────────────────────────


def _resolve_instructor_model() -> str:
    return os.environ.get("CONTROL_CENTER_MCP_INSTRUCTOR_MODEL") or DEFAULT_INSTRUCTOR_MODEL


def _async_instructor_client(provider_model: str):
    """Build an async Instructor client. Raises if the dependency is missing
    or the provider's API key isn't set."""
    if instructor is None:
        raise RuntimeError("instructor is not installed. `uv add instructor` to enable AI drafts.")
    if provider_model.startswith("google/") and not os.environ.get("GOOGLE_API_KEY"):
        raise RuntimeError("GOOGLE_API_KEY must be set to use Instructor with Google models.")
    if provider_model.startswith("openai/") and not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY must be set to use Instructor with OpenAI models.")
    if provider_model.startswith("anthropic/") and not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY must be set to use Instructor with Anthropic models.")
    return instructor.from_provider(provider_model, async_client=True)


# ── Dynamic-model construction ───────────────────────────────────────────────


def _literal_of(values: list[str]) -> Any:
    """Build a `Literal[...]` of string values at runtime.

    `Literal[*values]` requires PEP 646 (Python 3.11+); `Literal.__getitem__`
    works on every version. Used in place of dynamic Enums so the LLM can
    return plain strings (Instructor passes those straight through, and
    Pydantic v2 validates Literal-of-strings without a custom coercer).
    """
    return Literal.__getitem__(tuple(values))


def _python_type_for_spec(spec: FieldSpec) -> Any:
    """Map a FieldSpec to a Pydantic-friendly Python type.

    - `enum` strings → a runtime `Literal[...]` over the allowed values.
    - Everything else uses `BASE_TYPE_MAP`.
    """
    if spec.enum:
        return _literal_of(list(spec.enum))
    return BASE_TYPE_MAP[spec.type]


def _section_model(model_name: str, specs: list[FieldSpec], required: set[str]) -> type[BaseModel]:
    """Build a Pydantic submodel for a contract's config or params section.

    All non-required fields become Optional with the FieldSpec default; required
    fields stay mandatory. Descriptions carry the LLM's instructions.
    """
    fields: dict[str, Any] = {}
    for spec in specs:
        py_type = _python_type_for_spec(spec)
        description = spec.description or f"{spec.name} value for this job type."
        if spec.name in required:
            fields[spec.name] = (py_type, Field(..., description=description))
        else:
            optional_type = py_type | None
            default = spec.default
            fields[spec.name] = (optional_type, Field(default=default, description=description))
    if not fields:
        # Empty section — return an empty object model. We avoid setting __doc__
        # so the parent schema doesn't surface a misleading description to the LLM.
        return create_model(model_name)
    return create_model(model_name, **fields)


# ── Step 1: pick a JobType ───────────────────────────────────────────────────


def _build_job_type_selection_model() -> type[BaseModel]:
    job_type_literal = _literal_of(list(KNOWN_CONTRACTS.keys()))
    return create_model(
        "JobTypeSelection",
        selected=(job_type_literal, Field(..., description="The JobType that best fits the user's intent.")),
        reasoning=(str, Field(..., description="One concise sentence explaining why this JobType fits.")),
    )


def _extract_connector_names_from_contract(contract: JobTypeContract) -> list[str]:
    """Walk contract.requires for ExecutionRequirement.names entries."""
    names: list[str] = []
    seen: set[str] = set()
    for req in contract.requires or []:
        for n in req.names or []:
            text = str(n).strip()
            if text and text not in seen:
                seen.add(text)
                names.append(text)
    return names


def _job_type_catalog_blurb() -> str:
    """Human-readable summary of available JobTypes for the JobType-selector LLM call.

    Each entry surfaces the bits the model needs to discriminate JobTypes:
    display name, description, executor_type (so the model can tell a Python
    runtime from an MCP tool call), and approved connector names (so the model
    knows which JobType can actually reach the systems implied by the intent).
    Without the connector list, the model can't tell e.g. that an "MCP" JobType
    is the right home for an `sql-mcp`-driven query — it just sees three labels.
    """
    lines: list[str] = []
    for key, contract in KNOWN_CONTRACTS.items():
        display = contract.display_name or key
        desc = contract.description or "(no description)"
        executor = contract.executor_type
        connectors = _extract_connector_names_from_contract(contract)
        connector_str = ", ".join(connectors) if connectors else "(none required)"
        lines.append(
            f"- {key} — {display}\n"
            f"    description: {desc}\n"
            f"    executor: {executor}\n"
            f"    approved connectors: {connector_str}"
        )
    return "\n".join(lines)


async def select_job_type(
    *,
    intent: str,
    name: str = "",
    environment: str = "dev",
    provider_model: str | None = None,
    max_retries: int = 2,
) -> tuple[str, str]:
    """Pick the best-fit JobType for the user's intent. Returns (type, reasoning)."""
    resolved_model = provider_model or _resolve_instructor_model()
    client = _async_instructor_client(resolved_model)
    selection_model = _build_job_type_selection_model()

    result = await client.create(
        response_model=selection_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are routing a Control Center job request to the right JobType. "
                    "Pick exactly one JobType from the catalog; be conservative — if the "
                    "intent doesn't clearly map to a specialized type, pick the most general one."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Job name: {name or '(unspecified)'}\n"
                    f"Target environment: {environment}\n"
                    f"Intent:\n{intent}\n\n"
                    f"Available JobTypes:\n{_job_type_catalog_blurb()}"
                ),
            },
        ],
        max_retries=max_retries,
    )
    selected = str(result.selected)
    reasoning = str(result.reasoning).strip()
    logger.info("select_job_type → %s (%s)", selected, reasoning)
    return selected, reasoning


# ── Step 2: fill the dynamic JobDraft for the chosen contract ────────────────


def _build_draft_model(contract: JobTypeContract, approved_connectors: list[str]) -> type[BaseModel]:
    """Build a contract-shaped JobDraft model for Instructor.

    - `selected_job_type` is pinned to the contract's type via a Literal-of-one.
    - `selected_connectors` is constrained to the contract's approved names.
    - `config` and `params` are typed sub-models built from the FieldSpec lists.
    """
    config_specs = list(contract.config.fields.values())
    params_specs = list(contract.params.fields.values())

    config_model = _section_model("GeneratedConfig", config_specs, set(contract.config.required))
    params_model = _section_model("GeneratedParams", params_specs, set(contract.params.required))

    pinned_job_type = _literal_of([contract.type])
    if approved_connectors:
        connectors_type: Any = list[_literal_of(approved_connectors)]
    else:
        connectors_type = list[str]

    # Optional scalars default to None so that model_dump(exclude_none=True)
    # drops them when the LLM has no opinion. _apply_designer_patch skips
    # absent fields (preserves the user's current value), which gives this
    # tool the same "merge, don't clobber" semantics as patch_draft_snapshot.
    # The required fields below (intent, job_name, selected_job_type, config,
    # params) are always present in the output because they're the load-bearing
    # spine of the generated draft.
    omit_hint = " Omit (return null) if you have no strong opinion so the user's existing value survives."
    return create_model(
        "GeneratedJobDraft",
        intent=(str, Field(..., description="Plain-English statement of what this job should accomplish.")),
        job_name=(str, Field(..., description="Short, slug-friendly job title — three to six words.")),
        environment=(
            _literal_of(["dev", "staging", "prod"]) | None,
            Field(default=None, description="Target environment for execution." + omit_hint),
        ),
        data_sensitivity=(
            _literal_of(["low", "medium", "high"]) | None,
            Field(default=None, description="Pick 'high' for PII or regulated data, 'medium' for internal, 'low' for public." + omit_hint),
        ),
        tags_text=(str | None, Field(default=None, description="Comma-separated labels, e.g. 'finance, daily'." + omit_hint)),
        selected_job_type=(pinned_job_type, Field(..., description="Pinned to the resolved JobType.")),
        selected_connectors=(
            connectors_type | None,
            Field(default=None, description="Approved connector names required to satisfy the intent." + omit_hint),
        ),
        run_prompt=(str | None, Field(default=None, description="Optional per-run prompt passed alongside params." + omit_hint)),
        config=(config_model, Field(..., description="Job-level configuration for this JobType.")),
        params=(params_model, Field(..., description="Default run-time parameters for this JobType.")),
    )


async def generate_job_draft_from_intent(
    *,
    intent: str,
    name: str = "",
    environment: str = "dev",
    provider_model: str | None = None,
    max_retries: int = 2,
) -> dict[str, Any]:
    """End-to-end: intent → JobType pick → filled draft.

    Returns a flat dict shaped like a `patch_draft_snapshot` patch, e.g.:
        {
          "selected_job_type": "mcp",
          "job_name": "...",
          "intent": "...",
          "config": {...},
          "params": {...},
          ...
          "meta": {"job_type_reasoning": "...", "job_type": "..."}
        }
    """
    if not intent.strip():
        raise ValueError("intent must be non-empty.")

    resolved_model = provider_model or _resolve_instructor_model()
    job_type, reasoning = await select_job_type(
        intent=intent, name=name, environment=environment, provider_model=resolved_model,
    )
    contract = KNOWN_CONTRACTS.get(job_type)
    if contract is None:
        raise RuntimeError(f"select_job_type returned an unknown type: {job_type!r}")

    approved_connectors = _extract_connector_names_from_contract(contract)
    draft_model = _build_draft_model(contract, approved_connectors)

    client = _async_instructor_client(resolved_model)
    result = await client.create(
        response_model=draft_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are completing a Control Center job draft for a specific JobType. "
                    "Fill the required fields (intent, job_name, selected_job_type, config, params) "
                    "consistently with the user's intent. For optional fields (environment, "
                    "data_sensitivity, tags_text, selected_connectors, run_prompt): only fill them "
                    "if the intent clearly implies a value — otherwise return null so the user's "
                    "existing form value is preserved. Use the JobType's config and params schemas "
                    "exactly — do not invent fields. Pick connectors only from the approved list."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Job name hint: {name or '(none — propose one)'}\n"
                    f"Target environment: {environment}\n"
                    f"Resolved JobType: {job_type}\n"
                    f"JobType reasoning: {reasoning}\n"
                    f"Intent:\n{intent}"
                ),
            },
        ],
        max_retries=max_retries,
    )

    patch = result.model_dump(mode="json", exclude_none=True)
    patch["meta"] = {"job_type_reasoning": reasoning, "job_type": job_type}
    return patch
