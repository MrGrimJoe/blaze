"""
Text-to-speech for Blaze: several engines, and a voice chosen per character.

  espeak    espeak-ng (Linux/macOS/Windows; https://github.com/espeak-ng/espeak-ng)          voice=espeak:en-us+m3
  pyttsx3   Windows SAPI voices / macOS NSSpeech (`pip install pyttsx3`)                      voice=pyttsx3:Zira
  piper     Piper neural voices, offline (the `piper` program on PATH + a model you download)  voice=piper:en_US-ryan-medium
  silent    no audio; line lengths are estimated from the word count                         voice=off

A character's voice is written in the screenplay, `CAST: JOHN voice=espeak:en-gb+m2 rate=140 pitch=40`, so the text file stays
the one source of truth. With `voice=auto` (or nothing) the character gets a stable voice picked from the first engine that
exists, from a hash of their name plus gender and child. `blaze voices` lists what is installed, and the page can play a sample.

Piper models are `*.onnx` files (with their `.onnx.json`) found in $BLAZE_VOICES, ./library/voices or ~/.blaze/voices.
All clips are normalised to 22.05 kHz mono 16-bit with ffmpeg so they can be stitched together.
"""

from __future__ import annotations

import difflib
import hashlib
import os
import re
import shutil
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SAMPLE_RATE = 22050
ENGINE_NAMES = ("espeak", "pyttsx3", "piper")
ESPEAK_VARIANTS = ["m1", "m2", "m3", "m4", "m5", "m6", "m7", "f1", "f2", "f3", "f4", "f5", "whisper", "whisperf", "croak"]


@dataclass
class Profile:
    gender: str = "m"       # m | f
    child: bool = False
    seed: int = 0
    voice: str = "auto"     # auto | off | <engine>:<voice>
    rate: int = 0           # words per minute for this character; 0 = the speed chosen for the whole video
    pitch: int = -1         # 0..99 where the engine supports it; -1 = chosen automatically


def profile_for(name: str, gender: str = "n", child: bool = False, voice: str = "auto", rate: int = 0, pitch: int = -1) -> Profile:
    seed = int(hashlib.sha1(name.lower().encode("utf-8")).hexdigest(), 16)
    if gender not in ("m", "f"):
        gender = "f" if seed % 2 else "m"
    return Profile(gender, child, seed, voice or "auto", int(rate or 0), int(pitch))


def wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def _normalise(src: Path, dst: Path, tempo: float = 1.0) -> None:
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src)]
    if abs(tempo - 1.0) > 0.02:
        cmd += ["-filter:a", "atempo=%.3f" % max(0.5, min(2.0, tempo))]
    cmd += ["-ar", str(SAMPLE_RATE), "-ac", "1", "-sample_fmt", "s16", str(dst)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg could not normalise audio: " + r.stderr[-300:])


def _speakable(text: str) -> bool:
    """False for text with nothing to say aloud ('...', '!?'): engines return an empty file for it, which is not an error."""
    return bool(re.search(r"\w", text))


def _require_audio(raw: Path, engine: str, detail: str = "") -> None:
    """An engine that exits happily but wrote a file with no audio in it (a missing voice, a broken install) must fail loudly,
    not give a silent video. Seen for real: Windows pyttsx3 wrote 78-byte WAV headers with zero frames."""
    if not raw.exists() or wav_seconds(raw) <= 0:
        raise RuntimeError(f"{engine} produced no audio (the file is missing or has zero frames)" + (f"; {detail}" if detail else ""))


def _exe(name: str) -> str:
    """The full path of a program on PATH (so a .bat or .cmd shim also runs on Windows), or the bare name if it is not found."""
    return shutil.which(name) or name


def _voice_part(profile: Profile, engine_id: str) -> str:
    """The <voice> in `engine:<voice>` when this profile asks for this engine, else ''."""
    head, _, rest = (profile.voice or "auto").partition(":")
    return rest if head.lower() == engine_id and rest else ""


def _near(word: str, options: List[str], n: int = 4) -> str:
    return ", ".join(difflib.get_close_matches(word.lower(), [o.lower() for o in options], n=n, cutoff=0.4))


# ------------------------------------------------------------------------------------------------ engines
class SilentVoice:
    name = "silent"
    engine_id = "silent"

    def synth(self, text: str, profile: Profile, out_wav: Path) -> Optional[float]:
        return None


class EspeakVoice:
    name = "espeak-ng"
    engine_id = "espeak"
    hint = "Install espeak-ng (https://github.com/espeak-ng/espeak-ng) and make sure it is on PATH."

    def __init__(self, wpm: int = 150, binary: str = "espeak-ng"):
        self.wpm, self.binary = wpm, _exe(binary)

    @classmethod
    def available(cls) -> bool:
        return bool(shutil.which("espeak-ng"))

    @classmethod
    def list_voices(cls) -> List[dict]:
        if not cls.available():
            return []
        r = subprocess.run([_exe("espeak-ng"), "--voices"], capture_output=True, text=True)
        out: List[dict] = []
        for line in r.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 4:
                out.append({"id": f"espeak:{parts[1]}", "label": f"{parts[1]}  {parts[3].replace('_', ' ')}"})
        for lang in ("en-us", "en-gb"):                                  # the variants matter most for English
            if any(v["id"] == f"espeak:{lang}" for v in out):
                out += [{"id": f"espeak:{lang}+{v}", "label": f"{lang}  variant {v}"} for v in ESPEAK_VARIANTS]
        return out

    @classmethod
    def resolve(cls, vid: str) -> str:
        lang, _, variant = vid.partition("+")
        langs = [v["id"].split(":", 1)[1] for v in cls.list_voices() if "+" not in v["id"]]
        if lang not in langs:
            close = _near(lang, langs)
            raise ValueError(f"espeak has no voice {lang!r}" + (f" (close: {close})" if close else "") + ". `blaze voices` lists them.")
        if variant and not re.fullmatch(r"[a-z]+\d?", variant):
            raise ValueError(f"espeak variant {variant!r} is not valid; try one of {', '.join(ESPEAK_VARIANTS)}")
        return vid

    def synth(self, text: str, profile: Profile, out_wav: Path) -> Optional[float]:
        if not _speakable(text):
            return None
        s = profile.seed
        chosen = _voice_part(profile, "espeak")
        if chosen:
            voice, pitch = chosen, 50
        elif profile.child:
            voice, pitch = "en-us+f%d" % (1 + s % 4), 78
        elif profile.gender == "f":
            voice, pitch = "en-us+f%d" % (1 + s % 5), 52 + (s >> 4) % 16
        else:
            voice, pitch = "en-us+m%d" % (1 + s % 7), 30 + (s >> 4) % 20
        if profile.pitch >= 0:
            pitch = profile.pitch
        raw = out_wav.with_suffix(".raw.wav")
        r = subprocess.run([self.binary, "-v", voice, "-p", str(pitch), "-s", str(profile.rate or self.wpm),
                            "-w", str(raw), text], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("espeak-ng failed: " + (r.stderr or "")[-300:])
        _require_audio(raw, "espeak-ng", f"voice {voice!r}")
        _normalise(raw, out_wav)
        raw.unlink(missing_ok=True)
        return wav_seconds(out_wav)


class Pyttsx3Voice:
    name = "pyttsx3"
    engine_id = "pyttsx3"
    hint = "Run: pip install pyttsx3   (it uses the voices of your operating system)."

    def __init__(self, wpm: int = 150):
        import pyttsx3  # noqa: F401  (import error -> caller falls back)
        self.wpm = wpm

    @classmethod
    def available(cls) -> bool:
        try:
            import pyttsx3  # noqa: F401
            return True
        except Exception:
            return False

    @classmethod
    def _voices(cls):
        import pyttsx3
        engine = pyttsx3.init()
        try:
            return list(engine.getProperty("voices") or [])
        finally:
            try:
                engine.stop()
            except Exception:
                pass

    @classmethod
    def list_voices(cls) -> List[dict]:
        if not cls.available():
            return []
        try:
            return [{"id": f"pyttsx3:{v.id}", "label": v.name or v.id} for v in cls._voices()]
        except Exception:
            return []

    @classmethod
    def resolve(cls, vid: str) -> str:
        voices = cls._voices()
        for v in voices:
            if v.id == vid:
                return vid
        hits = [v for v in voices if vid.lower() in (v.name or "").lower()]
        if len(hits) == 1:
            return hits[0].id
        names = [v.name or v.id for v in voices]
        raise ValueError(f"pyttsx3 voice {vid!r} " + ("matches several voices; be more specific. " if hits else "was not found. ")
                         + "Installed: " + ", ".join(names[:8]) + ("..." if len(names) > 8 else ""))

    def synth(self, text: str, profile: Profile, out_wav: Path) -> Optional[float]:
        if not _speakable(text):
            return None
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty("voices") or []
        chosen = _voice_part(profile, "pyttsx3")
        if chosen:
            engine.setProperty("voice", chosen)
        else:
            want = [v for v in voices if (("female" in (v.name or "").lower() or "zira" in (v.name or "").lower()) == (profile.gender == "f"))]
            pool = want or voices
            if pool:
                engine.setProperty("voice", pool[profile.seed % len(pool)].id)
        engine.setProperty("rate", profile.rate or self.wpm)
        raw = out_wav.with_suffix(".raw.wav")
        engine.save_to_file(text, str(raw))
        engine.runAndWait()
        engine.stop()
        if not raw.exists() or wav_seconds(raw) <= 0:
            raise RuntimeError(
                "pyttsx3 produced no audio (file exists but has zero frames -- "
                "on Windows this usually means no SAPI voice is installed on "
                "this machine; engine.getProperty('voices') returned "
                f"{len(voices)} voice(s))"
            )
        _normalise(raw, out_wav)
        raw.unlink(missing_ok=True)
        return wav_seconds(out_wav)


def piper_dirs() -> List[Path]:
    dirs = [Path(p) for p in os.environ.get("BLAZE_VOICES", "").split(os.pathsep) if p]
    return dirs + [Path.cwd() / "library" / "voices", Path.home() / ".blaze" / "voices"]


class PiperVoice:
    name = "piper"
    engine_id = "piper"
    hint = ("Install Piper (the `piper` program on PATH) and put voice models (*.onnx and *.onnx.json) in "
            "./library/voices, ~/.blaze/voices or the folder named by $BLAZE_VOICES.")

    def __init__(self, wpm: int = 150, binary: str = "piper"):
        if not shutil.which(binary):
            raise RuntimeError("piper is not installed. " + self.hint)
        self.wpm, self.binary = wpm, _exe(binary)

    @classmethod
    def available(cls) -> bool:
        return bool(shutil.which("piper"))

    @classmethod
    def models(cls) -> Dict[str, Path]:
        found: Dict[str, Path] = {}
        for d in piper_dirs():
            if d.is_dir():
                for f in sorted(d.glob("*.onnx")):
                    found.setdefault(f.stem, f)
        return found

    @classmethod
    def list_voices(cls) -> List[dict]:
        return [{"id": f"piper:{k}", "label": k} for k in cls.models()] if cls.available() else []

    @classmethod
    def resolve(cls, vid: str) -> str:
        models = cls.models()
        if vid not in models:
            close = _near(vid, list(models)) if models else ""
            raise ValueError(f"no Piper model named {vid!r}" + (f" (close: {close})" if close else "") + ". " + cls.hint)
        return vid

    def synth(self, text: str, profile: Profile, out_wav: Path) -> Optional[float]:
        if not _speakable(text):
            return None
        vid = _voice_part(profile, "piper")
        models = self.models()
        if not vid or vid not in models:
            raise RuntimeError(f"Piper needs a model: write voice=piper:<name> (models found: {', '.join(models) or 'none'}). " + self.hint)
        raw = out_wav.with_suffix(".raw.wav")
        err = ""
        for flag in ("--output_file", "--output-file"):                      # the two spellings of Piper's output option
            r = subprocess.run([self.binary, "--model", str(models[vid]), flag, str(raw)], input=text, capture_output=True,
                               text=True, encoding="utf-8")
            if r.returncode == 0 and raw.exists():
                break
            err = (r.stderr or "")[-300:]
        else:
            raise RuntimeError("piper failed: " + err)
        _require_audio(raw, "piper", f"model {vid!r}")
        _normalise(raw, out_wav, tempo=(profile.rate or self.wpm) / 150.0)
        raw.unlink(missing_ok=True)
        return wav_seconds(out_wav)


ENGINES = {"espeak": EspeakVoice, "pyttsx3": Pyttsx3Voice, "piper": PiperVoice}


# ------------------------------------------------------------------------------------------------ choosing and checking
class Router:
    """What the pipeline talks to. A line goes to the engine its character asked for, or to the default one."""

    def __init__(self, default, wpm: int = 150):
        self.default, self.wpm = default, wpm
        self._made: Dict[str, object] = {}

    @property
    def name(self) -> str:
        return self.default.name

    def engine(self, engine_id: str):
        if engine_id not in self._made:
            cls = ENGINES.get(engine_id)
            if cls is None:
                raise RuntimeError(f"unknown voice engine {engine_id!r}; the engines are {', '.join(ENGINE_NAMES)}")
            try:
                self._made[engine_id] = cls(self.wpm)
            except Exception as e:
                raise RuntimeError(f"voice engine {engine_id} is not available: {e}. " + getattr(cls, "hint", "")) from e
        return self._made[engine_id]

    def synth(self, text: str, profile: Profile, out_wav: Path) -> Optional[float]:
        spec = (profile.voice or "auto").strip()
        if spec.lower() == "off":
            return None
        if spec.lower() == "auto":
            return self.default.synth(text, profile, out_wav)
        return self.engine(spec.split(":", 1)[0].lower()).synth(text, profile, out_wav)


def get_voice(mode: str = "auto", wpm: int = 150) -> Router:
    """mode: auto | espeak | pyttsx3 | piper | off  (the engine used for characters with no voice of their own)"""
    mode = (mode or "auto").lower()
    if mode in ("off", "none", "silent"):
        return Router(SilentVoice(), wpm)
    if mode in ("auto", "espeak") and shutil.which("espeak-ng"):
        return Router(EspeakVoice(wpm), wpm)
    if mode in ("auto", "pyttsx3"):
        try:
            return Router(Pyttsx3Voice(wpm), wpm)
        except Exception:
            pass
    if mode == "piper":
        try:
            return Router(PiperVoice(wpm), wpm)
        except Exception:
            pass
    if mode != "auto":
        raise RuntimeError(f"Voice backend '{mode}' is not available. Install espeak-ng, pyttsx3 or piper, or use --voice off.")
    return Router(SilentVoice(), wpm)


def check_spec(spec: str) -> str:
    """Check a `voice=` value against what is installed here. Returns the value to use; raises ValueError saying what to do."""
    spec = (spec or "auto").strip()
    if spec.lower() in ("auto", "off"):
        return spec.lower()
    engine_id, _, vid = spec.partition(":")
    engine_id = engine_id.lower()
    cls = ENGINES.get(engine_id)
    if cls is None or not vid:
        raise ValueError(f"{spec!r} is not a voice: write <engine>:<voice> with the engine one of {', '.join(ENGINE_NAMES)}")
    if not cls.available():
        raise ValueError(f"the {engine_id} engine is not installed on this computer. {cls.hint}")
    return f"{engine_id}:{cls.resolve(vid)}"


def engines_info() -> List[dict]:
    """Every engine, whether it is installed, and the voices it offers (for `blaze voices` and the page)."""
    out = []
    for eid, cls in ENGINES.items():
        ok = cls.available()
        out.append({"engine": eid, "available": ok, "hint": "" if ok else cls.hint, "voices": cls.list_voices() if ok else []})
    return out


def preview(text: str, spec: str, out_wav: Path, gender: str = "m", child: bool = False, rate: int = 0, pitch: int = -1,
            wpm: int = 150) -> float:
    """Speak `text` once with the given voice (used by `blaze voices --say` and the page's Play button). Returns the seconds."""
    spec = check_spec(spec)
    router = get_voice("auto", wpm)
    seconds = router.synth(text, profile_for("preview", gender, child, spec, rate, pitch), out_wav)
    if seconds is None:
        raise RuntimeError("there is no voice engine to play this with (install espeak-ng or pyttsx3)" if spec == "auto" else "that voice is silent")
    return seconds


def estimate_seconds(text: str, wpm: int = 150) -> float:
    words = max(1, len(text.split()))
    return max(1.2, words * 60.0 / wpm + 0.45)


def write_silence(path: Path, seconds: float) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SAMPLE_RATE)
        w.writeframes(b"\x00\x00" * int(seconds * SAMPLE_RATE))


def build_track(entries: List[Tuple[float, Path]], total_seconds: float, out_path: Path) -> Path:
    """Place clips at their start times on a silent track of exactly total_seconds."""
    total = int(round(total_seconds * SAMPLE_RATE))
    buf = bytearray(total * 2)
    for start, path in entries:
        with wave.open(str(path), "rb") as w:
            data = w.readframes(w.getnframes())
        off = int(start * SAMPLE_RATE) * 2
        data = data[: max(0, len(buf) - off)]
        buf[off: off + len(data)] = data
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(buf))
    return out_path
