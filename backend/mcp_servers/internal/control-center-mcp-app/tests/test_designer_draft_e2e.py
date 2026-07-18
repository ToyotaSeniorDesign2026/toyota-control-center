"""End-to-end draft authoring flows through the real MCP tool surface.

These exercise the contract-driven form + draft state machine entirely offline:
the three built-in JobType contracts (``sql``, ``mcp``, ``airflow_python``)
resolve from ``KNOWN_CONTRACTS`` without any backend call. The backend is faked
as *down* (no routes) only to make the graceful-degradation paths deterministic
rather than dependent on a real refused connection.
"""

from __future__ import annotations

import unittest

from _harness import (
    FakeBackend,
    first_text,
    mcp_client,
    patched_backend,
    structured,
)


class OpenDesignerTests(unittest.IsolatedAsyncioTestCase):
    async def test_open_with_reset_normalizes_type_and_environment(self) -> None:
        async with mcp_client() as client:
            res = await client.call_tool(
                "open_job_designer",
                {"job_type": "SQL", "environment": "PROD", "reset": True},
            )
            data = structured(res)
            self.assertEqual(data["status"], "opened")
            self.assertEqual(data["selectedJobType"], "sql")
            self.assertEqual(data["environment"], "prod")

    async def test_second_open_reattaches_and_preserves_work_in_progress(self) -> None:
        async with mcp_client() as client:
            await client.call_tool("open_job_designer", {"job_type": "sql", "reset": True})
            await client.call_tool("patch_draft_snapshot", {"patch": {"job_name": "Nightly ETL"}})

            # Idempotent re-open (e.g. another tab) must not clobber the draft.
            res = await client.call_tool("open_job_designer", {})
            self.assertEqual(structured(res)["status"], "reattached")

            snap = structured(await client.call_tool("get_draft_snapshot", {}))
            self.assertEqual(snap["draft"]["job_name"], "Nightly ETL")

    async def test_reset_clears_work_in_progress(self) -> None:
        async with mcp_client() as client:
            await client.call_tool("open_job_designer", {"job_type": "sql", "reset": True})
            await client.call_tool("patch_draft_snapshot", {"patch": {"job_name": "Nightly ETL"}})

            res = await client.call_tool("open_job_designer", {"reset": True})
            self.assertEqual(structured(res)["status"], "opened")

            snap = structured(await client.call_tool("get_draft_snapshot", {}))
            self.assertEqual(snap["draft"]["job_name"], "")
            self.assertEqual(snap["draft"]["selected_job_type"], "")


class FormSchemaTests(unittest.IsolatedAsyncioTestCase):
    async def test_known_contracts_resolve_offline(self) -> None:
        expected_connector_types = {
            "sql": ["sql-mcp"],
            "airflow_python": [],
        }
        async with mcp_client() as client:
            for job_type, connector_types in expected_connector_types.items():
                res = await client.call_tool("get_form_schema", {"job_type": job_type})
                schema = structured(res)
                self.assertEqual(schema["type"], job_type)
                self.assertEqual(schema["connector_types"], connector_types)
                # Field specs are present and required-annotated. Assert the flag
                # VALUE agrees with `required_config` — not just that the key
                # exists — so a regression that mislabels required-ness is caught.
                self.assertTrue(schema["config_fields"], f"{job_type}: no config_fields")
                required_config = set(schema["required_config"])
                for field in schema["config_fields"]:
                    self.assertIn("required", field)
                    self.assertEqual(
                        field["required"],
                        field["name"] in required_config,
                        f"{job_type}.{field['name']}: 'required' flag disagrees with required_config",
                    )
            # Non-vacuous: sql actually has a required config field ('query').
            sql_schema = structured(await client.call_tool("get_form_schema", {"job_type": "sql"}))
            self.assertTrue(
                any(f["required"] for f in sql_schema["config_fields"]),
                "expected sql to expose at least one required config field",
            )

    async def test_empty_job_type_returns_empty_payload(self) -> None:
        async with mcp_client() as client:
            schema = structured(await client.call_tool("get_form_schema", {"job_type": ""}))
            self.assertEqual(schema["config_fields"], [])
            self.assertEqual(schema["params_fields"], [])


