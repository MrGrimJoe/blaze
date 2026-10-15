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
    w, h = (getattr(a, "res", None) or "1280x720").lower().split("x")
    o = Options(width=int(w), height=int(h), fps=getattr(a, "fps", 24), voice=a.voice, wpm=a.wpm,
                keep_frames=a.keep_frames, node=a.node, library=Path(a.library) if getattr(a, "library", None) else None)
    if a.workers: o.workers = a.workers
    return o


def _common(p, size=True):
    p.add_argument("-o", "--output", default=None, help="output mp4 (default: <name>.mp4 next to the input)")
    if size:    # `build` re-renders at the size and fps stored in the project's project.json instead
        p.add_argument("--res", default="1280x720", help="frame size, e.g. 1920x1080 (default 1280x720)")
        p.add_argument("--fps", type=int, default=24)
    p.add_argument("--voice", default="auto", help="voice engine for characters with no voice= of their own: auto | espeak | pyttsx3 | piper | off")
    p.add_argument("--wpm", type=int, default=150, help="speaking speed in words per minute (about 105 is slow and clear)")
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
    from .ai import AnimationError, write_animation, write_screenplay
    cfg = Path(a.config) if a.config else None
    try:
        if a.quick:
            text = write_screenplay(a.idea, scenes=min(a.scenes, 3) if a.scenes == 4 else a.scenes, lines=a.lines or 14, level=a.level, config_path=cfg)
        else:
            text = write_animation(a.idea, scenes=a.scenes, lines_per_scene=a.lines or 5, level=a.level, config_path=cfg,
                                   progress=lambda m: print(f"  {m}..."))
    except (AnimationError, RuntimeError) as e:
        print(f"\n{e}", file=sys.stderr)
        return 2
    name = "_".join(a.idea.lower().split()[:4]) or "story"
    out = Path(a.output) if a.output else Path(name + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".txt").write_text(text, encoding="utf-8")
    print(f"Screenplay saved: {out.with_suffix('.txt')}\n")
    _report(make(text, out, _opts(a)))
    return 0


def cmd_expand(a) -> int:
    """Print the screenplay in its explicit core form: what every shorthand line stands for."""
    from .screenplay import parse, to_core
    sp = parse(Path(a.script).read_text(encoding="utf-8"))
    text = to_core(sp)
    if a.output:
        Path(a.output).write_text(text, encoding="utf-8")
        print(f"Wrote {a.output}")
    else:
        sys.stdout.write(text)
    for w in sp.warnings:
        print(f"note: {w}", file=sys.stderr)
    return 0


def cmd_voices(a) -> int:
    """List the voice engines and voices, or play a sample of one."""
    from . import voice as V
    if a.voice:
        out = Path(a.output or "voice-sample.wav")
        secs = V.preview(a.say, a.voice, out, gender=a.gender, rate=a.rate or 0, pitch=a.pitch if a.pitch is not None else -1)
        print(f"Wrote {out} ({secs:.1f}s). Use it in a screenplay with:  CAST: NAME voice={V.check_spec(a.voice)}")
        return 0
    for e in V.engines_info():
        if not e["available"]:
            print(f"{e['engine']}: not installed.  {e['hint']}")
            continue
        voices = [v for v in e["voices"] if not a.engine or a.engine == e["engine"]]
        if a.engine and a.engine != e["engine"]:
            continue
        print(f"{e['engine']}: {len(e['voices'])} voice(s)   (use as  CAST: NAME voice={e['engine']}:<voice>)")
        for v in voices[: (None if a.all else 12)]:
            print(f"    {v['id']:<34} {v['label']}")
        if not a.all and len(voices) > 12:
            print(f"    ... {len(voices) - 12} more; --all lists every voice, --engine {e['engine']} shows just this engine")
    print("\nTry one:  blaze voices --voice espeak:en-gb+f2 --say \"Hello there\"")
    return 0


def cmd_ui(a) -> int:
    from .ui import serve
    return serve(port=a.port, open_browser=not a.no_browser, workdir=Path(a.out) if a.out else None,
                 library=Path(a.library) if a.library else None, auto_exit=a.auto_exit)


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


def _safe_console() -> None:
    """A Windows console may use a code page that cannot show a character's name (Zoë, علی): print '?' for it instead of crashing."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None) -> int:
    _safe_console()
    ap = argparse.ArgumentParser(prog="blaze", description="Screenplay in, animated video out.")
    ap.add_argument("--version", action="version", version="blaze " + __version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("make", help="screenplay .txt -> mp4"); p.add_argument("script"); p.add_argument("--project"); _common(p); p.set_defaults(fn=cmd_make)
    p = sub.add_parser("build", help="re-render an edited project folder (size and fps come from its project.json)"); p.add_argument("project"); _common(p, size=False); p.set_defaults(fn=cmd_build)
    p = sub.add_parser("ai", help="idea -> screenplay (via your LLM) -> mp4"); p.add_argument("idea")
    p.add_argument("--scenes", type=int, default=4, help="number of scenes (default 4)")
    p.add_argument("--lines", type=int, default=None, help="spoken lines per scene (default 5; with --quick: in total, default 14)")
    p.add_argument("--quick", action="store_true", help="ONE request for a short screenplay instead of one per scene (cheaper)")
    p.add_argument("--level", help="language level for the dialogue, e.g. A2"); p.add_argument("--config", help="path to a BlazEng config.yaml")
    _common(p); p.set_defaults(fn=cmd_ai)
    p = sub.add_parser("expand", help="print a screenplay in its explicit core form (what each shorthand line stands for)")
    p.add_argument("script"); p.add_argument("-o", "--output", help="write to a file instead of the screen"); p.set_defaults(fn=cmd_expand)
    p = sub.add_parser("voices", help="list the voices you can give characters (CAST: NAME voice=...), or play a sample of one")
    p.add_argument("--engine", choices=("espeak", "pyttsx3", "piper")); p.add_argument("--all", action="store_true", help="list every voice")
    p.add_argument("--voice", help="play a sample of this voice, e.g. espeak:en-us+m3"); p.add_argument("--say", default="Hello there. This is how I sound.")
    p.add_argument("--gender", default="m", choices=("m", "f")); p.add_argument("--rate", type=int); p.add_argument("--pitch", type=int)
    p.add_argument("-o", "--output", help="where to write the sample (default voice-sample.wav)"); p.set_defaults(fn=cmd_voices)
    p = sub.add_parser("ui", help="open the Blaze page in your browser (write, check, make, watch)")
    p.add_argument("--port", type=int, default=8765); p.add_argument("--no-browser", action="store_true")
    p.add_argument("--auto-exit", action="store_true", help="stop when the page is closed (the installed app does this)")
    p.add_argument("--out", help="folder for the videos (default: ./blaze-videos)"); p.add_argument("--library")
    p.set_defaults(fn=cmd_ui)
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
    except (RuntimeError, ValueError) as e:
        print(f"\nBlaze failed: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
