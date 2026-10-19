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

The same report is uploaded as the `test-report` artifact, and each job uploads its own report (`report-*`). Every run writes its report to a file named after its system (`blaze-windows-latest.json`, ...): the final job downloads them all into one folder, and two runs with the same file name would overwrite each other and show as missing.

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

`BLAZE_NO_BROWSER=1` is not a guard: it tells the launcher not to open a browser, for scripts and tests that start the installed app.

## When a job fails

The job that runs the tests continues past a failure (or a time limit), commits its full log to a branch named
`ci-debug-logs-<job>-<system>` (for example `ci-debug-logs-windows-latest`, `ci-debug-logs-piper-ubuntu-latest`), and then fails.
Open that branch to read the whole log, without downloading anything. The log holds the output of `pytest -v -rs`, so it shows
every test and every skip. Two more places:

- If every test passed but the **report step** rejected the run (an unexpected skip, a missing report), the report's text is
  committed to the same branch as `report-<system>-run<N>.txt`.
- The `blaze` job also uploads its log as the `log-blaze-<system>` artifact, which does not depend on the push to the branch.

The installer workflow and the screenshots do the same in another way: a check that fails (a part of the staged installer that is
missing or too small, a check of the installed app, a screen of the page, a crash) is written as an **error annotation**, which is
shown on the run's page and can be read without opening the job log.

## Hangs

A hung test used to use up the whole job: on Windows the `blaze` and `piper` jobs ran into their one-hour limits and were cancelled,
and the cancelled job never reached the step that keeps its log. Now:

- Every pytest step runs with `--timeout=300 --timeout-method=thread` (`pytest-timeout`): a test that does not finish in five
  minutes prints the stack of every thread, which names the file and line it is waiting in, and stops the run. The Blender job allows
  ten minutes per test.
- Each test step has its own time limit (20 to 25 minutes, where the whole suite takes about a minute), and the log is committed when
  the step was cancelled as well as when it failed. `PYTHONUNBUFFERED` is set, so the log shows progress even through `| tee`.
- Blaze runs outside programs through `blaze/procs.py` (`run_bounded`): output goes to temporary files, not pipes, and when time runs out
  the whole process tree is stopped. `subprocess.run(timeout=...)` does not do that on Windows for a launcher such as `piper.exe`:
  it stops only the launcher, then waits for the pipes the child still holds.
- The Windows system voice is spoken in a process of its own (`blaze/_sapi_worker.py`, 60 seconds per line), because `pyttsx3`'s
  `runAndWait()` never returned on the runner and a call that never returns cannot be stopped from inside its own process.
- Questions asked while pytest is still collecting (does `piper` run, does `pyttsx3` have a voice) are bounded and asked once, in a
  process of their own: a hang there stopped every test, not only the ones that need the answer.

## Known risks

Not failing today, but what is most likely to turn a run red; the same list is in [STATUS.md](STATUS.md#known-risks).

- `ubuntu-latest` becomes Ubuntu 26 from 2026-10-19: the `apt` packages and `playwright install --with-deps` of the Linux jobs may
  need changing, or the jobs pinned to `ubuntu-24.04`.
- The actions the workflows use run on Node.js 20, which GitHub is retiring; they are forced onto Node 24 for now and only warn.
- A tagged release has not been published with the current code.

## What the tests are about

| Folder or file | What it checks |
|---|---|
| [`tests/test_blaze.py`](../tests/test_blaze.py) | the parser, the compiler's generated CDRCA, the pipeline, real end-to-end videos |
| [`tests/test_language.py`](../tests/test_language.py) | strict names and commands, the explicit core and the shorthand that expands into it (`to_core` round trip), text looks, non-Latin names |
| [`tests/test_voices.py`](../tests/test_voices.py) | a voice per character: espeak-ng, system voices, Piper (a stand-in program that runs on every system, and the real one on CI), empty-audio detection, the voice endpoints of the page, the CLI |
| [`tests/test_voice_engines.py`](../tests/test_voice_engines.py) | the voice engines on the system the tests run on |
| [`tests/test_ui.py`](../tests/test_ui.py) | the page's server and what it returns |
| [`tests/test_ui_library_and_modes.py`](../tests/test_ui_library_and_modes.py) | the library panel's server side (add a PNG, a talking mouth, a backdrop, a `.blend` through a stand-in for Blender, refusals, removal that cannot leave the library folder, the `asset=` check) and the timeline Running mode draws |
| [`tests/test_ai_animation.py`](../tests/test_ai_animation.py) | the AI writer, with scripted stand-ins for the providers |
| [`tests/test_blender.py`](../tests/test_blender.py) | the Blender bridge (a stand-in everywhere, real Blender on its own job) |
| [`tests/test_procs.py`](../tests/test_procs.py) | `run_bounded` always returns, and stops the child of a launcher that outlives it |
| [`tests/test_launcher.py`](../tests/test_launcher.py) | the launcher the installer's shortcut runs, when the app stops by itself, and `BLAZE_NO_BROWSER` |
| [`tests/test_installer_and_workflows.py`](../tests/test_installer_and_workflows.py) | the installer's staging, its Inno Setup script, that the workflows only use files that exist, that the staged app passes the installer's own size check, that the installed app has its example, and the check's annotations |
| [`tests/test_workflows.py`](../tests/test_workflows.py) | the workflow files: a bash script left to PowerShell on Windows, `pytest \| tee` without `pipefail`, bash syntax (with a bash that really runs: on Windows `bash` is often the WSL launcher), report names that do not match, two runs writing the same report file, a Windows leg allowed to skip its voice tests |
| [`tests/test_ci_report.py`](../tests/test_ci_report.py) | the report tool, including the skip policy |
| [`tests/test_license.py`](../tests/test_license.py) | the licence files |
| `studio/tests/` | the desktop studio |
| `cdrca/tests/` | CDRCA's transpiler and renderer |
| [`tools/screens/ui_screens.js`](../tools/screens/ui_screens.js) | not a test suite, but it **asserts** as it photographs: an error screen must show the error, choosing a voice must write it into the screenplay and Play must work, adding a character must clear the "not in the library" message, Editor mode must hide the side panel and mark the error line, and Running mode must draw a scenes row and a row per speaker |

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
- `pyttsx3`'s `runAndWait()` that never returns on Windows (now run in a process with a time limit), and `subprocess.run`'s own
  timeout that hangs on Windows when the program is a launcher (`blaze/procs.py`).
- A test that fails and makes pytest diff two whole audio files: on macOS `difflib` kept the job busy until it was cancelled. The
  test compares sizes and checksums.
- `bash` on a Windows runner being the WSL launcher, which fails every script with no message.
- A skip reason that says "espeak" where the job's allow-list says "espeak-ng", and report files with the same name in every
  matrix leg, so that all but one overwrote the others.
- A floor of 524 bytes for a 269-byte launcher in the installer's size check, which failed the installer build on every push.
- The page's example read from `tests/`, which the installer does not ship: in the installed app the example was empty.
- A browser opened by a test, which pings the page for ever and so keeps the app from stopping (`BLAZE_NO_BROWSER=1`).

## Adding a test

1. Put it in `tests/` (or `studio/tests/`). Prefer testing real behaviour: real files, real subprocesses, a real render when the
   tools exist.
2. If it needs a tool that CI installs, add a `BLAZE_REQUIRE_*` guard test so that a CI machine without the tool fails instead of skipping.
3. If it legitimately skips somewhere, make sure the reason text matches the `skips` of the jobs where that is accepted.
4. `python tools/check_docs.py` and `actionlint` after changing docs or workflows.
