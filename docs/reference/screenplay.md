# Screenplay format reference

A screenplay is a UTF-8 text file read line by line. Every value is exact: positions, colours, voices and text looks are numbers
and names you write, never words Blaze has to interpret. This page is the complete grammar; for a gentle introduction see
[Tutorial 2](../tutorials/02-writing-a-screenplay.md), and for why the language is built this way see
[Language design](../LANGUAGE-DESIGN.md).

## Two layers: the core and the shorthand

The **core** is a small set of statements that each say everything. The **shorthand** (the lines most people write) is only a
shorter way to write core statements, and the two can be mixed freely. `python blaze.py expand story.txt` prints any
screenplay in its core form, so you can always see what a shorthand line means.

| Shorthand | Core statement it stands for |
|---|---|
| `JOHN: Did you hear that?` | `SPEAK JOHN "Did you hear that?"` |
| `JOHN (look=shout): Stop!` | `SPEAK JOHN "Stop!" look=shout` |
| `> It was late.` or `NARRATOR: It was late.` | `NARRATE "It was late."` |
| `[ENTER TIM 9.5 4.2]` | `ENTER TIM 9.5 4.2` |
| `JOE: Hello! [HOP JOE]` | `SPEAK JOE "Hello!"` then `HOP JOE` |
| `INT. KITCHEN - DAY` | `SCENE: KITCHEN - DAY` |

In the core form the text is in double quotes (write `\"` for a quote inside it) and is taken literally: nothing in it is a
command. A complete screenplay written only in core statements:

```
TITLE: The Lost Key
CAST: JOHN gender=m coat=1
CAST: MARY gender=f dress=1

SCENE: street
BACKDROP: gen:street:night
SPEAK JOHN "Did you hear that?"
SPEAK MARY "It is just the wind."
NARRATE "Thunder rolled across the street."
MOVE JOHN 3
```

## Line types, in the order Blaze tries them

1. **Ignored lines**: empty lines, lines starting with `#` or `//`, and lines that begin with `(` and end with `)` (a stage
   direction for humans).
2. **Scene heading from a slugline**: `INT.`, `EXT.`, `INT/EXT.` or `I/E.` (any case) starts a new scene whose label is the rest
   of the line.
3. **Narration**: a line starting with `>`. The text after it is a caption, spoken by the narrator voice.
4. **Command lines**: a line starting with `[`. It may hold several commands, `[MOVE JOE 0] [HOP JOE]`. Every bracket must be a
   command; anything else is an error. Text outside the brackets gives a warning and is ignored.
5. **Name lines**: `NAME: text` or `NAME (note): text`, where NAME starts with a letter and is at most 24 characters from
   letters (any script), digits, space, `_`, `'`, `.` and `-`. If NAME is a directive below it is that directive; otherwise it is
   a spoken line, and NAME must be a known speaker (see Names).
6. **Core statements**: a line starting with an upper-case `DEFINE LOOK`, `SPEAK`, `NARRATE`, `ENTER`, `EXIT`, `MOVE`, `HOP` or
   `PAUSE`.
7. **Anything else** is shown as narration and gives the warning `not understood, shown as narration`.

A spoken line may end with, or contain, commands in brackets: `JOE: Hello! [HOP JOE]` makes Joe say the line, then hop. A
bracket in speech is a command if its first word is a command (`[HOP JOE]`), or if it is written in capitals and mentions a
number or a character, which means a misspelt command (`[MOV JOE 3]`, an error). Anything else keeps its brackets as part of the
text: `JOE: I put it in [the box]` and `JOE: Call [NASA] now` are speech.

## Directives (the NAME is one of these words, any case)

| Directive | Meaning |
|---|---|
| `TITLE: text` | a title card at the start of the video (3.2 s) |
| `SUBTITLE: text` | smaller text under the title on the title card |
| `CAST: NAME key=value ...` | declares a character: look, voice and default text look. One line per character. See Cast keys. |
| `SCENE: label` | starts a scene. The label is for you. |
| `BACKDROP: spec` | the backdrop of the current scene. See Backdrops. |
| `NARRATOR: text` | same as a `>` line |

