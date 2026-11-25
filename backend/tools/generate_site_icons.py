#!/usr/bin/env python3
"""Regenerate Auto160 favicon / apple-touch icons with Safari-safe padding.

Usage (from backend/):
  python tools/generate_site_icons.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1] / "app" / "static"
ICONS = ROOT / "icons"
FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
# Fallback for Linux CI / VM
FALLBACK_FONTS = [
    FONT_PATH,
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]
STOPS = [
    (0.00, (0x4A, 0x7F, 0xE8)),
    (0.55, (0x3E, 0xC8, 0xF0)),
    (1.00, (0x7F, 0xE8, 0xB0)),
]
# Safari Favorites apply a heavy squircle; keep ~26% empty on each side.
PAD_RATIO = 0.26
PAD_RATIO_SMALL = 0.18


def _font_path() -> str:
    for path in FALLBACK_FONTS:
        if Path(path).is_file():
            return path
    raise SystemExit("No usable bold TTF found for icon generation")


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _grad_color(t: float):
    t = max(0.0, min(1.0, t))
    for i in range(len(STOPS) - 1):
        t0, c0 = STOPS[i]
        t1, c1 = STOPS[i + 1]
        if t <= t1:
            u = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return _lerp(c0, c1, u)
    return STOPS[-1][1]


def render(size: int, pad_ratio: float = PAD_RATIO) -> Image.Image:
    font_file = _font_path()
    img = Image.new("RGB", (size, size), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    text = "160"
    max_w = int(size * (1 - 2 * pad_ratio))
    lo, hi = 4, size
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        font = ImageFont.truetype(font_file, mid)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_w:
            best = (font, bbox)
            lo = mid + 1
        else:
            hi = mid - 1
    assert best is not None
    font, bbox = best
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) // 2 - bbox[0]
    y = (size - th) // 2 - bbox[1]
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).text((x, y), text, font=font, fill=255)
    mp = mask.load()
    xs = [ix for ix in range(size) for iy in range(size) if mp[ix, iy] > 0]
    xmin, xmax = min(xs), max(xs)
    shift = ((size - 1 - xmax) - xmin) // 2
    if shift:
        shifted = Image.new("L", (size, size), 0)
        shifted.paste(mask, (shift, 0))
        mask = shifted
        mp = mask.load()
        xs = [ix for ix in range(size) for iy in range(size) if mp[ix, iy] > 0]
        xmin, xmax = min(xs), max(xs)
    pixels = img.load()
    span = max(1, xmax - xmin)
    for iy in range(size):
        for ix in range(size):
            a = mp[ix, iy]
            if not a:
                continue
            r, g, b = _grad_color((ix - xmin) / span)
            pixels[ix, iy] = (r * a // 255, g * a // 255, b * a // 255) if a < 255 else (r, g, b)
    return img


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
    for name, sz in sizes.items():
        im = render(sz, PAD_RATIO if sz >= 48 else PAD_RATIO_SMALL)
        im.save(ICONS / name, format="PNG", optimize=True)
        if name.startswith("apple-touch") or name.startswith("favicon-"):
            im.save(ROOT / name, format="PNG", optimize=True)
        print("wrote", name, sz)
    ico = [render(48), render(32, PAD_RATIO_SMALL), render(16, PAD_RATIO_SMALL)]
    for path in (ROOT / "favicon.ico", ICONS / "favicon.ico"):
        ico[0].save(
            path,
            format="ICO",
            sizes=[(48, 48), (32, 32), (16, 16)],
            append_images=ico[1:],
        )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 180 180" width="180" height="180" role="img" aria-label="Auto160">
  <rect x="0" y="0" width="180" height="180" fill="#000000"/>
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#4A7FE8"/>
      <stop offset="55%" stop-color="#3EC8F0"/>
      <stop offset="100%" stop-color="#7FE8B0"/>
    </linearGradient>
  </defs>
  <!-- ~{int(PAD_RATIO*100)}% side padding so Safari Favorites squircle does not clip the \"0\" -->
  <text x="90" y="108" text-anchor="middle" font-family="Arial Black, Helvetica Neue, Arial, sans-serif" font-size="46" font-weight="900" fill="url(#g)" letter-spacing="-0.5">160</text>
</svg>
"""
    for path in (ROOT / "favicon.svg", ICONS / "favicon.svg"):
        path.write_text(svg, encoding="utf-8")
    print("done")


if __name__ == "__main__":
    main()
