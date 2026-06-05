"""Создаёт иконку FinanceFugue.ico в стиле приложения."""
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise SystemExit("Установите Pillow: pip install Pillow")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "images" / "FinanceFugue.ico"
OUT.parent.mkdir(exist_ok=True)

BG = (30, 30, 30)
ACCENT = (0, 209, 255)
SIZES = [(256, 256), (48, 48), (32, 32), (16, 16)]
images = []

for size in SIZES:
    img = Image.new("RGBA", size, BG + (255,))
    draw = ImageDraw.Draw(img)
    margin = max(2, size[0] // 8)
    draw.rounded_rectangle(
        [margin, margin, size[0] - margin, size[1] - margin],
        radius=size[0] // 6,
        fill=(42, 42, 42, 255),
        outline=ACCENT + (255,),
        width=max(1, size[0] // 32),
    )
    font_size = size[0] // 2
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()
    text = "F"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((size[0] - tw) / 2, (size[1] - th) / 2 - size[0] * 0.05),
        text,
        fill=ACCENT + (255,),
        font=font,
    )
    images.append(img)

images[0].save(OUT, format="ICO", sizes=[(s[0], s[1]) for s in SIZES])
print("Created", OUT)
