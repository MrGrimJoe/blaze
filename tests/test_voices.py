"""A voice per character: engines, listing, checking, the pipeline, the page's endpoints and the CLI."""
import functools
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import threading
import time
import urllib.request
import wave
from pathlib import Path

import pytest

from blaze import cli, procs, ui, voice
from blaze.pipeline import BlazeError, Options, create_project

HAVE_ESPEAK = bool(shutil.which("espeak-ng") and shutil.which("ffmpeg"))
needs_espeak = pytest.mark.skipif(not HAVE_ESPEAK, reason="needs espeak-ng and ffmpeg")


def _fake_piper(tmp_path, monkeypatch, models=("en_US-test-medium",), silent=False):
    """A stand-in `piper` program: writes a wav whose length depends on the text, and logs how it was called.
    It is a Python program behind a shim (a shell script, or piper.bat on Windows) so it is found on PATH like the real one."""
    bindir, voices = tmp_path / "bin", tmp_path / "voices"
    bindir.mkdir(); voices.mkdir()
    for m in models:
        (voices / f"{m}.onnx").write_bytes(b"model"); (voices / f"{m}.onnx.json").write_text("{}")
    calls = tmp_path / "calls.jsonl"
    (bindir / "fake_piper.py").write_text(f"""import sys, wave, json
args = sys.argv[1:]
out = args[args.index("--output_file") + 1] if "--output_file" in args else args[args.index("--output-file") + 1]
text = sys.stdin.read()
with open({str(calls)!r}, "a", encoding="utf-8") as f:
    f.write(json.dumps({{"model": args[args.index("--model") + 1], "text": text}}) + "\\n")
frames = 0 if {silent!r} else int(22050 * (0.3 + 0.05 * len(text.split())))
with wave.open(out, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
    w.writeframes(b"\\x10\\x00" * frames)
""", encoding="utf-8")
    if sys.platform == "win32":
        (bindir / "piper.bat").write_text(f'@echo off\r\n"{sys.executable}" "{bindir / "fake_piper.py"}" %*\r\n')
    else:
        shim = bindir / "piper"
        shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{bindir / "fake_piper.py"}" "$@"\n')
        shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("BLAZE_VOICES", str(voices))
    return calls


def _nothing_installed(monkeypatch):
    """Pretend no voice program is on PATH and pyttsx3 is not importable (works the same on every operating system)."""
    monkeypatch.setattr(shutil, "which", lambda *_a, **_k: None)
    monkeypatch.setattr(voice.Pyttsx3Voice, "available", classmethod(lambda cls: False))


class TestChecking:
    @pytest.mark.parametrize("spec", ["auto", "off", "AUTO"])
    def test_auto_and_off_need_no_engine(self, spec):
        assert voice.check_spec(spec) == spec.lower()

    @pytest.mark.parametrize("spec", ["nonsense", "foo:bar", "espeak:", ":x"])
    def test_malformed_specs_are_refused(self, spec):
        with pytest.raises(ValueError):
            voice.check_spec(spec)

    def test_an_engine_that_is_not_installed_says_how_to_get_it(self, monkeypatch):
        _nothing_installed(monkeypatch)
        with pytest.raises(ValueError, match="not installed.*Install"):
            voice.check_spec("piper:anything")

    def test_every_engine_is_listed_with_its_state(self):
        info = {e["engine"]: e for e in voice.engines_info()}
        assert set(info) == {"espeak", "pyttsx3", "piper"}
        for e in info.values():
            assert e["available"] or (e["hint"] and e["voices"] == [])


