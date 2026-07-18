"""MCP Apps extension conformance for the Job Designer server.

Verified against the MCP Apps specification (``mcp-apps.mdx`` in this folder).
Section references below point at that document. The server's obligations are:

* serve a ``ui://`` UI resource that is a valid mcp-app HTML document,
* declare UI security metadata (``csp`` / ``domain`` / ``prefersBorder``) on
  both the ``resources/list`` entry and the ``resources/read`` content item,
* never let the HTML reference a domain the CSP does not declare,
* link tools to their UI resource via ``_meta.ui.resourceUri`` (not the
  deprecated flat key), pointing at a resource that actually exists,
* label tool ``visibility`` correctly. (Enforcing the *hiding* of app-only
  tools from the agent is the host's job per spec — the server's job is to
  label, which is what we assert here.)
"""

from __future__ import annotations

import re
import unittest
from urllib.parse import urlparse

import server as server_module
from _harness import mcp_client, tool_map, ui_meta

MCP_APP_MIME = "text/html;profile=mcp-app"  # spec §"Content Requirements"

# Tools the server marks app-only (callable by the iframe, hidden from the agent).
APP_ONLY_TOOLS = {
    "capture_current_draft",
    "generate_full_job_draft",
    "get_current_draft_ui_state",
    "preview_ai_suggested_changes",
}
# Tools that must remain reachable by the agent (visibility omitted ⇒ both,
# or explicitly includes "model").
MODEL_VISIBLE_TOOLS = {
    "open_job_designer",
    "list_job_types",
    "get_form_schema",
    "list_connectors",
    "get_draft_snapshot",
    "patch_draft_snapshot",
    "create_job",
    "trigger_run",
    "show_connector_risk_profile",
}

_EXTERNAL_REF_RE = re.compile(r"""(?:href|src)\s*=\s*["'](https?://[^"']+)["']""", re.IGNORECASE)


def _external_hosts(html: str) -> set[str]:
    """Origins (scheme://host) the HTML loads sub-resources from."""
    hosts: set[str] = set()
    for url in _EXTERNAL_REF_RE.findall(html):
        parsed = urlparse(url)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            hosts.add(f"{parsed.scheme}://{parsed.netloc}")
    return hosts


class FrameworkMimeAlignmentTests(unittest.TestCase):
    """Pin the framework's UI mime constant against the spec literal.

    Keeps the conformance assertions honest: if a FastMCP upgrade changed
    UI_MIME_TYPE away from the spec value, this is the single test that fails.
    """

    def test_fastmcp_ui_mime_matches_spec(self) -> None:
        from fastmcp.apps import UI_MIME_TYPE

        self.assertEqual(
            UI_MIME_TYPE,
            MCP_APP_MIME,
            "FastMCP's UI_MIME_TYPE drifted from the MCP Apps spec value",
        )


class UiResourceConformanceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._client = mcp_client()
        await self._client.__aenter__()
        self.resources = {str(r.uri): r for r in await self._client.list_resources()}
        self.main_uri = server_module.APP_RESOURCE_URI

    async def asyncTearDown(self) -> None:
        await self._client.__aexit__(None, None, None)

    async def test_main_resource_is_registered(self) -> None:
        self.assertIn(self.main_uri, self.resources)

    async def test_all_ui_resource_uris_use_ui_scheme(self) -> None:
        # spec: "URI MUST start with ui:// scheme"
        for uri in self.resources:
            self.assertTrue(uri.startswith("ui://"), f"non-ui:// resource: {uri}")

    async def test_listing_mimetype_is_mcp_app_profile(self) -> None:
        # spec: mimeType MUST be text/html;profile=mcp-app
        for uri, res in self.resources.items():
            self.assertEqual(res.mimeType, MCP_APP_MIME, f"{uri}: wrong mimeType")

    async def test_read_returns_valid_html5_document(self) -> None:
        # spec: Content MUST be a valid HTML5 document, served as the mcp-app profile.
        contents = await self._client.read_resource(self.main_uri)
        self.assertTrue(contents, "read returned no content")
        item = contents[0]
        self.assertEqual(item.mimeType, MCP_APP_MIME)
        html = item.text or ""
        self.assertRegex(html.lstrip()[:200].lower(), r"^<!doctype html")
        self.assertIn("</html>", html.lower())

    async def test_security_meta_present_on_listing_entry(self) -> None:
        # spec "Metadata Location": UIResourceMeta may live on the listing entry.
        meta = ui_meta(self.resources[self.main_uri])
        self.assertIn("csp", meta, "listing entry missing _meta.ui.csp")
        self.assertEqual(meta.get("domain"), server_module.APP_RESOURCE_DOMAIN)
        self.assertIsInstance(meta.get("prefersBorder"), bool)

    async def test_security_meta_present_on_read_content_item(self) -> None:
        # spec: hosts MUST check both locations, preferring the content item.
        # The server therefore must also stamp _meta.ui onto resources/read.
        contents = await self._client.read_resource(self.main_uri)
        meta = ui_meta(contents[0])
        self.assertIn("csp", meta, "read content item missing _meta.ui.csp")
        self.assertEqual(meta.get("domain"), server_module.APP_RESOURCE_DOMAIN)

    async def test_csp_declares_every_domain_the_html_loads(self) -> None:
        # spec "No Loosening": the host MUST NOT allow undeclared domains, so the
        # server's declared CSP must cover everything the document actually pulls.
        contents = await self._client.read_resource(self.main_uri)
        item = contents[0]
        html = item.text or ""
        csp = ui_meta(item).get("csp") or {}
        declared = set(csp.get("resourceDomains") or []) | set(csp.get("connectDomains") or [])
        declared_hosts = {f"{urlparse(d).scheme}://{urlparse(d).netloc}" for d in declared if "://" in d}

        referenced = _external_hosts(html)
        self.assertTrue(referenced, "HTML references no external host — assertion would be vacuous")
        undeclared = referenced - declared_hosts
        self.assertEqual(
            undeclared,
            set(),
            f"HTML loads from domains not declared in CSP (host would block them): {sorted(undeclared)}",
        )


class ToolUiLinkageTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._client = mcp_client()
        await self._client.__aenter__()
        self.tools = tool_map(await self._client.list_tools())
        self.resource_uris = {str(r.uri) for r in await self._client.list_resources()}

    async def asyncTearDown(self) -> None:
        await self._client.__aexit__(None, None, None)

    async def test_ui_tools_reference_an_existing_readable_resource(self) -> None:
        # spec §"Behavior": Resource MUST exist; host uses resources/read to fetch.
        linked = [t for t in self.tools.values() if ui_meta(t).get("resourceUri")]
        self.assertTrue(linked, "no UI-linked tools found")
        for tool in linked:
            uri = ui_meta(tool)["resourceUri"]
            self.assertTrue(uri.startswith("ui://"), f"{tool.name}: resourceUri not ui://")
            # "Resource MUST exist" — proven by a successful read.
            contents = await self._client.read_resource(uri)
            self.assertTrue(contents, f"{tool.name}: resourceUri {uri} not readable")

    async def test_open_job_designer_links_main_template(self) -> None:
        meta = ui_meta(self.tools["open_job_designer"])
        self.assertEqual(meta.get("resourceUri"), server_module.APP_RESOURCE_URI)

    async def test_no_tool_uses_deprecated_flat_resourceuri_key(self) -> None:
        # spec: flat _meta["ui/resourceUri"] is deprecated; use nested ui.resourceUri.
        for tool in self.tools.values():
            meta = getattr(tool, "meta", None) or {}
            self.assertNotIn(
                "ui/resourceUri",
                meta,
                f"{tool.name} uses the deprecated flat _meta['ui/resourceUri'] key",
            )


class ToolVisibilityTests(unittest.IsolatedAsyncioTestCase):
    """Visibility *labeling* conformance (spec §"Tool Metadata" / §"Visibility").

    The host enforces hiding/rejection; the server's contract is to label
    visibility correctly, which is what these assertions check.
    """

    async def asyncSetUp(self) -> None:
        self._client = mcp_client()
        await self._client.__aenter__()
        self.tools = tool_map(await self._client.list_tools())

    async def asyncTearDown(self) -> None:
        await self._client.__aexit__(None, None, None)

    def _visibility(self, name: str):
        return ui_meta(self.tools[name]).get("visibility")

    async def test_app_only_tools_are_labeled_app_only(self) -> None:
        for name in APP_ONLY_TOOLS:
            self.assertIn(name, self.tools, f"{name} not registered")
            self.assertEqual(
                self._visibility(name),
                ["app"],
                f"{name} must be visibility=['app'] so the host hides it from the agent",
            )

    async def test_model_visible_tools_remain_reachable_by_agent(self) -> None:
        # visibility omitted ⇒ default ["model","app"]; otherwise must include "model".
        for name in MODEL_VISIBLE_TOOLS:
            self.assertIn(name, self.tools, f"{name} not registered")
            vis = self._visibility(name)
            self.assertTrue(
                vis is None or "model" in vis,
                f"{name} would be hidden from the agent (visibility={vis})",
            )

    async def test_approval_provider_tool_is_model_only(self) -> None:
        # The Approval provider's request_approval is invoked by the model.
        self.assertIn("request_approval", self.tools)
        self.assertEqual(self._visibility("request_approval"), ["model"])


if __name__ == "__main__":
    unittest.main()
