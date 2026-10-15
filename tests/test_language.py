"""The screenplay language: strict names, an explicit core with sugar that expands into it, and text looks."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from blaze import art, compiler, looks
from blaze.screenplay import ScreenplayError, parse, to_core

REPO = Path(__file__).resolve().parent.parent
EXAMPLE = (Path(__file__).resolve().parent / "fixtures" / "sample_story.txt").read_text(encoding="utf-8")
DEMO = (REPO / "examples" / "looks-and-voices.txt").read_text(encoding="utf-8")


def beats(sp):
    return [[(b.kind, b.who, b.text, b.nums, b.look) for b in sc.beats] for sc in sp.scenes]


# ------------------------------------------------------------------------------------- names are strict
class TestStrictNames:
    @pytest.mark.parametrize("line", ["Later that day: Mary went home", "Note: bring an umbrella", "Meet at 12:30 ok"])
    def test_a_prose_line_with_a_colon_is_not_a_new_character(self, line):
        with pytest.raises(ScreenplayError, match="not a declared character") as e:
            parse(f"JOHN: hi\n{line}\nMARY: ok\n")
        assert str(e.value).startswith("line 2:") and "'>'" in str(e.value)

    def test_capitals_or_cast_make_a_speaker(self):
        sp = parse('CAST: Zoe gender=f\nZoe: hi\nJOHN: yo\n')
        assert sp.characters() == ["Zoe", "John"]

    def test_names_outside_a_to_z_work_once_declared(self):
        sp = parse('CAST: "Zoë" gender=f\nCAST: "علی" gender=m\nZoë: Hello\nعلی: salam\nJOHN: hi\n')
        assert sp.characters() == ["Zoë", "علی", "John"]
        with pytest.raises(ScreenplayError, match="not a declared character"):
            parse("Zoë: Hello\nJOHN: hi\n")                              # lower-case letters, so it must be declared

    def test_a_typo_in_a_command_cannot_invent_a_character(self):
        with pytest.raises(ScreenplayError, match=r"'JOHM' is not a character .*did you mean John") as e:
            parse("JOHN: hi\n[MOVE JOHM 3]\nMARY: yo\n")
        assert str(e.value).startswith("line 2:")

    def test_a_command_may_come_before_the_character_first_speaks(self):
        sp = parse("[MOVE JOHN 3]\nJOHN: hi\n")
        assert [b.kind for b in sp.scenes[0].beats] == ["move", "say"]

    def test_enter_may_introduce_but_a_typo_there_is_flagged(self):
        sp = parse("JOHN: hi\n[ENTER TIMM 9.5 3]\nJOHN: yo\n")
        assert any("TIMM".title() in w and "never speaks" in w for w in sp.warnings)

    def test_two_names_that_look_alike_warn_unless_declared(self):
        assert any("Jon looks like John" in w for w in parse("JOHN: hi\nJON: yo\nMARY: x\n").warnings)
        assert not parse("CAST: JON gender=m\nJOHN: hi\nJON: yo\nMARY: x\n").warnings

    def test_a_misspelt_directive_warns(self):
        assert any("did you mean TITLE" in w for w in parse("TITEL: oops\nJOHN: hi\n").warnings)

    def test_the_sample_story_is_clean(self):
        assert parse(EXAMPLE).warnings == []


class TestCommands:
    @pytest.mark.parametrize("cmd", ["[MOV JOHN 3]", "[WALK JOHN 3]"])
    def test_unknown_commands_are_errors(self, cmd):
        with pytest.raises(ScreenplayError, match="unknown command|not a command"):
            parse(f"JOHN: hi\n{cmd}\nMARY: yo\n")

    def test_the_error_suggests_the_command(self):
        with pytest.raises(ScreenplayError, match="did you mean MOVE"):
            parse("JOHN: hi\n[MOV JOHN 3]\n")
        with pytest.raises(ScreenplayError, match="did you mean MOVE"):
            parse("JOHN: hi [MOV JOHN 3]\n")

    def test_square_brackets_in_speech_are_text(self):
        sp = parse("JOHN: I put it in [the box] okay\nMARY: call [NASA] now\n")
        assert [b.text for b in sp.scenes[0].beats] == ["I put it in [the box] okay", "call [NASA] now"]

    def test_commands_written_as_their_own_lines_need_no_brackets(self):
        a = parse("JOHN: hi\nMOVE JOHN 3\nHOP JOHN\nPAUSE 1\nEXIT JOHN 9.5\n")
        b = parse("JOHN: hi\n[MOVE JOHN 3]\n[HOP JOHN]\n[PAUSE 1]\n[EXIT JOHN 9.5]\n")
        assert beats(a) == beats(b)


# ------------------------------------------------------------------------------------- core and sugar
class TestCoreAndSugar:
    SUGAR = "CAST: JOHN gender=m\nSCENE: s\nJOHN: Did you hear that?\n> It was late.\n[ENTER TIM 9.5 4]\nTIM: Hi!\n"
    CORE = 'CAST: JOHN gender=m\nSCENE: s\nSPEAK JOHN "Did you hear that?"\nNARRATE "It was late."\nENTER TIM 9.5 4\nSPEAK TIM "Hi!"\n'

    def test_sugar_and_core_are_the_same_screenplay(self):
        assert beats(parse(self.SUGAR)) == beats(parse(self.CORE))

    def test_speech_in_core_form_is_literal(self):
        sp = parse('SPEAK JOHN "Note: [HOP JOHN] and \\"quotes\\""\n')
        assert [(b.kind, b.text) for b in sp.scenes[0].beats] == [("say", 'Note: [HOP JOHN] and "quotes"')]

    def test_a_look_in_the_brackets_of_a_name_line_is_used_and_other_notes_are_ignored(self):
        sp = parse("DEFINE LOOK shout size=0.6\nJOHN (look=shout, angry): Stop!\n")
        b = sp.scenes[0].beats[0]
        assert b.look == "shout" and b.text == "Stop!"

    @pytest.mark.parametrize("text", [EXAMPLE, DEMO, 'CAST: "Zoë" gender=f\nCAST: "Dr Smith"\nZoë: hi\nDr Smith: yo\nHOP Zoë\n'])
    def test_expanding_and_parsing_again_gives_the_same_screenplay(self, text):
        sp = parse(text)
        again = parse(to_core(sp))
        assert beats(again) == beats(sp) and [s.backdrop for s in again.scenes] == [s.backdrop for s in sp.scenes]
        assert again.looks == sp.looks and again.speech == sp.speech
        assert to_core(again) == to_core(sp)                         # and the core form is stable

    def test_the_core_form_has_no_sugar(self):
        keywords = ("TITLE:", "SUBTITLE:", "CAST:", "DEFINE LOOK", "SCENE:", "BACKDROP:", "SPEAK ", "NARRATE ", "ENTER ", "EXIT ", "MOVE ", "HOP ", "PAUSE ")
        for line in to_core(parse(EXAMPLE)).splitlines():
            assert not line or line.startswith(keywords), line


class TestCastAndVoiceKeys:
    def test_voice_keys_do_not_leak_into_the_look(self):
        sp = parse("CAST: JOHN gender=m coat=1 voice=espeak:en-gb+m3 rate=140 pitch=40 look=bubble\nJOHN: hi\n")
        assert sp.cast["John"] == "gender=m coat=1"
        assert sp.speech["John"] == {"voice": "espeak:en-gb+m3", "rate": 140, "pitch": 40, "look": "bubble"}
        art.appearance_for("John", sp.cast["John"])                     # the look keys alone are still valid

    @pytest.mark.parametrize("bad, msg", [("voice=nope:x", "voice must be"), ("voice=espeak", "voice must be"), ("rate=9000", "rate must be"),
                                         ("rate=fast", "rate must be"), ("pitch=100", "pitch must be")])
    def test_bad_voice_values_are_errors(self, bad, msg):
        with pytest.raises(ScreenplayError, match=msg):
            parse(f"CAST: JOHN {bad}\nJOHN: hi\n")

    def test_a_quoted_cast_name_may_have_spaces(self):
        assert parse('CAST: "Mary Jane" gender=f\nMARY JANE: hi\n').characters() == ["Mary Jane"]

    def test_the_narrator_can_have_a_voice(self):
        sp = parse("CAST: Narrator voice=off\n> Once upon a time.\n")
        assert sp.speech["Narrator"]["voice"] == "off"


# ------------------------------------------------------------------------------------- looks
class TestLooks:
    def test_the_five_builtin_looks_exist(self):
        assert set(parse("JOHN: hi\n").looks) == {"bubble", "caption", "title", "subtitle", "none"}

    def test_define_with_a_base_and_without(self):
        sp = parse("DEFINE LOOK shout base=bubble size=0.6\nDEFINE LOOK plain fill=0x112233\nJOHN: hi\n")
        assert sp.looks["shout"].size == 0.6 and sp.looks["shout"].wrap == looks.BUILTIN["bubble"].wrap
        assert sp.looks["plain"].fill == 0x112233 and sp.looks["plain"].size == looks.BUILTIN["bubble"].size

    def test_redefining_a_builtin_keeps_the_rest_of_it(self):
        sp = parse("DEFINE LOOK caption ink=0xffd166\n> hi\n")
        assert sp.looks["caption"].ink == 0xFFD166 and sp.looks["caption"].fixed and sp.looks["caption"].y == -3.5

    def test_a_default_look_per_character(self):
        sp = parse("DEFINE LOOK big size=0.5\nCAST: JOHN look=big\nJOHN: hi\nMARY: yo\n")
        assert sp.look_name(sp.scenes[0].beats[0]) == "big" and sp.look_name(sp.scenes[0].beats[1]) == "bubble"

    @pytest.mark.parametrize("text, msg", [
        ("JOHN (look=nope): hi\n", "look 'nope' is not defined"),
        ('SPEAK JOHN "hi" look=nope\n', "look 'nope' is not defined"),
        ("CAST: JOHN look=nope\nJOHN: hi\n", "look 'nope' is not defined"),
        ("DEFINE LOOK a size=big\nJOHN: hi\n", "size must be a number"),
        ("DEFINE LOOK a fill=red\nJOHN: hi\n", "colour"),
        ("DEFINE LOOK a colour=0x1\nJOHN: hi\n", "unknown look key"),
        ("DEFINE LOOK a x=1\nJOHN: hi\n", "x and y go together"),
        ("DEFINE LOOK a alpha=2\nJOHN: hi\n", "alpha must be"),
        ("DEFINE LOOK a base=zzz\nJOHN: hi\n", "base=zzz is not defined"),
        ("DEFINE LOOK Bad-Name size=1\nJOHN: hi\n", "needs a name"),
    ])
    def test_bad_looks_are_errors_with_the_line(self, text, msg):
        with pytest.raises(ScreenplayError, match=msg):
            parse(text)

    def test_a_look_can_be_used_before_it_is_defined(self):
        assert parse("JOHN (look=late): hi\nDEFINE LOOK late size=0.5\n").looks["late"].size == 0.5

    def test_x_none_unsets_a_fixed_position(self):
        assert not parse("DEFINE LOOK caption x=none y=none\n> hi\n").looks["caption"].fixed


def _compile(text, tmp_path, dur=2.0, aspect=16 / 9):
    sp = parse(text)
    apps = {c: art.appearance_for(c, sp.cast.get(c, "")) for c in sp.characters()}
    bd = art.make_backdrop("street", art.MOODS["day"], tmp_path / "assets" / "bg.png")
    sc = sp.scenes[0]
    info = {i: (None, dur) for i, b in enumerate(sc.beats) if b.kind in ("say", "narr")}
    return compiler.compile_scene(1, sc, sp, apps, tmp_path, info, bd, 150, aspect), sp


def _props(shot, kind="Words"):
    return [l for l in shot.cdrca.read_text().splitlines() if l.startswith(f"use {kind}(")]


class TestCompilerUsesLooks:
    def test_a_look_changes_exactly_the_numbers_it_names(self, tmp_path):
        shot, _ = _compile("DEFINE LOOK shout base=bubble size=0.6 ink=0xff0000\nSCENE: s\nA: plain\nA (look=shout): LOUD\n", tmp_path)
        a, b = [l for l in _props(shot) if " as say_A" in l]
        fa, fb = a.split("(")[1].split(")")[0].split(", "), b.split("(")[1].split(")")[0].split(", ")
        assert fa[4] == "0.32" and fb[4] == "0.6" and fb[8] == "0xff0000" and fa[8] == "0x1b1f2a"
        assert fa[:4] != [] and fa[5:8] == fb[5:8]                      # wrap, fill, alpha untouched

    def test_a_fixed_look_is_one_prop_shared_by_every_speaker(self, tmp_path):
        shot, _ = _compile("DEFINE LOOK sign x=-4 y=3 ax=0 ay=1 tail=0\nSCENE: s\nA (look=sign): one\nB (look=sign): two\nA (look=sign): three\n", tmp_path)
        boxes = [l for l in _props(shot) if "as txt_sign" in l]
        assert len(boxes) == 1 and boxes[0].startswith("use Words(-4, 3, 0, 1,")
        assert not any(" as say_" in l for l in _props(shot))

    def test_the_hidden_look_speaks_without_drawing(self, tmp_path):
        shot, _ = _compile("SCENE: s\nA (look=none): secret\n", tmp_path)
        assert _props(shot) == [] and "flap" in shot.cdrca.read_text()
        assert shot.srt[0][2:] == ("A", "secret")

    def test_unclamped_looks_never_move_and_clamped_ones_stay_on_screen(self, tmp_path):
        shot, _ = _compile("DEFINE LOOK free x=0 y=0 clamp=0\nSCENE: s\nA: hi\nA (look=free): there\n", tmp_path)
        by = {l.split(" as ")[1]: l.split("(")[1].split(")")[0].split(", ") for l in _props(shot)}
        assert by["txt_free"][14:] == ["0", "0"] and float(by["say_A_1"][14]) > 6

    def test_narration_defaults_to_the_caption_look_and_may_use_another(self, tmp_path):
        shot, _ = _compile("DEFINE LOOK shout size=0.6\nSCENE: s\n> one\nNARRATE \"two\" look=title\nNARRATE \"three\" look=shout\n", tmp_path)
        aliases = {l.split(" as ")[1] for l in _props(shot)}
        assert aliases == {"caption", "txt_title", "txt_shout"}

    def test_the_title_card_follows_the_title_and_subtitle_looks(self, tmp_path):
        sp = parse("TITLE: T\nSUBTITLE: S\nDEFINE LOOK title ink=0xff00ff\nDEFINE LOOK subtitle show=0\nA: hi\n")
        shot = compiler.compile_title(0, sp, tmp_path, (10, 10, 20), (0, 0, 0))
        text = shot.cdrca.read_text()
        assert "0xff00ff" in text and 'say "T"' in text and 'say "S"' not in text          # a hidden subtitle look draws nothing

    def test_commands_that_cannot_happen_are_reported_not_hidden(self, tmp_path):
        shot, _ = _compile("SCENE: s\nA: hi\n[EXIT A 9.5]\n[MOVE A 2]\n[HOP A]\n[ENTER B 9.5 2]\n[ENTER B 9.5 2]\nB: yo\n", tmp_path)
        assert [n.split(", so ")[1] for n in shot.notes if "skipped" in n] == ["[MOVE] was skipped", "[HOP] was skipped", "[ENTER] was skipped"]
        assert all(n.startswith("line ") for n in shot.notes)

    def test_non_latin_names_get_safe_unique_ascii_files_and_aliases(self, tmp_path):
        sp = parse('CAST: "Zoë"\nCAST: "علی"\nCAST: "حسن"\nSCENE: s\nZoë: a\nعلی: b\nحسن: c\n')
        slugs = {art.slug(c) for c in sp.characters()}
        assert len(slugs) == 3 and all(s.isascii() for s in slugs)
        shot, _ = _compile('CAST: "Zoë"\nCAST: "علی"\nSCENE: s\nZoë: a\nعلی: b\n', tmp_path)
        aliases = re.findall(r"^use \w+\(.*\) as (\S+)$", shot.cdrca.read_text(), re.M)
        assert aliases and all(a.isascii() for a in aliases) and len(set(aliases)) == len(aliases)

    @pytest.mark.skipif(not shutil.which("node"), reason="node missing")
    def test_the_generated_script_with_looks_transpiles(self, tmp_path):
        shot, _ = _compile(DEMO.split("SCENE:", 1)[0]
                           + "SCENE: s\nJOHN: a\nMARY (look=whisper): b\nSPEAK JOHN \"c\" look=shout\nNARRATE \"d\" look=sign\nMARY (look=none): e\n", tmp_path)
        code = ("const {transpile}=require(%r);const fs=require('fs');"
                "const js=transpile({'index.cdrca':fs.readFileSync(%r,'utf8'),'atoms.cdrca':fs.readFileSync(%r,'utf8')});"
                "process.stdout.write(String(js.length>100)+' '+(js.match(/PropsDef:/g)||[]).length)"
                % (str(REPO / "cdrca" / "Back-end" / "Transpiler" / "index.js"), str(shot.cdrca), str(compiler.LIB_SOURCE)))
        r = subprocess.run(["node", "-e", code], capture_output=True, text=True)
        assert r.returncode == 0 and r.stdout == "true 1", r.stderr or r.stdout


class TestOneCopyOfTheLibrary:
    def test_studio_uses_the_same_atoms_library_as_blaze(self):
        copy = REPO / "studio" / "src" / "integrations" / "cdrca" / "atoms.cdrca"
        if copy.exists():
            assert copy.read_text(encoding="utf-8").split() == (REPO / "cdrca-lib" / "atoms.cdrca").read_text(encoding="utf-8").split(), \
                "studio's copy of atoms.cdrca has drifted from cdrca-lib/atoms.cdrca"
