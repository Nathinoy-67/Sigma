"""S23 END CARD background (film frames 1350-1440): the near-black oak-grain slate, softly lit from above by a warm
practical, with grain.  One still; the type is composited in post."""
import math

import bpy
from mathutils import Vector

import scene as S
import camera as C
import materials as M
import props as P

FRAMES = 90
PRESET = "default"


def build(res="look", samples=None, threshold=None, **kw):
    S.new_scene(res, PRESET, samples=samples, threshold=threshold, exposure=-1.2)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 0, 0
    coll = S.collection("S23")
    slate = P.slab("Slate", size=(1.2, 0.6, 0.04), location=(0, 0, 0), bevel=0.002,
                   material=M.wood("oak_cask", name="SlateOak", seed=23, plank_width=0.11, grain_axis="X", value=0.35,
                                   scratches=0.4, dust=0.3), coll=coll)
    S.area_light("Top", size=(0.9, 0.25), power=6.0, kelvin=3000, location=(0.0, 0.32, 0.55), target=(0, -0.02, 0), coll=coll)
    S.world((0.0, 0.0, 0.0), 0.0)
    cam = C.add_camera("CAM_S23", lens=50, location=(0, 0, 0.62), rotation_deg=(0, 0, 0), fstop=8.0, focus=0.62)
    return dict(cam=cam)
