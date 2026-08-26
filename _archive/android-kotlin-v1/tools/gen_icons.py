#!/usr/bin/env python3
"""Generate launcher icons for the MyMoney Android app from ./icon.png.

Produces, for each density:
  mipmap-<d>/ic_launcher.png          legacy square icon
  mipmap-<d>/ic_launcher_round.png    legacy round (circle-masked) icon
  mipmap-<d>/ic_launcher_foreground.png  adaptive foreground (108dp canvas,
                                         66dp safe-zone content)
and rewrites:
  mipmap-anydpi-v26/ic_launcher{,_round}.xml  adaptive icon referencing a
                                             solid background color sampled
                                             from the source icon edge
  values/colors.xml                    with ic_launcher_background
It also removes the scaffold .webp launcher icons.
"""
import os
from PIL import Image, ImageDraw

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
BASE = 48  # mdpi launcher icon size in px


def main() -> None:
    icon = Image.open(SRC).convert("RGBA")
    print("source:", icon.size)

    # Sample a background color from the icon's center region edge (padded).
    small = icon.resize((64, 64), Image.LANCZOS)
    px = small.getpixel((32, 32))
    color = "#%02X%02X%02X" % px[:3]
    print("background color:", color)

    for density, scale in DENSITIES.items():
        size = int(BASE * scale)
        d = os.path.join(RES, f"mipmap-{density}")
        os.makedirs(d, exist_ok=True)

        # Legacy square
        square = icon.resize((size, size), Image.LANCZOS)
        square.save(os.path.join(d, "ic_launcher.png"))

        # Legacy round (circle mask)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
        round_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        round_img.paste(square, (0, 0), mask)
        round_img.save(os.path.join(d, "ic_launcher_round.png"))

        # Adaptive foreground: 108dp canvas, icon in the 66dp safe zone
        canvas = int(108 * scale)
        safe = int(66 * scale)
        fg = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
        fg_icon = icon.resize((safe, safe), Image.LANCZOS)
        offset = (canvas - safe) // 2
        fg.paste(fg_icon, (offset, offset), fg_icon)
        fg.save(os.path.join(d, "ic_launcher_foreground.png"))

        # Drop scaffold webp launchers
        for name in ("ic_launcher.webp", "ic_launcher_round.webp"):
            p = os.path.join(d, name)
            if os.path.exists(p):
                os.remove(p)
                print("removed", p)

    # Adaptive icon XMLs
    anydpi = os.path.join(RES, "mipmap-anydpi-v26")
    os.makedirs(anydpi, exist_ok=True)
    for name in ("ic_launcher", "ic_launcher_round"):
        with open(os.path.join(anydpi, f"{name}.xml"), "w") as f:
            f.write(
                '<?xml version="1.0" encoding="utf-8"?>\n'
                '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
                '    <background android:drawable="@color/ic_launcher_background"/>\n'
                '    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>\n'
                '</adaptive-icon>\n'
            )
        print("wrote", os.path.join(anydpi, f"{name}.xml"))

    # colors.xml with the sampled background
    with open(os.path.join(RES, "values", "colors.xml"), "w") as f:
        f.write(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<resources>\n'
            f'    <color name="ic_launcher_background">{color}</color>\n'
            '</resources>\n'
        )
    print("wrote", os.path.join(RES, "values", "colors.xml"))
    print("done")


if __name__ == "__main__":
    main()
