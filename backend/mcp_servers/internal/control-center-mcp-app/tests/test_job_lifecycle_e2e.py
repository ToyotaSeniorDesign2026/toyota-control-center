"""End-to-end job creation and run triggering through the MCP tool surface.

The only mocked seam is the Control Center HTTP API (``utils.api_get`` /
``utils.api_post``) — the genuine external dependency. Everything else runs for
real: input validation, contract-driven coercion, body assembly. We assert the
*request* the tool builds (its actual contract with the backend) and that the
backend's response is forwarded unchanged.
"""

from __future__ import annotations

import unittest

from _harness import (
    FakeBackend,
    first_text,
    job_out,
    mcp_client,
    patched_backend,
    run_out,
    structured,
)


class CreateJobValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_name_is_rejected_before_any_http(self) -> None:
        fake = FakeBackend()  # no routes: a real POST would raise
        with patched_backend(fake):
            async with mcp_client() as client:
                res = await client.call_tool(
                    "create_job", {"name": "  ", "type": "sql", "connector": "sql-mcp"},
                    raise_on_error=False,
                )
                self.assertTrue(res.is_error)
                self.assertIn("name", first_text(res).lower())
        self.assertFalse(fake.called("POST", "/jobs"), "create must not POST on a validation failure")

    async def test_missing_type_is_rejected(self) -> None:
        with patched_backend(FakeBackend()):
            async with mcp_client() as client:
                res = await client.call_tool(
                    "create_job", {"name": "Job", "type": "", "connector": "sql-mcp"},
                    raise_on_error=False,
                )
                self.assertTrue(res.is_error)
                self.assertIn("type", first_text(res).lower())

    async def test_missing_connector_is_rejected(self) -> None:
        with patched_backend(FakeBackend()):
            async with mcp_client() as client:
                res = await client.call_tool(
                    "create_job", {"name": "Job", "type": "sql", "connector": ""},
                    raise_on_error=False,
                )
                self.assertTrue(res.is_error)
                self.assertIn("connector", first_text(res).lower())


class CreateJobBodyTests(unittest.IsolatedAsyncioTestCase):
    async def test_builds_normalized_body_and_forwards_response(self) -> None:
        fake = FakeBackend().on_post("/jobs", lambda body: job_out(id="job_new_42", **{
            k: body[k] for k in ("name", "type", "connector", "environment", "data_sensitivity", "config", "tags")
        }))
        with patched_backend(fake):
            async with mcp_client() as client:
                res = await client.call_tool(
                    "create_job",
                    {
                        "name": "  Nightly ETL  ",
                        "type": "SQL",                # normalized to "sql"
                        "connector": "  sql-mcp  ",
                        "environment": "PROD",        # lowercased
                        "data_sensitivity": "medium",
                        "tags": ["reporting"],
                        "tags_text": "finance, reporting",  # merged + de-duped + sorted
                        "config": {"database": "analytics", "db_driver": "postgres"},
                    },
                )
                result = structured(res)

            body = fake.last_body("POST", "/jobs")
            self.assertEqual(body["name"], "Nightly ETL")
            self.assertEqual(body["type"], "sql")
            self.assertEqual(body["connector"], "sql-mcp")
            self.assertEqual(body["environment"], "prod")
            self.assertEqual(body["data_sensitivity"], "medium")
            self.assertEqual(body["tags"], ["finance", "reporting"])
            self.assertEqual(body["config"]["database"], "analytics")
            self.assertEqual(body["config"]["db_driver"], "postgres")
            # Backend response is forwarded verbatim.
            self.assertEqual(result["id"], "job_new_42")

    async def test_config_is_coerced_through_the_contract(self) -> None:
        # sql.params has no int field, but the create path drops empty values and
        # forwards unknown keys — verify both, since the model often over-sends.
        fake = FakeBackend().on_post("/jobs", lambda body: job_out(config=body["config"]))
        with patched_backend(fake):
            async with mcp_client() as client:
                await client.call_tool(
                    "create_job",
                    {
                        "name": "Job",
                        "type": "sql",
                        "connector": "sql-mcp",
                        "config": {"database": "analytics", "timezone": "", "extra_note": "keep"},
                    },
                )
            config = fake.last_body("POST", "/jobs")["config"]
            self.assertEqual(config.get("database"), "analytics")
            self.assertNotIn("timezone", config, "empty values must be dropped")
            self.assertEqual(config.get("extra_note"), "keep", "unknown keys must be preserved")


class TriggerRunTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_job_id_is_rejected(self) -> None:
        with patched_backend(FakeBackend()):
            async with mcp_client() as client:
                res = await client.call_tool("trigger_run", {"job_id": ""}, raise_on_error=False)
                self.assertTrue(res.is_error)
                self.assertIn("job_id", first_text(res).lower())

    async def test_coerces_params_via_looked_up_job_type(self) -> None:
        fake = (
            FakeBackend()
            .on_get("/jobs/job1", job_out(id="job1", type="sql"))
            .on_post("/jobs/job1/runs", lambda body: run_out(job_id="job1", **{
                "action": body["action"], "target_environment": body["target_environment"]
            }))
        )
        with patched_backend(fake):
            async with mcp_client() as client:
                res = await client.call_tool(
                    "trigger_run",
                    {
                        "job_id": "job1",
                        "params": {"port": "5432", "host": "db.internal"},  # port coerced to int
                        "prompt": "  run it now  ",
                    },
                )
                result = structured(res)

            body = fake.last_body("POST", "/jobs/job1/runs")
            self.assertEqual(body["action"], "run")                 # default
            self.assertEqual(body["target_environment"], "dev")     # default
            self.assertEqual(body["params"]["port"], 5432)          # int, not "5432"
            self.assertIsInstance(body["params"]["port"], int)
            self.assertEqual(body["params"]["host"], "db.internal")
            self.assertEqual(body["prompt"], "run it now")          # trimmed
            self.assertEqual(result["job_id"], "job1")

    async def test_empty_target_environment_is_rejected(self) -> None:
        fake = FakeBackend().on_get("/jobs/job1", job_out(id="job1", type="sql"))
        with patched_backend(fake):
            async with mcp_client() as client:
                res = await client.call_tool(
                    "trigger_run", {"job_id": "job1", "target_environment": ""},
                    raise_on_error=False,
                )
                self.assertTrue(res.is_error)
                self.assertIn("environment", first_text(res).lower())
        self.assertFalse(fake.called("POST", "/jobs/job1/runs"))


if __name__ == "__main__":
    unittest.main()
