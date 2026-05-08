from __future__ import annotations

"""V2 executor registry.

Importing this package populates EXECUTOR_REGISTRY by importing each
executor module — each module registers itself by adding an entry below.

Add new executors here as they land:
    1. Create a new file under app/services/executors/v2/
    2. Subclass V2Executor, implement execute_async()
    3. Append the (ExecutorType, Class) entry below
"""

from control_center.specs import ExecutorType

from .airflow_python import AirflowPythonExecutor
from .base import V2Executor
from .mcp_agent import MCPAgentExecutor
from .mcp_tool import MCPToolExecutor
from .noop import NoopExecutor


EXECUTOR_REGISTRY: dict[ExecutorType, type[V2Executor]] = {
    ExecutorType.MCP_TOOL: MCPToolExecutor,
    ExecutorType.MCP_AGENT: MCPAgentExecutor,
    ExecutorType.AIRFLOW_PYTHON: AirflowPythonExecutor,
    ExecutorType.NOOP: NoopExecutor,
}


__all__ = [
    "EXECUTOR_REGISTRY",
    "AirflowPythonExecutor",
    "MCPAgentExecutor",
    "MCPToolExecutor",
    "NoopExecutor",
    "V2Executor",
]
