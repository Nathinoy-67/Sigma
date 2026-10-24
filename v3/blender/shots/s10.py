"""S10 CONSIGNEE (film frames 555-585, 30 local frames).

85 mm close on the side of one crate.  The swinging bulb rakes across the stencil 'CONSIGNEE: SIDNEY FRANK
IMPORTING CO. · NEW YORK'; straw and a green bottle shoulder show between the slats.  The light swings away into
darkness on the cut.
"""
import math

import bpy
from mathutils import Vector

import scene as S
import camera as C
import hold as H

FRAMES = 30
PRESET = "default"


def build(res="look", samples=None, threshold=None, **kw):
    S.new_scene(res, PRESET, samples=samples, threshold=threshold, exposure=0.3)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 0, FRAMES - 1
    coll = S.collection("S10")
    out = H.build_hold(coll, frames=FRAMES + 10)
    # re-time the bulb: it swings across the crate and away into darkness by the last frame
    piv = out["bulb"]["pivot"]
    piv.animation_data_clear()
    for f in range(FRAMES):
        u = f / (FRAMES - 1)
        a = math.radians(-6.0 + 22.0 * u)
        piv.rotation_euler = (a, math.radians(-14.0 + 10.0 * u), 0)
        piv.keyframe_insert("rotation_euler", frame=f)
    S.world((0.002, 0.0022, 0.003), 1.0)
    crate = bpy.data.objects["CrateC"]
    bpy.context.view_layer.update()
    c = crate.matrix_world.translation + Vector((0, 0.21, 0.20))
    cam_p = c + Vector((-0.22, 1.75, 0.12))
    cam = C.add_camera("CAM_S10", lens=85, location=cam_p, target=c, fstop=2.8, focus=c)
    C.slide(cam, 0, FRAMES - 1, (0.03, 0.0, 0.0))
    C.breathe(cam, amplitude_deg=0.04, period_frames=40, seed=10)
    return dict(cam=cam)
