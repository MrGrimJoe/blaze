"""The page's library panel (your own characters and backdrops) and the data the Running mode draws."""
import io
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from PIL import Image

from blaze import blender as bl
from blaze import ui
from blaze.library import Library

REPO = Path(__file__).resolve().parent.parent


def png(alpha=True, size=(40, 72)) -> bytes:
    im = Image.new("RGBA", size, (200, 30, 30, 255 if not alpha else 0))
    if alpha:
        for x in range(10, 30):
            for y in range(10, 60):
                im.putpixel((x, y), (200, 30, 30, 255))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)                                  # never write a library into the repository
    return ui.App(tmp_path / "videos", tmp_path / "library")


class TestLibraryAdd:
    def test_a_transparent_png_becomes_a_character(self, app):
        r = app.library_add("character", "Robo Boy", "robo.png", png())
        assert r == {"ok": True, "name": "robo_boy", "files": ["robo_boy.png"]}
        info = app.library_info()
        assert [c["name"] for c in info["characters"]] == ["robo_boy"]
        assert info["characters"][0]["transparent"] is True and info["characters"][0]["talk"] is False

    def test_the_name_defaults_to_the_file_name(self, app):
        assert app.library_add("character", "", "Zed.PNG", png())["name"] == "zed"

    def test_a_picture_without_transparency_gets_a_warning_not_a_refusal(self, app):
        r = app.library_add("character", "box", "box.png", png(alpha=False))
        assert r["ok"] and "transparent" in r["warning"]

    def test_the_talking_picture_goes_next_to_its_character(self, app):
        assert "error" in app.library_add("character", "robo", "r_talk.png", png(), variant="talk")      # no character yet
        app.library_add("character", "robo", "robo.png", png())
        assert app.library_add("character", "robo", "r_talk.png", png(), variant="talk")["ok"]
        assert app.library_info()["characters"][0]["talk"] is True
        assert "error" in app.library_add("character", "robo", "x.png", png(), variant="wave")

    def test_a_backdrop_is_cropped_to_16_by_9(self, app):
        assert app.library_add("backdrop", "lab", "lab.png", png(size=(300, 300)))["ok"]
        assert Image.open(app.library_file("backdrops", "lab")).size == (1920, 1080)
        assert [b["name"] for b in app.library_info()["backdrops"]] == ["lab"]

    @pytest.mark.parametrize("kind,filename,data", [("character", "notes.txt", b"hello"), ("character", "x.png", b"not a picture"),
                                                    ("character", "x.png", b""), ("sprite", "x.png", b"1")])
    def test_bad_uploads_are_refused_and_nothing_is_added(self, app, kind, filename, data):
        assert "error" in app.library_add(kind, "x", filename, data)
        assert app.library_info()["characters"] == []

    def test_a_huge_file_is_refused(self, app, monkeypatch):
        monkeypatch.setattr(ui.App, "IMAGE_LIMIT", 10)
        assert "limit" in app.library_add("character", "x", "x.png", png())["error"]

    def test_uploads_do_not_leave_temporary_files(self, app):
        app.library_add("character", "robo", "robo.png", png())
        assert not list((app.workdir / "uploads").glob("*/*"))


class TestBlendFiles:
    def test_without_blender_the_error_says_what_to_do(self, app, monkeypatch):
        monkeypatch.setattr(bl, "find_blender", lambda explicit=None: None)
        r = app.library_add("character", "robo", "robo.blend", b"BLENDER-v400")
        assert "Blender was not found" in r["error"] and "PNG" in r["error"]

    def test_with_blender_the_model_is_rendered_into_sprites(self, app, monkeypatch):
        calls = []

        def fake_sprites(blend, out_dir, name, size, samples, yaw, blender):
            calls.append((Path(blend).suffix, name, size))
            out = []
            for suffix in ("", "_talk", "_blink"):
                p = Path(out_dir) / f"{name}{suffix}.png"
                p.write_bytes(png()); out.append(p)
            return out
        monkeypatch.setattr(bl, "find_blender", lambda explicit=None: Path("/fake/blender"))
        monkeypatch.setattr(bl, "render_sprites", fake_sprites)
        r = app.library_add("character", "Robo", "robo.blend", b"BLENDER-v400")
        assert r["ok"] and r["files"] == ["robo.png", "robo_talk.png", "robo_blink.png"] and calls == [(".blend", "robo", (400, 720))]
        c = app.library_info()["characters"][0]
        assert c["talk"] and c["blink"]

    def test_a_blender_failure_is_reported_not_raised(self, app, monkeypatch):
        def boom(*a, **k):
            raise bl.BlenderError("no mesh in the file")
        monkeypatch.setattr(bl, "find_blender", lambda explicit=None: Path("/fake/blender"))
        monkeypatch.setattr(bl, "render_sprites", boom)
        r = app.library_add("character", "robo", "robo.blend", b"BLENDER-v400")
        assert "Blender could not render" in r["error"] and "no mesh" in r["error"]
        assert app.library_info()["characters"] == []

    def test_a_blend_has_no_talk_variant(self, app, monkeypatch):
        monkeypatch.setattr(bl, "find_blender", lambda explicit=None: Path("/fake/blender"))
        assert "shape keys" in app.library_add("character", "robo", "r.blend", b"x", variant="talk")["error"]


