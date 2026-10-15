# Tutorial 4: Voices, timing, quality and subtitles

## Voices

Blaze speaks every line with a text-to-speech engine installed on your computer. Nothing is sent anywhere.

| Engine | Where | Notes |
|---|---|---|
| **espeak-ng** (`espeak`) | Linux, macOS, Windows (github.com/espeak-ng/espeak-ng) | Used first when it is on your PATH. Clear but robotic. Many languages, plus voice variants such as `en-us+m3` or `en-gb+f2`. |
| **pyttsx3** | `pip install pyttsx3` | Uses the system voices on Windows (SAPI) and macOS. Used when espeak-ng is missing. |
| **Piper** (`piper`) | the `piper` program on your PATH | Offline neural voices, far more natural. You download the models you like (`.onnx` and `.onnx.json`) into `library/voices`, `~/.blaze/voices` or the folder in `$BLAZE_VOICES`. |

`python blaze.py doctor` shows whether one was found. `--voice auto|espeak|pyttsx3|piper|off` chooses the engine for characters who
do not ask for one (`auto` is the default; in the page the **Voices** switch is `auto` or `off`).

**Choose a voice for each character.** Put it on their `CAST:` line, together with an optional speed and pitch:

```
CAST: JOHN gender=m voice=espeak:en-gb+m3 rate=140
CAST: MARY gender=f voice=espeak:en-us+f2 pitch=70
CAST: Narrator voice=off
```

`voice=` is `<engine>:<voice>`, `auto`, or `off` for a silent character (their text is still shown and subtitled). `rate` is words
per minute for that character and `pitch` is 0 to 99 (espeak only). `python blaze.py voices` lists everything installed, and
`python blaze.py voices --voice espeak:en-gb+f2 --say "Hello"` writes a sample you can listen to before you decide. In the
page, every character in the outline has a drop-down, a **Play** button and a speed box; choosing a voice writes it into that
character's `CAST:` line, so the screenplay stays the one place that says how the video sounds. If a chosen voice is not
installed, Blaze stops before drawing anything and says what to install.

**Without a `voice=`,** each character has their own stable voice. It depends on their name, so the same name always sounds the
same, and on their look: `gender=f` and `gender=m` use different voices, and `child=1` raises the pitch. The narrator (`>` lines)
has a voice of its own. Characters you did not give a `gender` get one picked from their name.

**Speed.** `--wpm` is words per minute, default 150. About 105 is slow and clear, which suits language learners:

```
python blaze.py make story.txt --wpm 105
```

**Silent videos.** With `--voice off`, or when no engine is installed, Blaze still makes the video. It estimates how long each
line takes to say from its length and the `--wpm` speed (the words at that speed plus 0.45 seconds, and at least 1.2 seconds)
and the speech boxes reveal at that pace.

## How long things take on screen

You never set durations; Blaze works them out from what happens.

| In the screenplay | Time on screen |
|---|---|
| a spoken line | the length of the voice, plus 0.4 s before the next beat |
| a narrator line (`>`) | the length of the voice, plus 0.3 s |
| `[ENTER]`, `[MOVE]`, `[EXIT]` | the walking distance divided by 2.4 units per second (and the rest of the scene waits) |
| `[HOP]` | 0.5 s |
| `[PAUSE 1.5]` | exactly that many seconds |
| the title card | 3.2 s |

Everything plays one thing at a time. If you want a longer beat between two lines, add `[PAUSE 1]`.

## Quality and speed of making

The page's **Quality** menu and the command line's `--res` and `--fps` choose the picture:

| Page | `--res` | `--fps` used by the page | For |
|---|---|---|---|
| Draft | 640x360 | 12 | checking a story quickly |
| Standard | 960x540 | 20 | sharing |
| HD | 1280x720 | 24 | final |
| Full HD | 1920x1080 | 30 | final, large |

The command line defaults to 1280x720 at 24 fps. Any size works: `--res 1080x1920` makes a vertical video.

Making a video means drawing every frame in a headless browser. **Time grows with pixels times frames**, so Full HD at
30 fps is about 20 times the work of Draft (9 times the pixels, 2.5 times the frames). A computer with a graphics card will be much faster than the one used for
these numbers: on a one-core cloud machine with no graphics card, the 58-second example took about a minute at Draft quality,
and several minutes at Standard quality with voices.

Tips for slow computers:

- Always iterate at Draft. Only make the final at the quality you need.
- Blaze renders as many scenes at once as your computer has cores (up to 4). `--workers 1` renders one at a time, which
  uses less memory.
- Close other heavy programs. The renderer is CPU-bound.

## Subtitles

Every video comes with an `.srt` file with the same name (`story.srt` next to `story.mp4`; in the page it is the
**Subtitles** link):

```
1
00:00:03,200 --> 00:00:07,181
JOHN: Did you hear that? Something moved inside the warehouse.

2
00:00:07,583 --> 00:00:11,686
MARY: It's just the wind, John. Let's go home.
```

Each spoken or narrated line is one cue, timed to when it is said in the final video (a title card shifts everything by its
3.2 seconds). `.srt` works in every video player and uploads to YouTube and most editors. The subtitles are not burned into
the picture, because the speech boxes already show the words.

## Next

[Writing with AI](05-writing-with-ai.md), or [editing the generated CDRCA scripts](06-editing-the-cdrca-scripts.md).
