# CDRCA changes, as reviewable commits

Made against upstream `ISLAH-org/CDRCA` commit `6b8a742`. Apply to a checkout of that commit with
`git am cdrca-patches/*.patch`. Take, change or drop each one separately. Full detail: `docs/CDRCA-CHANGES.md`.

| # | Kind | Change |
|---|------|--------|
| 1 | bug fix | `def ACTION` parts only drive the prop they name; same-name lines combine |
| 2 | bug fix | emit the documented default scene options when a scene sets none (without them no action ever played) |
| 3 | bug fix | parser: a negative number in `def ACTION` parameters stays one parameter |
| 4 | bug fix | emit `JS { }` blocks (they were parsed, then dropped) |
| 5 | bug fix | define `mixClasses` in the renderer (`def PROP` called it, nothing defined it) |
| 6 | addition | `Back-end/Render/render.js`: headless, frame-exact renderer (playwright + Chromium) |
| 7 | addition | `render.js --from <sec>` skips the start of the animation |
| 8 | bug fix | tokenizer/parser keep the spaces in `def PROP` and `JS` bodies |
| 9 | bug fix | renderer `Scene` copied props exponentially in their number |
| 10 | addition | `render.js` waits for loads through `THREE.DefaultLoadingManager`; tests use `def PROP` props |
| 11 | bug fix | transpiler: a header block that only defines things is not a scene (no empty black scenes) |
