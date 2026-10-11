# CDRCA: what it can do, and what we changed (living document)

Update this file with every CDRCA commit. Base: upstream `ISLAH-org/CDRCA` `6b8a742`. Our changes are only the
commits in `cdrca-patches/` (table in its README). Nothing is pushed upstream; CDRCA's owner accepts or rejects each.

## What CDRCA can do today (as used by Blaze)

- Script files `.cdrca`; a scene is a `!--- SCENE name :: note --- ... !---END---` block.
- `use Prop(args) as alias` creates a prop; `add new action name stayMs lerpMs` adds a beat;
  `def ACTION name alias method param` says what each prop does in that beat (ONE token as parameter).
- `def PROP Name { ... }` defines a prop as a JS class (props are libraries written in CDRCA, not built in).
- `@IMPORT "./file.cdrca"` pulls in another file (e.g. `cdrca-lib/atoms.cdrca`: Picture, Words).
- `JS { ... }` blocks run as an IIFE (set globals with `globalThis.x`).
- Renderer: three.js r128 in the browser. `Back-end/Render/render.js` (ours) renders frame-exact to PNG/JPEG/mp4 headlessly.
- Known quirks: see `docs/CDRCA-PROPOSALS.md` and `handoff/02-RULES.md` section D.

## Change log

- **11 (2026-10-06)** transpiler: a header block that only defines things (def PROP / def ACTION / JS, no `use`, no action,
  no scene option) is no longer a scene. Before: `atoms.cdrca` (2 header blocks) added 2 empty scenes of ~2.5 s each, so
  every rendered scene began with black. Files: `Back-end/Transpiler/FullTranspiler.js` (`transpileScenes`),
  test in `tests/transpiler.test.js`. Verified: transpiler tests 8/8, render tests 4/4, sample story rendered
  (title card and first scene show content). Not changed: a scene that sets an option but uses no prop is still a scene.
- **1-10** see `cdrca-patches/README.md`.

## Blaze's own CDRCA library: `cdrca-lib/atoms.cdrca`

Written in CDRCA with `def PROP`; not a change to the language. Its history (newest first):

- **Speech boxes stay on screen.** `Words` gained two trailing parameters, `limit` and `limitY`: the box never reaches past
  x = +-limit or above y = limitY; it slides back and its pointer keeps aiming at the anchor (0 disables each). Before, a
  long line from a speaker standing near an edge ran off the frame. The compiler passes half the visible width and height
  minus 0.15. Tests: `tests/test_blaze.py` (the compiled parameters, and a rendered-pixel check that fails without the fix).
- `Picture` and `Words` as first written: see [reference/atoms.md](reference/atoms.md).
