"""
Text-to-speech for Blaze, with graceful fallbacks.

  espeak-ng   (Linux/macOS/Windows; install from https://github.com/espeak-ng/espeak-ng)  - used first if on PATH
  pyttsx3     (Windows SAPI voices, macOS NSSpeech; `pip install pyttsx3`)                  - used second
  silent      no audio; line lengths are estimated from word count

Every character gets a stable voice (hash of their name, plus gender/child from their look).
All clips are normalised to 22.05 kHz mono 16-bit with ffmpeg so they can be stitched together.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

SAMPLE_RATE = 22050


@dataclass
class Profile:
    gender: str = "m"       # m | f
    child: bool = False
    seed: int = 0


def profile_for(name: str, gender: str = "n", child: bool = False) -> Profile:
    seed = int(hashlib.sha1(name.lower().encode()).hexdigest(), 16)
    if gender not in ("m", "f"):
        gender = "f" if seed % 2 else "m"
    return Profile(gender, child, seed)


def wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def _normalise(src: Path, dst: Path) -> None:
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ar", str(SAMPLE_RATE), "-ac", "1",
                        "-sample_fmt", "s16", str(dst)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg could not normalise audio: " + r.stderr[-300:])


class SilentVoice:
    name = "silent"

    def synth(self, text: str, profile: Profile, out_wav: Path) -> Optional[float]:
        return None


class EspeakVoice:
    name = "espeak-ng"

    def __init__(self, wpm: int = 150, binary: str = "espeak-ng"):
        self.wpm, self.binary = wpm, binary

    def synth(self, text: str, profile: Profile, out_wav: Path) -> Optional[float]:
        s = profile.seed
        if profile.child:
            variant, pitch = "f%d" % (1 + s % 4), 78
        elif profile.gender == "f":
            variant, pitch = "f%d" % (1 + s % 5), 52 + (s >> 4) % 16
        else:
            variant, pitch = "m%d" % (1 + s % 7), 30 + (s >> 4) % 20
        raw = out_wav.with_suffix(".raw.wav")
        r = subprocess.run([self.binary, "-v", "en-us+" + variant, "-p", str(pitch), "-s", str(self.wpm),
                            "-w", str(raw), text], capture_output=True, text=True)
        if r.returncode != 0 or not raw.exists():
            raise RuntimeError("espeak-ng failed: " + (r.stderr or "")[-300:])
        _normalise(raw, out_wav)
        raw.unlink(missing_ok=True)
        return wav_seconds(out_wav)


class Pyttsx3Voice:
    name = "pyttsx3"

    def __init__(self, wpm: int = 150):
        import pyttsx3  # noqa: F401  (import error -> caller falls back)
        self.wpm = wpm

    def synth(self, text: str, profile: Profile, out_wav: Path) -> Optional[float]:
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty("voices") or []
        want = [v for v in voices if (("female" in (v.name or "").lower() or "zira" in (v.name or "").lower()) == (profile.gender == "f"))]
        pool = want or voices
        if pool:
            engine.setProperty("voice", pool[profile.seed % len(pool)].id)
        engine.setProperty("rate", self.wpm)
        raw = out_wav.with_suffix(".raw.wav")
        engine.save_to_file(text, str(raw))
        engine.runAndWait()
        engine.stop()
        if not raw.exists():
            raise RuntimeError("pyttsx3 produced no audio")
        _normalise(raw, out_wav)
        raw.unlink(missing_ok=True)
        return wav_seconds(out_wav)


def get_voice(mode: str = "auto", wpm: int = 150):
    """mode: auto | espeak | pyttsx3 | off"""
    mode = (mode or "auto").lower()
    if mode in ("off", "none", "silent"):
        return SilentVoice()
    if mode in ("auto", "espeak") and shutil.which("espeak-ng"):
        return EspeakVoice(wpm)
    if mode in ("auto", "pyttsx3"):
        try:
            return Pyttsx3Voice(wpm)
        except Exception:
            pass
    if mode not in ("auto",):
        raise RuntimeError(f"Voice backend '{mode}' is not available. Install espeak-ng or pyttsx3, or use --voice off.")
    return SilentVoice()


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
