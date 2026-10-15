# Tutorial 7: Troubleshooting

Start here, always:

```
python blaze.py doctor
```

It checks every tool Blaze needs and prints `OK`, `!!` (required and missing, with the fix after an arrow) or `--` (optional
and missing). Fix every `!!`, run it again, and most problems are gone.

## Install problems

| You see | Cause and fix |
|---|---|
| `!! Node.js` | Install Node.js from nodejs.org and open a new terminal. |
| `!! playwright (node module)` or `!! headless Chromium` | Run `python blaze.py setup`. It installs the renderer's browser (a few hundred MB). |
| `!! ffmpeg` | Install ffmpeg from ffmpeg.org and add it to your PATH, then open a new terminal. |
| `!! Pillow` | `pip install -r requirements.txt` |
| `-- voices (espeak-ng or pyttsx3)` | Optional. Videos are made without sound until you install espeak-ng, or on Windows `pip install pyttsx3`. |
| `-- Blender` | Optional. Only needed for `.blend` characters and backdrops. |
| `Blaze failed (setup): ...` | A tool is missing. Run `python blaze.py doctor`. |

On Windows, if `python` is not found, try `py blaze.py ...`. Put paths with spaces in quotes.

## The page

| You see | Cause and fix |
|---|---|
| `Port 8765 is already in use` | Blaze is already open in another window, or another program uses the port. Use `python blaze.py ui --port 8766`. |
| The page says *Blaze could not be reached* or *Lost contact with Blaze* | The terminal where you ran `python blaze.py ui` was closed or stopped. Start it again. Your screenplay is remembered in the browser. |
| *A video is already being made. Wait for it to finish.* | The page makes one video at a time. |
| *Make video* is greyed out | The screenplay is empty or has an error. Read the red line at the bottom; **Go to line** jumps to it. |
| It never finishes | Quality is too high for your computer. See "Slow" below. The terminal shows what is happening. |

## Screenplay problems

The message always names the line. The common ones:

| Message | Fix |
|---|---|
| `[ENTER JOE left] needs 2 exact number(s) at the end (positions are x values, not words)` | Write numbers: `[ENTER JOE 9.5 -3]`. 0 is the middle of the screen; see [Tutorial 2](02-writing-a-screenplay.md). |
| `unknown look key 'hatt'; valid keys: ...` | A typo in a `CAST:` line. The message lists every valid key. |
| `expected key=value, got 'man,'` | `CAST:` takes `key=value` pairs, not descriptions: `gender=m coat=1`. |
| `unknown place 'moon'; use one of: ...` / `unknown mood 'gloomy'; use one of: ...` | Pick from the list in the message. |
| `The screenplay has no dialogue or narration lines.` | Add at least one `NAME: text` line. |
| `CAST: ROBO asks for asset 'robo' but there is no library/characters/robo.png` | Add it: `python blaze.py asset add robo.png --name robo`. See [Tutorial 3](03-your-own-art.md). |
| `not understood, shown as narration` (warning) | A line is neither `NAME: text`, a command nor a comment. Check for a missing colon. |
| `unknown command [...]` | A command name is misspelled (the message suggests the closest). The five commands are ENTER, MOVE, EXIT, HOP, PAUSE. |
| `'Later that day' is not a declared character, so this line is not dialogue` | Only a `CAST:` character or a name in CAPITALS can speak. Start narration with `>`, or declare the name: `CAST: Zoe gender=f`. |
| `'JOHM' is not a character in this screenplay (did you mean John?)` | A command named someone who never speaks, enters or is cast. Fix the spelling. |
| `... is not on stage, so [MOVE] was skipped` (warning) | The character had left, or had not entered yet. Check the order of the commands. |
| `look 'shout' is not defined` | Define it: `DEFINE LOOK shout size=0.5`. See the [screenplay reference](../reference/screenplay.md). |
| `CAST Ann: the piper engine is not installed on this computer` / `no Piper model named ...` | The message says what to install. `python blaze.py voices` lists the voices that work here. |

## The video

| You see | Cause and fix |
|---|---|
| No sound | The **Voices** switch is off, `--voice off` was used, or no voice engine is installed (`doctor` shows `--`). Install espeak-ng or pyttsx3. |
| Every scene starts black for a moment | Normal. Each scene fades in from black over about 0.3 s. It is how CDRCA's renderer starts a scene. |
| A voice sounds the same for two characters | Voices depend on the name and on `gender=` and `child=`. Give them different genders, or write their names differently. |
| A character is too big or too small (your own picture) | Crop the empty space around the character in the picture; Blaze scales every character to the same height. |
| The mouth does not move (your own picture) | Add a `<name>_talk.png` with the mouth open and add the character again. |

## Slow

Drawing frames in a headless browser is CPU work, and a computer with no graphics card does it in software. Time is
proportional to pixels times frames.

- Work at **Draft** (640x360, 12 fps) until the story is right.
- Make the final once, at the size you need.
- `--workers 1` if the computer runs out of memory; the default is up to four scenes at once.
- Shorter scenes make quicker checks: split a long story, or temporarily comment out scenes with `#`.

## AI

See the messages in [Tutorial 5](05-writing-with-ai.md). The two most common:

- *No text_provider chosen*: pick a provider under **Write with AI** in the page, or fill in `studio/config.yaml`.
- *model not found*: the model name in `studio/config.yaml` is out of date; use a current one from your provider.

## Still stuck?

Run `python blaze.py doctor`, then re-run the failing command in a terminal and read the last lines it prints: Blaze ends
with `Blaze failed (<stage>): <what went wrong>`. The stage (`setup`, `assets`, `render`, `encode`, `screenplay`) tells you
which part to look at.
