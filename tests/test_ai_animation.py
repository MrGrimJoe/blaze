"""Whole animations from an LLM: outline, then one checked request per scene. A scripted fake stands in for the model."""
from pathlib import Path

import pytest

from blaze import ai
from blaze.screenplay import parse

REPO = Path(__file__).resolve().parent.parent

OUTLINE = """TITLE: The Kite
SUBTITLE: a short mystery
CAST: JOHN gender=m coat=1 top=0xd64036
CAST: MARY gender=f dress=1 top=0x3c78d6
SCENE 1: street | night_rain | John and Mary hear a strange noise
SCENE 2: beach | sunset | They find a kite and laugh"""
S1 = "SCENE: noise\nBACKDROP: gen:warehouse:day\nJOHN: Did you hear that?\nMARY: It is just the wind."
S2 = "SCENE: kite\nJOHN: Look, a kite!\nMARY: It is lovely."


class Fake:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def generate(self, prompt, system_instruction=None):
        self.calls.append(prompt)
        return self.replies.pop(0)


def animation(*replies, scenes=2, **kw):
    f = Fake(*replies)
    return ai.write_animation("a kite", scenes=scenes, provider=f, **kw), f


class TestWholeAnimation:
    def test_one_request_for_the_plan_and_one_per_scene(self):
        text, f = animation(OUTLINE, S1, S2)
        assert len(f.calls) == 3
        sp = parse(text)
        assert sp.title == "The Kite" and sp.subtitle == "a short mystery" and len(sp.scenes) == 2

    def test_the_cast_is_written_once_by_the_plan_and_never_by_the_scenes(self):
        text, _ = animation(OUTLINE, "CAST: JOHN gender=f\n" + S1, S2)
        assert text.count("CAST:") == 2 and "CAST: JOHN gender=m coat=1 top=0xd64036" in text

    def test_backdrops_come_from_the_plan_not_from_the_models_later_whims(self):
        text, _ = animation(OUTLINE, S1, S2)       # S1 asks for warehouse:day, the plan says street:night_rain
        assert [s.backdrop for s in parse(text).scenes] == ["gen:street:night_rain", "gen:beach:sunset"]

    def test_each_scene_request_sees_the_plan_and_the_earlier_scenes(self):
        _, f = animation(OUTLINE, S1, S2)
        assert "John and Mary hear a strange noise" in f.calls[2] and "Did you hear that?" in f.calls[2]
        assert "(this is the first scene)" in f.calls[1]

    def test_markdown_fences_are_removed(self):
        text, _ = animation("```\n" + OUTLINE + "\n```", "```text\n" + S1 + "\n```", S2)
        assert len(parse(text).scenes) == 2

    def test_progress_is_reported(self):
        msgs = []
        animation(OUTLINE, S1, S2, progress=msgs.append)
        assert msgs == ["Planning the story", "Writing scene 1 of 2", "Writing scene 2 of 2"]


class TestRetries:
    def test_a_bad_plan_is_sent_back_with_the_reason(self):
        bad = OUTLINE.replace("street | night_rain", "moon | night_rain")
        text, f = animation(bad, OUTLINE, S1, S2)
        assert "unknown place" in f.calls[1] and len(f.calls) == 4 and len(parse(text).scenes) == 2

    def test_wrong_number_of_scenes_is_refused(self):
        text, f = animation(OUTLINE.replace("SCENE 2: beach | sunset | They find a kite and laugh", ""), OUTLINE, S1, S2)
        assert "exactly 2 scenes" in f.calls[1]

    def test_a_character_outside_the_cast_is_refused(self):
        stray = "SCENE: noise\nJOHN: Hello.\nTIM: I am new here."
        text, f = animation(OUTLINE, stray, S1, S2)
        assert "Tim is not in the cast" in f.calls[2] and "Tim" not in parse(text).characters()

    def test_a_scene_without_dialogue_is_refused(self):
        _, f = animation(OUTLINE, "SCENE: quiet\nJOHN: Hi.", S1, S2)
        assert "at least 2 dialogue lines" in f.calls[2]

    def test_a_scene_that_never_works_stops_the_run_and_names_it(self):
        with pytest.raises(ai.AnimationError, match="scene 2"):
            animation(OUTLINE, S1, "no", "still no", "nope")

    def test_numbers_must_be_exact_in_scenes(self):
        wordy = S1 + "\n[ENTER MARY left]"
        _, f = animation(OUTLINE, wordy, S1, S2)
        assert "exact number" in f.calls[2]


class TestLimits:
    @pytest.mark.parametrize("n", [1, 9])
    def test_scene_count_bounds(self, n):
        with pytest.raises(ai.AnimationError):
            ai.write_animation("x", scenes=n, provider=Fake())

    def test_no_provider_chosen_gives_a_clear_next_step(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text('text_provider: ""\nvision_provider: ""\nimage_provider: ""\n', encoding="utf-8")
        with pytest.raises(RuntimeError, match="pick Anthropic, Gemini or OpenAI"):
            ai.write_animation("x", scenes=2, config_path=cfg)


def test_the_studio_copy_of_atoms_matches_the_source_of_truth():
    assert (REPO / "studio/src/integrations/cdrca/atoms.cdrca").read_text() == (REPO / "cdrca-lib/atoms.cdrca").read_text()
