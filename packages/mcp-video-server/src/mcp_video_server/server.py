"""MCP Video Server — wiring and initialization."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from mcp.server import Server

from .cache import CacheManager
from .debug import DebugWriter
from .extractor import FrameExtractor
from .frame_diff import FrameDiffPipeline
from .resolver import VideoResolver
from .transcription import create_backend


def _ensure_gitignore(root: Path, entries: list[str]) -> None:
    """Append entries to .gitignore if a .git dir exists."""
    if not (root / ".git").is_dir():
        return
    gitignore = root / ".gitignore"
    existing = gitignore.read_text() if gitignore.exists() else ""
    lines = existing.splitlines()
    added = False
    for entry in entries:
        if entry not in lines:
            lines.append(entry)
            added = True
    if added:
        gitignore.write_text("\n".join(lines) + "\n")


def create_server() -> Server:
    """Create and configure the MCP video server."""
    # Validate MCP_VIDEO_ROOT
    video_root = os.environ.get("MCP_VIDEO_ROOT")
    if not video_root:
        print(
            "Server misconfigured: MCP_VIDEO_ROOT environment variable is not set",
            file=sys.stderr,
        )
        sys.exit(1)

    root_path = Path(video_root).resolve()
    if not root_path.is_dir():
        print(
            f"MCP_VIDEO_ROOT is not a directory: {root_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Config
    cache_dir = os.environ.get("MCP_VIDEO_CACHE_DIR", str(root_path / ".mcp_cache"))
    debug_dir = os.environ.get("MCP_VIDEO_DEBUG_DIR", str(root_path / ".mcp_debug"))
    global_debug = os.environ.get("MCP_VIDEO_DEBUG", "0") == "1"

    # Create dirs
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    Path(debug_dir).mkdir(parents=True, exist_ok=True)

    # Auto-manage .gitignore
    _ensure_gitignore(root_path, [".mcp_cache", ".mcp_debug"])

    # Instantiate shared objects
    resolver = VideoResolver(root_path)
    cache = CacheManager(cache_dir)
    frame_diff = FrameDiffPipeline(cache)
    debug = DebugWriter(debug_dir, global_debug)

    # Transcription backend
    try:
        transcription = create_backend()
    except Exception:
        transcription = None

    # Create MCP server
    server = Server("mcp-video-server")

    # Store shared objects on server for tools to access
    server._video_root = root_path  # type: ignore[attr-defined]
    server._resolver = resolver  # type: ignore[attr-defined]
    server._cache = cache  # type: ignore[attr-defined]
    server._frame_diff = frame_diff  # type: ignore[attr-defined]
    server._debug = debug  # type: ignore[attr-defined]
    server._transcription = transcription  # type: ignore[attr-defined]

    # Log startup config
    tx_backend = transcription.backend_name if transcription else "none"
    print(f"MCP Video Server starting", file=sys.stderr)
    print(f"  Root: {root_path}", file=sys.stderr)
    print(f"  Cache: {cache_dir}", file=sys.stderr)
    print(f"  Debug: {debug_dir} (enabled={global_debug})", file=sys.stderr)
    print(f"  Transcription: {tx_backend}", file=sys.stderr)

    # Register tools
    from .tools import register_all_tools
    register_all_tools(server)

    return server
