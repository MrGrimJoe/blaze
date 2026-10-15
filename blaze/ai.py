"""
Prompt -> screenplay, using the text provider YOU chose (Anthropic, Gemini or OpenAI; there is no default:
see studio/config.yaml or the Blaze page). The model only writes text in Blaze's strict screenplay
format; everything after that is deterministic. Two ways in:

  write_screenplay   one request: idea -> a short screenplay (cheap; fine for a quick scene).
  write_animation    a whole animation, one request per step so every step is small and checked:
                       1. outline: title, the CAST (exact looks), and one planned scene per beat
                          (place, mood and what happens);
                       2. each scene is written on its own with that cast and the earlier scenes in view;
                          the cast block and every backdrop come from the outline, never from the model's
                          later whims, which is what keeps characters and places consistent;
                       3. the parser checks every step; its complaint goes back to the model (up to 2 tries).
                     A scene that still fails stops the run with a message naming it; nothing unchecked is shipped.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Callable, List, Optional

from . import art
from .screenplay import ScreenplayError, _display, parse

STUDIO = Path(__file__).resolve().parent.parent / "studio"

SYSTEM = """You write short screenplays in a strict plain-text format that a program turns into an animated video.
Output ONLY the screenplay text, no commentary, no markdown fences.

FORMAT (every position and appearance value is exact; never use words like left or right)
TITLE: <title>
SUBTITLE: <optional one-line tagline>
CAST: NAME gender=m|f [child=1] [hairstyle=short|long|bun|bald|curly|spiky] [hair=0xRRGGBB] [top=0xRRGGBB] [bottom=0xRRGGBB]
      [coat=1] [dress=1] [hat=fedora|cap|beanie] [glasses=1] [beard=1] [scarf=1] [skin=0..5]     (one line per character, max 4)

SCENE: <a short label for humans>
BACKDROP: gen:<place>:<mood>        place = street|room|warehouse|forest|beach|office
                                    mood = day|sunset|night|dim|rain|storm|snow|night_rain|night_snow
NAME: spoken line                   (NAME in CAPITALS, spelled the same way every time; one speaker per line; speech only, max 14 words per line)
> narrator caption line             (optional)
[ENTER NAME x0 x1]  walks in from x0 (use 9.5 or -9.5, off screen) to x1 (between -5 and 5)
[EXIT NAME x]       walks to x (9.5 or -9.5) and leaves
[MOVE NAME x]       walks to x (between -5 and 5);   [HOP NAME]   [PAUSE seconds]

RULES
- 2 to {scenes} scenes, about {lines} spoken lines in total, a clear beginning, middle and end.
- Characters speaking before any [ENTER] are on stage at the start. Use stage commands sparingly.
- A command may only name a character who speaks or enters; never invent a name inside a command. Every colon line is a speaker, so no other line may contain a colon.
- Dialogue must be natural and speakable aloud. No stage directions inside the spoken text.
{level}"""


def _clean(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n|\n```$", "", text)
    return text.strip()


def write_screenplay(idea: str, *, scenes: int = 3, lines: int = 14, level: Optional[str] = None,
                     provider=None, config_path: Optional[Path] = None) -> str:
    if provider is None:
        provider = _load_provider(config_path)
    level_txt = f"- Language level {level}: use short sentences and common everyday vocabulary suited to that level.\n" if level else ""
    system = SYSTEM.format(scenes=scenes, lines=lines, level=level_txt)
    prompt = f"Write the screenplay for this idea:\n{idea}"
    text = _clean(provider.generate(prompt, system_instruction=system))
    try:
        _validate(text)
        return text
    except ScreenplayError as e:
        retry = f"{prompt}\n\nYour previous answer could not be used: {e}\nReturn ONLY a valid screenplay in the format described."
        text = _clean(provider.generate(retry, system_instruction=system))
        _validate(text)  # let a second failure surface to the caller
        return text


def _validate(text: str) -> None:
    """The parser is forgiving (stray prose becomes narration); model output must have real dialogue."""
    sp = parse(text)
    says = sum(1 for sc in sp.scenes for b in sc.beats if b.kind == "say")
    if says < 2:
        raise ScreenplayError("it contains fewer than 2 dialogue lines of the form 'NAME: spoken text'")


def _load_provider(config_path: Optional[Path]):
    import yaml
    cfg_path = Path(config_path) if config_path else Path(os.environ.get("BLAZE_CONFIG") or STUDIO / "config.yaml")
    if not cfg_path.exists():
        raise RuntimeError(f"No config found at {cfg_path}. Run `python blaze.py ui` and choose a provider, or pass --config.")
    config = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    sys.path.insert(0, str(STUDIO))
    try:
        from src.providers.provider_factory import ProviderConfigError, get_text_provider
    finally:
        sys.path.pop(0)
    try:
        return get_text_provider(config)
    except ProviderConfigError as e:
        raise RuntimeError(f"{e} (Blaze: run `python blaze.py ui` and pick Anthropic, Gemini or OpenAI under Write with AI.)") from e


# --------------------------------------------------------------------------- whole animations
class AnimationError(RuntimeError):
    pass


OUTLINE_SYSTEM = """You plan short animated stories. A program turns your plan into scripts, so follow the format exactly.
Output ONLY the plan, no commentary, no markdown.

