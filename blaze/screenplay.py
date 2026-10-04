"""
Blaze screenplay format — plain text a human (or any LLM) can write.

    TITLE: The Lost Key
    SUBTITLE: A short story
    STYLE: bubbles            # bubbles | subtitles (karaoke-highlighted) | both
    CAST: JOHN = man, detective, red coat, glasses
    CAST: MARY = woman, blue dress, long hair
    CAST: ROBO = asset:robo        # use library/characters/robo.png instead of generated art

    SCENE: rainy street at night
    BACKDROP: my_lab               # optional: your own background (library/backdrops/my_lab.png or a path)
    JOHN: I heard something inside the warehouse.
    MARY (nervous): Stay close to me.
    [CAMERA push]                 (accepted, but skipped until CDRCA has camera control)
    [ENTER TIM right]
    TIM: Wait for me!
    [MOVE JOHN left]  [HOP MARY]  [PAUSE 1]  [EXIT TIM right]
    > Narrator lines start with a ">" and show as a caption.

    INT. WAREHOUSE - NIGHT        (screenplay-style scene headings work too)

Blank lines and lines starting with # or // are ignored. Parentheses on their own line, like
(John looks around), are treated as stage directions and ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

DIRECTIVES = {"TITLE", "SUBTITLE", "STYLE", "CAST", "SCENE", "BACKDROP", "NARRATOR", "WEATHER", "FPS", "VOICE"}


@dataclass
class Beat:
    kind: str                      # say | narr | enter | exit | move | hop | pause | camera | weather
    who: str = ""
    text: str = ""
    arg: str = ""                  # side / slot / seconds / camera mode / weather kind


@dataclass
class Scene:
    heading: str
    beats: List[Beat] = field(default_factory=list)
    backdrop: str = ""             # name of a library backdrop, or an image path (BACKDROP:)


@dataclass
class Screenplay:
    title: str = ""
    subtitle: str = ""
    style: str = "bubbles"
    cast: Dict[str, str] = field(default_factory=dict)       # display name -> description
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

        # a line made only of [commands]
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
            elif key == "STYLE":
                v = body.lower().split()[0]
                if v not in ("bubbles", "subtitles", "both"):
                    sp.warnings.append(f"line {n}: unknown STYLE {v!r} (use bubbles, subtitles or both)")
                else:
                    sp.style = v
            elif key == "CAST":
                cm = re.match(r"^([^=:]+?)\s*[=:]\s*(.*)$", body)
                if cm: sp.cast[who(cm.group(1))] = cm.group(2).strip()
                else: sp.cast[who(body)] = ""
            elif key == "SCENE":
                sp.scenes.append(Scene(heading=body))
            elif key == "NARRATOR":
                cur_scene().beats.append(Beat("narr", text=body))
            elif key == "WEATHER":
                cur_scene().beats.append(Beat("weather", arg=body.lower()))
            elif key == "BACKDROP":
                cur_scene().backdrop = body
            continue

        name = who(head)
        if paren and name not in sp.cast and re.search(r"[a-z]", paren, re.I):
            # "MARY (woman, red coat): ..." — treat as a cast description if it describes looks,
            # otherwise it is just an acting note like (nervous) and is ignored.
            if re.search(r"\b(man|woman|boy|girl|child|hair|coat|dress|hat|glasses|shirt|beard|jacket|hoodie)\b", paren, re.I):
                sp.cast[name] = paren.strip()
        scene = cur_scene()
        beats = scene.beats
        # inline commands after the dialogue: JOHN: Hello. [HOP JOHN]
        cmds = _BRACKET.findall(body)
        spoken = _BRACKET.sub("", body).strip()
        if spoken:
            beats.append(Beat("say", who=name, text=spoken))
        for cmd in cmds:
            _command(cmd, scene, who, sp, n)

    sp.scenes = [s for s in sp.scenes if s.beats or s.heading]
    if not any(b.kind in ("say", "narr") for s in sp.scenes for b in s.beats):
        raise ScreenplayError("The screenplay has no dialogue or narration lines.")
    for s in sp.scenes:
        s.beats = [b for b in s.beats if b.kind != "weather" or b.arg]
    return sp


def _command(cmd: str, scene: Scene, who, sp: Screenplay, n: int) -> None:
    parts = cmd.strip().split()
    if not parts:
        return
    op, args = parts[0].upper(), parts[1:]
    try:
        if op in ("ENTER", "EXIT"):
            side = args[-1].lower() if len(args) > 1 and args[-1].lower() in ("left", "right") else ""
            name = " ".join(args[:-1] if side else args)
            scene.beats.append(Beat(op.lower(), who=who(name), arg=side))
        elif op == "MOVE":
            name, dest = " ".join(args[:-1]), args[-1].lower()
            scene.beats.append(Beat("move", who=who(name), arg=dest))
        elif op == "HOP":
            scene.beats.append(Beat("hop", who=who(" ".join(args))))
        elif op == "PAUSE":
            scene.beats.append(Beat("pause", arg=str(float(args[0]) if args else 1.0)))
        elif op == "CAMERA":
            scene.beats.append(Beat("camera", arg=args[0].lower()))
        elif op == "WEATHER":
            scene.beats.append(Beat("weather", arg=args[0].lower()))
        else:
            sp.warnings.append(f"line {n}: unknown command [{cmd}]")
    except (IndexError, ValueError):
        sp.warnings.append(f"line {n}: could not read command [{cmd}]")
