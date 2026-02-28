"""Tool: get_video_metadata."""

from __future__ import annotations

import json
from datetime import datetime

from mcp.server import Server
from mcp.types import TextContent, Tool

from ..extractor import FrameExtractor
from . import tool_def


async def _get_video_metadata(server: Server, arguments: dict) -> list[TextContent]:
    resolver = server._resolver  # type: ignore[attr-defined]
    cache = server._cache  # type: ignore[attr-defined]
    debug_writer = server._debug  # type: ignore[attr-defined]

    filename = arguments.get("filename", "")
    debug = arguments.get("debug", False)

    try:
        video_path = resolver.resolve(filename)
    except ValueError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    # Check cache
    cached = cache.read_metadata(filename, video_path)
    if cached:
        cached["cached"] = True
        cached["filename"] = filename
        return [TextContent(type="text", text=json.dumps(cached, indent=2))]

    # Compute metadata
    ext = FrameExtractor(video_path)
    meta = ext.get_metadata()
    meta["filename"] = filename
    meta["cached"] = False
    meta["modified"] = datetime.fromtimestamp(meta["modified"]).strftime("%Y-%m-%dT%H:%M:%S")

    # Write to cache
    cache.write_metadata(filename, video_path, meta)

    # Debug output
    if debug_writer.is_active(debug):
        d = debug_writer.get_debug_dir(filename, "get_video_metadata")
        debug_writer.save_metadata(d, {"tool": "get_video_metadata", "filename": filename, "result": meta})

    return [TextContent(type="text", text=json.dumps(meta, indent=2))]


tool_def(
    Tool(
        name="get_video_metadata",
        description=(
            "Returns structured metadata about a video file: duration, fps, resolution, "
            "codec, audio info, rotation. Lightweight — reads from cache if available. "
            "Call before analysis to give baseline facts."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Video filename (from list_videos)"},
                "debug": {"type": "boolean", "default": False, "description": "Save debug output"},
            },
            "required": ["filename"],
        },
    ),
    _get_video_metadata,
)
