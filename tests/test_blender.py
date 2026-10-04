import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from blaze import blender as bl
from blaze.library import Library, slug
from blaze.pipeline import RENDER_SCRIPT, BlazeError, Options, create_project, make
from blaze.screenplay import parse

HERE = Path(__file__).resolve().parent
HAVE_BLENDER = bl.find_blender() is not None
needs_blender = pytest.mark.skipif(not HAVE_BLENDER, reason="Blender not installed (python blaze.py doctor)")


def png(path, size=(40, 72), color=(200, 40, 40, 255), alpha_hole=True):
    im = Image.new("RGBA", size, color)
    if alpha_hole:
        im.paste((0, 0, 0, 0), (0, 0, size[0], 8))
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path)
    return path


# ----------------------------------------------------------------- locating / running blender (no real Blender needed)
class TestBlenderBridge:
    def test_explicit_path_and_env_win(self, tmp_path, monkeypatch):
        fake = tmp_path / "myblender"; fake.write_text("x")
        assert bl.find_blender(str(fake)) == fake
        monkeypatch.setenv("BLAZE_BLENDER", str(fake))
        assert bl.find_blender() == fake

    @pytest.mark.skipif(sys.platform == "win32", reason="fake executable is a shell script")
    def test_errors_from_the_script_are_surfaced(self, tmp_path):
        fake = tmp_path / "blender"
        fake.write_text("#!/bin/sh\necho 'BLAZE_ERROR no visible mesh objects to render'\nexit 2\n")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        with pytest.raises(bl.BlenderError, match="no visible mesh"):
            bl.run(None, "sprites", ["--out", str(tmp_path)], blender=str(fake))

    @pytest.mark.skipif(sys.platform == "win32", reason="fake executable is a shell script")
    def test_output_files_and_json_are_parsed(self, tmp_path):
        fake = tmp_path / "blender"
        fake.write_text("#!/bin/sh\necho 'noise'\necho 'BLAZE_OUT /x/a.png'\necho 'BLAZE_JSON {\"k\": 1}'\n")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        outs, payload = bl.run(None, "info", [], blender=str(fake))
        assert outs == ["/x/a.png"] and payload == {"k": 1}

    def test_missing_blender_has_an_actionable_message(self, monkeypatch):
        monkeypatch.setattr(bl, "find_blender", lambda explicit=None: None)
        with pytest.raises(bl.BlenderError, match="blender.org"):
            bl.info(Path("x.blend"))


# ----------------------------------------------------------------- library (no Blender needed)
class TestLibrary:
    def test_add_character_keeps_variants_and_lookup_by_slug(self, tmp_path):
        src = png(tmp_path / "in" / "Hero One.png")
        png(tmp_path / "in" / "Hero One_talk.png", color=(40, 200, 40, 255))
        lib = Library([tmp_path / "library"])
        files = lib.add_character(src, "Hero One")
        assert {f.name for f in files} == {"hero_one.png", "hero_one_talk.png"}
        assert lib.character("HERO ONE") == tmp_path / "library" / "characters" / "hero_one.png"
        assert lib.list()["characters"] == ["hero_one"]

    def test_add_backdrop_cover_crops_to_16_9(self, tmp_path):
        src = tmp_path / "wide.jpg"; Image.new("RGB", (1000, 1000), (10, 120, 200)).save(src)
        out = Library([tmp_path / "library"]).add_backdrop(src, "Sky")
        assert Image.open(out).size == (1920, 1080)

    def test_alpha_detection_picks_character_vs_backdrop(self, tmp_path):
        lib = Library([tmp_path])
        assert lib.has_alpha(png(tmp_path / "c.png"))
        flat = tmp_path / "b.png"; Image.new("RGB", (10, 10)).save(flat)
        assert not lib.has_alpha(flat)

    def test_backdrop_by_path_relative_to_the_screenplay(self, tmp_path):
        img = tmp_path / "pics" / "bg.png"; img.parent.mkdir(); Image.new("RGB", (20, 10)).save(img)
        assert Library([tmp_path / "library"]).backdrop("pics/bg.png", tmp_path) == tmp_path / "pics" / "bg.png"

    def test_default_search_order_prefers_explicit_then_script_folder(self, tmp_path):
        lib = Library.default(tmp_path / "mine", tmp_path / "story")
        assert lib.roots[0] == tmp_path / "mine" and lib.roots[1] == tmp_path / "story" / "library"


class TestScreenplayAssets:
    def test_backdrop_directive_and_asset_cast(self):
        sp = parse("CAST: ROBO = asset:robo\nSCENE: lab\nBACKDROP: my_lab\nROBO: hi\n")
        assert sp.scenes[0].backdrop == "my_lab" and sp.cast["Robo"] == "asset:robo"


