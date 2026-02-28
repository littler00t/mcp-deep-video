"""MCP tool registration — central registry pattern."""

from __future__ import annotations

from typing import Any, Callable, Coroutine

from mcp.server import Server
from mcp.types import Tool

# Central registry
_TOOLS: list[Tool] = []
_HANDLERS: dict[str, Callable[..., Coroutine]] = {}


def tool_def(tool: Tool, handler: Callable[..., Coroutine]) -> None:
    """Register a tool definition and its handler."""
    _TOOLS.append(tool)
    _HANDLERS[tool.name] = handler


def register_all_tools(server: Server) -> None:
    """Import all tool modules and register with the MCP server."""
    # Import modules to trigger tool_def() calls
    from . import annotation, audio, cache_tools, listing, metadata, motion, visual

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return list(_TOOLS)

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list:
        handler = _HANDLERS.get(name)
        if handler is None:
            from mcp.types import TextContent
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        return await handler(server, arguments)
