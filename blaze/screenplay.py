"""
Blaze screenplay format: plain text with exact values, nothing guessed from words.

    TITLE: The Lost Key
    SUBTITLE: A short story
    CAST: JOHN gender=m coat=1 hat=fedora glasses=1 top=0xd64036
    CAST: MARY gender=f hairstyle=long top=0x3c78d6
    CAST: ROBO asset=robo                      # your own library/characters/robo.png

    SCENE: street at night                     # a label for you; it is not interpreted
    BACKDROP: gen:street:night_rain            # gen:<place>:<mood>, or a library backdrop name, or an image path
    JOHN: Did you hear that?
    MARY (nervous): It is just the wind.       # (...) after the name is a note and is ignored
    > A narrator line starts with ">".
    [ENTER TIM 9.5 4.2]     enter: start x, end x          [EXIT TIM 9.5]      walk to x and leave
    [MOVE JOHN 0]           walk to x                       [HOP MARY]  [PAUSE 1.5]

Positions are x coordinates in scene units (0 is the middle; the visible width is about 13.6 at the 16:9 default; a character
is about 2.4 wide). Characters on stage at the start are spread evenly. Blank lines and lines starting with # or // are ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

DIRECTIVES = {"TITLE", "SUBTITLE", "CAST", "SCENE", "BACKDROP", "NARRATOR"}


@dataclass
class Beat:
    kind: str                      # say | narr | enter | exit | move | hop | pause
    who: str = ""
    text: str = ""
    nums: List[float] = field(default_factory=list)


@dataclass
class Scene:
    heading: str
    beats: List[Beat] = field(default_factory=list)
    backdrop: str = ""             # gen:<place>:<mood> | library name | image path ("" = gen:street:day)


@dataclass
class Screenplay:
    title: str = ""
    subtitle: str = ""
    cast: Dict[str, str] = field(default_factory=dict)       # display name -> "key=value ..." (see art.appearance_for)
    scenes: List[Scene] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def characters(self) -> List[str]:
        seen: List[str] = []
        for sc in self.scenes:
            for b in sc.beats:
                if b.who and b.who not in seen:
                    seen.append(b.who)
        return seen


class ScreenplayError(Exception):
    pass


_NAME_LINE = re.compile(r"^([A-Za-z][A-Za-z0-9 _'.\-]{0,23}?)\s*(?:\(([^)]*)\))?\s*:\s*(.+)$")
_BRACKET = re.compile(r"\[([^\]]+)\]")
_SLUG_HEAD = re.compile(r"^(INT\.|EXT\.|INT/EXT\.|I/E\.)\s*(.+)$", re.I)
_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")


def _display(name: str) -> str:
    name = name.strip()
    return name.title() if name.isupper() else name


def parse(text: str) -> Screenplay:
    sp = Screenplay()
    canon: Dict[str, str] = {}                 # lower-case -> display name

    def who(name: str) -> str:
        key = name.strip().lower()
        if key not in canon:
            canon[key] = _display(name)
        return canon[key]

    def cur_scene() -> Scene:
        if not sp.scenes:
            sp.scenes.append(Scene(heading=""))
        return sp.scenes[-1]

    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        if line.startswith("(") and line.endswith(")"):
            continue

        m = _SLUG_HEAD.match(line)
        if m:
            sp.scenes.append(Scene(heading=m.group(2).strip()))
            continue

        if line.startswith(">"):
            cur_scene().beats.append(Beat("narr", text=line[1:].strip()))
            continue

        if line.startswith("["):
            rest = _BRACKET.sub("", line).strip()
            if rest:
                sp.warnings.append(f"line {n}: text outside [brackets] ignored: {rest[:40]!r}")
            for cmd in _BRACKET.findall(line):
                _command(cmd, cur_scene(), who, sp, n)
            continue

        m = _NAME_LINE.match(line)
        if not m:
            sp.warnings.append(f"line {n}: not understood, shown as narration: {line[:50]!r}")
            cur_scene().beats.append(Beat("narr", text=line))
            continue
        head, paren, body = m.group(1).strip(), m.group(2), m.group(3).strip()
        key = head.upper()

        if key in DIRECTIVES:
            if key == "TITLE": sp.title = body
            elif key == "SUBTITLE": sp.subtitle = body
            elif key == "CAST":
                parts = body.split(None, 1)
                if not parts:
                    raise ScreenplayError(f"line {n}: CAST needs a name")
                sp.cast[who(parts[0])] = parts[1] if len(parts) > 1 else ""
            elif key == "SCENE":
                sp.scenes.append(Scene(heading=body))
            elif key == "NARRATOR":
                cur_scene().beats.append(Beat("narr", text=body))
            elif key == "BACKDROP":
                cur_scene().backdrop = body
            continue
        if key in ("STYLE", "CAMERA", "WEATHER"):
            sp.warnings.append(f"line {n}: {key} is not supported (text always shows as a speech box; there is no camera or weather)")
            continue

        name = who(head)
        scene = cur_scene()
        cmds = _BRACKET.findall(body)
        spoken = _BRACKET.sub("", body).strip()
        if spoken:
            scene.beats.append(Beat("say", who=name, text=spoken))
        for cmd in cmds:
            _command(cmd, scene, who, sp, n)

    sp.scenes = [s for s in sp.scenes if s.beats or s.heading]
    if not any(b.kind in ("say", "narr") for s in sp.scenes for b in s.beats):
        raise ScreenplayError("The screenplay has no dialogue or narration lines.")
    return sp


def _command(cmd: str, scene: Scene, who, sp: Screenplay, n: int) -> None:
    parts = cmd.strip().split()
    if not parts:
        return
    op, args = parts[0].upper(), parts[1:]

    def numbers(count: int):
        """Split 'NAME WITH SPACES 1.5 2' into (name, [1.5, 2]); the numbers are exactly `count`, at the end."""
        tail = args[len(args) - count:] if count else []
        if len(args) < count or not all(_NUMBER.match(t) for t in tail):
            raise ScreenplayError(f"line {n}: [{cmd}] needs {count} exact number(s) at the end (positions are x values, not words)")
        return " ".join(args[:len(args) - count]), [float(t) for t in tail]

    if op == "ENTER":
        name, nums = numbers(2); scene.beats.append(Beat("enter", who=who(name), nums=nums))
    elif op == "EXIT":
        name, nums = numbers(1); scene.beats.append(Beat("exit", who=who(name), nums=nums))
    elif op == "MOVE":
        name, nums = numbers(1); scene.beats.append(Beat("move", who=who(name), nums=nums))
    elif op == "HOP":
        scene.beats.append(Beat("hop", who=who(" ".join(args))))
    elif op == "PAUSE":
        _, nums = numbers(1); scene.beats.append(Beat("pause", nums=nums))
    else:
        sp.warnings.append(f"line {n}: unknown command [{cmd}]")
