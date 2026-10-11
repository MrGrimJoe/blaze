# Blaze

**Write a story as plain text. Get an animated, voiced video.**

```
JOHN: Did you hear that?
MARY: It is just the wind.
[ENTER TIM 9.5 4.2]
TIM: Please don't be mad! I only came to find my kite.
```

Blaze turns a screenplay like this into an mp4 with characters, backdrops, speech bubbles, a voice for every character
and subtitles. It runs on your own computer, offline, with no account and no AI. If you want, an AI can write the
screenplay for you, but it never draws anything: **every frame is drawn by the [CDRCA](https://github.com/ISLAH-org/CDRCA)
animation engine from exact instructions**, so the same screenplay always gives the same video.

![The Blaze page: a screenplay on the left, the cast and scenes it understood on the right](docs/img/page.png)

## What Blaze is

Blaze is a **screenplay-to-video compiler**, not a video generator. Nothing is invented at render time.

1. You write a screenplay in a small, strict format (lines of dialogue plus a few stage commands).
2. Blaze checks it and tells you the exact line that is wrong, if any.
3. It draws the characters and backdrops, records a voice for each line, and works out the timing.
4. It writes one plain, readable CDRCA script per scene and renders every frame with CDRCA's own renderer.
5. It joins the scenes, voices and subtitles into one mp4.

You can open and edit the generated CDRCA scripts and render again, so nothing is a black box.

## What it can do

| | |
|---|---|
| **Scenes and dialogue** | Any number of scenes, any number of speakers, a narrator caption style, a title card with subtitle. |
| **Staging** | Characters walk in (`ENTER`), walk to a spot (`MOVE`), hop (`HOP`), walk out (`EXIT`), and you can `PAUSE`. Positions are exact numbers. Characters never stand on each other. |
| **Characters** | Drawn for you from exact traits (`gender`, `hairstyle`, `top`, `coat`, `hat`, `glasses`, `child` ...), with a mouth that moves while they speak. Or bring your own PNG or Blender model. |
| **Backdrops** | 6 places (street, room, warehouse, forest, beach, office) in 9 moods (day, sunset, night, dim, rain, storm, snow, night_rain, night_snow), drawn for you. Or bring your own image or Blender scene. |
| **Voices** | A different, stable voice per character (gender and age from their look), spoken at the speed you choose. Speech boxes reveal text in time with the voice. Or render silent. |
| **Subtitles** | An `.srt` file for every video. |
| **Output** | mp4 at the size and frame rate you choose (640x360 for quick drafts, 1920x1080 for the final). |
| **Editable** | Every video leaves a project folder with the generated CDRCA scripts, assets and audio. Change a number, run `blaze build`. |
| **A page and a command line** | `python blaze.py ui` opens a minimal page: write, see it understood as you type, make, watch, download. Or script it with `blaze make`. |
| **Blaze Studio** | A desktop window: describe a video loosely and it plans the shots, draws, renders and joins them. Includes an **offline demo** that needs no AI, no key and no GPU. |
| **Optional AI** | Describe a story and let your own Anthropic, Gemini or OpenAI account write the screenplay: one short scene, or a whole multi-scene story planned and checked step by step. No provider is chosen for you. |

## See it work

This is the bundled example, `tests/fixtures/sample_story.txt`, rendered by Blaze. Three scenes, three characters, voices on.

| Scene 1: street, night rain | Scene 2: inside the warehouse | Scene 3: the beach |
|---|---|---|
| ![](docs/img/scene-street.png) | ![](docs/img/scene-warehouse.png) | ![](docs/img/scene-beach.png) |

## Start in three minutes

**On Windows the easiest way is the installer**: download `Blaze_Setup_<version>.exe` (built by GitHub Actions, see
[docs/installer.md](docs/installer.md)), run it, and open **Blaze** from the Start menu. Python, Node.js, ffmpeg, the browser and
Windows voices are all inside it, and no administrator rights are needed.

**From source** (any system) you need **Python 3.9+**, **Node.js** and **ffmpeg**. Voices need **espeak-ng** (or `pip install pyttsx3` on Windows).

```
pip install -r requirements.txt
python blaze.py setup        # installs the renderer's headless browser (one time)
python blaze.py doctor       # checks that everything is in place
python blaze.py ui           # opens the page in your browser
```

In the page, press **start from an example**, then **Make video**. Pick **Draft** quality first: it is the fastest, and
a weak computer will thank you. The full walkthrough is in [Tutorial 1](docs/tutorials/01-your-first-video.md).

Prefer the command line?

```
python blaze.py make story.txt -o story.mp4 --res 960x540 --fps 20
```

## Learn it

| Tutorial | You will |
|---|---|
| [1. Your first video](docs/tutorials/01-your-first-video.md) | Install, open the page, make and watch a video. |
| [2. Writing a screenplay](docs/tutorials/02-writing-a-screenplay.md) | Learn every line type, with examples and the errors you will meet. |
| [3. Your own characters and backgrounds](docs/tutorials/03-your-own-art.md) | Use your own PNG, JPG or Blender models. |
| [4. Voices, timing and subtitles](docs/tutorials/04-voices-timing-subtitles.md) | Choose voices, speed, quality and understand how long things take. |
| [5. Writing with AI](docs/tutorials/05-writing-with-ai.md) | Choose a provider, write a scene or a whole story, and know what it costs and checks. |
| [6. Editing the CDRCA scripts](docs/tutorials/06-editing-the-cdrca-scripts.md) | Open what Blaze generated, change it and render again. |
| [7. Troubleshooting](docs/tutorials/07-troubleshooting.md) | Fix the problems people actually hit. |
| [8. Blaze Studio](docs/tutorials/08-blaze-studio.md) | Describe a video in a few sentences and let the desktop studio plan, draw and join it, with an offline demo that needs no AI. |

Reference: [screenplay format](docs/reference/screenplay.md) · [command line](docs/reference/cli.md) ·
[project folder](docs/reference/project-folder.md) · [how it works](docs/ARCHITECTURE.md) ·
[the Windows installer](docs/installer.md) · [seeing every screen](docs/screenshots.md) ·
[the desktop studio](docs/studio.md)

## Why you can trust the result

- **Exact, never guessed.** Positions are numbers, looks are `key=value`, places and moods are fixed names. Words like
  `left`, `tall` or `spooky` are errors with a message that says what to write instead, never silently interpreted.
- **Checked before anything is drawn.** The screenplay is parsed first, line by line. A typo costs a second, not a render.
- **Repeatable.** Same screenplay, same settings, same video.
- **AI is boxed in.** When AI writes for you, a parser checks every step and sends its complaint back to the model. The
  cast and every backdrop are fixed by the plan, so characters and places stay consistent across scenes. A scene that never
  passes stops the run instead of shipping something broken.

## What it is not

Blaze makes 2D, front-facing characters on drawn backdrops, one speaker at a time. It is not a realistic video model, it
has no camera moves, weather particles or lip-sync to individual sounds yet (the mouth flaps while a character speaks), and
characters face the viewer. Features CDRCA itself would need first are listed as requests in
[docs/CDRCA-PROPOSALS.md](docs/CDRCA-PROPOSALS.md); Blaze does not fake them.

## Status

Verified on Linux (Python 3.12, Node 22, Chromium with software rendering, ffmpeg, espeak-ng): the CDRCA tests (8 + 4),
Blaze's Python tests (145 passed, 10 skipped: the ones that need Blender or the Windows voice, which CI covers), the desktop studio's tests (344 passed, 2 skipped),
and sample stories rendered end to end with voices. An earlier session also
verified `asset add` against real Blender 4.0.2.

Not run yet, because they need machines other than the one this was written on: Windows and macOS, the Windows voices
(pyttsx3), Blender on a CI machine, the AI writer against a real provider, and the Windows installer. **They are all set up as
GitHub Actions** ([`ci.yml`](.github/workflows/ci.yml), [`build-blaze-installer.yml`](.github/workflows/build-blaze-installer.yml),
[`live-ai.yml`](.github/workflows/live-ai.yml)) and have not run yet; the first run may need small fixes. The files they use, and the
installed app's end-to-end check, were verified here against a staged copy of the app. The
[**Screens** workflow](docs/screenshots.md) photographs every screen so you can check the interface by eye.
Rendering without a GPU is slow: the 58-second example takes about a minute at Draft quality on a one-core test machine.

## Layout

```
blaze.py, blaze/      parser, compiler (screenplay -> CDRCA), art, voices, Blender bridge, library, pipeline, CLI, the page
blaze/ui_assets/      the page (one HTML file)
blaze_app.pyw         starts Blaze without a console window (the installer's shortcut runs this)
blender/              the script that runs inside Blender
cdrca/                CDRCA = upstream 6b8a742 + the reviewed commits in cdrca-patches/
cdrca-lib/            atoms.cdrca: the Picture and Words props, written in CDRCA itself
cdrca-patches/        the small changes made to CDRCA, as `git am` patches
studio/               Blaze Studio (the PyQt6 desktop window and its pipeline) and its own Windows installer
installer/            the Blaze Windows installer: staging script, Inno Setup script, icon and pictures, end-to-end check
tools/                screenshot scripts, the documentation checker, the live AI check
.github/workflows/    tests on three systems, the installer, the screenshots, the real-AI check
docs/                 tutorials, reference, architecture
tests/                Blaze's tests (CDRCA's are in cdrca/tests, the studio's in studio/tests)
```

```
python -m pytest tests                          # Blaze: real renders, voices and Blender are used when installed
(cd studio && python -m pytest tests)           # the desktop studio
(cd cdrca && node tests/transpiler.test.js && node tests/render.test.js)
python tools/check_docs.py                      # links work, every screenplay in the docs parses
```

## Licenses

Released under the Islamic Open Source License (IOSL), the license of the CDRCA project it is built on: see
[LICENSE.md](LICENSE.md) and [LICENSES.md](LICENSES.md). Software that Blaze uses or bundles keeps its own license:
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).
