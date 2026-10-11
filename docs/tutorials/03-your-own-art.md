# Tutorial 3: Your own characters and backgrounds

Blaze draws characters and backdrops for you, but you can use your own: a PNG you drew, a photo, or a model made in
Blender. They live in your **library**, a folder with two sub-folders.

```
library/
  characters/    robo.png   robo_talk.png   robo_blink.png
  backdrops/     lab.png
```

Blaze looks for the library in this order: the `--library` folder you name, `./library` next to your screenplay, then
`./library` in the folder you ran Blaze from. When you add a file, it goes into the first of those.

## 1. A character from a picture

What the picture must be:

- a **PNG with a transparent background** (so only the character shows),
- the character **facing the viewer**, standing, with **feet at the bottom edge** of the image,
- any size; a tall image around 400x720 matches the built-in characters best.

Add it:

```
python blaze.py asset add robo.png --name robo
```

Blaze sees that the image has transparency and adds it as a character. It converts it to PNG and copies it into
`library/characters/`. Use it in a screenplay with `asset=`:

```
CAST: ROBO asset=robo
CAST: MARY gender=f dress=1

SCENE: lab
BACKDROP: lab
ROBO: Good morning.
MARY: You are late, Robo.
```

`asset=robo` means "use library/characters/robo.png". Mixed casts work: Mary is still drawn by Blaze. If the file does
not exist you get an error that says where Blaze looked and the command that adds it:

```
CAST: ROBO asks for asset 'robo' but there is no library/characters/robo.png (looked in: ...). Add it with: blaze asset add <file> --name robo
```

### A moving mouth

If you also have a version with the mouth open, name it `<name>_talk.png` and keep it next to the first file when you add it:

```
robo.png
robo_talk.png      <- mouth open
```

`python blaze.py asset add robo.png --name robo` picks up `robo_talk.png` automatically (and `robo_blink.png`, kept for
your own use) and copies all of them. While the character speaks, Blaze swaps between the two pictures four times a
second. With no `_talk` picture the character simply stands still while speaking.

Voices still follow `gender=` and `child=`. You can write them next to `asset=`:

```
CAST: ROBO asset=robo gender=m
```

Everything except `asset` is used for the voice and the size (`child=1` is drawn smaller); looks that only change the
drawing (`hat`, `top`, ...) do nothing for a picture you supplied.

## 2. A backdrop from an image

```
python blaze.py asset add lab.jpg --name lab
```

An image with no transparency is added as a backdrop (PNG, JPG and WebP work). It is cropped to fill a 16:9 frame. Use it
by name:

```
BACKDROP: lab
```

With `blaze make` you can also point at a file directly, `BACKDROP: backgrounds/lab.jpg` (a path relative to the
screenplay file), without adding it to the library.

Override the automatic choice with `--as`:

```
python blaze.py asset add ghost.png --as backdrop      # a transparent image you want as a backdrop
python blaze.py asset add crowd.jpg --as character     # an opaque image you want as a character
```

See what you have:

```
python blaze.py asset list
```

## 3. Characters and backdrops from Blender

If you have [Blender](https://blender.org) installed, `.blend` files work too:

```
python blaze.py asset add robot.blend --name robo
python blaze.py asset add lab.blend --as backdrop --name lab
```

- A **character** `.blend` is rendered in front view, framed with its feet at the bottom edge, as `robo.png`, `robo_talk.png`
  and `robo_blink.png`. If the model has **shape keys named `talk` and `blink`**, they drive the open-mouth and closed-eyes
  pictures. Without them all three images look the same.
- A **backdrop** `.blend` is rendered as one frame from the scene's camera.

Options: `--blender <path>` if Blender is not found automatically, `--samples 64` for cleaner (slower) renders (default
32), `--yaw 30` to turn the subject by 30 degrees before rendering.

Rendering uses Blender's Cycles on the CPU, so no graphics card or display is needed. Blender only produces pictures; once
they are in the library everything works exactly as in section 1 and 2. `python blaze.py doctor` shows whether Blender
was found.

## 4. Sharing a library

The library is just folders of PNG files. Copy `library/` next to a screenplay on another computer and it works there:
the same screenplay with the same library gives the same video.

## Checking it works

Make a draft with your character in it:

```
python blaze.py make story.txt -o story.mp4 --res 640x360 --fps 10 --voice off
```

If the character looks too big or too small, edit the picture (crop the empty space around it); Blaze scales every
character to the same height unless `child=1`.

Next: [voices, timing and subtitles](04-voices-timing-subtitles.md).
