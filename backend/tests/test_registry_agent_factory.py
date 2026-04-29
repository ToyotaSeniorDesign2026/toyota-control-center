from __future__ import annotations

from contextlib import redirect_stdout
import io
import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from control_center.core.specs import BoundCapability
from control_center.core.registry import RegistryManager
from control_center.mcp import (
    MCPAgent,
    build_agent_from_registry,
    build_connector_selection_model,
    default_mcp_model,
    make_adapter_for_model,
    select_registry_connectors,
)
from control_center.mcp.adapters.base import BaseAdapter
from control_center.mcp.adapters.google import GoogleAdapter
from control_center.mcp.adapters.openai import OpenAIAdapter
from control_center.mcp.client import BaseClient
from control_center.mcp.models import ModelTurnResult, RequestedToolCall


class FakeClient(BaseClient):
    def __init__(self) -> None:
        self.connected: dict[str, dict[str, Any]] = {}

    @property
    def connected_servers(self) -> list[str]:
        return sorted(self.connected.keys())

    async def connect_to_server(self, server_name: str, server_config: dict[str, Any]) -> None:
        self.connected[server_name] = dict(server_config)

    async def disconnect_server(self, server_name: str) -> None:
        self.connected.pop(server_name, None)

    async def list_tools(self, server_name: str) -> list[Any]:
        return []

    async def list_prompts(self, server_name: str) -> list[Any]:
        return []

    async def list_resources(self, server_name: str) -> list[Any]:
        return []

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict[str, Any]) -> Any:
        raise NotImplementedError

    async def get_prompt(self, server_name: str, prompt_name: str, arguments: dict[str, Any]) -> Any:
        raise NotImplementedError

    async def read_resource(self, server_name: str, resource_uri: str) -> Any:
        raise NotImplementedError

    async def cleanup(self) -> None:
        return None


class FakeAdapter(BaseAdapter[dict[str, Any]]):
    def _convert_tool(self, mcp_tool: Any, client: BaseClient, server_name: str) -> dict[str, Any] | None:
        del mcp_tool, client, server_name
        return None

    def _convert_resource(self, mcp_resource: Any, client: BaseClient, server_name: str) -> dict[str, Any] | None:
        del mcp_resource, client, server_name
        return None

    def _convert_prompt(self, mcp_prompt: Any, client: BaseClient, server_name: str) -> dict[str, Any] | None:
        del mcp_prompt, client, server_name
        return None


class VerboseAdapter(BaseAdapter[dict[str, Any]]):
    async def create_all(self, client: BaseClient) -> None:
        del client
        self.clear_cache()
        self.tools = [{"name": "filesystem_list", "description": "List files", "parameters": {"type": "object"}}]
        self._register_binding(
            BoundCapability(
                framework_name="filesystem_list",
                server_name="filesystem",
                remote_name="list",
                kind="tool",
                description="List files",
            )
        )

    async def invoke(self, client: BaseClient, framework_name: str, arguments: dict[str, Any]) -> Any:
        del client, framework_name
        return {"content": [{"text": f"Listed {arguments['path']}"}]}

    def parse_result(self, result: Any) -> str:
        return result["content"][0]["text"]

    def _convert_tool(self, mcp_tool: Any, client: BaseClient, server_name: str) -> dict[str, Any] | None:
        del mcp_tool, client, server_name
        return None

    def _convert_resource(self, mcp_resource: Any, client: BaseClient, server_name: str) -> dict[str, Any] | None:
        del mcp_resource, client, server_name
        return None

    def _convert_prompt(self, mcp_prompt: Any, client: BaseClient, server_name: str) -> dict[str, Any] | None:
        del mcp_prompt, client, server_name
        return None


class VerboseModel:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(
        self,
        *,
        message: str,
        tools: list[Any],
        tool_results: list[dict[str, Any]] | None = None,
    ) -> ModelTurnResult:
        del message, tools
        self.calls += 1
        if self.calls == 1:
            return ModelTurnResult(
                text="I should inspect the docs directory first.",
                tool_calls=[
                    RequestedToolCall(
                        name="filesystem_list",
                        arguments={"path": "/tmp"},
                    )
                ],
            )
        return ModelTurnResult(
            text=f"Done. Tool results: {tool_results[0]['result']}",
            tool_calls=[],
        )