class TestPipelineWithLibrary:
    def _opts(self, **kw):
        return Options(width=320, height=180, fps=8, voice="off", progress=lambda m: None, **kw)

    def test_library_character_and_backdrop_are_used(self, tmp_path):
        png(tmp_path / "library" / "characters" / "robo.png"); png(tmp_path / "library" / "characters" / "robo_talk.png")
        Image.new("RGB", (64, 36), (0, 90, 200)).save(tmp_path / "library" / "backdrops" / "lab.png") if (tmp_path / "library" / "backdrops").mkdir(parents=True) is None else None
        text = "CAST: ROBO = asset:robo\nSCENE: x\nBACKDROP: lab\nROBO: hi\nMARY: hello\n"
        sp, manifest = create_project(text, tmp_path / "proj", self._opts(library=tmp_path / "library"))
        assets = {p.name for p in (tmp_path / "proj" / "assets").iterdir()}
        assert {"robo.png", "robo_talk.png", "bg_custom_lab.png", "mary.png"} <= assets     # Mary is generated, Robo is yours
        assert Image.open(tmp_path / "proj" / "assets" / "robo.png").getpixel((20, 40)) == (200, 40, 40, 255)
        script = (tmp_path / "proj" / "scenes" / "s01.cdrca").read_text()
        assert "bg_custom_lab.png" in script and "robo_talk.png" in script

    def test_missing_asset_is_a_clear_error(self, tmp_path):
        with pytest.raises(BlazeError, match="asset 'ghost'"):
            create_project("CAST: G = asset:ghost\nSCENE: x\nG: hi\nB: yo\n", tmp_path / "p", self._opts(library=tmp_path / "library"))
        with pytest.raises(BlazeError, match="BACKDROP: 'nowhere'"):
            create_project("SCENE: x\nBACKDROP: nowhere\nA: hi\nB: yo\n", tmp_path / "p2", self._opts(library=tmp_path / "library"))


# ----------------------------------------------------------------- real Blender
@pytest.fixture(scope="module")
def fixtures(tmp_path_factory):
    out = tmp_path_factory.mktemp("blend")
    exe = bl.find_blender()
    r = subprocess.run([str(exe), "-b", "--factory-startup", "-P", str(HERE / "fixtures" / "make_fixtures.py"), "--", str(out)],
                       capture_output=True, text=True, timeout=300)
    assert (out / "robot.blend").exists() and (out / "shot.blend").exists(), r.stdout[-600:] + r.stderr[-600:]
    return out


@needs_blender
class TestRealBlender:
    def test_info(self, fixtures):
        i = bl.info(fixtures / "robot.blend")
        assert i["meshes"] >= 5 and i["has_talk"] and i["has_blink"] and not i["has_camera"]
        assert bl.info(fixtures / "shot.blend")["has_camera"]

    def test_sprites_have_transparency_and_working_variants(self, fixtures, tmp_path):
        files = bl.render_sprites(fixtures / "robot.blend", tmp_path, "robo", samples=8)
        assert [f.name for f in files] == ["robo.png", "robo_talk.png", "robo_blink.png"]
        base, talk, blink = (Image.open(f) for f in files)
        assert base.size == (400, 720) and base.mode == "RGBA"
        assert base.getchannel("A").getextrema()[0] == 0                 # transparent background
        bbox = base.getchannel("A").getbbox()
        assert bbox[3] > 720 * 0.9                                       # feet sit near the bottom edge (Blaze's sprite convention)
        assert bbox[0] > 0 and bbox[2] < 400 and bbox[1] > 0             # nothing is clipped, even for a wide model
        assert base.tobytes() != talk.tobytes() and base.tobytes() != blink.tobytes()   # shape keys changed the picture

    def test_still_from_scene_camera(self, fixtures, tmp_path):
        p = bl.render_still(fixtures / "shot.blend", tmp_path / "bg.png", size=(480, 270), samples=4)
        assert Image.open(p).size == (480, 270)

    def test_a_blend_without_a_camera_cannot_be_a_backdrop(self, fixtures, tmp_path):
        with pytest.raises(bl.BlenderError, match="no active camera"):
            bl.render_still(fixtures / "robot.blend", tmp_path / "x.png", size=(64, 36), samples=1)

    def test_library_add_from_blend(self, fixtures, tmp_path):
        lib = Library([tmp_path / "library"])
        assert {f.name for f in lib.add_character(fixtures / "robot.blend", "Robo", samples=4)} == {"robo.png", "robo_talk.png", "robo_blink.png"}
        assert lib.add_backdrop(fixtures / "shot.blend", "Lab", samples=2, size=(320, 180)).exists()


@pytest.mark.skipif(not (HAVE_BLENDER and RENDER_SCRIPT.exists()), reason="needs Blender + the renderer")
def test_blender_assets_end_to_end(fixtures, tmp_path):
    import shutil
    if not (shutil.which("node") and shutil.which("ffmpeg")):
        pytest.skip("needs node + ffmpeg")
    r = subprocess.run(["node", "-e", "require('playwright')"], cwd=str(RENDER_SCRIPT.parents[2]), capture_output=True)
    if r.returncode != 0:
        pytest.skip("playwright not installed")
    lib = Library([tmp_path / "library"])
    lib.add_character(fixtures / "robot.blend", "robo", samples=4)
    lib.add_backdrop(fixtures / "shot.blend", "lab", samples=2, size=(640, 360))
    res = make("CAST: ROBO = asset:robo\nSCENE: x\nBACKDROP: lab\nROBO: Hello.\nMARY: Hi!\n", tmp_path / "o.mp4",
               Options(width=320, height=180, fps=8, voice="off", library=tmp_path / "library", progress=lambda m: None))
    assert res.video.exists() and res.video.stat().st_size > 1000
