# Status: what is verified, where, and what is not done

A green run on one machine says little about the others. This page says what has been checked, by what, and what has not.
It is a snapshot (**2026-10-15**); the live answer for tests is the latest run on the Actions tab ([TESTING.md](TESTING.md)).

## Verified, and how

| Area | Verified by | Where it ran |
|---|---|---|
| Screenplay language: strict names and commands, the explicit core, text looks, non-Latin names | `tests/test_language.py`, `tests/test_blaze.py`; the screenplay in every doc parses (`tools/check_docs.py`) | Linux |
| The generated CDRCA scripts | the tests above, CDRCA's own transpiler, and real renders. The warehouse demo rendered with the previous code and with the current code gives **identical frames** (2,983 of 2,983, voices off) | Linux |
| Voices: espeak-ng, chosen per character, speed and pitch | `tests/test_voices.py` | Linux |
| Voices: `pyttsx3` chosen per character | `tests/test_voices.py::TestPyttsx3PerCharacter`: against the real `pyttsx3` (131 voices, through its espeak driver) | Linux. **Not the Windows SAPI voices** |
| Voices: Piper | `tests/test_voices.py::TestRealPiper` against the real Piper 1.8.0 and the real `en-us-lessac-low` model: listing, a sample, speed, a character on Piper and one on espeak-ng in the same video, a real video with a sound track. Piper accepts both spellings of its output option | Linux |
| Empty audio from an engine is an error | `tests/test_voices.py::TestEmptyAudio`, for espeak-ng, `pyttsx3` and Piper | Linux |
| The page: voice drop-downs, Play, the screenplay rewritten when a voice is chosen, error messages | `tools/screens/ui_screens.js`, which asserts as it photographs: 18 screens, including a real video made through the page, the library panel, Editor mode and the Running timeline | Linux, with the bundled Chromium |
| The three modes (Editor, Smart, Running) and the library panel: adding a PNG and a backdrop, the "not in the library" message, Editor's line numbers and error line, Running's scenes and per-speaker rows, clicking a block or line to seek, dragging the playhead, keyboard, speed, zoom, reload, phone width | `tests/test_ui_library_and_modes.py` (25 tests) and a real browser run: the uploaded character and backdrop appear in a real rendered video; seeking and scrubbing were checked against a playable copy of that video | Linux, with the bundled Chromium |
| The installed app's end-to-end check (`installer/smoke_installed.py`), including the new voice preview, strict-name and looks-demo checks | run from source | Linux |
| CDRCA's tests | `node tests/transpiler.test.js`, `node tests/render.test.js` | Linux |
| Blaze Studio | `studio/tests`: 344 passed, 2 skipped (the Godot integration tests) with all its packages installed | Linux, offscreen |
| The workflow files | `actionlint` 1.7.12 with shellcheck and pyflakes: clean; `tests/test_workflows.py`; every bash step syntax-checked; the commands of the test steps run by hand (pytest with the junit report, the report tool, CDRCA's tests, the screenshot script, the smoke test) | Linux |
| The Linux leg of `ci.yml`, as CI runs it (same environment variables, same skip policy) | a full run with `tools/ci_report.py`: every skip was accepted by the policy | Linux |

## Not checked with the real thing

- **A real `.blend` through Blender, from the page.** No Blender was installed where this was built. The server's handling (the install
  message, the render call, a Blender error reported not raised, nothing left behind) is tested with a stand-in; `tests/test_blender.py`
  runs the real Blender on its own CI job, but the page's upload of a real model has not been tried.
- **The Running player playing the mp4.** The bundled headless Chromium cannot decode H.264, so the picture there is black. Real Chrome,
  Edge and Firefox can; the screenshots workflow's installed-page leg runs in real Chrome on Windows.

## Never run yet

These are set up as GitHub Actions but **have not run on GitHub with the current code**. The first run may need small fixes;
a failing job commits its log to a `ci-debug-logs-*` branch ([TESTING.md](TESTING.md)).

- **Windows and macOS legs of `ci.yml`** (`blaze`, and the Windows leg of `studio`). The changes were written with those systems
  in mind (a `.bat` stand-in for Piper, no blanking of `PATH`, safe console output, a check for empty audio) but no Windows or
  macOS machine ran them.
- **The Windows system (SAPI) voices** chosen per character: `tests/test_voices.py::TestPyttsx3PerCharacter`, and the SAPI check
  in the installer's smoke test. Only the Windows runner can show them.
- **The new `piper` job** on Linux and Windows, including the download and cache of the voice model, and the real Piper on Windows.
- **The `test-report` job**: the artifacts, the combined table, and the `NO REPORT` check have run only on this machine's output.
- **The Windows installer** (build with Inno Setup, silent install, the installed app) with the new files in it (`blaze/looks.py`,
  `examples/looks-and-voices.txt`).
- **The screenshots workflow in real Google Chrome.** Here the bundled Chromium cannot play the mp4, so the player screen was not seen playing.
- **The new `actionlint` step** in the `docs-and-licence` job.

## Not done

- **Removing Blaze Studio (the PyQt window).** It was left in place: nobody asked for it to be deleted, and it cannot be
  removed without choosing what happens to the AI writer. Blaze's own code depends on `studio/` in exactly three places,
  and `tests/test_architecture.py` keeps it to those three:
  1. `blaze/ai.py` imports the text providers from `studio/src/providers` (Anthropic, Gemini, OpenAI), and reads the same `config.yaml`.
  2. `blaze/ui.py` and `blaze/launcher.py` use `studio/config.yaml` as the default configuration, and the launcher has the studio's
     entry point and self-test.
  3. The installer (`installer/stage.py`, `installer/blaze.iss`, `installer/runtime-requirements.txt`) packages the studio and PyQt6.
  Removal would be: move the text-provider part of `studio/src/providers` (with its four provider tests) and a trimmed
  `config.yaml` into `blaze/`, point `ai.py`, `ui.py` and the launcher at them, delete `studio/`, `studio_app.pyw`,
  `tools/screens/studio_screens.py`, the studio job in `ci.yml` and `screenshots.yml`, the Studio tutorial and pictures, and the Studio
  parts of the installer and its tests. It is a large change to the installer, so it should be made on a branch and proven by the
  Windows installer workflow before it is merged.
  Studio's own scene composer still picks a place and mood from words in AI text ("sand" gives a beach), which the screenplay
  language forbids; the screenplay path does not use it.
- **A JavaScript-only core.** Blaze is Python (the compiler, the art, the voices, the page's server) around JavaScript (CDRCA and
  the renderer). The hard part of removing Python is `blaze/art.py`, which draws characters and backdrops with Pillow; it could be
  redrawn on a canvas in the headless browser that already ships. The voices, the pipeline and the server are small by comparison.
- **Long generated scripts.** CDRCA hides props an action does not mention, so every action lists every prop. A default on CDRCA's side would fix it ([CDRCA-PROPOSALS.md](CDRCA-PROPOSALS.md)).
- **Named parameters in `Words(...)` and `Picture(...)`.** They are rows of numbers ([atoms.md](reference/atoms.md)); named parameters need CDRCA support too.
- **Live AI providers.** The AI writer and Studio's own-story mode are tested with scripted stand-ins only; they need a person's key.
- **Old screenplays.** The language is stricter: a line such as `Note: bring umbrella` is now an error and `[MOV JOHN 3]` no longer
  passes silently. The messages say what to write ([screenplay reference](reference/screenplay.md)); there is no automatic converter.

See also: [LANGUAGE-DESIGN.md](LANGUAGE-DESIGN.md) (the rules for the language, and its debts), [CHANGELOG.md](../CHANGELOG.md).
