"""
Text looks: how a piece of on-screen text is drawn.

A look is a named bundle of exact numbers, defined by the screenplay author (DEFINE LOOK) or taken from the five that ship
with Blaze. Nothing here is interpreted from words: every key is a number, a colour 0xRRGGBB or 0/1.

    size   height of one line of text (scene units)        wrap   widest a line may be
    fill   box colour 0xRRGGBB                             alpha  box opacity 0..1
    ink    text colour                                     border outline colour      border_w  outline width
    pad    space between text and box edge                 tail   length of the pointer under the box (0 = none)
    x, y   FIXED position of the anchor; leave both out (or write none) to anchor the text above whoever speaks it
    ax, ay where the anchor sits inside the box, 0..1 from the left / bottom (default 0.5 and 0)
    clamp  1 = slide back inside the screen edges; 0 = never move the box
    show   1 = draw the text; 0 = say it (voice, subtitles, mouth) without drawing anything

The five built-in looks are `bubble` (a speech box above the speaker), `caption` (a bar near the bottom), `title`,
`subtitle` and `none` (nothing drawn). A screenplay may redefine any of them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Dict, Optional

KEYS = ("size", "wrap", "fill", "alpha", "ink", "border", "border_w", "pad", "tail", "x", "y", "ax", "ay", "clamp", "show")
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class Look:
    size: float = 0.32
    wrap: float = 6.4
    fill: int = 0xFFFFFF
    alpha: float = 1.0
    ink: int = 0x1B1F2A
    border: int = 0x1B1F2A
    border_w: float = 0.04
    pad: float = 0.22
    tail: float = 0.3
    x: Optional[float] = None
    y: Optional[float] = None
    ax: float = 0.5
    ay: float = 0.0
    clamp: bool = True
    show: bool = True

    @property
    def fixed(self) -> bool:
        return self.x is not None and self.y is not None


BUILTIN: Dict[str, Look] = {
    "bubble": Look(),
    "caption": Look(size=0.3, wrap=11, fill=0x0A0C12, alpha=0.8, ink=0xFFFFFF, border=0x0A0C12, border_w=0, pad=0.2, tail=0,
                    x=0.0, y=-3.5, clamp=False),
    "title": Look(size=0.8, wrap=12, fill=0x000000, alpha=0, ink=0xFFFFFF, border=0x000000, border_w=0, pad=0.1, tail=0,
                  x=0.0, y=-0.3, ay=0.5, clamp=False),
    "subtitle": Look(size=0.38, wrap=12, fill=0x000000, alpha=0, ink=0xFFFFFF, border=0x000000, border_w=0, pad=0.1, tail=0,
                     x=0.0, y=-1.5, ay=0.5, clamp=False),
    "none": Look(show=False),
}


def _number(key: str, v: str) -> float:
    try:
        return float(v)
    except ValueError:
        raise ValueError(f"{key} must be a number such as 0.32, not {v!r}") from None


def _colour(key: str, v: str) -> int:
    try:
        n = int(v, 0)
    except ValueError:
        raise ValueError(f"{key} must be a colour written 0xRRGGBB, not {v!r}") from None
    if not 0 <= n <= 0xFFFFFF:
        raise ValueError(f"{key} must be a colour between 0x000000 and 0xffffff, not {v!r}")
    return n


def _flag(key: str, v: str) -> bool:
    if v not in ("0", "1"):
        raise ValueError(f"{key} must be 0 or 1, not {v!r}")
    return v == "1"


def derive(base: Look, pairs: Dict[str, str]) -> Look:
    """A copy of `base` with the given key=value pairs applied. Unknown keys and bad values are errors."""
    unknown = sorted(set(pairs) - set(KEYS))
    if unknown:
        raise ValueError(f"unknown look key {unknown[0]!r}; valid keys: {', '.join(KEYS)}")
    changes: dict = {}
    for k, v in pairs.items():
        if k in ("x", "y") and v.lower() == "none":
            changes[k] = None
        elif k in ("fill", "ink", "border"):
            changes[k] = _colour(k, v)
        elif k in ("clamp", "show"):
            changes[k] = _flag(k, v)
        else:
            changes[k] = _number(k, v)
    out = replace(base, **changes)
    if out.size <= 0 or out.wrap <= 0:
        raise ValueError("size and wrap must be greater than 0")
    if not 0 <= out.alpha <= 1:
        raise ValueError("alpha must be between 0 and 1")
    for k in ("ax", "ay"):
        if not 0 <= getattr(out, k) <= 1:
            raise ValueError(f"{k} must be between 0 and 1")
    if (out.x is None) != (out.y is None):
        raise ValueError("x and y go together: give both for a fixed position, or neither to anchor above the speaker")
    if min(out.border_w, out.pad, out.tail) < 0:
        raise ValueError("border_w, pad and tail cannot be negative")
    return out


def to_pairs(look: Look, only_changed_from: Optional[Look] = None) -> Dict[str, str]:
    """The look as key=value text (used when a screenplay is written back out in its explicit form)."""
    ref = only_changed_from
    out: Dict[str, str] = {}
    for k in KEYS:
        v = getattr(look, k)
        if ref is not None and getattr(ref, k) == v:
            continue
        if v is None:
            out[k] = "none"
        elif k in ("fill", "ink", "border"):
            out[k] = "0x%06x" % v
        elif k in ("clamp", "show"):
            out[k] = "1" if v else "0"
        else:
            out[k] = ("%g" % v)
    return out
