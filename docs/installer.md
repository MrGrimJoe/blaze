# The Windows installer

Blaze comes as a normal Windows installer, `Blaze_Setup_<version>.exe`. **Everything Blaze needs is inside it**: its own Python,
Node.js, ffmpeg and the headless browser it draws with, Windows' built-in voices, and **Blaze Studio**, a desktop window that plans and draws a video from a description ([Tutorial 8](tutorials/08-blaze-studio.md)). You do not install anything else, you
do not need administrator rights, and nothing is changed outside its folder except the Start menu and the uninstall entry.

## Getting it

You never build it yourself. GitHub Actions builds it:

1. Open the repository's **Actions** tab.
2. Choose **Build Blaze Installer** (or **Screens**, which builds it too) and open the latest run.
3. Under **Artifacts**, download **blaze-installer**, unzip it, and run `Blaze_Setup_<version>.exe`.

To publish a release people can download without an account on the repository, push a version tag (`v0.2.0`), or run
**Build Blaze Installer** by hand with *publish_release* ticked. A release is created with the installer attached.

> **Windows may warn "Windows protected your PC"** the first time. The installer is not code-signed (a signing certificate
> costs money). Choose **More info**, then **Run anyway**. Everything in it is open: see
> [THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md) for what is bundled.

## What the wizard does

Welcome, the license (the Islamic Open Source License, in plain text), where to install (default: your own programs folder, so
no admin prompt), an optional desktop shortcut, then it installs and offers to open Blaze. Screenshots of every page are produced by
the [Screens workflow](screenshots.md).

| Where | What |
|---|---|
| `%LOCALAPPDATA%\Programs\Blaze` (or the folder you choose) | the program: `app\` (Blaze), `runtime\` (Python, Node, ffmpeg, browser) |
| Start menu | **Blaze** (opens the page), **Blaze Studio** (the desktop window), **Blaze videos**, **Blaze examples**, and the uninstaller |
| `%APPDATA%\Blaze\Studio` | Blaze Studio's settings and the files it makes |
| `%USERPROFILE%\Videos\Blaze` | the videos you make |
| `%USERPROFILE%\Documents\Blaze\library` | your own characters and backdrops ([Tutorial 3](tutorials/03-your-own-art.md)) |
| `%APPDATA%\Blaze\config.yaml` | your settings, including the AI provider key if you add one (it starts with every key empty) |
| `%LOCALAPPDATA%\Blaze\blaze.log` | what the app printed; look here if something goes wrong |

## Using it

Open **Blaze** from the Start menu. A browser tab opens with the page (it is served only from your own computer). **Closing
the tab closes Blaze** after a few seconds; while a video is being made it keeps going until it is done. If Blaze is already
open, starting it again just shows the page again.

Voices use Windows' own voices (through pyttsx3). If your Windows has none, videos are made without sound and the page says so.

## Updating and uninstalling

Run a newer installer over the old one; your videos, library and settings are kept. To remove Blaze use **Settings, Apps** or
the Start menu's uninstaller. It removes the program and leaves `Videos\Blaze`, the library and your settings alone.

## How it is built and proved

`installer/stage.py --download` assembles the folder to pack: it copies the app, downloads the embeddable Python and installs the
packages into it (Pillow, PyYAML, pyttsx3, and the three AI providers' libraries), copies Node, downloads ffmpeg (a GPL build, with
its source notice), and installs Playwright with its headless Chromium. Inno Setup (`installer/blaze.iss`) packs it with LZMA
compression and a modern wizard using the Blaze icon and pictures (`installer/make_assets.py` draws them).

Then, on a clean Windows machine in the same workflow run, it:

1. installs the `.exe` silently, per user;
2. checks every file and the Start-menu shortcut exist, and that the shipped config has no key;
3. imports everything in the bundled Python, and starts the Windows voice engine;
4. **opens Blaze Studio from the install and runs the offline demo through its window** (`studio_app.pyw --selftest`);
5. **starts the installed app exactly as the shortcut does and uses it**: checks the page, chooses a provider (and proves the key
   is saved in your own folder, not in the install folder), checks that your library is in your own folder, adds a character and
   removes it, makes a real video, checks that it comes with the timeline Running mode draws, streams it back as a player would, and
   tells the page to close and proves the app stops by itself (`installer/smoke_installed.py`);
6. photographs the installed app's page in real Chrome;
7. uninstalls, and checks the program is gone and `Videos\Blaze` is kept.

A separate job runs the real installer page by page and photographs each one. The files and the script are checked for
consistency by tests that run everywhere (`tests/test_installer_and_workflows.py`).

**Status:** this workflow has not run yet. It needs Windows, which the code was written without. The first run may need a fix;
the logs of each step say what. The staged app itself and the installed-app check were run against a staged copy of the app on
Linux and pass.

## Building it on your own Windows machine

You normally don't need to. If you want to: install Python 3.12, Node.js 22 and [Inno Setup 6](https://jrsoftware.org/isinfo.php), then

```
python installer/stage.py --download
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DAppVersion=0.2.0 installer\blaze.iss
```

The installer is written to `dist\`. To change the look, edit `installer/make_assets.py` and run it, or replace the files in
`installer/assets/`.
