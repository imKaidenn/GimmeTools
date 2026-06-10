"""
GimmeTools — app icon generator.

Renders the brand mark (rounded gradient tile + lightning bolt, matching the
in-app sidebar logo) at 4x and downsamples, then writes:
    assets/icon.ico   multi-resolution (16-256), used by the window, the exe,
                      and the installer
    assets/icon.png   256px, for docs / future use

Run with any Python that has Pillow:
    py install\\make_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

S = 1024                  # supersampled canvas (4x the 256 target)
RADIUS = 232              # ≈ 58px at 256 — matches the UI's 13px radius at 42px tiles

# Brand gradient stops (purple → blue → cyan), diagonal top-left → bottom-right
STOPS = [
    (0.00, (124, 58, 237)),
    (0.55, (77, 124, 254)),
    (1.00, (34, 211, 238)),
]

# Classic bolt, centered, on a 1024 grid
BOLT = [(600, 112), (296, 560), (488, 560), (424, 912), (744, 432), (536, 432)]


def lerp(a: tuple, b: tuple, t: float) -> tuple:
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient_color(t: float) -> tuple:
    for (t0, c0), (t1, c1) in zip(STOPS, STOPS[1:]):
        if t <= t1:
            return lerp(c0, c1, (t - t0) / (t1 - t0))
    return STOPS[-1][1]


def main() -> None:
    ASSETS.mkdir(exist_ok=True)

    # diagonal gradient
    img = Image.new("RGBA", (S, S))
    px = img.load()
    for y in range(S):
        for x in range(S):
            px[x, y] = gradient_color((x + y) / (2 * S - 2)) + (255,)

    # rounded-rect alpha mask
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], RADIUS, fill=255)
    img.putalpha(mask)

    # bolt with a soft dark underlay for depth, then white on top
    draw = ImageDraw.Draw(img)
    shadow = [(x + 14, y + 18) for x, y in BOLT]
    draw.polygon(shadow, fill=(10, 9, 17, 90))
    draw.polygon(BOLT, fill=(255, 255, 255, 255))

    base = img.resize((256, 256), Image.LANCZOS)
    base.save(ASSETS / "icon.png")
    base.save(
        ASSETS / "icon.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"wrote {ASSETS / 'icon.ico'} and icon.png")


if __name__ == "__main__":
    main()
