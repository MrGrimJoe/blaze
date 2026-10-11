"""
CDRCA rendering bridge (Blaze).

Drop-in alternative to GodotRenderer: same `render_shot(...)` signature, same
return value (ordered list of frame PNG paths), so PipelineOrchestrator can take
it as `godot_renderer=CdrcaRenderer(config)` with no orchestrator changes.

It shells out to CDRCA's headless CLI (Back-end/Render/render.js), which
transpiles a .cdrca script and steps the three.js renderer frame-by-frame in
headless Chromium. Failures come back as structured JSON ({stage, message}), which
CdrcaRenderError keeps so a repair step can feed the transpiler's message back to
the model that wrote the script.

Config keys (config.yaml):
  cdrca_render_script   path to cdrca-render.js        (default: cdrca/Back-end/Render/render.js in the Blaze repo)
  node_binary           node executable                 (default "node")
  storage_path, render_fps, render_width, render_height, render_timeout_seconds
"""

import json
import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_FPS = 24
_DEFAULT_TIMEOUT_SECONDS = 300


class CdrcaRenderError(Exception):
    """Raised when a CDRCA script fails to transpile/render, or tooling is missing.

    `stage` is one of: setup, args, transpile, run, render, encode, crash, timeout, output.
    `stage == "transpile"` means the script itself is invalid (a model/repair problem);
    other stages usually mean an environment problem.
    """

    def __init__(self, message: str, stage: str = "crash"):
        super().__init__(message)
        self.stage = stage


class CdrcaRenderer:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        storage_path = Path(config.get("storage_path", "./storage"))
        self.frames_dir = storage_path / "renders"
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.fps = int(config.get("render_fps", _DEFAULT_FPS))
        self.width = int(config.get("render_width", 1280))
        self.height = int(config.get("render_height", 720))
        self.timeout_seconds = int(config.get("render_timeout_seconds", _DEFAULT_TIMEOUT_SECONDS))
        self.node_binary = str(config.get("node_binary", "node"))
        script = config.get("cdrca_render_script")
        # default: the engine bundled in this repo (blaze/cdrca/Back-end/Render/render.js)
        bundled = Path(__file__).resolve().parents[4] / "cdrca" / "Back-end" / "Render" / "render.js"
        self.script = Path(script) if script else (bundled if bundled.exists() else None)

    def render_shot(
        self,
        scene_path: Path,
        shot_id: str,
        duration_seconds: float = 4.0,
        num_frames: Optional[int] = None,
    ) -> List[Path]:
        """Render a .cdrca scene to PNG frames and return their paths in order."""
        if self.script is None or not self.script.exists():
            raise CdrcaRenderError(
                "cdrca_render_script is not set or does not exist. Point it at "
                "cdrca/Back-end/Render/render.js in config.yaml.",
                stage="setup",
            )
        if shutil.which(self.node_binary) is None:
            raise CdrcaRenderError(f"'{self.node_binary}' not found on PATH (install Node.js).", stage="setup")

        frames = num_frames if num_frames is not None else max(1, round(duration_seconds * self.fps))
        out_dir = self.frames_dir / _sanitize(shot_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        for stale in out_dir.glob("*.png"):  # a partial old render must not pass for a new one
            stale.unlink()

        cmd = [
            self.node_binary, str(self.script.resolve()), str(Path(scene_path).resolve()),
            "--out", str(out_dir.resolve()),
            "--fps", str(self.fps),
            "--width", str(self.width),
            "--height", str(self.height),
            "--from", "1.5",                      # skip CDRCA's default intro scene
            "--duration", str(frames / self.fps),
        ]

        logger.info(f"CDRCA rendering {shot_id}: {frames} frames @ {self.fps}fps")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired as e:
            raise CdrcaRenderError(f"Render of '{shot_id}' timed out after {self.timeout_seconds}s", "timeout") from e

        if result.returncode != 0:
            raise _error_from_stderr(result.stderr, shot_id)

        output_frames = sorted(out_dir.glob("*.png"))
        if not output_frames:
            raise CdrcaRenderError(f"CDRCA exited successfully but wrote no frames for '{shot_id}'.", "output")
        if len(output_frames) != frames:
            logger.warning(f"Expected {frames} frames for '{shot_id}', got {len(output_frames)}")
        return output_frames


def _error_from_stderr(stderr: str, shot_id: str) -> CdrcaRenderError:
    """The CLI prints one JSON object to stderr on failure; fall back to raw text."""
    for line in reversed((stderr or "").strip().splitlines()):
        try:
            info = json.loads(line)
        except ValueError:
            continue
        if isinstance(info, dict) and info.get("ok") is False:
            return CdrcaRenderError(
                f"CDRCA {info.get('stage', 'crash')} error rendering '{shot_id}': {info.get('message', '')}",
                stage=str(info.get("stage", "crash")),
            )
    return CdrcaRenderError(f"CDRCA failed rendering '{shot_id}'. stderr tail: {(stderr or '')[-1500:]}", "crash")


def _sanitize(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip()) or "shot"
