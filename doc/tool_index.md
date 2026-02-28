# MCP Video Server — Tool Index

All 14 tools provided by `mcp-video-server`. Each tool is callable via the MCP protocol using any compatible client (Claude Desktop, Claude Code, MCP Inspector, Pydantic AI, etc.).

---

## Discovery

### `list_videos`

List video files available in the root directory. Returns filenames in the exact format expected by all other tools. **Call this first** in any session to discover available videos.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `subdirectory` | string | No | `null` = root only; specific subdir name; `"**"` = recursive |
| `include_metadata` | boolean | No | Include duration, resolution, fps per file |
| `include_cache_status` | boolean | No | Show which cache files exist for each video |

**Returns:** Text listing of available video files.

---

## Metadata

### `get_video_metadata`

Returns structured metadata about a video file: duration, fps, resolution, codec, audio info, rotation. Lightweight — reads from cache if available. Call before analysis to get baseline facts.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `filename` | string | Yes | Video filename (from `list_videos`) |
| `debug` | boolean | No | Save debug output |

**Returns:** JSON with `duration_seconds`, `fps`, `width`, `height`, `codec`, `has_audio`, `rotation`.

---

## Visual Extraction

### `get_video_overview`

Returns a JPEG grid image of frames spanning the entire video. Each cell is labeled with its timestamp. Use this first to understand the full structure — count reps, identify phases, spot patterns.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `filename` | string | Yes | Video filename (from `list_videos`) |
| `max_frames` | integer | No | Number of frames, 4–24 (default: 8) |
| `frame_selection` | `"even"` \| `"keyframe"` | No | `"even"` = evenly spaced (default); `"keyframe"` = Bhattacharyya histogram-based selection |
| `debug` | boolean | No | Save debug output |

**Returns:** JPEG grid image with timestamp labels.

### `get_video_section`

Returns a detailed grid of frames from a specific time range. Use after `get_video_overview` to zoom into a specific phase, exercise, or suspicious moment.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `filename` | string | Yes | Video filename |
| `start_seconds` | number | Yes | Start of section in seconds |
| `end_seconds` | number | Yes | End of section in seconds |
| `max_frames` | integer | No | Number of frames, 2–16 (default: 6) |
| `frame_selection` | `"even"` \| `"keyframe"` | No | `"even"` (default) or `"keyframe"` (Bhattacharyya) |
| `debug` | boolean | No | Save debug output |

**Returns:** JPEG grid image of the specified section.

### `get_precise_frame`

Extracts a single full-resolution frame at an exact timestamp. Use for critical moments: maximum load position, form breaks, joint angles. Returns lossless PNG.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `filename` | string | Yes | Video filename |
| `timestamp_seconds` | number | Yes | Exact time in seconds (sub-frame precision via `CAP_PROP_POS_MSEC`) |
| `debug` | boolean | No | Save debug output |

**Returns:** Full-resolution PNG image.

### `compare_frames`

Extracts frames at multiple specific timestamps and returns them as a side-by-side grid. Use for rep-to-rep comparison — identify candidate timestamps via other tools, then call this to see them together.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `filename` | string | Yes | Video filename |
| `timestamps` | array of numbers | Yes | List of timestamps in seconds (2–12 entries) |
| `label` | string | No | Optional title for the grid |
| `debug` | boolean | No | Save debug output |

**Returns:** JPEG grid image with labeled timestamps.

---

## Motion Analysis

### `detect_motion_events`

Identifies timestamps where significant motion occurs. Returns events with start/peak/end timestamps and intensity. Use to skip directly to active moments without scanning via overview.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `filename` | string | Yes | Video filename |
| `sensitivity` | number | No | 0.0–1.0, higher = more sensitive (default: 0.5) |
| `min_gap_seconds` | number | No | Minimum time between events |
| `debug` | boolean | No | Save debug output |

**Returns:** JSON array of motion events with `start`, `peak`, `end`, `intensity` fields.

### `detect_scenes`

