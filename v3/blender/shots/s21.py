"""S21 HERO STILL LIFE (film frames 1140-1320, 180 local frames).

On the bar by the window: the finished Jägerbomb (the shot glass resting at the bottom, fizz still rising, a ring of
foam) and, beside it, the frost-dusted square-shouldered green bottle, its label mostly under frost.  Behind: the moon
over the lake and the backwards pink neon in oval bokeh.  85 mm at f/4 holds both.

Rendering plan (the camera is locked; the slow 6 % push is a 2D move in post):
    --variant still   one high-resolution frame (everything static)
    --variant fizz    the highball region only, every frame (Cycles border render, transparent elsewhere)
    --variant bead    the bottle-shoulder region only, f56-f96 (a melt bead breaks loose on the 50.0 s hero hit, f60,
                      and runs, cutting a clear track through the frost to the deep green glass)
"""
import math

import bpy
from mathutils import Vector

import scene as S
import camera as C
import materials as M
import props as P
import lodge as E

FRAMES = 180
PRESET = "glass"
HB = Vector((-0.07, 1.95, E.BAR_Z))
BOT = Vector((0.085, 2.0, E.BAR_Z))
BEAD_F0, BEAD_F1 = 60, 86
TRACK = dict(x_min=0.012, y=0.007, width=0.0016, z_top=0.1845)
REGIONS = {"fizz": (0.30, 0.56, 0.06, 0.86), "bead": (0.58, 0.80, 0.50, 0.95)}   # border (x0, x1, y0, y1)


def bead_path(u):
    """Bottle-local point on the +X face for run progress u (0 at the neck, 1 at the end of the run)."""
    pts = [Vector((0.0172, TRACK["y"], 0.1845)), Vector((0.0300, TRACK["y"] + 0.0004, 0.1745)),
           Vector((0.0366, TRACK["y"] + 0.0006, 0.1660)), Vector((0.0368, TRACK["y"] - 0.0003, 0.1500))]
    seg = u * (len(pts) - 1)
    i = min(int(seg), len(pts) - 2)
    return pts[i].lerp(pts[i + 1], seg - i)


def build(res="look", samples=None, threshold=None, variant=None, **kw):
    S.new_scene(res, PRESET, samples=samples, threshold=threshold, exposure=-0.9)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 0, FRAMES - 1
    coll = S.collection("S21")
    out = E.build_room(coll, moon_z=4.3, moon_x=-2.6, neon_c=Vector((0.40, E.WIN_Y - 0.06, 1.40)))
    E.key_neon(out["neon"], [(0, 1.0)])
    # the Jägerbomb: amber-brown mix, the shot glass lying tilted on the bottom of the highball
    bomb = M.liquid("Bomb", 1.34, (0.80, 0.40, 0.11), 34.0, scatter=0.6, scatter_color=(0.9, 0.7, 0.4), anisotropy=0.5)
    hb = P.highball("Bomb", location=HB, fill=0.66, seed=21, coll=coll, drink_material=bomb, cond_facing_deg=-95.0,
                    n_streams=18)
    shot = P.shot_glass("SunkShot", location=HB + Vector((0.004, 0.003, hb.info["base"] + 0.0005)), frosted=False, fill=0.95,
                        seed=22, coll=coll, liquid_material=bomb)
    shot.root.rotation_euler = (math.radians(9.0), math.radians(-6.0), 0)
    shot.root.scale = (0.92, 0.92, 0.92)
    # the bottle: frosted, wet label, with the melt track keyed on the hero hit
    jager = M.jagermeister("JagerBottle", density=520.0)
    bt = P.bottle("Bottle", location=BOT, rotation_z_deg=-28.0, frosted=True, fill=0.93, seed=4, coll=coll, frost=0.5,
                  liquid_material=jager, frost_track=TRACK, frost_density=0.38)
    fm = bt.frost.data.materials[0]
    v = fm.node_tree.nodes["MeltFront"]
    for f, u in ((0, 0.0), (BEAD_F0, 0.0), (BEAD_F0 + 6, 0.35), (BEAD_F0 + 14, 0.7), (BEAD_F1, 1.0)):
        v.outputs[0].default_value = bead_path(u).z if u > 0 else TRACK["z_top"]
        v.outputs[0].keyframe_insert("default_value", frame=f)
    bead = P.scatter_drops("Bead", lambda r: None, 1, 0.001, 0.002, seed=3, coll=coll,
                           extra=[((0, 0, 0), (1, 0, 0), 0.0021, 2, 1.35)])
    bead.parent = bt.root
    for f in list(range(BEAD_F0 - 2, BEAD_F1 + 1)) + [0, FRAMES - 1]:
        u = min(max((f - BEAD_F0) / (BEAD_F1 - BEAD_F0), 0.0), 1.0)
        u = 1 - (1 - u) ** 1.6
        bead.location = bead_path(u) + Vector((0.0008, 0, 0))
        bead.keyframe_insert("location", frame=f)
    # light: warm key from front-left, cool window backlight, pink neon rim, warm pendant overhead
    S.area_light("Key", size=(0.5, 0.35), power=9.0, kelvin=3100, location=(HB + BOT) / 2 + Vector((-0.55, -0.55, 0.35)),
                 target=(HB + BOT) / 2 + Vector((0, 0, 0.10)), coll=coll)
    S.area_light("BackRim", size=(0.6, 0.2), power=4.0, kelvin=8000, location=(HB + BOT) / 2 + Vector((0.15, 0.45, 0.22)),
                 target=(HB + BOT) / 2 + Vector((0, 0, 0.08)), coll=coll)
    S.area_light("PinkRim", size=(0.2, 0.3), power=3.0, color=(1.0, 0.2, 0.5), location=BOT + Vector((0.4, 0.25, 0.15)),
                 target=BOT + Vector((0, 0, 0.12)), coll=coll)
    tgt = (HB + BOT) / 2 + Vector((0.0, 0.0, 0.11))
    cam = C.add_camera("CAM_S21", lens=85, location=tgt + Vector((-0.12, -1.30, 0.02)), target=tgt, fstop=4.0,
                       focus=HB + Vector((0.03, -0.03, 0.08)))
    if variant in REGIONS:
        x0, x1, y0, y1 = REGIONS[variant]
        sc.render.use_border = True
        sc.render.use_crop_to_border = False
        sc.render.border_min_x, sc.render.border_max_x = x0, x1
        sc.render.border_min_y, sc.render.border_max_y = y0, y1
        sc.render.film_transparent = True
    return dict(cam=cam)
