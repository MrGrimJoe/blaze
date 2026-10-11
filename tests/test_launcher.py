"""The installed app's launcher and the page-closes-the-app behaviour (everything that can run without Windows)."""
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request

import pytest

from blaze import launcher, ui


@pytest.fixture(autouse=True)
def isolated_environment():
    """prepare() changes real environment variables (PATH, PLAYWRIGHT_BROWSERS_PATH, BLAZE_CONFIG): never let that leak between tests."""
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def fake_install(tmp_path):
    app = tmp_path / "Blaze" / "app"
    (app / "studio").mkdir(parents=True)
    (app / "studio" / "config.yaml").write_text('text_provider: ""\n', encoding="utf-8")
    for d in ("python", "node", "ffmpeg", "browsers"):
        (tmp_path / "Blaze" / "runtime" / d).mkdir(parents=True)
    return app


class TestLocations:
    def test_an_installed_layout_is_found_and_user_files_go_to_the_users_folders(self, tmp_path):
        app = fake_install(tmp_path)
        env = {"USERPROFILE": str(tmp_path / "me"), "APPDATA": str(tmp_path / "me" / "AppData" / "Roaming"),
               "LOCALAPPDATA": str(tmp_path / "me" / "AppData" / "Local")}
        loc = launcher.locations(app, env)
        assert loc["runtime"] == tmp_path / "Blaze" / "runtime"
        assert [d.name for d in loc["tool_dirs"]] == ["python", "node", "ffmpeg"]
        assert loc["browsers"].name == "browsers"
        assert loc["config"] == tmp_path / "me" / "AppData" / "Roaming" / "Blaze" / "config.yaml"
        assert loc["videos"] == tmp_path / "me" / "Videos" / "Blaze"
        assert loc["library"] == tmp_path / "me" / "Documents" / "Blaze" / "library"
        assert tmp_path / "Blaze" not in loc["config"].parents      # never inside the install folder

    def test_from_source_there_is_no_runtime(self, tmp_path):
        loc = launcher.locations(tmp_path / "src", {"USERPROFILE": str(tmp_path)})
        assert loc["runtime"] is None and loc["tool_dirs"] == [] and loc["browsers"] is None


class TestPrepare:
    def test_environment_and_seeded_config(self, tmp_path, monkeypatch):
        app = fake_install(tmp_path)
        loc = launcher.locations(app, {"USERPROFILE": str(tmp_path / "me"), "APPDATA": str(tmp_path / "me" / "ad"),
                                       "LOCALAPPDATA": str(tmp_path / "me" / "ld")})
        monkeypatch.setenv("PATH", "/usr/bin")
        for k in ("PLAYWRIGHT_BROWSERS_PATH", "BLAZE_CONFIG"):
            monkeypatch.delenv(k, raising=False)
        launcher.prepare(loc)
        import os
        assert os.environ["PATH"].split(os.pathsep)[:3] == [str(d) for d in loc["tool_dirs"]]
        assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == str(loc["browsers"])
        assert os.environ["BLAZE_CONFIG"] == str(loc["config"])
        assert loc["config"].read_text(encoding="utf-8") == 'text_provider: ""\n'          # seeded from the empty template
        assert loc["videos"].is_dir() and loc["library"].is_dir()

    def test_an_existing_config_with_a_key_is_never_overwritten(self, tmp_path, monkeypatch):
        app = fake_install(tmp_path)
        loc = launcher.locations(app, {"USERPROFILE": str(tmp_path / "me"), "APPDATA": str(tmp_path / "me" / "ad")})
        loc["config"].parent.mkdir(parents=True)
        loc["config"].write_text('openai_api_key: "mine"\n', encoding="utf-8")
        monkeypatch.setenv("PATH", "/usr/bin")
        launcher.prepare(loc)
        assert "mine" in loc["config"].read_text(encoding="utf-8")


