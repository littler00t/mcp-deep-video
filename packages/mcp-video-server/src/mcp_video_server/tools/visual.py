"""Tools: get_video_overview, get_video_section, get_precise_frame, compare_frames."""

from __future__ import annotations

import base64
import json
import math
import time

from mcp.server import Server
from mcp.types import ImageContent, TextContent, Tool

from ..compositor import GridCompositor
from ..extractor import FrameExtractor
from . import tool_def


def _make_extractor_and_compositor(server: Server, filename: str):
    resolver = server._resolver  # type: ignore[attr-defined]
    video_path = resolver.resolve(filename)
    ext = FrameExtractor(video_path)
    comp = GridCompositor()
    return ext, comp, video_path


# --- get_video_overview ---

async def _get_video_overview(server: Server, arguments: dict) -> list:
    filename = arguments.get("filename", "")
    max_frames = arguments.get("max_frames", 20)
    frame_selection = arguments.get("frame_selection", "even")
    debug = arguments.get("debug", False)

    max_frames = max(4, min(max_frames, 24))

    try:
        ext, comp, video_path = _make_extractor_and_compositor(server, filename)
    except ValueError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    start_time = time.time()
    meta = ext.get_metadata()

    if frame_selection == "keyframe":
        frames = ext.extract_key_frames(max_frames)
    else:
        frames = ext.extract_frames_evenly(max_frames)

    cols = math.ceil(math.sqrt(len(frames)))
    grid = comp.create_grid_image(frames, cols=cols)
    grid_bytes = comp.image_to_bytes(grid, format="JPEG", quality=85)
    duration_ms = int((time.time() - start_time) * 1000)

    rows = math.ceil(len(frames) / cols) if cols > 0 else 1
    description = (
        f"Full video overview | Duration: {meta['duration_seconds']:.1f}s | "
        f"FPS: {meta['fps']:.1f} | Resolution: {meta['resolution']} | "
        f"Frames shown: {len(frames)} | Grid: {cols}x{rows}"
    )

    result_meta = {
        "filename": filename,
        "duration_seconds": meta["duration_seconds"],
        "fps": meta["fps"],
        "resolution": meta["resolution"],
        "frames_shown": len(frames),
        "frame_timestamps": [round(ts, 2) for _, ts in frames] if frames else [],
        "grid_cols": cols,
        "grid_rows": rows,
        "frame_selection": frame_selection,
    }

    # Debug
    debug_writer = server._debug  # type: ignore[attr-defined]
    if debug_writer.is_active(debug):
        d = debug_writer.get_debug_dir(filename, "get_video_overview")
        debug_writer.save_result_image(d, grid_bytes, "JPEG")
        debug_writer.save_metadata(d, {
            "tool": "get_video_overview",
            "filename": filename,
            "params": {"max_frames": max_frames, "frame_selection": frame_selection},
            "computed": result_meta,
            "duration_ms": duration_ms,
        })
        debug_writer.save_raw_frames(d, frames)

    b64 = base64.standard_b64encode(grid_bytes).decode("ascii")
    return [
        TextContent(type="text", text=f"{description}\n\n{json.dumps(result_meta)}"),
        ImageContent(type="image", data=b64, mimeType="image/jpeg"),
    ]


tool_def(
    Tool(
        name="get_video_overview",
        description=(
            "Returns a JPEG grid image of evenly-distributed frames spanning the entire "
            "video. Each cell is labeled with its timestamp. Use this first to understand "
            "the full structure — count reps, identify phases, spot patterns."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Video filename (from list_videos)"},
                "max_frames": {"type": "integer", "default": 20, "description": "Number of frames (4-24)"},
                "frame_selection": {
                    "type": "string",
                    "enum": ["even", "keyframe"],
                    "default": "even",
                    "description": "Frame selection method: 'even' (default) or 'keyframe' (Bhattacharyya)",
                },
                "debug": {"type": "boolean", "default": False},
            },
            "required": ["filename"],
        },
    ),
    _get_video_overview,
)


# --- get_video_section ---

