# MCP Deep Video Server

A monorepo containing a reusable **MCP Video Analysis Server** and example **Workout Judge** CLI applications.

## Packages

### [`packages/mcp-video-server`](packages/mcp-video-server/)

A Model Context Protocol (MCP) server providing 14 tools for LLM-driven video analysis: frame extraction, motion detection, scene segmentation, audio transcription, and frame annotation. Designed for Claude but works with any MCP-compatible client.

See [`doc/tool_index.md`](doc/tool_index.md) for a full reference of all available tools.

### [`examples/workout-judge`](examples/workout-judge/)

AI-powered exercise form analysis using Claude via Pydantic AI. Uses `FrameExtractor` and `GridCompositor` directly as Python imports with three custom Pydantic AI tools.

### [`examples/workout-judge-mcp`](examples/workout-judge-mcp/)

Same workout analysis, but connects to the MCP Video Server as a subprocess via `MCPServerStdio`. All 14 MCP tools are available to the agent through the `toolsets` parameter — no local tool definitions needed.

| | `workout-judge` | `workout-judge-mcp` |
|---|---|---|
| Video tools | Defined locally as Pydantic AI tools | Provided by MCP Video Server |
| Tool source | `FrameExtractor` + `GridCompositor` imported as Python library | `MCPServerStdio` subprocess |
| Available tools | 3 (overview, section, precise frame) | All 14 MCP server tools |
| Agent deps | `VideoAnalysisDeps` with extractor/compositor | None (tools come from MCP) |

## Quick Start

```bash
# Install all packages
uv sync

# Set your API key
export ANTHROPIC_API_KEY=your_key_here

# Run workout-judge (direct Python imports)
uv run workout-judge analyze example_videos/sample.mov

# Run workout-judge-mcp (MCP server as subprocess)
uv run workout-judge-mcp analyze example_videos/sample.mov
```

## Running the MCP Server

### Subprocess mode (stdio)

This is the default transport. The server communicates over stdin/stdout and is typically launched by an MCP client automatically.

```bash
# Run directly
MCP_VIDEO_ROOT=./example_videos uv run python -m mcp_video_server

# Or via the entry point
MCP_VIDEO_ROOT=./example_videos uv run mcp-video-server
```

### HTTP mode (SSE)

For remote or multi-client scenarios, run the server over HTTP using the MCP CLI:

```bash
# Install the mcp CLI if needed
uv pip install mcp[cli]

# Start an SSE server on port 8080
MCP_VIDEO_ROOT=./example_videos uv run mcp run --transport sse --port 8080 mcp_video_server.server:create_server
```

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MCP_VIDEO_ROOT` | Yes | Directory containing video files |
| `MCP_VIDEO_DEBUG` | No | Set to `1` to enable debug output |
| `MCP_VIDEO_DEBUG_DIR` | No | Custom debug output directory (default: `MCP_VIDEO_ROOT/.mcp_debug`) |
| `MCP_VIDEO_CACHE_DIR` | No | Custom cache directory (default: `MCP_VIDEO_ROOT/.mcp_cache`) |
| `GROQ_API_KEY` | No | Groq API key for fast audio transcription |

### Claude Desktop configuration

Add this to your Claude Desktop `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "video": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/workout-judge", "python", "-m", "mcp_video_server"],
      "env": {
        "MCP_VIDEO_ROOT": "/path/to/your/videos"
      }
    }
  }
}
```

### Claude Code configuration

The repo includes an `.mcp.json` file that configures the server for Claude Code. Enable it with:

```bash
# The .mcp.json is already present — just update MCP_VIDEO_ROOT if needed
# Claude Code will auto-detect and offer to enable the server
```

## Validating the MCP Server

Use the MCP Inspector to interactively test tools without an LLM:

```bash
# Install the inspector
npx @anthropic-ai/mcp-inspector

# In the inspector UI:
# 1. Set transport to "stdio"
# 2. Command: uv
# 3. Args: run python -m mcp_video_server
# 4. Environment: MCP_VIDEO_ROOT=/path/to/videos
# 5. Click "Connect"
# 6. Browse tools, call list_videos, get_video_overview, etc.
```

Or test programmatically:

```bash
# Verify the server starts and lists tools
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}' | MCP_VIDEO_ROOT=./example_videos uv run python -m mcp_video_server
```

## Testing VideoProcessor in Isolation

Verify frame extraction and grid composition without an API key:

```bash
uv run python -c "
from mcp_video_server import FrameExtractor, GridCompositor
ext = FrameExtractor('example_videos/sample.mov')
frames = ext.extract_key_frames(8)
GridCompositor().create_grid_image(frames).save('/tmp/grid_test.jpg')
print('Open /tmp/grid_test.jpg to verify')
"
```

## Repository Structure

```
workout-judge/
├── pyproject.toml                     # uv workspace root
├── packages/
│   └── mcp-video-server/             # MCP server (14 tools)
│       ├── pyproject.toml
│       └── src/mcp_video_server/
├── examples/
│   ├── workout-judge/                 # CLI example (direct imports)
│   │   ├── pyproject.toml
│   │   └── src/workout_judge/
│   └── workout-judge-mcp/            # CLI example (MCP client)
│       ├── pyproject.toml
│       └── src/workout_judge_mcp/
└── doc/
    ├── mcp_video_server_spec.md       # Full server specification
    └── tool_index.md                  # Tool reference
```

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- ffmpeg (for audio transcription)
- An Anthropic API key (for workout-judge examples)

## Video Format Notes

- Most H.264/AVC MP4 and MOV files work out of the box
- H.265/HEVC may not be supported by OpenCV on all platforms. Pre-convert with:
  ```bash
  ffmpeg -i input.mp4 -c:v libx264 -crf 18 output.mp4
  ```

## License

MIT
