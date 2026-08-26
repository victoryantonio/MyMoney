#!/usr/bin/env python3
"""Generate the notification icons for the MyMoney Android app from ./icon.png.

Android status-bar (small) icons MUST be single-color alpha masks — the
system tints them. We produce a white silhouette (`ic_stat_notify.png`) at
every density (24dp base) plus a full-color large icon
(`ic_notification_large.png`, drawable-nodpi) for `.setLargeIcon(...)`.

Silhouette strategy: keep the source alpha, force pure white. This works
because icon.png has a solid, roughly-square full-bleed shape.
"""
import os
from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../android
PROJECT = os.path.dirname(ROOT)
SRC = os.path.join(PROJECT, "icon.png")
RES = os.path.join(ROOT, "app", "src", "main", "res")

DENSITIES = {
    "mdpi": 1.0,
    "hdpi": 1.5,
    "xhdpi": 2.0,
    "xxhdpi": 3.0,
    "xxxhdpi": 4.0,
}
BASE = 24  # mdpi status-bar icon size in px
LARGE_BASE = 128  # large icon size (dp-ish; single nodpi asset)


def main() -> None:
    icon = Image.open(SRC).convert("RGBA")
    print("source:", icon.size)

    # Trim any fully-transparent border so the shape fills the canvas.
    alpha = icon.getchannel("A")
    bbox = alpha.getbbox()
    if bbox:
        icon = icon.crop(bbox)
        print("cropped to:", icon.size)

    # 1) White monochrome small icons (alpha mask) per density.
    for density, scale in DENSITIES.items():
        size = int(BASE * scale)
        d = os.path.join(RES, f"drawable-{density}")
        os.makedirs(d, exist_ok=True)

        small = icon.resize((size, size), Image.LANCZOS)
        white = Image.new("RGBA", (size, size), (255, 255, 255, 0))
        # Paste using the source alpha so only the shape survives.
        white.paste((255, 255, 255, 255), (0, 0), small)
        out = os.path.join(d, "ic_stat_notify.png")
        white.save(out)
        print("wrote", out)

    # 2) Full-color large icon (used by .setLargeIcon in notifications).
    nodpi = os.path.join(RES, "drawable-nodpi")
    os.makedirs(nodpi, exist_ok=True)
    large = icon.resize((LARGE_BASE, LARGE_BASE), Image.LANCZOS)
    out = os.path.join(nodpi, "ic_notification_large.png")
    large.save(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
