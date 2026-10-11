"""One whole production run, without any window: the offline demo for real, and every way a run can stop."""
import json
import threading
from pathlib import Path

import pytest
import yaml

from src.core.pipeline_factory import demo_config
from src.core.studio_run import RunCancelled, RunEvents, StudioRunError, run_studio
from src.providers.demo_provider import DEMO_STORY, BuiltinImageProvider, DemoPlanTextProvider
from tests.helpers import REPO, can_render

needs_render = pytest.mark.skipif(not can_render(), reason="needs node + playwright + ffmpeg")


@pytest.fixture
def cfg(tmp_path):
    c = yaml.safe_load((REPO / "studio" / "config.yaml").read_text(encoding="utf-8"))
    c["storage_path"] = str(tmp_path / "storage")
    return c


class TestDemoProviders:
    def test_the_built_in_story_is_a_plan_the_director_accepts(self, tmp_path):
        from src.core.director.director import Director
        from src.core.world_state.world_state import WorldStateManager
        plan = Director(DemoPlanTextProvider(), WorldStateManager({"storage_path": str(tmp_path)})).generate_production_plan("anything at all")
        assert [s.shot_id for s in plan.shots] == ["shot_001", "shot_002", "shot_003"]
        assert all(s.characters == ["John", "Mary"] for s in plan.shots)
        assert json.loads(DemoPlanTextProvider().generate("x")) == DEMO_STORY

    def test_characters_are_drawn_from_the_looks_in_the_description(self, tmp_path):
        from PIL import Image
        p = BuiltinImageProvider()
        a = p.generate_image("gender=m coat=1 hat=fedora top=0xd64036", tmp_path / "a.png")
        b = p.generate_image("gender=f dress=1 top=0x3c78d6", tmp_path / "b.png")
        assert Image.open(a).size == (400, 720) and Image.open(a).mode == "RGBA"
        assert a.read_bytes() != b.read_bytes()
        again = p.generate_image("gender=m coat=1 hat=fedora top=0xd64036", tmp_path / "a2.png")
        assert again.read_bytes() == a.read_bytes()                       # the same description is the same character

    def test_free_text_and_bad_looks_still_give_a_character(self, tmp_path):
        p = BuiltinImageProvider()
        assert p.generate_image("a tired detective in a brown coat", tmp_path / "x.png").exists()
        assert p.generate_image("hat=tophat coat=yes", tmp_path / "y.png").exists()          # unusable looks fall back, no crash

    def test_the_demo_config_needs_no_ai_and_keeps_its_files_apart(self, cfg):
        d = demo_config(cfg)
        assert (d["text_provider"], d["vision_provider"], d["image_provider"], d["render_backend"]) == ("demo", "dummy", "builtin", "cdrca")
        assert d["storage_path"].endswith("demo") and cfg["storage_path"] != d["storage_path"]
        from src.providers.provider_factory import validate_provider_config
        assert validate_provider_config(d)[0]


class TestRunsThatCannotStart:
    def test_an_empty_story_is_refused_with_a_reason(self, cfg):
        with pytest.raises(StudioRunError, match="Write what the video should be about"):
            run_studio(cfg, "   ")

    def test_no_provider_chosen_says_what_to_do(self, cfg):
        with pytest.raises(StudioRunError, match="Choose an AI provider first"):
            run_studio(cfg, "a story")

    def test_a_plan_that_is_not_json_is_explained_not_crashed(self, cfg):
        cfg.update(text_provider="dummy", vision_provider="dummy", image_provider="dummy")        # its answer is not a shot plan
        with pytest.raises(StudioRunError, match="shot plan could not be used"):
            run_studio(cfg, "a story")


