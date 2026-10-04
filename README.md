# Blaze

**Write a short screenplay (or let an AI write it). Get an animated video with voices, speech bubbles and subtitles.**
Every scene is a real [CDRCA](cdrca/) script, rendered by CDRCA's own renderer. No API key is needed to make a video;
an LLM is optional and only writes the screenplay.

> `blaze make`/`blaze build` (writing the screenplay yourself) need nothing beyond this repo. The
> optional `blaze ai` subcommand (writing the screenplay *for* you) is the one exception — it
> imports its LLM provider code from [BlazEng](https://github.com/MrGrimJoe/BlazEng), a separate
> repo, at runtime. Clone it, copy its `config.yaml.example` to `config.yaml` with an API key, and
> pass `--config /path/to/BlazEng/config.yaml`.

```
 idea ──(optional LLM)──▶ screenplay.txt ──▶ art + voices ──▶ one .cdrca per scene ──▶ CDRCA renders frames ──▶ mp4 + srt
                              ▲                                      ▲
                      you write this                 plain CDRCA: edit it, then `blaze build`
```

## How it uses CDRCA

Blaze does **not** change CDRCA's language, and adds no extension system or mini-language next to it. A generated scene is
ordinary CDRCA: `use <prop>(...) as <alias>`, `add new action ...`, `def ACTION ...`, with the standard props
(`ImageProp`, `TextProp`). Each thing that happens in the screenplay is one CDRCA action:

```
use ...exampleProps.ImageProp("../assets/john.png", -2.4, -0.1, 4.4, 0, "../assets/john_talk.png") as c_John
use ...exampleProps.TextProp(-2.4, 2.3, 0.32, "bubble") as say_John_1
add new action a001 3200 1
def ACTION a001 c_John talk ""
def ACTION a001 say_John_1 say "Did you hear that?"
```

The few things CDRCA needed (two bug fixes, a negative-number parser fix, `ImageProp`/`TextProp`, a headless render
script) are **small, separate, reviewable commits** in [`cdrca-patches/`](cdrca-patches/) on top of the upstream commit they
were made against. `cdrca/` in this repo is upstream plus exactly those commits (without the editor and `node_modules`).
Anything CDRCA lacks (camera moves, weather, animated subtitles, 3D models) is **not faked**; it is listed as a request for
the language's owner in [docs/CDRCA-PROPOSALS.md](docs/CDRCA-PROPOSALS.md).

## Quick start

Needs **Python 3.9+**, **Node.js**, **ffmpeg**. Optional: **espeak-ng** (or `pip install pyttsx3`) for voices, **Blender** for `.blend` assets.

```
pip install -r requirements.txt
python blaze.py setup        # installs playwright + headless Chromium (CDRCA's package.json is not modified)
python blaze.py doctor       # checks everything
python blaze.py make story.txt -o story.mp4     # story.txt is your screenplay (format below)
```

## Make a video

```
python blaze.py make story.txt -o story.mp4
python blaze.py make story.txt --style subtitles --pace slow         # caption bar instead of bubbles, slower voices
python blaze.py make story.txt --res 1920x1080 --fps 30
python blaze.py ai "two friends find a message in a bottle" --level A2 --config /path/to/BlazEng/config.yaml
```

Each run leaves an editable project folder (`story.blaze/`) and an `.srt`. Edit `scenes/*.cdrca`, then `python blaze.py build story.blaze`.

### The screenplay format

```
TITLE: The Lost Key
SUBTITLE: a very short story
STYLE: bubbles                 # bubbles | subtitles (caption bar) | both
CAST: JOHN = man, detective, red coat, glasses
CAST: ROBO = asset:robo        # use your own library/characters/robo.png

SCENE: rainy street at night   # or:  INT. WAREHOUSE - NIGHT
BACKDROP: my_lab               # optional: your own background
JOHN: Did you hear that?
MARY (nervous): It's just the wind.
> Narrator captions start with ">".
[ENTER TIM right]  [EXIT TIM left]  [MOVE JOHN center]  [HOP MARY]  [PAUSE 1]
```

`[CAMERA ...]` and `[WEATHER ...]` are accepted but **skipped with a note**: CDRCA has no camera or weather yet.

## Example

[`examples/the-warehouse`](examples/the-warehouse) is a short film made with Blaze — the
screenplay, the rendered `the_warehouse.mp4` and `.srt`, and the full project folder (so you can
open it in `blaze build` and see exactly how the pieces fit together).

## Your own designs and backgrounds (PNG or Blender)

```
python blaze.py asset add hero.png                       # transparent PNG -> character (hero_talk.png / hero_blink.png are picked up)
python blaze.py asset add forest.jpg                     # opaque image -> backdrop (cover-cropped to 16:9)
python blaze.py asset add robot.blend --name robo        # rendered through Blender into robo.png / robo_talk.png / robo_blink.png
python blaze.py asset add lab.blend --as backdrop        # one frame from the scene's camera
python blaze.py asset list
```

Then `CAST: ROBO = asset:robo` / `BACKDROP: lab` (or just name a character like a library asset). For a `.blend` character, shape
keys named `talk` and `blink` drive the mouth-open and eyes-closed pictures. The subject is framed in front view with its feet at
the bottom edge, rendered with Cycles on the CPU (no GPU or display needed). The library lives in `./library` next to your
screenplay (or `--library`). Blender only produces images; nothing in CDRCA changes.

## Layout

```
blaze.py, blaze/      screenplay parser, compiler (screenplay -> CDRCA), generated art, voices, Blender bridge, asset library, CLI
blender/              blaze_blender.py: the script that runs inside Blender
cdrca/                CDRCA = upstream + the reviewed commits in cdrca-patches/
cdrca-patches/        git format-patch series for CDRCA (apply with `git am`)
docs/                 CDRCA-PROPOSALS.md
examples/             the-warehouse: a short film made with blaze, screenplay + rendered mp4/srt included
tests/                Blaze tests; cdrca/tests has CDRCA's
```

[BlazEng](https://github.com/MrGrimJoe/BlazEng), a separate repo, has an optional CDRCA render
backend (`render_backend: cdrca`) and is also what `blaze ai` needs for LLM support (see above).

## Tests

```
python -m pytest tests                                   # real renders/Blender are used when installed, skipped otherwise
node cdrca/tests/transpiler.test.js && node cdrca/tests/render.test.js
```

## Status

Tested on Linux (Python 3.12, Node 22, Chromium via Playwright with software GL, ffmpeg, espeak-ng, Blender 4.0.2 with
Cycles). Not tested: Windows/macOS, pyttsx3 voices, `blaze ai` against a real LLM (tested with a fake provider), the CI
workflow, the studio's Qt UI. Software-GL rendering is slow (a 60 s video at 960x540 takes several minutes per core).
The Ubuntu build of Blender has no denoiser; Blaze retries without it automatically.

Not supported yet, because CDRCA itself would need it first (see the proposals): camera moves, animated weather, mood
tinting, word-by-word subtitles and blinking.

## Licenses

See [LICENSES.md](LICENSES.md). `cdrca/` is IOSL; the Blaze code itself is MrMIB License v1.0, see [LICENSE](LICENSE). BlazEng (separate repo) has its own.
