# Seeing every screen without running anything

You can check by eye that the interface loads and looks right without installing anything: a GitHub Actions run photographs
every screen and gathers them into one gallery.

## Get the gallery

1. Open the repository's **Actions** tab, choose **Screens**, and press **Run workflow** (it also runs on every push to `main`).
2. When it finishes, open the run. Its **summary** has a link to the gallery, and the page **Artifacts** has
   **blaze-screens-gallery** (unzip it and open `README.md`).
3. The gallery is also published on the repository's `ci-screenshots` branch: open `README.md` there to browse it with the
   pictures showing, with no download.

Each picture has a line under it saying what to check, so you can look for the right thing and write back what is wrong.

## What is photographed

| Section | How | Screens |
|---|---|---|
| **The Blaze page** | real Google Chrome against the running app | fresh page; example loaded; a mistake (red line, Go to line); a warning (Heads up); the format help; choosing an AI provider; AI ready (Whole story / Short scene); making a video (progress); the finished video playing; dark theme; phone width; tablet width |
| **The desktop studio's windows** | the real windows, drawn off-screen | the first-run provider window in five states (empty, Anthropic chosen, with a key, ready with a second image provider, Gemini ready); the **main window** empty, ready, working (shots and Cancel), failed, finished (a real demo run, with its still), and in the dark theme |
| **The Windows installer** | the real installer run page by page on Windows | welcome; license; license accepted; destination; tasks; ready; installing; finished; the app starting. *Best effort: it needs a desktop session, and the gallery lists any page it could not capture.* |
| **The installed app's page** | the installed app on Windows, in real Chrome | the same twelve screens as the page, served by the installed app with its bundled tools |

Nothing is faked: a screen that cannot be captured appears in the gallery as "could not be captured" with the reason.

## Running the screenshots yourself

```
python blaze.py ui --no-browser --port 8765 &
BASE_URL=http://127.0.0.1:8765 OUT=screens/page node tools/screens/ui_screens.js     # needs: npm i playwright
python tools/screens/studio_screens.py --out screens/studio                          # needs PyQt6
python tools/screens/make_gallery.py screens                                         # writes screens/README.md
```

Set `CHANNEL=chrome` to use an installed Chrome (needed to see the finished video play), `MAKE=0` to skip making a video, and
`ONLY=10,11,12` to redo some screens. Run the page with `BLAZE_CONFIG=/tmp/c.yaml` so the AI screens do not touch your real settings.
