from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import BinaryContent, ToolReturn

from mcp_video_server import DebugWriter, FrameExtractor, GridCompositor

from .models import WorkoutAnalysis

SYSTEM_PROMPT = """\
You are an elite fitness coach with deep expertise in biomechanics, sports science, and injury
prevention. You are analyzing a workout video to provide a detailed, actionable critique.

Required analysis sequence — follow this exactly:
1. Call get_video_overview() first — study the entire video, count reps, identify exercise phases
   (setup, concentric, eccentric, transitions), and note any obvious form issues.
2. Call get_video_section() for each critical phase you identified: setup/starting position,
   the primary movement (concentric), the return movement (eccentric), and any transitions.
3. Call get_precise_frame() at moments of maximum load, potential form breaks, joint stress
   positions, and any critical technique points you want to examine closely.
4. After gathering sufficient visual evidence, produce the structured WorkoutAnalysis output.

When scoring technique (1-10):
- 1-3: Significant injury risk — unsafe to continue without correction
- 4-6: Functional but suboptimal — common beginner/intermediate patterns
- 7-8: Good form — minor refinements would enhance performance
- 9-10: Competition-ready — textbook technique

Observations must reference specific timestamps visible in the frame labels.
Be specific about body parts, angles, and positions. Prioritize safety over performance.
"""


@dataclass
class VideoAnalysisDeps:
    extractor: FrameExtractor
    compositor: GridCompositor
    debug: DebugWriter
    video_filename: str


workout_agent: Agent[VideoAnalysisDeps, WorkoutAnalysis] = Agent(
    "anthropic:claude-sonnet-4-6",
    deps_type=VideoAnalysisDeps,
    output_type=WorkoutAnalysis,
    system_prompt=SYSTEM_PROMPT,
    defer_model_check=True,
)


@workout_agent.tool
async def get_video_overview(
    ctx: RunContext[VideoAnalysisDeps],
    max_frames: int = 20,
) -> ToolReturn:
    """Get a grid overview of evenly-distributed key frames from the entire video.

    Returns a JPEG grid image with timestamps on each cell. Use this first to understand
    the full structure of the workout — count reps, identify phases, spot patterns.

    Args:
        max_frames: Number of frames in the grid (default 20, max 24).
    """
    max_frames = min(max_frames, 24)
    ext = ctx.deps.extractor
    comp = ctx.deps.compositor
    meta = ext.get_metadata()

    frames = ext.extract_key_frames(max_frames)
    grid = comp.create_grid_image(frames)
    grid_bytes = comp.image_to_bytes(grid, format="JPEG")

    metadata_str = (
        f"Full video overview | "
        f"Duration: {meta['duration_seconds']:.1f}s | "
        f"FPS: {meta['fps']:.1f} | "
        f"Resolution: {meta['resolution']} | "
        f"Frames shown: {len(frames)}"
    )

    dbg = ctx.deps.debug
    if dbg.is_active():
        d = dbg.get_debug_dir(ctx.deps.video_filename, "get_video_overview")
        dbg.save_result_image(d, grid_bytes, "JPEG")
        dbg.save_metadata(d, {
            "tool": "get_video_overview",
            "filename": ctx.deps.video_filename,
            "params": {"max_frames": max_frames},
            "computed": {
                "duration_seconds": meta["duration_seconds"],
                "fps": meta["fps"],
                "resolution": meta["resolution"],
                "frames_shown": len(frames),
                "frame_timestamps": [round(ts, 2) for _, ts in frames],
            },
        })
        dbg.save_raw_frames(d, frames)

    return ToolReturn(
        return_value=metadata_str,
        content=[
            "Full video overview grid (timestamp shown at bottom of each cell):",
            BinaryContent(data=grid_bytes, media_type="image/jpeg"),
        ],
    )


