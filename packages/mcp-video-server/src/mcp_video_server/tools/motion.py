"""Tools: detect_motion_events, detect_scenes, detect_pauses, get_motion_timeline, get_motion_heatmap."""

from __future__ import annotations

import base64
import json
import math
import time

import cv2
import numpy as np
from mcp.server import Server
from mcp.types import ImageContent, TextContent, Tool
from PIL import Image

from ..compositor import GridCompositor
from ..extractor import FrameExtractor
from . import tool_def


def _get_deps(server: Server, filename: str):
    resolver = server._resolver  # type: ignore[attr-defined]
    video_path = resolver.resolve(filename)
    frame_diff = server._frame_diff  # type: ignore[attr-defined]
    debug_writer = server._debug  # type: ignore[attr-defined]
    return video_path, frame_diff, debug_writer


# --- detect_motion_events ---

async def _detect_motion_events(server: Server, arguments: dict) -> list[TextContent]:
    filename = arguments.get("filename", "")
    sensitivity = arguments.get("sensitivity", 0.5)
    min_gap_seconds = arguments.get("min_gap_seconds", 0.5)
    debug = arguments.get("debug", False)

    try:
        video_path, frame_diff, debug_writer = _get_deps(server, filename)
    except ValueError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    ext = FrameExtractor(video_path)
    meta = ext.get_metadata()
    fps = meta["fps"]
    duration = meta["duration_seconds"]

    diffs = frame_diff.get(filename, video_path)

    if len(diffs) == 0:
        return [TextContent(type="text", text=json.dumps({
            "filename": filename, "events": [], "total_events": 0,
        }))]

    baseline_mean = float(diffs.mean())
    baseline_std = float(diffs.std())
    threshold = baseline_mean + (1.0 - sensitivity) * baseline_std * 3

    above = diffs > threshold
    min_gap_frames = int(min_gap_seconds * fps)

    # Find contiguous regions above threshold, merging within min_gap
    events = []
    i = 0
    while i < len(above):
        if above[i]:
            start_idx = i
            end_idx = i
            while end_idx < len(above):
                # Extend while above or within gap
                if above[end_idx]:
                    end_idx += 1
                elif end_idx + min_gap_frames < len(above) and any(above[end_idx:end_idx + min_gap_frames]):
                    end_idx += 1
                else:
                    break
            # Find peak in this event
            segment = diffs[start_idx:end_idx]
            peak_offset = int(np.argmax(segment))
            peak_intensity = float(segment[peak_offset])

            events.append({
                "start_seconds": round(start_idx / fps, 2),
                "peak_seconds": round((start_idx + peak_offset) / fps, 2),
                "end_seconds": round(end_idx / fps, 2),
                "duration_seconds": round((end_idx - start_idx) / fps, 2),
                "peak_intensity": round(peak_intensity, 1),
                "intensity_normalized": round(peak_intensity / float(diffs.max()), 2) if diffs.max() > 0 else 0.0,
            })
            i = end_idx
        else:
            i += 1

    result = {
        "filename": filename,
        "events": events,
        "total_events": len(events),
        "sensitivity_used": sensitivity,
        "threshold_value": round(threshold, 1),
        "video_duration_seconds": round(duration, 2),
    }

    if debug_writer.is_active(debug):
        d = debug_writer.get_debug_dir(filename, "detect_motion_events")
        debug_writer.save_metadata(d, {"tool": "detect_motion_events", "filename": filename, "result": result})
        debug_writer.save_diff_scores(d, diffs.tolist())

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


tool_def(
    Tool(
        name="detect_motion_events",
        description=(
            "Identifies timestamps where significant motion occurs. Returns events "
            "with start/peak/end timestamps and intensity. Use to skip directly to "
            "active moments without scanning via overview."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "sensitivity": {"type": "number", "default": 0.5, "description": "0.0-1.0, higher = more sensitive"},
                "min_gap_seconds": {"type": "number", "default": 0.5, "description": "Min time between events"},
                "debug": {"type": "boolean", "default": False},
            },
            "required": ["filename"],
        },
    ),
    _detect_motion_events,
)


# --- detect_scenes ---

