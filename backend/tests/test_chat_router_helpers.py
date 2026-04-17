from __future__ import annotations

import unittest

from app.api.routers.chat import (
    ChatRequest,
    _deterministic_repo_connection_fields,
    _deterministic_sql_fields,
    _is_explicit_sql_run_request,
)


class ChatRouterHelperTests(unittest.TestCase):
    def test_runs_database_request_fills_sql_query_without_llm(self) -> None:
        fields = _deterministic_sql_fields(
            ChatRequest(
                message="I want to get all the runs in the database",
                current_draft_data={"job_type": "SQL", "job_name": "get-runs"},
            )
        )

        self.assertEqual(fields["connector"], "sql-dab")
        self.assertEqual(fields["connection_id"], "postgres")
        self.assertEqual(fields["query"], "SELECT * FROM runs;")

    def test_manual_run_type_does_not_count_as_explicit_execution(self) -> None:
        request = ChatRequest(
            message="please run it manually",
            current_draft_data={"job_type": "SQL", "job_name": "get-runs"},
        )

        self.assertFalse(_is_explicit_sql_run_request(request))
        self.assertEqual(_deterministic_sql_fields(request), {"run_type": "manual"})

    def test_run_job_now_counts_as_explicit_execution(self) -> None:
        request = ChatRequest(
            message="Nope, please run the job now",
            current_draft_data={"job_type": "SQL", "job_name": "get-runs"},
        )

        self.assertTrue(_is_explicit_sql_run_request(request))

    def test_create_job_request_marks_creation_requested(self) -> None:
        fields = _deterministic_sql_fields(
            ChatRequest(
                message="Please create the job",
                current_draft_data={"job_type": "SQL", "job_name": "get-resources"},
            )
        )

        self.assertTrue(fields["creation_requested"])

    def test_yes_after_resource_creation_counts_as_execution(self) -> None:
        request = ChatRequest(
            message="yes",
            current_draft_data={"job_type": "SQL", "job_name": "get-runs", "resource_id": "res_get_runs"},
        )

        self.assertTrue(_is_explicit_sql_run_request(request))

    def test_repo_connection_request_extracts_repo_fields(self) -> None:
        fields = _deterministic_repo_connection_fields(
            ChatRequest(
                message="Connect the GitHub repo toyota-data/dbt-core branch develop",
            )
        )

        self.assertEqual(fields["connection_intent"], "connect_repo")
        self.assertEqual(fields["type"], "repo_connection")
        self.assertEqual(fields["connector"], "github")
        self.assertEqual(fields["repo"], "toyota-data/dbt-core")
        self.assertEqual(fields["ref"], "develop")

    def test_repo_connection_request_without_repo_still_marks_intent(self) -> None:
        fields = _deterministic_repo_connection_fields(
            ChatRequest(
                message="Can you connect my GitHub repository?",
            )
        )

        self.assertEqual(fields["connection_intent"], "connect_repo")
        self.assertEqual(fields["connector"], "github")


if __name__ == "__main__":
    unittest.main()
