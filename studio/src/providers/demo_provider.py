"""Offline providers: the studio works end to end with no AI account, no key and no GPU.

DemoPlanTextProvider   returns a built-in three-shot story as the Director's JSON plan (it ignores the prompt: that is what a
                       demo is, and the window says so).
BuiltinImageProvider   draws characters with Pillow, using Blaze's own art code. `key=value` looks in the description
                       (gender=f dress=1 top=0x3c78d6 ...) are honoured; otherwise the look comes from the description itself,
                       so the same description always gives the same character.

They are advanced providers (`text_provider: demo`, `image_provider: builtin`), not choices in the first-run window.
"""
import hashlib
import json
import logging
import re
import sys
import tempfile
from pathlib import Path
from typing import Optional

from .base import ImageProvider, TextProvider

logger = logging.getLogger(__name__)

DEMO_STORY = {
    "shots": [
        {"shot_id": "shot_001", "scene_description": "A rainy night on a city street, a lamp glowing. John and Mary stand together.",
         "characters": ["John", "Mary"], "camera_angle": "wide shot", "lighting": "night rain",
         "action": "John and Mary talk", "duration_seconds": 3.0},
        {"shot_id": "shot_002", "scene_description": "Inside the old warehouse, boxes stacked along the walls. John walks ahead of Mary.",
         "characters": ["John", "Mary"], "camera_angle": "medium shot", "lighting": "dim warehouse light",
         "action": "John walks into the warehouse", "duration_seconds": 3.0},
        {"shot_id": "shot_003", "scene_description": "The beach at sunset, the sea behind them. They smile.",
         "characters": ["John", "Mary"], "camera_angle": "medium shot", "lighting": "golden sunset",
         "action": "They laugh and talk", "duration_seconds": 3.0},
    ],
    "world_state_seed": {
        "John": {"appearance": "gender=m coat=1 hat=fedora glasses=1 top=0xd64036"},
        "Mary": {"appearance": "gender=f hairstyle=long top=0x3c78d6 dress=1"},
    },
}


class DemoPlanTextProvider(TextProvider):
    """Answers every planning request with the built-in story."""

    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        return json.dumps(DEMO_STORY)


def _blaze_art():
    """Blaze's art module: importable from a checkout (the repository root is the parent of studio/) or when bundled."""
    try:
        from blaze import art
        return art
    except ImportError:
        root = Path(__file__).resolve().parents[3]
        if (root / "blaze" / "art.py").is_file():
            sys.path.insert(0, str(root))
            from blaze import art
            return art
        raise


class BuiltinImageProvider(ImageProvider):
    """Draws a character from its description, offline."""

    def generate_image(self, prompt: str, output_path: Path) -> Path:
        art = _blaze_art()
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        look = " ".join(t for t in re.findall(r"[a-z]+=\S+", prompt.lower()) if t.split("=")[0] in art.LOOK_KEYS)
        seed = "c" + hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:10]
        try:
            art.appearance_for(seed, look)
        except ValueError as e:                      # a malformed look in a free-text description: fall back to a stable one
            logger.warning(f"Ignoring unusable look in description ({e})")
            look = ""
        with tempfile.TemporaryDirectory() as tmp:
            base, _ = art.make_character(seed, look, Path(tmp))
            output_path.write_bytes(Path(base).read_bytes())
        logger.debug(f"Built-in character drawn: {output_path}")
        return output_path