class TestEmptyAudio:
    """Seen for real on Windows: an engine that exits happily but writes a file with zero frames must fail loudly."""

    def test_piper_that_writes_no_audio_is_an_error_not_a_silent_video(self, tmp_path, monkeypatch):
        _fake_piper(tmp_path, monkeypatch, silent=True)
        with pytest.raises(RuntimeError, match="piper produced no audio"):
            voice.get_voice("off").synth("hello there", voice.profile_for("A", voice="piper:en_US-test-medium"), tmp_path / "x.wav")

    @pytest.mark.parametrize("text", ["...", "?!", "  ", "-- --"])
    def test_text_with_nothing_to_say_is_not_an_error_and_makes_no_sound(self, tmp_path, monkeypatch, text):
        calls = _fake_piper(tmp_path, monkeypatch)
        assert voice.get_voice("off").synth(text, voice.profile_for("A", voice="piper:en_US-test-medium"), tmp_path / "x.wav") is None
        assert not calls.exists()                                          # the engine was never even started

    def test_the_check_itself(self, tmp_path):
        empty = tmp_path / "e.wav"
        voice.write_silence(empty, 0)
        with pytest.raises(RuntimeError, match="zero frames"):
            voice._require_audio(empty, "demo")
        with pytest.raises(RuntimeError, match="missing"):
            voice._require_audio(tmp_path / "nope.wav", "demo")
        ok = tmp_path / "ok.wav"
        voice.write_silence(ok, 0.2)
        voice._require_audio(ok, "demo")


class TestPiper:
    def test_models_are_found_listed_and_checked(self, tmp_path, monkeypatch):
        _fake_piper(tmp_path, monkeypatch, ("en_US-a-low", "en_GB-b-high"))
        ids = {v["id"] for v in voice.PiperVoice.list_voices()}
        assert ids == {"piper:en_US-a-low", "piper:en_GB-b-high"}
        assert voice.check_spec("piper:en_GB-b-high") == "piper:en_GB-b-high"
        with pytest.raises(ValueError, match="no Piper model named 'en_GB-b-hihg'.*close: en_gb-b-high"):
            voice.check_spec("piper:en_GB-b-hihg")

    def test_a_character_is_spoken_by_the_model_it_asked_for(self, tmp_path, monkeypatch):
        calls = _fake_piper(tmp_path, monkeypatch, ("one", "two"))
        router = voice.get_voice("off")                                    # the default is silent; Piper is chosen per character
        d = router.synth("hello there", voice.profile_for("Ann", "f", voice="piper:two"), tmp_path / "a.wav")
        assert d and abs(d - voice.wav_seconds(tmp_path / "a.wav")) < 0.05
        assert json.loads(calls.read_text().splitlines()[0])["model"].endswith("two.onnx")
        assert router.synth("x", voice.profile_for("Bob", "m", voice="off"), tmp_path / "b.wav") is None
        assert router.synth("x", voice.profile_for("Cy"), tmp_path / "c.wav") is None          # auto -> the (silent) default

    @pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg missing")
    def test_the_rate_changes_the_length(self, tmp_path, monkeypatch):
        _fake_piper(tmp_path, monkeypatch)
        v = voice.get_voice("off")
        slow = v.synth("one two three four five six", voice.profile_for("A", voice="piper:en_US-test-medium", rate=100), tmp_path / "s.wav")
        fast = v.synth("one two three four five six", voice.profile_for("A", voice="piper:en_US-test-medium", rate=200), tmp_path / "f.wav")
        assert slow > fast * 1.5

    def test_a_missing_model_is_an_error_not_silence(self, tmp_path, monkeypatch):
        _fake_piper(tmp_path, monkeypatch)
        with pytest.raises(RuntimeError, match="needs a model"):
            voice.get_voice("off").synth("x", voice.profile_for("A", voice="piper:missing"), tmp_path / "x.wav")


