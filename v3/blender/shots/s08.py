"""S08 OCULUS (film frames 450-480, 30 local frames).

50 mm from the cask aisle, looking up at the round oculus: a deep brick reveal, old glass in an iron ring, the sky
clipped to white-blue, a steady cool winter morning.  Rendered as ONE wider still; the slow push is a 2D move in post
that ends with the bright disc exactly where the porthole of S09 will be (post/moves.json).
"""
import bpy
from mathutils import Vector

import scene as S
import camera as C
import cellar as B

FRAMES = 30
PRESET = "default"


def build(res="look", samples=None, threshold=None, **kw):
    S.new_scene(res, PRESET, samples=samples, threshold=threshold, exposure=-0.8)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 0, 0
    coll = S.collection("S08")
    B.vault(coll)
    B.casks(coll, s07_chalk=False)
    lights = B.oculus_sun(target=Vector((0.4, 6.0, 0.4)), strength=7.0, kelvin=9500, coll=coll, shaft=False)
    lights["bounce"].data.energy = 60.0
    S.world((0.0015, 0.0017, 0.002), 1.0)
    # the sunlit floor further down the vault bounces a little light back up onto the entrance wall
    S.area_light("FloorBounce", size=(2.0, 1.0), power=7.0, kelvin=5500, location=(0.0, 2.2, 0.15),
                 target=(0.0, 0.0, 2.2), spread_deg=120.0)
    cam_p = Vector((0.35, 3.2, 0.55))
    cam = C.add_camera("CAM_S08", lens=40, location=cam_p, target=B.OCULUS + Vector((0.0, 0, -0.25)), fstop=2.8,
                       focus=B.OCULUS)
    return dict(cam=cam)
