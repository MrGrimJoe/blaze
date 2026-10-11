"""The main window, driven the way a person drives it (offscreen): every state, errors, cancel, and the real offline demo."""
import os
import threading
import time
from pathlib import Path

import pytest
import yaml

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from src.core.studio_run import RunCancelled, RunResult, StudioRunError  # noqa: E402
from src.ui import main_window as mw  # noqa: E402
from src.ui import theme  # noqa: E402
from tests.helpers import REPO, can_render  # noqa: E402

CHOSEN = {"text_provider": "openai", "vision_provider": "openai", "image_provider": "openai", "openai_api_key": "k"}
PLAN = [{"shot_id": "shot_001", "description": "A street at night.", "characters": ["Ana", "Ben"], "seconds": 3.0},
        {"shot_id": "shot_002", "description": "A warehouse.", "characters": ["Ana"], "seconds": 4.0}]


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    a.setStyle("Fusion")
    return a


def pump_until(app, condition, timeout=60.0):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if condition():
            return True
        time.sleep(0.01)
    return False


def finished_run(tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"not really a video" * 100)

    def run_fn(config, prompt, demo=False, events=None, cancel=None):
        events.on_stage("planning", "")
        events.on_plan(PLAN)
        for s in PLAN:
            events.on_shot(s["shot_id"], "queued", "")
        events.on_stage("rendering", "")
        events.on_shot("shot_001", "composed", "")
        events.on_shot("shot_001", "rendered", "12 frames")
        events.on_shot("shot_002", "failed", "boom")
        events.on_progress(5, 10)
        return RunResult(video=video, shots=2, seconds=7.0, demo=demo)
    return run_fn


def window(config=None, run_fn=None):
    w = mw.MainWindow(dict(config if config is not None else {}), run_fn=run_fn or (lambda *a, **k: None))
    w.show()
    return w


class TestProviderChip:
    @pytest.mark.parametrize("cfg,expected", [
        ({}, "Choose an AI provider"),
        ({"text_provider": "openai", "image_provider": "openai"}, "OpenAI"),
        ({"text_provider": "anthropic", "image_provider": "gemini"}, "Anthropic for text  ·  Google Gemini for images"),
        ({"text_provider": "gemini"}, "Google Gemini"),
    ])
    def test_the_chip_says_what_is_chosen(self, cfg, expected):
        assert mw.provider_summary(cfg) == expected

    def test_clicking_it_asks_to_change_the_provider(self, app):
        w = window(CHOSEN)
        got = []
        w.model_change_requested.connect(lambda: got.append(1))
        w.provider_chip.click()
        assert got == [1]

    def test_changing_the_config_updates_the_chip_and_the_buttons(self, app):
        w = window({})
        w.prompt.setPlainText("a story")
        assert not w.make_button.isEnabled()
        w.set_config(CHOSEN)
        assert w.provider_chip.text() == "OpenAI" and w.make_button.isEnabled()


class TestButtons:
    def test_without_a_provider_only_the_demo_is_available(self, app):
        w = window({})
        w.prompt.setPlainText("a story")
        assert not w.make_button.isEnabled() and w.demo_button.isEnabled()
        assert "offline demo" in w.hint.text() and "no key" in w.hint.text()

    def test_make_needs_a_provider_and_some_text(self, app):
        w = window(CHOSEN)
        assert not w.make_button.isEnabled()                        # nothing written yet
        w.prompt.setPlainText("two friends on a beach")
        assert w.make_button.isEnabled()
        w.prompt.setPlainText("   ")
        assert not w.make_button.isEnabled()


