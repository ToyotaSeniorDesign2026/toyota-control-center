from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.schemas.run import MCPExecutionConfig, MCPJobConfig, RunCreate
from app.services.connector_service import dispatch_execution
from app.services.execution_service import build_execution_request, build_job_spec, resolve_effective_mcp_config


class MCPJobServiceTests(unittest.TestCase):
    def test_build_job_spec_merges_resource_payload_and_mcp_config(self) -> None:
        resource = SimpleNamespace(
            id="res_123",
            name="research-job",
            type="research",
            connector="arxiv-research",
            data_sensitivity="medium",
            kind="runtime",
            environment="dev",
            config={},
            tags=[],
            owner_id="u_analyst",
            owner_domain="collections",
        )
        payload = RunCreate(
            resource_id="res_123",
            action="run",
            target_environment="prod",
            params={"topic": "rag evaluation"},
            job_config=MCPJobConfig(
                intent="research_summary",
                tasks=["search_papers"],
                metadata={"team": "ai-governance"},
            ),
            mcp_config=MCPExecutionConfig(
                server_names=["arxiv-research"],
                tool_name="search_papers",
                tool_arguments={"max_results": 3},
            ),
        )

        spec = build_job_spec(resource, payload)

        self.assertEqual(spec["intent"], "research_summary")
        self.assertEqual(spec["environment"], "prod")
        self.assertIn("pii", spec["risk_score_input"])
        self.assertIn("prod", spec["risk_score_input"])
        self.assertEqual(spec["tasks"], ["search_papers"])
        self.assertEqual(spec["metadata"]["resource_id"], "res_123")
        self.assertEqual(spec["metadata"]["params"]["topic"], "rag evaluation")
        self.assertEqual(spec["metadata"]["mcp_config"]["tool_name"], "search_papers")
        self.assertEqual(spec["metadata"]["team"], "ai-governance")

    def test_build_execution_request_resolves_mcp_boundary(self) -> None:
        resource = SimpleNamespace(
            id="res_123",
            name="research-job",
            type="research",
            connector="arxiv-research",
            data_sensitivity="low",
            kind="runtime",
            environment="dev",
            config={"topic": "retrieval augmented generation evaluation", "max_results": 4},
            tags=["demo"],
            owner_id="u_analyst",
            owner_domain="collections",
        )
        payload = RunCreate(
            resource_id="res_123",
            target_environment="dev",
            params={},
        )

        execution_request = build_execution_request(
            run_id="run_1",
            resource=resource,
            payload=payload,
            trigger_source="api",
        )

        self.assertEqual(execution_request.execution_backend, "mcp")
        self.assertEqual(execution_request.execution_mode, "direct_tool")
        self.assertEqual(execution_request.mcp_config.tool_name, "search_papers")
        self.assertEqual(execution_request.job_spec["metadata"]["resource_id"], "res_123")

    def test_every_execution_request_routes_through_mcp(self) -> None:
        execution_request = build_execution_request(
            run_id="run_1",
            resource=SimpleNamespace(
                id="res_123",
                name="research-job",
                type="research",
                connector="arxiv-research",
                data_sensitivity="low",
                kind="runtime",
                environment="dev",
                config={"topic": "retrieval augmented generation evaluation"},
                tags=[],
                owner_id="u_analyst",
                owner_domain="collections",
            ),
            payload=RunCreate(resource_id="res_123", target_environment="dev"),
            trigger_source="api",
        )

        self.assertEqual(execution_request.execution_backend, "mcp")

    def test_sql_resource_can_route_through_sql_mcp_server(self) -> None:
        execution_request = build_execution_request(
            run_id="run_sql_mcp",
            resource=SimpleNamespace(
                id="res_sql_mcp",
                name="sql-mcp-job",
                type="sql",
                connector="sql-dab",
                data_sensitivity="low",
                kind="runtime",
                environment="dev",
                config={"connection_id": "sql-dab"},
                tags=[],
                owner_id="u_analyst",
                owner_domain="collections",
            ),
            payload=RunCreate(
                resource_id="res_sql_mcp",
                target_environment="dev",
                params={"prompt": "Show me the latest open orders."},
                mcp_config=MCPExecutionConfig(
                    server_names=["sql-dab"],
                    prompt="Show me the latest open orders.",
                    allow_auto_selection=True,
                ),
            ),
            trigger_source="api",
        )

        self.assertEqual(execution_request.execution_backend, "mcp")
        self.assertEqual(execution_request.execution_mode, "agent")
        self.assertEqual(execution_request.mcp_config.server_names, ["sql-dab"])

    def test_dispatch_execution_uses_registered_executor(self) -> None:
        execution_request = build_execution_request(
            run_id="run_1",
            resource=SimpleNamespace(
                id="res_123",
                name="research-job",
                type="research",
                connector="arxiv-research",
                data_sensitivity="low",
                kind="runtime",
                environment="dev",
                config={"topic": "retrieval augmented generation evaluation"},
                tags=[],
                owner_id="u_analyst",
                owner_domain="collections",
            ),
            payload=RunCreate(resource_id="res_123", target_environment="dev"),
            trigger_source="api",
        )

        with patch("app.services.connector_service._EXECUTOR.execute") as execute:
            execute.return_value = {
                "connector_run_id": "mcp_1",
                "status": "succeeded",
                "duration_ms": 5,
                "metadata": {"ok": True},
                "error": None,
            }

            result = dispatch_execution(execution_request)

        execute.assert_called_once_with(execution_request)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["metadata"], {"ok": True})

    def test_research_resource_defaults_to_search_papers_tool(self) -> None:
        resource = SimpleNamespace(
            id="res_123",
            name="research-job",
            type="research",
            connector="arxiv-research",
            config={"topic": "retrieval augmented generation evaluation", "max_results": 4},
            data_sensitivity="low",
        )
        payload = RunCreate(
            resource_id="res_123",
            target_environment="dev",
            params={},
            mcp_config=None,
        )

        effective = resolve_effective_mcp_config(resource, payload)

        self.assertEqual(effective.server_names, ["arxiv-research"])
        self.assertEqual(effective.tool_name, "search_papers")
        self.assertEqual(effective.tool_arguments["topic"], "retrieval augmented generation evaluation")
        self.assertEqual(effective.tool_arguments["max_results"], 4)


if __name__ == "__main__":
    unittest.main()
