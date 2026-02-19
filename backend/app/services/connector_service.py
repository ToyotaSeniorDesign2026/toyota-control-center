from app.core.db import new_id


def execute_resource(db, user, run: dict):
    connector_run_id = new_id("mcp")
    # Stub result shaped like an MCP/connector adapter response.
    return {
        "connector_run_id": connector_run_id,
        "status": "succeeded",
        "duration_ms": 420,
        "metadata": {
            "resource_id": run["resource_id"],
            "target_environment": run["target_environment"],
        },
        "error": None,
    }
