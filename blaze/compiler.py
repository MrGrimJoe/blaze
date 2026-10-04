"""
Screenplay scene -> a plain CDRCA script.

The output is ordinary CDRCA using only constructs the language already has: `use <prop>(...) as <alias>`,
`add new action <name> <stay> <lerp>` and `def ACTION <name> <prop> <method> <args>`. Props are the
standard ones (ImageProp, TextProp). Every beat of the screenplay becomes one CDRCA action, so the
script reads as a list of what happens, in order; open it, edit it, and re-render it with `blaze build`.

What CDRCA does not have yet (camera moves, weather, mood tinting, word-by-word subtitles, blinking) is
not faked here: those screenplay commands are reported as notes and skipped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .art import Appearance, Mood, make_title_background, mood_from, slug
from .screenplay import Beat, Scene, Screenplay
from .voice import estimate_seconds

P = "ObjectAnimationSystem_INS.CORE_3d_PROPSsceneSYS.exampleProps."
INTRO_S, OUTRO_S = 1.5, 1.0     # CDRCA's default first scene (500ms lerp + 1000ms stay) and end scene (1000ms stay)
STEP_LERP_MS = 1                # a cut, not CDRCA's default 500ms scene fade
WALK_SPEED = 2.4                # = ImageProp.walkSpeed
OFFSCREEN = 9.5
BASE_HEIGHT = 4.4
FEET_Y = -2.3
SLOT = {"left": -4.5, "center": 0.0, "centre": 0.0, "right": 4.5}
GAP = {"say": 0.4, "narr": 0.3}


@dataclass
class Shot:
    index: int
    name: str
    cdrca: Path
    duration: float                 # seconds of video to keep (after skipping the default intro)
    skip: float = INTRO_S           # seconds to skip at the start of the render (CDRCA's default intro scene)
    audio: List[Tuple[float, Path]] = field(default_factory=list)
    srt: List[Tuple[float, float, str, str]] = field(default_factory=list)   # (start, end, who, text)
    mood: str = "day"
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


def clear_spot(x: float, others, gap: float = 2.3, limit: float = 5.8) -> float:
    """Nudge a destination so a character never stands on top of another (sprites are ~2.2 units wide)."""
    others = list(others)
    if all(abs(x - o) >= gap for o in others):
        return x
    cands = [max(-limit, min(limit, o + k * gap)) for o in others for k in (-1, 1)]
    cands = [c for c in cands if all(abs(c - o) >= gap - 0.01 for o in others)]
    return min(cands, key=lambda c: abs(c - x)) if cands else x


def _n(x: float) -> str:
    s = ("%.3f" % x).rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def _q(text: str) -> str:
    """A CDRCA string literal body: no double quotes, backslashes or line breaks."""
    return re.sub(r"\s+", " ", text.replace("\\", "/").replace('"', "'")).strip()


def _heading(text: str) -> str:
    return re.sub(r"-{3,}", "-", _q(text)) or "untitled"


def _ident(prefix: str, name: str, used: set) -> str:
    base = prefix + (re.sub(r"\W+", "_", name).strip("_") or "x")
    ident, k = base, 2
    while ident in used:
        ident, k = f"{base}_{k}", k + 1
    used.add(ident)
    return ident


class _Script:
    """Collects props and actions, then writes the .cdrca text."""

    def __init__(self):
        self.props: List[Tuple[str, str]] = []                 # (alias, 'ImageProp(...)')
        self.steps: List[Tuple[float, Dict[str, Tuple[str, str]]]] = []

    def prop(self, alias: str, ctor: str) -> None:
        self.props.append((alias, ctor))

    def step(self, seconds: float, cmds: Dict[str, Tuple[str, str]]) -> None:
        self.steps.append((max(0.05, seconds), cmds))

    @property
    def seconds(self) -> float:
        return sum(s + STEP_LERP_MS / 1000.0 for s, _ in self.steps)


def compile_title(index: int, sp: Screenplay, scenes_dir: Path, first_mood: Mood, seconds: float = 3.2) -> Shot:
    assets = scenes_dir.parent / "assets"
    top = tuple(max(0, int(c * 0.55)) for c in first_mood.sky_top)
    bottom = tuple(max(0, int(c * 0.25)) for c in first_mood.sky_bot)
    bg = make_title_background(top, bottom, assets / "bg_title.png")
    sc = _Script()
    sc.prop("backdrop", f'ImageProp("../assets/{bg.name}", 0, 0, 9.5, -1)')
    sc.prop("title", 'TextProp(0, -0.3, 0.8, "plain")')
    sc.prop("subtitle", 'TextProp(0, -1.5, 0.38, "plain")')
    cmds = {"title": ("say", f'"{_q(sp.title)}"')}
    if sp.subtitle:
        cmds["subtitle"] = ("say", f'"{_q(sp.subtitle)}"')
    sc.step(seconds, cmds)
    path = scenes_dir / "s00_title.cdrca"
    path.write_text(_render(sc, sp.title), encoding="utf-8")
    return Shot(index, "title", path, sc.seconds, title=True)


def _render(sc: _Script, heading: str) -> str:
    out = [f"!--- SCENE {_heading(heading)} ---", ""]
    out += [f"use {P}{ctor} as {alias}" for alias, ctor in sc.props]
    out.append("")
    for i, (secs, _) in enumerate(sc.steps, 1):
        out.append(f"add new action a{i:03d} {int(round(secs * 1000))} {STEP_LERP_MS}")
    out.append("")
    for i, (_, cmds) in enumerate(sc.steps, 1):
        for alias, _ctor in sc.props:
            method, arg = cmds.get(alias, ("modifyMesh", '""'))
            out.append(f"def ACTION a{i:03d} {alias} {method} {arg}")
        out.append("")
    out += ["!---END---", ""]
    return "\n".join(out)


def compile_scene(index: int, scene: Scene, sp: Screenplay, apps: Dict[str, Appearance], work: Path,
                  line_info: Dict[int, Tuple[Optional[Path], float]], backdrop: Path,
                  wpm: int = 150, aspect: float = 16 / 9) -> Shot:
    """line_info[j] = (wav or None, seconds) for beat j (say/narr beats)."""
    heading = scene.heading
    mood = mood_from(heading)
    name = f"s{index:02d}"
    scenes_dir = work / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    notes: List[str] = []

    present_first: Dict[str, str] = {}
    for b in scene.beats:
        if b.who and b.who not in present_first:
            present_first[b.who] = b.kind
    order: List[str] = [c for c, k in present_first.items() if k != "enter"]
    pos = layout(order)
    x0 = dict(pos)

    used: set = {"backdrop", "caption"}
    ident = {c: _ident("c_", c, used) for c in present_first}
    bubbles: Dict[Tuple[str, float], str] = {}
    sc = _Script()
    audio: List[Tuple[float, Path]] = []
    srt: List[Tuple[float, float, str, str]] = []
    show_bubbles = sp.style in ("bubbles", "both")
    show_caption = sp.style in ("subtitles", "both")

    def bubble_for(who: str) -> str:
        key = (who, round(pos.get(who, 0.0), 2))
        if key not in bubbles:
            bubbles[key] = _ident("say_", f"{who}_{len(bubbles) + 1}", used)
        return bubbles[key]

    def walk(moves: Dict[str, float]) -> float:
        """Commands for several characters walking at once; returns how long the step must last."""
        longest, cmds = 0.0, {}
        for c, dest in moves.items():
            longest = max(longest, abs(dest - pos[c]) / WALK_SPEED)
            cmds[ident[c]] = ("moveTo", _n(dest))
        return longest, cmds

    def now() -> float:
        return sc.seconds

    for j, b in enumerate(scene.beats):
        if b.kind in ("say", "narr"):
            wav, dur = line_info.get(j, (None, estimate_seconds(b.text, wpm)))
            who = b.who if b.kind == "say" else ""
            cmds: Dict[str, Tuple[str, str]] = {}
            if who:
                cmds[ident[who]] = ("talk", '""')
                if show_bubbles:
                    cmds[bubble_for(who)] = ("say", f'"{_q(b.text)}"')
            if not who or show_caption:
                label = f"{who.upper()}: {b.text}" if who else b.text
                cmds["caption"] = ("say", f'"{_q(label)}"')
            t0 = now()
            if wav is not None:
                audio.append((t0, wav))
            srt.append((t0, t0 + dur, who, b.text))
            sc.step(dur, cmds)
            sc.step(GAP[b.kind], {})
        elif b.kind == "pause":
            sc.step(float(b.arg or 1), {})
        elif b.kind == "hop":
            if b.who in pos:
                sc.step(0.5, {ident[b.who]: ("hop", "0.5")})
        elif b.kind == "enter":
            if b.who in order:
                continue
            side = b.arg or ("left" if len(order) % 2 == 0 else "right")
            order.insert(0, b.who) if side == "left" else order.append(b.who)
            target = layout(order)
            x0.setdefault(b.who, -OFFSCREEN if side == "left" else OFFSCREEN)
            pos[b.who] = x0[b.who]
            moves = {c: x for c, x in target.items() if abs(pos[c] - x) > 0.05}
            longest, cmds = walk(moves)
            sc.step(longest + 0.25, cmds)
            pos.update(target)
        elif b.kind == "exit":
            if b.who not in order:
                continue
            side = b.arg or ("left" if pos.get(b.who, 0) < 0 else "right")
            dest = -OFFSCREEN if side == "left" else OFFSCREEN
            longest, cmds = walk({b.who: dest})
            sc.step(longest + 0.2, cmds)
            order.remove(b.who); pos.pop(b.who)
            rest = layout(order)
            moves = {c: x for c, x in rest.items() if abs(pos[c] - x) > 0.05}
            if moves:
                longest, cmds = walk(moves)
                sc.step(longest + 0.15, cmds)
                pos.update(rest)
        elif b.kind == "move":
            if b.who not in pos:
                continue
            dest = SLOT.get(b.arg)
            if dest is None:
                try: dest = float(b.arg)
                except ValueError: continue
            dest = clear_spot(dest, [x for c, x in pos.items() if c != b.who])
            longest, cmds = walk({b.who: dest})
            sc.step(longest + 0.2, cmds)
            pos[b.who] = dest
        elif b.kind == "camera":
            notes.append(f"[CAMERA {b.arg}] skipped: CDRCA has no camera control yet")
        elif b.kind == "weather":
            notes.append(f"[WEATHER {b.arg}] skipped: CDRCA has no weather yet")

    if not sc.steps:
        sc.step(1.0, {})
    # the scene's weather/mood is only in the backdrop picture; say so once if it was asked for
    if mood.weather:
        notes.append(f"'{mood.weather}' is only suggested by the backdrop colours (no animated weather in CDRCA yet)")

    bg_h = 9.4 * max(1.0, aspect / (16 / 9))
    sc.prop("backdrop", f'ImageProp("../assets/{backdrop.name}", 0, 0, {_n(bg_h)}, -1)')
    for c in present_first:
        a = apps[c]
        h = BASE_HEIGHT * a.height_scale
        talk = f', "../assets/{slug(c)}_talk.png"' if (work / "assets" / f"{slug(c)}_talk.png").exists() else ""
        sc.prop(ident[c], f'ImageProp("../assets/{slug(c)}.png", {_n(x0.get(c, OFFSCREEN))}, {_n(FEET_Y + h / 2)}, {_n(h)}, 0{talk})')
    for (who, x), alias in bubbles.items():
        h = BASE_HEIGHT * apps[who].height_scale
        sc.prop(alias, f'TextProp({_n(max(-4.0, min(4.0, x)))}, {_n(FEET_Y + h + 0.2)}, 0.32, "bubble")')
    sc.prop("caption", 'TextProp(0, -3.5, 0.3, "caption")')

    path = scenes_dir / f"{name}.cdrca"
    path.write_text(_render(sc, heading), encoding="utf-8")
    return Shot(index, name, path, sc.seconds, INTRO_S, audio, srt, mood.name, notes=notes)
