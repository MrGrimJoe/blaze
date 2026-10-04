"""
Runs INSIDE Blender (headless):  blender -b [file.blend] --factory-startup -P blaze_blender.py -- <command> [options]

Commands
  info                         print JSON about the scene (objects, shape keys, actions, frame range, fps)
  sprites --out DIR --name N   render a character to transparent PNGs:  N.png, N_talk.png, N_blink.png
  still   --out FILE.png       render one frame from the scene's camera (for backdrops)
  render  --out DIR            render the scene's animation to PNG frames

Blaze reads the lines this script prints that start with BLAZE_ (BLAZE_JSON, BLAZE_OUT, BLAZE_ERROR).
Works with Blender 3.6+ (tested on 4.0). Uses Cycles on CPU so it runs on machines without a GPU / display.
"""

import argparse
import json
import math
import sys
import traceback
from pathlib import Path

import bpy
from mathutils import Vector

TALK_KEYS = ("talk", "mouth_open", "mouthopen", "open", "aa", "viseme_aa", "jawopen", "jaw_open")
BLINK_KEYS = ("blink", "eyes_closed", "eyesclosed", "eye_blink", "blink_l", "blink_r", "eyeblinkleft", "eyeblinkright")


def out(tag, payload):
    print("BLAZE_%s %s" % (tag, payload if isinstance(payload, str) else json.dumps(payload)), flush=True)


def fail(msg):
    out("ERROR", msg)
    sys.exit(2)


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="blaze_blender")
    ap.add_argument("command", choices=["info", "sprites", "still", "render"])
    ap.add_argument("--out")
    ap.add_argument("--name", default="character")
    ap.add_argument("--width", type=int)
    ap.add_argument("--height", type=int)
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--margin", type=float, default=0.04)
    ap.add_argument("--yaw", type=float, default=0.0, help="rotate the subject (degrees, around Z) before rendering")
    ap.add_argument("--keep-camera", action="store_true", help="use the scene's own camera instead of framing the subject")
    ap.add_argument("--start", type=int)
    ap.add_argument("--end", type=int)
    return ap.parse_args(argv)


# ----------------------------------------------------------------- helpers
def visible_meshes():
    return [o for o in bpy.context.scene.objects if o.type == "MESH" and not o.hide_render and o.visible_get()]


def world_bbox(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    lo, hi = Vector((1e9, 1e9, 1e9)), Vector((-1e9, -1e9, -1e9))
    for o in objs:
        eo = o.evaluated_get(dg)
        for c in eo.bound_box:
            p = eo.matrix_world @ Vector(c)
            lo = Vector((min(lo[i], p[i]) for i in range(3)))
            hi = Vector((max(hi[i], p[i]) for i in range(3)))
    return lo, hi


def setup_cycles(sc, samples):
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = max(1, samples)
    sc.cycles.preview_samples = 1
    try:
        sc.cycles.use_denoising = True
    except Exception:
        pass
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.image_settings.color_depth = "8"
    sc.render.resolution_percentage = 100


def render(**kw):
    """bpy.ops.render.render, retrying without the denoiser on builds that ship without OpenImageDenoise."""
    try:
        bpy.ops.render.render(**kw)
    except RuntimeError as e:
        if "Denois" in str(e):
            bpy.context.scene.cycles.use_denoising = False
            bpy.ops.render.render(**kw)
        else:
            raise


def ensure_lighting(sc):
    if not any(o.type == "LIGHT" for o in sc.objects):
        sun = bpy.data.objects.new("Blaze_Sun", bpy.data.lights.new("Blaze_Sun", "SUN"))
        sun.data.energy = 3.0
        sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(30))
        sc.collection.objects.link(sun)
        fill = bpy.data.objects.new("Blaze_Fill", bpy.data.lights.new("Blaze_Fill", "SUN"))
        fill.data.energy = 1.0
        fill.rotation_euler = (math.radians(70), 0, math.radians(-140))
        sc.collection.objects.link(fill)
    if sc.world is None:
        sc.world = bpy.data.worlds.new("Blaze_World")
    sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes.get("Background")
    if bg and not any(l.type == "LIGHT" for l in sc.objects if False):
        bg.inputs[0].default_value = (0.8, 0.8, 0.82, 1.0)
        bg.inputs[1].default_value = 0.6


