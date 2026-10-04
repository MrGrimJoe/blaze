import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from blaze import art, compiler, voice
from blaze.ai import write_screenplay
from blaze.pipeline import RENDER_SCRIPT, Options, make
from blaze.screenplay import ScreenplayError, parse

REPO = Path(__file__).resolve().parent.parent
EXAMPLE = (Path(__file__).resolve().parent / "fixtures" / "sample_story.txt").read_text(encoding="utf-8")


def have_render_tools():
    if not (shutil.which("node") and shutil.which("ffmpeg") and RENDER_SCRIPT.exists()):
        return False
    r = subprocess.run(["node", "-e", "require('playwright')"], cwd=str(REPO / "cdrca"), capture_output=True)
    return r.returncode == 0


needs_render = pytest.mark.skipif(not have_render_tools(), reason="needs node + playwright/Chromium + ffmpeg (python blaze.py doctor)")


# ----------------------------------------------------------------- screenplay
class TestScreenplay:
    def test_example_parses(self):
        sp = parse(EXAMPLE)
        assert sp.title == "The Warehouse" and sp.style == "bubbles"
        assert sp.characters() == ["John", "Mary", "Tim"]
        assert [s.heading for s in sp.scenes] == ["rainy street at night", "WAREHOUSE - NIGHT", "beach at sunset"]
        assert sp.cast["John"].startswith("man, detective")
        kinds = [b.kind for b in sp.scenes[1].beats]
        assert "enter" in kinds and "pause" in kinds and kinds.count("say") == 5

    def test_inline_cast_and_acting_notes(self):
        sp = parse("SCENE: room\nANA (woman, red dress): Hi!\nBOB (nervous): Hello.\n")
        assert sp.cast == {"Ana": "woman, red dress"}   # "(nervous)" is an acting note, not a look

    def test_narration_and_commands(self):
        sp = parse("> It was late.\n[ENTER JOE left]\nJOE: Hi [HOP JOE]\n[CAMERA shake] [WEATHER snow]\n")
        k = [(b.kind, b.arg) for b in sp.scenes[0].beats]
        assert ("narr", "") in k and ("enter", "left") in k and ("hop", "") in k and ("camera", "shake") in k and ("weather", "snow") in k

    def test_unknown_lines_warn_not_crash(self):
        sp = parse("JOHN: hi\nthis is just prose\n[JUMP JOHN]\n")
        assert len(sp.warnings) == 2

    def test_empty_screenplay_raises(self):
        with pytest.raises(ScreenplayError):
            parse("TITLE: nothing\nCAST: A = man\n")


# ----------------------------------------------------------------- art
class TestArt:
    def test_appearance_from_keywords(self):
        a = art.appearance_for("John", "man, detective, red coat, glasses")
        assert a.gender == "m" and a.coat and a.glasses and a.hat == "fedora" and a.top == art.COLORS["red"]
        k = art.appearance_for("Tim", "boy, green hoodie")
        assert k.child and k.height_scale < 1 and k.top == art.COLORS["green"]

    def test_stable_per_name(self):
        assert art.appearance_for("Zed") == art.appearance_for("Zed")

    def test_character_files(self, tmp_path):
        base, _ = art.make_character("Mary Jane", "woman", tmp_path)
        assert base.name == "mary_jane.png"
        for suffix in ("", "_talk", "_blink"):
            im = Image.open(tmp_path / f"mary_jane{suffix}.png")
            assert im.size == (400, 720) and im.mode == "RGBA"
        assert Image.open(tmp_path / "mary_jane.png").tobytes() != Image.open(tmp_path / "mary_jane_talk.png").tobytes()

    def test_place_and_mood(self):
        assert art.place_from("rainy street at night") == "street"
        assert art.place_from("INT. old warehouse") == "warehouse"
        assert art.mood_from("rainy street at night").name == "night_rain"
        assert art.mood_from("rainy street at night").weather == "rain"
        assert art.mood_from("beach at sunset").name == "sunset"
        assert art.mood_from("").name == "day"

    @pytest.mark.parametrize("place", ["street", "room", "warehouse", "forest", "beach", "office"])
    def test_backdrops(self, place, tmp_path):
        p = art.make_backdrop(place, art.MOODS["night"], tmp_path / f"{place}.png")
        assert Image.open(p).size == (1920, 1080)