async def _get_video_section(server: Server, arguments: dict) -> list:
    filename = arguments.get("filename", "")
    start_seconds = arguments.get("start_seconds", 0.0)
    end_seconds = arguments.get("end_seconds", 0.0)
    max_frames = arguments.get("max_frames", 10)
    frame_selection = arguments.get("frame_selection", "even")
    debug = arguments.get("debug", False)

    max_frames = max(2, min(max_frames, 16))

    try:
        ext, comp, video_path = _make_extractor_and_compositor(server, filename)
    except ValueError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    meta = ext.get_metadata()
    start_seconds = max(0.0, start_seconds)
    end_seconds = min(end_seconds, meta["duration_seconds"])

    if start_seconds >= end_seconds:
        return [TextContent(type="text", text=json.dumps({
            "error": f"Invalid time range: start_seconds ({start_seconds}) must be less than end_seconds ({end_seconds})"
        }))]

    start_time = time.time()

    if frame_selection == "keyframe":
        frames = ext.extract_key_frames(max_frames, start=start_seconds, end=end_seconds)
    else:
        frames = ext.extract_frames_evenly(max_frames, start=start_seconds, end=end_seconds)

    if not frames:
        return [TextContent(type="text", text=json.dumps({
            "error": f"No frames extracted from {start_seconds:.2f}s to {end_seconds:.2f}s"
        }))]

    cols = math.ceil(math.sqrt(len(frames)))
    grid = comp.create_grid_image(frames, cols=cols)
    grid_bytes = comp.image_to_bytes(grid, format="JPEG", quality=85)
    duration_ms = int((time.time() - start_time) * 1000)

    rows = math.ceil(len(frames) / cols) if cols > 0 else 1
    section_duration = end_seconds - start_seconds
    description = (
        f"Section {start_seconds:.2f}s-{end_seconds:.2f}s | "
        f"Duration: {section_duration:.1f}s | "
        f"Frames shown: {len(frames)} | Grid: {cols}x{rows}"
    )

    result_meta = {
        "filename": filename,
        "start_seconds": start_seconds,
        "end_seconds": end_seconds,
        "section_duration": section_duration,
        "frames_shown": len(frames),
        "frame_timestamps": [round(ts, 2) for _, ts in frames],
        "grid_cols": cols,
        "grid_rows": rows,
        "frame_selection": frame_selection,
    }

    debug_writer = server._debug  # type: ignore[attr-defined]
    if debug_writer.is_active(debug):
        d = debug_writer.get_debug_dir(filename, "get_video_section")
        debug_writer.save_result_image(d, grid_bytes, "JPEG")
        debug_writer.save_metadata(d, {
            "tool": "get_video_section",
            "filename": filename,
            "params": {"start_seconds": start_seconds, "end_seconds": end_seconds, "max_frames": max_frames},
            "computed": result_meta,
            "duration_ms": duration_ms,
        })
        debug_writer.save_raw_frames(d, frames)

    b64 = base64.standard_b64encode(grid_bytes).decode("ascii")
    return [
        TextContent(type="text", text=f"{description}\n\n{json.dumps(result_meta)}"),
        ImageContent(type="image", data=b64, mimeType="image/jpeg"),
    ]


tool_def(
    Tool(
        name="get_video_section",
        description=(
            "Returns a detailed grid of frames from a specific time range. "
            "Use after get_video_overview to zoom into a specific phase, exercise, "
            "or suspicious moment."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Video filename"},
                "start_seconds": {"type": "number", "description": "Start of section in seconds"},
                "end_seconds": {"type": "number", "description": "End of section in seconds"},
                "max_frames": {"type": "integer", "default": 10, "description": "Number of frames (2-16)"},
                "frame_selection": {
                    "type": "string",
                    "enum": ["even", "keyframe"],
                    "default": "even",
                    "description": "Frame selection: 'even' or 'keyframe' (Bhattacharyya)",
                },
                "debug": {"type": "boolean", "default": False},
            },
            "required": ["filename", "start_seconds", "end_seconds"],
        },
    ),
    _get_video_section,
)


# --- get_precise_frame ---

