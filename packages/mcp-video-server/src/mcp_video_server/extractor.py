"""FrameExtractor — OpenCV frame extraction with rotation support."""

from __future__ import annotations

import math
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def _log(msg: str) -> None:
    """Log to stderr for visibility during long operations."""
    print(f"[FrameExtractor] {msg}", file=sys.stderr, flush=True)


class FrameExtractor:
    """Extracts frames from video files using OpenCV."""

    def __init__(self, video_path: str | Path) -> None:
        self.video_path = str(video_path)
        self._cap = cv2.VideoCapture(self.video_path)
        if not self._cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        self._metadata: dict | None = None

    def __del__(self) -> None:
        if hasattr(self, "_cap") and self._cap is not None:
            self._cap.release()

    def get_metadata(self) -> dict:
        """Return video metadata including codec, rotation, and audio info.

        Results are cached on the instance after the first call.
        """
        if self._metadata is not None:
            return self._metadata

        t0 = time.time()
        fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_count = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration_seconds = frame_count / fps if fps > 0 else 0.0

        # Codec detection
        fourcc_int = int(self._cap.get(cv2.CAP_PROP_FOURCC))
        codec = "".join(chr((fourcc_int >> 8 * i) & 0xFF) for i in range(4)).strip().lower()
        if not codec or codec == "\x00\x00\x00\x00":
            codec = "unknown"

        # Rotation detection
        rotation = self._detect_rotation()

        # Audio detection
        has_audio, audio_codec = self._detect_audio()

        # File info
        p = Path(self.video_path)
        file_size_mb = round(p.stat().st_size / (1024 * 1024), 1) if p.exists() else 0.0
        modified = p.stat().st_mtime if p.exists() else 0.0

        self._metadata = {
            "duration_seconds": duration_seconds,
            "fps": fps,
            "total_frames": frame_count,
            "width": width,
            "height": height,
            "resolution": f"{width}x{height}",
            "codec": codec,
            "has_audio": has_audio,
            "audio_codec": audio_codec,
            "file_size_mb": file_size_mb,
            "modified": modified,
            "rotation_degrees": rotation,
            "frame_count": frame_count,  # alias for backward compat
        }
        _log(f"Metadata: {width}x{height} {fps:.1f}fps {duration_seconds:.1f}s codec={codec} rotation={rotation} ({time.time()-t0:.2f}s)")
        return self._metadata

    def _detect_rotation(self) -> int:
        """Detect video rotation from metadata using ffprobe."""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "quiet",
                    "-select_streams", "v:0",
                    "-show_entries", "stream_tags=rotate",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    self.video_path,
                ],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip())
        except Exception:
            pass
        return 0

    def _detect_audio(self) -> tuple[bool, str | None]:
        """Detect audio presence and codec using ffprobe."""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "quiet",
                    "-select_streams", "a:0",
                    "-show_entries", "stream=codec_name",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    self.video_path,
                ],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return True, result.stdout.strip()
        except Exception:
            pass
        return False, None

    def _read_frame_at_msec(self, msec: float) -> np.ndarray | None:
        """Read a frame at a specific millisecond position."""
        self._cap.set(cv2.CAP_PROP_POS_MSEC, msec)
        ret, frame = self._cap.read()
        if not ret:
            return None
        return frame

    def _read_frame_at_index(self, frame_index: int) -> np.ndarray | None:
        """Read a frame at a specific frame index."""
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ret, frame = self._cap.read()
        if not ret:
            return None
        return frame

    def _frame_to_pil(self, frame: np.ndarray) -> Image.Image:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)

    def apply_rotation(self, img: Image.Image, rotation: int | None = None) -> Image.Image:
        """Apply rotation correction for phone videos."""
        if rotation is None:
            rotation = self._detect_rotation()
        if rotation == 90:
            return img.transpose(Image.Transpose.ROTATE_270)
        elif rotation == 180:
            return img.transpose(Image.Transpose.ROTATE_180)
        elif rotation == 270:
            return img.transpose(Image.Transpose.ROTATE_90)
        return img

    def extract_frame_at(self, timestamp: float, apply_rotation: bool = True) -> Image.Image:
        """Extract a single frame at an exact timestamp (seconds)."""
        meta = self.get_metadata()
        duration = meta["duration_seconds"]
        ts = max(0.0, min(timestamp, duration))

        frame = self._read_frame_at_msec(ts * 1000.0)
        if frame is None:
            # Fallback to frame index
            fps = meta["fps"]
            idx = int(ts * fps)
            idx = max(0, min(idx, meta["total_frames"] - 1))
            frame = self._read_frame_at_index(idx)
        if frame is None:
            raise ValueError(f"Could not read frame at timestamp {timestamp}s")

        img = self._frame_to_pil(frame)
        if apply_rotation:
            img = self.apply_rotation(img, meta["rotation_degrees"])
        return img

    def extract_frames_evenly(
        self,
        n: int,
        start: float = 0.0,
        end: float | None = None,
    ) -> list[tuple[Image.Image, float]]:
        """Extract n evenly-spaced frames from [start, end]."""
        t0 = time.time()
        meta = self.get_metadata()
        duration = meta["duration_seconds"]
        rotation = meta["rotation_degrees"]

        if end is None:
            end = duration
        end = min(end, duration)
        start = max(0.0, start)

        if n <= 0 or start >= end:
            return []

        _log(f"Extracting {n} even frames from {start:.2f}s to {end:.2f}s ...")
        interval = (end - start) / n
        frames: list[tuple[Image.Image, float]] = []

        for i in range(n):
            ts = start + (i + 0.5) * interval
            ts = min(ts, end)
            frame = self._read_frame_at_msec(ts * 1000.0)
            if frame is None:
                continue
            img = self._frame_to_pil(frame)
            img = self.apply_rotation(img, rotation)
            frames.append((img, ts))

        _log(f"Extracted {len(frames)} even frames in {time.time()-t0:.2f}s")
        return frames

    def extract_key_frames(
        self,
        n: int,
        start: float = 0.0,
        end: float | None = None,
    ) -> list[tuple[Image.Image, float]]:
        """Extract n key frames using Bhattacharyya histogram-based selection.

        Divides the time range into n intervals and selects the most visually
        distinct frame from each interval.
        """
        t0 = time.time()
        meta = self.get_metadata()
        fps = meta["fps"]
        total_duration = meta["duration_seconds"]
        frame_count = meta["total_frames"]
        rotation = meta["rotation_degrees"]

        if end is None:
            end = total_duration
        end = min(end, total_duration)
        start = max(0.0, start)

        if n <= 0 or start >= end:
            return []

        _log(f"Extracting {n} key frames (Bhattacharyya) from {start:.2f}s to {end:.2f}s ...")
        start_frame = int(start * fps)
        end_frame = min(int(end * fps), frame_count - 1)
        total_frames_range = end_frame - start_frame

        if total_frames_range <= 0:
            return []

        candidates_per_interval = 5
        selected: list[tuple[Image.Image, float]] = []
        selected_hists: list[np.ndarray] = []

        for i in range(n):
            interval_start = start_frame + int(i * total_frames_range / n)
            interval_end = start_frame + int((i + 1) * total_frames_range / n)
            interval_end = min(interval_end, end_frame)

            if interval_start >= interval_end:
                interval_end = min(interval_start + 1, end_frame)

            candidate_indices = np.linspace(
                interval_start,
                interval_end,
                min(candidates_per_interval, interval_end - interval_start + 1),
                dtype=int,
            ).tolist()

            candidate_indices = list(dict.fromkeys(candidate_indices))

            best_frame = None
            best_pil = None
            best_ts = 0.0
            best_score = -1.0

            for idx in candidate_indices:
                frame = self._read_frame_at_index(idx)
                if frame is None:
                    continue
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
                cv2.normalize(hist, hist)

                if selected_hists:
                    score = sum(
                        float(cv2.compareHist(hist, h, cv2.HISTCMP_BHATTACHARYYA))
                        for h in selected_hists
                    )
                else:
                    score = 1.0 if idx == candidate_indices[len(candidate_indices) // 2] else 0.0

                if score > best_score or best_frame is None:
                    best_score = score
                    best_frame = frame
                    best_pil = self._frame_to_pil(frame)
                    best_ts = idx / fps

            if best_pil is not None:
                best_pil = self.apply_rotation(best_pil, rotation)
                selected.append((best_pil, best_ts))
                gray = cv2.cvtColor(best_frame, cv2.COLOR_BGR2GRAY)
                hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
                cv2.normalize(hist, hist)
                selected_hists.append(hist)

        _log(f"Extracted {len(selected)} key frames in {time.time()-t0:.2f}s")
        return selected