class TestOrchestratorCancel:
    def test_cancel_stops_after_the_running_step(self):
        from types import SimpleNamespace
        from src.core.orchestrator.orchestrator import PipelineOrchestrator
        o = PipelineOrchestrator({}, None, SimpleNamespace(get_asset=lambda *a: Path("x.png")), None, None, None)
        seen = []

        class Done(Exception):
            pass

        def asset(task):
            seen.append(task.shot_id)
            if len(seen) == 2:
                o.cancel()
        o._run_generate_asset = asset
        o.load_task_schedule([SimpleNamespace(task_type="generate_asset", shot_id=f"s{i}", payload={}) for i in range(5)])
        assert o.run_pipeline() is False
        assert seen == ["s0", "s1"]


@needs_render
class TestTheDemoForReal:
    def test_the_offline_demo_makes_a_video(self, cfg):
        log = []
        ev = RunEvents(on_stage=lambda s, d: log.append(("stage", s)), on_plan=lambda p: log.append(("plan", len(p))),
                       on_shot=lambda i, s, d: log.append(("shot", i, s)), on_progress=lambda a, b: log.append(("progress", a, b)))
        result = run_studio(cfg, "", demo=True, events=ev)
        assert result.demo and result.shots == 3 and result.seconds == 9.0
        assert result.video.exists() and result.video.stat().st_size > 20_000
        stages = [e[1] for e in log if e[0] == "stage"]
        assert stages[0] == "planning" and stages[-1] == "assembling" and {"assets", "composing", "rendering"} <= set(stages)
        assert [e for e in log if e[0] == "plan"] == [("plan", 3)]
        for shot_id in ("shot_001", "shot_002", "shot_003"):
            states = [e[2] for e in log if e[0] == "shot" and e[1] == shot_id]
            assert states[0] == "queued" and states[-1] == "rendered" and "composed" in states
        last = [e for e in log if e[0] == "progress"][-1]
        assert last[1] == last[2]
        import subprocess
        dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(result.video)]).decode())
        assert 8.0 < dur < 10.0

    def test_cancelling_stops_the_run(self, cfg):
        cancel = threading.Event()
        ev = RunEvents(on_plan=lambda p: cancel.set())
        with pytest.raises(RunCancelled):
            run_studio(cfg, "", demo=True, events=ev, cancel=cancel)

    def test_cancelling_during_the_steps_stops_it_early(self, cfg):
        cancel = threading.Event()
        count = []
        ev = RunEvents(on_progress=lambda a, b: (count.append(a), cancel.set() if a == 2 else None))
        with pytest.raises(RunCancelled):
            run_studio(cfg, "", demo=True, events=ev, cancel=cancel)
        assert max(count) < 11                                   # it did not run all 11 steps


class TestPerUserDataFolder:
    """The installed app must never write inside its install folder (Program Files is read-only)."""

    def _run(self, tmp_path, code):
        import subprocess
        import sys
        env = dict(__import__("os").environ, AIPS_DATA_DIR=str(tmp_path / "data"), QT_QPA_PLATFORM="offscreen", PYTHONPATH=str(REPO / "studio"))
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=tmp_path, env=env)
        assert r.returncode == 0, r.stderr[-800:]
        return r.stdout.strip()

    def test_config_logs_and_files_go_to_the_persons_folder(self, tmp_path):
        out = self._run(tmp_path, "import main; c = main.load_config(); print(main.config_path()); print(c['storage_path']); print(main.LOG_PATH)")
        cfg, storage, logs = out.splitlines()
        data = str(tmp_path / "data")
        assert cfg.startswith(data) and storage.startswith(data) and logs.startswith(data)
        assert (tmp_path / "data" / "config.yaml").is_file()                      # seeded from the empty template
        assert not (tmp_path / "storage").exists()                                  # nothing was written next to where it ran

    def test_saving_keeps_the_storage_path_relative_and_the_choice(self, tmp_path):
        out = self._run(tmp_path, "import main; c = main.load_config(); c['text_provider'] = 'openai'; main.save_config(c); d = main.load_config(); print(d['text_provider']); print(d['storage_path'])")
        assert out.splitlines()[0] == "openai" and out.splitlines()[1].startswith(str(tmp_path / "data"))