`DEFINE LOOK name key=value ...` is covered under Text looks. `STYLE:`, `CAMERA:` and `WEATHER:` lines are skipped and reported as
warnings; there is no camera or weather, and text is styled with looks.

Beats before the first `SCENE:` go into a scene with an empty label. A scene with no beats and no label is dropped.

## Names

Names are strict, so a typo cannot quietly become a new character.

- A speaker is **a character declared with `CAST:`**, or **a name written in capitals** (`JOHN`, `MARY JANE`). Anything else
  before a colon is an error: `'Later that day' is not a declared character, so this line is not dialogue`. Start narration
  with `>`.
- Names with lower-case letters, accents, or a script without capitals (`Zoë`, `McGee`, `علی`) must be declared first. A name
  with spaces or lower-case letters is quoted in CAST: `CAST: "Dr Smith" gender=m`.
- A command may only name a character who is in the screenplay (declared, speaking, or entering). `[MOVE JOHM 3]` is an error:
  `'JOHM' is not a character in this screenplay (did you mean John?)`. `ENTER` may introduce a character; if that character
  never speaks and is not in CAST you get a warning, in case the name is a typo.
- Names are matched ignoring case: `JOHN`, `John` and `john` are one character. An all-capitals name is shown with normal
  capitalisation (`JOHN` becomes `John`); other spellings are kept as written.
- Two undeclared names that are almost the same (`JOHN` and `JON`) give a warning. Declare both with CAST to say it is on
  purpose.

## Commands

All numbers are written like `4`, `-4`, `4.2`, `-0.5`: an optional minus, digits, and an optional fraction. No `+`, no leading
`.`, no exponents, no words. Command names are written in capitals; any case is accepted inside brackets.

| Command | Numbers | Effect |
|---|---|---|
| `ENTER NAME x0 x1` | 2 | NAME appears at x0 and walks to x1 |
| `MOVE NAME x` | 1 | NAME walks to x |
| `EXIT NAME x` | 1 | NAME walks to x and is gone |
| `HOP NAME` | 0 | NAME jumps once (0.5 s) |
| `PAUSE s` | 1 | nothing happens for s seconds |

An unknown command is an error that suggests the closest one:
`line 2: unknown command [MOV JOHN 3]. The commands are ENTER, EXIT, MOVE, HOP, PAUSE (did you mean MOVE?)`. A missing or
non-numeric number is an error: `line 2: [MOVE JOE left] needs 1 exact number(s) at the end (positions are x values, not words)`.

A command that cannot happen is skipped and reported in *Heads up*, never silently: moving, hopping or exiting someone who is
not on stage, or entering someone already there.

**Positions** are x coordinates in scene units. 0 is the middle. At 16:9 the visible width is about 13.6, so the edges are about
-6.8 and 6.8 (the visible half-width is 3.84 times the width-to-height ratio). Use 9.5 or -9.5 for off screen. A character
is about 2.4 wide. A destination that would put a character on top of another is moved to the nearest free spot. Characters
that speak before any `ENTER` start on stage, spread evenly.

## Text looks

Every piece of on-screen text is drawn with a **look**: a named bundle of exact numbers. Five ship with Blaze:

| Look | What it is |
|---|---|
| `bubble` | a speech box above the speaker (the default for spoken lines) |
| `caption` | a dark bar near the bottom (the default for narration) |
| `title`, `subtitle` | the title card text |
| `none` | draws nothing: the line is still spoken, subtitled and the speaker's mouth still moves |

Define your own, or change a built-in one, with `DEFINE LOOK`:

```
CAST: JOHN gender=m
DEFINE LOOK shout base=bubble size=0.55 wrap=7 fill=0xfff3b0 ink=0xc0141e border=0xc0141e border_w=0.07
DEFINE LOOK sign x=-4.6 y=3.5 ax=0 ay=1 size=0.34 wrap=3.2 tail=0 clamp=0
SCENE: street
JOHN (look=shout): STOP RIGHT THERE!
NARRATE "A sign flickered above the door." look=sign
JOHN (look=none): This is spoken but not drawn.
```

`DEFINE LOOK name key=value ...` starts from `base=<look>` if you give one; otherwise from the built-in of the same name if you are
redefining one, otherwise from `bubble`. A look may be used before the line that defines it.

