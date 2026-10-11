"""
Screenplay scene -> a CDRCA script that uses only exact numbers.

A generated scene imports cdrca-lib/atoms.cdrca (props written in CDRCA itself: Picture and Words), creates the props
with explicit positions / sizes / colours / speeds, and lists what happens as `add new action` + `def ACTION` lines, one
action per beat. Nothing is built into CDRCA for this and nothing is guessed: every value in the output is a number or
a literal you can edit.

Text is a Words prop per speaker; each speech action first sets that prop's reveal rate (characters per second, taken from
the length of the voice line) and then says the text. Open the .cdrca, change a number, `blaze build`.
"""

from __future__ import annotations

import math
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image

from .art import Appearance, make_title_background, slug
from .screenplay import Scene, Screenplay
from .voice import estimate_seconds

LIB_SOURCE = Path(__file__).resolve().parent.parent / "cdrca-lib" / "atoms.cdrca"
INTRO_S = 1.5            # CDRCA's default first scene (500 ms lerp + 1000 ms stay); the renderer skips it with --from
STEP_LERP_MS = 1         # an action's lerp time; 1 ms = a cut (0 would divide by zero in the renderer)
WALK_SPEED = 2.4         # units per second (Picture's `speed`)
FLAP_HZ = 4              # mouth swaps per second while talking
FEET_Y = -2.3
BASE_HEIGHT = 4.4
VIEW_HALF_H = 5 * math.tan(math.radians(75 / 2))   # half of the visible height at depth 0 (fov 75, camera at z=5)
EDGE_MARGIN = 0.15       # speech boxes stay this far inside the screen edge
VIEW_H = 9.4             # height that exactly fills the camera view at depth -1 (fov 75, camera at z=5)
GAP_S = {"say": 0.4, "narr": 0.3}
OFFSCREEN = 9.5

# speech box (Words) parameters, all explicit
BUBBLE = dict(size=0.32, wrap=6.4, fill="0xffffff", alpha=1, ink="0x1b1f2a", border="0x1b1f2a", border_w=0.04, pad=0.22, tail=0.3)
CAPTION = dict(size=0.3, wrap=11, fill="0x0a0c12", alpha=0.8, ink="0xffffff", border="0x0a0c12", border_w=0, pad=0.2, tail=0)
TITLE = dict(size=0.8, wrap=12, fill="0x000000", alpha=0, ink="0xffffff", border="0x000000", border_w=0, pad=0.1, tail=0)
SUBTITLE = dict(size=0.38, wrap=12, fill="0x000000", alpha=0, ink="0xffffff", border="0x000000", border_w=0, pad=0.1, tail=0)


@dataclass
class Shot:
    index: int
    name: str
    cdrca: Path
    duration: float                 # seconds of video to keep (after skipping the default intro)
    skip: float = INTRO_S
    audio: List[Tuple[float, Path]] = field(default_factory=list)
    srt: List[Tuple[float, float, str, str]] = field(default_factory=list)   # (start, end, who, text)
    mood: str = ""
    title: bool = False
    notes: List[str] = field(default_factory=list)


def layout(order: List[str]) -> Dict[str, float]:
    n = len(order)
    if n == 0: return {}
    if n == 1: xs = [0.0]
    elif n == 2: xs = [-2.4, 2.4]
    elif n == 3: xs = [-4.2, 0.0, 4.2]
    elif n == 4: xs = [-5.0, -1.7, 1.7, 5.0]
    else: xs = [-5.4 + 10.8 * i / (n - 1) for i in range(n)]
    return dict(zip(order, xs))


def _n(x: float) -> str:
    s = ("%.3f" % x).rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def _q(text: str) -> str:
    """A CDRCA string literal body: no double quotes, backslashes or line breaks."""
    return re.sub(r"\s+", " ", text.replace("\\", "/").replace('"', "'")).strip()


def _label(text: str) -> str:
    return re.sub(r"-{3,}", "-", _q(text)) or "untitled"


def _ident(prefix: str, name: str, used: set) -> str:
    base = prefix + (re.sub(r"\W+", "_", name).strip("_") or "x")
    ident, k = base, 2
    while ident in used:
        ident, k = f"{base}_{k}", k + 1
    used.add(ident)
    return ident


def _words(x, y, ax, ay, p, z=0.01, limit=0.0, limit_y=0.0) -> str:
    return (f'Words({_n(x)}, {_n(y)}, {_n(ax)}, {_n(ay)}, {_n(p["size"])}, {_n(p["wrap"])}, {p["fill"]}, {_n(p["alpha"])}, '
            f'{p["ink"]}, {p["border"]}, {_n(p["border_w"])}, {_n(p["pad"])}, {_n(p["tail"])}, {_n(z)}, {_n(limit)}, {_n(limit_y)})')


