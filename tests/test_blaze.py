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
        assert sp.title == "The Warehouse" and sp.subtitle == "a very short mystery"
        assert sp.characters() == ["John", "Mary", "Tim"]
        assert [s.heading for s in sp.scenes] == ["street", "inside", "beach"]
        assert [s.backdrop for s in sp.scenes] == ["gen:street:night_rain", "gen:warehouse:night", "gen:beach:sunset"]
        assert sp.cast["John"] == "gender=m coat=1 hat=fedora glasses=1 top=0xd64036"      # key=value, kept exactly
        enter = [b for b in sp.scenes[1].beats if b.kind == "enter"][0]
        assert enter.who == "Tim" and enter.nums == [9.5, 4.2]                            # exact numbers, not words
        kinds = [b.kind for b in sp.scenes[1].beats]
        assert "pause" in kinds and "hop" in kinds and kinds.count("say") == 5
        assert sp.warnings == []

    def test_inline_cast_is_gone_and_notes_are_ignored(self):
        sp = parse("CAST: ANA gender=f dress=1\nSCENE: room\nANA: Hi!\nBOB (nervous): Hello.\n")
        assert sp.cast == {"Ana": "gender=f dress=1"}                    # "(nervous)" is an acting note, never a look
        assert [(b.who, b.text) for b in sp.scenes[0].beats] == [("Ana", "Hi!"), ("Bob", "Hello.")]

    def test_narration_and_commands(self):
        sp = parse("> It was late.\n[ENTER JOE 9.5 2]\nJOE: Hi [HOP JOE]\n[MOVE JOE -3]\n[EXIT JOE 9.5]\n[PAUSE 1.5]\n")
        k = [(b.kind, b.who, b.nums) for b in sp.scenes[0].beats]
        assert k == [("narr", "", []), ("enter", "Joe", [9.5, 2.0]), ("say", "Joe", []), ("hop", "Joe", []),
                     ("move", "Joe", [-3.0]), ("exit", "Joe", [9.5]), ("pause", "", [1.5])]

    @pytest.mark.parametrize("cmd", ["[ENTER JOE left]", "[ENTER JOE 9.5]", "[MOVE JOE right]", "[EXIT JOE]", "[PAUSE long]"])
    def test_words_where_numbers_belong_are_errors(self, cmd):
        with pytest.raises(ScreenplayError, match="exact number"):
            parse(f"JOE: hi\n{cmd}\n")

    def test_removed_directives_warn_instead_of_being_faked(self):
        sp = parse("STYLE: both\nCAMERA: shake\nWEATHER: snow\nA: hi\n")
        assert len(sp.warnings) == 3 and all("not supported" in w for w in sp.warnings)

    def test_unknown_lines_warn_not_crash(self):
        sp = parse("JOHN: hi\nthis is just prose\n[JUMP JOHN]\n")
        assert len(sp.warnings) == 2

    def test_empty_screenplay_raises(self):
        with pytest.raises(ScreenplayError):
            parse("TITLE: nothing\nCAST: A gender=m\n")


# ----------------------------------------------------------------- art
class TestArt:
    def test_appearance_from_exact_keys(self):
        a = art.appearance_for("John", "gender=m coat=1 hat=fedora glasses=1 top=0xd64036")
        assert a.gender == "m" and a.coat and a.glasses and a.hat == "fedora" and a.top == (0xD6, 0x40, 0x36)
        k = art.appearance_for("Tim", "gender=m child=1 top=0x40a060")
        assert k.child and k.height_scale < 1 and k.top == (0x40, 0xA0, 0x60)

    def test_words_are_not_a_look(self):
        for bad in ("man, detective, red coat", "gender=x", "hat=tophat", "hairstyle=mohawk", "coat", "hatt=fedora", "coat=yes", "glasses=2", "top=red", "skin=9x"):
            with pytest.raises(ValueError):
                art.appearance_for("Zed", bad)

    def test_stable_per_name(self):
        assert art.appearance_for("Zed") == art.appearance_for("Zed")

    def test_character_files(self, tmp_path):
        base, _ = art.make_character("Mary Jane", "gender=f", tmp_path)
        assert base.name == "mary_jane.png"
        for suffix in ("", "_talk", "_blink"):
            im = Image.open(tmp_path / f"mary_jane{suffix}.png")
            assert im.size == (400, 720) and im.mode == "RGBA"
        assert Image.open(tmp_path / "mary_jane.png").tobytes() != Image.open(tmp_path / "mary_jane_talk.png").tobytes()

    def test_generator_spec_is_exact(self):
        place, mood = art.parse_generator("gen:street:night_rain")
        assert place == "street" and mood.name == "night_rain" and mood.weather == "rain"
        assert art.parse_generator("gen:beach:sunset")[1].name == "sunset"
        for bad in ("rainy street at night", "gen:street", "gen:moon:day", "gen:street:gloomy", "street:day:x"):
            with pytest.raises(ValueError):
                art.parse_generator(bad)

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
def _compile(text, tmp_path, scene_index=0, dur=2.0):
    sp = parse(text)
    apps = {c: art.appearance_for(c, sp.cast.get(c, "")) for c in sp.characters()}
    bd = art.make_backdrop("street", art.MOODS["day"], tmp_path / "assets" / "bg.png")
    scene = sp.scenes[scene_index]
    info = {i: (None, dur) for i, b in enumerate(scene.beats) if b.kind in ("say", "narr")}
    return compiler.compile_scene(1, scene, sp, apps, tmp_path, info, bd), sp