class TestLibraryRemoveAndUse:
    def test_remove_takes_the_mouth_pictures_too(self, app):
        app.library_add("character", "robo", "robo.png", png())
        app.library_add("character", "robo", "t.png", png(), variant="talk")
        r = app.library_remove("character", "robo")
        assert r["ok"] and sorted(r["removed"]) == ["robo.png", "robo_talk.png"]
        assert app.library_info()["characters"] == [] and "error" in app.library_remove("character", "robo")

    def test_remove_cannot_leave_the_library_folder(self, app, tmp_path):
        (tmp_path / "keep.png").write_bytes(png())
        assert "error" in app.library_remove("character", "../keep")
        assert (tmp_path / "keep.png").exists()

    def test_the_check_reports_a_missing_character_on_its_own_line(self, app):
        text = "CAST: MARY gender=f\nCAST: ROBO asset=robo\nSCENE: x\nROBO: hi\nMARY: hello\n"
        r = app.check(text)
        assert not r["ok"] and r["line"] == 2 and "no character 'robo'" in r["error"]
        app.library_add("character", "robo", "robo.png", png())
        assert app.check(text)["ok"]


class TestTimeline:
    def test_scenes_and_lines_sit_on_the_videos_own_clock(self, tmp_path):
        project = tmp_path / "p"
        project.mkdir()
        (project / "project.json").write_text(json.dumps({"fps": 10, "title": "T", "shots": [
            {"name": "title", "duration": 3.2, "title": True, "mood": "", "subs": []},
            {"name": "s1", "duration": 5.0, "mood": "gen:street:day", "subs": [[0.5, 2.0, "john", "Hello."], [2.5, 4.0, "", "Narration."]]},
            {"name": "s2", "duration": 2.04, "mood": "gen:beach:sunset", "subs": [[0.0, 1.0, "mary", "Bye."]]},
        ]}), encoding="utf-8")
        t = ui.App._timeline(project)
        assert [(s["name"], s["start"], s["end"]) for s in t["scenes"]] == [("title", 0, 3.2), ("s1", 3.2, 8.2), ("s2", 8.2, 10.2)]
        assert t["scenes"][0]["title"] is True and t["seconds"] == 10.2
        assert [(l["who"], l["start"], l["end"]) for l in t["lines"]] == [("john", 3.7, 5.2), ("", 5.7, 7.2), ("mary", 8.2, 9.2)]

    def test_a_missing_project_gives_an_empty_timeline(self, tmp_path):
        assert ui.App._timeline(tmp_path / "nothing") == {}

    def test_a_finished_job_carries_its_timeline(self):
        j = ui.Job(Path("."))
        j.state, j.timeline = "done", {"scenes": [], "lines": []}
        assert j.public()["timeline"] == {"scenes": [], "lines": []}


@pytest.fixture
def server(app):
    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer(("127.0.0.1", 0), ui.make_handler(app))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def call(url, data=None, method=None):
    req = urllib.request.Request(url, data=data, method=method or ("POST" if data is not None else "GET"))
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers


class TestLibraryOverHttp:
    def test_upload_list_fetch_picture_remove(self, server):
        s, body, _ = call(server + "/api/library/add?kind=character&name=robo&filename=robo.png", png())
        assert s == 200 and json.loads(body)["name"] == "robo"
        s, body, _ = call(server + "/api/library")
        info = json.loads(body)
        assert s == 200 and info["characters"][0]["url"] == "/api/library/img/characters/robo.png" and "blender" in info
        s, body, h = call(server + info["characters"][0]["url"])
        assert s == 200 and h["Content-Type"] == "image/png" and Image.open(io.BytesIO(body)).size == (40, 72)
        s, body, _ = call(server + "/api/library/remove", json.dumps({"kind": "character", "name": "robo"}).encode())
        assert s == 200
        assert call(server + "/api/library/img/characters/robo.png")[0] == 404

    def test_a_bad_upload_is_a_400_with_a_message(self, server):
        s, body, _ = call(server + "/api/library/add?kind=character&name=x&filename=x.exe", b"MZ")
        assert s == 400 and "not a PNG" in json.loads(body)["error"]

    def test_picture_urls_cannot_escape_the_library(self, server):
        for bad in ("/api/library/img/characters/..%2f..%2fetc%2fpasswd.png", "/api/library/img/characters/../x.png", "/api/library/img/secrets/x.png"):
            assert call(server + bad)[0] == 404

    def test_the_library_is_local_only(self, server):
        req = urllib.request.Request(server + "/api/library", headers={"Host": "evil.example"})
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req, timeout=5)
        assert e.value.code == 403
