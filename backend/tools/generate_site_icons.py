#!/usr/bin/env python3
"""Regenerate Auto160 favicon / apple-touch icons.

Design (like av.by): bright full-bleed brand-gradient square, no dark plate and no
padding, huge condensed near-black "160" filling the tile. A dark icon on a dark
Safari tab bar gets a light outline from the browser; a bright tile does not.

Usage (from backend/):
  python tools/generate_site_icons.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1] / "app" / "static"
ICONS = ROOT / "icons"

# Condensed heavy faces → tallest digits for a given width. First existing wins.
FONT_CANDIDATES = [
    ("/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf", 0),
    ("/System/Library/Fonts/Supplemental/Impact.ttf", 0),
    ("/System/Library/Fonts/Avenir Next Condensed.ttc", 8),  # Heavy
    ("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf", 0),
    ("/usr/share/fonts/truetype/liberation/LiberationSansNarrow-Bold.ttf", 0),
]

# Diagonal brand gradient (top-left → bottom-right).
BG_STOPS = [
    (0.00, (0x3F, 0x7B, 0xF0)),
    (0.50, (0x35, 0xC2, 0xF2)),
    (1.00, (0x6F, 0xE8, 0xB4)),
]
INK = (0x06, 0x0A, 0x12)

TEXT = "160"
# Share of the tile covered by the digits.
FILL_W = 0.94
FILL_H = 0.74
SS = 8  # supersampling factor for crisp small sizes


def _font(px: int) -> ImageFont.FreeTypeFont:
    for path, index in FONT_CANDIDATES:
        if Path(path).is_file():
            return ImageFont.truetype(path, px, index=index)
    raise SystemExit("No usable condensed bold TTF found for icon generation")


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _bg_color(t: float):
    t = max(0.0, min(1.0, t))
    for i in range(len(BG_STOPS) - 1):
        t0, c0 = BG_STOPS[i]
        t1, c1 = BG_STOPS[i + 1]
        if t <= t1:
            u = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return _lerp(c0, c1, u)
    return BG_STOPS[-1][1]


def _background(size: int) -> Image.Image:
    img = Image.new("RGB", (size, size))
    px = img.load()
    denom = 2 * (size - 1) or 1
    for y in range(size):
        for x in range(size):
            px[x, y] = _bg_color((x + y) / denom)
    return img


def _digits_mask(size: int, fill_w: float, fill_h: float) -> Image.Image:
    """White-on-black mask with the glyph box stretched to fill_w × fill_h of the tile."""
    big = size * SS
    font = _font(big)
    probe = Image.new("L", (big * 2, big * 2), 0)
    ImageDraw.Draw(probe).text((big // 2, big // 2), TEXT, font=font, fill=255)
    box = probe.getbbox()
    assert box, "empty glyph box"
    glyphs = probe.crop(box)
    target_w = int(big * fill_w)
    target_h = int(big * fill_h)
    glyphs = glyphs.resize((target_w, target_h), Image.Resampling.LANCZOS)
    mask = Image.new("L", (big, big), 0)
    mask.paste(glyphs, ((big - target_w) // 2, (big - target_h) // 2))
    return mask


def render(size: int) -> Image.Image:
    bg = _background(size * SS)
    mask = _digits_mask(size, FILL_W, FILL_H)
    ink = Image.new("RGB", bg.size, INK)
    bg.paste(ink, (0, 0), mask)
    return bg.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    ICONS.mkdir(parents=True, exist_ok=True)
    sizes = {
        "apple-touch-icon.png": 180,
        "apple-touch-icon-180x180.png": 180,
        "apple-touch-icon-precomposed.png": 180,
        "icon-192.png": 192,
        "icon-512.png": 512,
        "favicon-160.png": 160,
        "favicon-128.png": 128,
        "favicon-48.png": 48,
        "favicon-32.png": 32,
        "favicon-16.png": 16,
    }
    cache: dict[int, Image.Image] = {}
    for name, sz in sizes.items():
        im = cache.setdefault(sz, render(sz))
        im.save(ICONS / name, format="PNG", optimize=True)
        if name.startswith("apple-touch") or name.startswith("favicon-"):
            im.save(ROOT / name, format="PNG", optimize=True)
        print("wrote", name, sz)
    ico = [render(48), render(32), render(16)]
    for path in (ROOT / "favicon.ico", ICONS / "favicon.ico"):
        ico[0].save(
            path,
            format="ICO",
            sizes=[(48, 48), (32, 32), (16, 16)],
            append_images=ico[1:],
        )
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 180 180" width="180" height="180" role="img" aria-label="Auto160">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#3F7BF0"/>
      <stop offset="50%" stop-color="#35C2F2"/>
      <stop offset="100%" stop-color="#6FE8B4"/>
    </linearGradient>
  </defs>
  <rect width="180" height="180" fill="url(#bg)"/>
  <text x="90" y="141" text-anchor="middle" textLength="169" lengthAdjust="spacingAndGlyphs"
        font-family="DIN Condensed, Impact, Arial Narrow, sans-serif" font-size="150" font-weight="700"
        fill="#060A12">160</text>
</svg>
"""
    for path in (ROOT / "favicon.svg", ICONS / "favicon.svg"):
        path.write_text(svg, encoding="utf-8")
    print("done")


if __name__ == "__main__":
    main()
