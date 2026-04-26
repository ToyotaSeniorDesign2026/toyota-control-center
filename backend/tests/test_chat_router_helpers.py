from __future__ import annotations

import unittest
import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from app.api.routers.chat import (
    ChatRequest,
    ChatMessage,
    _answer_run_history_question,
    _coerce_to_sql,
    _deterministic_repo_connection_fields,
    _deterministic_sql_fields,
    _draft_without_connection_details,
    _is_explicit_sql_create_request,
    _is_explicit_sql_run_request,
    _is_new_database_request,
    _is_sql_job_flow_request,
    _looks_like_live_sql_lookup,
    _last_asked_sql_flow_field,
    _missing_sql_job_fields,
    _next_missing_sql_field,
    _sql_followup_response,
    send_chat_message,
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

    def test_live_sql_lookup_detects_first_time_query_requests(self) -> None:
        request = ChatRequest(message="Run a SQL query to list all users")

        self.assertTrue(_looks_like_live_sql_lookup(request))
        self.assertTrue(_is_sql_job_flow_request(request, job_creation_intent=False))

    def test_create_sql_job_enters_structured_job_flow(self) -> None:
        request = ChatRequest(message="Create a SQL job that gets all users")

        self.assertTrue(_is_sql_job_flow_request(request, job_creation_intent=True))

    def test_explicit_sql_create_request_detected(self) -> None:
        self.assertTrue(_is_explicit_sql_create_request("Looks good, create the job"))

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
            extracted_fields={"job_type": "SQL", "connector": "sql-mcp", "connection_id": "postgres"},
            session_env=request.session_env or {},
        )

        self.assertIsNotNone(response)
        self.assertIn("What SQL query would you like to run?", response)
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
                "connector": "sql-mcp",
                "connection_id": "postgres",
                "query": "SELECT * FROM users",
            },
            session_env=request.session_env or {},
        )

        self.assertIsNotNone(response)
        self.assertIn("job/resource name", response)
        self.assertNotIn("run the query now", response)

    def test_last_asked_sql_flow_field_recognizes_provide_sql_query_prompt(self) -> None:
        field = _last_asked_sql_flow_field(
            [
                {
                    "role": "assistant",
                    "content": (
                        "Could you please provide the SQL query that this job will execute? "
                        "For example, `CREATE TABLE customers (id SERIAL PRIMARY KEY);`"
                    ),
                }
            ]
        )

        self.assertEqual(field, "query")

    def test_last_asked_sql_flow_field_recognizes_who_will_be_owner_prompt(self) -> None:
        field = _last_asked_sql_flow_field(
            [
                {
                    "role": "assistant",
                    "content": "Who will be the owner of this job?",
                }
            ]
        )

        self.assertEqual(field, "owner")

    def test_plain_english_create_table_answer_coerces_to_sql(self) -> None:
        self.assertEqual(
            _coerce_to_sql('I want to create a new table called customers'),
            "CREATE TABLE customers (id SERIAL PRIMARY KEY);",
        )

    def test_explicit_create_sql_job_registers_without_tcp_reachability(self) -> None:
        request = ChatRequest(
            message="Please create the job for me",
            conversation_history=[
                ChatMessage(
                    role="assistant",
                    content="I couldn't reach the database at `localhost:5432` — would you like to update it?",
                )
            ],
            current_draft_data={
                "job_type": "SQL",
                "job_name": "Create Table",
                "owner": "htameez",
                "run_type": "manual",
                "query": "CREATE TABLE customers (id SERIAL PRIMARY KEY, name VARCHAR(100));",
                "connection_id": "postgres",
                "_connection_form_shown": True,
                "_connection_id_asked": True,
                "config": {"connection_id": "postgres"},
            },
            session_env={
                "SQL_DB_HOST": "localhost",
                "SQL_DB_PORT": "5432",
                "SQL_DB_DATABASE": "postgres",
                "SQL_DB_USERNAME": "postgres",
                "SQL_DB_PASSWORD": "postgres",
            },
        )

        registration = SimpleNamespace(
            message="Created SQL job `Create Table` and saved it as a Control Center resource.",
            resource_id="res_create_table",
            resource_name="Create Table",
            resource_created=True,
        )
        with patch("app.api.routers.chat._tcp_ping", return_value=True) as tcp_ping_mock, patch(
            "app.api.routers.chat.register_sql_job_from_chat",
            return_value=registration,
        ) as register_mock:
            response = asyncio.run(send_chat_message(request, db=object()))

        tcp_ping_mock.assert_called_once_with("localhost", "5432")
        register_mock.assert_called_once()
        self.assertEqual(response.resource_id, "res_create_table")
        self.assertEqual(response.extracted_fields["job_name"], "Create Table")
        self.assertEqual(response.extracted_fields["owner"], "htameez")
        self.assertEqual(
            response.extracted_fields["config"]["query"],
            "CREATE TABLE customers (id SERIAL PRIMARY KEY, name VARCHAR(100));",
        )

    def test_pending_field_advances_owner_answer_without_parsing_previous_prompt(self) -> None:
        request = ChatRequest(
            message="Hamna Tameez",
            conversation_history=[
                ChatMessage(
                    role="assistant",
                    content="Who will be the owner of this job?",
                )
            ],
            current_draft_data={
                "job_type": "SQL",
                "job_name": "Create Table",
                "_connection_form_shown": True,
                "_connection_id_asked": True,
                "_pending_field": "owner",
            },
            session_env={
                "SQL_DB_HOST": "localhost",
                "SQL_DB_PORT": "5432",
                "SQL_DB_DATABASE": "postgres",
                "SQL_DB_USERNAME": "postgres",
                "SQL_DB_PASSWORD": "postgres",
            },
        )

        response = asyncio.run(send_chat_message(request, db=object()))

        self.assertEqual(response.extracted_fields["owner"], "Hamna Tameez")
        self.assertEqual(response.extracted_fields["_pending_field"], "run_type")
        self.assertIn("manual", response.response.lower())
        self.assertIn("schedule", response.response.lower())

    def test_sql_connection_success_is_reported_after_connection_details_received(self) -> None:
        request = ChatRequest(
            message="I want to run a SQL query",
            current_draft_data={
                "job_type": "SQL",
                "_connection_form_shown": True,
                "_connection_id_asked": True,
            },
            session_env={
                "SQL_DB_HOST": "localhost",
                "SQL_DB_PORT": "5432",
                "SQL_DB_DATABASE": "postgres",
                "SQL_DB_USERNAME": "postgres",
                "SQL_DB_PASSWORD": "postgres",
            },
        )

        with patch("app.api.routers.chat._tcp_ping", return_value=True) as tcp_ping_mock:
            response = asyncio.run(send_chat_message(request, db=object()))

        tcp_ping_mock.assert_called_once_with("localhost", "5432")
        self.assertIn("successfully reached the database endpoint", response.response)
        self.assertEqual(response.extracted_fields["_connection_check_status"], "reachable")
        self.assertEqual(response.extracted_fields["_pending_field"], "job_name")

    def test_sql_connection_failure_is_reported_after_connection_details_received(self) -> None:
        request = ChatRequest(
            message="I want to run a SQL query",
            current_draft_data={
                "job_type": "SQL",
                "_connection_form_shown": True,
                "_connection_id_asked": True,
            },
            session_env={
                "SQL_DB_HOST": "localhost",
                "SQL_DB_PORT": "5432",
                "SQL_DB_DATABASE": "postgres",
                "SQL_DB_USERNAME": "postgres",
                "SQL_DB_PASSWORD": "postgres",
            },
        )

        with patch("app.api.routers.chat._tcp_ping", return_value=False):
            response = asyncio.run(send_chat_message(request, db=object()))

        self.assertIn("couldn't reach `localhost:5432`", response.response)
        self.assertEqual(response.extracted_fields["_connection_check_status"], "unreachable")
        self.assertEqual(response.extracted_fields["_pending_field"], "job_name")

    def test_last_run_question_reads_recent_run_from_database(self) -> None:
        db = SimpleNamespace(
            get=lambda model, resource_id: SimpleNamespace(name="customer-churn-analysis"),
        )

        with patch("app.api.routers.chat.get_chat_actor", return_value=SimpleNamespace(id="u_analyst")), patch(
            "app.api.routers.chat.list_runs",
            return_value=[
                {
                    "resource_id": "res_1",
                    "status": "succeeded",
                    "target_environment": "dev",
                    "updated_at": "2026-04-23T10:15:00Z",
                }
            ],
        ):
            response = _answer_run_history_question(db, "What was the last job I ran?")

        self.assertIsNotNone(response)
        self.assertIn("customer-churn-analysis", response)
        self.assertIn("succeeded", response)

    def test_recent_runs_question_returns_multiple_runs(self) -> None:
        db = SimpleNamespace(
            get=lambda model, resource_id: SimpleNamespace(name=f"job-for-{resource_id}"),
        )

        with patch("app.api.routers.chat.get_chat_actor", return_value=SimpleNamespace(id="u_analyst")), patch(
            "app.api.routers.chat.list_runs",
            return_value=[
                {
                    "resource_id": "res_2",
                    "status": "running",
                    "target_environment": "prod",
                    "updated_at": "2026-04-23T12:00:00Z",
                },
                {
                    "resource_id": "res_1",
                    "status": "succeeded",
                    "target_environment": "dev",
                    "updated_at": "2026-04-22T09:00:00Z",
                },
            ],
        ):
            response = _answer_run_history_question(db, "Show my recent runs")

        self.assertIsNotNone(response)
        self.assertIn("job-for-res_2", response)
        self.assertIn("job-for-res_1", response)

    def test_last_run_question_handles_empty_history(self) -> None:
        db = SimpleNamespace(get=lambda model, resource_id: None)

        with patch("app.api.routers.chat.get_chat_actor", return_value=SimpleNamespace(id="u_analyst")), patch(
            "app.api.routers.chat.list_runs",
            return_value=[],
        ):
            response = _answer_run_history_question(db, "What was my last run?")

        self.assertEqual(response, "I couldn't find any runs for you yet.")


    def test_next_missing_sql_field_requires_connection_details_after_form_shown(self) -> None:
        """After _connection_form_shown is set, _next_missing_sql_field still asks for connection fields."""
        # All universal fields present, form shown, but session_env missing connection details
        draft = {
            "job_type": "SQL",
            "job_name": "get-users",
            "owner": "Hamna Tameez",
            "run_type": "manual",
            "query": "SELECT * FROM users;",
            "_connection_form_shown": True,
        }
        # session_env missing everything
        self.assertEqual(_next_missing_sql_field(draft, {}), "database")

    def test_next_missing_sql_field_skips_connection_fields_when_session_env_complete(self) -> None:
        # _connection_id_asked must be set (form provides it, even if skipped) to clear that gate
        draft = {
            "job_type": "SQL",
            "job_name": "get-users",
            "owner": "Hamna Tameez",
            "run_type": "manual",
            "query": "SELECT * FROM users;",
            "_connection_form_shown": True,
            "_connection_id_asked": True,
        }
        session_env = {
            "SQL_DB_DATABASE": "mydb",
            "SQL_DB_USERNAME": "admin",
            "SQL_DB_PASSWORD": "secret",
            "SQL_DB_HOST": "localhost",
            "SQL_DB_PORT": "5432",
        }
        self.assertIsNone(_next_missing_sql_field(draft, session_env))

    def test_new_database_request_detected_with_sql_draft(self) -> None:
        self.assertTrue(_is_new_database_request(
            "Let's connect to a different database called postgres",
            {"job_type": "SQL"},
        ))
        self.assertTrue(_is_new_database_request(
            "connect to a new database",
            {"job_type": "SQL"},
        ))
        self.assertTrue(_is_new_database_request(
            "switch to a different database",
            {"job_type": "SQL"},
        ))

    def test_new_database_request_detected_via_sql_context_in_message(self) -> None:
        # No SQL draft but message contains SQL context words — still triggers
        self.assertTrue(_is_new_database_request(
            "connect to a different database called postgres",
            {},
        ))

    def test_new_database_request_not_triggered_without_pattern(self) -> None:
        self.assertFalse(_is_new_database_request(
            "create a SQL job that gets users",
            {"job_type": "SQL"},
        ))
        self.assertFalse(_is_new_database_request(
            "run the job now",
            {"job_type": "SQL"},
        ))

    def test_draft_without_connection_details_clears_connection_form_shown(self) -> None:
        draft = {
            "job_type": "SQL",
            "job_name": "get-users",
            "_connection_form_shown": True,
            "host": "localhost",
            "password": "secret",
        }
        clean = _draft_without_connection_details(draft)
        self.assertNotIn("_connection_form_shown", clean)
        self.assertNotIn("host", clean)
        self.assertEqual(clean["job_name"], "get-users")

    def test_draft_without_connection_details_preserves_job_fields(self) -> None:
        draft = {
            "job_type": "SQL",
            "job_name": "get-users",
            "owner": "Hamna Tameez",
            "run_type": "manual",
            "query": "SELECT * FROM users;",
            "host": "localhost",
            "port": "5432",
            "database": "postgres",
            "username": "admin",
            "password": "secret",
            "connection_id": "conn1",
            "_connection_id_asked": True,
            "config": {
                "host": "localhost",
                "port": "5432",
                "database": "postgres",
                "query": "SELECT * FROM users;",
            },
        }

        clean = _draft_without_connection_details(draft)

        self.assertEqual(clean["job_name"], "get-users")
        self.assertEqual(clean["owner"], "Hamna Tameez")
        self.assertEqual(clean["query"], "SELECT * FROM users;")
        self.assertNotIn("host", clean)
        self.assertNotIn("port", clean)
        self.assertNotIn("database", clean)
        self.assertNotIn("username", clean)
        self.assertNotIn("password", clean)
        self.assertNotIn("connection_id", clean)
        self.assertNotIn("_connection_id_asked", clean)
        self.assertEqual(clean["config"]["query"], "SELECT * FROM users;")
        self.assertNotIn("host", clean["config"])
        self.assertNotIn("database", clean["config"])


if __name__ == "__main__":
    unittest.main()
