# Tutorial 2: Writing a screenplay

A Blaze screenplay is a plain text file. Every line is one of a few kinds, and every value is exact: a number, a name from
a short list, or a `key=value`. This tutorial teaches each kind with an example. The complete grammar is in the
[screenplay reference](../reference/screenplay.md).

## The shape of a screenplay

```
TITLE: The Lost Key                      <- optional: a title card at the start
SUBTITLE: a very short story             <- optional: smaller text under the title

CAST: JOHN gender=m coat=1               <- who is in it, and what they look like (optional)
CAST: MARY gender=f dress=1

SCENE: street at night                   <- starts a scene (the label is for you)
BACKDROP: gen:street:night_rain          <- where it happens
JOHN: Did you hear that?                 <- a spoken line
MARY: It is just the wind.
```

Blank lines are ignored. So are lines that start with `#` or `//`, which makes them handy for notes to yourself.

## Spoken lines

```
JOHN: Did you hear that?
MARY (nervous): It is just the wind.
```

`NAME: words`. The name can be any text before the first colon. The first time a name speaks, that character exists. If you
never wrote a `CAST:` line for them, Blaze gives them a look that depends only on their name, so the same name always looks
the same.

Text in brackets after the name, such as `(nervous)`, is a note for you. It is ignored.

While a character speaks, their mouth moves and a speech box appears above them. The words appear as the voice says them.
The speech box slides back on screen if the speaker stands near an edge, and its pointer keeps aiming at them.

**Tips.** Keep lines to about 14 words or fewer so a box does not cover the picture. One speaker per line.

## A narrator

```
> The next evening, the kite was back in the sky.
```

A line starting with `>` is a caption at the bottom of the screen, spoken in a neutral voice.

## Cast and looks

```
CAST: JOHN gender=m coat=1 hat=fedora glasses=1 top=0xd64036
CAST: MARY gender=f hairstyle=long top=0x3c78d6 dress=1
CAST: TIM  gender=m child=1 hat=cap top=0x40a060
```

Everything after the name is `key=value`, separated by spaces. Anything you leave out is picked from a hash of the name,
so it is stable but not chosen by you.

| Key | Values |
|---|---|
| `gender` | `m`, `f` or `n` (also picks the voice; `n` gets one by name) |
| `child` | `0` or `1` (smaller, higher voice) |
| `skin` | `0` to `5`, or a colour like `0xc68642` |
| `hair`, `top`, `bottom` | a colour, written `0xRRGGBB` |
| `hairstyle` | `short`, `long`, `bun`, `bald`, `curly`, `spiky` |
| `coat`, `dress`, `glasses`, `beard`, `scarf` | `0` or `1` |
| `hat` | `none`, `fedora`, `cap`, `beanie` |

Colours are hexadecimal: `0xd64036` is red-ish, `0x3c78d6` blue, `0x40a060` green. Any colour picker will show you the hex
code; replace the `#` with `0x`.

A typo is an error, never ignored:

```
Zed: unknown look key 'hatt'; valid keys: beard, bottom, child, coat, dress, gender, glasses, hair, hairstyle, hat, scarf, skin, top
Zed: coat must be 0 or 1, not 'yes'
Zed: unknown hat 'tophat'
expected key=value, got 'man,'
```

To use your own picture or model instead, see [Tutorial 3](03-your-own-art.md): `CAST: ROBO asset=robo`.

## Scenes and backdrops

```
SCENE: inside the warehouse
BACKDROP: gen:warehouse:night
```

A `SCENE:` line starts a new scene; the text is only a label. Characters who speak in a scene are placed in it; each
scene is rendered separately and the scenes are joined in order.

`BACKDROP:` takes one of three things:

- `gen:<place>:<mood>`, drawn for you. Places: `street`, `room`, `warehouse`, `forest`, `beach`, `office`.
  Moods: `day`, `sunset`, `night`, `dim`, `rain`, `storm`, `snow`, `night_rain`, `night_snow`.
- the name of a backdrop in your library ([Tutorial 3](03-your-own-art.md)),
- or the path of an image file.

With no `BACKDROP:` line a scene gets `gen:street:day`. Misspell the name and you are told what the choices are:

```
unknown place 'moon'; use one of: street, room, warehouse, forest, beach, office
unknown mood 'gloomy'; use one of: day, sunset, night, dim, rain, storm, snow, night_rain, night_snow
backdrop generator must look like gen:<place>:<mood>, not 'rainy street at night'
```

