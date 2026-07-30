"""Generate static/og-default.png for Telegram/social previews."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "app" / "static" / "og-default.jpg"
LOGO = ROOT / "app" / "static" / "brand" / "logo-v5-horizontal.png"

W, H = 1200, 630


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def logo_on_transparent(path: Path, target_width: int) -> Image.Image:
    src = Image.open(path).convert("RGBA")
    pixels = src.load()
    assert pixels is not None
    for y in range(src.height):
        for x in range(src.width):
            r, g, b, a = pixels[x, y]
            # Treat near-black background as transparent
            if r < 28 and g < 28 and b < 28:
                pixels[x, y] = (r, g, b, 0)
            else:
                pixels[x, y] = (r, g, b, 255)
    ratio = target_width / src.width
    return src.resize((target_width, max(1, int(src.height * ratio))), Image.Resampling.LANCZOS)


def main() -> None:
    img = Image.new("RGB", (W, H), "#eaf1ff")
    draw = ImageDraw.Draw(img)

    # Soft gradient
    for y in range(H):
        t = y / (H - 1)
        r = int(234 + (220 - 234) * t)
        g = int(241 + (232 - 241) * t)
        b = int(255 + (251 - 255) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Card
    card = (72, 72, 1128, 558)
    draw.rounded_rectangle(card, radius=36, fill="#ffffff", outline="#c9dcff", width=4)

    # Brand logo
    logo = logo_on_transparent(LOGO, target_width=520)
    lx = (W - logo.width) // 2
    ly = 150
    img.paste(logo, (lx, ly), logo)

    # Taglines
    font_sub = load_font(34)
    font_line = load_font(28)
    sub = "подбор авто до 160 л.с. в Беларуси"
    line = "Каталог · Объявления av.by · Проверка VIN"

    def center_text(text: str, y: int, font: ImageFont.ImageFont, fill: str) -> None:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, y), text, font=font, fill=fill)

    center_text(sub, 340, font_sub, "#54637f")
    center_text(line, 400, font_line, "#1d4ed8")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, format="JPEG", quality=88, optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
