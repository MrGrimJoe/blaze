"""
The asset library: your own characters and backdrops, used instead of Blaze's generated art.

    library/characters/<name>.png  [+ <name>_talk.png  <name>_blink.png]     transparent PNG, feet at the bottom edge
    library/backdrops/<name>.png                                             any image (16:9 works best)

Use them from a screenplay:
    CAST: ROBO = asset:robo        (or just name the character ROBO: a library character with that name is picked up)
    BACKDROP: lab                  (a library backdrop, or a path relative to the screenplay)

Add to it with `blaze asset add <file>` (PNG/JPG, or a .blend rendered through Blender).
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image

from . import blender as bl

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_") or "asset"


class Library:
    def __init__(self, roots: List[Path]):
        seen, self.roots = set(), []
        for r in roots:
            r = Path(r)
            if r not in seen:
                seen.add(r); self.roots.append(r)

    @classmethod
    def default(cls, explicit: Optional[Path] = None, *around: Optional[Path]) -> "Library":
        """--library, then ./library next to the screenplay / project, then ./library in the working folder."""
        roots = [Path(explicit)] if explicit else []
        for base in around:
            if base: roots.append(Path(base) / "library")
        roots.append(Path.cwd() / "library")
        return cls(roots)

    @property
    def home(self) -> Path:
        return self.roots[0]

    # ---- lookup
    def _find(self, kind: str, name: str, exts=IMAGE_EXT) -> Optional[Path]:
        key = slug(name)
        for root in self.roots:
            for ext in exts:
                p = root / kind / (key + ext)
                if p.exists():
                    return p
        return None

    def character(self, name: str) -> Optional[Path]:
        return self._find("characters", name, (".png",))

    def backdrop(self, name: str, relative_to: Optional[Path] = None) -> Optional[Path]:
        direct = Path(name)
        for p in ([direct] if direct.is_absolute() else []) + ([Path(relative_to) / direct] if relative_to else []) + [direct]:
            if p.suffix.lower() in IMAGE_EXT and p.exists():
                return p
        return self._find("backdrops", name)

    def list(self) -> Dict[str, List[str]]:
        out = {"characters": [], "backdrops": []}
        for root in self.roots:
            for kind in out:
                d = root / kind
                if d.exists():
                    for p in sorted(d.iterdir()):
                        if p.suffix.lower() in IMAGE_EXT and not re.search(r"_(talk|blink)$", p.stem):
                            out[kind].append(p.stem)
        return {k: sorted(set(v)) for k, v in out.items()}

    # ---- add
    def add_character(self, src: Path, name: Optional[str] = None, *, blender: Optional[str] = None, samples: int = 32,
                      yaw: float = 0.0, size=(400, 720)) -> List[Path]:
        src = Path(src)
        name = slug(name or src.stem)
        dest = self.home / "characters"
        dest.mkdir(parents=True, exist_ok=True)
        if src.suffix.lower() == ".blend":
            return bl.render_sprites(src, dest, name, size, samples, yaw, blender)
        written = []
        for suffix in ("", "_talk", "_blink"):
            f = src.with_name(src.stem + suffix + src.suffix) if suffix else src
            if not f.exists():
                continue
            im = Image.open(f).convert("RGBA")
            out = dest / f"{name}{suffix}.png"
            im.save(out)
            written.append(out)
        if not written:
            raise FileNotFoundError(src)
        return written

    def add_backdrop(self, src: Path, name: Optional[str] = None, *, blender: Optional[str] = None, samples: int = 32,
                     size=(1920, 1080)) -> Path:
        src = Path(src)
        name = slug(name or src.stem)
        dest = self.home / "backdrops"
        dest.mkdir(parents=True, exist_ok=True)
        out = dest / f"{name}.png"
        if src.suffix.lower() == ".blend":
            return bl.render_still(src, out, size, samples, blender=blender)
        im = Image.open(src).convert("RGB")
        # cover-crop to the target aspect so it fills the frame without stretching
        tw, th = size
        scale = max(tw / im.width, th / im.height)
        im = im.resize((max(tw, round(im.width * scale)), max(th, round(im.height * scale))), Image.LANCZOS)
        left, top = (im.width - tw) // 2, (im.height - th) // 2
        im.crop((left, top, left + tw, top + th)).save(out)
        return out

    def has_alpha(self, path: Path) -> bool:
        try:
            im = Image.open(path)
            return im.mode in ("RGBA", "LA") and im.convert("RGBA").getchannel("A").getextrema()[0] < 250
        except Exception:
            return False