TITLE: <title>
SUBTITLE: <optional one-line tagline>
CAST: NAME gender=m|f [child=1] [hairstyle=short|long|bun|bald|curly|spiky] [hair=0xRRGGBB] [top=0xRRGGBB] [bottom=0xRRGGBB]
      [coat=1] [dress=1] [hat=fedora|cap|beanie] [glasses=1] [beard=1] [scarf=1] [skin=0..5]     (one line per character, 2 to 4)
SCENE 1: <place> | <mood> | <one sentence: what happens, who is in it>
SCENE 2: ...

place is one of: {places}
mood is one of: {moods}
Exactly {scenes} scenes with a clear beginning, middle and end. Give each character a distinct look (different colours)."""

SCENE_SYSTEM = """You write ONE scene of a short animated story in a strict plain-text format that a program turns into video.
Output ONLY the scene, no commentary, no markdown. Do not write TITLE or CAST lines: the cast is fixed.

SCENE: <a short label>
BACKDROP: gen:<place>:<mood>        (use exactly the backdrop given below)
NAME: spoken line                   (speech only, max 14 words; one speaker per line)
> narrator caption line             (optional)
[ENTER NAME x0 x1]  walks in from x0 (9.5 or -9.5, off screen) to x1 (between -5 and 5)
[EXIT NAME x]       walks to x (9.5 or -9.5) and leaves
[MOVE NAME x]       walks to x (between -5 and 5);   [HOP NAME]   [PAUSE seconds]

RULES
- Only these characters may speak or move: {names}. Characters who speak before any [ENTER] are already on stage.
- About {lines} spoken lines. Natural, speakable dialogue; no stage directions inside the spoken text.
- Continue the story from the earlier scenes; do not repeat them.
{level}"""


def _chat(provider, prompt: str, system: str, check: Callable[[str], object], what: str, tries: int = 3):
    """Ask, validate, and on failure feed the complaint back. Returns check(text)'s result."""
    last = None
    for attempt in range(tries):
        ask = prompt if last is None else f"{prompt}\n\nYour previous answer could not be used: {last}\nReturn ONLY the corrected {what}."
        text = _clean(provider.generate(ask, system_instruction=system))
        try:
            return check(text)
        except (ScreenplayError, ValueError) as e:
            last = str(e)
    raise AnimationError(f"The {what} could not be written after {tries} tries. Last problem: {last}")


def _parse_outline(text: str, scenes: int):
    title = subtitle = ""
    cast: List[str] = []
    plan = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        up = line.upper()
        if up.startswith("TITLE:"):
            title = line[6:].strip()
        elif up.startswith("SUBTITLE:"):
            subtitle = line[9:].strip()
        elif up.startswith("CAST:"):
            body = line[5:].strip()
            name, _, spec = body.partition(" ")
            art.appearance_for(_display(name), spec.strip())            # raises ValueError for unknown looks
            cast.append(line)
        else:
            m = re.match(r"(?i)scene\s*\d+\s*:\s*(.+)$", line)
            if m:
                parts = [p.strip() for p in m.group(1).split("|")]
                if len(parts) != 3:
                    raise ValueError(f"'{line}' must look like: SCENE n: <place> | <mood> | <what happens>")
                art.parse_generator(f"gen:{parts[0]}:{parts[1]}")             # raises ValueError for unknown place/mood
                plan.append((parts[0], parts[1], parts[2]))
    if not title:
        raise ValueError("there is no TITLE: line")
    if not 2 <= len(cast) <= 4:
        raise ValueError(f"the cast must have 2 to 4 CAST: lines, there are {len(cast)}")
    if len(plan) != scenes:
        raise ValueError(f"there must be exactly {scenes} scenes, there are {len(plan)}")
    return title, subtitle, cast, plan