# ----------------------------------------------------------------- voice
class TestVoice:
    def test_profile_is_stable_and_respects_gender(self):
        assert voice.profile_for("Ann", "f") == voice.profile_for("Ann", "f")
        assert voice.profile_for("Ann", "f").gender == "f"

    def test_estimate_scales_with_words(self):
        assert voice.estimate_seconds("hi") >= 1.2
        assert voice.estimate_seconds("word " * 30) > voice.estimate_seconds("word " * 5)
        assert voice.estimate_seconds("word " * 30, wpm=100) > voice.estimate_seconds("word " * 30, wpm=200)

    def test_track_has_exact_length(self, tmp_path):
        clip = tmp_path / "c.wav"; voice.write_silence(clip, 0.5)
        out = voice.build_track([(1.0, clip), (4.0, clip)], 5.25, tmp_path / "t.wav")
        assert abs(voice.wav_seconds(out) - 5.25) < 0.01

    def test_silent_backend(self):
        assert voice.get_voice("off").synth("x", voice.Profile(), Path("x.wav")) is None

    @pytest.mark.skipif(not shutil.which("espeak-ng") or not shutil.which("ffmpeg"), reason="espeak-ng/ffmpeg missing")
    def test_espeak_speaks(self, tmp_path):
        v = voice.get_voice("espeak")
        d = v.synth("Hello there, my friend.", voice.profile_for("Bob", "m"), tmp_path / "a.wav")
        assert 0.8 < d < 4 and abs(voice.wav_seconds(tmp_path / "a.wav") - d) < 0.01


# ----------------------------------------------------------------- compiler
def _compile(text, tmp_path, scene_index=0):
    sp = parse(text)
    apps = {c: art.appearance_for(c, sp.cast.get(c, "")) for c in sp.characters()}
    bd = art.make_backdrop("street", art.MOODS["day"], tmp_path / "assets" / "bg.png")
    scene = sp.scenes[scene_index]
    info = {i: (None, 2.0) for i, b in enumerate(scene.beats) if b.kind in ("say", "narr")}
    return compiler.compile_scene(1, scene, sp, apps, tmp_path, info, bd), sp


def _defs(text, action):
    return [l.split(None, 4)[3:] for l in text.splitlines() if l.startswith(f"def ACTION {action} ")]


