"""
Blender bridge: turn .blend files into the plain PNGs Blaze (and CDRCA's ImageProp) use.

  info(blend)                          what is in the file (meshes, shape keys, camera, frame range)
  render_sprites(blend, out, name)     transparent PNGs:  name.png, name_talk.png, name_blink.png
                                       (shape keys named talk / blink, if the model has them, drive the variants)
  render_still(blend, out_png)         one frame from the scene's camera, e.g. for a backdrop

Blender runs headless with Cycles on the CPU (no GPU or display needed). Nothing here touches CDRCA:
the output is ordinary images.  Blender 3.6+ (tested with 4.0).
"""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SCRIPT = Path(__file__).resolve().parent.parent / "blender" / "blaze_blender.py"


class BlenderError(Exception):
    pass


def find_blender(explicit: Optional[str] = None) -> Optional[Path]:
    """--blender path, $BLAZE_BLENDER / $BLENDER_PATH, `blender` on PATH, then the usual install folders."""
    cands: List[str] = [c for c in (explicit, os.environ.get("BLAZE_BLENDER"), os.environ.get("BLENDER_PATH")) if c]
    on_path = shutil.which("blender")
    if on_path: cands.append(on_path)
    pf = [os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")]
    for root in pf:
        cands += sorted(glob.glob(os.path.join(root, "Blender Foundation", "Blender *", "blender.exe")), reverse=True)
    cands += ["/Applications/Blender.app/Contents/MacOS/Blender", "/snap/bin/blender", "/usr/bin/blender"]
    for c in cands:
        if c and Path(c).exists():
            return Path(c)
    return None


def _need(blender: Optional[str]) -> Path:
    b = find_blender(blender)
    if b is None:
        raise BlenderError("Blender was not found. Install it from https://blender.org, or pass --blender <path> / set BLAZE_BLENDER.")
    return b


def run(blend: Optional[Path], command: str, args: List[str], blender: Optional[str] = None, timeout: int = 900) -> Tuple[List[str], Dict]:
    """Run one command of blender/blaze_blender.py. Returns (output files, JSON payload)."""
    exe = _need(blender)
    cmd = [str(exe), "-b", "--factory-startup"] + ([str(blend)] if blend else []) + ["-P", str(SCRIPT), "--", command] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise BlenderError(f"Blender took longer than {timeout}s on '{command}'") from e
    outs: List[str] = []
    payload: Dict = {}
    error = ""
    for line in r.stdout.splitlines():
        if line.startswith("BLAZE_OUT "): outs.append(line[10:].strip())
        elif line.startswith("BLAZE_JSON "):
            try: payload.update(json.loads(line[11:]))
            except ValueError: pass
        elif line.startswith("BLAZE_ERROR "): error = line[12:].strip()
    if error or r.returncode != 0:
        tail = [l for l in (r.stdout + "\n" + r.stderr).splitlines() if l.strip()][-6:]
        raise BlenderError(error or ("Blender failed:\n" + "\n".join(tail)))
    return outs, payload


def version(blender: Optional[str] = None) -> str:
    exe = _need(blender)
    r = subprocess.run([str(exe), "--version"], capture_output=True, text=True)
    m = re.search(r"Blender\s+([\d.]+)", r.stdout)
    return m.group(1) if m else r.stdout.strip().splitlines()[0]


def info(blend: Path, blender: Optional[str] = None) -> Dict:
    _, payload = run(blend, "info", [], blender)
    return payload


def render_sprites(blend: Path, out_dir: Path, name: str, size: Tuple[int, int] = (400, 720), samples: int = 32,
                   yaw: float = 0.0, blender: Optional[str] = None) -> List[Path]:
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    args = ["--out", str(out_dir), "--name", name, "--width", str(size[0]), "--height", str(size[1]), "--samples", str(samples)]
    if yaw: args += ["--yaw", str(yaw)]
    outs, _ = run(blend, "sprites", args, blender)
    return [Path(o) for o in outs]


def render_still(blend: Path, out_png: Path, size: Tuple[int, int] = (1920, 1080), samples: int = 32,
                 frame: Optional[int] = None, blender: Optional[str] = None) -> Path:
    out_png = Path(out_png); out_png.parent.mkdir(parents=True, exist_ok=True)
    args = ["--out", str(out_png), "--width", str(size[0]), "--height", str(size[1]), "--samples", str(samples)]
    if frame is not None: args += ["--start", str(frame)]
    outs, _ = run(blend, "still", args, blender)
    return Path(outs[-1]) if outs else out_png
