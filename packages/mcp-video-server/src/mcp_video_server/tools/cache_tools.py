"""Tool: clear_cache."""

from __future__ import annotations

import json

from mcp.server import Server
from mcp.types import TextContent, Tool

from . import tool_def


async def _clear_cache(server: Server, arguments: dict) -> list[TextContent]:
    cache = server._cache  # type: ignore[attr-defined]
    frame_diff = server._frame_diff  # type: ignore[attr-defined]

    filename = arguments.get("filename")
    cache_type = arguments.get("cache_type", "all")

    try:
        cleared = cache.clear(filename=filename, cache_type=cache_type)
    except ValueError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    # Evict in-memory frame diff cache
    if cache_type in ("all", "frame_diffs"):
        if filename:
            frame_diff.evict(filename)
        else:
            frame_diff.evict()

    total_freed = sum(item["freed_mb"] for item in cleared)

    result = {
        "cleared": cleared,
        "total_freed_mb": round(total_freed, 2),
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


tool_def(
    Tool(
        name="clear_cache",
        description=(
            "Clears cached data for one or all videos. Use when videos have been "
            "replaced or to recover disk space."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Video filename (null = all)"},
                "cache_type": {
                    "type": "string",
                    "enum": ["all", "transcript", "frame_diffs", "metadata"],
                    "default": "all",
                    "description": "Type of cache to clear",
                },
            },
        },
    ),
    _clear_cache,
)