async def _detect_scenes(server: Server, arguments: dict) -> list[TextContent]:
    filename = arguments.get("filename", "")
    threshold_multiplier = arguments.get("threshold_multiplier", 5.0)
    min_scene_seconds = arguments.get("min_scene_seconds", 1.0)
    debug = arguments.get("debug", False)

    try:
        video_path, frame_diff, debug_writer = _get_deps(server, filename)
    except ValueError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    ext = FrameExtractor(video_path)
    meta = ext.get_metadata()
    fps = meta["fps"]
    duration = meta["duration_seconds"]

    diffs = frame_diff.get(filename, video_path)

    if len(diffs) == 0:
        return [TextContent(type="text", text=json.dumps({
            "filename": filename, "scenes": [{"scene_index": 0, "start_seconds": 0.0, "end_seconds": duration, "duration_seconds": duration, "cut_timestamp_seconds": None}],
            "total_scenes": 1,
        }))]

    # Rolling mean over 1-second window
    window = max(1, int(fps))
    rolling_mean = np.convolve(diffs, np.ones(window) / window, mode="same")

    # Find spikes
    min_gap_frames = int(min_scene_seconds * fps)
    cut_frames = []
    for i in range(1, len(diffs) - 1):
        if rolling_mean[i] > 0 and diffs[i] > rolling_mean[i] * threshold_multiplier:
            # Validate: spike at i, normal at i-1 and i+1
            if diffs[i] > diffs[i - 1] * 2 and diffs[i] > diffs[i + 1] * 2:
                cut_frames.append((i, float(diffs[i])))

    # Filter by min_scene_seconds
    filtered_cuts = []
    for frame_idx, intensity in cut_frames:
        if not filtered_cuts or (frame_idx - filtered_cuts[-1][0]) >= min_gap_frames:
            filtered_cuts.append((frame_idx, intensity))
        elif intensity > filtered_cuts[-1][1]:
            filtered_cuts[-1] = (frame_idx, intensity)

    # Build scenes
    scenes = []
    prev_end = 0.0
    for idx, (frame_idx, intensity) in enumerate(filtered_cuts):
        cut_ts = round(frame_idx / fps, 2)
        scenes.append({
            "scene_index": idx,
            "start_seconds": round(prev_end, 2),
            "end_seconds": cut_ts,
            "duration_seconds": round(cut_ts - prev_end, 2),
            "cut_timestamp_seconds": cut_ts,
            "cut_intensity": round(intensity, 1),
        })
        prev_end = cut_ts

    # Final scene
    scenes.append({
        "scene_index": len(filtered_cuts),
        "start_seconds": round(prev_end, 2),
        "end_seconds": round(duration, 2),
        "duration_seconds": round(duration - prev_end, 2),
        "cut_timestamp_seconds": None,
    })

    result = {
        "filename": filename,
        "scenes": scenes,
        "total_scenes": len(scenes),
        "threshold_multiplier_used": threshold_multiplier,
    }

    if debug_writer.is_active(debug):
        d = debug_writer.get_debug_dir(filename, "detect_scenes")
        debug_writer.save_metadata(d, {"tool": "detect_scenes", "filename": filename, "result": result})

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


tool_def(
    Tool(
        name="detect_scenes",
        description=(
            "Identifies hard scene cuts or abrupt visual transitions. "
            "Use for segmenting multi-exercise videos, finding camera cuts, "
            "or identifying edit points."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "threshold_multiplier": {"type": "number", "default": 5.0, "description": "Higher = only hard cuts"},
                "min_scene_seconds": {"type": "number", "default": 1.0, "description": "Min scene duration"},
                "debug": {"type": "boolean", "default": False},
            },
            "required": ["filename"],
        },
    ),
    _detect_scenes,
)


# --- detect_pauses ---

async def _detect_pauses(server: Server, arguments: dict) -> list[TextContent]:
    filename = arguments.get("filename", "")
    min_duration_seconds = arguments.get("min_duration_seconds", 0.3)
    sensitivity = arguments.get("sensitivity", 0.5)
    debug = arguments.get("debug", False)

    try:
        video_path, frame_diff, debug_writer = _get_deps(server, filename)
    except ValueError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    ext = FrameExtractor(video_path)
    meta = ext.get_metadata()
    fps = meta["fps"]

    diffs = frame_diff.get(filename, video_path)

    if len(diffs) == 0:
        return [TextContent(type="text", text=json.dumps({"filename": filename, "pauses": [], "total_pauses": 0}))]

    baseline_mean = float(diffs.mean())
    threshold = baseline_mean * (1.0 + (1.0 - sensitivity) * 0.5)
    min_frames = int(min_duration_seconds * fps)

    below = diffs < threshold
    pauses = []
    i = 0
    while i < len(below):
        if below[i]:
            start = i
            while i < len(below) and below[i]:
                i += 1
            end = i
            if (end - start) >= min_frames:
                mean_intensity = float(diffs[start:end].mean())
                mid = (start + end) // 2
                pauses.append({
                    "start_seconds": round(start / fps, 2),
                    "end_seconds": round(end / fps, 2),
                    "duration_seconds": round((end - start) / fps, 2),
                    "representative_timestamp": round(mid / fps, 2),
                    "mean_intensity": round(mean_intensity, 1),
                })
        else:
            i += 1

    result = {
        "filename": filename,
        "pauses": pauses,
        "total_pauses": len(pauses),
        "sensitivity_used": sensitivity,
    }

    if debug_writer.is_active(debug):
        d = debug_writer.get_debug_dir(filename, "detect_pauses")
        debug_writer.save_metadata(d, {"tool": "detect_pauses", "filename": filename, "result": result})

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


