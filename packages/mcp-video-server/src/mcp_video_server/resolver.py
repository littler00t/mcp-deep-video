"""VideoResolver — path security and video file discovery."""

from __future__ import annotations

from pathlib import Path

SUPPORTED_EXTENSIONS = {
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".mts", ".mpg", ".mpeg",
}


class VideoResolver:
    """Validates and resolves video file paths within a root directory."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise ValueError(f"Video root is not a directory: {self.root}")

    def resolve(self, filename: str) -> Path:
        """Resolve a filename to an absolute path within the root.

        Raises ValueError on any traversal attempt or invalid input.
        """
        candidate = (self.root / filename).resolve()

        if not candidate.is_relative_to(self.root):
            raise ValueError(
                f"Access denied: '{filename}' resolves outside the video root directory"
            )

        if not candidate.exists():
            raise ValueError(
                f"File not found: '{filename}' — use list_videos to see available files"
            )

        if not candidate.is_file():
            raise ValueError(f"Not a file: '{filename}'")

        if candidate.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file format '{candidate.suffix}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        return candidate

    def list_video_files(self, subdirectory: str | None = None) -> list[str]:
        """List video files relative to root.

        Args:
            subdirectory: None = root only, "**" = recursive, or a specific subdir name.
        """
        if subdirectory == "**":
            search_dir = self.root
            pattern_dirs = True
        elif subdirectory is not None:
            sub = (self.root / subdirectory).resolve()
            if not sub.is_relative_to(self.root):
                raise ValueError(
                    f"Access denied: '{subdirectory}' resolves outside the video root directory"
                )
            if not sub.is_dir():
                raise ValueError(f"Not a directory: '{subdirectory}'")
            search_dir = sub
            pattern_dirs = False
        else:
            search_dir = self.root
            pattern_dirs = False

        results: list[str] = []

        if pattern_dirs:
            for p in sorted(search_dir.rglob("*")):
                if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS and not p.name.startswith("."):
                    rel = p.relative_to(self.root)
                    # Skip files inside cache/debug dirs
                    parts = rel.parts
                    if parts and parts[0] in (".mcp_cache", ".mcp_debug"):
                        continue
                    results.append(str(rel))
        else:
            for p in sorted(search_dir.iterdir()):
                if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS and not p.name.startswith("."):
                    results.append(str(p.relative_to(self.root)))

        return results
