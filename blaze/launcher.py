"""
The installed Blaze app: what the Start-menu shortcut runs (through pythonw, so there is no console window).

It makes the bundled tools findable, keeps your files in your own folders, opens the page, and closes itself when the page
is closed. Run from source it does the same with whatever tools are on your PATH.

    python -m blaze.launcher               start (or just open the page if Blaze is already running)
    python -m blaze.launcher --selftest    print where everything was found, as JSON, and exit

Layout of an installed copy (the folder the installer chose):

    runtime/python/  runtime/node/  runtime/ffmpeg/  runtime/browsers/      the tools Blaze needs
    app/             blaze/  cdrca/  cdrca-lib/  blender/  studio/  ...        Blaze itself
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import Dict, Optional

APP = Path(__file__).resolve().parent.parent          # the folder that holds blaze/
FIRST_PORT = 8765
PORTS_TRIED = 16


def _home() -> Path:
    return Path(os.environ.get("USERPROFILE") or Path.home())


def locations(app: Path = APP, env: Optional[Dict[str, str]] = None) -> dict:
    """Where the tools and the person's own files are. Pure: nothing is created here."""
    env = dict(os.environ if env is None else env)
    runtime = app.parent / "runtime"
    home = Path(env.get("USERPROFILE") or Path.home())
    appdata = Path(env.get("APPDATA") or home / ".config") / "Blaze"
    localdata = Path(env.get("LOCALAPPDATA") or home / ".local" / "share") / "Blaze"
    return {
        "app": app,
        "runtime": runtime if runtime.is_dir() else None,
        "tool_dirs": [d for d in (runtime / "python", runtime / "node", runtime / "ffmpeg") if d.is_dir()],
        "browsers": (runtime / "browsers") if (runtime / "browsers").is_dir() else None,
        "config": appdata / "config.yaml",
        "config_template": app / "studio" / "config.yaml",
        "videos": home / "Videos" / "Blaze",
        "library": home / "Documents" / "Blaze" / "library",
        "log": localdata / "blaze.log",
    }


def prepare(loc: dict, create: bool = True) -> None:
    """Make the bundled tools findable and give the person their own config, videos and library folders."""
    if loc["tool_dirs"]:
        os.environ["PATH"] = os.pathsep.join([str(d) for d in loc["tool_dirs"]] + [os.environ.get("PATH", "")])
    if loc["browsers"]:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(loc["browsers"])
    os.environ["BLAZE_CONFIG"] = str(loc["config"])
    if create:
        for key in ("videos", "library"):
            loc[key].mkdir(parents=True, exist_ok=True)
        loc["config"].parent.mkdir(parents=True, exist_ok=True)
        if not loc["config"].exists() and loc["config_template"].exists():
            shutil.copyfile(loc["config_template"], loc["config"])     # ships with every provider and key empty


def _blaze_answers(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=1.5) as r:
            return "sample" in json.loads(r.read())
    except Exception:
        return False


def _free(port: int) -> bool:
    import socket
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def pick_port() -> tuple:
    """(port, already_running). Reuses a running Blaze instead of starting a second one."""
    for port in range(FIRST_PORT, FIRST_PORT + PORTS_TRIED):
        if _blaze_answers(port):
            return port, True
        if _free(port):
            return port, False
    raise RuntimeError(f"No free port between {FIRST_PORT} and {FIRST_PORT + PORTS_TRIED - 1}.")


def _redirect_output_if_windowless(log: Path) -> None:
    """pythonw has no console: send what would be printed to a log file instead of failing."""
    if sys.stdout is None or sys.stderr is None:
        log.parent.mkdir(parents=True, exist_ok=True)
        stream = open(log, "a", encoding="utf-8", buffering=1)
        stream.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        sys.stdout = sys.stderr = stream


def selftest(loc: dict) -> dict:
    prepare(loc, create=False)
    found = {name: shutil.which(name) for name in ("node", "ffmpeg")}
    return {
        "app": str(loc["app"]),
        "runtime": str(loc["runtime"]) if loc["runtime"] else None,
        "browsers": str(loc["browsers"]) if loc["browsers"] else None,
        "config": str(loc["config"]), "videos": str(loc["videos"]), "library": str(loc["library"]),
        "node": found["node"], "ffmpeg": found["ffmpeg"],
        "cdrca_render": (loc["app"] / "cdrca" / "Back-end" / "Render" / "render.js").is_file(),
        "atoms": (loc["app"] / "cdrca-lib" / "atoms.cdrca").is_file(),
    }


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    loc = locations()
    if "--selftest" in args:
        print(json.dumps(selftest(loc), indent=2))
        return 0
    _redirect_output_if_windowless(loc["log"])
    prepare(loc)
    try:
        port, running = pick_port()
    except RuntimeError as e:
        print(e)
        return 1
    # BLAZE_NO_BROWSER=1: do not open a browser (for scripts and tests). A page that is open pings every few seconds, and that
    # keeps the app alive: an app started by a test on a machine with a default browser would otherwise never stop.
    open_browser = not os.environ.get("BLAZE_NO_BROWSER")
    if running:                                   # Blaze is already open: just show it again
        if open_browser:
            webbrowser.open(f"http://127.0.0.1:{port}")
        return 0
    if str(loc["app"]) not in sys.path:
        sys.path.insert(0, str(loc["app"]))
    from blaze.ui import serve
    return serve(port=port, open_browser=open_browser, workdir=loc["videos"], library=loc["library"], auto_exit=True)


if __name__ == "__main__":
    raise SystemExit(main())


# --------------------------------------------------------------------------- Blaze Studio (the desktop window)
def studio_selftest(loc: dict) -> dict:
    """Open the studio window off-screen, run the offline demo through it, and say whether a video came out.
    Proves the installed runtime has everything the studio needs: PyQt6, Node, the browser, ffmpeg, Blaze's art."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import tempfile
    import yaml
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from src.ui.main_window import MainWindow
    cfg = yaml.safe_load((loc["app"] / "studio" / "config.yaml").read_text(encoding="utf-8")) or {}
    cfg["storage_path"] = tempfile.mkdtemp(prefix="blaze-studio-selftest-")
    w = MainWindow(cfg)
    w.show()
    w.demo_button.click()
    end = time.time() + 600
    while time.time() < end and (w.busy or w.stack.currentIndex() == 1):
        app.processEvents()
        time.sleep(0.05)
    for _ in range(20):
        app.processEvents()
    ok = w.stack.currentIndex() == 2 and w.last_result is not None and w.last_result.video.exists()
    return {"ok": bool(ok), "video": str(w.last_result.video) if ok else None,
            "video_bytes": w.last_result.video.stat().st_size if ok else 0, "shots": w.last_result.shots if ok else 0,
            "error": None if ok else w.error_label.text()}


def main_studio(argv=None) -> int:
    """What the "Blaze Studio" shortcut runs (through pythonw)."""
    args = list(sys.argv[1:] if argv is None else argv)
    loc = locations()
    _redirect_output_if_windowless(loc["log"])
    prepare(loc)
    studio = loc["app"] / "studio"
    os.environ["AIPS_DATA_DIR"] = str(loc["config"].parent / "Studio")
    for p in (str(studio), str(loc["app"])):
        if p not in sys.path:
            sys.path.insert(0, p)
    os.chdir(studio)
    if "--selftest" in args:
        result = studio_selftest(loc)
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1
    import main as studio_main
    studio_main.main()
    return 0
