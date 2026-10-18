"""Real voice engines (espeak-ng, pyttsx3), tested wherever they exist. In CI the engine of each operating system must exist."""
import os

import pytest

from blaze import voice


def engine_or_skip(mode):
    try:
        return voice.get_voice(mode)
    except RuntimeError:
        # named as the program is, because ci.yml lists the skips a job accepts by these words (espeak-ng on Windows, pyttsx3 on Linux)
        pytest.skip(f"{ {'espeak': 'espeak-ng'}.get(mode, mode) } is not available here")


@pytest.mark.parametrize("mode", ["espeak", "pyttsx3"])
def test_the_engine_speaks_and_the_length_is_measured(mode, tmp_path):
    v = engine_or_skip(mode)
    out = tmp_path / "line.wav"
    seconds = v.synth("Hello there. This is a test.", voice.profile_for("Ana", "f"), out)
    assert out.exists() and out.stat().st_size > 2000
    assert 0.8 < seconds < 8
    assert abs(seconds - voice.wav_seconds(out)) < 0.05


@pytest.mark.parametrize("mode", ["espeak", "pyttsx3"])
def test_two_characters_get_different_voices_or_pitch(mode, tmp_path):
    v = engine_or_skip(mode)
    a, b = tmp_path / "a.wav", tmp_path / "b.wav"
    v.synth("Good morning everyone.", voice.profile_for("Ana", "f"), a)
    v.synth("Good morning everyone.", voice.profile_for("Ben", "m", child=False), b)
    assert a.read_bytes() != b.read_bytes()


def test_a_whole_track_is_built_from_lines(tmp_path):
    v = engine_or_skip("auto") if voice.get_voice("auto").name != "silent" else pytest.skip("no voice engine here")
    lines = []
    for i, text in enumerate(["One.", "Two and three."]):
        wav = tmp_path / f"{i}.wav"
        lines.append((i * 2.0, wav))
        v.synth(text, voice.profile_for("Ana", "f"), wav)
    track = voice.build_track(lines, 6.0, tmp_path / "track.wav")
    assert abs(voice.wav_seconds(track) - 6.0) < 0.1


@pytest.mark.skipif(not os.environ.get("BLAZE_REQUIRE_VOICE"), reason="CI sets BLAZE_REQUIRE_VOICE so a missing engine fails the build")
def test_ci_has_a_working_voice_engine():
    chosen = voice.get_voice("auto")
    assert chosen.name != "silent", "no voice engine was found on this operating system"
