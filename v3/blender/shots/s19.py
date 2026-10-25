"""S19 THE SECOND, angle B (film frames 1050-1080, 30 local frames).

Top-down, 65 mm at f/5.6, from above the rim: the crown collapses inward over the sinking glass into a churning ring
of foam; deep down sits the black mouth of the sunken shot glass, with a muted glass 'tonk' as it touches bottom.
The liquid is the MPM sim continued (sim frames 46-75: 1/400 s then 1/150 s per frame).
"""
import bpy
from mathutils import Vector

import scene as S
import camera as C
import stage as F
from s18 import setup_glass_and_shot

FRAMES = 30
PRESET = "glass"


def sim_frame(f):
    return min(46 + f, 77)


def build(res="look", samples=None, threshold=None, **kw):
    S.new_scene(res, PRESET, samples=samples, threshold=threshold, exposure=-0.2)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 0, FRAMES - 1
    coll = S.collection("S19")
    L = F.stage(coll)
    L["pendant"].location = F.HB + Vector((0.12, 0.10, 0.85))
    drink = F.energy_drink()
    setup_glass_and_shot(coll, sim_frame, drink)
    top = F.HB + Vector((0, 0, 0.15))
    cam = C.add_camera("CAM_S19", lens=65, location=top + Vector((0.0, -0.035, 0.20)), target=F.HB + Vector((0, 0, 0.05)),
                       fstop=5.6, focus=F.HB + Vector((0, 0, 0.10)))
    C.breathe(cam, amplitude_deg=0.05, period_frames=40, seed=19)
    return dict(cam=cam)