def frame_subject(sc, objs, w, h, margin, yaw):
    """Orthographic front camera; the subject's feet sit just above the bottom edge (Blaze's sprite convention)."""
    if yaw:
        empty = bpy.data.objects.new("Blaze_Yaw", None)
        sc.collection.objects.link(empty)
        for o in objs:
            if o.parent is None:
                o.parent = empty
        empty.rotation_euler = (0, 0, math.radians(yaw))
        bpy.context.view_layer.update()
    lo, hi = world_bbox(objs)
    bw, bh = max(hi.x - lo.x, hi.y - lo.y), hi.z - lo.z
    if bh <= 0:
        fail("the subject has no height; nothing to frame")
    scale = max(bh / (1 - 2 * margin), bw * (h / w) / (1 - 2 * margin))
    cx, cy = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
    cz = lo.z - margin * scale + scale / 2
    cam_data = bpy.data.cameras.new("Blaze_Cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = scale
    cam_data.clip_start, cam_data.clip_end = 0.01, 1000
    cam = bpy.data.objects.new("Blaze_Cam", cam_data)
    cam.location = (cx, cy - (max(hi.y - lo.y, 1) + 20), cz)
    cam.rotation_euler = (math.radians(90), 0, 0)
    sc.collection.objects.link(cam)
    sc.camera = cam


def shape_key_blocks(objs, names):
    found = []
    for o in objs:
        sk = o.data.shape_keys
        if sk:
            for kb in sk.key_blocks:
                if kb.name.lower().replace(" ", "_") in names:
                    found.append(kb)
    return found


# ----------------------------------------------------------------- commands
def cmd_info(a):
    sc = bpy.context.scene
    meshes = [o for o in sc.objects if o.type == "MESH"]
    keys = sorted({kb.name for o in meshes if o.data.shape_keys for kb in o.data.shape_keys.key_blocks if kb.name != "Basis"})
    info = {
        "blender": bpy.app.version_string,
        "scene": sc.name,
        "fps": sc.render.fps / (sc.render.fps_base or 1.0),
        "frame_start": sc.frame_start, "frame_end": sc.frame_end,
        "resolution": [sc.render.resolution_x, sc.render.resolution_y],
        "objects": len(sc.objects), "meshes": len(meshes),
        "armatures": len([o for o in sc.objects if o.type == "ARMATURE"]),
        "has_camera": sc.camera is not None,
        "shape_keys": keys,
        "actions": sorted(x.name for x in bpy.data.actions),
        "has_talk": bool(shape_key_blocks(meshes, TALK_KEYS)),
        "has_blink": bool(shape_key_blocks(meshes, BLINK_KEYS)),
    }
    out("JSON", info)


def cmd_sprites(a):
    if not a.out:
        fail("--out is required")
    sc = bpy.context.scene
    objs = visible_meshes()
    if not objs:
        fail("no visible mesh objects to render")
    outdir = Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    w, h = a.width or 400, a.height or 720
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.film_transparent = True
    setup_cycles(sc, a.samples)
    ensure_lighting(sc)
    if not a.keep_camera or sc.camera is None:
        frame_subject(sc, objs, w, h, a.margin, a.yaw)

    def still(suffix):
        p = outdir / ("%s%s.png" % (a.name, suffix))
        sc.render.filepath = str(p)
        render(write_still=True)
        out("OUT", str(p))

    still("")
    for suffix, names in (("_talk", TALK_KEYS), ("_blink", BLINK_KEYS)):
        blocks = shape_key_blocks(objs, names)
        if not blocks:
            continue
        old = [kb.value for kb in blocks]
        for kb in blocks:
            kb.slider_max = max(kb.slider_max, 1.0)
            kb.value = 1.0
        bpy.context.view_layer.update()
        still(suffix)
        for kb, v in zip(blocks, old):
            kb.value = v


def cmd_still(a):
    if not a.out:
        fail("--out is required")
    sc = bpy.context.scene
    if sc.camera is None:
        fail("the .blend has no active camera; add one so Blaze knows what to render")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    sc.render.resolution_x, sc.render.resolution_y = a.width or 1920, a.height or 1080
    sc.render.film_transparent = False
    setup_cycles(sc, a.samples)
    sc.render.image_settings.color_mode = "RGB"
    if a.start is not None:
        sc.frame_set(a.start)
    sc.render.filepath = str(a.out)
    render(write_still=True)
    out("OUT", str(a.out))


def cmd_render(a):
    if not a.out:
        fail("--out is required")
    sc = bpy.context.scene
    if sc.camera is None:
        fail("the .blend has no active camera; add one (or use `blaze asset add` for a character)")
    outdir = Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    if a.width and a.height:
        sc.render.resolution_x, sc.render.resolution_y = a.width, a.height
    if a.start is not None: sc.frame_start = a.start
    if a.end is not None: sc.frame_end = a.end
    if sc.render.engine not in ("CYCLES", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH"):
        sc.render.engine = "CYCLES"
    if sc.render.engine == "CYCLES":
        sc.cycles.device = "CPU"
        sc.cycles.samples = a.samples
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.resolution_percentage = 100
    sc.render.filepath = str(outdir / "frame_")
    out("JSON", {"fps": sc.render.fps / (sc.render.fps_base or 1.0), "frames": sc.frame_end - sc.frame_start + 1})
    render(animation=True)


def main():
    a = parse()
    try:
        {"info": cmd_info, "sprites": cmd_sprites, "still": cmd_still, "render": cmd_render}[a.command](a)
    except SystemExit:
        raise
    except Exception as e:  # report cleanly so Blaze can show it
        traceback.print_exc()
        fail("%s: %s" % (type(e).__name__, e))


main()
