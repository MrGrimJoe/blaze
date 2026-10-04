"""
Procedural art for Blaze — no API key, no downloads.

  make_character(name, description, out_dir)  -> writes <slug>.png, <slug>_talk.png, <slug>_blink.png
  make_backdrop(place, mood, out_path)        -> writes a 1920x1080 background PNG

Flat-vector style drawn with Pillow at 2x then downsampled. Appearance comes from
keywords in the CAST description ("woman, red coat, glasses") and otherwise from a hash of
the name, so a character looks the same in every run.
"""

from __future__ import annotations

import hashlib
import math
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageFilter

RGB = Tuple[int, int, int]
OUTLINE: RGB = (27, 31, 42)

COLORS: Dict[str, RGB] = {
    "red": (214, 64, 54), "blue": (60, 120, 214), "green": (64, 160, 96), "yellow": (236, 196, 60),
    "orange": (236, 130, 50), "purple": (130, 84, 190), "pink": (236, 130, 170), "black": (40, 42, 52),
    "white": (238, 238, 240), "gray": (130, 136, 148), "grey": (130, 136, 148), "brown": (128, 84, 52),
    "teal": (40, 160, 160), "navy": (36, 52, 110), "beige": (214, 190, 150), "tan": (200, 160, 110),
}
SKINS = [(255, 224, 196), (241, 194, 152), (224, 172, 124), (190, 132, 92), (141, 94, 66), (104, 68, 48)]
HAIRS = [(40, 30, 28), (78, 52, 34), (130, 84, 46), (214, 170, 80), (170, 60, 40), (60, 60, 70), (200, 200, 205)]
TOPS = ["red", "blue", "green", "orange", "purple", "teal", "yellow", "pink", "navy"]
BOTTOMS = [(52, 62, 96), (60, 60, 66), (96, 76, 58), (46, 84, 80)]
GARMENTS_TOP = r"(coat|jacket|shirt|dress|hoodie|sweater|top|blouse|suit|cloak|robe)"
GARMENTS_BOTTOM = r"(pants|jeans|trousers|skirt|shorts)"


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "char"


def _h(s: str) -> int:
    return int(hashlib.sha1(s.encode()).hexdigest(), 16)


@dataclass
class Appearance:
    skin: RGB
    hair: RGB
    hair_style: str          # short | long | bun | bald | curly | spiky
    top: RGB
    bottom: RGB
    shoe: RGB = (36, 38, 48)
    gender: str = "n"        # m | f | n
    child: bool = False
    coat: bool = False
    dress: bool = False
    hat: Optional[str] = None   # fedora | cap | beanie
    glasses: bool = False
    beard: bool = False
    scarf: bool = False
    accent: RGB = (255, 209, 102)
    flags: set = field(default_factory=set)

    @property
    def height_scale(self) -> float:
        return 0.76 if self.child else 1.0