class PatchDraftTests(unittest.IsolatedAsyncioTestCase):
    async def test_config_patches_merge(self) -> None:
        async with mcp_client() as client:
            await client.call_tool("open_job_designer", {"job_type": "sql", "reset": True})
            await client.call_tool("patch_draft_snapshot", {"patch": {"config": {"database": "analytics"}}})
            res = await client.call_tool("patch_draft_snapshot", {"patch": {"config": {"db_driver": "postgres"}}})
            config = structured(res)["config"]
            # Second patch must not drop the first key.
            self.assertEqual(config.get("database"), "analytics")
            self.assertEqual(config.get("db_driver"), "postgres")

    async def test_replace_config_replaces_whole_object(self) -> None:
        async with mcp_client() as client:
            await client.call_tool("open_job_designer", {"job_type": "sql", "reset": True})
            await client.call_tool("patch_draft_snapshot", {"patch": {"config": {"database": "analytics"}}})
            res = await client.call_tool(
                "patch_draft_snapshot", {"patch": {"replace_config": {"database": "fresh"}}}
            )
            config = structured(res)["config"]
            self.assertEqual(config, {"database": "fresh"})

    async def test_job_type_change_reloads_schema_and_resets_available_connectors(self) -> None:
        async with mcp_client() as client:
            await client.call_tool("open_job_designer", {"job_type": "sql", "reset": True})
            await client.call_tool("patch_draft_snapshot", {"patch": {"selectedConnectors": ["primary-sql"]}})

            res = await client.call_tool("patch_draft_snapshot", {"patch": {"selected_job_type": "airflow_python"}})
            data = structured(res)
            self.assertEqual(data["formSchema"]["type"], "airflow_python")
            self.assertIn("availableConnectors", data["applied"])
            # airflow_python declares no connector types → cleared options …
            self.assertEqual(data["availableConnectors"], [])
            # … but the user's explicit selection is intentionally preserved.
            self.assertEqual(data["selectedConnectors"], ["primary-sql"])

    async def test_get_draft_snapshot_reflects_last_patch(self) -> None:
        async with mcp_client() as client:
            await client.call_tool("open_job_designer", {"job_type": "mcp", "reset": True})
            await client.call_tool("patch_draft_snapshot", {"patch": {"intent": "summarize arxiv papers"}})
            snap = structured(await client.call_tool("get_draft_snapshot", {}))
            self.assertEqual(snap["draft"]["intent"], "summarize arxiv papers")

    async def test_non_dict_patch_is_rejected(self) -> None:
        async with mcp_client() as client:
            res = await client.call_tool(
                "patch_draft_snapshot", {"patch": "not-an-object"}, raise_on_error=False
            )
            self.assertTrue(res.is_error)
            self.assertIn("object", first_text(res).lower())


class PatchFringeInputTests(unittest.IsolatedAsyncioTestCase):
    """Malformed / adversarial patch payloads the host model can realistically
    emit. These lock in the *current* contract so the behavior can't drift
    silently; where the behavior is a deliberate limitation it is called out.
    """

    async def test_null_scalar_does_not_clear_an_existing_field(self) -> None:
        # DOCUMENTED LIMITATION: `patch_value` treats a missing key and an explicit
        # null identically, so the model cannot clear a field by sending null — the
        # prior value is preserved. (To wipe a field, send "" — an empty string.)
        async with mcp_client() as client:
            await client.call_tool("open_job_designer", {"job_type": "sql", "reset": True})
            await client.call_tool("patch_draft_snapshot", {"patch": {"job_name": "Keep Me"}})
            res = structured(await client.call_tool("patch_draft_snapshot", {"patch": {"job_name": None}}))
            self.assertEqual(res["jobName"], "Keep Me")
            # An empty string, by contrast, does clear it.
            cleared = structured(await client.call_tool("patch_draft_snapshot", {"patch": {"job_name": ""}}))
            self.assertEqual(cleared["jobName"], "")

    async def test_object_for_scalar_field_is_stringified_not_crashed(self) -> None:
        # Scalars are coerced via str(); an object lands as its repr rather than
        # raising. Not ideal, but it must stay non-fatal and deterministic.
        async with mcp_client() as client:
            await client.call_tool("open_job_designer", {"job_type": "sql", "reset": True})
            res = structured(await client.call_tool("patch_draft_snapshot", {"patch": {"job_name": {"x": 1}}}))
            self.assertIsInstance(res["jobName"], str)
            self.assertIn("x", res["jobName"])

    async def test_malformed_json_container_string_errors_without_mutating_state(self) -> None:
        # A config supplied as a json-ish string that fails to parse must raise a
        # tool error — and must NOT partially mutate the stored draft.
        async with mcp_client() as client:
            await client.call_tool("open_job_designer", {"job_type": "sql", "reset": True})
            await client.call_tool("patch_draft_snapshot", {"patch": {"config": {"database": "analytics"}}})

            res = await client.call_tool(
                "patch_draft_snapshot", {"patch": {"config": "{not valid json"}}, raise_on_error=False
            )
            self.assertTrue(res.is_error)

            snap = structured(await client.call_tool("get_draft_snapshot", {}))
            self.assertEqual(snap["draft"]["config"].get("database"), "analytics")

    async def test_unknown_job_type_errors_atomically(self) -> None:
        # A job-type the server can't resolve (no contract + backend unreachable)
        # must fail the patch as a whole — the stored draft's type is unchanged,
        # never left in a half-applied state.
        with patched_backend(FakeBackend()):
            async with mcp_client() as client:
                await client.call_tool("open_job_designer", {"job_type": "sql", "reset": True})
                res = await client.call_tool(
                    "patch_draft_snapshot",
                    {"patch": {"selected_job_type": "does_not_exist"}},
                    raise_on_error=False,
                )
                self.assertTrue(res.is_error)

                snap = structured(await client.call_tool("get_draft_snapshot", {}))
                self.assertEqual(snap["draft"]["selected_job_type"], "sql")


