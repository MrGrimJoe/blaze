"""Run inside Blender to build the test assets:  blender -b --factory-startup -P make_fixtures.py -- OUTDIR

  robot.blend   a small robot: head/body/limbs, 'talk' + 'blink' shape keys, Idle + Walk actions
  shot.blend    a camera shot: a cube spinning in front of a coloured floor, 24 frames at 24 fps
"""
import math
import sys
from pathlib import Path

import bpy

OUT = Path(sys.argv[sys.argv.index("--") + 1])
OUT.mkdir(parents=True, exist_ok=True)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def material(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1)
    return m


def add(kind, name, loc, mat, **kw):
    getattr(bpy.ops.mesh, "primitive_%s_add" % kind)(location=loc, **kw)
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(mat)
    return o


# ---------------------------------------------------------------- robot
sc = reset()
blue, grey, yellow = material("blue", (0.1, 0.35, 0.9)), material("grey", (0.55, 0.57, 0.62)), material("yellow", (1.0, 0.8, 0.1))
body = add("cube", "Body", (0, 0, 1.25), blue, size=1.0); body.scale = (0.8, 0.5, 0.9)
head = add("uv_sphere", "Head", (0, 0, 2.55), grey, radius=0.55)
eyes = [add("uv_sphere", "Eye%d" % i, (x, -0.46, 2.65), yellow, radius=0.11) for i, x in enumerate((-0.2, 0.2))]
for l, x in (("L", -0.55), ("R", 0.55)):
    add("cylinder", "Arm" + l, (x * 1.5, 0, 1.3), grey, radius=0.14, depth=1.2)
    add("cylinder", "Leg" + l, (x * 0.6, 0, 0.4), grey, radius=0.17, depth=0.8)
mouth = add("cube", "Mouth", (0, -0.5, 2.38), yellow, size=1.0); mouth.scale = (0.22, 0.05, 0.03)
# shape keys on the head: 'talk' opens the mouth, 'blink' squashes the eyes
for o in eyes + [mouth]:
    o.shape_key_add(name="Basis")
eyes[0].shape_key_add(name="blink").data  # keys must live on the objects that deform
for e in eyes:
    if not e.data.shape_keys or "blink" not in e.data.shape_keys.key_blocks:
        e.shape_key_add(name="Basis") if not e.data.shape_keys else None
        e.shape_key_add(name="blink")
    kb = e.data.shape_keys.key_blocks["blink"]
    for v, base in zip(kb.data, e.data.vertices):
        v.co.z = base.co.z * 0.08 + (base.co.z * 0 )
tk = mouth.shape_key_add(name="talk")
for v, base in zip(tk.data, mouth.data.vertices):
    v.co.z = base.co.z * 6.0
    v.co.x = base.co.x * 1.0
# parent everything under one root so animation moves the whole robot
root = bpy.data.objects.new("RobotRoot", None); sc.collection.objects.link(root)
for o in list(sc.objects):
    if o is not root and o.parent is None:
        o.parent = root


def action(name, frames, fn):
    root.animation_data_create()
    act = bpy.data.actions.new(name)
    root.animation_data.action = act
    for f, (z, rz) in frames:
        root.location.z = z; root.rotation_euler.z = rz
        root.keyframe_insert("location", index=2, frame=f)
        root.keyframe_insert("rotation_euler", index=2, frame=f)
    for fc in act.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
    return act


action("Idle", [(1, (0, 0)), (24, (0.06, 0)), (48, (0, 0))], None)
action("Walk", [(1, (0, -0.1)), (8, (0.18, 0)), (16, (0, 0.1)), (24, (0.18, 0)), (32, (0, -0.1))], None)
root.animation_data.action = None
root.location.z = 0; root.rotation_euler.z = 0
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "robot.blend"))

# ---------------------------------------------------------------- shot
sc = reset()
sc.render.fps = 24
sc.frame_start, sc.frame_end = 1, 24
sc.render.resolution_x, sc.render.resolution_y = 480, 270
floor = add("plane", "Floor", (0, 0, 0), material("floor", (0.2, 0.5, 0.35)), size=12)
cube = add("cube", "Cube", (0, 0, 1.0), material("cube", (0.95, 0.35, 0.2)), size=1.6)
cube.rotation_euler = (0, 0, 0); cube.keyframe_insert("rotation_euler", frame=1)
cube.rotation_euler = (0, 0, math.radians(180)); cube.keyframe_insert("rotation_euler", frame=24)
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam)
cam.location = (0, -7, 2.4); cam.rotation_euler = (math.radians(78), 0, 0); sc.camera = cam
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN")); sun.data.energy = 4; sun.rotation_euler = (0.9, 0.2, 0.6); sc.collection.objects.link(sun)
sc.world = bpy.data.worlds.new("W"); sc.world.use_nodes = True
sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.5, 0.7, 1.0, 1)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "shot.blend"))
print("FIXTURES OK")
