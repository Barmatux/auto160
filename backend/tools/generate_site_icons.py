#!/usr/bin/env python3
"""Regenerate the framed tab favicons from the master Auto160 logo.

Master: app/static/icons/icon-512.png (black tile, gradient "160") — also used as is for
apple-touch-icon / bookmarks / home screen, so those are NOT touched here.

Tab favicons get our own white frame: Safari draws a light outline around dark icons on a dark
tab bar, so we draw the frame ourselves. The result is fully opaque (alpha makes Safari paint
a white plate): white square, black rounded tile inset by the frame, logo inside.

Usage (from backend/):
  python tools/generate_site_icons.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"
ICONS = STATIC / "icons"
MASTER = ICONS / "icon-512.png"

SS = 8  # supersampling for the rounded mask
SIZES = [16, 32, 48, 128, 160]
FRAME = {16: 1, 32: 2, 48: 3, 128: 8, 160: 10}  # white frame width in px
WHITE = (255, 255, 255)


def framed(master: Image.Image, size: int) -> Image.Image:
    frame = FRAME[size]
    inner = size - 2 * frame
    radius = round(inner * 0.22)

    big_inner = inner * SS
    tile = master.resize((big_inner, big_inner), Image.LANCZOS)
    mask = Image.new("L", (big_inner, big_inner), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, big_inner - 1, big_inner - 1), radius=radius * SS, fill=255
    )
    tile.putalpha(mask)
    tile = tile.resize((inner, inner), Image.LANCZOS)

    out = Image.new("RGB", (size, size), WHITE)
    out.paste(tile, (frame, frame), tile)
    return out


def main() -> None:
    master = Image.open(MASTER).convert("RGB")
    images = {s: framed(master, s) for s in SIZES}
    for s, im in images.items():
        im.save(ICONS / f"favicon-{s}.png", optimize=True)
    # Legacy copies in /static (some clients request these paths).
    for s in (32, 48, 160):
        images[s].save(STATIC / f"favicon-{s}.png", optimize=True)
    images[128].save(STATIC / "favicon-128.png", optimize=True)
    images[16].save(STATIC / "favicon-16.png", optimize=True)
    ico_sizes = [(16, 16), (32, 32), (48, 48)]
    images[48].save(ICONS / "favicon.ico", format="ICO", sizes=ico_sizes)
    images[48].save(STATIC / "favicon.ico", format="ICO", sizes=ico_sizes)
    print("favicons written:", ", ".join(f"{s}px" for s in SIZES))


if __name__ == "__main__":
    main()