def _picture(src, x, y, w, h, z, speed, alt="", hz=0) -> str:
    return f'Picture("{src}", {_n(x)}, {_n(y)}, {_n(w)}, {_n(h)}, {_n(z)}, {_n(speed)}, "{alt}", {_n(hz)})'


class _Script:
    """Props and actions, written out as CDRCA text."""

    def __init__(self):
        self.props: List[Tuple[str, str]] = []                          # (alias, constructor call)
        self.steps: List[Tuple[float, Dict[str, List[Tuple[str, str]]]]] = []   # (seconds, {alias: [(method, arg), ...]})

    def prop(self, alias: str, ctor: str) -> None:
        self.props.append((alias, ctor))

    def step(self, seconds: float, cmds: Dict[str, List[Tuple[str, str]]]) -> None:
        self.steps.append((max(0.05, seconds), cmds))

    @property
    def seconds(self) -> float:
        return sum(s + STEP_LERP_MS / 1000.0 for s, _ in self.steps)

    def text(self, heading: str) -> str:
        out = ['@IMPORT "./atoms.cdrca"', "", f"!--- SCENE {_label(heading)} ---", ""]
        out += [f"use {ctor} as {alias}" for alias, ctor in self.props]
        out.append("")
        for i, (secs, _) in enumerate(self.steps, 1):
            out.append(f"add new action a{i:03d} {int(round(secs * 1000))} {STEP_LERP_MS}")
        out.append("")
        for i, (_, cmds) in enumerate(self.steps, 1):
            for alias, _ctor in self.props:
                for method, arg in cmds.get(alias, [("modifyMesh", '""')]):
                    out.append(f"def ACTION a{i:03d} {alias} {method} {arg}")
            out.append("")
        out += ["!---END---", ""]
        return "\n".join(out)


def install_library(scenes_dir: Path) -> None:
    """The library is copied next to the scenes so a project is self-contained."""
    scenes_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(LIB_SOURCE, scenes_dir / "atoms.cdrca")


def _image_aspect(path: Path) -> float:
    with Image.open(path) as im:
        return im.width / im.height


def compile_title(index: int, sp: Screenplay, scenes_dir: Path, top_rgb, bottom_rgb, seconds: float = 3.2) -> Shot:
    install_library(scenes_dir)
    assets = scenes_dir.parent / "assets"
    bg = make_title_background(top_rgb, bottom_rgb, assets / "bg_title.png")
    sc = _Script()
    sc.prop("backdrop", _picture(f"../assets/{bg.name}", 0, 0, VIEW_H * 16 / 9, VIEW_H, -1, 0))
    sc.prop("title", _words(0, -0.3, 0.5, 0.5, TITLE))
    sc.prop("subtitle", _words(0, -1.5, 0.5, 0.5, SUBTITLE))
    cmds = {"title": [("rate", "0"), ("say", f'"{_q(sp.title)}"')]}
    if sp.subtitle:
        cmds["subtitle"] = [("rate", "0"), ("say", f'"{_q(sp.subtitle)}"')]
    sc.step(seconds, cmds)
    path = scenes_dir / "s00_title.cdrca"
    path.write_text(sc.text(sp.title), encoding="utf-8")
    return Shot(index, "title", path, sc.seconds, title=True)


def clear_spot(x: float, others, gap: float = 2.3, limit: float = 5.8) -> float:
    """Nudge a destination so a character never stands on top of another (sprites are ~2.2 units wide)."""
    others = list(others)
    if all(abs(x - o) >= gap for o in others):
        return x
    cands = [max(-limit, min(limit, o + k * gap)) for o in others for k in (-1, 1)]
    cands = [c for c in cands if all(abs(c - o) >= gap - 0.01 for o in others)]
    return min(cands, key=lambda c: abs(c - x)) if cands else x


