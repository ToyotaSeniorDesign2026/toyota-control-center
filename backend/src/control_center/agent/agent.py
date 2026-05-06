from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any

from control_center.mcp.adapters import BaseAdapter
from control_center.mcp import BaseClient
from control_center.mcp import AgentToolExecution, LLMProtocol, ModelTurnResult

__all__ = ["AgentResponse", "MCPAgent"]


@dataclass
class AgentResponse:
    """Normalized response returned by the orchestration loop."""

    final_text: str
    tool_executions: list[AgentToolExecution] = field(default_factory=list)
    raw_model_response: Any | None = None


class MCPAgent:
    """
    Small orchestration layer that composes:
    - an MCP transport client
    - a framework adapter
    - either a provider-specific model wrapper or a model name handled by the adapter
    """

    def __init__(
        self,
        *,
        client: BaseClient,
        adapter: BaseAdapter[Any],
        model: str | LLMProtocol,
        max_tool_rounds: int = 5,
        verbose: bool = False,
    ) -> None:
        self._client = client
        self._adapter = adapter
        self._model = model
        self._max_tool_rounds = max_tool_rounds
        self._verbose = verbose

    @property
    def client(self) -> BaseClient:
        return self._client

    @property
    def adapter(self) -> BaseAdapter[Any]:
        return self._adapter

    async def cleanup(self) -> None:
        await self._client.cleanup()

    def _log(self, message: str) -> None:
        if self._verbose:
            print(message)

    async def refresh_capabilities(self) -> None:
        self._adapter.clear_cache()
        await self._adapter.create_all(self._client)

    async def _generate_turn(
        self,
        *,
        inputs: list[dict[str, Any]],
    ) -> ModelTurnResult:
        if isinstance(self._model, str):
            return await self._adapter.generate(
                model=self._model,
                inputs=inputs,
                tools=self._adapter.all_capabilities,
            )

        return await self._model.generate(
            inputs=inputs,
            tools=self._adapter.all_capabilities,
        )

    async def run(self, user_message: str) -> AgentResponse:
        await self.refresh_capabilities()

        tool_executions: list[AgentToolExecution] = []
        inputs: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
        last_model_result: ModelTurnResult | None = None

        for round_index in range(self._max_tool_rounds):
            model_result = await self._generate_turn(inputs=inputs)
            last_model_result = model_result
            self._log(f"(Round {round_index + 1}/{self._max_tool_rounds})")

            if model_result.text:
                self._log(f"(Model output: {model_result.text})")

            # Pair each call with a stable id so OpenAI assistant/tool input messages match up.
            # Providers that don't issue ids (e.g. Google) get a synthesized one.
            calls_with_ids: list[tuple[Any, str]] = [
                (tc, tc.id or f"call_{round_index}_{i}")
                for i, tc in enumerate(model_result.tool_calls)
            ]

            # Record the assistant turn so the next round sees full history.
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": model_result.text,
            }
            if calls_with_ids:
                assistant_msg["tool_calls"] = [
                    {
                        "id": cid,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, default=str),
                        },
                    }
                    for tc, cid in calls_with_ids
                ]
            inputs.append(assistant_msg)

            if not calls_with_ids:
                return AgentResponse(
                    final_text=model_result.text or "",
                    tool_executions=tool_executions,
                    raw_model_response=model_result.raw,
                )

            for requested_call, tool_call_id in calls_with_ids:
                serialized_arguments = json.dumps(requested_call.arguments, default=str, sort_keys=True)
                self._log(f"(Calling {requested_call.name} with {serialized_arguments})")

                # Look up the binding. If the model hallucinated a tool name,
                # feed the error back so it can pick a real tool next round.
                try:
                    binding = self._adapter.get_binding(requested_call.name)
                except Exception as exc:
                    error_text = f"[ERROR] Unknown tool {requested_call.name!r}: {exc}"
                    self._log(f"(Tool error: {error_text})")
                    inputs.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": error_text,
                    })
                    continue

                # Invoke the tool. Catch exceptions and return them as the
                # tool's "result" so the model can react instead of crashing.
                raw_result: Any = None
                try:
                    raw_result = await self._adapter.invoke(
                        self._client,
                        exposed_name=requested_call.name,
                        arguments=requested_call.arguments,
                    )
                    parsed_result = self._adapter.parse_result(raw_result)
                except Exception as exc:
                    parsed_result = (
                        f"[ERROR] Tool {requested_call.name!r} raised: {exc}. "
                        f"Try different arguments, a different tool, or stop "
                        f"calling tools and answer with what you have."
                    )
                    self._log(f"(Tool error: {parsed_result})")

                self._log(f"(Tool result from {requested_call.name}: {parsed_result})")

                tool_executions.append(
                    AgentToolExecution(
                        exposed_name=requested_call.name,
                        server_name=binding.server_name,
                        source_id=binding.source_id,
                        arguments=requested_call.arguments,
                        raw_result=raw_result,
                        parsed_result=parsed_result,
                    )
                )

                inputs.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": parsed_result,
                })

        final_text = (
            last_model_result.text
            if last_model_result and last_model_result.text
            else "Reached the tool-call limit before producing a final response."
        )
        return AgentResponse(
            final_text=final_text,
            tool_executions=tool_executions,
            raw_model_response=last_model_result.raw if last_model_result else None,
        )
