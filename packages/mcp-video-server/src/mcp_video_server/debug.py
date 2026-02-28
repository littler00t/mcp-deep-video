"""DebugWriter — saves debug output for tool calls."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from PIL import Image


class DebugWriter:
    """Writes debug output per tool call when debug mode is active."""

    def __init__(self, debug_dir: str | Path, global_debug: bool = False) -> None:
        self.debug_dir = Path(debug_dir)
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.global_debug = global_debug

    def is_active(self, per_call_debug: bool = False) -> bool:
        return self.global_debug or per_call_debug

    def get_debug_dir(self, filename: str, tool_name: str) -> Path:
        safe_name = filename.replace("/", "__").replace("\\", "__")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:20]
        d = self.debug_dir / safe_name / f"{tool_name}_{timestamp}"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_result_image(
        self,
        debug_dir: Path,
        image: Image.Image | bytes,
        format: str = "JPEG",
    ) -> None:
        ext = "jpg" if format.upper() == "JPEG" else "png"
        path = debug_dir / f"result.{ext}"
        if isinstance(image, bytes):
            path.write_bytes(image)
        else:
            image.save(path, format=format)

    def save_metadata(self, debug_dir: Path, metadata: dict) -> None:
        path = debug_dir / "metadata.json"
        path.write_text(json.dumps(metadata, indent=2, default=str))

    def save_diff_scores(self, debug_dir: Path, scores: list[float]) -> None:
        path = debug_dir / "diff_scores.json"
        path.write_text(json.dumps(scores))

    def save_raw_frames(
        self,
        debug_dir: Path,
        frames: list[tuple[Image.Image, float]],
    ) -> None:
        frames_dir = debug_dir / "frames_raw"
        frames_dir.mkdir(exist_ok=True)
        for i, (img, ts) in enumerate(frames):
            img.save(frames_dir / f"{i}_{ts:.3f}.jpg", format="JPEG", quality=85)
