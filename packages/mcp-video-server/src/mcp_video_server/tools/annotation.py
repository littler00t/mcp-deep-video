"""Tool: annotate_frame."""

from __future__ import annotations

import base64
import json
import math

import cv2
import numpy as np
from mcp.server import Server
from mcp.types import ImageContent, TextContent, Tool

from ..compositor import GridCompositor
from ..extractor import FrameExtractor
from . import tool_def


async def _annotate_frame(server: Server, arguments: dict) -> list:
    filename = arguments.get("filename", "")
    timestamp_seconds = arguments.get("timestamp_seconds", 0.0)
    lines = arguments.get("lines") or []
    angles = arguments.get("angles") or []
    labels = arguments.get("labels") or []
    debug = arguments.get("debug", False)

    try:
        resolver = server._resolver  # type: ignore[attr-defined]
        video_path = resolver.resolve(filename)
        debug_writer = server._debug  # type: ignore[attr-defined]
    except ValueError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    ext = FrameExtractor(video_path)
    meta = ext.get_metadata()
    ts = max(0.0, min(timestamp_seconds, meta["duration_seconds"]))

    # Extract frame as OpenCV (BGR) for drawing
    frame_cv = ext._read_frame_at_msec(ts * 1000.0)
    if frame_cv is None:
        idx = int(ts * meta["fps"])
        idx = max(0, min(idx, meta["total_frames"] - 1))
        frame_cv = ext._read_frame_at_index(idx)
    if frame_cv is None:
        return [TextContent(type="text", text=json.dumps({"error": f"Could not read frame at {ts}s"}))]

    # Apply rotation
    rotation = meta.get("rotation_degrees", 0)
    if rotation == 90:
        frame_cv = cv2.rotate(frame_cv, cv2.ROTATE_90_COUNTERCLOCKWISE)
    elif rotation == 180:
        frame_cv = cv2.rotate(frame_cv, cv2.ROTATE_180)
    elif rotation == 270:
        frame_cv = cv2.rotate(frame_cv, cv2.ROTATE_90_CLOCKWISE)

    angle_labels = []

    # Draw lines
    for line in lines:
        pt1 = tuple(line["from"])
        pt2 = tuple(line["to"])
        color = tuple(reversed(line.get("color", [0, 255, 0])))  # RGB -> BGR
        thickness = line.get("thickness", 2)
        cv2.line(frame_cv, pt1, pt2, color, thickness)

    # Draw angles
    for angle_def in angles:
        pts = angle_def["points"]
        p1 = np.array(pts[0], dtype=float)
        vertex = np.array(pts[1], dtype=float)
        p3 = np.array(pts[2], dtype=float)

        v1 = p1 - vertex
        v2 = p3 - vertex
        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8)
        angle_deg = math.degrees(math.acos(np.clip(cos_angle, -1.0, 1.0)))

        color = tuple(reversed(angle_def.get("color", [255, 255, 0])))  # RGB -> BGR
        label_text = angle_def.get("label", "angle")
        full_label = f"{label_text}: {angle_deg:.0f}°"
        angle_labels.append(full_label)

        # Draw lines from vertex
        cv2.line(frame_cv, tuple(map(int, vertex)), tuple(map(int, p1)), color, 2)
        cv2.line(frame_cv, tuple(map(int, vertex)), tuple(map(int, p3)), color, 2)

        # Draw arc
        start_angle = math.degrees(math.atan2(-v1[1], v1[0]))
        end_angle = math.degrees(math.atan2(-v2[1], v2[0]))
        radius = 30
        cv2.ellipse(frame_cv, tuple(map(int, vertex)), (radius, radius),
                     0, -start_angle, -end_angle, color, 2)

        # Draw label
        label_pos = (int(vertex[0]) + 10, int(vertex[1]) - 10)
        _draw_text_with_bg(frame_cv, full_label, label_pos, color)

    # Draw labels
    for lbl in labels:
        point = tuple(lbl["point"])
        text = lbl["text"]
        color = tuple(reversed(lbl.get("color", [255, 255, 255])))  # RGB -> BGR
        size = lbl.get("size", 1.0)
        _draw_text_with_bg(frame_cv, text, point, color, scale=size)

    # Convert to PIL
    rgb = cv2.cvtColor(frame_cv, cv2.COLOR_BGR2RGB)
    from PIL import Image
    img = Image.fromarray(rgb)

    comp = GridCompositor()
    img_bytes = comp.image_to_bytes(img, format="PNG")

    ts_label = comp.format_timestamp(ts)
    parts = [f"{len(lines)} lines" if lines else None,
             f"{len(angles)} angle{'s' if len(angles) != 1 else ''}" if angles else None,
             f"{len(labels)} label{'s' if len(labels) != 1 else ''}" if labels else None]
    annotations_str = ", ".join(p for p in parts if p)
    angle_info = ""
    for al in angle_labels:
        angle_info += f" ({al})"

    description = f"Annotated frame at {ts_label} | {annotations_str}{angle_info} | {img.width}x{img.height}px PNG"

    result_meta = {
        "filename": filename,
        "timestamp_seconds": ts,
        "lines_drawn": len(lines),
        "angles_drawn": len(angles),
        "labels_drawn": len(labels),
        "angle_measurements": angle_labels,
        "width": img.width,
        "height": img.height,
    }

    if debug_writer.is_active(debug):
        d = debug_writer.get_debug_dir(filename, "annotate_frame")
        debug_writer.save_result_image(d, img_bytes, "PNG")
        debug_writer.save_metadata(d, {"tool": "annotate_frame", "filename": filename, "computed": result_meta})

    b64 = base64.standard_b64encode(img_bytes).decode("ascii")
    return [
        TextContent(type="text", text=f"{description}\n\n{json.dumps(result_meta)}"),
        ImageContent(type="image", data=b64, mimeType="image/png"),
    ]


