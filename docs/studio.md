# The desktop studio (BlazEng)

The `studio/` folder is **BlazEng, "AI Production Studio"**. Blaze uses it in two ways and ships it inside Blaze's Windows installer
as a second app, **Blaze Studio**.

| | Blaze (the repository root) | Blaze Studio (`studio/`) |
|---|---|---|
| What it does | screenplay in, video out, deterministic | a story description in; the studio plans the shots, draws, renders and joins them |
| Needs AI | no (optional, to write the screenplay) | for your own stories yes (a text provider; an image provider too); the **offline demo** needs none |
| Interface | the page, the command line | a desktop window, and a Python API |
| Shared | the AI writer uses the studio's provider layer (Anthropic, Gemini, OpenAI, and local options) | its CDRCA backend uses Blaze's `atoms.cdrca`, art code and renderer |

## Providers: no default

There is no default AI provider. Choose Anthropic, Gemini or OpenAI in the first-run window (or on Blaze's page) and paste your
own key; it is stored in `config.yaml` on your computer, which ships with every key empty. Local models are yours to set up. Details
and the independent text, vision and image slots are in [`studio/README.md`](../studio/README.md).

## What the desktop app does

`python main.py` (or **Blaze Studio** from the Start menu) opens the **first-run provider window** when no provider is chosen, then
the **main window**: you describe a video, it plans the shots, draws the characters, sets up and renders each scene and joins them
into one video, with progress, cancel, plain-language errors and a finished-video view. An **offline demo** runs the whole flow
with no AI, no key and no GPU. The tutorial is [Tutorial 8](tutorials/08-blaze-studio.md).

## It ships inside Blaze's installer

[Blaze's installer](installer.md) already carries Python, Node.js, ffmpeg and the browser the offline demo needs, so Blaze Studio
works there out of the box. Its settings and files are kept in `%APPDATA%\Blaze\Studio`, never in the install folder. The installer
workflow opens the studio from the install and runs the demo through its window.

## BlazEng's own repository

BlazEng also lives in its own repository, [github.com/MrGrimJoe/BlazEng](https://github.com/MrGrimJoe/BlazEng), where its setup
scripts, Godot installer and design notes are kept; they are not part of this repository. `studio/` here is the copy Blaze uses
and ships. It is the more recent one: it has no default provider, the real main window, the offline demo, a working cancel, and a
CDRCA renderer that draws backdrops. To bring those to the BlazEng repository, copy `studio/` over its working tree. The separate
repository keeps its own license file; the copy in this repository is released under the same license as everything else here.
