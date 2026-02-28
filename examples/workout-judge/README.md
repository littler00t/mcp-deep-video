# Workout Judge

AI-powered exercise form analysis using Claude and MCP Video Server.

## How It Works

Workout Judge uses a Pydantic AI agent with Claude to analyze workout videos through a hierarchical drill-down strategy:

1. **Overview** — Get a grid of key frames spanning the entire video
2. **Section** — Zoom into specific exercise phases
3. **Precise** — Extract full-resolution frames at critical moments
4. **Analysis** — Structured output with technique score, observations, and recommendations

## Setup

```bash
# From the repo root
uv sync

# Set your API key
export ANTHROPIC_API_KEY=your_key_here

# Run
cd examples/workout-judge
workout-judge analyze /path/to/video.mp4
```

## Technique Scoring

| Score | Meaning |
|-------|---------|
| 1-3 | Significant injury risk |
| 4-6 | Functional but suboptimal |
| 7-8 | Good form, minor refinements |
| 9-10 | Competition-ready technique |

## Dependencies

This example depends on [mcp-video-server](../../packages/mcp-video-server/) for video processing primitives (`FrameExtractor`, `GridCompositor`).
