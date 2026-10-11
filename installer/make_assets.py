"""Draws Blaze's icon and the installer's wizard images. Output is committed, so CI does not need this; run it to change the look:

    python installer/make_assets.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "assets"
INK, PAPER, MUTE, ACCENT = (21, 23, 26), (251, 251, 250), (123, 128, 138), (43, 68, 255)
FONTS = ["C:/Windows/Fonts/segoeuib.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Helvetica.ttc"]
FONTS_REGULAR = ["C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Helvetica.ttc"]


def font(size, bold=True):
    for f in (FONTS if bold else FONTS_REGULAR):
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def mark(size: int, tile: bool = True) -> Image.Image:
    """The mark: a speech bubble holding a play triangle, on an ink rounded square."""
    s = size * 4                                   # draw large, shrink for smooth edges
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if tile:
        d.rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * 0.22), fill=INK)
    bx0, by0, bx1, by1 = int(s * .17), int(s * .20), int(s * .83), int(s * .68)
    d.rounded_rectangle((bx0, by0, bx1, by1), radius=int(s * .12), fill=PAPER)
    d.polygon([(int(s * .30), by1 - 2), (int(s * .30), int(s * .83)), (int(s * .46), by1 - 2)], fill=PAPER)     # the bubble's tail
    cx, cy, r = (bx0 + bx1) // 2 + int(s * .02), (by0 + by1) // 2, int(s * .14)
    d.polygon([(cx - r * 0.8, cy - r), (cx - r * 0.8, cy + r), (cx + r * 1.05, cy)], fill=ACCENT)                # play
    return im.resize((size, size), Image.LANCZOS)


def icon():
    base = mark(256)
    base.save(OUT / "blaze.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    base.save(OUT / "blaze.png")


def wizard_large(w=164, h=314):
    """The tall picture on the Welcome and Finished pages."""
    k = 3
    im = Image.new("RGB", (w * k, h * k), INK)
    d = ImageDraw.Draw(im)
    for y in range(h * k):                          # a quiet vertical gradient toward the accent
        t = y / (h * k)
        d.line([(0, y), (w * k, y)], fill=tuple(int(INK[i] + (c - INK[i]) * 0.22 * t * t) for i, c in enumerate(ACCENT)))
    m = mark(int(w * 0.70 * k), tile=False)
    im.paste(m, ((w * k - m.width) // 2, int(h * k * 0.12)), m)
    d.text((w * k // 2, int(h * k * 0.52)), "Blaze", font=font(int(30 * k)), fill=PAPER, anchor="mm")
    d.text((w * k // 2, int(h * k * 0.60)), "screenplay to video", font=font(int(11 * k), False), fill=(190, 195, 205), anchor="mm")
    im.resize((w, h), Image.LANCZOS).save(OUT / "wizard-large.bmp")


def wizard_small(w=55, h=58):
    """The small picture at the top right of the other pages."""
    k = 6
    im = Image.new("RGB", (w * k, h * k), PAPER)
    m = mark(int(min(w, h) * 0.86 * k))
    im.paste(m, ((w * k - m.width) // 2, (h * k - m.height) // 2), m)
    im.resize((w, h), Image.LANCZOS).save(OUT / "wizard-small.bmp")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    icon(); wizard_large(); wizard_small()
    print("wrote", ", ".join(sorted(p.name for p in OUT.iterdir())))