@needs_espeak
class TestEspeakPerCharacter:
    def test_listing_and_variants(self):
        ids = {v["id"] for v in voice.EspeakVoice.list_voices()}
        assert "espeak:en-us" in ids and "espeak:en-gb+f2" in ids
        assert voice.check_spec("espeak:en-gb+m3") == "espeak:en-gb+m3"
        with pytest.raises(ValueError, match="no voice"):
            voice.check_spec("espeak:xx-nope")

    def test_two_characters_with_two_chosen_voices_sound_different(self, tmp_path):
        v = voice.get_voice("espeak")
        a, b = tmp_path / "a.wav", tmp_path / "b.wav"
        v.synth("Good morning everyone.", voice.profile_for("Same", "m", voice="espeak:en-gb+m3"), a)
        v.synth("Good morning everyone.", voice.profile_for("Same", "m", voice="espeak:en-us+f2"), b)
        assert a.read_bytes() != b.read_bytes()

    def test_rate_and_pitch_are_honoured(self, tmp_path):
        v = voice.get_voice("espeak")
        base = v.synth("one two three four five six seven", voice.profile_for("A", rate=120), tmp_path / "1.wav")
        fast = v.synth("one two three four five six seven", voice.profile_for("A", rate=220), tmp_path / "2.wav")
        assert base > fast * 1.3
        hi, lo = tmp_path / "hi.wav", tmp_path / "lo.wav"
        v.synth("hello", voice.profile_for("A", pitch=90), hi); v.synth("hello", voice.profile_for("A", pitch=10), lo)
        assert hi.read_bytes() != lo.read_bytes()

    def test_the_old_automatic_voice_is_unchanged(self, tmp_path):
        v = voice.get_voice("espeak")
        a = v.synth("Hello there.", voice.profile_for("Ana", "f"), tmp_path / "a.wav")
        b = v.synth("Hello there.", voice.profile_for("Ana", "f", voice="auto"), tmp_path / "b.wav")
        wa, wb = (tmp_path / "a.wav").read_bytes(), (tmp_path / "b.wav").read_bytes()
        # compared by size, checksum and length: when they differ pytest must not try to diff two whole audio files (on macOS
        # difflib spent the rest of the job on that, which hid the failure)
        assert (len(wa), hashlib.sha256(wa).hexdigest(), a) == (len(wb), hashlib.sha256(wb).hexdigest(), b)

    def test_preview_speaks_a_sample(self, tmp_path):
        secs = voice.preview("Testing one two", "espeak:en-us+m1", tmp_path / "p.wav")
        assert 0.5 < secs < 6 and (tmp_path / "p.wav").stat().st_size > 2000


@functools.lru_cache(maxsize=None)
def _pyttsx3_works() -> bool:
    """Asked while pytest is still collecting, so it must never be able to hang the run: a Windows SAPI engine that does not
    answer (no audio device, a runner without voices) used to stop every test, not just these. It is asked in a separate
    process with a time limit instead, and once."""
    if not shutil.which("ffmpeg"):
        return False
    code = "import pyttsx3; e = pyttsx3.init(); print(len(e.getProperty('voices') or []))"
    try:
        r = procs.run_bounded([sys.executable, "-c", code], 60)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and r.stdout.strip().isdigit() and int(r.stdout.strip()) > 0


@pytest.mark.skipif(not _pyttsx3_works(), reason="needs pyttsx3 with at least one system voice, and ffmpeg")
class TestPyttsx3PerCharacter:
    """On the Windows CI runner these use the real SAPI voices; on Linux, pyttsx3 drives espeak."""

    def test_the_systems_voices_are_listed_and_a_chosen_one_is_accepted(self):
        listed = voice.Pyttsx3Voice.list_voices()
        assert all(v["id"].startswith("pyttsx3:") and v["label"] for v in listed)
        first = listed[0]["id"]
        assert voice.check_spec(first) == first

    def test_a_voice_can_also_be_named_by_part_of_its_name_when_that_is_unambiguous(self):
        names = [v["label"] for v in voice.Pyttsx3Voice.list_voices()]
        unique = [n for n in names if sum(n.lower() in m.lower() for m in names) == 1]
        if not unique:
            pytest.skip("every voice name on this machine is a substring of another")
        got = voice.check_spec("pyttsx3:" + unique[0])
        assert got.startswith("pyttsx3:")

    def test_two_characters_with_two_system_voices_sound_different(self, tmp_path):
        listed = voice.Pyttsx3Voice.list_voices()
        if len(listed) < 2:
            pytest.skip("only one system voice is installed")
        v = voice.get_voice("off")                         # the default is silent; the characters ask for pyttsx3 themselves
        a, b = tmp_path / "a.wav", tmp_path / "b.wav"
        da = v.synth("Good morning everyone.", voice.profile_for("X", voice=listed[0]["id"]), a)
        db = v.synth("Good morning everyone.", voice.profile_for("X", voice=listed[-1]["id"]), b)
        assert da > 0.3 and db > 0.3 and a.read_bytes() != b.read_bytes()

    def test_the_speed_changes_the_length(self, tmp_path):
        spec = voice.Pyttsx3Voice.list_voices()[0]["id"]
        v = voice.get_voice("off")
        slow = v.synth("one two three four five six seven eight", voice.profile_for("X", voice=spec, rate=110), tmp_path / "s.wav")
        fast = v.synth("one two three four five six seven eight", voice.profile_for("X", voice=spec, rate=240), tmp_path / "f.wav")
        assert slow > fast * 1.2

    def test_preview_through_the_page_code(self, tmp_path):
        spec = voice.Pyttsx3Voice.list_voices()[0]["id"]
        assert voice.preview("Testing one two", spec, tmp_path / "p.wav") > 0.3


