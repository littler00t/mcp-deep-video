"""GridCompositor — frame grid images with timestamp labels."""

from __future__ import annotations

import io
import math

from PIL import Image, ImageDraw, ImageFont


class GridCompositor:
    """Composes frames into labeled grid images."""

    def __init__(
        self,
        cell_width: int = 320,
        cell_height: int = 240,
        label_height: int = 20,
    ) -> None:
        self.cell_width = cell_width
        self.cell_height = cell_height
        self.label_height = label_height
        self._font = self._load_font()

    def _load_font(self) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        for path in [
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]:
            try:
                return ImageFont.truetype(path, 13)
            except Exception:
                continue
        return ImageFont.load_default()

    @staticmethod
    def format_timestamp(seconds: float) -> str:
        """Format seconds as M:SS.ss or H:MM:SS.ss."""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        if h > 0:
            return f"{h}:{m:02d}:{s:05.2f}"
        return f"{m}:{s:05.2f}"

    def create_grid_image(
        self,
        frames: list[tuple[Image.Image, float]],
        cols: int | None = None,
    ) -> Image.Image:
        """Create a grid image with timestamp labels.

        Args:
            frames: List of (image, timestamp_seconds) tuples.
            cols: Number of columns. Defaults to ceil(sqrt(n)).
        """
        if not frames:
            return Image.new("RGB", (self.cell_width, self.cell_height + self.label_height), (20, 20, 20))

        if cols is None:
            cols = math.ceil(math.sqrt(len(frames)))

        rows = math.ceil(len(frames) / cols)
        grid_w = cols * self.cell_width
        grid_h = rows * (self.cell_height + self.label_height)
        grid = Image.new("RGB", (grid_w, grid_h), (20, 20, 20))

        for idx, (pil_img, ts) in enumerate(frames):
            row = idx // cols
            col = idx % cols
            x = col * self.cell_width
            y = row * (self.cell_height + self.label_height)

            # Resize frame to cell size
            resized = pil_img.resize((self.cell_width, self.cell_height), Image.LANCZOS)
            grid.paste(resized, (x, y))

            # Draw timestamp label with semi-transparent background
            label_img = Image.new("RGBA", (self.cell_width, self.label_height), (0, 0, 0, 160))
            draw = ImageDraw.Draw(label_img)
            label = self.format_timestamp(ts)
            draw.text((4, 3), label, fill=(255, 255, 255, 255), font=self._font)
            # Paste onto grid using alpha composite
            temp = Image.new("RGBA", (self.cell_width, self.label_height), (0, 0, 0, 0))
            temp.paste(grid.crop((x, y + self.cell_height, x + self.cell_width, y + self.cell_height + self.label_height)).convert("RGBA"))
            composited = Image.alpha_composite(temp, label_img)
            grid.paste(composited.convert("RGB"), (x, y + self.cell_height))

        return grid

    @staticmethod
    def image_to_bytes(img: Image.Image, format: str = "JPEG", quality: int = 85) -> bytes:
        """Convert PIL Image to bytes."""
        buf = io.BytesIO()
        if format.upper() == "JPEG":
            img.convert("RGB").save(buf, format="JPEG", quality=quality, optimize=True)
        else:
            img.save(buf, format=format)
        buf.seek(0)
        return buf.read()
