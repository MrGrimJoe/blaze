"""
Is the installer real? Two checks the build runs, so a hollow installer can never leave the build as if it were good.

    python installer/check_installer.py --stage installer/build/Blaze     before compiling: is everything staged, and big enough?
    python installer/check_installer.py --installer dist                  after compiling: is the .exe as big as a full one?

Why sizes: a full Blaze installer carries Python with PyQt6, Node, ffmpeg and a headless Chromium, about 280 MB. If a download
or an install step quietly produced less, the old build still compiled something and called it an installer. The floors
below are well under what a full build weighs (about half) and far above what a hollow one does. Exit status 0 only when
every check passes; the table it prints goes into the job log either way.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

MB = 1024 * 1024

# (what, path under the staged folder, smallest size in MB). A folder is measured as the sum of its files.
STAGED = [
    ("Python (embeddable)", "runtime/python/python.exe", 0.01),
    ("Python packages (PyQt6, Pillow, AI providers ...)", "runtime/python/Lib/site-packages", 60),
    ("Node.js", "runtime/node/node.exe", 30),
    ("ffmpeg", "runtime/ffmpeg/ffmpeg.exe", 50),
    ("ffprobe", "runtime/ffmpeg/ffprobe.exe", 50),
    ("headless Chromium", "runtime/browsers", 80),
    ("the renderer's playwright", "app/cdrca/node_modules/playwright/package.json", 0.0005),
    ("Blaze itself", "app/blaze_app.pyw", 0.0005),
    ("Blaze Studio", "app/studio/main.py", 0.0005),
]
INSTALLER_MIN_MB = 150


def size_of(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    if path.is_dir():
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return -1


def check_stage(stage: Path, items=None) -> list:
    problems = []
    print(f"{'part':<52}{'size':>10}   floor")
    for what, rel, floor in (items if items is not None else STAGED):
        n = size_of(stage / rel)
        floor_b = int(floor * MB)
        ok = n >= max(floor_b, 1)
        print(f"{what:<52}{(n / MB if n >= 0 else 0):>8.1f} MB   {floor:g} MB  {'ok' if ok else 'TOO SMALL OR MISSING'}   ({rel})")
        if not ok:
            problems.append(f"{what}: {'missing' if n < 0 else f'{n / MB:.2f} MB'} at {rel}, a full build has at least {floor:g} MB")
    return problems


def check_installer(dist: Path, min_mb: float = INSTALLER_MIN_MB) -> list:
    exes = sorted(dist.glob("Blaze_Setup_*.exe"))
    if len(exes) != 1:
        return [f"expected exactly one Blaze_Setup_*.exe in {dist}, found {len(exes)}"]
    mb = exes[0].stat().st_size / MB
    print(f"{exes[0].name}: {mb:.1f} MB (a full installer is about 280 MB; the floor is {min_mb:g} MB)")
    return [] if mb >= min_mb else [f"{exes[0].name} is only {mb:.1f} MB: it is missing parts, not a full installer (floor {min_mb:g} MB)"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", help="the staged folder, installer/build/Blaze")
    ap.add_argument("--installer", help="the folder holding Blaze_Setup_*.exe")
    ap.add_argument("--min-mb", type=float, default=INSTALLER_MIN_MB)
    a = ap.parse_args(argv)
    if not (a.stage or a.installer):
        ap.error("give --stage and/or --installer")
    problems = []
    if a.stage:
        problems += check_stage(Path(a.stage))
    if a.installer:
        problems += check_installer(Path(a.installer), a.min_mb)
    for p in problems:
        print(f"PROBLEM: {p}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
