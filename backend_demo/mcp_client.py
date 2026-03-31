
# Based on the tutorial:
# "MCP: Build Rich-Context AI Apps with Anthropic"
# https://learn.deeplearning.ai/courses/mcp-build-rich-context-ai-apps-with-anthropic
# Accessed February 2026 by Noah Barnard

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from google import genai
from google.genai import types as genai_types
from typing import Union, Type, List, Dict, Any
from pydantic import BaseModel
import argparse
import json
import copy
import asyncio
from contextlib import AsyncExitStack
from dotenv import load_dotenv
import os


load_dotenv()
if not os.environ.get("GEMINI_API_KEY"):
    raise RuntimeError("GEMINI_API_KEY is not set")


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: Union[Type[BaseModel], Dict[str, Any]]

    def to_llm_tool(self) -> Dict[str, Any]:
        if isinstance(self.parameters, type) and issubclass(self.parameters, BaseModel):
            schema = self.parameters.model_json_schema()
        else:
            schema = self.parameters
        return {"name": self.name, "description": self.description, "parameters": schema}


class ConversationMemory:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self._messages = [] if enabled else None

    def add(self, content):
        if self.enabled:
            self._messages.append(content)

    def get(self):
        if not self.enabled:
            return []
        return self._messages

    def get_copy(self):
        if not self.enabled:
            return []
        return copy.deepcopy(self._messages)

    def reset(self):
        if self.enabled:
            self._messages = []

    def set_enabled(self, enabled: bool):
        if enabled and not self.enabled:
            self._messages = []
        elif not enabled:
            self._messages = None
        self.enabled = enabled