async def _get_precise_frame(server: Server, arguments: dict) -> list:
    filename = arguments.get("filename", "")
    timestamp_seconds = arguments.get("timestamp_seconds", 0.0)
    debug = arguments.get("debug", False)

    try:
        ext, comp, video_path = _make_extractor_and_compositor(server, filename)
    except ValueError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    meta = ext.get_metadata()
    ts = max(0.0, min(timestamp_seconds, meta["duration_seconds"]))
    frame = ext.extract_frame_at(ts)
    frame_bytes = comp.image_to_bytes(frame, format="PNG")

    ts_label = comp.format_timestamp(ts)
    description = f"Precise frame at {ts_label} ({ts:.3f}s) — {frame.width}x{frame.height}px PNG"

    result_meta = {
        "filename": filename,
        "requested_timestamp": timestamp_seconds,
        "actual_timestamp": ts,
        "width": frame.width,
        "height": frame.height,
    }

    debug_writer = server._debug  # type: ignore[attr-defined]
    if debug_writer.is_active(debug):
        d = debug_writer.get_debug_dir(filename, "get_precise_frame")
        debug_writer.save_result_image(d, frame_bytes, "PNG")
        debug_writer.save_metadata(d, {
            "tool": "get_precise_frame",
            "filename": filename,
            "params": {"timestamp_seconds": timestamp_seconds},
            "computed": result_meta,
        })

    b64 = base64.standard_b64encode(frame_bytes).decode("ascii")
    return [
        TextContent(type="text", text=f"{description}\n\n{json.dumps(result_meta)}"),
        ImageContent(type="image", data=b64, mimeType="image/png"),
    ]


tool_def(
    Tool(
        name="get_precise_frame",
        description=(
            "Extracts a single full-resolution frame at an exact timestamp. "
            "Use for critical moments: maximum load position, form breaks, "
            "joint angles. Returns lossless PNG."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Video filename"},
                "timestamp_seconds": {"type": "number", "description": "Exact time in seconds"},
                "debug": {"type": "boolean", "default": False},
            },
            "required": ["filename", "timestamp_seconds"],
        },
    ),
    _get_precise_frame,
)


# --- compare_frames ---

async def _compare_frames(server: Server, arguments: dict) -> list:
    filename = arguments.get("filename", "")
    timestamps = arguments.get("timestamps", [])
    label = arguments.get("label")
    debug = arguments.get("debug", False)

    if len(timestamps) < 2:
        return [TextContent(type="text", text=json.dumps({"error": "timestamps must have at least 2 entries"}))]
    if len(timestamps) > 12:
        timestamps = timestamps[:12]

    try:
        ext, comp, video_path = _make_extractor_and_compositor(server, filename)
    except ValueError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    meta = ext.get_metadata()
    duration = meta["duration_seconds"]
    warnings = []

    frames = []
    for ts in sorted(timestamps):
        actual_ts = max(0.0, min(ts, duration))
        if actual_ts != ts:
            warnings.append(f"Timestamp {ts}s clamped to {actual_ts}s")
        try:
            frame = ext.extract_frame_at(actual_ts)
            frames.append((frame, actual_ts))
        except ValueError:
            warnings.append(f"Could not extract frame at {ts}s")

    if not frames:
        return [TextContent(type="text", text=json.dumps({"error": "No frames could be extracted"}))]

    cols = math.ceil(math.sqrt(len(frames)))
    grid = comp.create_grid_image(frames, cols=cols)
    grid_bytes = comp.image_to_bytes(grid, format="JPEG", quality=85)

    ts_str = ", ".join(f"{ts:.2f}s" for _, ts in frames)
    description = f"Frame comparison | {len(frames)} frames | Timestamps: {ts_str}"
    if label:
        description = f"{label} | {description}"

    result_meta = {
        "filename": filename,
        "frames_shown": len(frames),
        "timestamps": [round(ts, 2) for _, ts in frames],
        "label": label,
    }
    if warnings:
        result_meta["warnings"] = warnings

    debug_writer = server._debug  # type: ignore[attr-defined]
    if debug_writer.is_active(debug):
        d = debug_writer.get_debug_dir(filename, "compare_frames")
        debug_writer.save_result_image(d, grid_bytes, "JPEG")
        debug_writer.save_metadata(d, {
            "tool": "compare_frames",
            "filename": filename,
            "params": {"timestamps": timestamps, "label": label},
            "computed": result_meta,
        })

    b64 = base64.standard_b64encode(grid_bytes).decode("ascii")
    return [
        TextContent(type="text", text=f"{description}\n\n{json.dumps(result_meta)}"),
        ImageContent(type="image", data=b64, mimeType="image/jpeg"),
    ]


tool_def(
    Tool(
        name="compare_frames",
        description=(
            "Extracts multiple specific frames and returns them as a side-by-side grid. "
            "Use for rep-to-rep comparison — identify candidate timestamps via other tools, "
            "then call this to see them together."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Video filename"},
                "timestamps": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "List of timestamps in seconds (2-12 entries)",
                },
                "label": {"type": "string", "description": "Optional title for the grid"},
                "debug": {"type": "boolean", "default": False},
            },
            "required": ["filename", "timestamps"],
        },
    ),
    _compare_frames,
)
