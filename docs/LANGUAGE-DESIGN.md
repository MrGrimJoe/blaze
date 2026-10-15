# Language design: for whoever owns the screenplay language

This is a hand-over note. It says how the screenplay language is layered, the rules that keep it from going wrong again, and
what adding a feature involves. The reference for users is [Screenplay format](reference/screenplay.md).

## What the language is, and what it is not

Blaze has **two languages** and they are separate:

1. **CDRCA**, the animation language Blaze renders with. It lives in `cdrca/` and is **not Blaze's to change**. Blaze only
   writes CDRCA scripts. Anything it would like from CDRCA is written down in [CDRCA-PROPOSALS.md](CDRCA-PROPOSALS.md) for the
   CDRCA owner to accept or refuse, and the patches Blaze needs today are in [CDRCA-CHANGES.md](CDRCA-CHANGES.md).
2. **The screenplay format**, which is Blaze's own and is what this note is about. It is compiled *into* CDRCA scripts
   (`compiler.py`).

Everything below is about the second one. Nothing in this layer needs a change to CDRCA, and it should stay that way.

## The layers

```
screenplay text
   │  screenplay.py  (two passes; strict names; errors with line numbers)
   ▼
CORE statements, as a Screenplay model     ◀── `blaze expand` prints this (to_core)
   │  compiler.py    (positions, timing, text looks -> props and actions)
   ▼
CDRCA scripts (one per scene)  ──▶  CDRCA renders  ──▶  ffmpeg  ──▶  mp4
```

- **The core** is what a statement *means*: `SPEAK`, `NARRATE`, `ENTER`, `EXIT`, `MOVE`, `HOP`, `PAUSE`, `CAST`, `DEFINE LOOK`,
  `SCENE`, `BACKDROP`, `TITLE`, `SUBTITLE`. Each one carries all its parameters. Nothing is implied by position or by a word.
- **The shorthand** (`NAME: text`, `> text`, `[MOVE JOE 3]`, sluglines, `NAME (look=x): text`) is only a shorter way to write core
  statements. Every shorthand line must expand to exactly one core statement (plus, for a spoken line, the commands in its
  brackets), and `parse(to_core(sp))` must give back the same screenplay. `tests/test_language.py` checks this on the sample
  stories.
- **The model** (`Screenplay`, `Scene`, `Beat`, `Look`) is the contract between the parser and the compiler. The compiler never
  sees text; the parser never knows about props.

If you want a new convenience, add it as shorthand that expands to the core. If it cannot be expressed in the core, the core is
missing a statement, and that is the thing to design first.

## Rules that keep it sound

1. **Nothing is guessed from words.** Positions are numbers, colours are `0xRRGGBB`, places and moods come from fixed lists. A
   value that is not exact is an error that names the line and says what is valid.
2. **Nothing is invented from a typo.** A speaker is declared (`CAST:`) or written in capitals; a command may only name someone
   who exists. `parse()` runs twice for this: pass 1 collects every name that is cast, speaks or enters, pass 2 is strict about
   them. A mistake must stop the build or be reported, never quietly become a new character or a skipped line.
3. **Unknown means error.** An unknown command, look key or voice is an error with the closest valid name suggested. Warnings are
   for things that are suspicious but possibly intended (two almost-equal names, a character who enters and never speaks).
4. **Looks and voices are named bundles of numbers, defined by the author.** There is no built-in "style: dramatic". The five
   built-in looks are ordinary looks and can be redefined. A voice is `<engine>:<voice>` and is checked against what is
   installed before anything is drawn.
5. **The text file is the only source of truth.** The page edits the screenplay (`setCastKey` in `ui_assets/index.html` rewrites
   a `CAST:` line); it keeps no settings of its own. A video must be reproducible from the text alone.
6. **No screenplay text is ever executed.** A voice id cannot be a path or a command; Piper models are found by name in known
   folders only.

## Adding a feature: the checklist

1. Write the core statement first: its name, its parameters, what is an error. Put it in the reference.
2. `screenplay.py`: parse it into the model (add a field to `Beat`/`Screenplay` if needed), and make `to_core` print it.
3. `compiler.py`: compile it. If it needs something CDRCA does not do, write it in `cdrca-lib/atoms.cdrca` using only what CDRCA
   already offers, or add a request to CDRCA-PROPOSALS.md. Do not change `cdrca/`.
4. Add shorthand last, if it earns its place, and add it to the expansion table in the reference.
5. Tests: a parse test, a round-trip test (`to_core`), an error-message test, and a compile test. Then
   `python tools/check_docs.py`, which parses every screenplay in the documentation.

## What is in this change (version 0.3 work)

- Strict names and commands (the typo-creates-a-character and silent-skip problems).
- The explicit core, `DEFINE LOOK` / `look=` for text, `none` for voice-only lines, `blaze expand`.
- A voice per character (`CAST: NAME voice=... rate=... pitch=...`), the `blaze voices` command, and the page's per-character
  voice pickers with a Play button. Engines: espeak-ng, pyttsx3, Piper.
- Non-Latin character names (declared with CAST), with safe file names and CDRCA aliases.
- A test that Studio's copy of `atoms.cdrca` has not drifted from `cdrca-lib/atoms.cdrca`, and one that keeps Blaze's own modules from depending on the studio (`tests/test_architecture.py`).

## Known debts

These are real and were left alone on purpose, so the next owner knows where they are. The full list, with what was verified
and where, is in [STATUS.md](STATUS.md).

- **Studio still exists.** It is a second front end (`studio/`, PyQt) with its own scene composer that guesses a place and mood
  from words in AI text, which the rest of the language forbids. `blaze/ai.py`, `blaze/ui.py`, `blaze/launcher.py`, the installer,
  CI and many tests depend on it, so removing it is its own piece of work. STATUS.md lists the steps; `tests/test_architecture.py`
  stops any new module depending on it.
- **Python plus JavaScript.** The core is Python; CDRCA and the renderer are JavaScript. Porting `art.py` (Pillow drawing) is the
  hard part of going JavaScript-only; it could be redrawn on a canvas in the headless browser that already ships.
- **Generated scripts are long.** CDRCA hides props an action does not mention, so every action lists every prop (for a scene it
  is about actions x props lines). A CDRCA-side default would fix it; see CDRCA-PROPOSALS.md.
- **Positional arguments in `Words(...)`/`Picture(...)`.** The constructor calls are a row of numbers. They are documented in
  [atoms.md](reference/atoms.md), but named parameters would read better and need CDRCA support.
- **No converter for old screenplays.** The language is stricter than it was (names and commands); the error messages say what
  to write, but nothing rewrites an old file.