## Staging: moving around

```
[ENTER TIM 9.5 4.2]     Tim walks in: starts at x = 9.5 (off screen), ends at x = 4.2
[MOVE JOHN 0]           John walks to x = 0
[EXIT TIM 9.5]          Tim walks to x = 9.5 and is gone
[HOP MARY]              Mary jumps once
[PAUSE 1.5]             nothing happens for 1.5 seconds
```

Positions are **x coordinates in scene units**. `0` is the middle of the screen. The picture is about 13.6 units wide at
16:9, so the edges are about -6.8 and 6.8; a character is about 2.4 units wide. Use `9.5` or `-9.5` for "off screen".

```
  -9.5 (off screen)   -6.8 (edge)      0 (middle)      6.8 (edge)   9.5 (off screen)
```


Rules worth knowing:

- Characters who speak before any `[ENTER]` are already on stage at the start of the scene and are spread out evenly.
- A character who is entered (`ENTER`) is not on screen until that command.
- Characters never end up standing on each other: Blaze moves a destination to the nearest free spot.
- Walking takes distance divided by 2.4 units per second; the rest of the scene waits for the walk to finish.

Words where a number belongs are errors, because Blaze does not guess what "left" means, and so are mistakes in names and
commands, because Blaze does not guess what you meant:

```
line 2: [ENTER JOE left] needs 2 exact number(s) at the end (positions are x values, not words)
line 3: unknown command [MOV JOE 3]. The commands are ENTER, EXIT, MOVE, HOP, PAUSE (did you mean MOVE?)
line 4: 'JOHM' is not a character in this screenplay (did you mean John?). Add it with CAST:, or let it speak or ENTER first.
line 5: 'Later that day' is not a declared character, so this line is not dialogue. ...
```

A speaker is a character declared with `CAST:`, or a name written in CAPITALS. A line such as `Later that day: Mary went home` is
therefore an error, not a new character called "Later that day"; write narration with `>`. Names with lower-case letters,
accents or another script (`Zoë`, `McGee`) are declared first with `CAST: "Zoë" gender=f`.

Things that are not supported, such as `STYLE:`, `CAMERA:` and `WEATHER:` lines, give a warning and are skipped, so a
screenplay written for something fancier still renders. A command that cannot happen (moving someone who is not on stage) is
skipped with a warning that names the line.

## Two ways to write the same thing

`JOHN: Did you hear that?` is shorthand for the explicit statement `SPEAK JOHN "Did you hear that?"`, and `> It was late.` is
shorthand for `NARRATE "It was late."`. Use whichever you like; they can be mixed. `python blaze.py expand story.txt` shows
the explicit form of a whole screenplay. The explicit form is also where you choose how text looks:

```
CAST: JOHN gender=m voice=espeak:en-gb+m3
DEFINE LOOK shout base=bubble size=0.55 ink=0xc0141e
SCENE: street
SPEAK JOHN "Stop right there!" look=shout
```

See the [screenplay reference](../reference/screenplay.md) for text looks and the voice keys.

## A complete example

```
TITLE: The Kite
SUBTITLE: a tiny mystery

CAST: ANA gender=f dress=1 top=0xe07a1f
CAST: LEO gender=m child=1 hat=cap top=0x40a060

SCENE: the park
BACKDROP: gen:forest:day
ANA: I heard a noise by the old tree.
[MOVE ANA -3]
[ENTER LEO 9.5 3.5]
LEO: Please don't be mad! I came to find my kite.
ANA: Your kite?
LEO: It flew away yesterday.
[HOP LEO]

SCENE: the beach
BACKDROP: gen:beach:sunset
> The next evening, the kite was back in the sky.
LEO: Thank you for helping me!
ANA: Next time, tell me first.
```

Two scenes, two characters, a walk-in, a hop and a narrator caption. Paste it into the page and press **Make video**.

## Habits that save time

- **Draft first.** Write the whole story, make a **Draft** video, fix what is wrong, then make the final quality.
- **Watch the bottom line of the page.** It names the line that is wrong, with a **Go to line** button.
- **Keep names consistent.** `JOHN` and `John` are the same person (an all-capitals name is shown in normal case), but `Jon`
  is someone new.
- **Use the same `CAST:` lines for every scene.** The cast is global; you only write it once at the top.
