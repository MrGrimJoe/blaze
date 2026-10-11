"""Shared by the window and run tests."""
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def can_render() -> bool:
    """node + Playwright (with a browser) + ffmpeg: what the offline demo needs to make a real video."""
    if not (shutil.which("node") and shutil.which("ffmpeg")):
        return False
    r = subprocess.run(["node", "-e", "require('playwright')"], cwd=REPO / "cdrca", capture_output=True)
    return r.returncode == 0
