"""
End-to-end check of an installed (or staged) Blaze, the way a person uses it:

  1. start the app exactly as the Start-menu shortcut does (pythonw blaze_app.pyw);
  2. wait for the page, check what it reports (no AI provider chosen, nothing preselected);
  3. choose a provider on the page and prove the key is saved in the person's folder, never in the install folder;
  4. make a real video through the page's own API and fetch it back with a range request, as a player does;
  5. say the page is closing and prove the app stops by itself.

    python installer/smoke_installed.py --python "C:\\...\\runtime\\python\\pythonw.exe" --script "C:\\...\\app\\blaze_app.pyw"

Run from a source checkout to test the script itself:  --python python3 --script blaze_app.pyw --home /tmp/h
Writes smoke-results.json (and prints a table). Exit status 0 only when every check passed.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PORTS = range(8765, 8781)
results: list = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append({"check": name, "ok": bool(ok), "detail": detail})
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   ({detail})" if detail else ""), flush=True)
    if not ok and not name.startswith("a voice engine"):
        annotate("error", "Installed app check", name + (f" -- {detail}" if detail else ""))
    return bool(ok)


def annotate(level: str, title: str, message: str) -> None:
    """On GitHub Actions also say it as an annotation: it is on the run's page and available from the API, which a job log is not."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        text = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::{level} title={title}::{text}", flush=True)


def call(base: str, path: str, body=None, method=None, headers=None, timeout=60):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, method=method or ("POST" if body is not None else "GET"), headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if r.headers.get("Content-Type", "").startswith("application/json") else raw), dict(r.headers)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw), dict(e.headers)
        except ValueError:
            return e.code, raw, dict(e.headers)


# a 1x1 transparent PNG: enough for the library to accept a character without needing Pillow here
TINY_PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")


