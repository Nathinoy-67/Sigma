"""S07 1935 (film frames 390-450, 60 local frames).

100 mm on the head of the last cask in the right row as the year's light keeps sliding over it.  A spider thread
strung across the foreground catches the sun; rack focus (with lens breathing) to the chalk: '1934' struck through,
and the fresh '1935' beside it -- revealed between two time-lapse frames on f30 (film f420, bar 8 downbeat, timpani).
Fresh chalk dust lies on the chime ledge.  After the reveal the light settles to a steady, cool winter morning.
"""
import math
import random

import bpy
from mathutils import Vector

import scene as S
import camera as C
import materials as M
import props as P
import cellar as B
from s06 import SEASONS

FRAMES = 60
PRESET = "default"


def build(res="look", samples=None, threshold=None, **kw):
    S.new_scene(res, PRESET, samples=samples, threshold=threshold, exposure=-0.5)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 0, FRAMES - 1
    coll = S.collection("S07")
    B.vault(coll)
    casks = B.casks(coll)
    root = casks[(1, 5)]
    bpy.context.view_layer.update()
    c = root.matrix_world.translation.copy()
    hx = c.x - B.CASK_L / 2 + 0.032                  # head plane (faces -x)
    head = Vector((hx, c.y, c.z))
    # chalk dust on the lower chime ledge (fresh: the mark was just made)
    rng = random.Random(35)
    dm, dt = M.new_material("ChalkDust")
    dt.output(dt.principled(base=(0.8, 0.79, 0.75), rough=0.95))
    for i in range(160):
        a = math.radians(rng.uniform(-150, -30))
        r = B.R_HEAD - B.STAVE_T * rng.uniform(0.2, 0.9)
        p = Vector((hx - rng.uniform(0.0, 0.03), c.y + r * math.cos(a), c.z + r * math.sin(a) + 0.002))
        bpy.ops.mesh.primitive_ico_sphere_add(radius=rng.uniform(0.0002, 0.0009), subdivisions=1, location=p)
        d = bpy.context.active_object
        d.name = "ChalkDust"
        d.scale = (1, 1, 0.5)
        d.data.materials.append(dm)
        S.link(d, coll)
    # spider thread across the foreground, from the head hoop to the cradle rail
    p0 = head + Vector((-0.02, 0.33, 0.20))
    p1 = head + Vector((-0.30, 0.05, -0.32))
    mid = (p0 + p1) / 2 + Vector((0, 0, -0.012))
    cu = bpy.data.curves.new("SpiderThread", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.00006
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(1)
    for bp, q in zip(sp.bezier_points, (p0, p1)):
        bp.co = q
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    sp.bezier_points[0].handle_right = p0 + (mid - p0) * 0.66 + Vector((0, 0, -0.01))
    sp.bezier_points[1].handle_left = p1 + (mid - p1) * 0.66 + Vector((0, 0, -0.01))
    th = bpy.data.objects.new("SpiderThread", cu)
    S.link(th, coll)
    tm, tt = M.new_material("Silk")
    tt.output(tt.add_shader(tt.principled(base=(0.9, 0.9, 0.9), rough=0.08, spec=1.0, transmission=0.6),
                            tt.node("ShaderNodeEmission", {"Color": (1, 0.95, 0.85), "Strength": 0.0})))
    th.data.materials.append(tm)
    # light: two time-lapse sweeps across the head, then a steady cool winter morning from f30
    lights = B.oculus_sun(target=head, strength=9.0, coll=coll, shaft=False)
    sun = lights["sun"]
    lights["bounce"].data.energy = 60.0
    rng = random.Random(7)
    for f in range(FRAMES):
        if f < 30:
            day, u = divmod(f, 15)
            u = (u + 0.5) / 15
            K, k = SEASONS[4 + day] if 4 + day < len(SEASONS) else SEASONS[-1]
            tgt = head + Vector((0, 0.55 - 1.1 * u, 0.1 * math.sin(math.pi * u)))
            e = 9.0 * k * math.sin(math.pi * u) ** 0.35 * (1 + rng.uniform(-0.05, 0.05))
        else:
            K, tgt, e = 9500, head + Vector((0, -0.17, 0.02)), 7.0
        d = (tgt - B.OCULUS).normalized()
        sun.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        sun.data.energy = e
        sun.data.color = S.kelvin(K)
        sun.keyframe_insert("rotation_euler", frame=f)
        sun.data.keyframe_insert("energy", frame=f)
        sun.data.keyframe_insert("color", frame=f)
    for idb in (sun, sun.data):
        for fc in C.fcurves(idb):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    # the winter morning also fills the head softly (else the fresh '1935' sits in the dark)
    fill = S.area_light("WinterFill", size=(0.6, 0.6), power=10.0, kelvin=8500, location=head + Vector((-0.85, -0.6, 0.4)),
                        target=head + Vector((0, -0.2, 0.0)), coll=coll)
    for f, e in ((0, 0.0), (29, 0.0), (30, 10.0)):
        fill.data.energy = e
        fill.data.keyframe_insert("energy", frame=f)
    for fc in C.fcurves(fill.data):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"
    S.world((0.0015, 0.0017, 0.002), 1.0)
    # camera: 100 mm, ~1 m off the head, slightly from the aisle side; rack thread -> chalk around the reveal
    chalk_pt = head + Vector((0, -0.10, 0.02))
    cam_p = head + Vector((-1.45, 0.30, 0.05))
    cam = C.add_camera("CAM_S07", lens=85, location=cam_p, target=head + Vector((0, -0.02, 0.0)), fstop=2.8)
    thread_pt = p0 + (p1 - p0) * 0.35
    C.rack_focus(cam, [(0, thread_pt), (18, thread_pt), (34, chalk_pt), (FRAMES - 1, chalk_pt)], breathing=0.02)
    C.breathe(cam, amplitude_deg=0.02, period_frames=70, seed=7)
    return dict(cam=cam)
