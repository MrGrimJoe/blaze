"""
CdrcaSceneComposer - builds a plain CDRCA script for one Shot from its asset images.

Same interface as SceneComposer.compose_shot(shot, assets) -> Path, so it can be passed to
PipelineOrchestrator as `scene_composer=`. The script imports `atoms.cdrca` (the Picture prop, written
in CDRCA itself; nothing is built into the language) and uses `add new action` and `def ACTION`.
Characters stand side by side; keywords in shot.action decide whether they walk a little or nod while
they talk (a small hop: shot art has no second mouth-open picture).

The backdrop is drawn by Blaze's art code from the shot's own words: a shot is free text written by an AI, so the place
(street, room, warehouse, forest, beach, office) and mood (day, sunset, night, dim, rain, storm, snow, night_rain,
night_snow) are chosen by looking for those words in scene_description, lighting and action (see _backdrop_for). Nothing
matched gives a street by day. If Blaze's art code is not available the shot simply has no backdrop.
"""

import logging
import math
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

# CDRCA's camera: perspective, fov 75, z=5 -> world height visible at z=0.
_VIEW_HEIGHT = 2 * 5 * math.tan(math.radians(75 / 2))
_CAMERA_SCALE = {"wide shot": 0.5, "wide": 0.5, "medium shot": 1.0, "medium": 1.0,
                 "close-up": 1.8, "close up": 1.8, "closeup": 1.8, "overhead": 0.7}
_BASE_SPRITE_HEIGHT = 4.2
_FEET_Y = -2.3
_LIB = Path(__file__).resolve().parents[2] / "integrations" / "cdrca" / "atoms.cdrca"   # copy of cdrca-lib/atoms.cdrca
_VIEW_HEIGHT_BG = 9.4      # the backdrop is drawn a little larger than the visible height (it sits further back)
_DEFAULT_ASPECT = 0.55     # width / height when the image size cannot be read
_INTRO_SECONDS = 1.5       # CDRCA's default first scene; the renderer skips it (--from)


class CdrcaComposeError(Exception):
    pass


# first match wins, so the specific places come before the general ones ("inside the warehouse" is a warehouse, not a room)
_PLACE_WORDS = [
    ("warehouse", ("warehouse", "factory", "depot", "storage")),
    ("beach", ("beach", "shore", "seaside", "ocean", "coast", "sand")),
    ("forest", ("forest", "woods", "woodland", "park", "garden", "jungle")),
    ("office", ("office", "desk", "workplace", "boardroom")),
    ("room", ("room", "house", "kitchen", "bedroom", "apartment", "home", "indoors", "inside")),
    ("street", ("street", "road", "city", "alley", "sidewalk", "town")),
]


def _has(text: str, words) -> bool:
    return any(re.search(rf"\b{w}", text) for w in words)


def _backdrop_for(shot) -> tuple:
    """(place, mood) for a shot, from the words in its description, lighting and action."""
    text = " ".join([getattr(shot, "scene_description", "") or "", getattr(shot, "lighting", "") or "",
                     getattr(shot, "action", "") or ""]).lower()
    place = next((p for p, words in _PLACE_WORDS if _has(text, words)), "street")
    night = _has(text, ("night", "midnight", "moonlit", "moon", "dark"))
    if night and _has(text, ("rain", "drizzle", "wet")):
        mood = "night_rain"
    elif night and _has(text, ("snow",)):
        mood = "night_snow"
    elif _has(text, ("storm", "thunder", "lightning")):
        mood = "storm"
    elif _has(text, ("rain", "drizzle", "downpour")):
        mood = "rain"
    elif _has(text, ("snow", "blizzard")):
        mood = "snow"
    elif _has(text, ("sunset", "sundown", "dusk", "golden")):
        mood = "sunset"
    elif night:
        mood = "night"
    elif _has(text, ("dim", "candle", "gloomy", "lamplit", "shadow")):
        mood = "dim"
    else:
        mood = "day"
    return place, mood


def _blaze_art():
    """Blaze's art module, or None when it is not available (a checkout has it next to studio/; a bundled app may include it)."""
    try:
        from blaze import art
        return art
    except ImportError:
        root = Path(__file__).resolve().parents[4]          # studio/src/core/scene_composer/ -> the repository root
        if (root / "blaze" / "art.py").is_file():
            import sys
            sys.path.insert(0, str(root))
            from blaze import art
            return art
    return None


