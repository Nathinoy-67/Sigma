"""S15 WHOEVER (film frames 795-870, 75 local frames).

50 mm at f/1.8, locked off at counter height.  An empty chrome bar stool with a cracked red vinyl seat is still turning
slowly; it decelerates and comes to rest while neon pink and pendant highlights slide around its chrome column.
Whoever sat here has just stood up.
"""
import math

import bpy
from mathutils import Vector

import scene as S
import camera as C
import lodge as E

FRAMES = 75
PRESET = "default"


def build(res="look", samples=None, threshold=None, **kw):
    S.new_scene(res, PRESET, samples=samples, threshold=threshold, exposure=-0.4)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 0, FRAMES - 1
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.5
    coll = S.collection("S15")
    out = E.build_room(coll, stools_y=(-0.6, 0.15, 0.9, 1.65), moon_z=7.2, moon_x=-1.2,
                       neon_c=Vector((0.36, E.WIN_Y - 0.06, 1.36)))
    E.key_neon(out["neon"], [(0, 1.0)])
    root, seat = out["stools"][2]
    # the seat spins down: angular speed decays to zero (ease-out), ~200 deg over the shot
    total = math.radians(200.0)
    for f in range(FRAMES):
        u = f / (FRAMES - 1)
        a = total * (1 - (1 - u) ** 2.6)
        seat.rotation_euler = (0, 0, a)
        seat.keyframe_insert("rotation_euler", frame=f)
    st = root.location.copy()
    tgt = st + Vector((0, 0, 0.62))
    cam_p = st + Vector((1.05, -0.80, 0.84))
    # pink neon and blue window light skimming the chrome from behind
    S.area_light("PinkRim", size=(0.4, 0.4), power=10.0, color=(1.0, 0.2, 0.5), location=st + Vector((-0.3, 1.2, 0.9)),
                 target=st + Vector((0, 0, 0.5)), coll=coll)
    cam = C.add_camera("CAM_S15", lens=50, location=cam_p, target=tgt + Vector((0, 0.18, 0.04)), fstop=1.8,
                       focus=st + Vector((0, 0, 0.7)))
    C.breathe(cam, amplitude_deg=0.02, period_frames=90, seed=15)
    return dict(cam=cam)