def _names(cast_lines: List[str]) -> List[str]:
    return [_display(l[5:].strip().split()[0]) for l in cast_lines]


def _scene_checker(header: str, cast_names: List[str], backdrop: str, scene_no: int):
    def check(text: str) -> str:
        lines = [l for l in text.splitlines() if not re.match(r"(?i)\s*(title|subtitle|cast)\s*:", l)]
        body = [l for l in lines if not re.match(r"(?i)\s*backdrop\s*:", l)]
        while body and not body[0].strip():
            body.pop(0)
        if not body or not re.match(r"(?i)\s*scene\s*:", body[0]):
            raise ScreenplayError("it must start with a 'SCENE: <label>' line")
        scene = "\n".join([body[0].strip(), f"BACKDROP: {backdrop}"] + body[1:]).strip()
        sp = parse(f"{header}\n\n{scene}\n")
        says = [b for sc in sp.scenes for b in sc.beats if b.kind == "say"]
        if len(says) < 2:
            raise ScreenplayError("it needs at least 2 dialogue lines of the form 'NAME: spoken text'")
        stray = sorted({n for n in sp.characters() if n not in cast_names})
        if stray:
            raise ScreenplayError(f"{', '.join(stray)} {'is' if len(stray) == 1 else 'are'} not in the cast ({', '.join(cast_names)}); only cast members may appear")
        return scene
    return check


def write_animation(idea: str, *, scenes: int = 4, lines_per_scene: int = 5, level: Optional[str] = None, provider=None,
                    config_path: Optional[Path] = None, progress: Optional[Callable[[str], None]] = None) -> str:
    """A whole animation as a validated screenplay. Needs scenes + 1 requests when nothing has to be retried."""
    if not 2 <= scenes <= 8:
        raise AnimationError("scenes must be between 2 and 8")
    say = progress or (lambda m: None)
    if provider is None:
        provider = _load_provider(config_path)
    moods = ", ".join(list(art.MOODS) + list(art.NIGHT_WET))
    say("Planning the story")
    title, subtitle, cast_lines, plan = _chat(
        provider, f"Plan an animated story for this idea:\n{idea}",
        OUTLINE_SYSTEM.format(places=", ".join(art.PLACES), moods=moods, scenes=scenes),
        lambda t: _parse_outline(t, scenes), "plan")
    names = _names(cast_lines)
    header = "\n".join([f"TITLE: {title}"] + ([f"SUBTITLE: {subtitle}"] if subtitle else []) + cast_lines)
    level_txt = f"- Language level {level}: use short sentences and common everyday vocabulary suited to that level.\n" if level else ""
    done: List[str] = []
    for i, (place, mood, what) in enumerate(plan, 1):
        say(f"Writing scene {i} of {scenes}")
        backdrop = f"gen:{place}:{mood}"
        story_so_far = "\n\n".join(done) if done else "(this is the first scene)"
        prompt = (f"Story: {title}\nWhole plan:\n" + "\n".join(f"{n}. {p} | {m} | {w}" for n, (p, m, w) in enumerate(plan, 1))
                  + f"\n\nEarlier scenes:\n{story_so_far}\n\nWrite scene {i} now: {what}\nBackdrop: {backdrop}")
        scene = _chat(provider, prompt, SCENE_SYSTEM.format(names=", ".join(names), lines=lines_per_scene, level=level_txt),
                      _scene_checker(header, names, backdrop, i), f"scene {i}")
        done.append(scene)
    text = header + "\n\n" + "\n\n".join(done) + "\n"
    parse(text)                                                    # the whole thing must still parse
    return text
