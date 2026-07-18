"""Unit + integration coverage for `job_generation.py` — the two-step Instructor
flow behind `generate_full_job_draft`.

This module builds Pydantic models at runtime (`create_model`, `Literal`
construction, contract-shaped sub-models) and shapes the result into a
`patch_draft_snapshot`-style dict. None of that was exercised anywhere else in
the suite; the one `generate_full_job_draft` e2e test mocks the whole module out.

Boundary: the genuine external dependency is the LLM call. We fake *only* that —
`select_job_type` and the Instructor client — and let the real model
construction, validation, and `model_dump(exclude_none=True)` shaping run. That
mirrors the harness rule of faking the lowest real boundary and nothing above it.
"""

from __future__ import annotations

import typing
import unittest
from unittest import mock

from pydantic import ValidationError

import job_generation as jg
from control_center.specs import KNOWN_CONTRACTS
from control_center.specs.job_type import FieldSpec, FieldType


class LiteralAndTypeMappingTests(unittest.TestCase):
    def test_literal_of_builds_a_literal_over_the_values(self) -> None:
        lit = jg._literal_of(["a", "b", "c"])
        self.assertEqual(set(typing.get_args(lit)), {"a", "b", "c"})

    def test_enum_spec_maps_to_a_literal(self) -> None:
        spec = FieldSpec(name="mode", type=FieldType.STRING, enum=["fast", "slow"])
        py_type = jg._python_type_for_spec(spec)
        self.assertEqual(set(typing.get_args(py_type)), {"fast", "slow"})

    def test_scalar_spec_maps_through_base_type_map(self) -> None:
        self.assertIs(jg._python_type_for_spec(FieldSpec(name="n", type=FieldType.INTEGER)), int)
        self.assertIs(jg._python_type_for_spec(FieldSpec(name="s", type=FieldType.STRING)), str)


class SectionModelTests(unittest.TestCase):
    def test_required_and_optional_fields_are_marked_correctly(self) -> None:
        specs = [
            FieldSpec(name="req", type=FieldType.STRING),
            FieldSpec(name="opt", type=FieldType.INTEGER, default=7),
        ]
        model = jg._section_model("Sec", specs, {"req"})
        fields = model.model_fields
        self.assertTrue(fields["req"].is_required())
        self.assertFalse(fields["opt"].is_required())
        # Optional field falls back to the FieldSpec default.
        self.assertEqual(model(req="x").opt, 7)

    def test_missing_required_field_fails_validation(self) -> None:
        model = jg._section_model("Sec", [FieldSpec(name="req", type=FieldType.STRING)], {"req"})
        with self.assertRaises(ValidationError):
            model()

    def test_enum_field_rejects_out_of_range_value(self) -> None:
        specs = [FieldSpec(name="mode", type=FieldType.STRING, enum=["a", "b"])]
        model = jg._section_model("Sec", specs, set())
        self.assertEqual(model(mode="a").mode, "a")
        with self.assertRaises(ValidationError):
            model(mode="c")

    def test_empty_section_yields_a_blank_model_without_doc(self) -> None:
        model = jg._section_model("Empty", [], set())
        self.assertEqual(model.model_fields, {})
        self.assertIsNone(model.__doc__)  # no misleading description leaks to the LLM


class JobTypeSelectionModelTests(unittest.TestCase):
    def test_selection_is_constrained_to_known_contracts(self) -> None:
        model = jg._build_job_type_selection_model()
        a_known_type = next(iter(KNOWN_CONTRACTS))
        self.assertEqual(model(selected=a_known_type, reasoning="fits").selected, a_known_type)

    def test_unknown_selection_is_rejected(self) -> None:
        model = jg._build_job_type_selection_model()
        with self.assertRaises(ValidationError):
            model(selected="not_a_real_type", reasoning="nope")


class ConnectorExtractionTests(unittest.TestCase):
    def test_sql_contract_yields_its_declared_mcp_server(self) -> None:
        self.assertEqual(jg._extract_connector_names_from_contract(KNOWN_CONTRACTS["sql"]), ["sql-mcp"])

    def test_contract_without_requirements_yields_empty_list(self) -> None:
        self.assertEqual(jg._extract_connector_names_from_contract(KNOWN_CONTRACTS["airflow_python"]), [])