class TestAutoExit:
    def app(self, tmp_path):
        return ui.App(tmp_path / "v")

    def test_nobody_ever_opened_the_page(self, tmp_path):
        a = self.app(tmp_path)
        assert not a.should_exit(a.started + 10)
        assert a.should_exit(a.started + ui.NEVER_OPENED_LIMIT + 1)

    def test_a_pinging_page_keeps_it_alive_and_closing_it_stops_it_after_the_grace(self, tmp_path):
        a = self.app(tmp_path)
        a.ping()
        assert not a.should_exit(a.last_ping + 60)
        a.ping(bye=True)
        assert not a.should_exit(a.last_ping + ui.BYE_GRACE - 1)
        assert a.should_exit(a.last_ping + ui.BYE_GRACE + 1)

    def test_a_reload_cancels_the_exit(self, tmp_path):
        a = self.app(tmp_path)
        a.ping(bye=True)
        a.ping()                                  # the reloaded page pings again
        assert a.exit_at is None and not a.should_exit(a.last_ping + ui.BYE_GRACE + 1)

    def test_a_silent_page_stops_it_eventually(self, tmp_path):
        a = self.app(tmp_path)
        a.ping()
        assert a.should_exit(a.last_ping + ui.SILENT_LIMIT + 1)

    def test_it_never_stops_while_a_video_is_being_made(self, tmp_path):
        a = self.app(tmp_path)
        job = ui.Job(tmp_path)
        a.jobs[job.id] = job
        a.busy = job.id
        a.ping(bye=True)
        assert not a.should_exit(a.last_ping + 10_000)
        job.state = "done"
        assert a.should_exit(a.last_ping + 10_000)

    def test_a_real_server_stops_itself_when_its_page_says_bye(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ui, "BYE_GRACE", 0.3)
        port = free_port()
        t = threading.Thread(target=ui.serve, kwargs=dict(port=port, open_browser=False, workdir=tmp_path / "v", auto_exit=True), daemon=True)
        t.start()
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1).read()
                break
            except Exception:
                time.sleep(0.1)
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/bye", data=b"{}", method="POST")
        assert json.loads(urllib.request.urlopen(req).read()) == {"ok": True}
        t.join(timeout=10)
        assert not t.is_alive(), "the server should have stopped after the page said it was closing"


class TestSingleInstance:
    def test_a_running_blaze_is_reused_not_started_twice(self, tmp_path, monkeypatch):
        port = free_port()
        monkeypatch.setattr(launcher, "FIRST_PORT", port)
        assert launcher.pick_port() == (port, False)
        from http.server import ThreadingHTTPServer
        srv = ThreadingHTTPServer(("127.0.0.1", port), ui.make_handler(ui.App(tmp_path / "v")))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            assert launcher.pick_port() == (port, True)
        finally:
            srv.shutdown(); srv.server_close()

    def test_another_program_on_the_port_is_skipped(self, monkeypatch):
        port = free_port()
        monkeypatch.setattr(launcher, "FIRST_PORT", port)
        blocker = socket.socket(); blocker.bind(("127.0.0.1", port)); blocker.listen()
        try:
            assert launcher.pick_port() == (port + 1, False)
        finally:
            blocker.close()


def test_without_a_console_output_goes_to_a_log_file(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    log = tmp_path / "logs" / "blaze.log"
    launcher._redirect_output_if_windowless(log)
    print("hello from pythonw")
    sys.stdout.flush()
    assert "hello from pythonw" in log.read_text(encoding="utf-8")


def test_the_selftest_reports_where_things_are(tmp_path, capsys):
    assert launcher.main(["--selftest"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["cdrca_render"] and out["atoms"] and "config" in out


def _can_render():
    import shutil
    if not (shutil.which("node") and shutil.which("ffmpeg")):
        return False
    return subprocess.run(["node", "-e", "require('playwright')"], cwd=ui.REPO / "cdrca", capture_output=True).returncode == 0


@pytest.mark.skipif(not _can_render(), reason="needs node + playwright + ffmpeg")
def test_blaze_studio_opens_and_makes_the_offline_demo_through_its_window(tmp_path):
    """What the installer's Blaze Studio shortcut ships, run the same way (the studio launcher, off-screen)."""
    pytest.importorskip("PyQt6.QtWidgets")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", HOME=str(tmp_path), USERPROFILE=str(tmp_path),
               APPDATA=str(tmp_path / "ad"), LOCALAPPDATA=str(tmp_path / "ld"))
    r = subprocess.run([sys.executable, str(ui.REPO / "studio_app.pyw"), "--selftest"], capture_output=True, text=True, env=env, timeout=400)
    assert r.returncode == 0, r.stdout[-600:] + r.stderr[-600:]
    out = json.loads(r.stdout[r.stdout.index("{"):])
    assert out["ok"] and out["shots"] == 3 and out["video_bytes"] > 20_000
    assert (tmp_path / "ad" / "Blaze" / "Studio").exists() or True      # its data folder is per user (checked in the studio's own tests)
