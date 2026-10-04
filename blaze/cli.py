"""blaze — screenplay in, animated video out."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__
from .pipeline import REPO, BlazeError, Options, create_project, make, render_project
from .screenplay import ScreenplayError



def _opts(a) -> Options:
    w, h = (a.res or "1280x720").lower().split("x")
    o = Options(width=int(w), height=int(h), fps=a.fps, voice=a.voice, wpm=a.wpm, style=getattr(a, "style", None),
                keep_frames=a.keep_frames, node=a.node, library=Path(a.library) if getattr(a, "library", None) else None)
    if a.workers: o.workers = a.workers
    if a.pace: o.wpm = {"slow": 105, "normal": 150, "fast": 185}[a.pace]
    return o


def _common(p):
    p.add_argument("-o", "--output", default=None, help="output mp4 (default: <name>.mp4 next to the input)")
    p.add_argument("--res", default="1280x720", help="frame size, e.g. 1920x1080 (default 1280x720)")
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--voice", default="auto", help="auto | espeak | pyttsx3 | off")
    p.add_argument("--pace", choices=("slow", "normal", "fast"), help="speaking speed (slow ~105 wpm, good for language learners)")
    p.add_argument("--wpm", type=int, default=150)
    p.add_argument("--style", choices=("bubbles", "subtitles", "both"), help="dialogue display (overrides STYLE:)")
    p.add_argument("--workers", type=int, default=0, help="scenes rendered in parallel")
    p.add_argument("--keep-frames", action="store_true")
    p.add_argument("--node", default="node")
    p.add_argument("--library", help="folder with characters/ and backdrops/ (default: ./library next to the screenplay)")


def _report(res) -> None:
    print(f"\nDone: {res.video}  ({res.duration:.1f}s, {res.shots} scenes)")
    if res.srt: print(f"Subtitles: {res.srt}")
    print(f"Editable project: {res.project}  (edit scenes/*.cdrca, then: blaze build \"{res.project}\")")


def cmd_make(a) -> int:
    src = Path(a.script)
    out = Path(a.output) if a.output else src.with_suffix(".mp4")
    _report(make(src.read_text(encoding="utf-8"), out, _opts(a), Path(a.project) if a.project else None, src.resolve().parent))
    return 0


def cmd_build(a) -> int:
    project = Path(a.project)
    out = Path(a.output) if a.output else project.with_suffix(".mp4")
    _report(render_project(project, out, _opts(a)))
    return 0


def cmd_ai(a) -> int:
    from .ai import write_screenplay
    text = write_screenplay(a.idea, scenes=a.scenes, lines=a.lines, level=a.level, config_path=Path(a.config) if a.config else None)
    name = "_".join(a.idea.lower().split()[:4]) or "story"
    out = Path(a.output) if a.output else Path(name + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".txt").write_text(text, encoding="utf-8")
    print(f"Screenplay saved: {out.with_suffix('.txt')}\n")
    _report(make(text, out, _opts(a)))
    return 0


def cmd_asset(a) -> int:
    from .library import Library, IMAGE_EXT
    lib = Library.default(Path(a.library) if a.library else None)
    if a.action == "list":
        found = lib.list()
        print(f"Library: {lib.home}")
        for kind, names in found.items():
            print(f"  {kind}: {', '.join(names) if names else '(none)'}")
        return 0
    src = Path(a.file)
    if not src.exists():
        print(f"File not found: {src}", file=sys.stderr); return 2
    kind = a.kind
    if not kind:
        if src.suffix.lower() == ".blend": kind = "character"
        elif src.suffix.lower() in IMAGE_EXT: kind = "character" if lib.has_alpha(src) else "backdrop"
        else:
            print("Give a .png/.jpg/.webp image or a .blend file.", file=sys.stderr); return 2
        print(f"Adding as a {kind} (override with --as character|backdrop)")
    if kind == "character":
        files = lib.add_character(src, a.name, blender=a.blender, samples=a.samples, yaw=a.yaw)
    else:
        files = [lib.add_backdrop(src, a.name, blender=a.blender, samples=a.samples)]
    for f in files: print("  added", f)
    return 0


def cmd_setup(a) -> int:
    npm, npx = shutil.which("npm"), shutil.which("npx")
    if not npm or not npx:
        print("npm not found: install Node.js from https://nodejs.org first."); return 1
    print("Installing the renderer's browser (playwright + headless Chromium)...")
    cwd = str(REPO / "cdrca")
    # --no-save: CDRCA's own package.json is left untouched
    if subprocess.call([npm, "install", "--no-save", "playwright"], cwd=cwd) != 0:
        return 1
    return subprocess.call([npx, "playwright", "install", "chromium"], cwd=cwd)


def doctor(a) -> int:
    ok = True

    def row(good: bool, what: str, fix: str = "", optional: bool = False):
        nonlocal ok
        mark = "OK " if good else ("-- " if optional else "!! ")
        print(f"  {mark}{what}" + ("" if good or not fix else f"   -> {fix}"))
        if not good and not optional: ok = False

    print("Blaze doctor")
    row(sys.version_info >= (3, 9), f"Python {sys.version.split()[0]}", "need 3.9+")
    try:
        import PIL; row(True, f"Pillow {PIL.__version__}")
    except ImportError:
        row(False, "Pillow", "pip install pillow")
    node = shutil.which(a.node)
    row(bool(node), "Node.js", "install from https://nodejs.org")
    if node:
        r = subprocess.run([node, "-e", "require('playwright')"], cwd=str(REPO / "cdrca"), capture_output=True, text=True)
        row(r.returncode == 0, "playwright (node module)", "run: python blaze.py setup")
        if r.returncode == 0:
            r = subprocess.run([node, "-e", "require('playwright').chromium.launch().then(b=>b.close()).then(()=>process.exit(0)).catch(e=>{console.error(e.message.split('\\n')[0]);process.exit(1)})"],
                               cwd=str(REPO / "cdrca"), capture_output=True, text=True)
            row(r.returncode == 0, "headless Chromium", "run: python blaze.py setup   (or: npx playwright install chromium)")
    row(bool(shutil.which("ffmpeg")), "ffmpeg", "install from https://ffmpeg.org and add to PATH")
    has_espeak = bool(shutil.which("espeak-ng"))
    try:
        import pyttsx3; has_py = True
    except ImportError:
        has_py = False
    row(has_espeak or has_py, "voices (espeak-ng or pyttsx3)", "optional: install espeak-ng, or pip install pyttsx3 (uses Windows voices)", optional=True)
    from . import blender as _bl
    b = _bl.find_blender()
    row(bool(b), "Blender" + (f" {_bl.version()}" if b else ""), "optional: only needed for .blend assets (https://blender.org)", optional=True)
    print("\nAll required tools found." if ok else "\nFix the !! items above, then run doctor again.")
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="blaze", description="Screenplay in, animated video out.")
    ap.add_argument("--version", action="version", version="blaze " + __version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("make", help="screenplay .txt -> mp4"); p.add_argument("script"); p.add_argument("--project"); _common(p); p.set_defaults(fn=cmd_make)
    p = sub.add_parser("build", help="re-render an edited project folder"); p.add_argument("project"); _common(p); p.set_defaults(fn=cmd_build)
    p = sub.add_parser("ai", help="idea -> screenplay (via your LLM) -> mp4"); p.add_argument("idea")
    p.add_argument("--scenes", type=int, default=3); p.add_argument("--lines", type=int, default=14)
    p.add_argument("--level", help="language level for the dialogue, e.g. A2"); p.add_argument("--config", help="path to a BlazEng config.yaml")
    _common(p); p.set_defaults(fn=cmd_ai)
    p = sub.add_parser("asset", help="manage your own characters and backdrops (PNG/JPG or .blend via Blender)")
    p.add_argument("action", choices=("add", "list")); p.add_argument("file", nargs="?")
    p.add_argument("--name"); p.add_argument("--as", dest="kind", choices=("character", "backdrop"))
    p.add_argument("--library"); p.add_argument("--blender"); p.add_argument("--samples", type=int, default=32)
    p.add_argument("--yaw", type=float, default=0.0, help="rotate a .blend subject before rendering (degrees)")
    p.set_defaults(fn=cmd_asset)
    p = sub.add_parser("setup", help="install the renderer (npm install + Chromium)"); p.set_defaults(fn=cmd_setup)
    p = sub.add_parser("doctor", help="check that everything needed is installed"); p.add_argument("--node", default="node"); p.set_defaults(fn=doctor)

    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except (BlazeError, ScreenplayError) as e:
        stage = getattr(e, "stage", "screenplay")
        print(f"\nBlaze failed ({stage}): {e}", file=sys.stderr)
        if stage == "setup": print("Run: python blaze.py doctor", file=sys.stderr)
        return 2
    except RuntimeError as e:
        print(f"\nBlaze failed: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
