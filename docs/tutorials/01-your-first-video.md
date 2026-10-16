# Tutorial 1: Your first video

About 10 minutes, most of it waiting for the install. You will end with a finished mp4 and know where everything is.

## 1. Install Blaze

**Windows, the easy way:** run the installer (`Blaze_Setup_<version>.exe`, see [the installer](../installer.md)) and open
**Blaze** from the Start menu. Everything is included. Then skip to [step 3](#3-make-the-example): the page opens by itself.

**From source (any system):** install what Blaze needs.

| Needed | Why | Get it |
|---|---|---|
| Python 3.9 or newer | Blaze itself | python.org |
| Node.js | runs CDRCA, the animation engine | nodejs.org |
| ffmpeg | joins frames and sound into an mp4 | ffmpeg.org (it must be on your PATH) |
| espeak-ng *(optional)* | the voices | github.com/espeak-ng/espeak-ng, or on Windows `pip install pyttsx3` to use the system voices |
| Blender *(optional)* | only for your own `.blend` models | blender.org |

Then, in the Blaze folder:

```
pip install -r requirements.txt
python blaze.py setup
python blaze.py doctor
```

`setup` downloads the headless browser the renderer uses (one time, a few hundred MB). `doctor` checks everything and
prints a list. Every required line should say `OK`; lines marked `--` are optional. On Windows you can type `blaze` instead
of `python blaze.py`.

If `doctor` shows `!!`, the text after the arrow tells you the fix. See [Troubleshooting](07-troubleshooting.md).

## 2. Open the page

```
python blaze.py ui
```

(Installed from the installer? The Start-menu shortcut does this for you.) Your browser opens on `http://127.0.0.1:8765`. The page is served only from your own computer; nothing is uploaded.
Leave the terminal window open while you use it.

![The Blaze page](../img/page.png)

The page has three parts:

- **Left: the screenplay.** Type here. It is saved in your browser as you go.
- **Right: what Blaze understood.** Title, cast and scenes appear as you type. If something is wrong, the bottom line
  turns red, names the problem and has a **Go to line** button.
- **Top: quality, voices and Make video.** Beside the name are three tabs, which show the same screenplay in different ways:
  **Editor** is just the code with line numbers (no side panel); **Smart** is the view described above; **Running** is the finished
  video with a timeline under it, where you can drag the playhead, click any line to jump to it, change the speed and zoom. A dot
  appears on **Running** when a new video is ready, and the last video is still there after you reload the page.

## 3. Make the example

1. Press **start from an example**. A three-scene mystery appears.
2. Set **Quality** to **Draft** and leave **Voices** on (turn it off if you have no voice engine).
3. Press **Make video** (or Ctrl+Enter).

A thin line under the top bar and the words *Drawing scenes* show progress. On a one-core test machine with no graphics
card, the 58-second example took about a minute at Draft quality. Bigger sizes take proportionally longer.

When it finishes, the video appears on the right with **Download video** and **Subtitles** links.

> The first half-second of every scene fades in from black. That is how the renderer starts each scene, not a fault.

## 4. Write your own

Clear the box and type:

```
TITLE: The Lost Key
CAST: JOHN gender=m top=0xd64036
CAST: MARY gender=f dress=1

SCENE: street
BACKDROP: gen:street:night
JOHN: Have you seen my key?
MARY: It is in your hand.
[HOP JOHN]
JOHN: So it is.
```

The right side now shows 1 scene and 2 characters. Press **Make video**.

What each line did:

- `CAST:` gave John and Mary exact looks. `top=0xd64036` is a shirt colour (red) written as `0xRRGGBB`.
- `BACKDROP: gen:street:night` asked for a street at night. `gen:<place>:<mood>`, both exact names.
- `NAME: text` is a spoken line. The speaker's mouth moves and a speech box appears.
- `[HOP JOHN]` makes John jump once.

Now break it on purpose: change `[HOP JOHN]` to `[MOVE JOHN left]`. The bottom line turns red:

```
[MOVE JOHN left] needs 1 exact number(s) at the end (positions are x values, not words)
```

Blaze never guesses what "left" means. Write `[MOVE JOHN -4]`, a number where 0 is the middle of the screen.

## 5. The same thing from the command line

Save the screenplay as `story.txt` and run:

```
python blaze.py make story.txt -o story.mp4 --res 640x360 --fps 10
```

You get `story.mp4`, `story.srt` and a folder `story.blaze/` (see [the project folder](../reference/project-folder.md)).

## Where your videos are

The page keeps each video in `./blaze-videos/<id>/` next to where you started it: `video.mp4`, `subtitles.srt` and a
`project/` folder. You can choose another place with `python blaze.py ui --out D:\videos`.

## Next

- [Tutorial 2](02-writing-a-screenplay.md): every line type and staging command.
- [Tutorial 3](03-your-own-art.md): your own characters and backdrops.
