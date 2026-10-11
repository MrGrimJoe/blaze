"""
Builds the folder the Windows installer packs: installer/build/Blaze/

    python installer/stage.py                  just the app (what a test needs)
    python installer/stage.py --download       the whole thing, on a Windows machine (what CI runs)

    build/Blaze/
      app/        Blaze itself (blaze/, cdrca/, cdrca-lib/, blender/, docs/, studio/ providers, examples/ ...)
      runtime/    python/ (embeddable + packages)   node/ (node.exe)   ffmpeg/   browsers/ (headless Chromium)
      blaze.ico   LICENSE.txt   THIRD-PARTY-NOTICES.md
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
PY_VERSION = "3.12.8"
FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
PRUNE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", "node_modules", ".git", ".DS_Store")


def say(msg: str) -> None:
    print(f"[stage] {msg}", flush=True)


# ------------------------------------------------------------------------------------------------ the app
def stage_app(out: Path) -> Path:
    app = out / "app"
    if app.exists():
        shutil.rmtree(app)
    app.mkdir(parents=True)
    for name in ("blaze", "blender", "cdrca-lib", "docs"):
        shutil.copytree(REPO / name, app / name, ignore=PRUNE)
    # CDRCA: the engine only (its tests and examples are not needed to render)
    shutil.copytree(REPO / "cdrca", app / "cdrca", ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules", ".git", "tests", "examples"))
    # Blaze Studio (the desktop window, which also holds the AI writer's provider layer) and the config it reads.
    # Every provider and key ships empty; the CDRCA renderer is the backend (Godot is not part of this installer).
    (app / "studio").mkdir()
    shutil.copytree(REPO / "studio" / "src", app / "studio" / "src", ignore=PRUNE)
    shutil.copyfile(REPO / "studio" / "main.py", app / "studio" / "main.py")
    config = (REPO / "studio" / "config.yaml").read_text(encoding="utf-8").rstrip("\n")
    if re.search(r"^render_backend:", config, re.M):
        config = re.sub(r"^render_backend:.*$", "render_backend: cdrca   # Blaze installer: the studio renders with the bundled CDRCA, not Godot", config, flags=re.M)
    else:
        config += "\n\n# Blaze installer: the studio renders with the bundled CDRCA, not Godot\nrender_backend: cdrca"
    (app / "studio" / "config.yaml").write_text(config + "\n", encoding="utf-8")
    for f in ("blaze.py", "blaze_app.pyw", "studio_app.pyw", "README.md", "LICENSE.md", "LICENSES.md", "requirements.txt"):
        shutil.copyfile(REPO / f, app / f)
    (app / "examples").mkdir()
    shutil.copyfile(REPO / "tests" / "fixtures" / "sample_story.txt", app / "examples" / "the-warehouse.txt")
    version = re.search(r'__version__\s*=\s*"([^"]+)"', (REPO / "blaze" / "__init__.py").read_text(encoding="utf-8")).group(1)
    (app / "VERSION").write_text(version + "\n", encoding="utf-8")
    shutil.copyfile(HERE / "assets" / "blaze.ico", out / "blaze.ico")
    shutil.copyfile(REPO / "THIRD-PARTY-NOTICES.md", out / "THIRD-PARTY-NOTICES.md")
    write_license_txt(REPO / "LICENSE.md", out / "LICENSE.txt")
    say(f"app staged ({sum(1 for _ in app.rglob('*') if _.is_file())} files, version {version})")
    return app


def write_license_txt(markdown: Path, target: Path) -> None:
    """The installer's license page shows plain text: the same words without the markdown marks."""
    text = markdown.read_text(encoding="utf-8")
    text = re.sub(r"^#+\s*", "", text, flags=re.M)
    text = text.replace("**", "").replace("`", "")
    target.write_text(text.strip() + "\n", encoding="utf-8-sig")


# ------------------------------------------------------------------------------------------------ the runtime
def download(url: str, target: Path) -> Path:
    say(f"downloading {url}")
    target.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "blaze-installer-build"})
    with urllib.request.urlopen(req, timeout=300) as r, open(target, "wb") as f:
        shutil.copyfileobj(r, f)
    if target.stat().st_size < 1_000_000:
        raise SystemExit(f"download looks wrong ({target.stat().st_size} bytes): {url}")
    return target


