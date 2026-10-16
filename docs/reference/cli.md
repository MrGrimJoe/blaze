# Command line reference

Run as `python blaze.py <command>` (on Windows also `blaze <command>`). `python blaze.py --version` prints the version and
`python blaze.py <command> --help` lists a command's options.

Exit status: `0` success; `2` Blaze stopped with a message (a screenplay error, a missing tool, an AI problem); `1` for
`doctor` and `setup` when something needed is missing.

## `make`: screenplay to video

```
python blaze.py make story.txt [-o story.mp4] [options]
```

Reads the screenplay, checks it, makes the art and voices, renders, and writes the video, `<name>.srt`, and the project
folder `<name>.blaze/` (or the folder given with `--project`).

## `build`: render an edited project again

```
python blaze.py build story.blaze [-o story.mp4] [--voice ...] [--workers N] [--keep-frames] [--node PATH] [--library DIR]
```

Re-renders every scene script in the project folder and joins the audio already in it. Size and frame rate come from the
project's `project.json`; `build` has no `--res` or `--fps`. See [Tutorial 6](../tutorials/06-editing-the-cdrca-scripts.md).

## `ai`: describe a story, get a video

```
python blaze.py ai "two friends find a message in a bottle" [options]
```

Your chosen provider writes a screenplay (it is saved as `<first words>.txt` next to the video), then the video is made.
Needs a provider chosen; see [Tutorial 5](../tutorials/05-writing-with-ai.md).

| Option | Meaning |
|---|---|
| `--scenes N` | number of scenes, 2 to 8 (default 4) |
| `--lines N` | spoken lines per scene (default 5; with `--quick` it is the total, default 14) |
| `--quick` | one request for a short screenplay instead of a plan plus one request per scene |
| `--level A2` | ask for simple vocabulary at that language level |
| `--config PATH` | use another `config.yaml` (default `studio/config.yaml`) |

All the options common to `make` also apply.

## `ui`: the page

```
python blaze.py ui [--port 8765] [--no-browser] [--out DIR] [--library DIR]
```

Serves the page on `127.0.0.1` only (requests from any other host name are refused) and opens it in your browser. Videos
are kept in `--out` (default `./blaze-videos`). Stop it with Ctrl+C.

The page has three modes, **Editor**, **Smart** and **Running** (open one directly with `http://127.0.0.1:8765/#editor`). Characters and
backdrops you add in Smart are saved in `--library` (default `./library`), the same place `blaze make` and `blaze asset` use.

## `expand`: see what the shorthand means

```
python blaze.py expand story.txt [-o story.core.txt]
```

Prints the screenplay in its explicit core form (`SPEAK`, `NARRATE`, one `CAST:` line per character, every `DEFINE LOOK`).
The result is a screenplay too, and makes the same video. Warnings go to the error stream. See the
[screenplay reference](screenplay.md).

## `voices`: choose a voice for a character

```
python blaze.py voices [--engine espeak|pyttsx3|piper] [--all]
python blaze.py voices --voice espeak:en-gb+f2 [--say "Hello"] [--gender m|f] [--rate 140] [--pitch 60] [-o sample.wav]
```

The first form lists the engines (and says how to install the ones that are missing) and the voices each offers; the second
plays a sample of one voice to a wav file. Use what you find in a screenplay as `CAST: NAME voice=<engine>:<voice>`. The page
does the same with a drop-down and a Play button for every character. See
[Tutorial 4](../tutorials/04-voices-timing-subtitles.md).

## `asset`: your own characters and backdrops

```
python blaze.py asset add FILE [--name NAME] [--as character|backdrop] [--library DIR]
                               [--blender PATH] [--samples N] [--yaw DEGREES]
python blaze.py asset list [--library DIR]
```

See [Tutorial 3](../tutorials/03-your-own-art.md). With no `--as`, a `.blend` file and any image with transparency become
characters, and an opaque image becomes a backdrop.

## `setup` and `doctor`

```
python blaze.py setup      # npm install playwright, then download headless Chromium (inside the cdrca folder)
python blaze.py doctor     # checks Python, Pillow, Node.js, the renderer's browser, ffmpeg, voices and Blender
```

`doctor` marks required tools `OK` or `!!` (with the fix after an arrow) and optional ones `--`. It exits `1` if a required
tool is missing. `setup` does not change CDRCA's own `package.json`.

## Options common to `make`, `build` and `ai`

| Option | Default | Meaning |
|---|---|---|
| `-o`, `--output FILE` | `<name>.mp4` | the video to write |
| `--res WxH` | `1280x720` | frame size (not in `build`) |
| `--fps N` | `24` | frames per second (not in `build`) |
| `--voice MODE` | `auto` | `auto`, `espeak`, `pyttsx3` or `off` |
| `--wpm N` | `150` | speaking speed in words per minute (about 105 is slow and clear) |
| `--workers N` | up to 4, by CPU count | scenes rendered at once |
| `--keep-frames` | off | keep the rendered frame images in the project folder |
| `--node PATH` | `node` | the Node.js program to use |
| `--library DIR` | `./library` next to the screenplay | where your own characters and backdrops are |

`make` also takes `--project DIR` to choose the project folder.
