"""Tool: list_videos."""

from __future__ import annotations

import json
from datetime import datetime

from mcp.server import Server
from mcp.types import TextContent, Tool

from ..extractor import FrameExtractor
from . import tool_def


async def _list_videos(server: Server, arguments: dict) -> list[TextContent]:
    resolver = server._resolver  # type: ignore[attr-defined]
    cache = server._cache  # type: ignore[attr-defined]
    root = server._video_root  # type: ignore[attr-defined]

    subdirectory = arguments.get("subdirectory")
    include_metadata = arguments.get("include_metadata", False)
    include_cache_status = arguments.get("include_cache_status", True)

    try:
        files = resolver.list_video_files(subdirectory)
    except ValueError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    result_files = []
    total_size = 0.0

    for filename in files:
        video_path = resolver.resolve(filename)
        stat = video_path.stat()
        size_mb = round(stat.st_size / (1024 * 1024), 1)
        total_size += size_mb

        entry: dict = {
            "filename": filename,
            "size_mb": size_mb,
            "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%dT%H:%M:%S"),
        }

        if include_cache_status:
            entry["cached"] = cache.get_cache_status(filename)

        if include_metadata:
            cached_meta = cache.read_metadata(filename, video_path)
            if cached_meta:
                entry["metadata"] = {
                    "duration_seconds": cached_meta.get("duration_seconds"),
                    "resolution": cached_meta.get("resolution"),
                    "fps": cached_meta.get("fps"),
                }
            else:
                try:
                    ext = FrameExtractor(video_path)
                    meta = ext.get_metadata()
                    entry["metadata"] = {
                        "duration_seconds": meta["duration_seconds"],
                        "resolution": meta["resolution"],
                        "fps": meta["fps"],
                    }
                except Exception:
                    entry["metadata"] = None

        result_files.append(entry)

    result = {
        "root": str(root),
        "subdirectory": subdirectory,
        "files": result_files,
        "total_files": len(result_files),
        "total_size_mb": round(total_size, 1),
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


tool_def(
    Tool(
        name="list_videos",
        description=(
            "List video files available in the root directory. Returns filenames "
            "in the exact format expected by all other tools. Call this first in "
            "any session to discover available videos."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "subdirectory": {
                    "type": "string",
                    "description": 'null = root only; specific subdir name; "**" = recursive',
                },
                "include_metadata": {
                    "type": "boolean",
                    "default": False,
                    "description": "Include duration, resolution, fps per file",
                },
                "include_cache_status": {
                    "type": "boolean",
                    "default": True,
                    "description": "Show which cache files exist for each video",
                },
            },
        },
    ),
    _list_videos,
)
