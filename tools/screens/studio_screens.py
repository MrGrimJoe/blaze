"""
Screenshots of the desktop studio's windows (the first-run provider window in each state, and the main window).

    QT_QPA_PLATFORM=offscreen python tools/screens/studio_screens.py --out screens/studio

Writes <out>/*.png and <out>/manifest.json.
"""
import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
STUDIO = Path(__file__).resolve().parents[2] / "studio"
sys.path.insert(0, str(STUDIO))

from PyQt6.QtWidgets import QApplication  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="screens/studio")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    from src.ui.model_setup_dialog import ModelSetupDialog

    manifest, failed = [], 0

    def grab(widget, name, title, check):
        widget.show()
        for _ in range(5):
            app.processEvents()
        widget.grab().save(str(out / f"{name}.png"))
        manifest.append({"file": f"{name}.png", "title": title, "check": check})
        print("  ok ", name)

    def choose(d, provider):
        d.provider.setCurrentIndex(d.provider.findData(provider))

    try:
        d = ModelSetupDialog({})
        grab(d, "01-first-run-empty", "First run: nothing chosen",
             "No provider is preselected. Save is disabled. The wording says the key stays on this computer.")
        choose(d, "anthropic")
        grab(d, "02-anthropic-chosen", "Anthropic chosen",
             "A note says Anthropic cannot make images. The image menu offers only Gemini and OpenAI. Save is disabled.")
        d.key.setText("sk-ant-demo-key-not-real")
        grab(d, "03-anthropic-key-typed", "Anthropic with a key, no image source yet",
             "The key shows as dots. Save is still disabled until an image provider is chosen.")
        d.image.setCurrentIndex(d.image.findData("openai"))
        d.image_key.setText("sk-demo-image-key-not-real")
        grab(d, "04-anthropic-ready", "Anthropic for text, OpenAI for images",
             "A second key field appears for the image provider. Save is enabled.")
        d2 = ModelSetupDialog({})
        choose(d2, "gemini")
        d2.key.setText("demo-gemini-key-not-real")
        grab(d2, "05-gemini-ready", "Gemini for everything",
             "Images default to the same provider, no second key field, Save is enabled.")
        # ---- the main window, in every state --------------------------------------------------------
        import shutil
        import tempfile
        import threading
        import time
        from src.core.studio_run import RunCancelled, RunResult, StudioRunError, run_studio
        from src.providers.demo_provider import DEMO_STORY
        from src.ui import theme
        from src.ui.main_window import MainWindow as RealMainWindow

        chosen = {"text_provider": "anthropic", "vision_provider": "anthropic", "image_provider": "openai",
                  "anthropic_api_key": "demo", "openai_api_key": "demo", "image_openai_api_key": "demo"}
        plan = [{"shot_id": s["shot_id"], "description": s["scene_description"], "characters": s["characters"],
                 "seconds": s["duration_seconds"]} for s in DEMO_STORY["shots"]]

        def pump(win, seconds=0.5):
            end = time.time() + seconds
            while time.time() < end:
                app.processEvents()
                time.sleep(0.01)

        def until(win, cond, timeout=240):
            end = time.time() + timeout
            while time.time() < end and not cond():
                pump(win, 0.2)

        w = RealMainWindow({})
        pump(w)
        grab(w, "07-main-empty", "Main window: nothing chosen yet",
             "Calm and empty. The provider chip says Choose an AI provider; Make video is greyed out; the hint explains the offline demo.")
        w2 = RealMainWindow(chosen)
        w2.prompt.setPlainText("Two friends find a message in a bottle on a beach at sunset. They read it together and decide to look for who sent it.")
        pump(w2)
        grab(w2, "08-main-ready", "Main window: a story written, a provider chosen",
             "The chip shows both providers. Make video is dark and enabled. The hint explains what will happen.")

        def hold(config, prompt, demo=False, events=None, cancel=None):
            events.on_stage("rendering", "")
            events.on_plan(plan)
            for sh in plan:
                events.on_shot(sh["shot_id"], "queued", "")
            events.on_shot("shot_001", "rendered", "")
            events.on_shot("shot_002", "composed", "")
            events.on_progress(5, 11)
            cancel.wait(60)
            raise RunCancelled()
        w3 = RealMainWindow(chosen, run_fn=hold)
        w3.prompt.setPlainText("Two friends find a message in a bottle on a beach at sunset.")
        w3.make_button.click()
        until(w3, lambda: len(w3.rows) == 3 and w3.progress.value() > 0, 20)
        pump(w3, 0.5)
        grab(w3, "09-main-working", "Main window: working",
             "A heading says what is happening, a thin progress line grows, each shot shows its own state with a coloured dot, and Cancel is available.")
        w3.cancel()
        until(w3, lambda: not w3.busy, 20)

        def fail(config, prompt, demo=False, events=None, cancel=None):
            raise StudioRunError("The AI's shot plan could not be used: it was not valid JSON.")
        w4 = RealMainWindow(chosen, run_fn=fail)
        w4.prompt.setPlainText("A story")
        w4.make_button.click()
        until(w4, lambda: w4.stack.currentIndex() == 3 and not w4.busy, 20)
        pump(w4, 0.3)
        grab(w4, "10-main-error", "Main window: something went wrong",
             "A plain sentence says what failed (in red), and a button takes you back to your story, which is kept.")

        storage = tempfile.mkdtemp()
        w5 = RealMainWindow({"storage_path": storage})
        w5.demo_button.click()
        until(w5, lambda: w5.stack.currentIndex() in (2, 3) and not w5.busy)
        pump(w5, 0.5)
        if w5.stack.currentIndex() == 2:
            grab(w5, "11-main-result", "Main window: the finished offline demo",
                 "A still from the video, its length and size, and Play, Show in folder and Save a copy. This one was made for real by the offline demo.")
        else:
            manifest.append({"file": "", "title": "Main window: the finished offline demo", "check": "",
                             "error": "the offline demo could not run here: " + w5.error_label.text()[:160]})
        w6 = RealMainWindow({})
        w6.setStyleSheet(theme.stylesheet(True))
        pump(w6)
        grab(w6, "12-main-dark", "Main window: dark theme",
             "The same window in dark: readable text, the accent colour lifted, nothing washed out.")
        shutil.rmtree(storage, ignore_errors=True)
    except Exception as e:  # keep what was captured, report the rest
        failed += 1
        manifest.append({"file": "", "title": "error", "check": "", "error": f"{type(e).__name__}: {e}"})
        print("  FAIL", type(e).__name__, e)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
