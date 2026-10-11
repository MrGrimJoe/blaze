# Screenplay format reference

A screenplay is a UTF-8 text file read line by line. Every value is exact. This page is the complete grammar; for a gentle
introduction see [Tutorial 2](../tutorials/02-writing-a-screenplay.md).

## Line types, in the order Blaze tries them

1. **Ignored lines**: empty lines, lines starting with `#` or `//`, and lines that begin with `(` and end with `)` (a
   stage direction for humans).
2. **Scene heading from a slugline**: a line starting with `INT.`, `EXT.`, `INT/EXT.` or `I/E.` (any case) starts a new scene
   whose label is the rest of the line, as in screenplays written for film. The label is not interpreted.
3. **Narration**: a line starting with `>`. The text after it is a caption, spoken by the narrator voice.
4. **Commands**: a line starting with `[`. It may hold several commands, `[MOVE JOE 0] [HOP JOE]`. Text outside the brackets
   gives a warning and is ignored.
5. **Name lines**: `NAME: text` or `NAME (note): text`, where NAME starts with a letter and is at most 24 characters from
   letters, digits, space, `_`, `'`, `.` and `-`. If NAME is one of the directives below it is that directive; otherwise it is
   a spoken line.
6. **Anything else** is shown as narration and gives the warning `not understood, shown as narration`.

A spoken line may end with commands in brackets: `JOE: Hello! [HOP JOE]` makes Joe say the line, then hop.

## Directives (the NAME is one of these words, any case)

| Directive | Meaning |
|---|---|
| `TITLE: text` | a title card at the start of the video (3.2 s) |
| `SUBTITLE: text` | smaller text under the title on the title card |
| `CAST: NAME key=value ...` | defines a character's look. One line per character. See Cast keys. |
| `SCENE: label` | starts a scene. The label is for you. |
| `BACKDROP: spec` | the backdrop of the current scene. See Backdrops. |
| `NARRATOR: text` | same as a `>` line |

`STYLE:`, `CAMERA:` and `WEATHER:` lines are accepted for compatibility, skipped, and reported as warnings (`... is not
supported (text always shows as a speech box; there is no camera or weather)`).

Beats before the first `SCENE:` go into a scene with an empty label. A scene with no beats and no label is dropped.

## Names

- Names are matched ignoring case: `JOHN`, `John` and `john` are one character. An all-capitals name is shown with normal
  capitalisation (`JOHN` becomes `John`); other spellings are kept as written.
- A character exists the moment its name speaks, is cast, or is used in a command.
- Spaces are allowed in names (`MARY JANE: Hi`); in commands the name is everything before the trailing numbers.

## Commands

All numbers are written like `4`, `-4`, `4.2`, `-0.5`: an optional minus, digits, and an optional fraction. No `+`, no leading
`.`, no exponents, no words.

| Command | Numbers | Effect |
|---|---|---|
| `[ENTER NAME x0 x1]` | 2 | NAME appears at x0 and walks to x1 |
| `[MOVE NAME x]` | 1 | NAME walks to x |
| `[EXIT NAME x]` | 1 | NAME walks to x and is gone |
| `[HOP NAME]` | 0 | NAME jumps once (0.5 s) |
| `[PAUSE s]` | 1 | nothing happens for s seconds |

Anything else is reported as `unknown command [...]` and skipped. A missing or non-numeric number is an error:
`line 2: [MOVE JOE left] needs 1 exact number(s) at the end (positions are x values, not words)`.

**Positions** are x coordinates in scene units. 0 is the middle. At 16:9 the visible width is about 13.6, so the edges are about
-6.8 and 6.8 (the visible half-width is 3.84 times the width-to-height ratio). Use 9.5 or -9.5 for off screen. A character
is about 2.4 wide. A destination that would put a character on top of another is moved to the nearest free spot. Characters
that speak before any `ENTER` start on stage, spread evenly.

Speech boxes are anchored above the speaker (the anchor is limited to x between -4 and 4) and slide back inside the screen if
needed; their pointer keeps aiming at the speaker.

## Cast keys

`CAST: NAME key=value key=value ...`. The separators are spaces; values have no spaces. Unknown keys and bad values are errors.
Keys you leave out are chosen from a hash of the name, so a name always gets the same look.

| Key | Values |
|---|---|
| `gender` | `m`, `f`, `n` |
| `child` | `0`, `1` |
| `skin` | `0` to `5` (a built-in tone) or a colour `0xRRGGBB` |
| `hair`, `top`, `bottom` | a colour `0xRRGGBB` (decimal also works) |
| `hairstyle` | `short`, `long`, `bun`, `bald`, `curly`, `spiky` (a `bun` under a hat becomes `short`) |
| `coat`, `dress`, `glasses`, `beard`, `scarf` | `0`, `1` |
| `hat` | `none`, `fedora`, `cap`, `beanie` |
| `asset` | the name of a character in your library (see [Tutorial 3](../tutorials/03-your-own-art.md)); the other keys are then used only for voice (`gender`, `child`) and size (`child`) |

`gender` and `child` also choose the voice. `child=1` draws a smaller character.

## Backdrops

`BACKDROP:` takes one of:

- **`gen:<place>:<mood>`** drawn for you.
  - places: `street`, `room`, `warehouse`, `forest`, `beach`, `office`
  - moods: `day`, `sunset`, `night`, `dim`, `rain`, `storm`, `snow`, `night_rain`, `night_snow`
- **a library name**, such as `lab`, found in `library/backdrops/lab.png`
- **an image path** (`.png`, `.jpg`, `.jpeg`, `.webp`), relative to the screenplay file

With no `BACKDROP:` a scene uses `gen:street:day`. A name that is none of these is an error that says what is missing and how
to add it.

## Errors and warnings

**Errors** stop everything before any drawing, with a line number where there is one:

- a command whose numbers are missing or are words
- an unknown look key, a bad flag value, an unknown hat or hairstyle, a bad gender
- an unknown place or mood in `gen:`, or a `gen:` spec not in the form `gen:<place>:<mood>`
- a `CAST:` asset or a `BACKDROP:` name that is not in the library
- a screenplay with no spoken or narrated line at all

**Warnings** do not stop anything; the page lists them under *Heads up* and the command line prints them:

- `unknown command [...]`
- `... is not supported` for `STYLE`, `CAMERA`, `WEATHER`
- `text outside [brackets] ignored`
- `not understood, shown as narration`