class TestARun:
    def test_a_run_shows_the_shots_then_the_result(self, app, tmp_path):
        w = window(CHOSEN, finished_run(tmp_path))
        w.prompt.setPlainText("two friends on a beach")
        w.make_button.click()
        assert w.stack.currentIndex() == mw.PROGRESS
        assert pump_until(app, lambda: w.stack.currentIndex() == mw.RESULT and not w.busy)
        assert list(w.rows) == ["shot_001", "shot_002"]
        assert w.rows["shot_001"].head.text().endswith("done") and w.rows["shot_002"].head.text().endswith("failed")
        assert w.rows["shot_002"].toolTip() == "boom"
        assert w.progress.value() == 100 and w.result_meta.text().startswith("2 shots  ·  7 s")
        assert w.make_button.isEnabled() and w.demo_button.isEnabled() and not w.cancel_button.isVisible()

    def test_while_it_runs_you_can_only_cancel(self, app):
        release = threading.Event()

        def slow(config, prompt, demo=False, events=None, cancel=None):
            events.on_plan(PLAN)
            cancel.wait(30)
            raise RunCancelled()
        w = window(CHOSEN, slow)
        w.prompt.setPlainText("x")
        w.make_button.click()
        assert pump_until(app, lambda: len(w.rows) == 2)
        assert w.busy and w.cancel_button.isVisible() and not w.make_button.isEnabled() and not w.provider_chip.isEnabled()
        assert "cancel" in w.hint.text().lower()
        w.cancel()
        assert pump_until(app, lambda: not w.busy)
        assert w.stack.currentIndex() == mw.EMPTY and "Cancelled" in w.empty_label.text()
        assert w.make_button.isEnabled() and w.provider_chip.isEnabled()

    def test_a_failure_is_shown_in_plain_words(self, app):
        def fail(config, prompt, demo=False, events=None, cancel=None):
            raise StudioRunError("The AI's shot plan could not be used: not JSON")
        w = window(CHOSEN, fail)
        w.prompt.setPlainText("x")
        w.make_button.click()
        assert pump_until(app, lambda: w.stack.currentIndex() == mw.ERROR and not w.busy)
        assert "shot plan could not be used" in w.error_label.text()
        w.retry_button.click()
        assert w.stack.currentIndex() == mw.EMPTY and w.prompt.toPlainText() == "x"       # the story is kept

    def test_an_unexpected_exception_does_not_freeze_the_window(self, app):
        def crash(config, prompt, demo=False, events=None, cancel=None):
            raise ZeroDivisionError("oops")
        w = window(CHOSEN, crash)
        w.prompt.setPlainText("x")
        w.make_button.click()
        assert pump_until(app, lambda: w.stack.currentIndex() == mw.ERROR and not w.busy)
        assert "Something unexpected went wrong" in w.error_label.text() and "oops" in w.error_label.text()
        assert w.make_button.isEnabled()

    def test_a_second_run_starts_clean(self, app, tmp_path):
        w = window(CHOSEN, finished_run(tmp_path))
        w.prompt.setPlainText("x")
        for _ in range(2):
            w.make_button.click()
            assert pump_until(app, lambda: w.stack.currentIndex() == mw.RESULT and not w.busy)
        assert w.shot_list.count() == 2

    def test_closing_while_it_runs_does_not_hang(self, app):
        def slow(config, prompt, demo=False, events=None, cancel=None):
            cancel.wait(30)
            raise RunCancelled()
        w = window(CHOSEN, slow)
        w.prompt.setPlainText("x")
        w.make_button.click()
        pump_until(app, lambda: w.busy)
        started = time.time()
        w.close()
        assert time.time() - started < 8 and not w.busy

    def test_the_demo_button_runs_with_demo_set(self, app, tmp_path):
        seen = {}
        base = finished_run(tmp_path)

        def run(config, prompt, demo=False, events=None, cancel=None):
            seen["demo"], seen["prompt"] = demo, prompt
            return base(config, prompt, demo=demo, events=events, cancel=cancel)
        w = window({}, run)
        w.demo_button.click()
        assert pump_until(app, lambda: w.stack.currentIndex() == mw.RESULT and not w.busy)
        assert seen["demo"] is True
        assert "demo" in w.result_title.text().lower() and w.result_meta.text().endswith("offline demo")


class TestTheme:
    def test_light_and_dark_both_style_every_part(self):
        for dark in (False, True):
            css = theme.stylesheet(dark)
            t = theme.tokens(dark)
            assert t["accent"] in css and t["bg"] in css and "QPushButton#primary" in css and "QProgressBar::chunk" in css


@pytest.mark.skipif(not can_render(), reason="needs node + playwright + ffmpeg")
def test_the_real_offline_demo_through_the_window(app, tmp_path):
    cfg = yaml.safe_load((REPO / "studio" / "config.yaml").read_text(encoding="utf-8"))
    cfg["storage_path"] = str(tmp_path / "storage")
    w = mw.MainWindow(cfg)                      # the real run_fn
    w.show()
    w.demo_button.click()
    assert pump_until(app, lambda: w.stack.currentIndex() in (mw.RESULT, mw.ERROR) and not w.busy, timeout=240)
    assert w.stack.currentIndex() == mw.RESULT, w.error_label.text()
    assert w.last_result.video.exists() and w.last_result.shots == 3
    assert w.poster.pixmap() is not None and not w.poster.pixmap().isNull()           # a still from the video
    assert [w.rows[s].head.text().endswith("done") for s in w.rows] == [True, True, True]
