# The atoms: Picture and Words

`cdrca-lib/atoms.cdrca` (copied into every project as `scenes/atoms.cdrca`) holds the only two props Blaze uses. They are
written in CDRCA itself with `def PROP`; nothing about them is built into the language. Every value is an explicit number or
a literal: positions and sizes in scene units, colours as `0xRRGGBB`, times in seconds, speeds in units per second.

## Picture

```
use Picture(src, x, y, w, h, z, speed, altSrc, flapHz) as name
```

| Parameter | Meaning |
|---|---|
| `src`, `altSrc` | image paths, relative to the script; `altSrc` may be `""` when there is no second picture |
| `x`, `y` | the centre of the picture |
| `w`, `h` | its width and height |
| `z` | depth; more negative is further away (backdrops use -1, characters 0) |
| `speed` | units per second used by `moveTo` |
| `flapHz` | how many times per second `flap` swaps `src` and `altSrc` |

Actions (each takes exactly one parameter, written after the prop name in `def ACTION beat name action parameter`):

| Action | Parameter | Effect |
|---|---|---|
| `modifyMesh` | `""` | stand at (x, y) showing `src` |
| `flap` | `""` | stand, swapping `src` and `altSrc` |
| `moveTo` | an x | walk in a straight line to that x, at `speed` |
| `hop` | a height | jump once, that many units high |
| `hide` | `""` | not drawn during this beat |

## Words

```
use Words(x, y, ax, ay, size, wrapW, fill, fillAlpha, ink, border, borderW, pad, tail, z, limit, limitY) as name
```

| Parameter | Meaning |
|---|---|
| `x`, `y` | where the anchor point goes |
| `ax`, `ay` | the anchor inside the box, 0 to 1 from its left and its bottom |
| `size` | the height of one line of text |
| `wrapW` | the widest a line may be |
| `fill`, `fillAlpha` | the box colour and its opacity, 0 to 1 |
| `ink`, `border` | the text colour and the outline colour |
| `borderW` | the outline width |
| `pad` | the space between the text and the box edge |
| `tail` | the length of a pointer drawn under the box, ending at the anchor (0 for none) |
| `z` | depth |
| `limit` | the box never reaches past x = -limit or x = +limit: it slides back on screen and the pointer keeps pointing at the anchor (0 for no limit) |
| `limitY` | the box never reaches above y = limitY; it is pushed down instead (0 for no limit) |

Actions:

| Action | Parameter | Effect |
|---|---|---|
| `rate` | characters per second | how fast later `say` actions reveal their text in this prop (0 shows it all at once) |
| `say` | `"text"` | show the text, revealing it at the current rate from the moment the beat starts |
| `hide` / `modifyMesh` | `""` | not drawn during this beat |

## Writing scenes by hand

A scene is `@IMPORT "./atoms.cdrca"`, a `!--- SCENE name ---` block that creates props with `use`, one `add new action name
stayMilliseconds lerpMilliseconds` line per beat, and one `def ACTION` line for every prop in every beat (a prop not listed
in a beat is not drawn in it). A lerp of `1` is a hard cut; `0` is not allowed by the renderer.

Because `atoms.cdrca` is plain CDRCA you can add props of your own to it, with `def PROP`, in the same style.