class FakeInstructorClient:
    def __init__(self, selected_connectors: list[str], decision_reasoning: str) -> None:
        self.selected_connectors = selected_connectors
        self.decision_reasoning = decision_reasoning
        self.calls: list[dict[str, Any]] = []

    def create(self, *, response_model: Any, messages: list[dict[str, str]], max_retries: int) -> Any:
        self.calls.append(
            {
                "response_model": response_model,
                "messages": messages,
                "max_retries": max_retries,
            }
        )
        connector_enum = response_model.model_fields["connectors"].annotation.__args__[0]
        return response_model(
            connectors=[connector_enum(name) for name in self.selected_connectors],
            decision_reasoning=self.decision_reasoning,
        )


class RegistryManagerTests(unittest.TestCase):
    def test_filesystem_server_config_applies_environment_overrides(self) -> None:
        manager = RegistryManager(environment="dev")

        config = manager.get_server_config("filesystem")

        self.assertEqual(config["command"], "npx")
        self.assertEqual(config["args"], ["-y", "--quiet", "@modelcontextprotocol/server-filesystem", "."])
        self.assertEqual(config["timeout"], 60)
        self.assertNotIn("cwd", config)

    def test_internal_script_server_config_sets_cwd(self) -> None:
        manager = RegistryManager(environment="dev")

        config = manager.get_server_config("fastmcp-docs")

        self.assertEqual(
            config["cwd"],
            str(manager._get_mcp_servers_dir()),
        )
        self.assertEqual(
            config["args"],
            ["run", "--with", "fastmcp", "internal/fastmcp-docs/fastmcp_docs.py"],
        )

    def test_server_bundle_uses_mcp_servers_shape(self) -> None:
        manager = RegistryManager(environment="dev")

        bundle = manager.get_server_bundle(["filesystem", "fetch"])

        self.assertEqual(sorted(bundle.keys()), ["mcpServers"])
        self.assertEqual(sorted(bundle["mcpServers"].keys()), ["fetch", "filesystem"])

    def test_google_adapter_strips_provider_incompatible_schema_keys(self) -> None:
        adapter = GoogleAdapter()
        tool = SimpleNamespace(
            name="list_files",
            description="List files",
            inputSchema={
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "recursive": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
        )

        declaration = adapter._convert_tool(tool, client=None, server_name="filesystem")

        self.assertIsNotNone(declaration)
        parameters = declaration["parameters"]
        self.assertNotIn("$schema", parameters)
        self.assertNotIn("additionalProperties", parameters)
        self.assertEqual(parameters["type"], "object")
        self.assertEqual(sorted(parameters["properties"].keys()), ["path", "recursive"])

    def test_openai_adapter_converts_mcp_tools_to_function_tools(self) -> None:
        adapter = OpenAIAdapter()
        tool = SimpleNamespace(
            name="list_files",
            description="List files",
            inputSchema={
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "recursive": {"type": "boolean"},
                },
            },
        )

        declaration = adapter._convert_tool(tool, client=None, server_name="filesystem")

        self.assertIsNotNone(declaration)
        self.assertEqual(declaration["type"], "function")
        function = declaration["function"]
        self.assertEqual(function["name"], "filesystem_list_files")
        self.assertEqual(function["description"], "List files")
        self.assertNotIn("$schema", function["parameters"])
        self.assertEqual(sorted(function["parameters"]["properties"].keys()), ["path", "recursive"])

    def test_mcp_provider_defaults_to_openai_model(self) -> None:
        with patch.dict("os.environ", {"OPENAI_MODEL": "gpt-4o-mini"}, clear=False):
            self.assertEqual(default_mcp_model(), "gpt-4o-mini")
            self.assertIsInstance(make_adapter_for_model(default_mcp_model()), OpenAIAdapter)
            self.assertIsInstance(make_adapter_for_model("gemini-3.1-pro-preview"), GoogleAdapter)

    def test_connector_selection_model_uses_dynamic_connector_enum(self) -> None:
        selection_model = build_connector_selection_model(["filesystem", "fastmcp-docs"])

        connector_enum = selection_model.model_fields["connectors"].annotation.__args__[0]
        self.assertEqual(sorted(member.value for member in connector_enum), ["fastmcp-docs", "filesystem"])
        instance = selection_model(
            connectors=[connector_enum("filesystem")],
            decision_reasoning="Needs local file access.",
        )
        self.assertEqual([item.value for item in instance.connectors], ["filesystem"])
        self.assertEqual(instance.decision_reasoning, "Needs local file access.")

        parsed = selection_model.model_validate(
            {
                "connectors": ["fastmcp-docs"],
                "decision_reasoning": "Docs are required.",
            }
        )
        self.assertEqual([item.value for item in parsed.connectors], ["fastmcp-docs"])


class RegistryAgentFactoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_build_agent_from_registry_uses_resolved_server_configs(self) -> None:
        fake_client = FakeClient()
        fake_adapter = FakeAdapter()

        agent = await build_agent_from_registry(
            environment="dev",
            server_names=["filesystem", "fastmcp-docs"],
            client=fake_client,
            adapter=fake_adapter,
            model="test-model",
        )

        self.assertIsInstance(agent, MCPAgent)
        self.assertIs(agent.client, fake_client)
        self.assertIs(agent.adapter, fake_adapter)
        self.assertEqual(sorted(fake_client.connected_servers), ["fastmcp-docs", "filesystem"])
        self.assertEqual(fake_client.connected["filesystem"]["command"], "npx")
        self.assertEqual(
            fake_client.connected["fastmcp-docs"]["cwd"],
            str(RegistryManager(environment="dev")._get_mcp_servers_dir()),
        )

    async def test_select_registry_connectors_uses_dynamic_model_and_returns_reasoning(self) -> None:
        fake_instructor = FakeInstructorClient(
            selected_connectors=["filesystem", "fetch"],
            decision_reasoning="The request needs local files and web retrieval.",
        )

        connectors, reasoning = await select_registry_connectors(
            prompt="Look through local docs and fetch remote pages if needed.",
            environment="dev",
            instructor_client=fake_instructor,
        )

        self.assertEqual(connectors, ["filesystem", "fetch"])
        self.assertEqual(reasoning, "The request needs local files and web retrieval.")
        self.assertEqual(len(fake_instructor.calls), 1)

    async def test_build_agent_from_registry_can_select_servers_from_prompt(self) -> None:
        fake_client = FakeClient()
        fake_adapter = FakeAdapter()
        fake_instructor = FakeInstructorClient(
            selected_connectors=["filesystem"],
            decision_reasoning="Only filesystem is required.",
        )

        agent = await build_agent_from_registry(
            environment="dev",
            selection_prompt="Read local project files and summarize them.",
            client=fake_client,
            adapter=fake_adapter,
            instructor_client=fake_instructor,
            model="test-model",
        )

        self.assertIsInstance(agent, MCPAgent)
        self.assertEqual(fake_client.connected_servers, ["filesystem"])


class MCPAgentVerboseTests(unittest.IsolatedAsyncioTestCase):
    async def test_verbose_mode_prints_model_and_tool_activity(self) -> None:
        agent = MCPAgent(
            client=FakeClient(),
            adapter=VerboseAdapter(),
            model=VerboseModel(),
            max_tool_rounds=3,
            verbose=True,
        )

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            response = await agent.run("Inspect /tmp")

        output = stdout.getvalue()
        self.assertIn("(Round 1/3)", output)
        self.assertIn("(Model output: I should inspect the docs directory first.)", output)
        self.assertIn('(Calling filesystem_list with {"path": "/tmp"})', output)
        self.assertIn("(Tool result from filesystem_list: Listed /tmp)", output)
        self.assertIn("(Round 2/3)", output)
        self.assertIn("Done. Tool results: Listed /tmp", response.final_text)


if __name__ == "__main__":
    unittest.main()
