"""Base MCP protocol conformance for the Job Designer server.

Verified against the Model Context Protocol schema (``mcp-schema.mdx`` in this
folder). These tests assert the server speaks valid MCP — independent of the
MCP Apps extension (covered in ``test_mcp_apps_conformance.py``).

Everything runs through a real in-memory FastMCP client; nothing here is mocked.
"""

from __future__ import annotations

import unittest

from jsonschema import Draft202012Validator

import server as server_module
from _harness import mcp_client, tool_map

# The tools this server intends to expose to a host. ``request_approval`` is
# contributed by the FastMCP Approval provider, not declared in build_server.
EXPECTED_TOOLS = {
    "open_job_designer",
    "list_job_types",
    "get_form_schema",
    "list_connectors",
    "capture_current_draft",
    "get_draft_snapshot",
    "patch_draft_snapshot",
    "generate_full_job_draft",
    "get_current_draft_ui_state",
    "preview_ai_suggested_changes",
    "create_job",
    "trigger_run",
    "show_connector_risk_profile",
}


class InitializeHandshakeTests(unittest.IsolatedAsyncioTestCase):
    async def test_server_info_advertises_canonical_name(self) -> None:
        async with mcp_client() as client:
            info = client.initialize_result
            self.assertEqual(info.serverInfo.name, server_module.SERVER_NAME)

    async def test_server_advertises_instructions_and_capabilities(self) -> None:
        async with mcp_client() as client:
            info = client.initialize_result
            # SERVER_DESCRIPTION is surfaced as MCP `instructions`.
            self.assertTrue(info.instructions)
            self.assertIsNotNone(info.capabilities.tools)
            self.assertIsNotNone(info.capabilities.resources)

    async def test_ping_roundtrips(self) -> None:
        async with mcp_client() as client:
            await client.ping()  # raises if the transport/handshake is broken


class ToolListConformanceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._client = mcp_client()
        await self._client.__aenter__()
        self.tools = await self._client.list_tools()

    async def asyncTearDown(self) -> None:
        await self._client.__aexit__(None, None, None)

    async def test_all_expected_tools_present(self) -> None:
        names = set(tool_map(self.tools))
        missing = EXPECTED_TOOLS - names
        self.assertEqual(missing, set(), f"server is missing tools: {sorted(missing)}")

    async def test_tool_names_are_unique(self) -> None:
        names = [t.name for t in self.tools]
        dupes = {n for n in names if names.count(n) > 1}
        self.assertEqual(dupes, set(), f"duplicate tool names: {sorted(dupes)}")

    async def test_every_tool_has_name_and_description(self) -> None:
        for tool in self.tools:
            self.assertTrue(tool.name, "tool with empty name")
            self.assertTrue(
                (tool.description or "").strip(),
                f"tool {tool.name!r} has no description (MCP: description is how the model picks tools)",
            )

    async def test_input_schemas_are_valid_json_schema_objects(self) -> None:
        # MCP requires inputSchema to be a JSON Schema object describing tool args.
        for tool in self.tools:
            schema = tool.inputSchema
            self.assertIsInstance(schema, dict, f"{tool.name}: inputSchema not an object")
            self.assertEqual(
                schema.get("type"),
                "object",
                f"{tool.name}: inputSchema.type must be 'object'",
            )
            # The schema must itself be a legal JSON Schema (draft 2020-12).
            Draft202012Validator.check_schema(schema)

    async def test_output_schemas_when_present_are_object_schemas(self) -> None:
        for tool in self.tools:
            schema = tool.outputSchema
            if schema is None:
                continue
            self.assertIsInstance(schema, dict, f"{tool.name}: outputSchema not an object")
            self.assertEqual(schema.get("type"), "object", f"{tool.name}: outputSchema.type")
            Draft202012Validator.check_schema(schema)


class ResourceListConformanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_resources_have_uri_name_and_mimetype(self) -> None:
        async with mcp_client() as client:
            resources = await client.list_resources()
            self.assertTrue(resources, "server exposes no resources")
            for res in resources:
                self.assertTrue(str(res.uri), "resource with empty uri")
                self.assertTrue(res.name, f"resource {res.uri} has no name")
                self.assertTrue(res.mimeType, f"resource {res.uri} has no mimeType")


if __name__ == "__main__":
    unittest.main()
