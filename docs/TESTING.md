# Testing and CI

Every test runs on GitHub Actions, on every push and pull request, on the systems the tests are about: Linux, **Windows** and
macOS. This page explains what runs where, how to read the result, and why a green run means something specific.

[![tests](https://github.com/MrGrimJoe/blaze/actions/workflows/ci.yml/badge.svg)](https://github.com/MrGrimJoe/blaze/actions/workflows/ci.yml)
[![installer](https://github.com/MrGrimJoe/blaze/actions/workflows/build-blaze-installer.yml/badge.svg)](https://github.com/MrGrimJoe/blaze/actions/workflows/build-blaze-installer.yml)
[![screens](https://github.com/MrGrimJoe/blaze/actions/workflows/screenshots.yml/badge.svg)](https://github.com/MrGrimJoe/blaze/actions/workflows/screenshots.yml)

What a green run does **not** prove is in [STATUS.md](STATUS.md).

## Run the tests yourself

```
pip install -r requirements.txt pytest
python blaze.py doctor                          # which tools this computer has (the tests use what is installed)
python -m pytest tests                          # Blaze: real renders, voices, the page's server, the launcher, the workflow files
(cd studio && python -m pytest tests)           # the desktop studio
(cd cdrca && node tests/transpiler.test.js && node tests/render.test.js)       # CDRCA itself
python tools/check_docs.py                      # links, every screenplay in the docs parses, README links every file
actionlint                                      # the workflow files (pip install actionlint-py)
```

Locally a test that needs a missing tool is skipped. On CI that is not allowed (see Skips below).

## The workflows

| Workflow | Runs on | What it does |
|---|---|---|
| [`ci.yml`](../.github/workflows/ci.yml) | every push and pull request | all the test jobs below, then one combined report |
| [`build-blaze-installer.yml`](../.github/workflows/build-blaze-installer.yml) | every push (called by `screenshots.yml`), every `v*` tag, and by hand | builds the Windows installer, installs it silently, runs the installed app end to end, photographs it; publishes a release when asked |
| [`screenshots.yml`](../.github/workflows/screenshots.yml) | every push | photographs every screen of the page, the studio and the installer in real browsers and gathers them in a gallery ([screenshots.md](screenshots.md)) |

### Jobs in `ci.yml`

| Job | Systems | Runs | What only this job can show |
|---|---|---|---|
| `blaze` | Linux, **Windows**, macOS | all of `tests/`, then CDRCA's own tests | the same code on three systems: file paths, console encoding, ffmpeg builds, real renders, the page's server, the launcher; on Windows the **system (SAPI) voices** through `pyttsx3`, including a voice chosen per character |
| `studio` | Linux, **Windows** | all of `studio/tests` (the desktop window, the offline demo, providers, orchestrator) | the PyQt window and its pipeline on Windows |
| `blender` | Linux | `tests/test_blender.py` against a real Blender | `.blend` characters and backdrops |
| `piper` | Linux, **Windows** | `tests/test_voices.py` with the real `piper` program and a real voice model, including a real video | real neural voices, and the Piper command line on Windows |
| `docs-and-licence` | Linux | `tools/check_docs.py`, the licence checks, **`actionlint`** on every workflow | broken links, screenplays in the docs that no longer parse, a README that does not link every file, a workflow file with a mistake |
| `test-report` | Linux | combines the reports of all of the above | a test run that never reported, an unexpected skip |

## Reading a run

Open the run on the **Actions** tab. Its **summary** page ends with the **Test report**: one table with a row for every test
run (for example `Blaze tests (windows-latest)`), the counts, and under it every skipped test with the reason. Each job's own
summary has the same information for that job: **passed, skipped, failed per test file**, so that you can see that
`tests/test_voices.py` ran 48 tests on Windows and which ones were skipped, and not only a total.

A run is green only if every row is `ok`:

- no test failed or errored;
- no test was skipped for a reason the job does not list (see Skips);
- at least one test ran;
- every expected report exists. A job that crashed before it got to testing shows as `NO REPORT`, and fails the run.

The same report is uploaded as the `test-report` artifact, and each job uploads its own report (`report-*`).

## Skips

A test is skipped when something it needs is missing (Blender, a voice engine, a browser). On your own computer that is fine.
On CI it is a way for a test to stop testing without anyone noticing, so each job lists the skip reasons it accepts as a
regular expression (`skips` in the job's matrix in `ci.yml`). Anything else turns the run red and is listed as **NO** in the
report.

| Leg | May skip | May **not** skip |
|---|---|---|
| Linux, macOS | Blender (own job), the real Piper (own job), `pyttsx3` (Windows only) | espeak-ng voices (installed there), everything else |
| Windows | Blender, the real Piper (own job), espeak-ng voices (not installed on the runner), tests that need a POSIX shell script | **anything about `pyttsx3`**: the Windows system voices are what this leg exists to test |
| Blender job | nothing | everything: Blender is installed on purpose |
| Piper job | Linux: `pyttsx3` tests. Windows: espeak-ng tests | everything about Piper |
| Studio | the two Godot integration tests, which need a Godot binary | everything else |

Three guard tests turn a missing tool into a failure on CI. They are skipped locally and run when CI sets the variable:

| Variable | Set by | Guard |
|---|---|---|
| `BLAZE_REQUIRE_VOICE=1` | `blaze` and `piper` jobs | at least one voice engine exists |
| `BLAZE_REQUIRE_BLENDER=1` | `blender` job | Blender is installed |
| `BLAZE_REQUIRE_PIPER=1` | `piper` job | the real `piper` program and a voice model are installed |

## When a job fails

The job that runs the tests continues past a failure, commits its full log to a branch named `ci-debug-logs-<job>-<system>`
(for example `ci-debug-logs-windows-latest`, `ci-debug-logs-piper-ubuntu-latest`), and then fails. Open that branch to read the
whole log, without downloading anything. The log holds the output of `pytest -v -rs`, so it shows every test and every skip.

## What the tests are about

| Folder or file | What it checks |
|---|---|
| [`tests/test_blaze.py`](../tests/test_blaze.py) | the parser, the compiler's generated CDRCA, the pipeline, real end-to-end videos |
| [`tests/test_language.py`](../tests/test_language.py) | strict names and commands, the explicit core and the shorthand that expands into it (`to_core` round trip), text looks, non-Latin names |
| [`tests/test_voices.py`](../tests/test_voices.py) | a voice per character: espeak-ng, system voices, Piper (a stand-in program that runs on every system, and the real one on CI), empty-audio detection, the voice endpoints of the page, the CLI |
| [`tests/test_voice_engines.py`](../tests/test_voice_engines.py) | the voice engines on the system the tests run on |
| [`tests/test_ui.py`](../tests/test_ui.py) | the page's server and what it returns |
| [`tests/test_ai_animation.py`](../tests/test_ai_animation.py) | the AI writer, with scripted stand-ins for the providers |
| [`tests/test_blender.py`](../tests/test_blender.py) | the Blender bridge (a stand-in everywhere, real Blender on its own job) |
| [`tests/test_launcher.py`](../tests/test_launcher.py) | the launcher the installer's shortcut runs |
| [`tests/test_installer_and_workflows.py`](../tests/test_installer_and_workflows.py) | the installer's staging, its Inno Setup script, and that the workflows only use files that exist |
| [`tests/test_workflows.py`](../tests/test_workflows.py) | the workflow files: a bash script left to PowerShell on Windows, `pytest \| tee` without `pipefail`, bash syntax, report names that do not match, a Windows leg allowed to skip its voice tests |
| [`tests/test_ci_report.py`](../tests/test_ci_report.py) | the report tool, including the skip policy |
| [`tests/test_license.py`](../tests/test_license.py) | the licence files |
| `studio/tests/` | the desktop studio |
| `cdrca/tests/` | CDRCA's transpiler and renderer |
| [`tools/screens/ui_screens.js`](../tools/screens/ui_screens.js) | not a test suite, but it **asserts** as it photographs: an error screen must show the error, choosing a voice must write it into the screenplay and Play must work |

## Mistakes the tests were written to catch

Each of these happened, or was found, and has a test so it cannot come back:

- A bash script run by PowerShell on a Windows runner (a step with no `shell: bash`).
- A job that pipes `pytest` into `tee` without `shell: bash`: without `pipefail` a failing test still shows as a pass.
- `ffprobe -of csv=p=0` prints a trailing comma on some builds, so comparing its output with `==` fails on macOS and Windows.
- A voice engine that exits successfully but writes a WAV file with zero frames (Windows `pyttsx3`, a missing voice). It is now an
  error for every engine, not a silent video.
- A test that blanks `PATH` to pretend a tool is missing (unreliable on Windows) instead of patching the lookup.
- A stand-in program written as a POSIX shell script, which Windows cannot run by name.
- Printing a character name such as `Zoë` to a Windows console that cannot show it.
- A demo screenplay that asks for an engine-specific voice, and so fails where that engine is not installed.

## Adding a test

1. Put it in `tests/` (or `studio/tests/`). Prefer testing real behaviour: real files, real subprocesses, a real render when the
   tools exist.
2. If it needs a tool that CI installs, add a `BLAZE_REQUIRE_*` guard test so that a CI machine without the tool fails instead of skipping.
3. If it legitimately skips somewhere, make sure the reason text matches the `skips` of the jobs where that is accepted.
4. `python tools/check_docs.py` and `actionlint` after changing docs or workflows.