def write_pth(python_dir: Path) -> Path:
    """Embeddable Python ignores PYTHONPATH when a ._pth file exists, so everything it may import is listed here."""
    pth = next(python_dir.glob("python*._pth"))
    zipname = next(python_dir.glob("python*.zip")).name
    pth.write_text("\n".join([zipname, ".", r"Lib\site-packages", r"..\..\app", "import site", ""]), encoding="utf-8")
    return pth


def stage_python(out: Path, version: str = PY_VERSION) -> None:
    dest = out / "runtime" / "python"
    zip_path = download(f"https://www.python.org/ftp/python/{version}/python-{version}-embed-amd64.zip", out.parent / "dl" / "python-embed.zip")
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(dest)
    pth = write_pth(dest)
    minor = ".".join(version.split(".")[:2])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--target", str(dest / "Lib" / "site-packages"),
                           "--platform", "win_amd64", "--python-version", minor, "--only-binary=:all:", "--no-compile",
                           "-r", str(HERE / "runtime-requirements.txt")])
    say(f"python staged ({pth.name} written)")


def stage_node(out: Path, node_exe: str | None) -> Path:
    exe = Path(node_exe or shutil.which("node") or "")
    if not exe.is_file():
        raise SystemExit("node.exe not found: install Node.js or pass --node")
    dest = out / "runtime" / "node"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(exe, dest / exe.name)
    say(f"node staged ({exe})")
    return dest / exe.name


def stage_ffmpeg(out: Path) -> None:
    zip_path = download(FFMPEG_URL, out.parent / "dl" / "ffmpeg.zip")
    dest = out / "runtime" / "ffmpeg"
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            base = name.rsplit("/", 1)[-1]
            if base in ("ffmpeg.exe", "ffprobe.exe", "LICENSE.txt"):
                with z.open(name) as src, open(dest / base, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    if not (dest / "ffmpeg.exe").is_file():
        raise SystemExit("ffmpeg.exe was not found in the downloaded archive")
    (dest / "SOURCE.txt").write_text(
        "This ffmpeg is a GPL build made by BtbN (https://github.com/BtbN/FFmpeg-Builds). Blaze runs it as a separate program.\n"
        "Its source code and the build scripts are available from that address and from https://ffmpeg.org/.\n", encoding="utf-8")
    say("ffmpeg staged")


def stage_renderer(out: Path, node: Path) -> None:
    """playwright into cdrca/node_modules, and the headless Chromium it drives into runtime/browsers."""
    npm = shutil.which("npm")
    if not npm:
        raise SystemExit("npm not found: install Node.js")
    tmp = out.parent / "npm-tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    subprocess.check_call([npm, "install", "--prefix", str(tmp), "--no-save", "--no-audit", "--no-fund", "playwright"])
    modules = out / "app" / "cdrca" / "node_modules"
    shutil.copytree(tmp / "node_modules", modules, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".bin", ".package-lock.json"))
    env = dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=str(out / "runtime" / "browsers"))
    cli = next(p for p in (modules / "playwright-core" / "cli.js", modules / "playwright" / "node_modules" / "playwright-core" / "cli.js") if p.is_file())
    r = subprocess.call([str(node), str(cli), "install", "--only-shell", "chromium"], env=env)
    if r != 0:                         # an older Playwright without --only-shell: take the full browser
        subprocess.check_call([str(node), str(cli), "install", "chromium"], env=env)
    say("renderer staged (playwright + headless Chromium)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(HERE / "build" / "Blaze"))
    ap.add_argument("--download", action="store_true", help="also fetch Python, Node, ffmpeg and the browser (Windows build machine)")
    ap.add_argument("--node", help="path to node.exe (default: the one on PATH)")
    ap.add_argument("--python-version", default=PY_VERSION)
    a = ap.parse_args(argv)
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    stage_app(out)
    if a.download:
        stage_python(out, a.python_version)
        node = stage_node(out, a.node)
        stage_ffmpeg(out)
        stage_renderer(out, node)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