class DraftModelTests(unittest.TestCase):
    def _sql_model(self):
        contract = KNOWN_CONTRACTS["sql"]
        return jg._build_draft_model(contract, jg._extract_connector_names_from_contract(contract))

    def test_valid_sql_draft_builds(self) -> None:
        inst = self._sql_model()(
            intent="run a query",
            job_name="nightly sql",
            selected_job_type="sql",
            config={"query": "SELECT 1"},
            params={},
        )
        self.assertEqual(inst.selected_job_type, "sql")
        # Optional top-level fields default to None so exclude_none drops them.
        self.assertIsNone(inst.environment)
        self.assertIsNone(inst.selected_connectors)

    def test_selected_job_type_is_pinned_to_the_contract(self) -> None:
        with self.assertRaises(ValidationError):
            self._sql_model()(
                intent="i", job_name="n", selected_job_type="mcp",
                config={"query": "SELECT 1"}, params={},
            )

    def test_connectors_are_constrained_to_the_approved_list(self) -> None:
        model = self._sql_model()
        # Approved name validates.
        ok = model(intent="i", job_name="n", selected_job_type="sql",
                   config={"query": "SELECT 1"}, params={}, selected_connectors=["sql-mcp"])
        self.assertEqual(ok.selected_connectors, ["sql-mcp"])
        # An unapproved name does not.
        with self.assertRaises(ValidationError):
            model(intent="i", job_name="n", selected_job_type="sql",
                  config={"query": "SELECT 1"}, params={}, selected_connectors=["rogue-mcp"])

    def test_required_config_field_is_enforced(self) -> None:
        with self.assertRaises(ValidationError):
            self._sql_model()(
                intent="i", job_name="n", selected_job_type="sql",
                config={}, params={},  # sql config requires "query"
            )

    def test_contract_without_connectors_accepts_freeform_list(self) -> None:
        contract = KNOWN_CONTRACTS["airflow_python"]
        model = jg._build_draft_model(contract, [])
        inst = model(
            intent="i", job_name="n", selected_job_type="airflow_python",
            config={}, params={}, selected_connectors=["anything-goes"],
        )
        self.assertEqual(inst.selected_connectors, ["anything-goes"])


class _FakeInstructorClient:
    """Stands in for an Instructor async client: returns a validated instance of
    whatever `response_model` the orchestrator built."""

    def __init__(self, values: dict) -> None:
        self._values = values

    async def create(self, *, response_model, messages, max_retries=2, **_):
        return response_model(**self._values)


class GenerateJobDraftOrchestrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_intent_must_be_non_empty(self) -> None:
        with self.assertRaises(ValueError):
            await jg.generate_job_draft_from_intent(intent="   ")

    async def test_end_to_end_shapes_a_patch_dict_with_meta(self) -> None:
        draft_values = {
            "intent": "pull sales and summarize",
            "job_name": "daily sales",
            "selected_job_type": "sql",
            "config": {"query": "SELECT * FROM sales"},
            "params": {},
        }
        with mock.patch.object(
            jg, "select_job_type",
            mock.AsyncMock(return_value=("sql", "intent maps to a SQL query")),
        ), mock.patch.object(
            jg, "_async_instructor_client",
            return_value=_FakeInstructorClient(draft_values),
        ):
            patch = await jg.generate_job_draft_from_intent(intent="pull sales and summarize")

        # Load-bearing spine is present and correctly typed.
        self.assertEqual(patch["selected_job_type"], "sql")
        self.assertEqual(patch["job_name"], "daily sales")
        self.assertEqual(patch["config"]["query"], "SELECT * FROM sales")
        # Contract defaults survive the dump (db_driver/timezone), None fields drop.
        self.assertEqual(patch["config"].get("db_driver"), "postgresql")
        self.assertNotIn("database", patch["config"])  # None → excluded
        self.assertEqual(patch["params"].get("port"), 5432)  # spec default
        self.assertNotIn("password", patch["params"])  # None → excluded, no secret invented
        # Meta carries the JobType reasoning for the UI toast.
        self.assertEqual(patch["meta"], {"job_type_reasoning": "intent maps to a SQL query", "job_type": "sql"})

    async def test_unknown_selected_type_from_step_one_raises(self) -> None:
        # If step 1 ever returns a type with no contract, step 2 must fail loudly
        # rather than build a draft against a missing schema.
        with mock.patch.object(
            jg, "select_job_type",
            mock.AsyncMock(return_value=("ghost_type", "hallucinated")),
        ):
            with self.assertRaises(RuntimeError):
                await jg.generate_job_draft_from_intent(intent="do something")


if __name__ == "__main__":
    unittest.main()
