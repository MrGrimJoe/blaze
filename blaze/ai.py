"""
Prompt -> screenplay, using a text provider from BlazEng's config.yaml (Gemini, OpenAI,
Anthropic, Ollama... whatever BlazEng already supports). The model only has to write a screenplay,
which LLMs are good at; everything after that is deterministic. If the result does not parse, the
parser's complaint is fed back once.

BlazEng (github.com/MrGrimJoe/BlazEng) is a separate repo from this one -- `blaze ai` imports its
provider code at runtime, so it needs an actual BlazEng checkout. There's no default path to guess
here (the two repos aren't nested or co-located by convention), so --config is required: point it
at a BlazEng checkout's config.yaml, with an API key filled in.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional

from .screenplay import ScreenplayError, parse

SYSTEM = """You write short screenplays in a strict plain-text format that a program turns into an animated video.
Output ONLY the screenplay text, no commentary, no markdown fences.

FORMAT
TITLE: <title>
SUBTITLE: <optional one-line tagline>
CAST: NAME = <looks: man/woman/boy/girl, clothing with colours, hair, glasses, hat>   (one line per character, max 4 characters)

SCENE: <place and time/mood, e.g. "rainy street at night" or "cozy room, sunset">
NAME: spoken line                      (one speaker per line; speech only, max 14 words per line)
> narrator caption line                (optional)
[ENTER NAME left|right]  [EXIT NAME left|right]  [MOVE NAME left|center|right]  [HOP NAME]  [PAUSE 1]

RULES
- Places that have artwork: street, room, warehouse, forest/park, beach, office/school/cafe. Moods: day, sunset, night, dim, rain, storm, snow.
- 2 to {scenes} scenes, about {lines} spoken lines in total, a clear beginning, middle and end.
- Use stage commands sparingly (a few per scene) and only for characters that exist.
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
    if config_path is None:
        raise RuntimeError(
            "blaze ai needs --config pointing at a BlazEng config.yaml with an API "
            "key filled in. BlazEng is a separate repo: "
            "github.com/MrGrimJoe/BlazEng -- clone it, copy its config.yaml.example "
            "to config.yaml, add a key, then pass --config /path/to/BlazEng/config.yaml."
        )
    cfg_path = Path(config_path)
    if not cfg_path.exists():
        raise RuntimeError(f"No config found at {cfg_path}.")
    config = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    # config.yaml lives at the BlazEng checkout's root, so its parent directory
    # is where src/providers/provider_factory.py can actually be imported from.
    blazeng_root = cfg_path.resolve().parent
    sys.path.insert(0, str(blazeng_root))
    try:
        from src.providers.provider_factory import get_text_provider
    finally:
        sys.path.pop(0)
    return get_text_provider(config)
