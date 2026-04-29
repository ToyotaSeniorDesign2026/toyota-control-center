from __future__ import annotations

import unittest

from app.api.routers.chat import (
    ChatRequest,
    _deterministic_repo_connection_fields,
    _deterministic_sql_fields,
    _is_explicit_sql_run_request,
    _missing_sql_job_fields,
    _sql_followup_response,
)


class ChatRouterHelperTests(unittest.TestCase):
    def test_runs_database_request_fills_sql_query_without_llm(self) -> None:
        fields = _deterministic_sql_fields(
            ChatRequest(
                message="I want to get all the runs in the database",
                current_draft_data={"job_type": "SQL", "job_name": "get-runs"},
            )
        )

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

    def test_create_and_run_sql_request_marks_run_after_create(self) -> None:
        fields = _deterministic_sql_fields(
            ChatRequest(
                message="Please create the job and run it",
                current_draft_data={"job_type": "SQL", "job_name": "get-resources"},
            )
        )

        self.assertTrue(fields["creation_requested"])
        self.assertTrue(fields["run_after_create"])
        self.assertEqual(fields["action"], "run")

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

    def test_sql_followup_response_asks_for_query_not_connector(self) -> None:
        request = ChatRequest(
            message="connect to a SQL database",
            current_draft_data={"job_type": "SQL"},
            session_env={
                "SQL_DB_HOST": "localhost",
                "SQL_DB_PORT": "5432",
                "SQL_DB_DATABASE": "control_center",
                "SQL_DB_USERNAME": "postgres",
                "SQL_DB_PASSWORD": "postgres",
                "SQL_CONNECTION_ID": "postgres",
            },
        )

        response = _sql_followup_response(
            request,
            extracted_fields={"job_type": "SQL", "connector": "sql-dab", "connection_id": "postgres"},
            session_env=request.session_env or {},
        )

        self.assertIsNotNone(response)
        self.assertIn("sql-dab", response)
        self.assertIn("next thing I need is the SQL query", response)
        self.assertNotIn("connector or database type", response)

    def test_missing_sql_job_fields_prioritizes_name_owner_target_environment_run_type(self) -> None:
        missing = _missing_sql_job_fields(
            extracted_fields={"job_type": "SQL", "query": "SELECT * FROM users"},
            current_draft=None,
        )

        self.assertEqual(
            missing,
            ["job_name", "owner", "target_environment", "run_type"],
        )

    def test_sql_followup_response_asks_for_job_name_after_query(self) -> None:
        request = ChatRequest(
            message="connect to a SQL database",
            current_draft_data={"job_type": "SQL"},
            session_env={
                "SQL_DB_HOST": "localhost",
                "SQL_DB_PORT": "5432",
                "SQL_DB_DATABASE": "control_center",
                "SQL_DB_USERNAME": "postgres",
                "SQL_DB_PASSWORD": "postgres",
                "SQL_CONNECTION_ID": "postgres",
            },
        )

        response = _sql_followup_response(
            request,
            extracted_fields={
                "job_type": "SQL",
                "connector": "sql-dab",
                "connection_id": "postgres",
                "query": "SELECT * FROM users",
            },
            session_env=request.session_env or {},
        )

        self.assertIsNotNone(response)
        self.assertIn("job/resource name", response)
        self.assertNotIn("run the query now", response)


if __name__ == "__main__":
    unittest.main()