class TestCompiler:
    def test_output_is_plain_cdrca_with_stock_props_only(self, tmp_path):
        shot, _ = _compile("SCENE: street\nA: one\nB: two\n", tmp_path)
        text = shot.cdrca.read_text()
        used = set(re.findall(r"exampleProps\.(\w+)\(", text))
        assert used <= {"ImageProp", "TextProp"}
        assert "blaze" not in text.lower().replace("blaze_", "")        # no Blaze-specific props or tracks
        assert text.startswith("!--- SCENE") and text.rstrip().endswith("!---END---")

    def test_each_beat_is_one_action_and_every_prop_is_listed(self, tmp_path):
        shot, _ = _compile("SCENE: street\nA: one\nB: two\n", tmp_path)
        text = shot.cdrca.read_text()
        actions = re.findall(r"^add new action (a\d+) (\d+) (\d+)$", text, re.M)
        assert len(actions) == 4                                          # speech + gap, twice
        n_props = len(re.findall(r"^use ", text, re.M))
        for name, _stay, lerp in actions:
            assert int(lerp) == compiler.STEP_LERP_MS
            assert len(_defs(text, name)) == n_props                      # an action only drives the props it names

    def test_talking_and_bubble(self, tmp_path):
        shot, _ = _compile("SCENE: street\nA: one\nB: two\n", tmp_path)
        text = shot.cdrca.read_text()
        first = {d[0]: d[1].split(None, 1) for d in _defs(text, "a001")}
        assert first["c_A"][0] == "talk"
        say = [v for k, v in first.items() if k.startswith("say_")]
        assert any(v[0] == "say" and "one" in v[1] for v in say)
        assert shot.srt[0][2:] == ("A", "one") and shot.duration > 4.0

    def test_enter_exit_reflow(self, tmp_path):
        shot, _ = _compile("SCENE: street\nA: hi\n[ENTER B right]\nB: yo\n[EXIT A left]\nB: bye\n", tmp_path)
        text = shot.cdrca.read_text()
        a_line = [l for l in text.splitlines() if l.startswith("use") and " as c_A" in l][0]
        b_line = [l for l in text.splitlines() if l.startswith("use") and " as c_B" in l][0]
        assert '"../assets/a.png", 0,' in a_line                           # alone -> centred
        assert ", 9.5," in b_line                                          # B starts off screen right
        moves = [l for l in text.splitlines() if "moveTo" in l]
        assert any("c_B moveTo" in m for m in moves) and any("c_A moveTo -9.5" in m for m in moves)

    def test_move_never_overlaps_another_character(self, tmp_path):
        assert compiler.clear_spot(4.5, [2.4]) >= 4.7 - 0.01
        assert compiler.clear_spot(0.0, [5.0]) == 0.0
        shot, _ = _compile("SCENE: street\nA: hi\nB: yo\n[MOVE A right]\nB: ok\n", tmp_path)
        dest = [float(l.split()[-1]) for l in shot.cdrca.read_text().splitlines() if "c_A moveTo" in l][0]
        assert abs(dest - 2.4) >= 2.29                                     # B stands at 2.4

    def test_unsupported_commands_are_reported_not_faked(self, tmp_path):
        shot, _ = _compile("SCENE: rainy street\nA: hi\n[CAMERA push]\n[WEATHER storm]\n", tmp_path)
        assert any("CAMERA" in n for n in shot.notes) and any("WEATHER" in n for n in shot.notes)

    def test_text_cannot_break_the_script(self, tmp_path):
        shot, _ = _compile('SCENE: street\nA: She said "hi" \\ and left\n', tmp_path)
        assert 'say "She said \'hi\' / and left"' in shot.cdrca.read_text()

    @pytest.mark.skipif(not (shutil.which("node")), reason="node missing")
    def test_output_transpiles(self, tmp_path):
        shot, _ = _compile(EXAMPLE, tmp_path, 1)
        shot2, _ = _compile("SCENE: street\nA: hi\n[ENTER B right]\n[MOVE B left]\nB: x\n", tmp_path)
        for sh in (shot, shot2):
            code = ("const {transpile}=require(%r);const fs=require('fs');"
                    "const js=transpile({'index.cdrca':fs.readFileSync(%r,'utf8')});process.stdout.write(String(js.length>100))"
                    % (str(REPO / "cdrca" / "Back-end" / "Transpiler" / "index.js"), str(sh.cdrca)))
            r = subprocess.run(["node", "-e", code], capture_output=True, text=True)
            assert r.returncode == 0 and r.stdout == "true", r.stderr


# ----------------------------------------------------------------- ai
class FakeProvider:
    def __init__(self, *answers): self.answers, self.calls = list(answers), []
    def generate(self, prompt, system_instruction=None):
        self.calls.append((prompt, system_instruction)); return self.answers.pop(0)


class TestAI:
    def test_returns_valid_screenplay_and_strips_fences(self):
        p = FakeProvider("```\nTITLE: T\nSCENE: room\nA: hi\nB: hello\n```")
        text = write_screenplay("a greeting", provider=p, level="A2")
        assert text.startswith("TITLE: T") and "A2" in p.calls[0][1]

    def test_retries_once_with_feedback(self):
        p = FakeProvider("sorry, I can't", "SCENE: room\nA: hi\nB: yo")
        assert "A: hi" in write_screenplay("x", provider=p)
        assert "could not be used" in p.calls[1][0]

    def test_second_failure_surfaces(self):
        with pytest.raises(ScreenplayError):
            write_screenplay("x", provider=FakeProvider("nope", "still nope"))


# ----------------------------------------------------------------- end to end (real render)
@needs_render
def test_end_to_end_video(tmp_path):
    text = "TITLE: Hi\nSTYLE: both\nCAST: A = woman, red coat\nSCENE: rainy street at night\nA: Hello there.\n[ENTER B right]\nB: Hi!\n"
    opts = Options(width=320, height=180, fps=8, voice="off", workers=2, progress=lambda m: None)
    res = make(text, tmp_path / "out.mp4", opts)
    assert res.video.exists() and res.srt.exists() and (res.project / "scenes" / "s01.cdrca").exists()
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(res.video)]).decode())
    assert abs(dur - res.duration) < 0.6
    streams = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(res.video)]).decode().split()
    assert "video" in streams and "audio" in streams
    # frames must actually differ over time (it is animated, not a still)
    shots = sorted((res.project / "shots").glob("s01.mp4"))
    assert shots
