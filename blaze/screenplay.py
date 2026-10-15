"""
Blaze screenplay format: plain text with exact values, nothing guessed from words.

There are two layers, and the second is only a shorthand for the first.

CORE (every statement says everything; this is what `blaze expand` prints)

    TITLE: The Lost Key
    SUBTITLE: A short story
    CAST: JOHN gender=m coat=1 hat=fedora voice=espeak:en-us+m3 rate=140       # look keys, then voice/rate/pitch/look
    CAST: "Zoë" gender=f                                                       # a name with lower-case letters is quoted
    DEFINE LOOK shout base=bubble size=0.6 ink=0xff2020                        # a text look: exact numbers, see looks.py
    SCENE: street at night
    BACKDROP: gen:street:night_rain
    SPEAK JOHN "Did you hear that?" look=shout
    NARRATE "It was late." look=caption
    ENTER TIM 9.5 4.2          EXIT TIM 9.5          MOVE JOHN 0          HOP MARY          PAUSE 1.5

SUGAR (each line below expands to exactly one core statement)

    JOHN: Did you hear that?            ->  SPEAK JOHN "Did you hear that?"
    JOHN (look=shout): Stop!            ->  SPEAK JOHN "Stop!" look=shout       (other words in the brackets are acting notes, ignored)
    > It was late.                      ->  NARRATE "It was late."
    [ENTER TIM 9.5 4.2]                 ->  ENTER TIM 9.5 4.2                   (also at the end of a spoken line)
    INT. KITCHEN - DAY                  ->  SCENE: KITCHEN - DAY

Names are strict: a speaker is a CAST member, or written in CAPITALS. Anything else before a colon is an error, never a
new character. A command may only name someone who is in the screenplay. Unknown commands are errors with a suggestion.

Positions are x coordinates in scene units (0 is the middle; the visible width is about 13.6 at the 16:9 default; a character
is about 2.4 wide). Characters on stage at the start are spread evenly. Blank lines and lines starting with # or // are ignored.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from . import looks as looks_mod
from .looks import Look

DIRECTIVES = {"TITLE", "SUBTITLE", "CAST", "SCENE", "BACKDROP", "NARRATOR"}
UNSUPPORTED = ("STYLE", "CAMERA", "WEATHER")
VERBS = ("ENTER", "EXIT", "MOVE", "HOP", "PAUSE")
SPEECH_KEYS = ("voice", "rate", "pitch", "look")
ENGINE_NAMES = ("espeak", "pyttsx3", "piper")


@dataclass
class Beat:
    kind: str                      # say | narr | enter | exit | move | hop | pause
    who: str = ""
    text: str = ""
    nums: List[float] = field(default_factory=list)
    look: str = ""                 # a text look written on this line; "" = the default for this speaker / narration
    line: int = 0


@dataclass
class Scene:
    heading: str
    beats: List[Beat] = field(default_factory=list)
    backdrop: str = ""             # gen:<place>:<mood> | library name | image path ("" = gen:street:day)


@dataclass
class Screenplay:
    title: str = ""
    subtitle: str = ""
    cast: Dict[str, str] = field(default_factory=dict)        # display name -> "key=value ..." (looks only; see art.appearance_for)
    speech: Dict[str, dict] = field(default_factory=dict)     # display name -> {"voice": "espeak:en-us", "rate": 140, "pitch": 40, "look": "shout"}
    looks: Dict[str, Look] = field(default_factory=dict)      # text looks, the built-in five plus the ones DEFINEd
    scenes: List[Scene] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def characters(self) -> List[str]:
        seen: List[str] = []
        for sc in self.scenes:
            for b in sc.beats:
                if b.who and b.who not in seen:
                    seen.append(b.who)
        return seen

    def look_name(self, beat: Beat) -> str:
        if beat.look:
            return beat.look
        if beat.kind == "narr":
            return "caption"
        return str(self.speech.get(beat.who, {}).get("look") or "bubble")

    def look_of(self, beat: Beat) -> Look:
        return self.looks.get(self.look_name(beat)) or looks_mod.BUILTIN["bubble"]


class ScreenplayError(Exception):
    pass


_NAME_LINE = re.compile(r"^([^\W\d_][\w .'\-]{0,23}?)\s*(?:\(([^)]*)\))?\s*:\s*(.+)$")
_BRACKET = re.compile(r"\[([^\]]+)\]")
_SLUG_HEAD = re.compile(r"^(INT\.|EXT\.|INT/EXT\.|I/E\.)\s*(.+)$", re.I)
_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
_CORE = re.compile(r"^(DEFINE\s+LOOK|SPEAK|NARRATE|ENTER|EXIT|MOVE|HOP|PAUSE)\b\s*(.*)$")
_SPEAK = re.compile(r'^(.+?)\s+"((?:[^"\\]|\\.)*)"\s*(.*)$')
_NARRATE = re.compile(r'^"((?:[^"\\]|\\.)*)"\s*(.*)$')
_CAST_LINE = re.compile(r"^\s*CAST\s*:\s*(.*)$", re.I)


def _display(name: str) -> str:
    name = name.strip()
    return name.title() if name.isupper() else name


def _unescape(s: str) -> str:
    return re.sub(r"\\(.)", r"\1", s)


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _num_text(v: float) -> str:
    return ("%.6f" % v).rstrip("0").rstrip(".") or "0"


def _cast_split(body: str) -> Tuple[str, str]:
    """'JOHN gender=m' -> ('JOHN', 'gender=m');  '"Dr Smith" gender=m' -> ('Dr Smith', 'gender=m')."""
    body = body.strip()
    if body.startswith('"'):
        end = body.find('"', 1)
        if end < 0:
            return "", ""
        return body[1:end].strip(), body[end + 1:].strip()
    parts = body.split(None, 1)
    return (parts[0], parts[1] if len(parts) > 1 else "") if parts else ("", "")


def _cast_names(text: str) -> Set[str]:
    out: Set[str] = set()
    for raw in text.splitlines():
        m = _CAST_LINE.match(raw)
        if m:
            name, _ = _cast_split(m.group(1))
            if name:
                out.add(name.lower())
    return out


def _speaker_ok(head: str, cast_lower: Set[str]) -> bool:
    h = head.strip()
    return h.lower() in cast_lower or h.isupper()


def _suggest(word: str, options, cutoff: float = 0.6) -> str:
    hit = difflib.get_close_matches(word.lower(), [o.lower() for o in options], n=1, cutoff=cutoff)
    return hit[0] if hit else ""


def parse(text: str) -> Screenplay:
    cast_lower = _cast_names(text)
    _, introduced = _parse(text, cast_lower, None)                 # pass 1: who is introduced anywhere (casting, speaking, ENTER)
    known = cast_lower | {n.lower() for n in introduced}
    sp, _ = _parse(text, cast_lower, known)                        # pass 2: strict, a command may only name a known character
    return sp


def _parse(text: str, cast_lower: Set[str], known: Optional[Set[str]]) -> Tuple[Screenplay, Set[str]]:
    sp = Screenplay(looks=dict(looks_mod.BUILTIN))
    canon: Dict[str, str] = {}                 # lower-case -> display name
    introduced: Set[str] = set()
    first_line: Dict[str, int] = {}
    pending_looks: List[Tuple[int, str, Dict[str, str]]] = []
    known_words = {w for k in (known or set()) for w in k.split()}

    def who(name: str) -> str:
        key = name.strip().lower()
        if key not in canon:
            canon[key] = _display(name)
        return canon[key]

    def ref(name: str, n: int) -> str:
        """A character a command points at. It must already be in the screenplay: a typo must not invent a new one."""
        key = name.strip().lower()
        if known is not None and key not in known:
            hint = _suggest(key, known)
            raise ScreenplayError(
                f"line {n}: '{name.strip()}' is not a character in this screenplay"
                + (f" (did you mean {_display(hint.upper()) if hint.upper().isupper() else hint}?)" if hint else "")
                + ". Add it with CAST:, or let it speak or ENTER first.")
        return who(name)

    def cur_scene() -> Scene:
        if not sp.scenes:
            sp.scenes.append(Scene(heading=""))
        return sp.scenes[-1]

    def pairs_of(s: str, n: int, what: str) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for tok in s.split():
            if "=" not in tok:
                raise ScreenplayError(f"line {n}: {what}: expected key=value, got {tok!r}")
            k, v = tok.split("=", 1)
            out[k.strip().lower()] = v.strip()
        return out

    def is_command(group: str, n: int) -> bool:
        toks = group.split()
        if not toks:
            return False
        if toks[0].upper() in VERBS:
            return True
        if known is None or not toks[0].isupper() or len(toks) < 2:
            return False
        later = toks[1:]
        if any(_NUMBER.match(t) or t.lower() in known_words for t in later):
            hint = _suggest(toks[0], VERBS)
            raise ScreenplayError(f"line {n}: unknown command [{group}]. The commands are {', '.join(VERBS)}"
                                  + (f" (did you mean {hint.upper()}?)" if hint else ""))
        return False

    def say(name: str, body: str, look: str, n: int) -> None:
        if not _speaker_ok(name, cast_lower):
            raise ScreenplayError(
                f"line {n}: '{name.strip()}' is not a declared character, so this line is not dialogue. "
                f"Declare it with CAST: {name.strip()}, write the speaker in CAPITALS, or start a narration line with '>'")
        who_ = who(name)
        introduced.add(name.strip())
        first_line.setdefault(who_, n)
        cmds: List[str] = []

        def pull(m):
            if is_command(m.group(1), n):
                cmds.append(m.group(1))
                return ""
            return m.group(0)
        spoken = re.sub(r"\s{2,}", " ", _BRACKET.sub(pull, body)).strip()
        scene = cur_scene()
        if spoken:
            scene.beats.append(Beat("say", who=who_, text=spoken, look=look, line=n))
        for cmd in cmds:
            _command(cmd, n)

    def _command(cmd: str, n: int) -> None:
        scene = cur_scene()
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

        if op == "ENTER":                                      # entering is how a character can first appear
            name, nums = numbers(2)
            if not name:
                raise ScreenplayError(f"line {n}: [{cmd}] needs a name")
            introduced.add(name)
            scene.beats.append(Beat("enter", who=who(name), nums=nums, line=n))
        elif op == "EXIT":
            name, nums = numbers(1); scene.beats.append(Beat("exit", who=ref(name, n), nums=nums, line=n))
        elif op == "MOVE":
            name, nums = numbers(1); scene.beats.append(Beat("move", who=ref(name, n), nums=nums, line=n))
        elif op == "HOP":
            if not args:
                raise ScreenplayError(f"line {n}: [{cmd}] needs a name")
            scene.beats.append(Beat("hop", who=ref(" ".join(args), n), line=n))
        elif op == "PAUSE":
            _, nums = numbers(1); scene.beats.append(Beat("pause", nums=nums, line=n))
        else:
            hint = _suggest(op, VERBS)
            raise ScreenplayError(f"line {n}: unknown command [{cmd}]. The commands are {', '.join(VERBS)}"
                                  + (f" (did you mean {hint.upper()}?)" if hint else ""))

    def narrate(body: str, look: str, n: int) -> None:
        cur_scene().beats.append(Beat("narr", text=body, look=look, line=n))

    def cast_line(body: str, n: int) -> None:
        name, rest = _cast_split(body)
        if not name:
            raise ScreenplayError(f"line {n}: CAST needs a name")
        speech: dict = {}
        look_tokens: List[str] = []
        for tok in rest.split():
            k, _, v = tok.partition("=")
            k = k.lower()
            if "=" not in tok or k not in SPEECH_KEYS:
                look_tokens.append(tok)
                continue
            if k == "voice":
                m = re.fullmatch(r"(auto|off|([a-z0-9_]+):\S+)", v, re.I)
                if not m or (m.group(2) and m.group(2).lower() not in ENGINE_NAMES):
                    raise ScreenplayError(f"line {n}: CAST {name}: voice must be auto, off, or <engine>:<voice> with the engine one of "
                                          f"{', '.join(ENGINE_NAMES)} (run `blaze voices` to see what is installed), not {v!r}")
                speech["voice"] = v if v.lower() in ("auto", "off") else v.split(":", 1)[0].lower() + ":" + v.split(":", 1)[1]
            elif k in ("rate", "pitch"):
                lo, hi = (40, 400) if k == "rate" else (0, 99)
                if not re.fullmatch(r"\d+", v) or not lo <= int(v) <= hi:
                    raise ScreenplayError(f"line {n}: CAST {name}: {k} must be a whole number from {lo} to {hi}"
                                          + (" (words per minute)" if k == "rate" else "") + f", not {v!r}")
                speech[k] = int(v)
            else:
                speech["look"] = v.lower()
        disp = who(name)
        sp.cast[disp] = " ".join(look_tokens)
        if speech:
            sp.speech[disp] = speech
        else:
            sp.speech.pop(disp, None)

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
            narrate(line[1:].strip(), "", n)
            continue

        if line.startswith("["):
            rest = _BRACKET.sub("", line).strip()
            if rest:
                sp.warnings.append(f"line {n}: text outside [brackets] ignored: {rest[:40]!r}")
            for g in _BRACKET.findall(line):
                if is_command(g, n):
                    _command(g, n)
                else:
                    hint = _suggest(g.split()[0], VERBS) if g.split() else ""
                    raise ScreenplayError(f"line {n}: unknown command [{g}]. The commands are {', '.join(VERBS)}"
                                          + (f" (did you mean {hint.upper()}?)" if hint else "")
                                          + ". For narration start the line with '>'")
            continue

        m = _NAME_LINE.match(line)
        core = None if m else _CORE.match(line)
        if core:
            verb, rest = re.sub(r"\s+", " ", core.group(1)), core.group(2).strip()
            if verb == "DEFINE LOOK":
                parts = rest.split(None, 1)
                if not parts or not looks_mod.NAME_RE.match(parts[0].lower()):
                    raise ScreenplayError(f"line {n}: DEFINE LOOK needs a name made of letters, digits and _ (starting with a letter)")
                pending_looks.append((n, parts[0].lower(), pairs_of(parts[1] if len(parts) > 1 else "", n, f"look {parts[0]}")))
            elif verb == "SPEAK":
                sm = _SPEAK.match(rest)
                if not sm:
                    raise ScreenplayError(f'line {n}: SPEAK needs a name and the text in quotes, as in SPEAK JOHN "Hello" look=bubble')
                extra = pairs_of(sm.group(3), n, "SPEAK")
                if set(extra) - {"look"}:
                    raise ScreenplayError(f"line {n}: SPEAK only takes look=<name>, not {sorted(set(extra) - {'look'})[0]!r}")
                _say_core(say, cur_scene, sm.group(1), _unescape(sm.group(2)), extra.get("look", "").lower(), n, cast_lower, who, introduced, first_line)
            elif verb == "NARRATE":
                nm = _NARRATE.match(rest)
                if not nm:
                    raise ScreenplayError(f'line {n}: NARRATE needs the text in quotes, as in NARRATE "It was late." look=caption')
                extra = pairs_of(nm.group(2), n, "NARRATE")
                if set(extra) - {"look"}:
                    raise ScreenplayError(f"line {n}: NARRATE only takes look=<name>, not {sorted(set(extra) - {'look'})[0]!r}")
                narrate(_unescape(nm.group(1)), extra.get("look", "").lower(), n)
            else:
                _command(f"{verb} {rest}", n)
            continue

        if not m:
            sp.warnings.append(f"line {n}: not understood, shown as narration: {line[:50]!r}")
            narrate(line, "", n)
            continue
        head, paren, body = m.group(1).strip(), m.group(2), m.group(3).strip()
        key = head.upper()

        if key in DIRECTIVES and head.lower() not in cast_lower:
            if key == "TITLE": sp.title = body
            elif key == "SUBTITLE": sp.subtitle = body
            elif key == "CAST": cast_line(body, n)
            elif key == "SCENE": sp.scenes.append(Scene(heading=body))
            elif key == "NARRATOR": narrate(body, "", n)
            elif key == "BACKDROP": cur_scene().backdrop = body
            continue
        if key in UNSUPPORTED:
            sp.warnings.append(f"line {n}: {key} is not supported (there is no camera or weather; the look of text is set with DEFINE LOOK)")
            continue

        look = ""
        if paren:
            for tok in paren.replace(",", " ").split():
                if tok.lower().startswith("look="):
                    look = tok[5:].lower()
        say(head, body, look, n)

    # ---- text looks: resolved in order, a look may build on an earlier one (base=) or on the built-in it redefines
    for n, name, pairs in pending_looks:
        base_name = pairs.pop("base", "").lower()
        if base_name:
            if base_name not in sp.looks:
                raise ScreenplayError(f"line {n}: look {name}: base={base_name} is not defined (looks: {', '.join(sorted(sp.looks))})")
            base = sp.looks[base_name]
        else:
            base = sp.looks.get(name) or looks_mod.BUILTIN["bubble"]
        try:
            sp.looks[name] = looks_mod.derive(base, pairs)
        except ValueError as e:
            raise ScreenplayError(f"line {n}: look {name}: {e}")
    if known is not None:
        for sc in sp.scenes:
            for b in sc.beats:
                if b.look and b.look not in sp.looks:
                    raise ScreenplayError(f"line {b.line}: look '{b.look}' is not defined (looks: {', '.join(sorted(sp.looks))}). "
                                          f"Define it with DEFINE LOOK {b.look} ...")
        for name, sd in sp.speech.items():
            if sd.get("look") and sd["look"] not in sp.looks:
                raise ScreenplayError(f"CAST {name}: look '{sd['look']}' is not defined (looks: {', '.join(sorted(sp.looks))})")

    sp.scenes = [s for s in sp.scenes if s.beats or s.heading]
    if not any(b.kind in ("say", "narr") for s in sp.scenes for b in s.beats):
        raise ScreenplayError("The screenplay has no dialogue or narration lines.")

    if known is not None:
        _typo_warnings(sp, cast_lower, first_line)
    return sp, introduced


def _say_core(say, cur_scene, name, text, look, n, cast_lower, who, introduced, first_line):
    """SPEAK: the text is already exact (quotes unescaped), so it is not searched for [commands]."""
    if not _speaker_ok(name, cast_lower):
        raise ScreenplayError(
            f"line {n}: '{name.strip()}' is not a declared character. Declare it with CAST: {name.strip()}, "
            f"write the speaker in CAPITALS, or use NARRATE for text nobody speaks")
    who_ = who(name)
    introduced.add(name.strip())
    first_line.setdefault(who_, n)
    if text.strip():
        cur_scene().beats.append(Beat("say", who=who_, text=text.strip(), look=look, line=n))


def _typo_warnings(sp: Screenplay, cast_lower: Set[str], first_line: Dict[str, int]) -> None:
    """Names that were not declared are made up on the spot, so look for ones that are suspiciously close to something else."""
    chars = sp.characters()
    said = {b.who for sc in sp.scenes for b in sc.beats if b.kind == "say"}
    for sc in sp.scenes:
        for b in sc.beats:
            if b.kind == "enter" and b.who not in said and b.who.lower() not in cast_lower:
                sp.warnings.append(f"line {b.line}: {b.who} enters but never speaks and is not in CAST (a typo?)")
    for j, b in enumerate(chars):
        if b.lower() in cast_lower or len(b) < 3:
            continue
        for a in chars[:j]:
            if difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() >= 0.8:
                sp.warnings.append(f"line {first_line.get(b, 0)}: {b} looks like {a}: two different characters? "
                                   f"(add CAST: {b} to say it is on purpose)")
                break
        for d in sorted(DIRECTIVES | set(UNSUPPORTED)):
            if len(b) >= 4 and difflib.SequenceMatcher(None, b.lower(), d.lower()).ratio() >= 0.75:
                sp.warnings.append(f"line {first_line.get(b, 0)}: {b} was taken as a new speaker; did you mean {d}: ?")
                break


# ----------------------------------------------------------------------------------------------- the explicit core
def _core_name(name: str) -> str:
    """The name as the core form writes it: all capitals when that is what it was, otherwise as written."""
    return name.upper() if _display(name.upper()) == name else name


def cast_label(name: str) -> str:
    """How a character is written after `CAST:` so that it parses back to the same character."""
    label = _core_name(name)
    return f'"{label}"' if (" " in label or not label.isupper()) else label


def to_core(sp: Screenplay) -> str:
    """The screenplay written out in the explicit core: every sugar line becomes the one statement it stands for.
    Parsing the result gives the same screenplay (`blaze expand` prints this)."""
    out: List[str] = []
    if sp.title: out.append(f"TITLE: {sp.title}")
    if sp.subtitle: out.append(f"SUBTITLE: {sp.subtitle}")
    names = list(dict.fromkeys(list(sp.cast) + sp.characters()))
    for c in names:
        label = cast_label(c)
        bits = [sp.cast.get(c, "")]
        sd = sp.speech.get(c, {})
        for k in SPEECH_KEYS:
            if k in sd:
                bits.append(f"{k}={sd[k]}")
        out.append(("CAST: " + label + " " + " ".join(b for b in bits if b)).rstrip())
    for name, look in sp.looks.items():
        base = looks_mod.BUILTIN.get(name) or looks_mod.BUILTIN["bubble"]
        pairs = looks_mod.to_pairs(look, only_changed_from=base)
        if pairs or name not in looks_mod.BUILTIN:
            out.append(("DEFINE LOOK " + name + " " + " ".join(f"{k}={v}" for k, v in pairs.items())).rstrip())
    for sc in sp.scenes:
        out.append("")
        out.append(f"SCENE: {sc.heading or '(no label)'}")
        if sc.backdrop:
            out.append(f"BACKDROP: {sc.backdrop}")
        for b in sc.beats:
            lk = f" look={b.look}" if b.look else ""
            nm = _core_name(b.who) if b.who else ""
            if b.kind == "say":
                out.append(f'SPEAK {nm} "{_escape(b.text)}"{lk}')
            elif b.kind == "narr":
                out.append(f'NARRATE "{_escape(b.text)}"{lk}')
            elif b.kind == "enter":
                out.append(f"ENTER {nm} {_num_text(b.nums[0])} {_num_text(b.nums[1])}")
            elif b.kind in ("exit", "move"):
                out.append(f"{b.kind.upper()} {nm} {_num_text(b.nums[0])}")
            elif b.kind == "hop":
                out.append(f"HOP {nm}")
            elif b.kind == "pause":
                out.append(f"PAUSE {_num_text(b.nums[0])}")
    return "\n".join(out).strip() + "\n"