@functools.lru_cache(maxsize=None)
def _real_piper_model():
    """The name of a real Piper voice model, when the real `piper` program is installed (CI installs both; see ci.yml).
    Asked while pytest is still collecting, so it is bounded (on Windows piper.exe is a launcher: subprocess.run's own timeout
    hangs after it fires, because the child keeps the pipes open) and asked once, not once per decorator."""
    if not voice.PiperVoice.available():
        return None
    try:
        r = procs.run_bounded([voice._exe("piper"), "--help"], 60)
    except (OSError, subprocess.SubprocessError):
        return None
    if "--model" not in (r.stdout + r.stderr):
        return None
    models = list(voice.PiperVoice.models())
    return models[0] if models else None


@pytest.mark.skipif(not os.environ.get("BLAZE_REQUIRE_PIPER"), reason="CI sets BLAZE_REQUIRE_PIPER so a missing Piper fails the build")
def test_ci_has_the_real_piper_and_a_real_voice_model():
    assert voice.PiperVoice.available(), "the `piper` program is not on PATH (pip install piper-tts)"
    assert _real_piper_model(), "no Piper voice model found in $BLAZE_VOICES, ./library/voices or ~/.blaze/voices"


@pytest.mark.skipif(not _real_piper_model() or not shutil.which("ffmpeg"), reason="needs the real piper program, a voice model and ffmpeg")
class TestRealPiper:
    """Run against the real Piper and a real neural voice model, not a stand-in."""

    def test_the_model_is_listed_and_accepted(self):
        name = _real_piper_model()
        assert f"piper:{name}" in {v["id"] for v in voice.PiperVoice.list_voices()}
        assert voice.check_spec(f"piper:{name}") == f"piper:{name}"

    def test_it_speaks_real_audio_normalised_for_blaze(self, tmp_path):
        spec = f"piper:{_real_piper_model()}"
        secs = voice.preview("Hello from the real Piper.", spec, tmp_path / "p.wav")
        assert 0.8 < secs < 8
        with wave.open(str(tmp_path / "p.wav"), "rb") as w:
            assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (voice.SAMPLE_RATE, 1, 2)

    def test_the_speed_changes_the_length(self, tmp_path):
        spec = f"piper:{_real_piper_model()}"
        v = voice.get_voice("off")
        text = "one two three four five six seven eight nine ten"
        slow = v.synth(text, voice.profile_for("A", voice=spec, rate=110), tmp_path / "s.wav")
        fast = v.synth(text, voice.profile_for("A", voice=spec, rate=230), tmp_path / "f.wav")
        assert slow > fast * 1.4

    def test_a_character_on_piper_and_one_silent_make_a_screenplay_with_real_audio(self, tmp_path):
        spec = f"piper:{_real_piper_model()}"
        text = f"CAST: ANN gender=f voice={spec}\nCAST: BOB gender=m voice=off\nANN: Hello Bob, I am a neural voice.\nBOB: I say nothing.\n"
        sp, man = create_project(text, tmp_path / "proj", Options(voice="off", progress=lambda m: None))
        wavs = sorted((tmp_path / "proj" / "audio").glob("*.wav"))
        assert len(wavs) == 1 and voice.wav_seconds(wavs[0]) > 0.8      # Ann is spoken; Bob (voice=off) has no audio file


