from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from app.schemas.run import RunCreate
from app.services.execution_service import build_execution_request
from app.services.executors.sql_executor import SQLJobExecutor


class SQLExecutorTests(unittest.TestCase):
    def _build_request(self, query: str) -> object:
        return build_execution_request(
            run_id="run_sql",
            resource=SimpleNamespace(
                id="res_sql",
                name="sql-job",
                type="sql",
                connector="internal",
                data_sensitivity="low",
                kind="runtime",
                environment="dev",
                config={"query": query},
                tags=[],
                owner_id="u_analyst",
                owner_domain="collections",
            ),
            payload=RunCreate(resource_id="res_sql", target_environment="dev"),
            trigger_source="api",
        )

    def test_sql_executor_runs_read_only_query(self) -> None:
        executor = SQLJobExecutor()
        execution_request = self._build_request("select 1 as value")

        fake_result = MagicMock()
        fake_result.fetchmany.return_value = [(1,)]
        fake_result.keys.return_value = ["value"]

        fake_connection = MagicMock()
        fake_connection.execute.return_value = fake_result
        fake_connection.__enter__.return_value = fake_connection
        fake_connection.__exit__.return_value = None

        fake_engine = MagicMock()
        fake_engine.connect.return_value = fake_connection

        with patch("app.services.executors.sql_executor.create_engine", return_value=fake_engine):
            result = executor.execute(execution_request)

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["metadata"]["row_count"], 1)
        self.assertEqual(result["metadata"]["rows"], [{"value": 1}])

    def test_sql_executor_rejects_non_read_only_query(self) -> None:
        executor = SQLJobExecutor()
        execution_request = self._build_request("delete from users")

        result = executor.execute(execution_request)

        self.assertEqual(result["status"], "failed")
        self.assertIn("read-only", result["error"])


if __name__ == "__main__":
    unittest.main()