@workout_agent.tool
async def get_video_section(
    ctx: RunContext[VideoAnalysisDeps],
    start_seconds: float,
    end_seconds: float,
    max_frames: int = 10,
) -> ToolReturn:
    """Get a detailed grid of key frames from a specific time range in the video.

    Use this to zoom into specific phases of the exercise (e.g., the descent, the lockout,
    a particular rep). Call once per phase after reviewing the overview.

    Args:
        start_seconds: Start of the section in seconds.
        end_seconds: End of the section in seconds.
        max_frames: Number of frames in the grid (default 10, max 16).
    """
    max_frames = min(max_frames, 16)
    ext = ctx.deps.extractor
    comp = ctx.deps.compositor
    meta = ext.get_metadata()

    start_seconds = max(0.0, start_seconds)
    end_seconds = min(end_seconds, meta["duration_seconds"])

    if start_seconds >= end_seconds:
        return ToolReturn(
            return_value=f"Invalid range: {start_seconds:.2f}s to {end_seconds:.2f}s",
        )

    frames = ext.extract_key_frames(max_frames, start=start_seconds, end=end_seconds)
    if not frames:
        return ToolReturn(
            return_value=f"No frames extracted from {start_seconds:.2f}s to {end_seconds:.2f}s",
        )

    grid = comp.create_grid_image(frames)
    grid_bytes = comp.image_to_bytes(grid, format="JPEG")

    metadata_str = (
        f"Section {start_seconds:.2f}s\u2013{end_seconds:.2f}s | "
        f"Frames shown: {len(frames)}"
    )

    dbg = ctx.deps.debug
    if dbg.is_active():
        d = dbg.get_debug_dir(ctx.deps.video_filename, "get_video_section")
        dbg.save_result_image(d, grid_bytes, "JPEG")
        dbg.save_metadata(d, {
            "tool": "get_video_section",
            "filename": ctx.deps.video_filename,
            "params": {"start_seconds": start_seconds, "end_seconds": end_seconds, "max_frames": max_frames},
            "computed": {
                "frames_shown": len(frames),
                "frame_timestamps": [round(ts, 2) for _, ts in frames],
            },
        })
        dbg.save_raw_frames(d, frames)

    return ToolReturn(
        return_value=metadata_str,
        content=[
            f"Section grid ({start_seconds:.2f}s to {end_seconds:.2f}s), timestamps shown per cell:",
            BinaryContent(data=grid_bytes, media_type="image/jpeg"),
        ],
    )


@workout_agent.tool
async def get_precise_frame(
    ctx: RunContext[VideoAnalysisDeps],
    timestamp_seconds: float,
) -> ToolReturn:
    """Extract a single high-quality frame at an exact timestamp.

    Use this for critical moments: maximum load position, suspected form breaks,
    joint angles you want to measure precisely. Returns a full-resolution PNG.

    Args:
        timestamp_seconds: Exact time in the video in seconds.
    """
    ext = ctx.deps.extractor
    comp = ctx.deps.compositor
    meta = ext.get_metadata()

    ts = max(0.0, min(timestamp_seconds, meta["duration_seconds"]))
    frame = ext.extract_frame_at(ts)
    frame_bytes = comp.image_to_bytes(frame, format="PNG")

    ts_label = comp.format_timestamp(ts)

    dbg = ctx.deps.debug
    if dbg.is_active():
        d = dbg.get_debug_dir(ctx.deps.video_filename, "get_precise_frame")
        dbg.save_result_image(d, frame_bytes, "PNG")
        dbg.save_metadata(d, {
            "tool": "get_precise_frame",
            "filename": ctx.deps.video_filename,
            "params": {"timestamp_seconds": timestamp_seconds},
            "computed": {
                "actual_timestamp": ts,
                "width": frame.width,
                "height": frame.height,
            },
        })

    return ToolReturn(
        return_value=f"Precise frame at {ts_label} ({ts:.3f}s) \u2014 {frame.width}x{frame.height}px PNG",
        content=[
            f"Precise frame at {ts_label}:",
            BinaryContent(data=frame_bytes, media_type="image/png"),
        ],
    )