def upload(base: str, query: str, data: bytes):
    """POST a file as the request body (how the page adds a character to the library)."""
    req = urllib.request.Request(base + "/api/library/add?" + query, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def find_blaze(deadline: float):
    while time.time() < deadline:
        for port in PORTS:
            try:
                s, body, _ = call(f"http://127.0.0.1:{port}", "/api/status", timeout=2)
                if s == 200 and isinstance(body, dict) and "sample" in body:
                    return f"http://127.0.0.1:{port}", body
            except Exception:
                pass
        time.sleep(1)
    return None, None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--python", required=True, help="the Python that runs the app (pythonw.exe when installed)")
    ap.add_argument("--script", required=True, help="path to blaze_app.pyw")
    ap.add_argument("--story", help="screenplay to make (default: the installed example)")
    ap.add_argument("--home", help="use this folder as the user's home (tests); default: the real one")
    ap.add_argument("--quality", default="fast")
    ap.add_argument("--make-timeout", type=int, default=900)
    ap.add_argument("--out", default="smoke-results.json")
    a = ap.parse_args(argv)

    script = Path(a.script).resolve()
    app_dir = script.parent
    env = dict(os.environ)
    env.pop("BLAZE_CONFIG", None)       # the app must choose its own (a PLAYWRIGHT_BROWSERS_PATH from outside is left alone: the app overrides it when it bundles a browser)
    if a.home:
        home = Path(a.home).resolve()
        home.mkdir(parents=True, exist_ok=True)
        env.update(USERPROFILE=str(home), HOME=str(home), APPDATA=str(home / "AppData" / "Roaming"), LOCALAPPDATA=str(home / "AppData" / "Local"))
    story = Path(a.story) if a.story else app_dir / "examples" / "the-warehouse.txt"

    print("Where the app puts things:")
    me = subprocess.run([a.python.replace("pythonw", "python"), "-m", "blaze.launcher", "--selftest"], cwd=app_dir, env=env, capture_output=True, text=True)
    where = json.loads(me.stdout) if me.returncode == 0 else {}
    check("launcher self-test runs", me.returncode == 0, me.stderr.strip()[-200:])
    if where:
        check("bundled node and ffmpeg are found (or on PATH)", bool(where.get("node")) and bool(where.get("ffmpeg")), f"node={where.get('node')} ffmpeg={where.get('ffmpeg')}")
        check("renderer and atoms library are present", where.get("cdrca_render") and where.get("atoms"))
        check("config lives outside the install folder", str(app_dir) not in where["config"], where["config"])

    print("Starting the app like the shortcut does:")
    proc = subprocess.Popen([a.python, str(script)], cwd=app_dir, env=env)
    try:
        base, status = find_blaze(time.time() + 120)
        if not check("the page is served", base is not None, base or "no answer within 120 s"):
            return finish(a.out, proc)
        check("no AI provider is chosen out of the box", status.get("ai") is False and status.get("provider") == "", json.dumps({k: status[k] for k in ('ai', 'provider')}))
        html = call(base, "/")[1].decode("utf-8", "ignore")
        check("the page loads", "<title>Blaze</title>" in html)

        s, r, _ = call(base, "/api/check", {"text": story.read_text(encoding="utf-8")})
        check("the example screenplay checks out", s == 200 and r.get("ok") and len(r["scenes"]) >= 1, f"{len(r.get('scenes', []))} scenes")
        s, r, _ = call(base, "/api/check", {"text": "A: hi\n[ENTER A left]"})
        check("a mistake is reported with its line", s == 200 and r.get("ok") is False and r.get("line") == 2)

        s, r, _ = call(base, "/api/check", {"text": "JOHN: hi\nLater that day: Mary went home\n"})
        check("an undeclared speaker is refused, not turned into a character", s == 200 and r.get("ok") is False and r.get("line") == 2, str(r.get("error", ""))[:80])
        s, r, _ = call(base, "/api/check", {"text": "JOHN: hi\n[MOV JOHN 3]\n"})
        check("a misspelt command is refused with a suggestion", s == 200 and r.get("ok") is False and "did you mean MOVE" in str(r.get("error", "")))

        # the three modes live in the page; the library (your own characters) lives in the person's folder, not the install folder
        check("the page has its three modes", all(f'data-mode="{m}"' in html for m in ("editor", "smart", "running")))
        s, lib, _ = call(base, "/api/library")
        check("the library is in the person's folder, not the install folder", s == 200 and str(app_dir) not in lib.get("home", str(app_dir)), str(lib.get("home")))
        cast = "CAST: SMOKEBOT asset=smoke_bot\nSCENE: x\nSMOKEBOT: hi\n"
        s, r, _ = call(base, "/api/check", {"text": cast})
        check("a character that is not in the library is reported on its line", s == 200 and r.get("ok") is False and r.get("line") == 1 and "smoke_bot" in str(r.get("error", "")), str(r.get("error", ""))[:80])
        s, r = upload(base, "kind=character&name=smoke_bot&filename=smoke_bot.png", TINY_PNG)
        check("a character can be added from the page", s == 200 and r.get("ok"), json.dumps(r)[:120])
        s, r, _ = call(base, "/api/check", {"text": cast})
        check("after adding it the screenplay checks out", s == 200 and r.get("ok"), str(r.get("error", ""))[:80])
        s, r, _ = call(base, "/api/library/remove", {"kind": "character", "name": "smoke_bot"})
        check("and it can be removed again", s == 200 and r.get("ok"), json.dumps(r)[:120])

        # voices: the installed app must offer the system voices (Windows SAPI), play one, and use one for a character
        s, r, _ = call(base, "/api/voices")
        engines = {e["engine"]: e for e in r.get("engines", [])} if s == 200 and isinstance(r, dict) else {}
        pick = ""
        for name in (("pyttsx3", "espeak", "piper") if sys.platform == "win32" else ("espeak", "pyttsx3", "piper")):
            if engines.get(name, {}).get("voices"):
                pick = engines[name]["voices"][0]["id"]
                break
        if sys.platform == "win32":
            sapi = engines.get("pyttsx3", {})
            check("the system (SAPI) voices are listed", bool(sapi.get("available")) and len(sapi.get("voices", [])) >= 1, f"{len(sapi.get('voices', []))} voice(s)")
        if pick:
            s, r, _ = call(base, "/api/voice-preview", {"voice": pick, "text": "Testing one two three."})
            ok = s == 200 and "url" in r
            body = call(base, r["url"])[1] if ok else b""
            check("a chosen voice can be previewed", ok and body[:4] == b"RIFF" and len(body) > 2000, f"{pick}: {len(body)} bytes" if ok else str(r)[:100])
        else:
            print("  (no voice engine on this machine: the voice checks are skipped)")

        cfg = Path(where.get("config", ""))
        s, r, _ = call(base, "/api/ai/setup", {"provider": "bogus", "key": "x"})
        check("an unknown provider is refused", s == 400)
        s, r, _ = call(base, "/api/ai/setup", {"provider": "openai", "key": "sk-smoke-test-not-real"})
        check("choosing a provider works", s == 200 and r.get("ok"))
        saved = cfg.read_text(encoding="utf-8") if cfg.is_file() else ""
        check("the key is saved in the person's own config", "sk-smoke-test-not-real" in saved, str(cfg))
        shipped = (app_dir / "studio" / "config.yaml")
        check("the install folder's config still has no key", not shipped.is_file() or "sk-smoke-test-not-real" not in shipped.read_text(encoding="utf-8"))
        cfg.write_text(saved.replace("sk-smoke-test-not-real", "").replace('text_provider: "openai"', 'text_provider: ""'), encoding="utf-8")   # leave nothing behind

        print("Making a video through the page:")
        s, job, _ = call(base, "/api/make", {"text": story.read_text(encoding="utf-8"), "quality": a.quality, "voice": "auto"})
        check("making starts", s == 200 and job.get("id"), json.dumps(job)[:120])
        deadline = time.time() + a.make_timeout
        while s == 200 and time.time() < deadline:
            _, job, _ = call(base, "/api/job/" + job["id"])
            if job["state"] != "running":
                break
            time.sleep(3)
        check("the video was made", job.get("state") == "done", job.get("error") or job.get("message", "") or json.dumps(job)[:300])
        if job.get("state") == "done":
            check("a voice engine was used", "silent" not in (job.get("voice") or "silent").lower(), f"voice={job.get('voice')!r} (silent means none was found: a warning, not a failure of the app)") or None
            s, body, hdr = call(base, job["video"], headers={"Range": "bytes=0-1023"})
            check("the video can be streamed with a range request", s == 206 and len(body) == 1024 and "mp4" in hdr.get("Content-Type", ""), f"status {s}")
            s, body, hdr = call(base, job["srt"])
            check("subtitles can be downloaded", s == 200 and b"-->" in body)
            tl = job.get("timeline") or {}
            check("the finished video carries a timeline for Running mode", len(tl.get("scenes", [])) >= 2 and len(tl.get("lines", [])) >= 1 and tl.get("seconds", 0) > 3,
                  f"{len(tl.get('scenes', []))} scenes, {len(tl.get('lines', []))} lines, {tl.get('seconds')} s")
            videos = Path(where.get("videos", ""))
            found = list(videos.glob("*/video.mp4"))
            check("the video is in the person's Videos\\Blaze folder", bool(found) and found[0].stat().st_size > 10_000, str(videos))

        demo = app_dir / "examples" / "looks-and-voices.txt"
        if demo.is_file():
            print("Making a video with text looks and a chosen voice per character:")
            text = demo.read_text(encoding="utf-8")
            if pick:
                text = text.replace("CAST: JOHN gender=m coat=1 hat=fedora ", f"CAST: JOHN gender=m coat=1 hat=fedora voice={pick} ")
            s, job, _ = call(base, "/api/make", {"text": text, "quality": a.quality, "voice": "auto"})
            check("making the looks demo starts", s == 200 and job.get("id"), json.dumps(job)[:120])
            deadline = time.time() + a.make_timeout
            while s == 200 and time.time() < deadline:
                _, job, _ = call(base, "/api/job/" + job["id"])
                if job["state"] != "running":
                    break
                time.sleep(3)
            check("the looks demo video was made", job.get("state") == "done", job.get("error") or job.get("message", "") or json.dumps(job)[:300])
            if job.get("state") == "done":
                s, body, _ = call(base, job["srt"])
                check("every line of the looks demo is subtitled, drawn or not", s == 200 and body.count(b"-->") == 7, f"{body.count(b'-->')} cues")
        else:
            check("the looks demo is installed", False, str(demo))

        print("Closing the page:")
        s, _, _ = call(base, "/api/bye", {})
        check("the page says it is closing", s == 200)
        try:
            proc.wait(timeout=90)
            check("the app stops by itself", True, f"exit code {proc.returncode}")
        except subprocess.TimeoutExpired:
            check("the app stops by itself", False, "still running 90 s after the page closed")
    finally:
        if proc.poll() is None:
            proc.kill()
    return finish(a.out, proc)


def finish(out: str, proc) -> int:
    ok = all(r["ok"] for r in results if not r["check"].startswith("a voice engine"))
    Path(out).write_text(json.dumps({"ok": ok, "results": results}, indent=2), encoding="utf-8")
    failed = [r["check"] for r in results if not r["ok"]]
    print("\nALL CHECKS PASSED" if not failed else f"\nFAILED: {failed}")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:                  # a crash is named too, not only a failed check
        import traceback
        annotate("error", "Installed app check crashed", "".join(traceback.format_exception_only(type(e), e)).strip()[:500])
        raise
