# Tutorial 6: Editing the CDRCA scripts

Blaze does not hide how the video is made. Every video leaves a **project folder** containing one plain-text script per
scene, written in the [CDRCA](https://github.com/ISLAH-org/CDRCA) animation language. Open one, change a number, render
again. This is how you change things the screenplay format does not cover: a speech-box colour, an exact position, a pause
length, a walking speed.

## Where the scripts are

`blaze make story.txt` leaves `story.blaze/` next to your video (the page keeps it as `project/` inside the video's folder):

```
story.blaze/
  screenplay.txt          the screenplay that was used
  project.json            the scene list, size and frame rate, subtitle timings
  scenes/                 s00_title.cdrca, s01.cdrca, s02.cdrca ... and atoms.cdrca
  assets/                 the character and backdrop pictures
  audio/                  one .wav per spoken line, and a track per scene
  shots/                  one mp4 per scene (rebuilt every time)
```

Details of every file are in [the project folder reference](../reference/project-folder.md).

## Reading a scene script

Open `scenes/s01.cdrca`. This is the real beginning of the first scene of the example story, lightly shortened:

```
@IMPORT "./atoms.cdrca"

!--- SCENE street ---

use Picture("../assets/bg_street_night_rain.png", 0, 0, 16.711, 9.4, -1, 0, "", 0) as backdrop
use Picture("../assets/john.png", -2.4, -0.1, 2.444, 4.4, 0, 2.4, "../assets/john_talk.png", 4) as c_John
use Words(-2.4, 2.3, 0.5, 0, 0.32, 6.4, 0xffffff, 1, 0x1b1f2a, 0x1b1f2a, 0.04, 0.22, 0.3, 0.01, 6.671, 3.687) as say_John_1

add new action a001 3981 1
add new action a002 400 1

def ACTION a001 c_John flap ""
def ACTION a001 say_John_1 rate 15.629
def ACTION a001 say_John_1 say "Did you hear that? Something moved inside the warehouse."
def ACTION a002 c_John modifyMesh ""
```

Read it top to bottom:

- `@IMPORT "./atoms.cdrca"` loads the two building blocks, `Picture` (an image) and `Words` (a speech box or caption).
  They are written in CDRCA itself in `scenes/atoms.cdrca`, a file you can read too.
- `!--- SCENE street ---` starts the scene.
- `use Picture(...) as c_John` creates a prop: here the picture of John. The numbers are, in order: the image, x, y, width,
  height, depth, walking speed, the *mouth-open* image and how many times a second to swap. `use Words(...) as say_John_1`
  creates John's first speech box.
- `add new action a001 3981 1` is a **beat**: it lasts 3981 milliseconds (the length of John's voice line), with a
  1 millisecond transition, which is a hard cut.
- `def ACTION a001 c_John flap ""` says what a prop does during a beat: here John flaps his mouth. `say "..."` makes the
  speech box show that text, revealing it at `rate` characters per second. Every beat lists every prop, because a prop
  that is not mentioned is not drawn during that beat.

Every parameter of `Picture` and `Words` is explained in the [atoms reference](../reference/atoms.md).

## Edits that work well

| To change | Edit |
|---|---|
| a speech box's colour | the two colours in its `use Words(...)` line: the 7th value is the fill, the 9th the text colour (for example `0xffffff` becomes `0xffe9a8`) |
| where a character stands | `x` (the 2nd value) in its `use Picture(...)` line |
| a character's size | the width and height values (4th and 5th) |
| how long a beat lasts | the number after the beat name: `add new action a002 400 1` is 400 ms; make it `1500` for a longer pause |
| walking speed | the 7th value of `use Picture(...)` (units per second) |
| the text shown in a speech box | the text in the `say "..."` line (the voice is not changed: that is in `audio/`) |

If you want to change **what is said**, edit the screenplay and make the video again; the scripts are generated from it.

## Render again

```
python blaze.py build story.blaze -o story.mp4
```

`build` re-renders every scene script and joins the audio that is already in `audio/`. It uses the size and frame rate
written in `project.json` (`width`, `height`, `fps`); edit those three numbers to change them. It writes a new `.srt` from
the timings in `project.json`.

We checked this flow: changing a speech box's fill colour in a generated script and running `build` gives a video whose
speech box has the new colour.

## Mistakes

If a script has a syntax error, `build` stops and prints where. Undo your last edit, or delete the project folder and make
the video again from the screenplay. **Your screenplay is the source; the project folder is generated.** Running
`blaze make` again overwrites generated scripts, so keep any hand edits you care about in a copy.

## Using the scripts elsewhere

The scripts are ordinary CDRCA, so they are not locked to Blaze: they follow the language described in CDRCA's own
documentation, and what Blaze needed from CDRCA itself is listed in [CDRCA-CHANGES.md](../CDRCA-CHANGES.md).

Next: [troubleshooting](07-troubleshooting.md).
