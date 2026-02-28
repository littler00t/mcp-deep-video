# MCP Video Analysis Server

A Model Context Protocol (MCP) server for detailed visual analysis of video files. Enables LLMs (primarily Claude) to extract frames, detect motion, transcribe audio, and annotate videos.

## Quick Start

```bash
# Install
uv pip install -e packages/mcp-video-server

# Run
MCP_VIDEO_ROOT=/path/to/videos python -m mcp_video_server
```

## Claude Desktop Configuration

```json
{
  "mcpServers": {
    "video": {
      "command": "python",
      "args": ["-m", "mcp_video_server"],
      "env": {
        "MCP_VIDEO_ROOT": "/path/to/videos"
      }
    }
  }
}
```

## Tools (14 total)

| Tool | Returns | Description |
|------|---------|-------------|
| `list_videos` | JSON | List available video files |
| `get_video_metadata` | JSON | Duration, fps, resolution, codec, audio info |
| `get_video_overview` | JPEG grid | Evenly-distributed frames across full video |
| `get_video_section` | JPEG grid | Frames within a time range |
| `get_precise_frame` | PNG | Single full-resolution frame at timestamp |
| `compare_frames` | JPEG grid | Side-by-side frame comparison |
| `detect_motion_events` | JSON | Timestamps of significant motion |
| `detect_scenes` | JSON | Scene cuts / transitions |
| `detect_pauses` | JSON | Stationary moments |
| `get_motion_timeline` | PNG chart | Motion intensity over time |
| `get_motion_heatmap` | PNG | Spatial motion concentration |
| `annotate_frame` | PNG | Draw lines, angles, labels on frame |
| `get_audio_transcript` | JSON | Time-aligned audio transcript |
| `clear_cache` | JSON | Clear cached data |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MCP_VIDEO_ROOT` | Yes | — | Root directory containing videos |
| `MCP_VIDEO_CACHE_DIR` | No | `{ROOT}/.mcp_cache` | Cache directory |
| `MCP_VIDEO_DEBUG_DIR` | No | `{ROOT}/.mcp_debug` | Debug output directory |
| `MCP_VIDEO_DEBUG` | No | `0` | Set to `1` for global debug output |
| `GROQ_API_KEY` | No | — | Use Groq API for transcription |

## Optional Dependencies

```bash
# Groq transcription (fast cloud-based)
pip install mcp-video-server[transcription]

# Local Whisper transcription
pip install mcp-video-server[whisper]

# Motion timeline charts
pip install mcp-video-server[charts]
```

## Python API

The core modules are importable for use outside the MCP server:

```python
from mcp_video_server import FrameExtractor, GridCompositor

ext = FrameExtractor("video.mp4")
frames = ext.extract_key_frames(8)
grid = GridCompositor().create_grid_image(frames)
grid.save("overview.jpg")
```
