# The project folder

`blaze make story.txt` writes `story.mp4`, `story.srt` and a folder `story.blaze/`. The page writes the same things into
`blaze-videos/<id>/` as `video.mp4`, `subtitles.srt` and `project/`. The folder is generated from your screenplay;
[Tutorial 6](../tutorials/06-editing-the-cdrca-scripts.md) shows how to edit it and render again.

```
story.blaze/
  screenplay.txt
  project.json
  scenes/
    atoms.cdrca          the Picture and Words props, copied from cdrca-lib/
    s00_title.cdrca      the title card scene (only when the screenplay has a TITLE)
    s01.cdrca ...        one CDRCA script per scene
  assets/
    <name>.png, <name>_talk.png, <name>_blink.png     one set per character
    bg_<place>_<mood>.png, bg_title.png, bg_custom_*.png     the backdrops
  audio/
    s01_00.wav ...       one voice file per spoken or narrated line: scene 01, beat 00
    s01_track.wav ...    the whole scene's sound, timed to its picture
    title_track.wav
  shots/
    s01.mp4 ...          each scene rendered, then joined into the final video
    list.txt             the order in which they are joined
  frames/                the rendered pictures, removed after encoding unless you pass --keep-frames
```

## project.json

```json
{
  "version": 1,
  "title": "The Warehouse",
  "fps": 20,
  "width": 960,
  "height": 540,
  "shots": [
    {
      "name": "s01",
      "cdrca": "scenes/s01.cdrca",
      "duration": 20.905,
      "mood": "gen:street:night_rain",
      "title": false,
      "skip": 1.5,
      "notes": [],
      "audio": [[0, "audio/s01_00.wav"]],
      "subs": [[0.0, 3.981, "John", "Did you hear that? ..."]]
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `fps`, `width`, `height` | the size and frame rate `build` renders at. Edit them to change the output. |
| `shots` | the scenes in order |
| `name`, `cdrca` | the scene's name and its script, relative to the folder |
| `duration` | the scene's length in seconds |
| `mood` | the backdrop spec the scene was made with (informational) |
| `title` | true for the title card |
| `skip` | seconds at the start of the script that are not part of the video (CDRCA's built-in intro, 1.5 s) |
| `audio` | `[beat index, wav file]` for each spoken line (empty when voices are off) |
| `subs` | `[start, end, name, text]` in seconds within the scene; `build` turns them into the `.srt` |
| `notes` | notes the compiler attached to the scene (normally empty) |

Paths are relative to the project folder, and the folder can be moved or copied as a whole.
