"""Shared by the window and run tests."""
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def can_render() -> bool:
    """node + Playwright (with a browser) + ffmpeg: what the offline demo needs to make a real video.

    require('playwright') alone isn't enough: the npm package can resolve (stale node_modules or
    cache) while the browser binary itself was never downloaded for this OS/session -- confirmed
    on Windows CI, where that gap let test_the_real_offline_demo_through_the_window and
    test_the_offline_demo_makes_a_video past this guard and then fail for real instead of
    skipping. Launching (and immediately closing) a real browser is the only check that can't be
    fooled by a present-but-useless npm package.
    """
    if not (shutil.which("node") and shutil.which("ffmpeg")):
        return False
    r = subprocess.run(
        ["node", "-e", "require('playwright').chromium.launch().then(b => b.close())"],
        cwd=REPO / "cdrca", capture_output=True, timeout=60,
    )
    return r.returncode == 0