def appearance_for(name: str, description: str = "") -> Appearance:
    d = (description or "").lower()
    h = _h(name.lower())
    pick = lambda seq, k: seq[(h >> k) % len(seq)]

    gender = "n"
    if re.search(r"\b(woman|girl|female|lady|mother|mom|mum|she|her|queen|actress|grandma|sister)\b", d): gender = "f"
    elif re.search(r"\b(man|boy|male|father|dad|he|his|king|grandpa|brother|guy)\b", d): gender = "m"
    else: gender = "f" if (h >> 3) % 2 else "m"
    child = bool(re.search(r"\b(child|kid|boy|girl|little|toddler|young)\b", d))

    skin = pick(SKINS, 5)
    for word, col in (("pale", SKINS[0]), ("dark-skinned", SKINS[4]), ("tan skin", SKINS[2])):
        if word in d: skin = col
    hair = pick(HAIRS, 9)
    m = re.search(r"\b(" + "|".join(COLORS) + r"|blond|blonde)\s+hair\b", d)
    if m: hair = (214, 170, 80) if m.group(1).startswith("blond") else COLORS[m.group(1)]
    style = pick(["short", "short", "spiky", "curly"], 13) if gender != "f" else pick(["long", "long", "bun", "short", "curly"], 13)
    for k in ("bald", "long", "bun", "curly", "spiky", "short"):
        if re.search(r"\b" + k + r"\b", d): style = k

    top = COLORS[pick(TOPS, 17)]
    bottom = pick(BOTTOMS, 21)
    m = re.search(r"\b(" + "|".join(COLORS) + r")\s+" + GARMENTS_TOP, d)
    if m: top = COLORS[m.group(1)]
    m = re.search(r"\b(" + "|".join(COLORS) + r")\s+" + GARMENTS_BOTTOM, d)
    if m: bottom = COLORS[m.group(1)]

    a = Appearance(skin=skin, hair=hair, hair_style=style, top=top, bottom=bottom, gender=gender, child=child)
    a.coat = bool(re.search(r"\b(coat|trench|cloak|robe|detective|suit|jacket)\b", d))
    a.dress = bool(re.search(r"\b(dress|skirt|gown)\b", d)) or (gender == "f" and not a.coat and (h >> 25) % 3 == 0 and not child)
    if re.search(r"\b(fedora|detective)\b", d): a.hat = "fedora"
    elif re.search(r"\b(beanie)\b", d): a.hat = "beanie"
    elif re.search(r"\b(cap|hat)\b", d): a.hat = "cap"
    a.glasses = bool(re.search(r"\b(glasses|spectacles|specs)\b", d))
    a.beard = bool(re.search(r"\b(beard|mustache|moustache)\b", d)) or (gender == "m" and not child and not re.search(r"\b(clean)\b", d) and (h >> 29) % 5 == 0)
    a.scarf = bool(re.search(r"\b(scarf)\b", d))
    if a.hat and style == "bun": a.hair_style = "short"
    return a


# ------------------------------------------------------------------ characters
_W, _H, _S = 400, 720, 2  # final size and supersample factor


