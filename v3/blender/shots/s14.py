"""S14 THE SET-UP (film frames 735-795, 60 local frames).

The lens 3 cm above the lacquered fir bar, 50 mm at f/2, a 35 cm motion-control slide towards the window: past a cork
coaster and a folded bar towel, arriving at a straight-sided highball of pale-gold energy drink, beaded with
condensation and fizzing, and beside it a frosted shot glass full of near-black Jägermeister.  Soft behind: the moon
window, the backwards pink OPEN, warm enamel pendants, the back bar.
"""
import math

import bpy
from mathutils import Vector

import scene as S
import camera as C
import materials as M
import props as P
import lodge as E

FRAMES = 60
PRESET = "glass"
HB = Vector((-0.04, 1.86, E.BAR_Z))           # highball
SHOT = Vector((0.065, 1.80, E.BAR_Z))         # shot glass


def build(res="look", samples=None, threshold=None, **kw):
    S.new_scene(res, PRESET, samples=samples, threshold=threshold, exposure=-0.5)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 0, FRAMES - 1
    coll = S.collection("S14")
    moon_x, moon_z = -1.2, 7.2
    out = E.build_room(coll, moon_z=moon_z, moon_x=moon_x, neon_c=Vector((0.36, E.WIN_Y - 0.06, 1.36)))
    E.key_neon(out["neon"], [(0, 1.0)])
    P.highball("Highball", location=HB, fill=0.62, seed=5, coll=coll, cond_facing_deg=-100.0)
    P.shot_glass("Shot", location=SHOT, frosted=True, fill=0.84, seed=12, coll=coll, frost=0.7, frost_density=0.65,
                 liquid_material=M.jagermeister("JagerS14", density=520.0))
    P.coaster("Coaster", location=(0.07, 1.42, E.BAR_Z), radius=0.05, seed=3, coll=coll)
    E.bar_towel("BarTowel", (-0.16, 1.28, E.BAR_Z), coll, rot_z=12.0)
    # a warm practical close behind the glasses so the drink glows from behind
    S.area_light("BackGlow", size=(0.3, 0.1), power=6.0, kelvin=2700, location=HB + Vector((0.05, 0.45, 0.12)),
                 target=HB + Vector((0, 0, 0.06)), coll=coll)
    S.area_light("CamFill", size=(0.4, 0.2), power=1.5, kelvin=3200, location=HB + Vector((0.25, -0.6, 0.15)),
                 target=HB + Vector((0, 0, 0.06)), coll=coll)
    z = E.BAR_Z + 0.03
    p0, p1 = Vector((0.01, 1.03, z)), Vector((0.01, 1.38, z))
    cam = C.add_camera("CAM_S14", lens=50, location=p0, target=p0 + Vector((0, 1.0, 0.11)), fstop=2.0, focus=HB)
    C.move(cam, [(0, p0), (FRAMES - 1, p1)])
    C.rack_focus(cam, [(0, Vector((0.07, 1.42, E.BAR_Z + 0.01))), (22, Vector((-0.16, 1.32, E.BAR_Z + 0.02))),
                       (44, HB + Vector((0, -0.03, 0.06))), (FRAMES - 1, HB + Vector((0, -0.03, 0.06)))], breathing=0.01)
    C.breathe(cam, amplitude_deg=0.02, period_frames=70, seed=14)
    return dict(cam=cam)
