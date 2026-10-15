"""
Blaze UI: one quiet page in your browser. Write a screenplay on the left, see it understood on the right, press Make video.

    python blaze.py ui            # opens http://127.0.0.1:8765

Nothing but the standard library is used. The page talks to this small local server (127.0.0.1 only, never the network):
it checks the screenplay as you type, runs the same pipeline as `blaze make` in a background thread, and serves the result.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import threading
import time
import uuid
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Optional

from .pipeline import REPO, BlazeError, Options, make
from . import voice as voice_mod
from .screenplay import ScreenplayError, cast_label, parse
from .voice import estimate_seconds

ASSETS = Path(__file__).resolve().parent / "ui_assets"
SAMPLE = REPO / "tests" / "fixtures" / "sample_story.txt"
BYE_GRACE = 10          # seconds after the page says it is closing before an auto-exit app stops
SILENT_LIMIT = 300      # seconds without any ping (a hidden tab may be throttled to one a minute)
NEVER_OPENED_LIMIT = 300  # seconds to wait for a first page when nobody has opened it
RESOLUTIONS = {"fast": (640, 360, 12), "standard": (960, 540, 20), "hd": (1280, 720, 24), "full": (1920, 1080, 30)}


class Job:
    def __init__(self, work: Path):
        self.id = uuid.uuid4().hex[:10]
        self.work = work
        self.state = "running"            # running | done | error
        self.message = "Starting"
        self.scenes_total = 0
        self.scenes_done = 0
        self.error = ""
        self.video: Optional[Path] = None
        self.srt: Optional[Path] = None
        self.seconds = 0.0
        self.notes: list = []
        self.voice = ""                     # which voice engine was used ("silent" when none was found)

    def progress(self, line: str) -> None:
        line = line.strip()
        m = re.match(r"Rendering (\d+) scene", line)
        if m:
            self.scenes_total = int(m.group(1)); self.message = "Drawing scenes"
        elif line.startswith("done:"):
            self.scenes_done += 1; self.message = f"Drawing scenes ({self.scenes_done} of {self.scenes_total})"
        elif line.startswith("Voice:"):
            self.message = "Recording voices"
            self.voice = line[len("Voice:"):].strip()
        elif line.startswith("note:"):
            self.notes.append(line[5:].strip())

    def public(self) -> dict:
        total = max(1, self.scenes_total)
        pct = 0.08 if not self.scenes_total else 0.15 + 0.8 * self.scenes_done / total
        if self.state == "done":
            pct = 1.0
        d = {"id": self.id, "state": self.state, "message": self.message, "progress": round(pct, 3), "notes": self.notes, "voice": self.voice}
        if self.state == "error":
            d["error"] = self.error
        if self.state == "done":
            d.update(video=f"/media/{self.id}/video.mp4", srt=f"/media/{self.id}/subtitles.srt" if self.srt else "", seconds=round(self.seconds, 1))
        return d


class App:
    def __init__(self, workdir: Path, library: Optional[Path] = None):
        self.workdir = workdir
        self.library = library
        self.jobs: Dict[str, Job] = {}
        self._voices: Optional[list] = None
        self.lock = threading.Lock()
        self.busy: Optional[str] = None
        self.started = time.time()
        self.last_ping: Optional[float] = None     # the open page pings every few seconds
        self.exit_at: Optional[float] = None       # set when the page says it is closing

    def ping(self, bye: bool = False) -> None:
        now = time.time()
        self.last_ping = now
        self.exit_at = now + BYE_GRACE if bye else None     # a reload pings again within the grace and cancels it

    def should_exit(self, now: Optional[float] = None) -> bool:
        """For the installed app: stop when the page was closed (or went silent) and no video is being made."""
        now = now or time.time()
        if self.busy and self.jobs[self.busy].state == "running":
            return False
        if self.exit_at is not None and now >= self.exit_at:
            return True
        if self.last_ping is not None:
            return now - self.last_ping > SILENT_LIMIT
        return now - self.started > NEVER_OPENED_LIMIT

    # ------------------------------------------------------------------ checking
    def check(self, text: str) -> dict:
        try:
            sp = parse(text)
        except ScreenplayError as e:
            m = re.match(r"line (\d+): (.*)", str(e))
            return {"ok": False, "error": m.group(2) if m else str(e), "line": int(m.group(1)) if m else 0}
        scenes, seconds = [], 0.0
        for sc in sp.scenes:
            lines = sum(1 for b in sc.beats if b.kind in ("say", "narr"))
            for b in sc.beats:
                if b.kind in ("say", "narr"):
                    seconds += estimate_seconds(b.text) + 0.4
                elif b.kind == "pause":
                    seconds += b.nums[0]
                elif b.kind in ("enter", "exit", "move", "hop"):
                    seconds += 1.0
            scenes.append({"heading": sc.heading or "Untitled", "backdrop": sc.backdrop or "gen:street:day", "lines": lines})
        warnings = []
        for w in sp.warnings:
            m = re.match(r"line (\d+): (.*)", w)
            warnings.append({"line": int(m.group(1)) if m else 0, "text": m.group(2) if m else w})
        people = sp.characters() + (["Narrator"] if any(b.kind == "narr" for sc in sp.scenes for b in sc.beats) and "Narrator" not in sp.characters() else [])
        voices = {c: {"label": cast_label(c), "voice": sp.speech.get(c, {}).get("voice", "auto"), "rate": sp.speech.get(c, {}).get("rate", 0),
                      "pitch": sp.speech.get(c, {}).get("pitch", -1)} for c in people}
        return {"ok": True, "title": sp.title, "cast": sp.characters(), "scenes": scenes, "warnings": warnings,
                "seconds": round(seconds + 3.2), "voices": voices, "looks": sorted(sp.looks)}

    # ------------------------------------------------------------------ voices
    def voices(self) -> dict:
        """The engines and voices installed on this computer (listing them can be slow, so it is done once)."""
        if self._voices is None:
            self._voices = voice_mod.engines_info()
        return {"engines": self._voices}

    def preview(self, spec: str, text: str, gender: str, rate: int, pitch: int) -> dict:
        """Speak a sample line with one voice and return where the page can play it."""
        import hashlib
        text = (text or "Hello there. This is how I sound.").strip()[:200]
        try:
            spec = voice_mod.check_spec(spec)
            key = hashlib.sha1(json.dumps([spec, text, gender, rate, pitch]).encode("utf-8")).hexdigest()[:16]
            out = self.workdir / "previews" / f"{key}.wav"
            out.parent.mkdir(parents=True, exist_ok=True)
            seconds = 0.0
            if out.exists():
                seconds = voice_mod.wav_seconds(out)
            else:
                seconds = voice_mod.preview(text, spec, out, gender=gender if gender in ("m", "f") else "m", rate=rate, pitch=pitch)
        except (ValueError, RuntimeError) as e:
            return {"error": str(e)}
        return {"url": f"/preview/{key}.wav", "seconds": round(seconds, 1)}

    # ------------------------------------------------------------------ making
    def start(self, text: str, quality: str, voice: str) -> dict:
        with self.lock:
            if self.busy and self.jobs[self.busy].state == "running":
                return {"error": "A video is already being made. Wait for it to finish."}
            w, h, fps = RESOLUTIONS.get(quality, RESOLUTIONS["standard"])
            work = self.workdir / uuid.uuid4().hex[:8]
            work.mkdir(parents=True, exist_ok=True)
            job = Job(work)
            self.jobs[job.id] = job
            self.busy = job.id
        opts = Options(width=w, height=h, fps=fps, voice=voice if voice in ("auto", "off") else "auto",
                       library=self.library, progress=job.progress)
        threading.Thread(target=self._run, args=(job, text, opts), daemon=True).start()
        return job.public()

    def _run(self, job: Job, text: str, opts: Options) -> None:
        try:
            job.message = "Reading the screenplay"
            res = make(text, job.work / "video.mp4", opts, job.work / "project", self.library.parent if self.library else None)
            job.video, job.srt, job.seconds = res.video, res.srt, res.duration
            if res.srt:
                shutil.copyfile(res.srt, job.work / "subtitles.srt"); job.srt = job.work / "subtitles.srt"
            job.state, job.message = "done", "Done"
        except (BlazeError, ScreenplayError, RuntimeError, ValueError) as e:
            job.state, job.error = "error", str(e)
        except Exception as e:  # never leave the page waiting
            job.state, job.error = "error", f"Unexpected problem: {e}"

    # ------------------------------------------------------------------ writing with an AI
    # The installed app keeps its config (and so your key) in your own folder: BLAZE_CONFIG points there.
    CONFIG = Path(os.environ.get("BLAZE_CONFIG") or REPO / "studio" / "config.yaml")
    CLOUD = ("anthropic", "gemini", "openai")

    def _ai_config(self) -> dict:
        try:
            import yaml
            return yaml.safe_load(self.CONFIG.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}

    def ai_provider(self) -> str:
        """The provider chosen by the person, or '' when none is chosen yet. There is no default."""
        cfg = self._ai_config()
        provider = str(cfg.get("text_provider") or "").strip().lower()
        if provider in ("ollama", "huggingface"):
            return provider
        if provider in self.CLOUD:
            key = str(cfg.get(f"{provider}_api_key") or "").strip()
            return provider if key and not key.endswith("_HERE") else ""
        return ""

    def ai_available(self) -> bool:
        return bool(self.ai_provider())

    def ai_setup(self, provider: str, key: str) -> dict:
        """Save the person's chosen provider and key into studio/config.yaml (this computer only)."""
        provider, key = provider.strip().lower(), key.strip()
        if provider not in self.CLOUD:
            return {"error": "Choose Anthropic, Gemini or OpenAI."}
        if not key or "\n" in key or len(key) > 400:
            return {"error": "Paste your API key."}
        values = {"text_provider": provider, "vision_provider": provider, f"{provider}_api_key": key}
        if provider != "anthropic":          # Anthropic cannot make images
            values["image_provider"] = provider
        try:
            text = self.CONFIG.read_text(encoding="utf-8") if self.CONFIG.exists() else ""
            for k, v in values.items():
                line = f"{k}: {json.dumps(v)}"
                pattern = re.compile(rf"^{re.escape(k)}:.*$", re.M)
                text = pattern.sub(lambda _m: line, text, count=1) if pattern.search(text) else text.rstrip("\n") + f"\n{line}\n"
            self.CONFIG.write_text(text, encoding="utf-8")
        except OSError as e:
            return {"error": f"Could not save: {e}"}
        return {"ok": True, "provider": provider}

    def ai_write(self, idea: str, whole: bool = False, scenes: int = 4) -> dict:
        """whole=False: one request (cheap). whole=True: outline + one request per scene, each checked."""
        from .ai import write_animation, write_screenplay
        try:
            if whole:
                return {"text": write_animation(idea, scenes=max(2, min(8, int(scenes))))}
            return {"text": write_screenplay(idea)}
        except Exception as e:
            return {"error": f"The AI could not write a usable screenplay: {e}"}


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = "Blaze"

        def log_message(self, *a):
            pass

        def _json(self, obj, status=200):
            body = json.dumps(obj).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if n > 2_000_000:
                return {}
            try:
                return json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return {}

        def _local_only(self) -> bool:
            host = (self.headers.get("Host") or "").split(":")[0]
            return host in ("127.0.0.1", "localhost")

        def do_GET(self):
            if not self._local_only():
                return self._json({"error": "local only"}, 403)
            path = self.path.split("?")[0]
            if path == "/":
                return self._file(ASSETS / "index.html", "text/html; charset=utf-8")
            if path == "/api/ping":
                app.ping()
                return self._json({"ok": True})
            if path == "/api/status":
                return self._json({"ai": app.ai_available(), "provider": app.ai_provider(), "sample": SAMPLE.read_text(encoding="utf-8") if SAMPLE.exists() else ""})
            if path == "/api/voices":
                return self._json(app.voices())
            m = re.fullmatch(r"/preview/([0-9a-f]{16})\.wav", path)
            if m:
                return self._file(app.workdir / "previews" / f"{m.group(1)}.wav", "audio/wav")
            m = re.fullmatch(r"/api/job/(\w+)", path)
            if m:
                job = app.jobs.get(m.group(1))
                return self._json(job.public() if job else {"error": "unknown job"}, 200 if job else 404)
            m = re.fullmatch(r"/media/(\w+)/(video\.mp4|subtitles\.srt)", path)
            if m and m.group(1) in app.jobs:
                f = app.jobs[m.group(1)].work / m.group(2)
                ctype = "video/mp4" if f.suffix == ".mp4" else "text/plain; charset=utf-8"
                return self._file(f, ctype, ranged=f.suffix == ".mp4", download="download=1" in self.path)
            self.send_error(404)

        def do_POST(self):
            if not self._local_only():
                return self._json({"error": "local only"}, 403)
            data = self._body()
            if self.path == "/api/bye":
                app.ping(bye=True)
                return self._json({"ok": True})
            if self.path == "/api/check":
                return self._json(app.check(str(data.get("text", ""))))
            if self.path == "/api/voice-preview":
                def whole(k, default):
                    try:
                        return int(data.get(k, default))
                    except (TypeError, ValueError):
                        return default
                r = app.preview(str(data.get("voice", "")), str(data.get("text", "")), str(data.get("gender", "m")),
                                whole("rate", 0), whole("pitch", -1))
                return self._json(r, 400 if "error" in r else 200)
            if self.path == "/api/make":
                r = app.start(str(data.get("text", "")), str(data.get("quality", "standard")), str(data.get("voice", "auto")))
                return self._json(r, 409 if "error" in r else 200)
            if self.path == "/api/ai/setup":
                r = app.ai_setup(str(data.get("provider", "")), str(data.get("key", "")))
                return self._json(r, 400 if "error" in r else 200)
            if self.path == "/api/ai":
                idea = str(data.get("idea", "")).strip()
                if not idea:
                    return self._json({"error": "Describe the story first."}, 400)
                r = app.ai_write(idea, whole=bool(data.get("whole")), scenes=int(data.get("scenes") or 4))
                return self._json(r, 502 if "error" in r else 200)
            self.send_error(404)

        def _file(self, f: Path, ctype: str, ranged: bool = False, download: bool = False):
            if not f.exists():
                return self.send_error(404)
            size = f.stat().st_size
            start, end, status = 0, size - 1, 200
            rng = self.headers.get("Range")
            if ranged and rng:
                m = re.fullmatch(r"bytes=(\d*)-(\d*)", rng.strip())
                if m:
                    if m.group(1):
                        start = int(m.group(1)); end = int(m.group(2)) if m.group(2) else size - 1
                    elif m.group(2):
                        start = max(0, size - int(m.group(2)))
                    end = min(end, size - 1)
                    status = 206
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            if download:
                self.send_header("Content-Disposition", f'attachment; filename="{f.name}"')
            self.end_headers()
            try:
                with open(f, "rb") as fh:
                    fh.seek(start)
                    left = end - start + 1
                    while left > 0:
                        chunk = fh.read(min(65536, left))
                        if not chunk:
                            break
                        self.wfile.write(chunk); left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass

    return Handler


def serve(port: int = 8765, open_browser: bool = True, workdir: Optional[Path] = None, library: Optional[Path] = None,
          auto_exit: bool = False) -> int:
    workdir = Path(workdir) if workdir else Path.cwd() / "blaze-videos"
    workdir.mkdir(parents=True, exist_ok=True)
    app = App(workdir, library)
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))
    except OSError:
        print(f"Port {port} is already in use (is Blaze already open in another window?). Try: python blaze.py ui --port {port + 1}")
        return 1
    url = f"http://127.0.0.1:{port}"
    print(f"Blaze is open at {url}   (Ctrl+C to stop; videos are kept in {workdir})")
    if auto_exit:        # the installed app: closing the page closes Blaze
        def watch():
            while True:
                time.sleep(2)
                if app.should_exit():
                    server.shutdown()
                    return
        threading.Thread(target=watch, daemon=True).start()
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0