def _draw_character(a: Appearance, mouth_open: bool, eyes_closed: bool) -> Image.Image:
    S = _S
    im = Image.new("RGBA", (_W * S, _H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    ow = 5 * S
    P = lambda *v: [int(x * S) for x in v]

    def rr(box, r, fill, outline=OUTLINE, w=ow):
        d.rounded_rectangle(P(*box), radius=int(r * S), fill=fill, outline=outline, width=w)

    def el(box, fill, outline=OUTLINE, w=ow):
        d.ellipse(P(*box), fill=fill, outline=outline, width=w)

    def poly(pts, fill, outline=OUTLINE, w=ow):
        d.polygon(P(*[c for p in pts for c in p]), fill=fill, outline=outline)
        d.line(P(*[c for p in pts + [pts[0]] for c in p]), fill=outline, width=w, joint="curve")

    shade = lambda c, k: tuple(max(0, min(255, int(v * k))) for v in c)

    # ground shadow
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse(P(95, 676, 305, 712), fill=(0, 0, 0, 70))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6 * S)))
    d = ImageDraw.Draw(im)

    skin, hair = a.skin, a.hair
    # legs + shoes
    if a.dress:
        rr((152, 520, 192, 665), 14, skin); rr((208, 520, 248, 665), 14, skin)
    else:
        rr((150, 470, 195, 665), 14, a.bottom); rr((205, 470, 250, 665), 14, a.bottom)
    rr((136, 640, 200, 692), 20, a.shoe); rr((200, 640, 264, 692), 20, a.shoe)

    # arms behind torso, then torso
    rr((76, 262, 120, 472), 20, a.top); rr((280, 262, 324, 472), 20, a.top)
    el((76, 462, 122, 508), skin); el((278, 462, 324, 508), skin)
    if a.dress:
        poly([(122, 290), (278, 290), (322, 565), (78, 565)], a.top)
        rr((120, 250, 280, 330), 34, a.top)
    else:
        rr((115, 250, 285, 492 if not a.coat else 560), 38, a.top)
        if a.coat:
            poly([(170, 250), (230, 250), (200, 340)], (240, 240, 244))
            d.line(P(200, 340, 200, 556), fill=OUTLINE, width=ow // 2)
            for yy in (390, 440, 490): el((192, yy, 208, yy + 16), shade(a.top, 0.6), w=ow // 2)
            poly([(150, 250), (185, 250), (170, 330)], shade(a.top, 0.78))
            poly([(250, 250), (215, 250), (230, 330)], shade(a.top, 0.78))
        else:
            d.arc(P(165, 232, 235, 290), 0, 180, fill=OUTLINE, width=ow)
    if a.scarf:
        rr((148, 236, 252, 282), 20, a.accent)
    # neck + ears + head
    rr((176, 212, 224, 268), 10, shade(skin, 0.94))
    if a.hair_style == "long":
        rr((112, 88, 288, 340), 60, hair)
    if a.hair_style == "bun":
        el((160, 18, 240, 98), hair)
    el((104, 168, 146, 214), skin); el((254, 168, 296, 214), skin)
    el((122, 82, 278, 268), skin)
    # hair front
    if a.hair_style != "bald":
        d.pieslice(P(116, 72, 284, 262), 180, 360, fill=hair, outline=OUTLINE, width=ow)
        if a.hair_style == "curly":
            for cx, cy in ((140, 100), (170, 78), (200, 70), (230, 78), (260, 100), (126, 130), (274, 130)):
                el((cx - 26, cy - 26, cx + 26, cy + 26), hair)
        elif a.hair_style == "spiky":
            for x0 in range(132, 272, 28):
                poly([(x0, 120), (x0 + 14, 62), (x0 + 28, 120)], hair)
        elif a.hair_style == "long":
            rr((112, 120, 140, 300), 14, hair); rr((260, 120, 288, 300), 14, hair)
    # beard
    if a.beard:
        poly([(146, 238), (254, 238), (246, 262), (200, 288), (154, 262)], shade(hair, 0.85))
    # face
    ex = (170, 230); ey = 192
    for x in ex:
        if eyes_closed:
            d.arc(P(x - 14, ey - 8, x + 14, ey + 14), 200, 340, fill=OUTLINE, width=ow)
        else:
            el((x - 13, ey - 17, x + 13, ey + 17), (255, 255, 255), w=int(ow * 0.7))
            el((x - 7, ey - 8, x + 7, ey + 8), OUTLINE, outline=None, w=0)
            el((x - 3, ey - 6, x + 1, ey - 2), (255, 255, 255), outline=None, w=0)
        d.line(P(x - 16, ey - 30, x + 14, ey - 34 if x < 200 else ey - 28), fill=shade(hair, 0.75), width=ow)
    d.line(P(200, 204, 197, 226, 206, 226), fill=shade(skin, 0.7), width=int(ow * 0.7), joint="curve")
    if mouth_open:
        el((180, 236, 220, 268), (90, 34, 44), w=int(ow * 0.8))
        d.pieslice(P(186, 250, 214, 272), 0, 180, fill=(236, 120, 130))
    else:
        d.arc(P(176, 222, 224, 262), 25, 155, fill=OUTLINE, width=ow)
    el((130, 222, 158, 240), (255, 150, 150, 70), outline=None, w=0); el((242, 222, 270, 240), (255, 150, 150, 70), outline=None, w=0)
    if a.glasses:
        for x in ex: el((x - 25, ey - 24, x + 25, ey + 24), (200, 230, 255, 50), w=int(ow * 0.8))
        d.line(P(195, ey - 4, 205, ey - 4), fill=OUTLINE, width=ow)
    # hats
    if a.hat == "fedora":
        el((92, 92, 308, 140), (60, 52, 50)); rr((132, 30, 268, 112), 28, (72, 64, 62))
        rr((132, 84, 268, 104), 6, a.accent if a.accent != (255, 209, 102) else (150, 40, 40))
    elif a.hat == "cap":
        d.pieslice(P(118, 56, 282, 230), 180, 360, fill=a.top if a.top != skin else (60, 90, 160), outline=OUTLINE, width=ow)
        rr((180, 120, 312, 146), 12, shade(a.top, 0.8))
    elif a.hat == "beanie":
        d.pieslice(P(116, 50, 284, 240), 180, 360, fill=a.accent, outline=OUTLINE, width=ow)
        el((184, 28, 216, 60), (255, 255, 255))
    return im.resize((_W, _H), Image.LANCZOS)


def make_character(name: str, description: str, out_dir: Path) -> Tuple[Path, Appearance]:
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    a = appearance_for(name, description)
    base = out_dir / f"{slug(name)}.png"
    _draw_character(a, False, False).save(base)
    _draw_character(a, True, False).save(out_dir / f"{slug(name)}_talk.png")
    _draw_character(a, False, True).save(out_dir / f"{slug(name)}_blink.png")
    return base, a


# ------------------------------------------------------------------ moods & backdrops
@dataclass
class Mood:
    name: str
    sky_top: RGB
    sky_bot: RGB
    light: Tuple[float, float, float]     # multiplies "lit by ambient" colours
    tint: int                             # multiplies characters (0xRRGGBB)
    night: bool = False
    weather: Optional[str] = None         # rain | storm | snow
    dark_interior: bool = False


MOODS = {
    "day": Mood("day", (108, 178, 236), (206, 232, 250), (1, 1, 1), 0xFFFFFF),
    "sunset": Mood("sunset", (84, 70, 146), (252, 168, 104), (1.0, 0.8, 0.68), 0xFFD9B8),
    "night": Mood("night", (8, 12, 32), (34, 46, 92), (0.34, 0.4, 0.66), 0xA9B6E8, night=True),
    "dim": Mood("dim", (60, 66, 84), (96, 100, 118), (0.5, 0.48, 0.5), 0xC8C4C4, dark_interior=True),
    "rain": Mood("rain", (96, 106, 124), (150, 160, 174), (0.74, 0.8, 0.88), 0xC4CEDC, weather="rain"),
    "storm": Mood("storm", (38, 44, 62), (78, 86, 106), (0.5, 0.55, 0.68), 0x9AA6C0, night=True, weather="storm"),
    "snow": Mood("snow", (170, 182, 198), (226, 232, 240), (0.92, 0.95, 1.0), 0xEAF0FF, weather="snow"),
}
MOOD_ALIASES = {"rainy": "rain", "raining": "rain", "stormy": "storm", "thunder": "storm", "snowy": "snow", "dark": "night",
                "evening": "sunset", "dusk": "sunset", "dawn": "sunset", "morning": "day", "sunny": "day", "noon": "day",
                "moody": "dim", "gloomy": "dim", "cloudy": "rain"}


def mood_from(text: str) -> Mood:
    """First mood word wins, except that rain/snow + night combine (a rainy night is dark AND wet)."""
    t = (text or "").lower()
    found = []
    for w in re.findall(r"[a-z]+", t):
        w = MOOD_ALIASES.get(w, w)
        if w in MOODS and w not in found:
            found.append(w)
    if not found:
        return MOODS["day"]
    if found[0] in ("rain", "snow") and "night" in found or found[0] == "night" and any(f in ("rain", "snow") for f in found):
        wet = next(f for f in found if f in ("rain", "snow"))
        n = MOODS["night"]
        return Mood(f"night_{wet}", n.sky_top, n.sky_bot, n.light, n.tint, night=True, weather=wet)
    return MOODS[found[0]]


PLACES = [
    ("street", r"street|city|road|alley|town|sidewalk|downtown|avenue|outside|corner"),
    ("warehouse", r"warehouse|factory|garage|basement|dungeon|cellar|storage|hangar|cave"),
    ("forest", r"forest|woods|jungle|park|garden|camp|trail|field|farm"),
    ("beach", r"beach|sea|ocean|shore|lake|harbor|dock|coast"),
    ("office", r"office|school|classroom|lab|shop|cafe|restaurant|bank|library|store|station|hospital|airport|meeting"),
    ("room", r"room|house|home|kitchen|bedroom|apartment|hall|living|flat|hotel|inside|indoors"),
]


def place_from(text: str) -> str:
    t = (text or "").lower()
    for name, pat in PLACES:
        if re.search(pat, t): return name
    return "street"


W, H = 1920, 1080


def _grad(top: RGB, bot: RGB, y0=0, y1=H, w=W) -> Image.Image:
    g = Image.new("RGB", (w, y1 - y0))
    d = ImageDraw.Draw(g)
    for y in range(y1 - y0):
        t = y / max(1, y1 - y0 - 1)
        d.line([(0, y), (w, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    return g


def _glow(im: Image.Image, cx, cy, r, color, alpha=120, blur=None):
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (alpha,))
    layer = layer.filter(ImageFilter.GaussianBlur(blur or r * 0.6))
    base = im.convert("RGBA"); base.alpha_composite(layer)
    return base.convert("RGB")


def make_backdrop(place: str, mood: Mood, out_path: Path, seed: int = 0) -> Path:
    rng = random.Random(f"{place}-{mood.name}-{seed}")
    L = mood.light
    sh = lambda c: tuple(max(0, min(255, int(c[i] * L[i]))) for i in range(3))
    im = _grad(mood.sky_top, mood.sky_bot)
    d = ImageDraw.Draw(im)
    horizon = int(H * 0.62)

    def sky_bodies():
        if mood.night:
            for _ in range(140):
                x, y, r = rng.randrange(W), rng.randrange(int(H * 0.5)), rng.choice((1, 1, 2, 2, 3))
                d.ellipse([x - r, y - r, x + r, y + r], fill=(220, 226, 255))
        if mood.weather in (None, "snow") or mood.name in ("night", "sunset", "day"):
            x, y = int(W * rng.choice((0.2, 0.78))), int(H * 0.2)
            col = (236, 240, 255) if mood.night else (255, 236, 170) if mood.name != "sunset" else (255, 214, 140)
            nonlocal_im[0] = _glow(nonlocal_im[0], x, y, 110, col, 140)
            d2 = ImageDraw.Draw(nonlocal_im[0]); d2.ellipse([x - 44, y - 44, x + 44, y + 44], fill=col)
        if not mood.night and mood.weather is None:
            for _ in range(5):
                cx, cy = rng.randrange(W), rng.randrange(60, 300)
                cl = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dd = ImageDraw.Draw(cl)
                for k in range(5): dd.ellipse([cx + k * 50 - 70, cy - 26 - (k % 2) * 14, cx + k * 50 + 70, cy + 34], fill=(255, 255, 255, 150))
                b = nonlocal_im[0].convert("RGBA"); b.alpha_composite(cl.filter(ImageFilter.GaussianBlur(10))); nonlocal_im[0] = b.convert("RGB")
        if mood.weather in ("rain", "storm"):
            cl = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dd = ImageDraw.Draw(cl)
            for k in range(14): dd.ellipse([k * 150 - 100, rng.randrange(0, 160) - 60, k * 150 + 260, rng.randrange(120, 300)], fill=(60, 66, 80, 120))
            b = nonlocal_im[0].convert("RGBA"); b.alpha_composite(cl.filter(ImageFilter.GaussianBlur(40))); nonlocal_im[0] = b.convert("RGB")

    nonlocal_im = [im]
    outdoor = place in ("street", "forest", "beach")
    if outdoor:
        sky_bodies(); im = nonlocal_im[0]; d = ImageDraw.Draw(im)

    lit = lambda: mood.night or mood.dark_interior

    if place == "street":
        # far skyline, near buildings, road
        for layer, (base_h, col, wmin, wmax) in enumerate([(0.30, (92, 108, 140), 90, 170), (0.40, (66, 78, 108), 120, 220)]):
            x = -20
            while x < W:
                bw, bh = rng.randrange(wmin, wmax), int(H * (base_h + rng.random() * 0.22))
                c = sh(col)
                d.rectangle([x, horizon - bh, x + bw, horizon + 8], fill=c)
                for wy in range(horizon - bh + 26, horizon - 10, 44):
                    for wx in range(x + 14, x + bw - 20, 34):
                        on = rng.random() < (0.45 if lit() else 0.12)
                        d.rectangle([wx, wy, wx + 16, wy + 22], fill=(255, 214, 120) if on else tuple(min(255, v + 18) for v in c))
                x += bw + rng.randrange(0, 14)
        d.rectangle([0, horizon, W, H], fill=sh((82, 86, 96)))                              # sidewalk + road
        d.rectangle([0, horizon, W, horizon + 70], fill=sh((150, 150, 158)))
        d.rectangle([0, horizon + 70, W, horizon + 84], fill=sh((110, 110, 118)))
        d.rectangle([0, horizon + 84, W, H], fill=sh((58, 60, 70)))
        for x in range(-60, W, 260): d.rectangle([x, int(H * 0.93), x + 130, int(H * 0.93) + 12], fill=sh((230, 210, 120)))
        for lx in (int(W * 0.12), int(W * 0.88)):                                           # street lamps
            d.rectangle([lx - 8, horizon - 360, lx + 8, horizon + 70], fill=sh((40, 44, 56)))
            d.rectangle([lx - 50, horizon - 372, lx + 12, horizon - 356], fill=sh((40, 44, 56)))
            if lit():
                im = _glow(im, lx - 38, horizon - 340, 150, (255, 220, 140), 150); d = ImageDraw.Draw(im)
            d.ellipse([lx - 52, horizon - 356, lx - 22, horizon - 338], fill=(255, 236, 180) if lit() else sh((210, 210, 200)))
    elif place == "forest":
        d.rectangle([0, horizon - 40, W, H], fill=sh((52, 120, 70)))
        for k, (col, hmin, hmax, step, yoff) in enumerate([((58, 104, 86), 260, 380, 120, 40), ((40, 88, 62), 330, 500, 140, 70), ((26, 66, 44), 420, 640, 200, 120)]):
            x = -60
            while x < W + 60:
                th = rng.randrange(hmin, hmax); tw = rng.randrange(90, 150); base = horizon + yoff
                c = sh(col)
                d.rectangle([x + tw // 2 - 10, base - 30, x + tw // 2 + 10, base + 40], fill=sh((60, 40, 30)))
                for j in range(4):
                    d.polygon([(x + tw // 2, base - th + j * th * 0.18), (x - 8 + j * 6, base - 30 - (3 - j) * th * 0.08), (x + tw + 8 - j * 6, base - 30 - (3 - j) * th * 0.08)], fill=c)
                x += step + rng.randrange(-30, 40)
        d.polygon([(int(W * 0.3), H), (int(W * 0.46), horizon + 60), (int(W * 0.56), horizon + 60), (int(W * 0.78), H)], fill=sh((176, 146, 100)))
        if mood.night:
            for _ in range(40):
                x, y = rng.randrange(W), rng.randrange(int(H * 0.45), int(H * 0.9))
                im = _glow(im, x, y, 10, (220, 255, 140), 200, 6)
            d = ImageDraw.Draw(im)
    elif place == "beach":
        sea_top = horizon - 120
        d.rectangle([0, sea_top, W, horizon + 10], fill=sh((40, 120, 190)))
        for y in range(sea_top + 10, horizon, 22):
            for x in range(rng.randrange(60), W, 140):
                d.arc([x, y, x + 70, y + 14], 200, 340, fill=sh((150, 210, 240)), width=3)
        sand = _grad(sh((236, 214, 160)), sh((206, 178, 120)), horizon, H)
        im.paste(sand, (0, horizon)); d = ImageDraw.Draw(im)
        px = int(W * 0.84)                                                                   # palm
        d.line([px, H, px - 40, horizon - 220], fill=sh((100, 70, 44)), width=26)
        for ang in (-150, -110, -70, -30, 10, 40):
            ex, ey = px - 40 + int(190 * math.cos(math.radians(ang))), horizon - 220 + int(120 * math.sin(math.radians(ang)))
            d.line([px - 40, horizon - 220, ex, ey], fill=sh((40, 130, 70)), width=18)
    elif place == "warehouse":
        im = _grad(sh((86, 88, 98)), sh((52, 54, 64)), 0, horizon); full = Image.new("RGB", (W, H), sh((60, 62, 70))); full.paste(im, (0, 0)); im = full
        d = ImageDraw.Draw(im)
        for x in range(0, W, 120): d.rectangle([x, 0, x + 6, horizon], fill=sh((46, 48, 56)))
        d.rectangle([0, horizon, W, H], fill=sh((92, 92, 98))); d.rectangle([0, horizon, W, horizon + 10], fill=sh((40, 42, 50)))
        for x in range(0, W, 300): d.line([x, horizon + 10, x - 240 + (x - W // 2) // 3, H], fill=sh((70, 70, 78)), width=3)
        for cx, cy, s in ((int(W * 0.1), horizon - 10, 190), (int(W * 0.24), horizon + 10, 140), (int(W * 0.9), horizon - 10, 210), (int(W * 0.76), horizon + 5, 150)):
            d.rectangle([cx - s // 2, cy - s, cx + s // 2, cy], fill=sh((150, 104, 62)), outline=sh((70, 46, 28)), width=6)
            for k in range(1, 4): d.line([cx - s // 2, cy - s + k * s // 4, cx + s // 2, cy - s + k * s // 4], fill=sh((110, 76, 44)), width=4)
        for lx in (int(W * 0.35), int(W * 0.65)):
            d.line([lx, 0, lx, 150], fill=(30, 30, 36), width=4); d.ellipse([lx - 34, 140, lx + 34, 176], fill=(255, 232, 170))
            cone = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(cone).polygon([(lx - 26, 170), (lx + 26, 170), (lx + 300, horizon + 160), (lx - 300, horizon + 160)], fill=(255, 236, 170, 70))
            b = im.convert("RGBA"); b.alpha_composite(cone.filter(ImageFilter.GaussianBlur(14))); im = b.convert("RGB"); d = ImageDraw.Draw(im)
    elif place == "office":
        im = Image.new("RGB", (W, H), sh((196, 202, 214))); d = ImageDraw.Draw(im)
        d.rectangle([0, horizon + 60, W, H], fill=sh((92, 100, 118)))
        d.rectangle([0, horizon + 50, W, horizon + 66], fill=sh((70, 76, 92)))
        wx0, wx1 = int(W * 0.22), int(W * 0.78)
        win = _grad(mood.sky_top, mood.sky_bot, 120, horizon - 40, wx1 - wx0); im.paste(win, (wx0, 120)); d = ImageDraw.Draw(im)
        x = wx0
        while x < wx1:
            bw = rng.randrange(50, 110); bh = rng.randrange(60, 230)
            d.rectangle([x, horizon - 40 - bh, min(x + bw, wx1), horizon - 40], fill=sh((110, 122, 150))); x += bw + 6
        d.rectangle([wx0 - 10, 110, wx1 + 10, horizon - 30], outline=sh((70, 76, 92)), width=14)
        d.line([W // 2, 120, W // 2, horizon - 40], fill=sh((70, 76, 92)), width=10)
        d.rectangle([int(W * 0.05), horizon + 30, int(W * 0.17), horizon + 200], fill=sh((120, 84, 56)))          # desk
        d.ellipse([int(W * 0.84), horizon - 120, int(W * 0.93), horizon + 40], fill=sh((60, 130, 80)))               # plant
        d.rectangle([int(W * 0.87), horizon + 30, int(W * 0.90), horizon + 120], fill=sh((150, 90, 60)))
    else:  # room
        wall = sh((214, 196, 172)) if not mood.dark_interior else sh((150, 140, 132))
        im = Image.new("RGB", (W, H), wall); d = ImageDraw.Draw(im)
        d.rectangle([0, int(H * 0.44), W, horizon + 50], fill=sh((186, 164, 140)))                                    # wainscot
        d.rectangle([0, int(H * 0.44) - 8, W, int(H * 0.44) + 8], fill=sh((140, 118, 96)))
        d.rectangle([0, horizon + 50, W, H], fill=sh((150, 106, 70)))
        for x in range(-200, W + 200, 150): d.line([x, horizon + 50, x + (x - W // 2) // 2, H], fill=sh((120, 82, 52)), width=3)
        wx0, wx1 = int(W * 0.36), int(W * 0.64)
        win = _grad(mood.sky_top, mood.sky_bot, 130, int(H * 0.5), wx1 - wx0); im.paste(win, (wx0, 130)); d = ImageDraw.Draw(im)
        d.rectangle([wx0 - 8, 122, wx1 + 8, int(H * 0.5) + 8], outline=sh((244, 240, 232)), width=14)
        d.line([W // 2, 130, W // 2, int(H * 0.5)], fill=sh((244, 240, 232)), width=10)
        d.polygon([(wx0 - 70, 110), (wx0 + 20, 110), (wx0 + 60, int(H * 0.55)), (wx0 - 70, int(H * 0.55))], fill=sh((170, 80, 80)))
        d.polygon([(wx1 + 70, 110), (wx1 - 20, 110), (wx1 - 60, int(H * 0.55)), (wx1 + 70, int(H * 0.55))], fill=sh((170, 80, 80)))
        for fx, fy, fw, fh in ((int(W * 0.09), 210, 150, 110), (int(W * 0.14), 360, 100, 130), (int(W * 0.79), 240, 170, 120)):
            d.rectangle([fx, fy, fx + fw, fy + fh], fill=sh((230, 226, 210)), outline=sh((90, 64, 44)), width=8)
            d.rectangle([fx + 14, fy + 14, fx + fw - 14, fy + fh - 14], fill=sh((110, 150, 170)))
        d.rectangle([int(W * 0.86), horizon - 260, int(W * 0.97), horizon + 50], fill=sh((100, 70, 48)))              # shelf
        for k in range(4): d.line([int(W * 0.86), horizon - 260 + k * 86, int(W * 0.97), horizon - 260 + k * 86], fill=sh((70, 48, 32)), width=8)
        lx = int(W * 0.2)
        d.rectangle([lx - 6, horizon - 90, lx + 6, horizon + 50], fill=sh((60, 48, 40)))
        d.polygon([(lx - 50, horizon - 90), (lx + 50, horizon - 90), (lx + 30, horizon - 160), (lx - 30, horizon - 160)], fill=(250, 226, 160))
        if lit() or mood.night:
            im = _glow(im, lx, horizon - 130, 220, (255, 214, 140), 150); d = ImageDraw.Draw(im)

    # weather haze + vignette
    if mood.weather:
        im = Image.blend(im, Image.new("RGB", im.size, mood.sky_bot), 0.12)
    vig = Image.new("L", im.size, 0); vd = ImageDraw.Draw(vig)
    vd.ellipse([-W * 0.25, -H * 0.3, W * 1.25, H * 1.3], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(160))
    dark = ImageChops.multiply(im, Image.new("RGB", im.size, (170, 170, 180)))
    im = Image.composite(im, dark, vig)
    out_path = Path(out_path); out_path.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_path)
    return out_path


def make_title_background(top: RGB, bottom: RGB, out_path: Path, seed: int = 7) -> Path:
    """Gradient with soft drifting dots, for the title card (used through ImageProp like any backdrop)."""
    rng = random.Random(seed)
    im = _grad(top, bottom).convert("RGBA")
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for _ in range(90):
        x, y, r = rng.randrange(W), rng.randrange(H), rng.choice((2, 2, 3, 4, 6))
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, rng.randrange(25, 80)))
    im.alpha_composite(layer.filter(ImageFilter.GaussianBlur(1.2)))
    out_path = Path(out_path); out_path.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(out_path)
    return out_path