def _defs(text, action):
    """[[alias, 'method param'], ...] for every `def ACTION <action> ...` line."""
    return [l.split(None, 4)[3:] for l in text.splitlines() if l.startswith(f"def ACTION {action} ")]


def _scene_count(js_source):
    return len(re.findall(r"PropsDef:", js_source))


class TestCompiler:
    def test_output_imports_the_cdrca_library_and_uses_only_its_props(self, tmp_path):
        shot, _ = _compile("SCENE: street\nA: one\nB: two\n", tmp_path)
        text = shot.cdrca.read_text()
        assert text.startswith('@IMPORT "./atoms.cdrca"') and text.rstrip().endswith("!---END---")
        assert set(re.findall(r"^use (\w+)\(", text, re.M)) == {"Picture", "Words"}   # written in CDRCA, not built in
        assert "exampleProps" not in text and "ImageProp" not in text and "TextProp" not in text
        assert (shot.cdrca.parent / "atoms.cdrca").read_text() == compiler.LIB_SOURCE.read_text()

    def test_each_beat_is_one_action_and_every_prop_is_listed(self, tmp_path):
        shot, _ = _compile("SCENE: street\nA: one\nB: two\n", tmp_path)
        text = shot.cdrca.read_text()
        actions = re.findall(r"^add new action (a\d+) (\d+) (\d+)$", text, re.M)
        assert len(actions) == 4                                          # speech + gap, twice
        aliases = set(re.findall(r"^use \w+\(.*\) as (\w+)$", text, re.M))
        for name, _stay, lerp in actions:
            assert int(lerp) == compiler.STEP_LERP_MS
            assert {d[0] for d in _defs(text, name)} == aliases           # an action only drives the props it names

    def test_speech_rate_comes_from_the_voice_length(self, tmp_path):
        shot, _ = _compile("SCENE: street\nA: one two three four\nB: two\n", tmp_path, dur=2.0)
        text = shot.cdrca.read_text()
        first = {}
        for alias, rest in _defs(text, "a001"):
            first.setdefault(alias, []).append(rest.split(None, 1))
        assert first["c_A"] == [["flap", '""']]                           # the speaker's mouth moves
        say = first["say_A_1"]
        assert say[1] == ["say", '"one two three four"']
        rate = float(say[0][1])
        assert say[0][0] == "rate" and abs(rate - len("one two three four") / (2.0 * 0.9)) < 0.01   # exact chars per second
        assert shot.srt[0][2:] == ("A", "one two three four") and shot.duration > 4.0

    def test_enter_exit_reflow(self, tmp_path):
        shot, _ = _compile("SCENE: street\nA: hi\n[ENTER B 9.5 2]\nB: yo\n[EXIT A -9.5]\nB: bye\n", tmp_path)
        text = shot.cdrca.read_text()
        a_line = [l for l in text.splitlines() if l.startswith("use") and " as c_A" in l][0]
        b_line = [l for l in text.splitlines() if l.startswith("use") and " as c_B" in l][0]
        assert '"../assets/a.png", 0,' in a_line                           # alone -> centred
        assert ", 9.5," in b_line                                          # B starts at x = 9.5, off screen
        moves = [l for l in text.splitlines() if "moveTo" in l]
        assert any("c_B moveTo" in m for m in moves) and any("c_A moveTo -9.5" in m for m in moves)

    def test_move_never_overlaps_another_character(self, tmp_path):
        assert compiler.clear_spot(4.5, [2.4]) >= 4.7 - 0.01
        assert compiler.clear_spot(0.0, [5.0]) == 0.0
        shot, _ = _compile("SCENE: street\nA: hi\nB: yo\n[MOVE A 2.5]\nB: ok\n", tmp_path)
        dest = [float(l.split()[-1]) for l in shot.cdrca.read_text().splitlines() if "c_A moveTo" in l][0]
        assert abs(dest - 2.4) >= 2.29                                     # B stands at 2.4

    @pytest.mark.parametrize("aspect", [16 / 9, 4 / 3, 1.0])
    def test_speech_boxes_are_limited_to_the_visible_screen(self, tmp_path, aspect):
        import math
        sp = parse("SCENE: street\nA: hi\n[ENTER B 9.5 4.2]\nB: a long line at the right edge\n")
        apps = {c: art.appearance_for(c, "") for c in sp.characters()}
        bd = art.make_backdrop("street", art.MOODS["day"], tmp_path / "assets" / "bg.png")
        scene = sp.scenes[0]
        info = {i: (None, 2.0) for i, b in enumerate(scene.beats) if b.kind in ("say", "narr")}
        shot = compiler.compile_scene(1, scene, sp, apps, tmp_path, info, bd, 150, aspect)
        boxes = [l for l in shot.cdrca.read_text().splitlines() if l.startswith("use Words(") and " as say_" in l]
        assert boxes
        half_h = 5 * math.tan(math.radians(75 / 2))
        for line in boxes:
            args = line[len("use Words("):line.index(") as")].split(", ")
            assert len(args) == 16
            assert abs(float(args[14]) - (half_h * aspect - 0.15)) < 0.01     # limit: half the visible width, minus a margin
            assert abs(float(args[15]) - (half_h - 0.15)) < 0.01              # limitY

    def test_text_cannot_break_the_script(self, tmp_path):
        shot, _ = _compile('SCENE: street\nA: She said "hi" \\ and left\n', tmp_path)
        assert 'say "She said \'hi\' / and left"' in shot.cdrca.read_text()

    @pytest.mark.skipif(not (shutil.which("node")), reason="node missing")
    def test_output_transpiles_to_exactly_one_scene(self, tmp_path):
        shot, _ = _compile(EXAMPLE, tmp_path, 1)
        shot2, _ = _compile("SCENE: street\nA: hi\n[ENTER B 9.5 2]\n[MOVE B -3]\nB: x\n", tmp_path)
        for sh in (shot, shot2):
            code = ("const {transpile}=require(%r);const fs=require('fs');"
                    "const js=transpile({'index.cdrca':fs.readFileSync(%r,'utf8'),'atoms.cdrca':fs.readFileSync(%r,'utf8')});"
                    "process.stdout.write(String(js.length>100)+' '+(js.match(/PropsDef:/g)||[]).length)"
                    % (str(REPO / "cdrca" / "Back-end" / "Transpiler" / "index.js"), str(sh.cdrca), str(compiler.LIB_SOURCE)))
            r = subprocess.run(["node", "-e", code], capture_output=True, text=True)
            # the library's own header blocks must not add empty scenes (CDRCA patch 11)
            assert r.returncode == 0 and r.stdout == "true 1", r.stderr or r.stdout


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
def test_speech_box_stays_on_screen_at_the_edges(tmp_path):
    """Regression: a long line from a speaker standing near the right edge ran off the frame ('...I only came to fin')."""
    text = ("CAST: AMY gender=f dress=1\nCAST: BEN gender=m child=1 top=0x40a060\nSCENE: street\nBACKDROP: gen:street:night\n"
            "AMY: Hello there. I was hoping we could talk.\n[ENTER BEN 9.5 4.2]\n"
            "BEN: Please don't be mad! I only came to find my kite.\n[MOVE AMY -4.5]\n"
            "AMY: Then you may look near the old tree over there.\n")
    opts = Options(width=320, height=180, fps=8, voice="off", workers=1, progress=lambda m: None)
    res = make(text, tmp_path / "out.mp4", opts)
    cues = [c for c in res.srt.read_text(encoding="utf-8").split("\n\n") if c.strip()]
    from PIL import ImageStat
    for cue in (cues[1], cues[2]):                                      # BEN at the right edge, then AMY at the left
        start, end = cue.splitlines()[1].split(" --> ")
        sec = lambda t: int(t[:2]) * 3600 + int(t[3:5]) * 60 + int(t[6:8]) + int(t[9:]) / 1000
        t = sec(start) + 0.9 * (sec(end) - sec(start))                  # the text is fully revealed by now
        frame = tmp_path / f"f_{t:.1f}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(res.video), "-frames:v", "1", str(frame)], check=True)
        im = Image.open(frame).convert("RGB")
        w, h = im.size
        for x in (0, w - 1):                                           # the outermost pixel columns
            col = [im.getpixel((x, y)) for y in range(0, h // 2)]
            assert not any(p == (255, 255, 255) for p in col), f"speech box touches the screen edge (column {x}) at {t:.1f}s"


@needs_render
def test_end_to_end_video(tmp_path):
    text = ("TITLE: Hi\nCAST: A gender=f coat=1 top=0xd64036\nSCENE: street\nBACKDROP: gen:street:night_rain\n"
            "A: Hello there.\n[ENTER B 9.5 2]\nB: Hi!\n")
    opts = Options(width=320, height=180, fps=8, voice="off", workers=2, progress=lambda m: None)
    res = make(text, tmp_path / "out.mp4", opts)
    assert res.video.exists() and res.srt.exists() and (res.project / "scenes" / "s01.cdrca").exists()
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(res.video)]).decode())
    assert abs(dur - res.duration) < 0.6
    streams = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(res.video)]).decode().split()
    assert "video" in streams and "audio" in streams
    # one second in, the scene must show content (regression: empty scenes from the library's header blocks made it black
    # for seconds). Frame 0 itself is black on purpose of the renderer: every scene fades in over ~0.3 s.
    shot = res.project / "shots" / "s01.mp4"
    assert shot.exists()
    frame = tmp_path / "first.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "1.0", "-i", str(shot), "-frames:v", "1", str(frame)], check=True)
    from PIL import ImageStat
    assert ImageStat.Stat(Image.open(frame).convert("L")).mean[0] > 15