def _can_render() -> bool:
    if not (shutil.which("node") and shutil.which("ffmpeg")):
        return False
    return subprocess.run(["node", "-e", "require('playwright')"], cwd=str(Path(__file__).resolve().parent.parent / "cdrca"), capture_output=True).returncode == 0


@pytest.mark.skipif(not _real_piper_model() or not _can_render(), reason="needs the real piper program, a voice model and the renderer (node, playwright, ffmpeg)")
def test_a_real_video_with_a_real_piper_voice_has_audio_and_is_as_long_as_the_speech(tmp_path):
    """The whole path with a real neural voice: screenplay -> Piper audio -> CDRCA frames -> ffmpeg -> an mp4 with a sound track."""
    from blaze.pipeline import make
    spec = f"piper:{_real_piper_model()}"
    text = f"CAST: ANN gender=f voice={spec}\nCAST: BOB gender=m voice=off\nSCENE: s\nANN: Hello Bob, I am a neural voice.\nBOB: And I say nothing at all.\n"
    res = make(text, tmp_path / "v.mp4", Options(width=320, height=180, fps=8, voice="off", workers=1, progress=lambda m: None))
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(res.video)]).decode().split()
    assert "audio" in [x.rstrip(",") for x in out]                 # csv=p=0 leaves a trailing comma on some ffmpeg builds
    lines = [w for w in (res.project / "audio").glob("*.wav") if not w.stem.endswith("_track")]       # the per-scene track is not a line
    assert len(lines) == 1 and res.duration > voice.wav_seconds(lines[0])        # only Ann is spoken; Bob has voice=off


class TestPipelineVoices:
    TEXT = "CAST: ANN gender=f voice=piper:two rate=170\nCAST: BOB gender=m voice=off\nANN: Hello there my friend.\nBOB: Not a sound.\n> Meanwhile.\n"

    @pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg missing")
    def test_each_line_is_spoken_by_its_own_character_voice(self, tmp_path, monkeypatch):
        calls = _fake_piper(tmp_path, monkeypatch, ("one", "two"))
        logs = []
        sp, man = create_project(self.TEXT, tmp_path / "proj", Options(voice="off", progress=logs.append))
        spoken = [json.loads(l) for l in calls.read_text().splitlines()]
        assert [c["text"].strip() for c in spoken] == ["Hello there my friend."] and spoken[0]["model"].endswith("two.onnx")
        assert any(l.startswith("Voices:") and "Ann = piper:two" in l and "Bob = off" in l for l in logs)
        assert any(l.strip() == "Voice: silent" for l in logs)

    def test_a_voice_that_is_not_installed_stops_before_any_drawing(self, tmp_path, monkeypatch):
        _nothing_installed(monkeypatch)
        with pytest.raises(BlazeError, match="CAST Ann: .*not installed") as e:
            create_project("CAST: ANN voice=piper:x\nANN: hi\n", tmp_path / "proj", Options(voice="off", progress=lambda m: None))
        assert e.value.stage == "voices"
        assert not (tmp_path / "proj" / "scenes").exists() or not list((tmp_path / "proj" / "scenes").glob("*.cdrca"))