tool_def(
    Tool(
        name="detect_pauses",
        description=(
            "Identifies timestamps where the subject is stationary. "
            "For movement analysis, pauses are often the most important: "
            "lockout, catch position, bottom of squat, top of deadlift."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "min_duration_seconds": {"type": "number", "default": 0.3, "description": "Min pause length"},
                "sensitivity": {"type": "number", "default": 0.5, "description": "0.0-1.0, higher = more residual movement"},
                "debug": {"type": "boolean", "default": False},
            },
            "required": ["filename"],
        },
    ),
    _detect_pauses,
)


# --- get_motion_timeline ---

async def _get_motion_timeline(server: Server, arguments: dict) -> list:
    filename = arguments.get("filename", "")
    resolution_seconds = arguments.get("resolution_seconds", 0.5)
    debug = arguments.get("debug", False)

    try:
        video_path, frame_diff, debug_writer = _get_deps(server, filename)
    except ValueError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    ext = FrameExtractor(video_path)
    meta = ext.get_metadata()
    fps = meta["fps"]
    duration = meta["duration_seconds"]

    diffs = frame_diff.get(filename, video_path)

    if len(diffs) == 0:
        return [TextContent(type="text", text=json.dumps({"error": "No frame data"}))]

    # Aggregate into time buckets
    bucket_frames = max(1, int(resolution_seconds * fps))
    n_buckets = math.ceil(len(diffs) / bucket_frames)
    bucket_means = []
    bucket_times = []
    for i in range(n_buckets):
        start = i * bucket_frames
        end = min(start + bucket_frames, len(diffs))
        bucket_means.append(float(diffs[start:end].mean()))
        bucket_times.append(round((start + end) / 2 / fps, 2))

    baseline = float(diffs.mean())
    max_val = max(bucket_means) if bucket_means else 1.0

    # Render chart with matplotlib
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return [TextContent(type="text", text=json.dumps({
            "error": "matplotlib not installed. Install with: pip install matplotlib"
        }))]

    fig, ax = plt.subplots(figsize=(12, 4), dpi=100)

    # Color bars by intensity
    colors = []
    for v in bucket_means:
        norm = v / max_val if max_val > 0 else 0
        if norm > 0.7:
            colors.append("#e74c3c")  # red
        elif norm > 0.3:
            colors.append("#f39c12")  # orange
        else:
            colors.append("#95a5a6")  # grey

    ax.bar(bucket_times, bucket_means, width=resolution_seconds * 0.9, color=colors)
    ax.axhline(y=baseline, color="#3498db", linestyle="--", alpha=0.7, label="baseline")
    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("Motion Intensity")
    ax.set_title(f"Motion Timeline — {filename}")
    ax.legend()
    fig.tight_layout()

    import io
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100)
    plt.close(fig)
    buf.seek(0)
    chart_bytes = buf.read()

    # Compute metadata
    peak_idx = int(np.argmax(bucket_means))
    active_threshold = baseline * 1.5
    active_periods = []
    quiet_periods = []
    in_active = False
    period_start = 0.0

    for i, v in enumerate(bucket_means):
        t = bucket_times[i]
        if v > active_threshold and not in_active:
            if i > 0:
                quiet_periods.append({"start": period_start, "end": t})
            period_start = t
            in_active = True
        elif v <= active_threshold and in_active:
            active_periods.append({"start": period_start, "end": t})
            period_start = t
            in_active = False

    if in_active:
        active_periods.append({"start": period_start, "end": round(duration, 2)})
    else:
        quiet_periods.append({"start": period_start, "end": round(duration, 2)})

    active_time = sum(p["end"] - p["start"] for p in active_periods)
    active_fraction = round(active_time / duration, 2) if duration > 0 else 0.0

    result_meta = {
        "filename": filename,
        "peak_timestamp_seconds": bucket_times[peak_idx] if bucket_times else 0.0,
        "peak_intensity": round(max_val, 1),
        "active_fraction": active_fraction,
        "quiet_periods": quiet_periods,
        "active_periods": active_periods,
    }

    description = f"Motion timeline | {filename} | Duration: {duration:.1f}s | Peak at {result_meta['peak_timestamp_seconds']}s"

    if debug_writer.is_active(debug):
        d = debug_writer.get_debug_dir(filename, "get_motion_timeline")
        debug_writer.save_result_image(d, chart_bytes, "PNG")
        debug_writer.save_metadata(d, {"tool": "get_motion_timeline", "filename": filename, "computed": result_meta})

    b64 = base64.standard_b64encode(chart_bytes).decode("ascii")
    return [
        TextContent(type="text", text=f"{description}\n\n{json.dumps(result_meta)}"),
        ImageContent(type="image", data=b64, mimeType="image/png"),
    ]


