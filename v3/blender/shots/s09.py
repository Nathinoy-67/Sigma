"""S09 THE CROSSING (film frames 480-555, 75 local frames).

MATCH CUT on the bar 9 downbeat: the bright disc of the oculus becomes the riveted brass porthole of a 1970s
freighter, a steel-grey Atlantic swell rolling past at dusk.  Pull back 2 m (35 mm, f/2.8) revealing the hold: riveted
frames, chipped green paint over rust, a cargo net, slatted crates stencilled for export with green bottle necks in
straw.  The caged bulb swings on its flex, its wire shadows rocking across the crates; the camera rolls +-1.5 deg
with the ship.
"""
import math

import bpy
from mathutils import Vector

import scene as S
import camera as C
import hold as H

FRAMES = 75
PRESET = "default"


def build(res="look", samples=None, threshold=None, **kw):
    S.new_scene(res, PRESET, samples=samples, threshold=threshold, exposure=-0.4)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 0, FRAMES - 1
    coll = S.collection("S09")
    H.build_hold(coll, frames=FRAMES + 40)
    S.world((0.002, 0.0022, 0.003), 1.0)
    p0 = Vector((0.0, 1.22, H.PORT.z))
    p1 = Vector((0.22, 3.22, H.PORT.z - 0.05))
    cam = C.add_camera("CAM_S09", lens=35, location=p0, target=H.PORT, fstop=2.8, focus=H.PORT)
    C.move(cam, [(0, p0), (FRAMES - 1, p1)])
    C.aim_keys(cam, [(0, H.PORT), (FRAMES - 1, H.PORT + Vector((0.05, 0, -0.80)))])
    C.rack_focus(cam, [(0, H.PORT), (40, H.PORT + Vector((0, 0.5, -0.5))), (FRAMES - 1, Vector((0.1, 0.6, 0.8)))], breathing=0.01)
    return dict(cam=cam)