Identifies hard scene cuts or abrupt visual transitions. Use for segmenting multi-exercise videos, finding camera cuts, or identifying edit points.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `filename` | string | Yes | Video filename |
| `threshold_multiplier` | number | No | Higher = only hard cuts (default: 3.0) |
| `min_scene_seconds` | number | No | Minimum scene duration |
| `debug` | boolean | No | Save debug output |

**Returns:** JSON array of scene boundaries with timestamps.

### `detect_pauses`

Identifies timestamps where the subject is stationary. For movement analysis, pauses are often the most important: lockout, catch position, bottom of squat, top of deadlift.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `filename` | string | Yes | Video filename |
| `min_duration_seconds` | number | No | Minimum pause length |
| `sensitivity` | number | No | 0.0–1.0, higher = tolerates more residual movement |
| `debug` | boolean | No | Save debug output |

**Returns:** JSON array of pause periods with `start`, `end`, `duration` fields.

### `get_motion_timeline`

Returns a chart image showing motion intensity over time. Provides an instant visual map of where activity is concentrated. Requires `matplotlib` (`pip install mcp-video-server[charts]`).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `filename` | string | Yes | Video filename |
| `resolution_seconds` | number | No | Time bucket size (default: 0.5) |
| `debug` | boolean | No | Save debug output |

**Returns:** PNG chart image.

### `get_motion_heatmap`

Returns a full-resolution PNG showing where in the frame movement is spatially concentrated. Overlays a colored heatmap on a reference frame. For squats, shows hot zones at hips and barbell.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `filename` | string | Yes | Video filename |
| `start_seconds` | number | No | Start of range (`null` = beginning) |
| `end_seconds` | number | No | End of range (`null` = end) |
| `debug` | boolean | No | Save debug output |

**Returns:** PNG image with heatmap overlay.

---

## Annotation

### `annotate_frame`

Extracts a frame and draws lines, angle arcs, and text labels using provided coordinates. The LLM identifies key points from `get_precise_frame`, then calls this to produce an annotated image with form measurements.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `filename` | string | Yes | Video filename |
| `timestamp_seconds` | number | Yes | Timestamp in seconds |
| `lines` | array | No | Line segments: `[{"start": [x,y], "end": [x,y], "color": "red", "label": "..."}]` |
| `angles` | array | No | Angle arcs: `[{"vertex": [x,y], "start": [x,y], "end": [x,y], "label": "..."}]` |
| `labels` | array | No | Text labels: `[{"position": [x,y], "text": "..."}]` |
| `debug` | boolean | No | Save debug output |

**Returns:** PNG image with annotations drawn.

---

## Audio

### `get_audio_transcript`

Returns a time-aligned transcript of the video's audio. First call extracts and transcribes audio (cached for subsequent calls). Uses Groq API if `GROQ_API_KEY` is set, otherwise falls back to local Whisper.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `filename` | string | Yes | Video filename |
| `start_seconds` | number | No | Start of window (`null` = beginning) |
| `end_seconds` | number | No | End of window (`null` = end) |
| `word_level` | boolean | No | Include word-level timestamps |
| `debug` | boolean | No | Save debug output |

**Returns:** JSON transcript with segments and timestamps.

---

## Cache Management

### `clear_cache`

Clears cached data for one or all videos. Use when videos have been replaced or to recover disk space.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `filename` | string | No | Video filename (`null` = clear all) |
| `cache_type` | `"all"` \| `"transcript"` \| `"frame_diffs"` \| `"metadata"` | No | Type of cache to clear (default: `"all"`) |

**Returns:** Text confirmation of cleared cache entries.

---

## Recommended Workflow

For analyzing a video, follow this sequence:

1. **`list_videos`** — discover available files
2. **`get_video_metadata`** — get duration, resolution, fps
3. **`get_video_overview`** — see the full video at a glance
4. **`detect_motion_events`** — find active moments
5. **`get_video_section`** — zoom into specific phases
6. **`get_precise_frame`** — examine critical moments at full resolution
7. **`compare_frames`** — compare rep-to-rep or before/after
8. **`annotate_frame`** — measure angles and draw reference lines
