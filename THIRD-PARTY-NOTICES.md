# Third-party software

Blaze is released under the IOSL (see [LICENSE.md](LICENSE.md)). It uses, and the Windows installer bundles, the programs
below, each under its own license. Blaze runs them as separate programs or imports them as libraries; it does not change
them.

| Software | Used for | License | Where |
|---|---|---|---|
| CDRCA | the animation language and renderer | IOSL | github.com/ISLAH-org/CDRCA (in `cdrca/`) |
| three.js | drawing, inside CDRCA | MIT | in `cdrca/Front-end/` |
| Python (embeddable) | runs Blaze (Windows installer) | PSF License | python.org |
| Pillow | pictures | HPND | python-pillow.org |
| PyYAML | reading `config.yaml` | MIT | pyyaml.org |
| pyttsx3 | Windows system voices (Windows installer) | MPL-2.0 | github.com/nateshmbhat/pyttsx3 |
| Node.js | runs CDRCA's renderer (Windows installer) | MIT | nodejs.org |
| Playwright | drives the headless browser | Apache-2.0 | playwright.dev |
| Chromium (headless, fetched by Playwright) | draws the frames | BSD-3-Clause and others | chromium.org |
| ffmpeg (GPL build) | joins frames and sound into mp4 | GPL v3 | github.com/BtbN/FFmpeg-Builds, source at ffmpeg.org |
| espeak-ng (optional, not bundled) | voices on Linux and macOS | GPL v3 | github.com/espeak-ng/espeak-ng |
| Blender (optional, not bundled) | `.blend` characters and backdrops | GPL v3 | blender.org |
| PyQt6 | Blaze Studio's windows (in the Blaze installer and the studio installer) | GPL v3 or commercial | riverbankcomputing.com |
| PyInstaller and Inno Setup | building the studio installer | GPL with bootloader exception; Inno Setup license | pyinstaller.org, jrsoftware.org |

Notes

- The ffmpeg in the Blaze installer is a GPL build because Blaze encodes with x264. It is a separate program that Blaze starts;
  its source is available from the links above. The installer includes this file so the notice travels with it.
- PyQt6 is GPL. Blaze Studio (`studio/`) imports it, and both installers include it (the Blaze installer carries Blaze
  Studio as a second app); if you distribute them you must satisfy its terms (or buy Riverbank's commercial license). Blaze
  itself (`blaze/`) does not import PyQt6; the two are separate programs in one installer.
- This list describes what the code does; it is not legal advice.
