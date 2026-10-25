"""S22 CLOSING (film frames 1320-1350, 30 local frames).

35 mm, locked off from inside: the window, the backwards neon OPEN, and the moon now high over the lake.  The sign
stutters at 55.2 s and 55.4 s and dies with a click on f1335 (local f15); the room's pink cast drains to moon blue.
Rendered as TWO stills (--variant on / off); post blends them frame by frame with the stutter keys in post/moves.json.
"""
import bpy
from mathutils import Vector

import scene as S
import camera as C
import lodge as E

FRAMES = 30
PRESET = "default"
NEON_KEYS = [(0, 1.0), (5, 0.15), (6, 1.0), (10, 0.0), (11, 0.8), (15, 0.0)]


def build(res="look", samples=None, threshold=None, variant="on", **kw):
    S.new_scene(res, PRESET, samples=samples, threshold=threshold, exposure=-0.5)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 0, 0
    coll = S.collection("S22")
    out = E.build_room(coll, moon_z=8.0, moon_x=0.9, neon_c=Vector((0.40, E.WIN_Y - 0.06, 1.40)))
    E.key_neon(out["neon"], [(0, 1.0 if (variant or "on") == "on" else 0.0)])
    cam_p = Vector((-0.55, -0.35, 1.42))
    cam = C.add_camera("CAM_S22", lens=35, location=cam_p, target=Vector((0.15, E.WIN_Y, 1.62)), fstop=4.0,
                       focus=Vector((0.2, E.WIN_Y, 1.5)))
    return dict(cam=cam)
