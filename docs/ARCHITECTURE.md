# How Blaze works

Blaze is a pipeline of small, separately testable steps. Each step turns exact input into exact output; the only step that can
use AI is the optional first one, and what it produces is checked like anything you would type yourself.

```
idea ──(optional AI: ai.py)──┐
                             ▼
screenplay text ──▶ parse (screenplay.py) ──▶ art + voices ──▶ compile (compiler.py) ──▶ render (CDRCA) ──▶ encode ──▶ mp4 + srt
                                                 art.py            one .cdrca per scene    cdrca/ via node    ffmpeg
                                                 library.py
                                                 voice.py
                                                 blender.py
```

## The steps

| Step | Module | What it does |
|---|---|---|
| Write (optional) | `ai.py` | Asks your chosen provider for a plan and then one scene at a time; checks every answer with the parser; the program, not the model, fixes the cast and the backdrops. |
| Parse | `screenplay.py`, `looks.py` | Turns text into scenes and beats (`say`, `narr`, `enter`, `exit`, `move`, `hop`, `pause`), the cast with its voices, and the text looks. Shorthand lines expand to an explicit core (`to_core`). Rejects anything inexact or unknown with a line number. Collects warnings. See [Language design](LANGUAGE-DESIGN.md). |
| Characters and backdrops | `art.py`, `library.py`, `blender.py` | Draws characters from exact looks and backdrops from `gen:<place>:<mood>` with Pillow, or takes your own pictures from the library (PNG/JPG, or `.blend` rendered through Blender). |
| Voices | `voice.py` | Synthesises each line with the engine the character asked for (`voice=espeak:...`, `pyttsx3:...`, `piper:...`, `off`), or the first engine found, or estimates its length when silent. Without a `voice=` the voice depends on the name and on `gender` and `child`. |
| Compile | `compiler.py` | Works out positions and timing, then writes one CDRCA script per scene: which props exist and, for every beat, what each prop does. |
| Render | `cdrca/` (CDRCA) via Node.js | CDRCA's own transpiler and three.js renderer, run headless in Chromium by `Back-end/Render/render.js`, draw every frame of the script. |
| Encode and join | `pipeline.py` | ffmpeg turns each scene's frames and its sound track into an mp4, joins the scenes, and the `.srt` is written from the timings. |
| Everything around it | `cli.py`, `ui.py`, `launcher.py` | The command line; the local page; and the launcher the Windows shortcut runs (it makes the bundled tools findable, keeps your files in your own folders, and closes Blaze when the page is closed). |

`pipeline.py` ties them together and writes the project folder ([reference](reference/project-folder.md)).

## Why scripts per scene, and why CDRCA

Blaze does not draw frames itself. It writes CDRCA scripts and lets CDRCA render them, so what you see is exactly what the
scripts say, and you can open, read and edit the scripts. Blaze adds nothing next to CDRCA: there is no plugin system, and no
prop is built into CDRCA for Blaze. The two props Blaze uses, `Picture` and `Words`, are written *in CDRCA* in
[`cdrca-lib/atoms.cdrca`](../cdrca-lib/atoms.cdrca) and imported by every scene ([atoms reference](reference/atoms.md)).

## Timing

The compiler gives each beat a length (a spoken line is the voice's length plus 0.4 s; walking is distance divided by 2.4
units a second) and writes it as one CDRCA action with a 1 ms transition, which is a hard cut. A scene's sound track is
built from the voice files at the same offsets, so picture and sound stay together by construction.

## What changed in CDRCA

Blaze runs CDRCA as it is, plus eleven small commits (bug fixes, a headless renderer, a fix so that library files do not
become empty scenes). They are kept as `git am` patches in [`cdrca-patches/`](../cdrca-patches/) and described in
[CDRCA-CHANGES.md](CDRCA-CHANGES.md). What Blaze would like CDRCA to gain, for its owner to decide, is in
[CDRCA-PROPOSALS.md](CDRCA-PROPOSALS.md); none of it has been implemented or faked.

## The page

`blaze/ui.py` is a small local web server (standard library only) bound to `127.0.0.1`. It serves one HTML file, checks the
screenplay as you type with the same parser, runs the same `make` as the command line in a background thread (one video at a
time), and serves the result. It also stores your provider choice in `studio/config.yaml` for the AI writer.

The page (`blaze/ui_assets/index.html`, plain HTML and JavaScript, no framework) has three modes that share one screenplay:
**Editor** (the code, line numbers, the error line marked), **Smart** (the outline, voices and library panels beside the code) and
**Running** (the finished video and a timeline). Switching modes only changes which parts are shown; `#editor`, `#smart` and
`#running` in the URL open one. There is no build step, so a bug is found by opening the file.

Two things beyond checking and making:

- **The library.** `GET /api/library` lists your characters and backdrops (and whether Blender is installed); `POST
  /api/library/add?kind=&name=&filename=[&variant=]` takes the file itself as the request body (a PNG/JPG/WebP is checked and
  converted, a `.blend` is rendered by Blender into `name.png`, `name_talk.png`, `name_blink.png`); `POST /api/library/remove`;
  `GET /api/library/img/<characters|backdrops>/<name>.png` serves a picture. Files go to the first library folder (`--library`, or
  `./library`; the installed app uses `Documents\Blaze\library`), the same folders `blaze make` reads, so the page and the command
  line see the same characters. `/api/check` reports a `CAST` whose `asset=` is not in the library, on that line.
- **The timeline.** When a video finishes, `/api/job/<id>` carries `timeline`: the scenes and every spoken line on the finished
  video's own clock, computed from `project.json` with the same offsets the subtitle file uses. Running mode draws only from that.

## Tests

| Where | What |
|---|---|
| `tests/` | the parser, art, compiler, voices, library, Blender bridge, the page's server, the AI writer (with scripted stand-ins), and real renders when node, Chromium, ffmpeg and espeak-ng are installed (including pixel checks that speech boxes stay on screen) |
| `cdrca/tests/` | CDRCA's transpiler and renderer |
| `studio/tests/` | the desktop studio's pipeline, providers and first-run window |
