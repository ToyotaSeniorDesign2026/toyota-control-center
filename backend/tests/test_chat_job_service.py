from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.services.chat_job_service import maybe_run_sql_job_from_chat, register_sql_job_from_chat


class ChatJobServiceTests(unittest.TestCase):
    def test_register_sql_job_from_chat_uses_existing_job_name_from_draft(self) -> None:
        actor = SimpleNamespace(id="u_analyst", role="user", domain="collections")
        created_resource = {"id": "res_get_users"}

        with patch("app.services.chat_job_service.get_chat_actor", return_value=actor), patch(
            "app.services.chat_job_service._find_sql_resource_for_actor", return_value=None
        ), patch(
            "app.services.chat_job_service.create_resource",
            return_value=created_resource,
        ) as create_resource_mock:
            result = register_sql_job_from_chat(
                object(),
                extracted_fields={"creation_requested": True},
                current_draft={
                    "job_type": "SQL",
                    "job_name": "get-users-10",
                    "connector": "postgres",
                    "connection_id": "postgres",
                    "query": "SELECT * FROM users;",
                    "target_environment": "dev",
                    "run_type": "manual",
                },
            )

        self.assertEqual(result.resource_id, "res_get_users")
        self.assertTrue(result.resource_created)
        self.assertEqual(create_resource_mock.call_args.args[2].name, "get-users-10")
        self.assertEqual(create_resource_mock.call_args.args[2].connector, "sql-mcp")
        self.assertEqual(create_resource_mock.call_args.args[2].environment, "dev")
        self.assertEqual(create_resource_mock.call_args.args[2].config["query"], "SELECT * FROM users;")
        self.assertNotIn("target_environment", create_resource_mock.call_args.args[2].config)
        self.assertNotIn("environment", create_resource_mock.call_args.args[2].config)

    def test_existing_sql_resource_runs_without_recreating_resource(self) -> None:
        db = object()
        actor = SimpleNamespace(id="u_analyst", role="user", domain="collections")
        resource = SimpleNamespace(
            id="res_sql_1",
            name="dealer_sales_summary",
            environment="dev",
            config={"query": "select * from sales"},
        )

        with patch("app.services.chat_job_service.get_chat_actor", return_value=actor), patch(
            "app.services.chat_job_service._find_sql_resource_for_actor", return_value=resource
        ), patch("app.services.chat_job_service.create_resource") as create_resource_mock, patch(
            "app.services.chat_job_service.create_run_and_maybe_execute",
            return_value={"id": "run_123", "status": "succeeded"},
        ) as create_run_mock:
            result = maybe_run_sql_job_from_chat(
                db,
                message="Run the SQL job dealer_sales_summary",
                extracted_fields={"job_type": "SQL", "action": "run", "name": "dealer_sales_summary"},
                current_draft=None,
            )

        self.assertIsNotNone(result)
        self.assertTrue(result.executed)
        self.assertEqual(result.resource_id, "res_sql_1")
        self.assertEqual(result.run_id, "run_123")
        create_resource_mock.assert_not_called()
        self.assertEqual(create_run_mock.call_args.args[2].resource_id, "res_sql_1")

    def test_missing_sql_resource_can_be_created_and_run_from_chat(self) -> None:
        db = object()
        actor = SimpleNamespace(id="u_analyst", role="user", domain="collections")
        created_resource = {"id": "res_new_1"}
        resource_model = SimpleNamespace(
            id="res_new_1",
            name="ad_hoc_sales_check",
            environment="dev",
            config={"query": "select 1"},
        )

        with patch("app.services.chat_job_service.get_chat_actor", return_value=actor), patch(
            "app.services.chat_job_service._find_sql_resource_for_actor", return_value=None
        ), patch(
            "app.services.chat_job_service.create_resource",
            return_value=created_resource,
        ) as create_resource_mock, patch(
            "app.services.chat_job_service.create_run_and_maybe_execute",
            return_value={"id": "run_456", "status": "queued"},
        ) as create_run_mock:
            db = SimpleNamespace(get=lambda model, resource_id: resource_model)
            result = maybe_run_sql_job_from_chat(
                db,
                message="Create and run a SQL job named ad_hoc_sales_check with query select 1",
                extracted_fields={
                    "job_type": "SQL",
                    "action": "run",
                    "name": "ad_hoc_sales_check",
                    "query": "select 1",
                },
                current_draft=None,
            )

        self.assertIsNotNone(result)
        self.assertTrue(result.executed)
        self.assertTrue(result.resource_created)
        self.assertEqual(create_resource_mock.call_args.args[2].connector, "sql-mcp")
        self.assertEqual(create_run_mock.call_args.args[2].resource_id, "res_new_1")

    def test_non_execution_chat_message_does_not_trigger_sql_run(self) -> None:
        result = maybe_run_sql_job_from_chat(
            object(),
            message="Explain how SQL resources work",
            extracted_fields={"job_type": "SQL"},
            current_draft=None,
        )
        self.assertIsNone(result)

    def test_sql_job_name_containing_runs_does_not_trigger_execution(self) -> None:
        result = maybe_run_sql_job_from_chat(
            object(),
            message="get-runs",
            extracted_fields={"job_name": "get-runs"},
            current_draft={"job_type": "SQL"},
        )
        self.assertIsNone(result)

    def test_manual_run_type_message_does_not_trigger_execution(self) -> None:
        result = maybe_run_sql_job_from_chat(
            object(),
            message="please run it manually",
            extracted_fields={"run_type": "manual"},
            current_draft={"job_type": "SQL", "job_name": "get-runs"},
        )
        self.assertIsNone(result)

    def test_explicit_run_uses_live_draft_job_name_as_resource_name(self) -> None:
        actor = SimpleNamespace(id="u_analyst", role="user", domain="collections")
        created_resource = {"id": "res_get_runs"}
        resource_model = SimpleNamespace(
            id="res_get_runs",
            name="get-runs",
            environment="dev",
            config={"query": "SELECT * FROM runs", "connection_id": "postgres"},
        )

        with patch("app.services.chat_job_service.get_chat_actor", return_value=actor), patch(
            "app.services.chat_job_service._find_sql_resource_for_actor", return_value=None
        ), patch(
            "app.services.chat_job_service.create_resource",
            return_value=created_resource,
        ) as create_resource_mock, patch(
            "app.services.chat_job_service.create_run_and_maybe_execute",
            return_value={"id": "run_get_runs", "status": "succeeded"},
        ) as create_run_mock:
            db = SimpleNamespace(get=lambda model, resource_id: resource_model)
            result = maybe_run_sql_job_from_chat(
                db,
                message="please run the job for me",
                extracted_fields=None,
                current_draft={
                    "job_type": "SQL",
                    "job_name": "get-runs",
                    "connector": "sql-mcp",
                    "connection_id": "postgres",
                    "query": "SELECT * FROM runs",
                    "target_environment": "dev",
                    "run_type": "manual",
                },
            )

        self.assertIsNotNone(result)
        self.assertTrue(result.executed)
        self.assertTrue(result.resource_created)
        self.assertEqual(create_resource_mock.call_args.args[2].name, "get-runs")
        self.assertEqual(create_resource_mock.call_args.args[2].connector, "sql-mcp")
        self.assertEqual(create_resource_mock.call_args.args[2].config["connection_id"], "postgres")
        self.assertEqual(create_run_mock.call_args.args[2].target_environment, "dev")

    def test_ui_connector_label_is_normalized_before_resource_creation(self) -> None:
        actor = SimpleNamespace(id="u_analyst", role="user", domain="collections")
        created_resource = {"id": "res_label"}
        resource_model = SimpleNamespace(
            id="res_label",
            name="get-runs",
            environment="dev",
            config={"query": "SELECT * FROM runs;", "connection_id": "postgres"},
        )

        with patch("app.services.chat_job_service.get_chat_actor", return_value=actor), patch(
            "app.services.chat_job_service._find_sql_resource_for_actor", return_value=None
        ), patch(
            "app.services.chat_job_service.create_resource",
            return_value=created_resource,
        ) as create_resource_mock, patch(
            "app.services.chat_job_service.create_run_and_maybe_execute",
            return_value={"id": "run_label", "status": "succeeded"},
        ):
            db = SimpleNamespace(get=lambda model, resource_id: resource_model)
            result = maybe_run_sql_job_from_chat(
                db,
                message="please run the job now",
                extracted_fields=None,
                current_draft={
                    "job_type": "SQL",
                    "job_name": "get-runs",
                    "connector": "Control Center Dev Database",
                    "connection_id": "postgres",
                    "query": "SELECT * FROM runs;",
                    "target_environment": "dev",
                },
            )

        self.assertIsNotNone(result)
        self.assertEqual(create_resource_mock.call_args.args[2].connector, "sql-mcp")


if __name__ == "__main__":
    unittest.main()
