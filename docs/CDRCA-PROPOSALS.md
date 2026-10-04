# Proposals for CDRCA (for its owner to accept, change or reject)

Blaze uses CDRCA exactly as it is, plus the small reviewed changes in `cdrca-patches/`. These are things it would
like CDRCA to have, written as requests. **No code for any of them has been written or added anywhere**; each should be
designed the CDRCA way by whoever owns the language, if at all.

## Things that look like bugs (not fixed in the patches)

1. **`BGcolor = <color>` is dropped.** The parser accepts it (statement type `BGCOLOR`), but the full transpiler never maps
   it to a scene's `backgroundColor`, so a scene's background cannot be set from a script. (Repro: transpile a scene with
   `BGcolor = 0xff0000`; no `backgroundColor` in the output.)
2. **A single-letter alias fails to parse**: `use ...BouncingSphereProp() as a` -> `Expected alias name after 'as'`
   (`as ball` works).
3. **`lerpTime` of 0 on an action** divides by zero in the renderer's lerp progress (use 1 to get a hard cut).
4. `Front-end/index.html` loads `./parser.js`, which is not in the repository.

## Features Blaze would use

Ordered by how much they would help, most first. For each: what it is for, not how to build it.

1. **Camera control from a script** (position / zoom over an action). Today the camera is created inside the renderer and
   fixed at z=5. Blaze would use it for push-ins, pans and shake.
2. **Choosing the length of the default first and last scene.** Every script gets 1.5 s of intro (500 ms fade + 1000 ms
   stay) and 1 s of outro that cannot be set from the language. Blaze skips them when rendering.
3. **Per-action control of the scene fade** (or "cut" as a first-class transition). The renderer fades every mesh in over
   `lerpTime` at the start of every action; Blaze uses `lerpTime 1` to get cuts.
4. **Props that stay visible when an action does not name them**, as an opt-in. Today a prop an action does not mention is
   hidden (ImageProp/TextProp) or drawn at its defaults, so scripts must list every prop in every action.
5. **Text with per-word styling** (a highlighted current word), for language-learning subtitles.
6. **Sprite sheets / more than two frames in ImageProp** (blink, visemes for lip-sync, walk cycles).
7. **Weather / particle prop** (rain, snow) and **post-effects** (tint, vignette, flash).
8. **A glTF/GLB model prop with animation clips**, for 3D characters made in Blender. (The renderer is already three.js.)
9. **A standard library of scene-building helpers written in CDRCA itself**, once the language has imports/packages, so
   things like "a conversation between two characters" can ship as CDRCA packages instead of living in another tool.
10. **A render command in the CDRCA CLI** (the `Back-end/Render/render.js` in the patches is a stand-alone script that
    could become `cdrca render`).
