import ast
import inspect
import json
import os
from pprint import pprint
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Union, Callable, Type, get_type_hints

from fastmcp import Client, FastMCP
from google import genai
from google.genai import types
from openai import AsyncOpenAI


@dataclass
class FunctionDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]
    required: List[str]
    # Store the actual callable if provided
    callable: Optional[Callable] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FunctionDefinition":
        return cls(
            name=data["name"],
            description=data["description"],
            parameters=data["parameters"],
            required=data["parameters"].get("required", []),
        )

    @classmethod
    def from_callable(cls, func: Callable) -> "FunctionDefinition":
        """Create a FunctionDefinition from a callable object."""
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)

        parameters = {}
        required_params = []

        # Type mapping from Python types to JSON schema types
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
            datetime: "string",
            date: "string",
            # Add more type mappings as needed
        }

        def get_type_info(param_type: Type) -> Dict[str, Any]:
            """Get JSON schema type info for a Python type."""
            # Handle Optional types
            if (
                getattr(param_type, "__origin__", None) is Union
                and type(None) in param_type.__args__
            ):
                actual_type = next(
                    t for t in param_type.__args__ if t is not type(None)
                )
                return get_type_info(actual_type)

            # Handle List types
            if getattr(param_type, "__origin__", None) is list:
                item_type = param_type.__args__[0]
                return {
                    "type": "array",
                    "items": {"type": type_map.get(item_type, "string")},
                }

            # Handle Dict types
            if getattr(param_type, "__origin__", None) is dict:
                return {"type": "object"}

            # Handle basic types
            base_type = type_map.get(param_type, "string")
            type_info = {"type": base_type}

            # Add format for special string types
            if param_type in (datetime, date):
                type_info["format"] = "date-time" if param_type is datetime else "date"

            return type_info

        # Process parameters
        for name, param in sig.parameters.items():
            param_type = type_hints.get(name, str)
            type_info = get_type_info(param_type)

            parameters[name] = type_info

            # Check if parameter is required
            if param.default == inspect.Parameter.empty:
                required_params.append(name)
            else:
                # Add default value to schema if available
                parameters[name]["default"] = param.default

        # Create the function definition
        return cls(
            name=func.__name__,
            description=func.__doc__ or "No description provided.",
            parameters={
                "type": "object",
                "properties": parameters,
                "required": required_params,
            },
            required=required_params,
            callable=func,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class MCPFunctionClient:
    """Client for managing MCP server connections and tool discovery."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the MCP Function Client.

        Args:
            config: MCP configuration dictionary with server definitions
        """
        self.config = config or {}
        self.clients: Dict[str, Client] = {}
        self.tools: Dict[str, Dict[str, Any]] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize connections to all configured MCP servers."""
        if self._initialized:
            return

        for server_name, server_config in self.config.get("mcpServers", {}).items():
            try:
                temp_server_config = {
                    "mcpServers": {server_name: server_config}}
                client = Client(temp_server_config)

                async with client:
                    # Discover tools for this server
                    tools = await client.list_tools()
                self.clients[server_name] = client

                for tool in tools:
                    tool_name = f"{server_name}_{tool.name}"
                    self.tools[tool_name] = {
                        "server": server_name, "tool": tool}
            except Exception as e:
                print(f"Failed to initialize MCP server {server_name}: {e}")

        self._initialized = True

    async def cleanup(self) -> None:
        """Clean up all MCP server connections."""
        for client in self.clients.values():
            try:
                await client.__aexit__(None, None, None)
            except Exception as e:
                print(f"Error cleaning up MCP client: {e}")
        self.clients.clear()
        self.tools.clear()
        self._initialized = False

    def get_tool_definition(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get the definition of an MCP tool."""
        return self.tools.get(tool_name)

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Execute an MCP tool.

        Args:
            tool_name: Name of the tool to execute (format: server_name_tool_name)
            arguments: Arguments to pass to the tool

        Returns:
            The result of the tool execution
        """
        if not self._initialized:
            await self.initialize()

        tool_info = self.tools.get(tool_name)
        if not tool_info:
            raise ValueError(f"Unknown MCP tool: {tool_name}")

        server_name = tool_info["server"]
        client = self.clients.get(server_name)
        if not client:
            raise ValueError(f"No client found for server: {server_name}")

        try:
            async with client:
                result = await client.call_tool(tool_info["tool"].name, arguments)
                print(f"Result: {result}")
                # result có thể là CallToolResult hoặc list các kết quả

                def _extract_text(res: Any) -> str:
                    texts: List[str] = []
                    content = getattr(res, "content", None)
                    # content thường là list các block có thuộc tính .text
                    if isinstance(content, list):
                        for item in content:
                            text = getattr(item, "text", None)
                            if text:
                                texts.append(str(text))
                            elif isinstance(item, str):
                                texts.append(item)
                            elif isinstance(item, dict) and "text" in item:
                                texts.append(str(item["text"]))
                    elif isinstance(content, str):
                        texts.append(content)
                    return "\n".join(t for t in texts if t).strip()

                if result is None:
                    return ""
                if isinstance(result, list):
                    pieces = [_extract_text(r) for r in result]
                    return "\n".join(p for p in pieces if p)
                return _extract_text(result)

        except Exception as e:
            raise RuntimeError(f"Failed to execute MCP tool {tool_name}: {e}")

    @asynccontextmanager
    async def managed(self):
        """Context manager for MCP client lifecycle."""
        try:
            await self.initialize()
            yield self
        finally:
            await self.cleanup()
