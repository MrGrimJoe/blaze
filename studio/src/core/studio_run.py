"""
One production run, start to finish, with no UI in it: prompt -> plan -> assets -> scenes -> frames -> one mp4.

The window runs this in a background thread and listens to the events; tests and scripts call it directly.

    result = run_studio(config, "a detective finds a clue", events=RunEvents(on_stage=print))
    result = run_studio(config, "", demo=True)           # the offline demo: no AI, no key, no GPU
"""
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

STAGES = ("planning", "assets", "composing", "rendering", "assembling")
_TASK_STAGE = {"generate_asset": "assets", "compose_scene": "composing", "render": "rendering"}


class StudioRunError(Exception):
    """A run could not finish. The message is written for the person using the window."""


class RunCancelled(Exception):
    pass


@dataclass
class RunEvents:
    """Everything optional. Called from the thread that runs the pipeline."""
    on_stage: Optional[Callable[[str, str], None]] = None          # (stage, detail)
    on_plan: Optional[Callable[[List[Dict[str, Any]]], None]] = None   # [{shot_id, description, characters, seconds}]
    on_shot: Optional[Callable[[str, str, str], None]] = None      # (shot_id, status, detail)
    on_progress: Optional[Callable[[int, int], None]] = None       # (steps done, steps in all)


@dataclass
class RunResult:
    video: Path
    shots: int
    seconds: float
    demo: bool = False
    failures: List[str] = field(default_factory=list)


def _emit(fn, *args):
    if fn:
        try:
            fn(*args)
        except Exception:                      # a listener's mistake must never break a run
            logger.exception("event listener failed")


def run_studio(config: Dict[str, Any], prompt: str, *, demo: bool = False,
               events: Optional[RunEvents] = None, cancel: Optional[threading.Event] = None) -> RunResult:
    from src.core.pipeline_factory import build_pipeline, demo_config
    from src.providers.provider_factory import validate_provider_config

    ev = events or RunEvents()
    cancel = cancel or threading.Event()
    cfg = demo_config(config) if demo else config

    if not demo:
        if not (prompt or "").strip():
            raise StudioRunError("Write what the video should be about first.")
        ok, why = validate_provider_config(cfg)
        if not ok:
            raise StudioRunError(f"Choose an AI provider first ({why}). Use Change provider.")

    _emit(ev.on_stage, "planning", "Preparing" if demo else "Asking the AI for a shot plan")
    try:
        director, orchestrator, _world, _assets = build_pipeline(cfg)
    except Exception as e:
        raise StudioRunError(f"The pipeline could not start: {e}") from e

    try:
        plan = director.generate_production_plan(prompt or "Offline demo")
    except Exception as e:
        raise StudioRunError(f"The AI's shot plan could not be used: {e}") from e
    tasks = director.create_task_schedule(plan)
    shots = [{"shot_id": s.shot_id, "description": s.scene_description, "characters": list(s.characters),
              "seconds": float(s.duration_seconds)} for s in plan.shots]
    _emit(ev.on_plan, shots)
    for s in shots:
        _emit(ev.on_shot, s["shot_id"], "queued", "")
    if cancel.is_set():
        raise RunCancelled()

    orchestrator.load_task_schedule(tasks)
    total = len(tasks)

    def shot_update(shot_id, status, details):
        _emit(ev.on_shot, shot_id, status, details)

    def progress(done, _total):
        _emit(ev.on_progress, done, total)
        if cancel.is_set():
            orchestrator.cancel()
        elif done < total:
            stage = _TASK_STAGE.get(tasks[done].task_type)
            if stage:
                _emit(ev.on_stage, stage, "")

    orchestrator.on_shot_update = shot_update
    orchestrator.on_progress = progress
    first = _TASK_STAGE.get(tasks[0].task_type) if tasks else None
    if first:
        _emit(ev.on_stage, first, "")
    orchestrator.run_pipeline()
    if cancel.is_set():
        raise RunCancelled()

    if orchestrator.failures:
        lines = [f"{f.shot_id} ({f.task_type}): {f.error}" for f in orchestrator.failures[:3]]
        more = f" and {len(orchestrator.failures) - 3} more" if len(orchestrator.failures) > 3 else ""
        raise StudioRunError("Some steps failed: " + "; ".join(lines) + more)

    frames = {s["shot_id"]: orchestrator._rendered_frames[s["shot_id"]] for s in shots if s["shot_id"] in orchestrator._rendered_frames}
    if not frames:
        raise StudioRunError("Nothing was rendered, so there is no video to assemble.")
    _emit(ev.on_stage, "assembling", "Joining the shots into one video")
    from src.integrations.ffmpeg.video_assembler import VideoAssembler
    try:
        video = VideoAssembler(cfg).assemble(frames, output_name=f"video_{time.strftime('%Y%m%d_%H%M%S')}.mp4")
    except Exception as e:
        raise StudioRunError(f"The shots were drawn but could not be joined into a video: {e}") from e
    return RunResult(video=Path(video), shots=len(frames), seconds=sum(s["seconds"] for s in shots), demo=demo)