tool_def(
    Tool(
        name="get_motion_timeline",
        description=(
            "Returns a chart image showing motion intensity over time. "
            "Provides an instant visual map of where activity is concentrated. "
            "Requires matplotlib."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "resolution_seconds": {"type": "number", "default": 0.5, "description": "Time bucket size"},
                "debug": {"type": "boolean", "default": False},
            },
            "required": ["filename"],
        },
    ),
    _get_motion_timeline,
)


# --- get_motion_heatmap ---

async def _get_motion_heatmap(server: Server, arguments: dict) -> list:
    filename = arguments.get("filename", "")
    start_seconds = arguments.get("start_seconds")
    end_seconds = arguments.get("end_seconds")
    debug = arguments.get("debug", False)

    try:
        resolver = server._resolver  # type: ignore[attr-defined]
        video_path = resolver.resolve(filename)
        debug_writer = server._debug  # type: ignore[attr-defined]
    except ValueError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    ext = FrameExtractor(video_path)
    meta = ext.get_metadata()
    fps = meta["fps"]
    duration = meta["duration_seconds"]

    if start_seconds is None:
        start_seconds = 0.0
    if end_seconds is None:
        end_seconds = duration

    start_seconds = max(0.0, start_seconds)
    end_seconds = min(end_seconds, duration)

    cap = cv2.VideoCapture(str(video_path))
    cap.set(cv2.CAP_PROP_POS_MSEC, start_seconds * 1000)

    accumulator = None
    prev_gray = None
    mid_frame = None
    frame_count = 0
    mid_target = int((end_seconds - start_seconds) * fps / 2)

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        pos_sec = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        if pos_sec > end_seconds:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)

        if prev_gray is not None:
            diff = np.abs(gray - prev_gray)
            if accumulator is None:
                accumulator = diff
            else:
                accumulator += diff

        if frame_count == mid_target:
            mid_frame = frame.copy()

        prev_gray = gray
        frame_count += 1

    cap.release()

    if accumulator is None or mid_frame is None:
        return [TextContent(type="text", text=json.dumps({"error": "Not enough frames for heatmap"}))]

    # Normalize to 0-255
    if accumulator.max() > 0:
        accumulator = (accumulator / accumulator.max() * 255).astype(np.uint8)
    else:
        accumulator = accumulator.astype(np.uint8)

    # Apply colormap
    heatmap = cv2.applyColorMap(accumulator, cv2.COLORMAP_JET)

    # Alpha blend over midpoint frame
    blended = cv2.addWeighted(mid_frame, 0.5, heatmap, 0.5, 0)

    # Convert to PIL and bytes
    rgb = cv2.cvtColor(blended, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(rgb)

    # Apply rotation
    rotation = meta.get("rotation_degrees", 0)
    if rotation:
        img = ext.apply_rotation(img, rotation)

    comp = GridCompositor()
    img_bytes = comp.image_to_bytes(img, format="PNG")

    width, height = img.size
    range_str = "Full video" if start_seconds == 0 and end_seconds >= duration else f"{start_seconds:.1f}s-{end_seconds:.1f}s"
    description = f"Motion heatmap | {filename} | {range_str} | {width}x{height}px"

    result_meta = {
        "filename": filename,
        "start_seconds": start_seconds,
        "end_seconds": end_seconds,
        "frames_analyzed": frame_count,
        "width": width,
        "height": height,
    }

    if debug_writer.is_active(debug):
        d = debug_writer.get_debug_dir(filename, "get_motion_heatmap")
        debug_writer.save_result_image(d, img_bytes, "PNG")
        debug_writer.save_metadata(d, {"tool": "get_motion_heatmap", "filename": filename, "computed": result_meta})

    b64 = base64.standard_b64encode(img_bytes).decode("ascii")
    return [
        TextContent(type="text", text=f"{description}\n\n{json.dumps(result_meta)}"),
        ImageContent(type="image", data=b64, mimeType="image/png"),
    ]


tool_def(
    Tool(
        name="get_motion_heatmap",
        description=(
            "Returns a full-resolution PNG showing where in the frame movement is "
            "spatially concentrated. Overlays a colored heatmap on a reference frame. "
            "For squats, shows hot zones at hips and barbell."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "start_seconds": {"type": "number", "description": "Start of range (null = beginning)"},
                "end_seconds": {"type": "number", "description": "End of range (null = end)"},
                "debug": {"type": "boolean", "default": False},
            },
            "required": ["filename"],
        },
    ),
    _get_motion_heatmap,
)