class CdrcaSceneComposer:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.storage_path = Path(config.get("storage_path", "./storage"))
        self.scenes_dir = self.storage_path / "cdrca_scenes"
        self.scenes_dir.mkdir(parents=True, exist_ok=True)
        w = int(config.get("render_width", 1280))
        h = int(config.get("render_height", 720))
        self.aspect = w / h

    def compose_shot(self, shot, assets: Dict[str, Path]) -> Path:
        chars = list(shot.characters or [])
        for name in chars:
            if name not in assets:
                raise CdrcaComposeError(f"Shot '{shot.shot_id}' references character '{name}' but no asset image was provided")

        scale = _CAMERA_SCALE.get((shot.camera_angle or "").lower(), 1.0)
        height = min(_BASE_SPRITE_HEIGHT * scale, _VIEW_HEIGHT * 0.95)
        y = round(_FEET_Y + height / 2, 3)
        action = (shot.action or "").lower()
        walks = bool(re.search(r"\b(walk|run|pace|move|cross|enter|leave|approach|follow)", action))
        talks = bool(re.search(r"\b(talk|speak|say|shout|argue|whisper|ask|reply|laugh)", action))

        usable = _VIEW_HEIGHT * self.aspect * 0.7
        step = usable / max(len(chars), 1)
        idents = _identifiers(chars)
        stay = max(200, int(shot.duration_seconds * 1000))
        name = _sanitize(shot.shot_id)

        shutil.copyfile(_LIB, self.scenes_dir / "atoms.cdrca")
        walk_speed = round(1.2 / (stay / 1000), 3)
        lines = ['@IMPORT "./atoms.cdrca"', f"!--- SCENE {name} ---", ""]
        backdrop = self._backdrop(shot)
        if backdrop:
            bg_h = _VIEW_HEIGHT_BG * max(1.0, self.aspect / (16 / 9))
            lines.append(f'use Picture("{backdrop}", 0, 0, {round(bg_h * 16 / 9, 3)}, {round(bg_h, 3)}, -1, 0, "", 0) as backdrop')
        positions = []
        for i, c in enumerate(chars):
            x = round(-usable / 2 + step * (i + 0.5), 3)
            positions.append(x)
            w = round(height * _aspect(assets[c]), 3)
            # Picture(src, x, y, w, h, z, speed, altSrc, flapHz)
            lines.append(f'use Picture("{self._rel(assets[c], name)}", {x}, {y}, {w}, {round(height, 3)}, 0, {walk_speed}, "", 0) as {idents[i]}')
        lines += ["", f"add new action main {stay} 1", ""]
        if backdrop:
            lines.append('def ACTION main backdrop modifyMesh ""')
        for i, ident in enumerate(idents):
            if walks:
                lines.append(f"def ACTION main {ident} moveTo {round(positions[i] + 1.2, 3)}")
            elif talks:
                lines.append(f"def ACTION main {ident} hop 0.12")
            else:
                lines.append(f'def ACTION main {ident} modifyMesh ""')
        lines += ["", "!---END---", ""]

        scene_path = self.scenes_dir / f"{name}.cdrca"
        scene_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"Composed CDRCA scene for {shot.shot_id}: {scene_path}")
        return scene_path

    def _backdrop(self, shot):
        """Path (relative to the scene file) of the backdrop picture for a shot, drawing it first if needed; None without Blaze's art."""
        art = _blaze_art()
        if art is None:
            logger.info("Blaze's art code is not available: no backdrop")
            return None
        place, mood = _backdrop_for(shot)
        target = self.scenes_dir / "backdrops" / f"{place}_{mood}.png"
        if not target.exists():
            _, mood_obj = art.parse_generator(f"gen:{place}:{mood}")
            target.parent.mkdir(parents=True, exist_ok=True)
            art.make_backdrop(place, mood_obj, target)
        return self._rel(target, f"{place}_{mood}")

    def _rel(self, image: Path, name: str) -> str:
        """Image path relative to the scene file (the renderer resolves paths like a web page does)."""
        try:
            return Path(os.path.relpath(Path(image).resolve(), self.scenes_dir.resolve())).as_posix()
        except ValueError:                       # different drive on Windows: copy it next to the scene
            local = self.scenes_dir / f"{name}_{Path(image).name}"
            shutil.copyfile(image, local)
            return local.name


def _aspect(image) -> float:
    """width / height of an image: Pillow when installed, else the PNG header, else a sensible default."""
    try:
        from PIL import Image
        with Image.open(image) as im:
            return im.width / im.height
    except Exception:
        pass
    try:
        head = Path(image).read_bytes()[:24]
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            w, h = int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
            return w / h if h else _DEFAULT_ASPECT
    except OSError:
        pass
    return _DEFAULT_ASPECT


def _identifiers(names):
    used, out = set(), []
    for n in names:
        base = "c_" + (re.sub(r"\W+", "_", n.strip()) or "char")
        ident, k = base, 2
        while ident in used:
            ident, k = f"{base}_{k}", k + 1
        used.add(ident)
        out.append(ident)
    return out


def _sanitize(shot_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", str(shot_id).strip()) or "shot"