| Key | Meaning |
|---|---|
| `size` | height of a line of text, scene units (bubble 0.32) |
| `wrap` | widest a line may be before it wraps (bubble 6.4) |
| `fill`, `ink`, `border` | box colour, text colour, outline colour: `0xRRGGBB` |
| `alpha` | box opacity, 0 to 1 |
| `border_w`, `pad`, `tail` | outline width, space between text and box edge, length of the pointer (0 for none) |
| `x`, `y` | a **fixed** position for the anchor. Give both, or neither (or `none`) to anchor above whoever speaks. |
| `ax`, `ay` | where the anchor sits in the box, 0 to 1 from the left and from the bottom (default 0.5 and 0) |
| `clamp` | `1`: slide back inside the screen edges (default); `0`: never move the box |
| `show` | `1`: draw the text (default); `0`: do not draw it |

Choose a look per line with `look=name` (in the brackets after a name, or on `SPEAK` and `NARRATE`), or give a character a
default with `CAST: JOHN look=shout`. A look that is anchored above the speaker follows them; a look with `x` and `y` is one
box in one place, shared by everyone who uses it. An unknown look name, an unknown key, a bad colour and a lone `x` are errors
that name the line.

## Cast keys

`CAST: NAME key=value key=value ...`. The separators are spaces; values have no spaces. Unknown look keys and bad values are
errors. Look keys you leave out are chosen from a hash of the name, so a name always gets the same look.

| Key | Values |
|---|---|
| `gender` | `m`, `f`, `n` |
| `child` | `0`, `1` |
| `skin` | `0` to `5` (a built-in tone) or a colour `0xRRGGBB` |
| `hair`, `top`, `bottom` | a colour `0xRRGGBB` (decimal also works) |
| `hairstyle` | `short`, `long`, `bun`, `bald`, `curly`, `spiky` (a `bun` under a hat becomes `short`) |
| `coat`, `dress`, `glasses`, `beard`, `scarf` | `0`, `1` |
| `hat` | `none`, `fedora`, `cap`, `beanie` |
| `asset` | the name of a character in your library (see [Tutorial 3](../tutorials/03-your-own-art.md)); the other look keys are then used only for voice (`gender`, `child`) and size (`child`) |

`gender` and `child` also choose the automatic voice. `child=1` draws a smaller character.

Voice and text keys, on the same line:

| Key | Values |
|---|---|
| `voice` | `auto` (default), `off` (this character is silent), or `<engine>:<voice>`: `espeak:en-us+m3`, `pyttsx3:Zira`, `piper:en_US-ryan-medium`. `python blaze.py voices` lists what is installed. |
| `rate` | words per minute for this character, 40 to 400 (default: the video's `--wpm`) |
| `pitch` | 0 to 99, for engines that support it (espeak) |
| `look` | the default text look for this character's lines |

The narrator is `CAST: Narrator voice=...` (it may also take `gender`). A voice that is not installed is an error before any
drawing, saying what to install. See [Tutorial 4](../tutorials/04-voices-timing-subtitles.md).

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

- a speaker that is not declared and not in capitals; a command naming someone who is not in the screenplay
- an unknown command; a command whose numbers are missing or are words
- an unknown or badly valued look key, an undefined look, a `base=` that does not exist
- a bad `voice`, `rate` or `pitch`; a voice whose engine or model is not installed
- an unknown look key in CAST, a bad flag value, an unknown hat or hairstyle, a bad gender
- an unknown place or mood in `gen:`, or a `gen:` spec not in the form `gen:<place>:<mood>`
- a `CAST:` asset or a `BACKDROP:` name that is not in the library
- a screenplay with no spoken or narrated line at all

**Warnings** do not stop anything; the page lists them under *Heads up* and the command line prints them:

- `... is not supported` for `STYLE`, `CAMERA`, `WEATHER`
- `text outside [brackets] ignored`
- `not understood, shown as narration`
- `X enters but never speaks and is not in CAST (a typo?)`
- `Jon looks like John: two different characters?`
- `Titel was taken as a new speaker; did you mean TITLE: ?`
- `... is not on stage, so [MOVE] was skipped` (and the same for `HOP`, `EXIT`, a repeated `ENTER`)