class CaptureDraftTests(unittest.IsolatedAsyncioTestCase):
    async def test_capture_rejects_non_ui_state_payload(self) -> None:
        async with mcp_client() as client:
            res = await client.call_tool(
                "capture_current_draft",
                {"current_state": {"job_name": "oops"}},  # missing required UI keys
                raise_on_error=False,
            )
            self.assertTrue(res.is_error)
            self.assertIn("get_draft_snapshot", first_text(res))

    async def test_capture_roundtrips_real_ui_state(self) -> None:
        async with mcp_client() as client:
            await client.call_tool("open_job_designer", {"job_type": "sql", "reset": True})
            # get_current_draft_ui_state emits a real Prefab UI-state payload.
            ui_state = structured(await client.call_tool("get_current_draft_ui_state", {}))
            ui_state["jobName"] = "Captured Job"

            captured = structured(
                await client.call_tool("capture_current_draft", {"current_state": ui_state})
            )
            self.assertEqual(captured["status"], "captured")
            self.assertEqual(captured["draft"]["job_name"], "Captured Job")

            # The capture is now the authoritative snapshot.
            snap = structured(await client.call_tool("get_draft_snapshot", {}))
            self.assertEqual(snap["draft"]["job_name"], "Captured Job")


class PreviewSuggestionsTests(unittest.IsolatedAsyncioTestCase):
    async def test_preview_diffs_ui_state_against_ai_draft(self) -> None:
        async with mcp_client() as client:
            await client.call_tool("open_job_designer", {"job_type": "sql", "reset": True})
            # AI proposes a job name into the stored draft.
            await client.call_tool("patch_draft_snapshot", {"patch": {"job_name": "AI Suggested Name"}})

            # The browser form still has a different (empty) job name.
            ui_state = structured(await client.call_tool("get_current_draft_ui_state", {}))
            ui_state["jobName"] = "Human Typed Name"

            preview = structured(
                await client.call_tool("preview_ai_suggested_changes", {"current_state": ui_state})
            )
            self.assertEqual(preview["status"], "ready")
            self.assertGreater(preview["change_count"], 0)
            labels = {c["label"] for c in preview["changes"]}
            self.assertIn("Job name", labels)


class ListJobTypesFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_falls_back_to_static_contracts_when_backend_down(self) -> None:
        # No /job-types route → BackendError → must degrade to the static set.
        with patched_backend(FakeBackend()):
            async with mcp_client() as client:
                res = await client.call_tool("list_job_types", {})
                types = {item["type"] for item in structured(res)["items"]}
                self.assertTrue({"sql", "mcp", "airflow_python"}.issubset(types))


if __name__ == "__main__":
    unittest.main()
