from __future__ import annotations

import unittest

from app.services.resource_type_service import validate_resource_contract


class ResourceTypeServiceTests(unittest.TestCase):
    def test_sql_config_allows_chat_collected_connection_fields(self) -> None:
        contract = validate_resource_contract(
            "runtime",
            "sql",
            {
                "query": "CREATE TABLE example (id SERIAL PRIMARY KEY);",
                "connection_id": "postgres",
                "host": "host.docker.internal",
                "port": "5432",
                "database": "postgres",
                "username": "postgres",
                "password": "postgres",
            },
        )

        self.assertEqual(contract["type"], "sql")


if __name__ == "__main__":
    unittest.main()