class TestCli:
    def test_expand_prints_the_core(self, tmp_path, capsys):
        f = tmp_path / "s.txt"; f.write_text("JOHN: hi\n> late\n", encoding="utf-8")
        assert cli.main(["expand", str(f)]) == 0
        out = capsys.readouterr().out
        assert 'SPEAK JOHN "hi"' in out and 'NARRATE "late"' in out and "CAST: JOHN" in out

    def test_expand_reports_a_bad_screenplay_with_its_line(self, tmp_path, capsys):
        f = tmp_path / "s.txt"; f.write_text("JOHN: hi\nLater that day: x\n", encoding="utf-8")
        assert cli.main(["expand", str(f)]) == 2
        assert "line 2" in capsys.readouterr().err

    def test_voices_lists_engines_and_says_how_to_install_the_missing(self, capsys, monkeypatch):
        _nothing_installed(monkeypatch)
        assert cli.main(["voices"]) == 0
        out = capsys.readouterr().out
        assert "espeak: not installed" in out and "pyttsx3: not installed" in out and "piper: not installed" in out

    @needs_espeak
    def test_voices_plays_a_sample_to_a_file(self, tmp_path, capsys):
        out = tmp_path / "s.wav"
        assert cli.main(["voices", "--voice", "espeak:en-us+f2", "--say", "Hello", "-o", str(out)]) == 0
        assert out.stat().st_size > 2000 and "CAST: NAME voice=espeak:en-us+f2" in capsys.readouterr().out

    def test_a_bad_voice_is_a_clean_error(self, capsys):
        assert cli.main(["voices", "--voice", "nope:x"]) == 2
        assert "Blaze failed" in capsys.readouterr().err


class TestPageEndpoints:
    @pytest.fixture
    def server(self, tmp_path):
        from http.server import ThreadingHTTPServer
        app = ui.App(tmp_path / "videos")
        srv = ThreadingHTTPServer(("127.0.0.1", 0), ui.make_handler(app))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        yield f"http://127.0.0.1:{srv.server_address[1]}", app
        srv.shutdown(); srv.server_close()

    @staticmethod
    def post(url, body):
        req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST")
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_check_reports_each_characters_voice_and_the_core_label_to_edit(self, server):
        url, _ = server
        code, r = self.post(url + "/api/check", {"text": 'CAST: JOHN voice=espeak:en-us+m3 rate=140\nCAST: "McGee"\nCAST: "Zoë"\nJOHN: hi\nMcGee: yo\nZoë: x\n> and\n'})
        assert code == 200 and r["ok"]
        assert r["voices"]["John"] == {"label": "JOHN", "voice": "espeak:en-us+m3", "rate": 140, "pitch": -1}
        assert r["voices"]["McGee"]["label"] == '"McGee"' and r["voices"]["McGee"]["voice"] == "auto"
        assert r["voices"]["Zoë"]["label"] == "ZOË"                      # written in capitals it parses back to the same character
        assert r["voices"]["Narrator"]["label"] == "NARRATOR" and "bubble" in r["looks"]

    def test_the_voice_list_endpoint(self, server):
        url, _ = server
        d = json.loads(urllib.request.urlopen(url + "/api/voices").read())
        assert {e["engine"] for e in d["engines"]} == {"espeak", "pyttsx3", "piper"}

    def test_a_bad_preview_is_a_400_with_the_reason(self, server):
        url, _ = server
        code, r = self.post(url + "/api/voice-preview", {"voice": "nope:x"})
        assert code == 400 and "not a voice" in r["error"]

    @needs_espeak
    def test_a_preview_is_made_cached_and_served(self, server):
        url, app = server
        code, r = self.post(url + "/api/voice-preview", {"voice": "espeak:en-gb+m2", "text": "Hello", "rate": 150})
        assert code == 200 and r["url"].startswith("/preview/") and r["seconds"] > 0.3
        again = self.post(url + "/api/voice-preview", {"voice": "espeak:en-gb+m2", "text": "Hello", "rate": 150})[1]
        assert again["url"] == r["url"]
        resp = urllib.request.urlopen(url + r["url"])
        assert resp.headers["Content-Type"] == "audio/wav" and len(resp.read()) > 2000
        assert not any(p.suffix != ".wav" for p in (app.workdir / "previews").iterdir())

    def test_a_preview_path_cannot_escape(self, server):
        url, _ = server
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(url + "/preview/../../etc/passwd.wav")
        assert e.value.code == 404

    def test_the_page_has_the_voice_panel(self):
        html = (Path(__file__).resolve().parent.parent / "blaze" / "ui_assets" / "index.html").read_text(encoding="utf-8")
        assert "/api/voices" in html and "/api/voice-preview" in html and "setCastKey" in html


