"""S18 THE SECOND, angle A (film frames 1005-1050, 45 local frames, SIM 2), in total silence.

A side profile at the liquid line, 100 mm at f/5.6, through the highball wall, in extreme slow motion (one frame =
1/400 s).  The heavy base of the shot glass enters the top of frame already falling; on local f15 (film f1020, bar 18
downbeat) it breaks the surface: the surface craters round it, a column of air follows it down, and the displaced drink
shoots up the 5 mm gap as a crown that tears into spray hanging in the air -- rimmed silver by the window behind and
pink by the neon.  Condensation beads soft at the frame edge.

The liquid is the MPM sim (sims/mpm_plunge.py, SIM_DIR) surfaced in Geometry Nodes; the shot glass follows the sim's
prescribed motion.
"""
import json
import math
import os

import bpy
from mathutils import Vector

import scene as S
import camera as C
import materials as M
import props as P
import fluid as FL
import stage as F

FRAMES = 45
PRESET = "glass"
SIM_DIR = os.environ.get("OYOS_SIM2", os.path.join(S.FRAMES, "sim2"))
OFFSET = 3                     # local frame f shows sim frame f - OFFSET (impact: sim 12 -> local 15)


def sim_frame(f):
    return max(0, f - OFFSET)


def setup_glass_and_shot(coll, frame_fn, drink, shot_seed=12):
    hb = F.glass(coll, drink=drink, bubbles=False, cond_facing_deg=-90.0)
    for part in ("liquid", "bubbles", "foam"):
        ob = getattr(hb, part, None)
        if ob is not None:
            ob.hide_render = True
    meta = json.load(open(os.path.join(SIM_DIR, "meta.json")))
    shot = P.shot_glass("Shot", location=F.HB, frosted=True, fill=0.84, seed=shot_seed, coll=coll, frost=0.7,
                        frost_density=0.65, liquid_material=M.jagermeister("JagerStage", density=520.0))
    sc = bpy.context.scene
    for f in range(sc.frame_start, sc.frame_end + 1):
        k = min(frame_fn(f), len(meta["shot"]) - 1)
        t, z, vz = meta["shot"][k]
        shot.root.location = F.HB + Vector((0, 0, z))
        shot.root.keyframe_insert("location", frame=f)
    C.set_interpolation(shot.root, "location", "LINEAR")
    liquid = FL.particle_liquid("Plunge", SIM_DIR, drink, coll=coll, frame_map=frame_fn, location=F.HB)
    return hb, shot, liquid


def build(res="look", samples=None, threshold=None, **kw):
    S.new_scene(res, PRESET, samples=samples, threshold=threshold, exposure=-0.3)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 0, FRAMES - 1
    sc.render.use_motion_blur = False
    coll = S.collection("S18")
    F.stage(coll)
    drink = F.energy_drink()
    setup_glass_and_shot(coll, sim_frame, drink)
    tgt = F.HB + Vector((0, 0, 0.112))
    cam = C.add_camera("CAM_S18", lens=100, location=tgt + Vector((0.0, -0.62, 0.0)), target=tgt, fstop=5.6,
                       focus=F.HB + Vector((0, -0.02, 0.11)))
    return dict(cam=cam)
