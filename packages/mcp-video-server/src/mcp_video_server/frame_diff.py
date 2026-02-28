"""FrameDiffPipeline — shared frame difference computation with caching."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .cache import CacheManager


class FrameDiffPipeline:
    """Computes and caches per-frame difference arrays.

    3-tier lookup: in-memory dict -> disk .npy -> compute from scratch.
    """

    def __init__(self, cache: CacheManager) -> None:
        self.cache = cache
        self._memory: dict[str, np.ndarray] = {}

    def get(self, filename: str, video_path: Path) -> np.ndarray:
        """Get frame difference array, using cache when possible."""
        if filename in self._memory:
            return self._memory[filename]

        # Try disk cache
        cached = self.cache.read_frame_diffs(filename, video_path)
        if cached is not None:
            self._memory[filename] = cached
            return cached

        # Compute from scratch
        diffs = self._compute(video_path)
        self._memory[filename] = diffs
        self.cache.write_frame_diffs(filename, video_path, diffs)
        return diffs

    def evict(self, filename: str | None = None) -> None:
        """Evict entries from the in-memory cache."""
        if filename is None:
            self._memory.clear()
        else:
            self._memory.pop(filename, None)

    @staticmethod
    def _compute(video_path: Path) -> np.ndarray:
        """Compute mean absolute per-pixel diff between consecutive grayscale frames."""
        cap = cv2.VideoCapture(str(video_path))
        diffs: list[float] = []
        prev_gray = None

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if prev_gray is not None:
                diff = cv2.absdiff(gray, prev_gray)
                diffs.append(float(diff.mean()))
            prev_gray = gray

        cap.release()
        return np.array(diffs, dtype=np.float32)