def _draw_text_with_bg(frame: np.ndarray, text: str, pos: tuple, color: tuple, scale: float = 0.7) -> None:
    """Draw text with semi-transparent black background."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    thickness = max(1, int(scale * 2))
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
    x, y = pos
    # Background rectangle
    overlay = frame.copy()
    cv2.rectangle(overlay, (x - 2, y - th - 4), (x + tw + 2, y + baseline + 2), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
    # Text
    cv2.putText(frame, text, (x, y), font, scale, color, thickness, cv2.LINE_AA)


tool_def(
    Tool(
        name="annotate_frame",
        description=(
            "Extracts a frame and draws lines, angle arcs, and text labels using "
            "provided coordinates. The LLM identifies key points from get_precise_frame, "
            "then calls this to produce an annotated image with form measurements."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "timestamp_seconds": {"type": "number", "description": "Timestamp in seconds"},
                "lines": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "from": {"type": "array", "items": {"type": "integer"}, "description": "[x, y]"},
                            "to": {"type": "array", "items": {"type": "integer"}, "description": "[x, y]"},
                            "color": {"type": "array", "items": {"type": "integer"}, "default": [0, 255, 0]},
                            "thickness": {"type": "integer", "default": 2},
                        },
                        "required": ["from", "to"],
                    },
                },
                "angles": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "points": {"type": "array", "items": {"type": "array"}, "description": "[[x,y],[x,y],[x,y]]"},
                            "label": {"type": "string"},
                            "color": {"type": "array", "items": {"type": "integer"}, "default": [255, 255, 0]},
                        },
                        "required": ["points", "label"],
                    },
                },
                "labels": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "point": {"type": "array", "items": {"type": "integer"}, "description": "[x, y]"},
                            "text": {"type": "string"},
                            "color": {"type": "array", "items": {"type": "integer"}, "default": [255, 255, 255]},
                            "size": {"type": "number", "default": 1.0},
                        },
                        "required": ["point", "text"],
                    },
                },
                "debug": {"type": "boolean", "default": False},
            },
            "required": ["filename", "timestamp_seconds"],
        },
    ),
    _annotate_frame,
)