FAKE_WORKER = """import json, sys, time, wave
req = json.load(open(sys.argv[1], encoding="utf-8"))
mode = req["text"]
if mode == "hang":
    time.sleep(300)
if mode == "boom":
    json.dump({"error": "RuntimeError: no such voice"}, open(sys.argv[2], "w"))
    sys.exit(0)
frames = 0 if mode == "silent" else 11025
with wave.open(req["wav"], "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050); w.writeframes(b"\\x00\\x00" * frames)
json.dump({"voices": 2, "engine": "fake", "seen": req}, open(sys.argv[2], "w"))
"""


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg missing")
class TestTheSystemVoiceRunsInAProcessOfItsOwn:
    """pyttsx3's runAndWait() never returned on the Windows runner. The system voice now runs in blaze/_sapi_worker.py, in a
    process that is stopped when time runs out, so these use a stand-in worker (the real one needs a real system voice)."""

    @pytest.fixture
    def speaker(self, tmp_path, monkeypatch):
        worker = tmp_path / "fake_worker.py"
        worker.write_text(FAKE_WORKER, encoding="utf-8")
        monkeypatch.setattr(voice, "SYSTEM_VOICE_WORKER", worker)
        v = object.__new__(voice.Pyttsx3Voice)        # no pyttsx3 needed: the stand-in does the speaking
        v.wpm = 150
        return v

    def test_a_line_is_spoken_and_normalised(self, speaker, tmp_path):
        seconds = speaker.synth("hello", voice.profile_for("Ana", "f", rate=170), tmp_path / "x.wav")
        assert seconds == pytest.approx(0.5, abs=0.05) and (tmp_path / "x.wav").stat().st_size > 2000
        assert not (tmp_path / "x.raw.wav").exists()

    def test_a_voice_that_never_answers_is_an_error_after_the_limit(self, speaker, tmp_path, monkeypatch):
        monkeypatch.setattr(voice, "SYSTEM_VOICE_TIMEOUT", 2)
        t0 = time.time()
        with pytest.raises(RuntimeError, match="did not finish within 2 s"):
            speaker.synth("hang", voice.profile_for("Ana"), tmp_path / "x.wav")
        assert time.time() - t0 < 30

    def test_the_workers_own_error_is_the_message(self, speaker, tmp_path):
        with pytest.raises(RuntimeError, match="no such voice"):
            speaker.synth("boom", voice.profile_for("Ana"), tmp_path / "x.wav")

    def test_a_silent_result_is_an_error_not_a_silent_video(self, speaker, tmp_path):
        with pytest.raises(RuntimeError, match="produced no audio"):
            speaker.synth("silent", voice.profile_for("Ana"), tmp_path / "x.wav")


class TestTheWorkersChoiceOfVoice:
    @pytest.fixture
    def worker(self):
        spec = importlib.util.spec_from_file_location("sapi_worker_under_test", voice.SYSTEM_VOICE_WORKER)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    VOICES = [("tok\\ZIRA", "Microsoft Zira Desktop"), ("tok\\DAVID", "Microsoft David Desktop"), ("tok\\MARK", "Microsoft Mark")]

    def test_a_voice_asked_for_by_id_or_by_a_part_of_its_name(self, worker):
        assert worker._pick(self.VOICES, "tok\\MARK", False, 0) == "tok\\MARK"
        assert worker._pick(self.VOICES, "david", False, 0) == "tok\\DAVID"

    def test_a_voice_that_is_missing_or_ambiguous_is_an_error(self, worker):
        with pytest.raises(ValueError, match="was not found"):
            worker._pick(self.VOICES, "nobody", False, 0)
        with pytest.raises(ValueError, match="several"):
            worker._pick(self.VOICES, "microsoft", False, 0)

    def test_without_a_request_the_gender_and_the_seed_choose(self, worker):
        assert worker._pick(self.VOICES, "", True, 7) == "tok\\ZIRA"
        assert worker._pick(self.VOICES, "", False, 0) in ("tok\\DAVID", "tok\\MARK")
        assert worker._pick(self.VOICES, "", False, 3) == worker._pick(self.VOICES, "", False, 3)
        assert worker._pick([], "", False, 3) is None
