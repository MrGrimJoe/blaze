"""The Blaze page's local server: checking, provider choice (no default), and that nothing leaks."""
import json
import threading
import urllib.request
from pathlib import Path

import pytest
import yaml

from blaze import ui

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def app(tmp_path, monkeypatch):
    cfg = tmp_path / "config.yaml"
    cfg.write_text((REPO / "studio" / "config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(ui.App, "CONFIG", cfg)
    return ui.App(tmp_path / "videos")


class TestCheck:
    def test_good_screenplay(self, app):
        r = app.check("TITLE: T\nCAST: A gender=f\nSCENE: x\nA: Hello there.\nB: Hi!\n")
        assert r["ok"] and r["title"] == "T" and r["cast"] == ["A", "B"] and r["scenes"][0]["lines"] == 2 and r["seconds"] > 3

    def test_error_names_the_line_and_the_fix(self, app):
        r = app.check("A: hi\n[ENTER A left]\n")
        assert not r["ok"] and r["line"] == 2 and "exact number" in r["error"]

    def test_empty_screenplay_is_an_error_not_a_crash(self, app):
        assert app.check("TITLE: nothing")["ok"] is False


class TestNoDefaultProvider:
    def test_nothing_is_chosen_out_of_the_box(self, app):
        assert app.ai_provider() == "" and app.ai_available() is False

    def test_the_shipped_config_has_no_provider_and_no_key(self):
        cfg = yaml.safe_load((REPO / "studio" / "config.yaml").read_text(encoding="utf-8"))
        assert not cfg["text_provider"] and not cfg["vision_provider"] and not cfg["image_provider"]
        assert all(not str(v).strip() for k, v in cfg.items() if k.endswith("api_key") or k == "hf_token")

    @pytest.mark.parametrize("provider", ["anthropic", "gemini", "openai"])
    def test_choosing_one_of_the_three(self, app, provider):
        assert app.ai_setup(provider, " my-key ") == {"ok": True, "provider": provider}
        assert app.ai_provider() == provider
        cfg = yaml.safe_load(app.CONFIG.read_text(encoding="utf-8"))
        assert cfg["text_provider"] == cfg["vision_provider"] == provider and cfg[f"{provider}_api_key"] == "my-key"
        assert cfg["image_provider"] == ("" if provider == "anthropic" else provider)   # Claude cannot make images
        assert cfg["render_fps"] == 24                                                   # the rest of the file is untouched
        assert "# " in app.CONFIG.read_text(encoding="utf-8")                            # comments are kept

    @pytest.mark.parametrize("provider,key", [("", "k"), ("bogus", "k"), ("gemini", ""), ("gemini", "a\nb"), ("ollama", "k")])
    def test_bad_choices_are_refused_and_change_nothing(self, app, provider, key):
        before = app.CONFIG.read_text(encoding="utf-8")
        assert "error" in app.ai_setup(provider, key)
        assert app.CONFIG.read_text(encoding="utf-8") == before and app.ai_provider() == ""

    def test_a_provider_without_a_key_is_not_available(self, app):
        app.CONFIG.write_text(app.CONFIG.read_text(encoding="utf-8").replace('text_provider: ""', 'text_provider: "gemini"'), encoding="utf-8")
        assert app.ai_available() is False


@pytest.fixture
def server(app):
    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer(("127.0.0.1", 0), ui.make_handler(app))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown(); srv.server_close()


def _post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


class TestServer:
    def test_page_and_status(self, server):
        html = urllib.request.urlopen(server + "/").read().decode()
        assert "<title>Blaze</title>" in html and "gemini" not in html.lower().replace('value="gemini"', "").replace("google gemini", "")
        status = json.loads(urllib.request.urlopen(server + "/api/status").read())
        assert status["ai"] is False and status["provider"] == ""

    def test_check_endpoint(self, server):
        code, r = _post(server + "/api/check", {"text": "A: hi\nB: yo\n"})
        assert code == 200 and r["ok"]

    def test_setup_endpoint_validates(self, server):
        assert _post(server + "/api/ai/setup", {"provider": "nope", "key": "k"})[0] == 400
        assert _post(server + "/api/ai/setup", {"provider": "openai", "key": "k"})[0] == 200
        assert json.loads(urllib.request.urlopen(server + "/api/status").read())["provider"] == "openai"

    def test_only_local_hosts_are_served(self, server):
        req = urllib.request.Request(server + "/api/status", headers={"Host": "evil.example"})
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req)
        assert e.value.code == 403


class TestHeartbeatAndVoice:
    def test_the_page_pings_and_says_goodbye(self, server):
        assert json.loads(urllib.request.urlopen(server + "/api/ping").read()) == {"ok": True}
        assert _post(server + "/api/bye", {}) == (200, {"ok": True})

    def test_a_job_reports_which_voice_was_used(self, tmp_path):
        j = ui.Job(tmp_path)
        assert j.public()["voice"] == ""
        j.progress("Voice: espeak-ng")
        assert j.public()["voice"] == "espeak-ng"
        j.progress("Voice: silent")
        assert j.public()["voice"] == "silent"

    def test_the_page_warns_when_a_video_has_no_sound(self):
        html = (REPO / "blaze" / "ui_assets" / "index.html").read_text(encoding="utf-8")
        assert "No voice engine was found" in html and "/api/ping" in html and "/api/bye" in html
