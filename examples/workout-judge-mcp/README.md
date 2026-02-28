# Workout Judge (MCP Client)

AI-powered exercise form analysis using Claude — this version uses the **MCP Video Server** as a tool provider instead of importing video processing code directly.

## How It Differs from `workout-judge`

| | `workout-judge` | `workout-judge-mcp` |
|---|---|---|
| Video tools | Defined locally as Pydantic AI tools | Provided by MCP Video Server |
| Tool source | `FrameExtractor` + `GridCompositor` imported as Python library | `MCPServerStdio` subprocess |
| Available tools | 3 (overview, section, precise frame) | All 14 MCP server tools |
| Agent deps | `VideoAnalysisDeps` with extractor/compositor | None (tools come from MCP) |

## Setup

```bash
# From the repo root
uv sync

# Set your API key
export ANTHROPIC_API_KEY=your_key_here

# Run
uv run workout-judge-mcp analyze /path/to/video.mp4
```

The MCP server is started automatically as a subprocess — no manual server setup needed.

## How It Works

1. The CLI resolves the video path and creates an `MCPServerStdio` pointing at `mcp_video_server`
2. `MCP_VIDEO_ROOT` is set to the video's parent directory
3. `MCP_VIDEO_DEBUG=1` is enabled so debug output is saved
4. The Pydantic AI agent receives all 14 MCP tools via the `toolsets` parameter
5. The prompt tells Claude which filename to use with the tools
6. Claude calls MCP tools (overview, section, precise frame, etc.) and receives images back
7. Structured `WorkoutAnalysis` output is rendered with Rich

## Dependencies

This example depends on [mcp-video-server](../../packages/mcp-video-server/) which is launched as a stdio subprocess.
