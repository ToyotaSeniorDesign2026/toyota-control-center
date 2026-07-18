"""Conformance for the Connector Risk Profile MCP App extension.

Two layers:

* **Classification** — ``_classify_tool_risk`` buckets MCP ``ToolAnnotations``
  into risk bands. The MCP base schema (``mcp-schema.mdx``) defines the four
  hint fields and, critically, that they are advisory and may be absent. This
  server applies the spec's paranoid defaults when a hint is ``None``
  (``destructiveHint``/``openWorldHint`` ⇒ treat as true). Pure functions, no mocks.

* **Rendering** — ``show_connector_risk_profile`` is an ``app=True`` tool that
  returns a Prefab UI. The genuine external dependency is the live MCP probe
  (``_fetch_connector_tool_profile`` → connects to a connector). We fake *only*
  that probe — building a faithful profile with the real classifier/aggregator —
  and assert the tool renders a valid Prefab app for both the success and the
  unreachable-connector paths.
"""

from __future__ import annotations

import json
import unittest
from unittest import mock

import server as server_module
from _harness import mcp_client, structured

classify = server_module._classify_tool_risk
aggregate = server_module._compute_profile_aggregates


class RiskClassificationTests(unittest.TestCase):
    def test_spec_hint_defaults_are_paranoid(self) -> None:
        # MCP ToolAnnotations: unset destructive/openWorld must be assumed true.
        self.assertEqual(
            server_module._SPEC_HINT_DEFAULTS,
            {
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": True,
            },
        )

    def test_missing_annotations_is_unknown_band(self) -> None:
        result = classify(None)
        self.assertEqual(result["band"], "unknown")
        self.assertIn("unannotated", result["flags"])

    def test_empty_annotations_dict_defaults_to_high_risk(self) -> None:
        # Present-but-empty annotations ⇒ defaults apply ⇒ destructive + external.
        result = classify({})
        self.assertEqual(result["band"], "high")
        self.assertCountEqual(result["flags"], ["destructive", "external"])

    def test_pure_read_only_local_tool_is_low_risk(self) -> None:
        result = classify({"readOnlyHint": True, "openWorldHint": False})
        self.assertEqual(result["band"], "low")
        self.assertIn("read-only", result["flags"])

    def test_read_only_but_external_is_medium_risk(self) -> None:
        # Only readOnlyHint is set; destructiveHint and openWorldHint both default
        # to True (paranoid). So the band is medium (reads the outside world) and
        # — by the same defaults — the tool still carries the "destructive" flag.
        result = classify({"readOnlyHint": True})
        self.assertEqual(result["band"], "medium")
        self.assertCountEqual(result["flags"], ["read-only", "destructive", "external"])

    def test_destructive_and_external_is_high_risk(self) -> None:
        result = classify({"destructiveHint": True, "openWorldHint": True})
        self.assertEqual(result["band"], "high")

    def test_contained_non_destructive_tool_is_low_risk(self) -> None:
        result = classify({"destructiveHint": False, "openWorldHint": False})
        self.assertEqual(result["band"], "low")
        self.assertEqual(result["flags"], [])

    def test_title_is_carried_through(self) -> None:
        self.assertEqual(classify({"title": "Delete Everything"})["title"], "Delete Everything")


class AggregateTests(unittest.TestCase):
    def _tool(self, name: str, annotations) -> dict:
        return {
            "name": name,
            "description": "",
            "param_count": 0,
            "required_count": 0,
            "has_output_schema": annotations is not None,
            **classify(annotations),
        }

    def test_annotation_and_output_schema_percentages(self) -> None:
        tools = [
            self._tool("read_file", {"readOnlyHint": True, "openWorldHint": False}),
            self._tool("fetch_url", None),  # unannotated, no output schema
        ]
        agg = aggregate(tools)
        self.assertEqual(agg["annotation_pct"], 50)
        self.assertEqual(agg["output_schema_pct"], 50)

    def test_empty_tool_list_does_not_divide_by_zero(self) -> None:
        agg = aggregate([])
        self.assertEqual(agg["annotation_pct"], 0)
        self.assertEqual(agg["output_schema_pct"], 0)
        self.assertEqual(agg["families"], [])


def _faithful_profile(connector: str) -> dict:
    """A complete profile dict (mirrors ``_fetch_connector_tool_profile`` output)
    built with the production classifier/aggregator so the fake stays faithful."""
    tools = [
        {"name": "read_file", "description": "Read a file", "param_count": 1, "required_count": 1,
         "has_output_schema": True, **classify({"readOnlyHint": True, "openWorldHint": False})},
        {"name": "delete_repo", "description": "Delete a repo", "param_count": 1, "required_count": 1,
         "has_output_schema": False, **classify({"destructiveHint": True, "openWorldHint": True})},
        {"name": "fetch_url", "description": "Fetch a URL", "param_count": 2, "required_count": 1,
         "has_output_schema": False, **classify(None)},
    ]
    band_counts = {band[0]: 0 for band in server_module._RISK_BANDS}
    for tool in tools:
        band_counts[tool["band"]] += 1
    return {
        "connector": connector, "ok": True, "error": None,
        "tool_count": len(tools), "band_counts": band_counts,
        "tools": tools, "aggregates": aggregate(tools),
    }


class RiskProfileAppE2ETests(unittest.IsolatedAsyncioTestCase):
    async def test_validation_rejects_blank_connector(self) -> None:
        async with mcp_client() as client:
            res = await client.call_tool(
                "show_connector_risk_profile", {"connector": "  "}, raise_on_error=False
            )
            self.assertTrue(res.is_error)

    async def test_renders_prefab_app_for_probed_connector(self) -> None:
        async with mcp_client() as client:
            with mock.patch.object(
                server_module, "_fetch_connector_tool_profile",
                side_effect=lambda name: _faithful_profile(name),
            ):
                res = await client.call_tool("show_connector_risk_profile", {"connector": "github"})

            self.assertFalse(res.is_error)
            app = structured(res)
            # A serialized Prefab app payload.
            self.assertIn("$prefab", app)
            self.assertIn("view", app)
            # The rendered tree mentions the connector and the risk bands present.
            blob = json.dumps(app)
            self.assertIn("github", blob)
            self.assertIn("High risk", blob)

    async def test_unreachable_connector_renders_error_app_not_tool_error(self) -> None:
        # A probe failure must degrade into a rendered error card, not an MCP error.
        async with mcp_client() as client:
            with mock.patch.object(
                server_module, "_fetch_connector_tool_profile",
                side_effect=lambda name: server_module._profile_error(name, "registry lookup failed"),
            ):
                res = await client.call_tool(
                    "show_connector_risk_profile", {"connector": "ghost"}, raise_on_error=False
                )

            self.assertFalse(res.is_error)
            blob = json.dumps(structured(res))
            self.assertIn("Cannot probe 'ghost'", blob)
            self.assertIn("registry lookup failed", blob)


if __name__ == "__main__":
    unittest.main()