class MCPChatBot:

    def __init__(self, stateful=True, model="gemini-3-flash-preview"):
        # Initialize sessions and client objects
        self.memory = ConversationMemory(enabled=stateful)
        self.sessions: List[ClientSession] = []
        self.exit_stack = AsyncExitStack()
        self.client = genai.Client()
        self.model = model
        self.available_tools: List[ToolDefinition] = []
        self.tool_to_session: Dict[str, ClientSession] = {}
        self.config = genai_types.GenerateContentConfig(
            system_instruction="You are a helpful chatbot."
        )
        self.banned_keys = {"$schema", "$id", "$defs", "definitions", "$ref", "exclusiveMaximum", "exclusiveMinimum"}
        if model.startswith("gemini"):
            self.banned_keys.update({"additionalProperties", "additional_properties"})

    @staticmethod
    def mcp_tools_to_llm_function_decls(mcp_tools, banned_keys=None) -> List[ToolDefinition]:
        """
        Convert MCP list_tools().tools -> list[dict] with standard LLM function declaration format:
            [{"name": ..., "description": ..., "parameters": {...}}, ...]
        """
        tool_defs = []

        for tool in (mcp_tools or []):
            schema = copy.deepcopy(tool.inputSchema) if getattr(tool, "inputSchema", None) else None
            # FastMCP typically already provides: {"type": "object", "properties":..., "required":[...]}

            if not schema:  # Fallback to an empty object schema
                schema = {"type": "object", "properties": {}}
            if schema.get("type") != "object":  # Wrap non-object schemas in an object if needed (rare)
                schema = {"type": "object", "properties": {"value": schema}, "required": ["value"]}

            schema = MCPChatBot.remove_schema_keys(schema, banned_keys)

            tool_defs.append(ToolDefinition(
                name=tool.name,
                description=tool.description or "",
                parameters=schema,
            ))

        return tool_defs

    @staticmethod
    def remove_schema_keys(schema, banned_keys=None):
        """Return a copy of the JSON schema with banned_keys stripped recursively."""
        if banned_keys is None:
            banned_keys = set()
        if isinstance(schema, dict):
            return {
                key: MCPChatBot.remove_schema_keys(value, banned_keys)
                for key, value in schema.items()
                if key not in banned_keys
            }
        if isinstance(schema, list):
            return [MCPChatBot.remove_schema_keys(item, banned_keys) for item in schema]
        return schema

    async def connect_to_server(self, server_name: str, server_config: dict) -> None:
        """Connect to a single MCP server."""
        try:
            server_params = StdioServerParameters(**server_config)
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            read, write = stdio_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()
            self.sessions.append(session)

            # List available tools for this session
            response = await session.list_tools()
            tools = response.tools or []
            print(f"\nConnected to {server_name} with tools:", [tool.name for tool in tools])

            new_tools = self.mcp_tools_to_llm_function_decls(response.tools, self.banned_keys)
            if new_tools:
                self.available_tools.extend(new_tools)
                for tool in new_tools:
                    self.tool_to_session[tool.name] = session
            function_decls = [
                tool.to_llm_tool() if isinstance(tool, ToolDefinition) else tool for tool in self.available_tools
            ]
            self.config = genai_types.GenerateContentConfig(
                tools=[genai_types.Tool(function_declarations=function_decls)],
                system_instruction="You are a helpful chatbot with access to MCP tools."
            )
            print(new_tools)
        except Exception as e:
            print(f"Failed to connect to {server_name}: {e}")

    async def connect_to_servers(self):
        """Connect to all configured MCP servers."""
        try:
            with open("server_config.json", "r") as file:
                data = json.load(file)

            servers = data.get("mcpServers", {})

            for server_name, server_config in servers.items():
                await self.connect_to_server(server_name, server_config)
        except Exception as e:
            print(f"Error loading server configuration: {e}")
            raise

    # Process a single user query, handle tools, and return assistant output
    async def process_query(self, query: str):
        last_output_type = None  # "assistant" | "tool"

        if self.memory.enabled:
            contents = self.memory.get()  # Get messages by reference
            self.memory.add({"role": "user", "parts": [{"text": query}]})
        else:
            contents = [{"role": "user", "parts": [{"text": query}]}]

        while True:

            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=self.config
            )

            # Append assistant content
            candidate = response.candidates[0]
            if self.memory.enabled:
                self.memory.add(candidate.content)
            else:
                contents.append(candidate.content)
            parts = candidate.content.parts or []

            output_text = ""
            function_call = None
            for part in parts:

                # Stream text response
                if hasattr(part, "text") and part.text:
                    output_text += part.text
                    print(f"\nAssistant: {part.text}")
                    last_output_type = "assistant"

                # Check for tool call response
                if hasattr(part, "function_call") and part.function_call:
                    function_call = part.function_call

            if not function_call:
                return output_text

            # Execute tool
            tool_name = function_call.name
            tool_args = dict(function_call.args or {})
            if last_output_type != "tool":
                last_output_type = "tool"
                print()  # newline
            print(f"(Calling {tool_name} with {tool_args})")
            session = self.tool_to_session[tool_name]
            result = await session.call_tool(tool_name, arguments=tool_args)

            # Append tool result
            function_response_part = genai_types.Part.from_function_response(
                name=tool_name,
                response={"result": result}
            )

            tool_response = genai_types.Content(
                role="user",
                parts=[function_response_part]
            )

            if self.memory.enabled:
                self.memory.add(tool_response)
            else:
                contents.append(tool_response)

    # Interactive CLI chat loop. Type 'quit' to exit.
    async def chat_loop(self):

        print("\nMCP Chatbot Started!")
        print("Type your queries or 'quit' to exit.")
        while True:
            try:
                query = input("\nQuery: ").strip()
                if query.lower() == "quit":
                    break
                await self.process_query(query)
            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """Cleanly close all resources using AsyncExitStack."""
        await self.exit_stack.aclose()


async def main():
    parser = argparse.ArgumentParser(description="MCP chatbot client")
    parser.add_argument("--query", type=str, default=None, help="Run a single query and exit")
    args = parser.parse_args()

    chatbot = MCPChatBot()
    try:
        await chatbot.connect_to_servers()
        if args.query:
            output = await chatbot.process_query(args.query)
            if output:
                print(output)
        else:
            await chatbot.chat_loop()
    finally:
        await chatbot.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
