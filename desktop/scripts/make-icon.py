#!/usr/bin/env python3
"""Generate the 1024px master icon from the Kontext brand mark.

uv run --with pillow python desktop/scripts/make-icon.py
pnpm exec tauri icon desktop/icons/source.png -o desktop/src-tauri/icons
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 1024
SUPERSAMPLE = 4
CANVAS = SIZE * SUPERSAMPLE
OUTPUT = Path(__file__).resolve().parents[1] / "icons" / "source.png"

BLUE = "#0052CC"
CYAN = "#06B6D4"
BACKGROUND = "#FFFFFF"
BORDER = "#E5E7EB"

# The favicon's dark-mode icon: a 30%-radius rounded square with the 40x40
# mark inset to 15%..85%.
CORNER_RADIUS = int(CANVAS * 0.30)
INSET = int(CANVAS * 0.15)
MARK_SIZE = CANVAS - 2 * INSET
UNIT = MARK_SIZE / 40.0


def _point(x: float, y: float) -> tuple[float, float]:
    return INSET + x * UNIT, INSET + y * UNIT


def main() -> None:
    image = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (0, 0, CANVAS - 1, CANVAS - 1),
        radius=CORNER_RADIUS,
        fill=BACKGROUND,
        outline=BORDER,
        width=max(1, SUPERSAMPLE),
    )

    stroke = 5 * UNIT
    cap = stroke / 2
    center = _point(20, 20)
    # Pillow draws an arc inward from its bounding box, so expand the box by
    # half the stroke to keep the stroke centred on the 14-unit path.
    arc_radius = (14 + 2.5) * UNIT
    bbox = (
        center[0] - arc_radius,
        center[1] - arc_radius,
        center[0] + arc_radius,
        center[1] + arc_radius,
    )

    # Blue arc across the top-left, with round caps.
    draw.arc(bbox, start=175, end=275, fill=BLUE, width=int(stroke))
    for x, y in ((6.05, 21.22), (21.22, 6.05)):
        px, py = _point(x, y)
        draw.ellipse((px - cap, py - cap, px + cap, py + cap), fill=BLUE)

    # Cyan arc across the bottom-right, with round caps.
    draw.arc(bbox, start=-5, end=95, fill=CYAN, width=int(stroke))
    for x, y in ((33.95, 18.78), (18.78, 33.95)):
        px, py = _point(x, y)
        draw.ellipse((px - cap, py - cap, px + cap, py + cap), fill=CYAN)

    # The two orbit dots.
    for x, y, color in ((29.9, 10.1, BLUE), (10.1, 29.9, CYAN)):
        px, py = _point(x, y)
        radius = 4.5 * UNIT
        draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=color)

    image = image.resize((SIZE, SIZE), Image.LANCZOS)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
