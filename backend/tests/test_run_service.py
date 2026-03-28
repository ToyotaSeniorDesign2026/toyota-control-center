from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.services.run_service import _successful_completion_status, retry_run


class RetryRunTests(unittest.TestCase):
    def test_successful_completion_status_uses_succeeded_for_mcp_runtime_jobs(self) -> None:
        self.assertEqual(_successful_completion_status("runtime", "mcp", "research"), "succeeded")
        self.assertEqual(_successful_completion_status("runtime", "native", "sql"), "succeeded")
        self.assertEqual(_successful_completion_status("runtime", "native", "agent"), "running")
        self.assertEqual(_successful_completion_status("artifact", "mcp", "report"), "deployed")

    def test_retry_run_reuses_stored_execution_config(self) -> None:
        run = SimpleNamespace(
            id="run_1",
            resource_id="res_123",
            action="run",
            target_environment="dev",
            requested_by="u_analyst",
            domain="collections",
            submitted_config_json={
                "action": "run",
                "target_environment": "prod",
                "params": {"topic": "rag"},
                "job_config": {
                    "intent": "research_summary",
                    "schedule": None,
                    "tasks": ["search_papers"],
                    "metadata": {"source": "retry"},
                },
                "mcp_config": {
                    "server_names": ["arxiv-research"],
                    "tool_name": "search_papers",
                    "tool_arguments": {"max_results": 3},
                    "prompt": None,
                    "connector_selection_prompt": None,
                    "allow_auto_selection": False,
                },
            },
        )
        db = SimpleNamespace(get=lambda model, run_id: run)
        user = SimpleNamespace(role="user", id="u_analyst", domain="collections")

        with patch("app.services.run_service.append_run_log"), patch(
            "app.services.run_service.write_audit"
        ), patch("app.services.run_service.create_run_and_maybe_execute") as create_run:
            create_run.return_value = {"id": "run_retry"}

            result = retry_run(db, user, "run_1")

        payload = create_run.call_args.args[2]
        self.assertEqual(payload.resource_id, "res_123")
        self.assertEqual(payload.target_environment, "prod")
        self.assertEqual(payload.params, {"topic": "rag"})
        self.assertEqual(payload.job_config.intent, "research_summary")
        self.assertEqual(payload.mcp_config.server_names, ["arxiv-research"])
        self.assertEqual(payload.mcp_config.tool_name, "search_papers")
        self.assertEqual(result, {"id": "run_retry"})


if __name__ == "__main__":
    unittest.main()
