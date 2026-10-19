# Changelog

## Unreleased (language, looks and voices)

**CI, the voices on Windows, and the installer** (2026-10-19: the workflows are green, and now named **Blaze tests**, **Blaze screens** and **Blaze installers**)
- Windows: the system voice (`pyttsx3`) is spoken in a process of its own (`blaze/_sapi_worker.py`, 60 s per line; on Windows it uses
  SAPI directly and synchronously). `runAndWait()` never returned on the runner and hung the `blaze` and `piper` jobs until their
  time limits.
- `blaze/procs.py`: `run_bounded` runs a program with a limit that holds on Windows too (output in temporary files, the whole
  process tree stopped); the voice engines use it. `subprocess.run(timeout=...)` hung after its own timeout on Windows for `piper.exe`.
- CI: a 5-minute limit per test with a stack dump of every thread, limits on every test step, unbuffered output, the log kept when a
  step is cancelled, the `blaze` log also as an artifact, the report's text kept when it rejects a run, one report file per system,
  and a bash that really runs for the workflow syntax test on Windows. Failed checks of the installer and the page are annotations.
- Installer: the size check no longer fails on the 269-byte launcher and says which part is wrong; the installed app has its example
  (the page read it from `tests/`, which is not shipped, so it was empty); `BLAZE_NO_BROWSER=1` starts the launcher without a browser.
- The README has a download table. The Windows installer is at a fixed address, the "Latest build" release, which the **Blaze installers**
  workflow edits after every build of `main` that passed all its checks (an Actions artifact cannot be linked: it needs a login and
  expires). The screens gallery and the test results are linked too.
- Known risks, not failing today: `ubuntu-latest` becomes Ubuntu 26 from 2026-10-19, the actions run on Node.js 20, and a tagged
  release has not been published with this code ([docs/STATUS.md](docs/STATUS.md#known-risks)).

**Three modes, and your own characters in the page**
- The page has three tabs: **Editor** (just the code, with line numbers and the error line marked), **Smart** (the page as it was) and
  **Running** (the finished video on a timeline: scenes, one row per speaker, a draggable playhead, a clickable list of lines, speed, zoom,
  arrow keys and Space). The last video is restored after a reload; the URL hash (`#editor`, `#smart`, `#running`) opens a mode.
- Characters and backdrops can be added, listed, given a talking mouth and removed from the page, from a PNG/JPG/WebP or from a `.blend`
  through Blender. New endpoints: `/api/library`, `/api/library/add`, `/api/library/remove`, `/api/library/img/...`.
- A `CAST: X asset=name` that is not in the library is reported while you type, on its own line.
- A finished job carries a `timeline` (scenes and lines on the video's clock) for the Running mode.
- Tests: `tests/test_ui_library_and_modes.py`; three new page screens (16 library, 17 editor, 18 running).
- Not verified here: a real `.blend` through Blender (none installed in the sandbox; the server tests use a stand-in for Blender), and the
  mp4 playing in the Running player (headless Chromium cannot decode H.264; seeking and the timeline were checked against a playable copy).

**Language**
- A screenplay is now two layers: an explicit core (`SPEAK`, `NARRATE`, `ENTER`, `EXIT`, `MOVE`, `HOP`, `PAUSE`, `DEFINE LOOK`) and the
  existing shorthand, which expands to it. `blaze expand story.txt` prints the core form; it parses back to the same screenplay.
- Names are strict. A speaker must be declared with `CAST:` or written in capitals; `Later that day: ...` is an error, not a new
  character. A command may only name a character in the screenplay (`[MOVE JOHM 3]` is an error with "did you mean John?").
- Unknown commands are errors with a suggestion (they were warnings, so `[MOV JOHN 3]` silently did nothing). Square brackets in
  speech that are not commands (`[the box]`, `[NASA]`) are kept as text.
- Commands that cannot happen (moving someone who is not on stage) are now reported instead of silently skipped.
- Warnings for names that are almost the same (`JOHN`/`JON`), characters that enter and never speak, and misspelt directives.
- Character names in any script (`Zoë`, `علی`) work when declared with `CAST:`; file names and CDRCA aliases stay ASCII and unique.
- `CAST: "Dr Smith" ...` quoted names.

**Text**
- Text looks: `DEFINE LOOK name key=value ...`, used per line (`JOHN (look=shout): ...`, `SPEAK ... look=shout`) or per character
  (`CAST: JOHN look=shout`). Anchored above the speaker or at a fixed `x`/`y`; `look=none` speaks without drawing.
- The five built-in looks (`bubble`, `caption`, `title`, `subtitle`, `none`) are ordinary looks and can be redefined.
- The generated scripts only contain the text props a scene uses.

**Voices**
- A voice per character: `CAST: JOHN voice=espeak:en-gb+m3 rate=140 pitch=40`; `voice=off` for a silent character.
- New engine: Piper (offline neural voices). espeak-ng and pyttsx3 accept a chosen voice too.
- `blaze voices` lists the installed engines and voices and plays samples.
- The page has a voice drop-down, a Play button and a speed box for every character; choosing writes the `CAST:` line.
- A voice that is not installed stops the build before drawing, with what to install.

**Tests and CI**
- Every test run reports through `tools/ci_report.py`: counts per test file, every skip with its reason, one combined table on the
  run's summary page (`test-report` job). A skip is accepted only for a reason its job lists; a job that never reported fails the run.
- New `piper` job: the real Piper and a real voice model on Linux and Windows. The Windows leg of `blaze` may not skip the system-voice tests.
- `actionlint` runs on every push; `tests/test_workflows.py` guards the workflow files (bash under PowerShell, `| tee` without
  `pipefail`, bash syntax, report names, skip policy).
- Fixed: the `blender` job piped pytest into `tee` without `shell: bash`, so a failing Blender test would not have failed the job.
- Fixed: the screenshots workflow started Blaze without checking that it came up.
- The page screenshots now assert what they show; three new screens (misspelt names and commands, the voice picker, text looks);
  the "A warning" screen no longer relies on an unknown command being a warning.
- The installer's end-to-end check also tests strict names, the system (SAPI) voices, a previewed voice, and the looks demo; the
  installer ships `examples/looks-and-voices.txt`.
- Same bug classes as the cross-platform fixes already made: every voice engine rejects an empty audio file; programs are run by
  full path; console output cannot crash on a name the console cannot show; tests no longer blank `PATH`, use a POSIX-only stand-in
  or compare `ffprobe` output without allowing for its trailing comma.
- `README.md` now links every file, and `tools/check_docs.py` enforces it. New: [docs/TESTING.md](docs/TESTING.md), [docs/STATUS.md](docs/STATUS.md).

**Other**
- `tests/test_language.py`, `tests/test_voices.py`; Studio's copy of `atoms.cdrca` is checked against `cdrca-lib/`.
- `docs/LANGUAGE-DESIGN.md`: hand-over note for the owner of the screenplay language, with the known debts.
- Not changed: CDRCA (`cdrca/`), Blaze Studio, the installer. Studio's own tests were run in the sandbox used for this change and gave the same
  result with and without it (279 passed, 44 failed for lack of its optional packages), so they say nothing about this change either way.
