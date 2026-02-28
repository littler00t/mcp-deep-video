"""CacheManager — disk caching with staleness checks."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


class CacheManager:
    """Manages disk cache for video metadata, frame diffs, and transcripts."""

    def __init__(self, cache_dir: str | Path) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cache_dir(self, filename: str) -> Path:
        """Get the cache subdirectory for a video file."""
        safe_name = filename.replace("/", "__").replace("\\", "__")
        d = self.cache_dir / safe_name
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _staleness_header(self, video_path: Path) -> dict:
        stat = video_path.stat()
        return {
            "source_mtime": stat.st_mtime,
            "source_size_bytes": stat.st_size,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def _is_stale(self, video_path: Path, meta_path: Path) -> bool:
        if not meta_path.exists():
            return True
        try:
            meta = json.loads(meta_path.read_text())
            stat = video_path.stat()
            return (
                meta.get("source_mtime") != stat.st_mtime
                or meta.get("source_size_bytes") != stat.st_size
            )
        except Exception:
            return True

    # --- Metadata ---

    def read_metadata(self, filename: str, video_path: Path) -> dict | None:
        cache = self.get_cache_dir(filename) / "metadata.json"
        if not cache.exists():
            return None
        try:
            data = json.loads(cache.read_text())
            # Staleness check on metadata itself
            stat = video_path.stat()
            if (
                data.get("source_mtime") != stat.st_mtime
                or data.get("source_size_bytes") != stat.st_size
            ):
                return None
            return data
        except Exception:
            return None

    def write_metadata(self, filename: str, video_path: Path, metadata: dict) -> None:
        cache = self.get_cache_dir(filename) / "metadata.json"
        header = self._staleness_header(video_path)
        data = {**header, **metadata}
        cache.write_text(json.dumps(data, indent=2))

    # --- Frame diffs ---

    def read_frame_diffs(self, filename: str, video_path: Path) -> np.ndarray | None:
        cache_dir = self.get_cache_dir(filename)
        npy_path = cache_dir / "frame_diffs.npy"
        meta_path = cache_dir / "frame_diffs_meta.json"

        if not npy_path.exists():
            return None
        if self._is_stale(video_path, meta_path):
            return None

        try:
            return np.load(npy_path)
        except Exception:
            return None

    def write_frame_diffs(self, filename: str, video_path: Path, diffs: np.ndarray) -> None:
        cache_dir = self.get_cache_dir(filename)
        np.save(cache_dir / "frame_diffs.npy", diffs)
        meta_path = cache_dir / "frame_diffs_meta.json"
        meta_path.write_text(json.dumps(self._staleness_header(video_path), indent=2))

    # --- Transcript ---

    def read_transcript(self, filename: str, video_path: Path) -> dict | None:
        cache = self.get_cache_dir(filename) / "transcript.json"
        if not cache.exists():
            return None
        try:
            data = json.loads(cache.read_text())
            stat = video_path.stat()
            if (
                data.get("source_mtime") != stat.st_mtime
                or data.get("source_size_bytes") != stat.st_size
            ):
                return None
            return data
        except Exception:
            return None

    def write_transcript(self, filename: str, video_path: Path, transcript: dict) -> None:
        cache = self.get_cache_dir(filename) / "transcript.json"
        header = self._staleness_header(video_path)
        data = {**header, **transcript}
        cache.write_text(json.dumps(data, indent=2))

    # --- Cache status ---

    def get_cache_status(self, filename: str) -> dict[str, bool]:
        d = self.get_cache_dir(filename)
        return {
            "metadata": (d / "metadata.json").exists(),
            "frame_diffs": (d / "frame_diffs.npy").exists(),
            "transcript": (d / "transcript.json").exists(),
        }

    # --- Clear ---

    def clear(self, filename: str | None = None, cache_type: str = "all") -> list[dict]:
        """Clear cache files. Returns list of cleared items with freed space."""
        import shutil

        type_files = {
            "metadata": ["metadata.json"],
            "frame_diffs": ["frame_diffs.npy", "frame_diffs_meta.json"],
            "transcript": ["transcript.json"],
        }

        if cache_type == "all":
            target_types = list(type_files.keys())
        elif cache_type in type_files:
            target_types = [cache_type]
        else:
            raise ValueError(f"Invalid cache_type: {cache_type}")

        cleared: list[dict] = []

        if filename is not None:
            dirs = [self.get_cache_dir(filename)]
            names = [filename]
        else:
            dirs = []
            names = []
            if self.cache_dir.exists():
                for d in sorted(self.cache_dir.iterdir()):
                    if d.is_dir():
                        dirs.append(d)
                        names.append(d.name.replace("__", "/"))

        for d, name in zip(dirs, names):
            freed = 0.0
            types_cleared = []
            for t in target_types:
                for f in type_files[t]:
                    fp = d / f
                    if fp.exists():
                        freed += fp.stat().st_size / (1024 * 1024)
                        fp.unlink()
                        if t not in types_cleared:
                            types_cleared.append(t)
            if types_cleared:
                cleared.append({
                    "filename": name,
                    "types": types_cleared,
                    "freed_mb": round(freed, 2),
                })

        return cleared
