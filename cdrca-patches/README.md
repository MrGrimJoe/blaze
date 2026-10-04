# CDRCA changes, as reviewable commits

Made against upstream `ISLAH-org/CDRCA` commit `6b8a742` ("rough sketch for full plugin implementation").
Apply to a checkout of that commit with `git am cdrca-patches/*.patch`; take, change or drop each one separately.

| # | Kind | What |
|---|---|---|
| 1 | bug fix | `def ACTION`: each part only drives the prop it names, and several `def ACTION <same name>` lines combine (as `examples/demo_animation.cdrca` shows it is meant to work) |
| 2 | bug fix | emit the documented default scene options (1000/1000/500/0x000000) when a scene sets none; without them the renderer never leaves its first scene and no action plays. Adds `tests/transpiler.test.js` |
| 3 | addition | `ImageProp` and `TextProp`, in the same style and place as the existing example props. No new syntax |
| 4 | addition | `Back-end/Render/render.js`: headless, frame-exact rendering to images/mp4 (stand-alone; only needs playwright to run it) |
| 5 | docs | README sections for the above |
| 6 | addition | `render.js --from <sec>` |
| 7 | bug fix | parser: a negative number in `def ACTION` parameters stays one parameter |

Not changed and not added: the language's syntax, the existing props, the scene/action machinery, the plugin sketch.
Requests that need the owner's design decisions are in `../docs/CDRCA-PROPOSALS.md`.
