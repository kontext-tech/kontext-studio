#!/usr/bin/env python3
"""Generate the 1024px master icon for `tauri icon`.

uv run --with pillow python desktop/scripts/make-icon.py
pnpm exec tauri icon desktop/icons/source.png -o desktop/src-tauri/icons
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = 1024
OUTPUT = Path(__file__).resolve().parents[1] / "icons" / "source.png"
FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in FONT_CANDIDATES:
        path = Path(candidate)
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue
    return ImageFont.load_default(size=size)


def main() -> None:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), radius=220, fill="#1c1c1a")

    font = _font(600)
    box = draw.textbbox((0, 0), "K", font=font)
    width = box[2] - box[0]
    height = box[3] - box[1]
    draw.text(
        ((SIZE - width) / 2 - box[0], (SIZE - height) / 2 - box[1]),
        "K",
        font=font,
        fill="#f7f7f5",
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
