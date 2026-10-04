"""
The Blaze pipeline:  screenplay text -> art -> voices -> .cdrca scenes -> frames -> mp4 (+ .srt)

Everything lands in a project folder (<output>.blaze/) so you can open the generated .cdrca files,
edit them by hand, and rebuild with `blaze build <project>`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import re
import shutil as _shutil

from . import art, compiler, voice as voice_mod
from .library import Library
from .screenplay import Screenplay, parse

REPO = Path(__file__).resolve().parent.parent
RENDER_SCRIPT = REPO / "cdrca" / "Back-end" / "Render" / "render.js"


class BlazeError(Exception):
    def __init__(self, message: str, stage: str = "pipeline", shot: str = ""):
        super().__init__(message)
        self.stage, self.shot = stage, shot


@dataclass
class Options:
    width: int = 1280
    height: int = 720
    fps: int = 24
    voice: str = "auto"            # auto | espeak | pyttsx3 | off
    wpm: int = 150                 # speaking speed (slower = better for learners; ~110)
    style: Optional[str] = None    # bubbles | subtitles | both (overrides STYLE:)
    workers: int = field(default_factory=lambda: max(1, min(4, os.cpu_count() or 2)))
    keep_frames: bool = False
    node: str = "node"
    library: Optional[Path] = None   # your characters/backdrops (default: ./library next to the screenplay, then the cwd)
    progress: Callable[[str], None] = print


@dataclass
class Result:
    video: Path
    project: Path
    duration: float
    shots: int
    srt: Optional[Path]
    warnings: List[str]


def _need(binary: str, hint: str) -> None:
    if shutil.which(binary) is None:
        raise BlazeError(f"'{binary}' was not found on PATH. {hint}", "setup")


def check_tools(opts: Options) -> None:
    _need(opts.node, "Install Node.js from https://nodejs.org")
    _need("ffmpeg", "Install ffmpeg (https://ffmpeg.org) and make sure it is on PATH")
    if not RENDER_SCRIPT.exists():
        raise BlazeError(f"Renderer not found at {RENDER_SCRIPT}", "setup")


# --------------------------------------------------------------------------- build the project
def create_project(text: str, project: Path, opts: Options, base_dir: Optional[Path] = None) -> Tuple[Screenplay, dict]:
    sp = parse(text)
    if opts.style: sp.style = opts.style
    log = opts.progress
    for d in ("assets", "audio", "scenes"):
        (project / d).mkdir(parents=True, exist_ok=True)
    (project / "screenplay.txt").write_text(text, encoding="utf-8")

    chars = sp.characters()
    log(f"Characters: {', '.join(chars) or '(none)'}   Scenes: {len(sp.scenes)}")
    lib = Library.default(opts.library, base_dir, project)
    apps: Dict[str, art.Appearance] = {}
    for c in chars:
        desc = sp.cast.get(c, "")
        m = re.search(r"asset:\s*([\w .\-]+)", desc, re.I)
        hint = m.group(1).strip() if m else c
        look = re.sub(r"asset:\s*[\w .\-]+,?", "", desc, flags=re.I).strip(" ,")
        found = lib.character(hint)
        if m and found is None:
            raise BlazeError(f"CAST: {c} asks for asset '{hint}' but there is no library/characters/{hint}.png "
                             f"(looked in: {', '.join(str(r) for r in lib.roots)}). Add it with: blaze asset add <file> --name {hint}", "assets")
        apps[c] = art.appearance_for(c, look)           # gender / child still come from the description (voice, scale)
        if found is not None:
            log(f"  {c}: using library asset {found.name}")
            for suffix in ("", "_talk", "_blink"):
                f = found.with_name(found.stem + suffix + found.suffix)
                if f.exists():
                    _shutil.copyfile(f, project / "assets" / f"{art.slug(c)}{suffix}.png")
        else:
            art.make_character(c, desc, project / "assets")

    speaker = voice_mod.get_voice(opts.voice, opts.wpm)
    log(f"Voice: {speaker.name}")
    jobs = []  # (scene index, beat index, who, text, wav)
    for si, sc in enumerate(sp.scenes, 1):
        for bj, b in enumerate(sc.beats):
            if b.kind in ("say", "narr"):
                who = b.who if b.kind == "say" else "Narrator"
                a = apps.get(who)
                prof = voice_mod.profile_for(who, a.gender if a else "m", a.child if a else False)
                jobs.append((si, bj, prof, b.text, project / "audio" / f"s{si:02d}_{bj:02d}.wav"))

    def synth(job):
        si, bj, prof, txt, wav = job
        dur = speaker.synth(txt, prof, wav)
        return (si, bj), ((wav, dur) if dur is not None else (None, voice_mod.estimate_seconds(txt, opts.wpm)))

    with ThreadPoolExecutor(max_workers=opts.workers) as ex:
        info = dict(ex.map(synth, jobs))

    backdrops: Dict[str, Path] = {}
    shots: List[compiler.Shot] = []
    first_mood = art.mood_from(sp.scenes[0].heading if sp.scenes else "")
    if sp.title:
        shots.append(compiler.compile_title(0, sp, project / "scenes", first_mood))
    notes: List[str] = []
    for si, sc in enumerate(sp.scenes, 1):
        place, mood = art.place_from(sc.heading), art.mood_from(sc.heading)
        if sc.backdrop:
            src = lib.backdrop(sc.backdrop, base_dir)
            if src is None:
                raise BlazeError(f"BACKDROP: '{sc.backdrop}' was not found (looked for library/backdrops/{art.slug(sc.backdrop)}.png "
                                 f"and a file by that path). Add it with: blaze asset add <file> --as backdrop --name {sc.backdrop}", "assets")
            key = "custom_" + art.slug(sc.backdrop)
            if key not in backdrops:
                dst = project / "assets" / f"bg_{key}.png"
                from PIL import Image as _I
                im = _I.open(src).convert("RGB")
                tw, th = 1920, 1080
                k = max(tw / im.width, th / im.height)
                im = im.resize((max(tw, round(im.width * k)), max(th, round(im.height * k))))
                l, t = (im.width - tw) // 2, (im.height - th) // 2
                im.crop((l, t, l + tw, t + th)).save(dst)
                backdrops[key] = dst
        else:
            key = f"{place}_{mood.name}"
            if key not in backdrops:
                backdrops[key] = art.make_backdrop(place, mood, project / "assets" / f"bg_{key}.png")
        li = {bj: v for (s, bj), v in info.items() if s == si}
        shots.append(compiler.compile_scene(si, sc, sp, apps, project, li, backdrops[key], opts.wpm, opts.width / opts.height))

    for s_ in shots:
        notes += [f"{s_.name}: {n}" for n in s_.notes]
    sp.warnings += notes
    manifest = {
        "version": 1, "title": sp.title, "fps": opts.fps, "width": opts.width, "height": opts.height,
        "shots": [{
            "name": s.name, "cdrca": str(s.cdrca.relative_to(project)).replace("\\", "/"), "duration": round(s.duration, 3),
            "mood": s.mood, "title": s.title, "skip": s.skip, "notes": s.notes,
            "audio": [[round(t, 3), str(w.relative_to(project)).replace("\\", "/")] for t, w in s.audio],
            "subs": [[round(a, 3), round(b, 3), who, text] for a, b, who, text in s.srt],
        } for s in shots],
    }
    (project / "project.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    return sp, manifest


# --------------------------------------------------------------------------- render the project
def _run_render(shot: dict, project: Path, manifest: dict, opts: Options) -> Path:
    fps = manifest["fps"]
    frames = max(1, round(shot["duration"] * fps))
    out = project / "frames" / shot["name"]
    if out.exists(): shutil.rmtree(out)
    cmd = [opts.node, str(RENDER_SCRIPT), str(project / shot["cdrca"]), "--out", str(out), "--fps", str(fps),
           "--width", str(manifest["width"]), "--height", str(manifest["height"]),
           "--from", str(shot.get("skip", 0)), "--duration", str(frames / fps), "--format", "jpeg"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        stage, msg = "render", (r.stderr or r.stdout)[-600:]
        for line in reversed((r.stderr or "").strip().splitlines()):
            try:
                j = json.loads(line)
                if isinstance(j, dict) and j.get("ok") is False:
                    stage, msg = j.get("stage", "render"), j.get("message", msg); break
            except ValueError:
                pass
        raise BlazeError(f"{shot['name']} ({shot['cdrca']}): {msg}", stage, shot["name"])
    return out


def _encode_shot(shot: dict, frames_dir: Path, project: Path, manifest: dict) -> Path:
    fps = manifest["fps"]
    frames = len(list(frames_dir.glob("*.jpg")))
    seconds = frames / fps
    wav = project / "audio" / f"{shot['name']}_track.wav"
    voice_mod.build_track([(t, project / w) for t, w in shot["audio"]], seconds, wav)
    out = project / "shots" / f"{shot['name']}.mp4"
    out.parent.mkdir(exist_ok=True)
    fade = f"fade=t=in:st=0:d=0.25,fade=t=out:st={max(0.0, seconds - 0.35):.3f}:d=0.35"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(frames_dir / "%06d.jpg"), "-i", str(wav),
           "-vf", fade, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2", "-shortest", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise BlazeError(f"ffmpeg failed on {shot['name']}: {r.stderr[-400:]}", "encode", shot["name"])
    return out


def _srt_time(s: float) -> str:
    ms = int(round(s * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); sec, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def render_project(project: Path, out_mp4: Path, opts: Options) -> Result:
    check_tools(opts)
    manifest = json.loads((project / "project.json").read_text(encoding="utf-8"))
    log = opts.progress
    shots = manifest["shots"]
    log(f"Rendering {len(shots)} scene(s) at {manifest['width']}x{manifest['height']} {manifest['fps']}fps "
        f"({opts.workers} at a time)...")

    def one(shot):
        frames_dir = _run_render(shot, project, manifest, opts)
        mp4 = _encode_shot(shot, frames_dir, project, manifest)
        if not opts.keep_frames: shutil.rmtree(frames_dir, ignore_errors=True)
        log(f"  done: {shot['name']}")
        return mp4

    with ThreadPoolExecutor(max_workers=opts.workers) as ex:
        mp4s = list(ex.map(one, shots))
    if not opts.keep_frames: shutil.rmtree(project / "frames", ignore_errors=True)

    lst = project / "shots" / "list.txt"
    lst.write_text("".join("file '%s'\n" % p.resolve().as_posix().replace("'", r"'\''") for p in mp4s), encoding="utf-8")
    out_mp4 = Path(out_mp4); out_mp4.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
                        "-movflags", "+faststart", str(out_mp4)], capture_output=True, text=True)
    if r.returncode != 0:
        raise BlazeError("ffmpeg concat failed: " + r.stderr[-400:], "encode")

    srt_lines, offset, n = [], 0.0, 1
    for s in shots:
        for a, b, who, text in s["subs"]:
            srt_lines.append(f"{n}\n{_srt_time(offset + a)} --> {_srt_time(offset + b)}\n{(who.upper() + ': ') if who else ''}{text}\n")
            n += 1
        offset += max(1, round(s["duration"] * manifest["fps"])) / manifest["fps"]
    srt = None
    if srt_lines:
        srt = out_mp4.with_suffix(".srt"); srt.write_text("\n".join(srt_lines), encoding="utf-8")
    return Result(out_mp4, project, offset, len(shots), srt, [])


def make(text: str, out_mp4: Path, opts: Options, project: Optional[Path] = None, base_dir: Optional[Path] = None) -> Result:
    check_tools(opts)
    out_mp4 = Path(out_mp4)
    project = Path(project) if project else out_mp4.with_suffix(".blaze")
    project.mkdir(parents=True, exist_ok=True)
    sp, _ = create_project(text, project, opts, base_dir)
    for w in sp.warnings:
        opts.progress("  note: " + w)
    res = render_project(project, out_mp4, opts)
    res.warnings = sp.warnings
    return res
