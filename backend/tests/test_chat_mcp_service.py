from __future__ import annotations

import unittest

from unittest.mock import patch

from app.services.chat_mcp_service import needs_github_personal_access_token, should_run_prompt_native_mcp


class ChatMCPServiceTests(unittest.TestCase):
    def test_database_lookup_uses_prompt_native_mcp(self) -> None:
        self.assertTrue(should_run_prompt_native_mcp("Get all resources from the database"))

    def test_research_lookup_uses_prompt_native_mcp(self) -> None:
        self.assertTrue(should_run_prompt_native_mcp("Search arxiv for papers about MCP agents"))

    def test_create_job_stays_on_form_path(self) -> None:
        self.assertFalse(should_run_prompt_native_mcp("Create a SQL job"))

    def test_active_job_creation_draft_stays_on_form_path(self) -> None:
        self.assertFalse(
            should_run_prompt_native_mcp(
                "get-users-3",
                current_draft={"job_type": "SQL"},
            )
        )

    def test_query_like_answer_during_job_creation_stays_on_form_path(self) -> None:
        self.assertFalse(
            should_run_prompt_native_mcp(
                "I want to get all users from the database",
                current_draft={"job_type": "SQL", "job_name": "get-users-3"},
            )
        )

    def test_casual_chat_does_not_use_mcp(self) -> None:
        self.assertFalse(should_run_prompt_native_mcp("Hi, what can you do?"))

    def test_github_lookup_requires_token_when_not_configured(self) -> None:
        with patch.dict("os.environ", {}, clear=False):
            self.assertTrue(
                needs_github_personal_access_token("List open pull requests in toyota/control-center")
            )

    def test_supplied_github_token_satisfies_live_request(self) -> None:
        with patch.dict("os.environ", {}, clear=False):
            self.assertFalse(
                needs_github_personal_access_token(
                    "List open pull requests in toyota/control-center",
                    supplied_token="ghp_test",
                )
            )


if __name__ == "__main__":
    unittest.main()