def compile_scene(index: int, scene: Scene, sp: Screenplay, apps: Dict[str, Appearance], work: Path,
                  line_info: Dict[int, Tuple[Optional[Path], float]], backdrop: Path,
                  wpm: int = 150, aspect: float = 16 / 9) -> Shot:
    """line_info[j] = (wav or None, seconds) for beat j (say/narr beats)."""
    name = f"s{index:02d}"
    scenes_dir = work / "scenes"
    install_library(scenes_dir)
    assets = work / "assets"

    present_first: Dict[str, str] = {}
    for b in scene.beats:
        if b.who and b.who not in present_first:
            present_first[b.who] = b.kind
    order: List[str] = [c for c, k in present_first.items() if k != "enter"]
    pos = layout(order)
    x0 = dict(pos)
    for b in scene.beats:                                          # an entering character starts where the screenplay says
        if b.kind == "enter":
            x0.setdefault(b.who, b.nums[0])

    used: set = {"backdrop", "caption"}
    ident = {c: _ident("c_", c, used) for c in present_first}
    boxes: Dict[Tuple[str, float], str] = {}
    sc = _Script()
    audio: List[Tuple[float, Path]] = []
    srt: List[Tuple[float, float, str, str]] = []

    def box_for(who: str) -> str:
        key = (who, round(pos.get(who, 0.0), 2))
        if key not in boxes:
            boxes[key] = _ident("say_", f"{who}_{len(boxes) + 1}", used)
        return boxes[key]

    def walk(moves: Dict[str, float]):
        longest, cmds = 0.0, {}
        for c, dest in moves.items():
            longest = max(longest, abs(dest - pos[c]) / WALK_SPEED)
            cmds[ident[c]] = [("moveTo", _n(dest))]
        return longest, cmds

    for j, b in enumerate(scene.beats):
        if b.kind in ("say", "narr"):
            wav, dur = line_info.get(j, (None, estimate_seconds(b.text, wpm)))
            who = b.who if b.kind == "say" else ""
            cps = max(1.0, len(b.text) / max(0.3, dur * 0.9))            # reveal the whole text a little before the voice ends
            cmds: Dict[str, List[Tuple[str, str]]] = {}
            if who:
                cmds[ident[who]] = [("flap", '""')]
                cmds[box_for(who)] = [("rate", _n(cps)), ("say", f'"{_q(b.text)}"')]
            else:
                cmds["caption"] = [("rate", _n(cps)), ("say", f'"{_q(b.text)}"')]
            t0 = sc.seconds
            if wav is not None:
                audio.append((t0, wav))
            srt.append((t0, t0 + dur, who, b.text))
            sc.step(dur, cmds)
            sc.step(GAP_S[b.kind], {})
        elif b.kind == "pause":
            sc.step(b.nums[0], {})
        elif b.kind == "hop":
            if b.who in pos:
                sc.step(0.5, {ident[b.who]: [("hop", "0.5")]})
        elif b.kind == "enter":
            if b.who in order:
                continue
            order.append(b.who)
            pos[b.who] = b.nums[0]
            dest = clear_spot(b.nums[1], [x for c, x in pos.items() if c != b.who])
            longest, cmds = walk({b.who: dest})
            sc.step(longest + 0.25, cmds)
            pos[b.who] = dest
        elif b.kind == "exit":
            if b.who not in order:
                continue
            longest, cmds = walk({b.who: b.nums[0]})
            sc.step(longest + 0.2, cmds)
            order.remove(b.who); pos.pop(b.who)
        elif b.kind == "move":
            if b.who not in pos:
                continue
            dest = clear_spot(b.nums[0], [x for c, x in pos.items() if c != b.who])
            longest, cmds = walk({b.who: dest})
            sc.step(longest + 0.2, cmds)
            pos[b.who] = dest

    if not sc.steps:
        sc.step(1.0, {})

    view_half_w = VIEW_HALF_H * aspect          # half of the visible width at depth 0 (where characters and bubbles are)
    bg_h = VIEW_H * max(1.0, aspect / (16 / 9))
    bg_w = bg_h * (_image_aspect(backdrop) if backdrop.exists() else 16 / 9)
    sc.prop("backdrop", _picture(f"../assets/{backdrop.name}", 0, 0, bg_w, bg_h, -1, 0))
    for c in present_first:
        a = apps[c]
        h = BASE_HEIGHT * a.height_scale
        base = assets / f"{slug(c)}.png"
        w = h * (_image_aspect(base) if base.exists() else 400 / 720)
        talk = f"../assets/{slug(c)}_talk.png" if (assets / f"{slug(c)}_talk.png").exists() else ""
        sc.prop(ident[c], _picture(f"../assets/{slug(c)}.png", x0.get(c, OFFSCREEN), FEET_Y + h / 2, w, h, 0, WALK_SPEED, talk, FLAP_HZ if talk else 0))
    for (who, x), alias in boxes.items():
        h = BASE_HEIGHT * apps[who].height_scale
        sc.prop(alias, _words(max(-4.0, min(4.0, x)), FEET_Y + h + 0.2, 0.5, 0, BUBBLE, limit=round(view_half_w - EDGE_MARGIN, 3), limit_y=round(VIEW_HALF_H - EDGE_MARGIN, 3)))
    sc.prop("caption", _words(0, -3.5, 0.5, 0, CAPTION))

    path = scenes_dir / f"{name}.cdrca"
    path.write_text(sc.text(scene.heading), encoding="utf-8")
    return Shot(index, name, path, sc.seconds, INTRO_S, audio, srt, mood=scene.backdrop or "gen:street:day")
