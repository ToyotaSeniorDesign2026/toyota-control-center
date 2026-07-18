"""Secret-handling conformance for the draft snapshot surface.

The server keeps two views of a draft:

* **AI-facing** (``get_draft_snapshot`` / ``patch_draft_snapshot`` returns) —
  secret fields are masked with ``utils.SECRET_MARKER`` so credentials never
  reach the model or transcript.
* **iframe-sync** (``get_current_draft_ui_state``) — real values are preserved
  so the browser form can be repopulated.

"Secret" is contract-driven: a field is sensitive when its FieldSpec sets
``sensitive`` / ``write_only`` / ``format == "secret"``. In the built-in
contracts that is ``sql.params.password`` and ``airflow_python.config.airflow_token``.
"""

from __future__ import annotations

import json
import unittest

import utils
from _harness import mcp_client, structured

MARKER = utils.SECRET_MARKER


class SecretMaskingTests(unittest.IsolatedAsyncioTestCase):
    async def test_sql_password_is_masked_for_the_model(self) -> None:
        async with mcp_client() as client:
            await client.call_tool("open_job_designer", {"job_type": "sql", "reset": True})
            await client.call_tool(
                "patch_draft_snapshot",
                {"patch": {"params": {"password": "hunter2", "host": "db.internal", "username": "svc"}}},
            )
            snap = structured(await client.call_tool("get_draft_snapshot", {}))
            params = snap["draft"]["params"]

            self.assertEqual(params["password"], MARKER)
            # Non-secret siblings are untouched.
            self.assertEqual(params["host"], "db.internal")
            self.assertEqual(params["username"], "svc")
            # The plaintext secret must not leak anywhere in the AI-facing JSON.
            self.assertNotIn("hunter2", json.dumps(snap))

    async def test_airflow_token_config_field_is_masked(self) -> None:
        async with mcp_client() as client:
            await client.call_tool("open_job_designer", {"job_type": "airflow_python", "reset": True})
            await client.call_tool(
                "patch_draft_snapshot",
                {"patch": {"config": {"airflow_token": "tok_abc123", "airflow_url": "https://af.example"}}},
            )
            snap = structured(await client.call_tool("get_draft_snapshot", {}))
            config = snap["draft"]["config"]

            self.assertEqual(config["airflow_token"], MARKER)
            self.assertEqual(config["airflow_url"], "https://af.example")
            self.assertNotIn("tok_abc123", json.dumps(snap))

    async def test_empty_secret_is_not_masked(self) -> None:
        # mask_secrets only masks non-empty values; an empty field stays empty
        # (so the UI shows a blank input, not a fake "•••").
        async with mcp_client() as client:
            await client.call_tool("open_job_designer", {"job_type": "sql", "reset": True})
            await client.call_tool("patch_draft_snapshot", {"patch": {"params": {"password": ""}}})
            snap = structured(await client.call_tool("get_draft_snapshot", {}))
            self.assertEqual(snap["draft"]["params"].get("password", ""), "")


class PatchReturnRedactionTests(unittest.IsolatedAsyncioTestCase):
    """`patch_draft_snapshot` is model-visible, so *its own return* — not just
    `get_draft_snapshot` — must never carry plaintext secrets.

    Regression guard: the tool spreads the raw `_apply_designer_patch` result
    (whose merge base pulls the stored secret forward), so the top-level
    `config`/`params` have to be masked in addition to the nested `draft`.
    """

    async def test_patch_return_masks_secret_in_top_level_params(self) -> None:
        async with mcp_client() as client:
            await client.call_tool("open_job_designer", {"job_type": "sql", "reset": True})
            res = structured(
                await client.call_tool(
                    "patch_draft_snapshot",
                    {"patch": {"params": {"password": "hunter2", "host": "db.internal"}}},
                )
            )
            # Top-level (not just draft.*) must be masked.
            self.assertEqual(res["params"]["password"], MARKER)
            self.assertEqual(res["params"]["host"], "db.internal")
            self.assertEqual(res["draft"]["params"]["password"], MARKER)
            self.assertNotIn("hunter2", json.dumps(res))

    async def test_secret_stays_masked_on_later_unrelated_patch(self) -> None:
        # The exfiltration path: set the secret once, then issue any unrelated
        # patch — the merge base carries the real value forward. Its return must
        # still be masked at the top level.
        async with mcp_client() as client:
            await client.call_tool("open_job_designer", {"job_type": "sql", "reset": True})
            await client.call_tool(
                "patch_draft_snapshot", {"patch": {"params": {"password": "hunter2"}}}
            )
            res = structured(
                await client.call_tool(
                    "patch_draft_snapshot", {"patch": {"params": {"host": "db2"}}}
                )
            )
            self.assertEqual(res["params"]["password"], MARKER)
            self.assertEqual(res["params"]["host"], "db2")
            self.assertNotIn("hunter2", json.dumps(res))

    async def test_patch_return_masks_secret_in_top_level_config(self) -> None:
        async with mcp_client() as client:
            await client.call_tool("open_job_designer", {"job_type": "airflow_python", "reset": True})
            res = structured(
                await client.call_tool(
                    "patch_draft_snapshot",
                    {"patch": {"config": {"airflow_token": "tok_abc123", "airflow_url": "https://af.example"}}},
                )
            )
            self.assertEqual(res["config"]["airflow_token"], MARKER)
            self.assertEqual(res["config"]["airflow_url"], "https://af.example")
            self.assertNotIn("tok_abc123", json.dumps(res))


class IframeSyncPreservesSecretsTests(unittest.IsolatedAsyncioTestCase):
    async def test_iframe_sync_path_returns_real_secret(self) -> None:
        # The form-repopulation path must keep the true value, or the user would
        # lose their password on every AI-assisted edit round-trip.
        async with mcp_client() as client:
            await client.call_tool("open_job_designer", {"job_type": "sql", "reset": True})
            await client.call_tool("patch_draft_snapshot", {"patch": {"params": {"password": "hunter2"}}})

            ui_state = structured(await client.call_tool("get_current_draft_ui_state", {}))
            self.assertEqual(ui_state["params"]["password"], "hunter2")

    async def test_echoed_marker_does_not_overwrite_stored_secret(self) -> None:
        # The model often echoes back the redacted "•••" it was shown. That must
        # be dropped, not written over the real credential.
        async with mcp_client() as client:
            await client.call_tool("open_job_designer", {"job_type": "sql", "reset": True})
            await client.call_tool("patch_draft_snapshot", {"patch": {"params": {"password": "hunter2"}}})

            # A later patch carries the marker (echoed) plus a real change.
            await client.call_tool(
                "patch_draft_snapshot",
                {"patch": {"params": {"password": MARKER, "host": "newhost"}}},
            )

            ui_state = structured(await client.call_tool("get_current_draft_ui_state", {}))
            # Real secret survives; the legitimate sibling change still applies.
            self.assertEqual(ui_state["params"]["password"], "hunter2")
            self.assertEqual(ui_state["params"]["host"], "newhost")


if __name__ == "__main__":
    unittest.main()
