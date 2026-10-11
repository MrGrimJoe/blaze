# The desktop studio (BlazEng) and the Windows installer

The `studio/` folder is **BlazEng, "AI Production Studio"**, an older, separate project that Blaze grew next to. The two
fit together like this:

| | Blaze (this repository's root) | BlazEng (`studio/`) |
|---|---|---|
| What it does | screenplay in, video out, deterministic | story prompt in; an AI director plans shots, makes art, composes scenes, renders, checks and repairs |
| Needs AI | no (optional, to write the screenplay) | yes (a text provider; image and vision providers for the full pipeline) |
| Interface | the page, the command line | a Qt window with an offline demo (see below) and a Python API |
| Shared | Blaze's AI writer uses BlazEng's provider layer (Anthropic, Gemini, OpenAI, and local options) | BlazEng's CDRCA backend uses Blaze's `atoms.cdrca` and the same renderer |

## Providers: no default

There is no default AI provider. Choose Anthropic, Gemini or OpenAI in the first-run window (or on Blaze's page) and paste
your own key; it is stored in `config.yaml` on your computer, which ships with every key empty. Details and the
independent text/vision/image slots are in [`studio/README.md`](../studio/README.md).

## What the desktop app does

`python main.py` (or **Blaze Studio** from the Start menu) opens the **first-run provider window** when no provider is chosen, then
the **main window**: you describe a video, it plans the shots, draws the characters, sets up and renders each scene and joins them
into one video, with progress, cancel, plain-language errors and a finished-video view. An **offline demo** runs the whole flow
with no AI, no key and no GPU. The tutorial is [Tutorial 8](tutorials/08-blaze-studio.md).

**Blaze Studio is in the Blaze installer** ([installer.md](installer.md)), which already carries Python, Node.js, ffmpeg and the
browser the demo needs, so it works there out of the box. The separate studio installer below is built around Godot and does not
include Node.js, so the offline demo (which renders with CDRCA) needs `render_backend: cdrca` and Node.js on that one.

## The studio's Windows installer is built by GitHub Actions

(Blaze itself has a separate installer: see [installer.md](installer.md).)

You do not build `AIProductionStudio_Setup.exe` on your computer. The workflow
`.github/workflows/build-installer.yml` builds it on a Windows runner:

1. check out the repository and install Python 3.12 and the studio's requirements, plus PyInstaller;
2. download and stage the pieces the spec expects: ffmpeg (`bin/ffmpeg.exe`), Godot 4.7.2 (`godot/`), and an empty `storage/`;
3. build the app with PyInstaller (`AIProductionStudio.spec`);
4. install Inno Setup and compile `installer.iss` into `dist\installer\AIProductionStudio_Setup.exe`;
5. upload the installer as an artifact (kept for 30 days);
6. start the built app headless and check that it opens and writes a per-user `config.yaml` with no key in it.

To get an installer, open the repository's **Actions** tab, choose *Build AI Production Studio Installer*, press
**Run workflow** (tick *publish_release* to attach it to a GitHub Release), then download the artifact. It also runs on pushes
to `main` that touch `studio/`.

If PyInstaller fails, the workflow pushes its log to a branch named `ci-debug-logs` so the failure can be read without
re-running. The smoke test (step 6) runs after the artifact is uploaded, so a failing check never hides the installer.

Because the app never writes inside its install folder (Program Files is read-only), the installed build keeps its
`config.yaml`, logs and generated files in `%APPDATA%\AI Production Studio`, seeding the config from the bundled template.

**Status:** this workflow and the installer have not been run yet (they need a Windows runner). The first run may need a
fix, most likely a missing file in the PyInstaller spec; the log branch is there for that.

There are two copies of the workflow: `.github/workflows/build-installer.yml` at the repository root (GitHub only reads
workflows from the root) and `studio/.github/workflows/build-installer.yml`, for when `studio/` is its own repository. Keep
the one that matches how you host the code.
