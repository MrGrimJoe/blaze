"""
Tests for CdrcaRenderer + CdrcaSceneComposer.

  1. Mocked/unit tests — run anywhere (no node/Chromium needed).
  2. A real end-to-end test (compose -> render -> assemble mp4) — skipped unless
     BLAZENG_CDRCA_RENDER points at cdrca/Back-end/Render/render.js and
     node + playwright/Chromium + ffmpeg are available.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.core.scene_composer.cdrca_composer import CdrcaComposeError, CdrcaSceneComposer
from src.integrations.cdrca.renderer import CdrcaRenderError, CdrcaRenderer


def make_shot(**kw):
    base = dict(shot_id="shot_001", scene_description="A quiet street", characters=["John", "Mary"],
                camera_angle="medium shot", lighting="night", action="John walks and talks", duration_seconds=2.0)
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def cfg(tmp_path):
    fake_script = tmp_path / "cdrca-render.js"
    fake_script.write_text("// fake")
    return {"storage_path": str(tmp_path / "storage"), "cdrca_render_script": str(fake_script),
            "render_fps": 10, "render_width": 640, "render_height": 360}


class TestComposer:
    def test_writes_scene_with_one_sprite_per_character(self, cfg, tmp_path):
        assets = {"John": tmp_path / "john.png", "Mary": tmp_path / "mary.png"}
        path = CdrcaSceneComposer(cfg).compose_shot(make_shot(), assets)
        text = path.read_text()
        assert path.suffix == ".cdrca"
        assert text.startswith('@IMPORT "./atoms.cdrca"')
        assert text.count("use Picture(") == 3                      # two characters and the backdrop; the prop comes from atoms.cdrca, not the language
        assert "as backdrop" in text and text.count("as c_") == 2
        assert "ImageProp" not in text and "SpriteProp" not in text
        assert (path.parent / "atoms.cdrca").read_text() == (Path(__file__).resolve().parent.parent / "src/integrations/cdrca/atoms.cdrca").read_text()
        assert "def ACTION main c_John" in text and "def ACTION main c_Mary" in text

    def test_missing_asset_raises(self, cfg, tmp_path):
        with pytest.raises(CdrcaComposeError):
            CdrcaSceneComposer(cfg).compose_shot(make_shot(), {"John": tmp_path / "john.png"})

    def test_motion_follows_action_keywords(self, cfg, tmp_path):
        c = CdrcaSceneComposer(cfg)
        a = {"John": tmp_path / "j.png"}
        assert "moveTo" in c.compose_shot(make_shot(characters=["John"], action="he walks away"), a).read_text()
        assert "hop 0.12" in c.compose_shot(make_shot(characters=["John"], action="she says hello"), a).read_text()
        assert 'modifyMesh ""' in c.compose_shot(make_shot(characters=["John"], action="stands still"), a).read_text()

    def test_duplicate_names_get_unique_identifiers(self, cfg, tmp_path):
        assets = {"A B": tmp_path / "a.png", "A_B": tmp_path / "b.png"}
        text = CdrcaSceneComposer(cfg).compose_shot(make_shot(characters=["A B", "A_B"]), assets).read_text()
        assert "as c_A_B\n" in text and "as c_A_B_2\n" in text


    def test_picture_size_follows_the_image(self, cfg, tmp_path):
        from PIL import Image
        Image.new("RGBA", (200, 400)).save(tmp_path / "tall.png")
        text = CdrcaSceneComposer(cfg).compose_shot(make_shot(characters=["John"], camera_angle="medium shot"), {"John": tmp_path / "tall.png"}).read_text()
        line = [l for l in text.splitlines() if l.startswith("use Picture(") and " as c_John" in l][0]
        args = line[len("use Picture("):line.index(") as")].split(", ")
        w, h = float(args[3]), float(args[4])
        assert abs(w / h - 0.5) < 0.01


class TestBackdrops:
    @pytest.mark.parametrize("scene,lighting,action,expected", [
        ("A rainy night on a city street", "night rain", "", ("street", "night_rain")),
        ("Inside the old warehouse, boxes stacked", "dim warehouse light", "", ("warehouse", "dim")),
        ("The beach at sunset", "golden sunset", "", ("beach", "sunset")),
        ("A quiet kitchen at dawn", "natural daylight", "", ("room", "day")),
        ("A snowy forest path", "overcast", "", ("forest", "snow")),
        ("The office after midnight, snow outside", "", "", ("office", "night_snow")),
        ("Thunder over the park", "", "", ("forest", "storm")),
        ("Somewhere", "", "", ("street", "day")),                    # nothing matched: a street by day
    ])
    def test_place_and_mood_come_from_the_shots_words(self, scene, lighting, action, expected):
        from src.core.scene_composer.cdrca_composer import _backdrop_for
        assert _backdrop_for(make_shot(scene_description=scene, lighting=lighting, action=action)) == expected

    def test_the_backdrop_picture_is_drawn_and_used(self, cfg, tmp_path):
        from PIL import Image
        c = CdrcaSceneComposer(cfg)
        path = c.compose_shot(make_shot(scene_description="The beach at sunset", characters=[]), {})
        text = path.read_text()
        assert 'use Picture("backdrops/beach_sunset.png", 0, 0,' in text and ", -1, 0," in text
        assert Image.open(c.scenes_dir / "backdrops" / "beach_sunset.png").size == (1920, 1080)
        assert 'def ACTION main backdrop modifyMesh ""' in text

    def test_without_blazes_art_there_is_simply_no_backdrop(self, cfg, monkeypatch):
        from src.core.scene_composer import cdrca_composer
        monkeypatch.setattr(cdrca_composer, "_blaze_art", lambda: None)
        text = CdrcaSceneComposer(cfg).compose_shot(make_shot(characters=[]), {}).read_text()
        assert "backdrop" not in text


class TestRendererErrors:
    def test_missing_script_is_a_setup_error(self, tmp_path):
        r = CdrcaRenderer({"storage_path": str(tmp_path), "cdrca_render_script": str(tmp_path / "nope.js")})
        with pytest.raises(CdrcaRenderError) as e:
            r.render_shot(tmp_path / "s.cdrca", "s")
        assert e.value.stage == "setup"

    def test_structured_transpile_error_is_preserved(self, cfg, tmp_path):
        scene = tmp_path / "s.cdrca"
        scene.write_text("x")
        proc = subprocess.CompletedProcess([], 1, "", json.dumps({"ok": False, "stage": "transpile", "message": "Unexpected token"}) + "\n")
        with patch("shutil.which", return_value="/usr/bin/node"), patch("subprocess.run", return_value=proc):
            with pytest.raises(CdrcaRenderError) as e:
                CdrcaRenderer(cfg).render_shot(scene, "shot_001")
        assert e.value.stage == "transpile" and "Unexpected token" in str(e.value)

    def test_builds_expected_command(self, cfg, tmp_path):
        scene = tmp_path / "s.cdrca"
        scene.write_text("x")
        renderer = CdrcaRenderer(cfg)

        def fake_run(cmd, **kw):
            out = Path(cmd[cmd.index("--out") + 1])
            for i in range(20):
                (out / f"{i:06d}.png").write_bytes(b"png")
            return subprocess.CompletedProcess(cmd, 0, "{}", "")

        with patch("shutil.which", return_value="/usr/bin/node"), patch("subprocess.run", side_effect=fake_run) as run:
            frames = renderer.render_shot(scene, "shot 001", duration_seconds=2.0)
        cmd = run.call_args[0][0]
        assert len(frames) == 20 and cmd[cmd.index("--fps") + 1] == "10"
        assert cmd[cmd.index("--from") + 1] == "1.5"


_BUNDLED = Path(__file__).resolve().parents[2] / "cdrca" / "Back-end" / "Render" / "render.js"
REAL = os.environ.get("BLAZENG_CDRCA_RENDER") or (str(_BUNDLED) if _BUNDLED.exists() else None)
real_ok = bool(REAL) and Path(REAL).exists() and shutil.which("node") and shutil.which("ffmpeg")


@pytest.mark.skipif(not real_ok, reason="needs node + playwright/Chromium + ffmpeg (run: python blaze.py doctor)")
def test_end_to_end_compose_render_assemble(tmp_path):
    from PIL import Image, ImageDraw
    from src.integrations.ffmpeg.video_assembler import VideoAssembler  # existing BlazEng module

    assets = {}
    for name, col in (("John", (230, 80, 60, 255)), ("Mary", (60, 140, 230, 255))):
        im = Image.new("RGBA", (300, 600), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.ellipse((90, 20, 210, 140), fill=col)
        d.rectangle((70, 150, 230, 450), fill=col)
        p = tmp_path / f"{name}.png"
        im.save(p)
        assets[name] = p

    config = {"storage_path": str(tmp_path / "storage"), "cdrca_render_script": REAL,
              "render_fps": 8, "render_width": 480, "render_height": 270}
    shot = make_shot(duration_seconds=2.0)
    scene = CdrcaSceneComposer(config).compose_shot(shot, assets)
    frames = CdrcaRenderer(config).render_shot(scene, shot.shot_id, duration_seconds=shot.duration_seconds)
    assert len(frames) == 16
    assert len({f.read_bytes() for f in frames}) > 4  # frames actually differ (it's animated)
    mp4 = VideoAssembler(config).assemble({shot.shot_id: frames})
    assert Path(mp4).exists() and Path(mp4).stat().st_size > 0
