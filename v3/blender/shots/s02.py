"""S02 BOTANICALS (film frames 75-135, 60 local frames).

The apothecary's mise en place on brown kraft paper: one small heap per botanical in a staggered row along the
workbench.  100 mm macro at f/2.8, lens 2 cm above the bench, a 12 cm motion-control slide left to right; the focus
plane travels with three hero heaps.  Raking east sun from frame left throws long shadows to the right; out-of-focus
foreground heaps pass the lens as natural wipes; amber apothecary jars glint far behind.
"""
import math
import random

import bpy
import numpy as np
from mathutils import Vector

import scene as S
import camera as C
import materials as M
import props as P
import botanicals as B
import workroom as A

FRAMES = 60
PRESET = "default"

# (kind, centre x, centre y, heap radius, counts) -- the row recedes slightly to the right
HEAPS = [
    ("star_anise", -0.105, 0.010, 0.022, {"star_anise": 9}),
    ("cinnamon", -0.075, 0.040, 0.026, {"cinnamon": 5}),
    ("cardamom", -0.052, -0.012, 0.016, {"cardamom": 22}),
    ("juniper", -0.022, 0.018, 0.017, {"juniper": 46}),
    ("saffron", 0.000, -0.018, 0.006, None),
    ("chamomile", 0.026, 0.026, 0.020, {"chamomile": 16}),
    ("orange_peel", 0.054, -0.006, 0.022, {"orange_peel": 4}),
    ("licorice", 0.083, 0.032, 0.022, {"licorice": 6}),
    ("ginger", 0.105, -0.010, 0.020, {"ginger": 5}),
    ("poppy", 0.132, 0.020, 0.016, None),
]
FOREGROUND = [("star_anise", -0.045, -0.115, 0.02, {"star_anise": 6, "juniper": 10}),
              ("cardamom", 0.075, -0.125, 0.02, {"cardamom": 10, "juniper": 12})]


def poppy_slope(center, radius, height, n, seed, coll):
    """A little cone of poppy seeds (0.9-1.2 mm blue-grey kidneys), instanced."""
    tc = bpy.data.collections.get("PoppyTemplates")
    if tc is None:
        tc = S.collection("PoppyTemplates")
        tc.hide_render = True
        m, t = M.new_material("PoppySeed")
        n_ = t.noise(scale=4000.0, detail=2.0)
        t.output(t.principled(base=t.mixc(n_, (0.06, 0.07, 0.085), (0.13, 0.14, 0.16)), rough=0.45,
                              normal=t.bump(t.voronoi(scale=9000.0), 0.4, 0.00005)))
        import bmesh
        for i in range(3):
            bm = bmesh.new()
            bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
            for v in bm.verts:
                v.co.x *= 1.0
                v.co.y *= 0.78
                v.co.z *= 0.62
                if v.co.x > 0.3:                  # kidney notch
                    v.co.y -= 0.18 * (v.co.x - 0.3)
            me = bpy.data.meshes.new(f"poppy_t{i}")
            bm.to_mesh(me)
            bm.free()
            me.shade_smooth()
            ob = bpy.data.objects.new(f"poppy_t{i}", me)
            tc.objects.link(ob)
            ob.data.materials.append(m)
    rng = np.random.default_rng(seed)
    Pp, R, Sc, I = [], [], [], []
    cx, cy, cz = center
    for k in range(n):
        r = radius * math.sqrt(rng.random()) * 1.15
        a = rng.uniform(0, 2 * math.pi)
        z = cz + max(0.0, height * (1 - r / radius)) + rng.uniform(0, 0.0004)
        s = rng.uniform(0.00045, 0.0006)
        Pp.append((cx + r * math.cos(a), cy + r * math.sin(a), z + s * 0.5))
        R.append((rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), rng.uniform(0, 6.28)))
        Sc.append((s, s, s))
        I.append(int(rng.integers(0, 3)))
    return P.instanced_points("PoppySeeds", Pp, R, Sc, I, tc, coll)


def build(res="look", samples=None, threshold=None, **kw):
    S.new_scene(res, PRESET, samples=samples, threshold=threshold, exposure=-0.2)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 0, FRAMES - 1
    coll = S.collection("S02")
    A.room(coll, floor=False)
    kraft = A.kraft_sheet("Kraft", size=(0.46, 0.34), center=(0.01, 0.0, 0.0), rotation_z_deg=4.0, seed=3, coll=coll)
    A.kraft_sheet("Kraft2", size=(0.30, 0.22), center=(-0.02, -0.15, -0.0002), rotation_z_deg=-9.0, seed=8, coll=coll)
    for i, (kind, x, y, r, counts) in enumerate(HEAPS):
        z = 0.0
        if kind == "saffron" and counts is None:
            B.drape_saffron([], 28, center=(x, y), radius=r, seed=40 + i, coll=coll, floor_z=z)
        elif kind == "poppy":
            poppy_slope((x, y, z + 0.0003), r, 0.007, 1800, 50 + i, coll)
        else:
            B.heap(center=(x, y, z), radius=r, counts=counts, seed=10 + i, coll=coll, n_crumbs=120 if i < len(HEAPS) else 0,
                   height=r * 0.6)
    # amber jars on a shelf far behind (bokeh only)
    for i, (x, h, rr) in enumerate(((-0.16, 0.16, 0.036), (-0.07, 0.12, 0.03), (0.05, 0.19, 0.04), (0.17, 0.14, 0.034))):
        A.apothecary_jar(f"Jar{i}", (x, 0.40 + 0.03 * (i % 2), 0.0), height=h, radius=rr, seed=i, coll=coll)
    lights = A.dawn(target=(0.0, 0.0, 0.01), azimuth_deg=18.0, elevation_deg=8.0, strength=9.0, kelvin=3400,
                    sky_strength=0.35, bounce=0.1, coll=coll, bar_through=(0.02, -0.03, 0.0),
                    transom_through=(0.0, 0.25, 0.0))
    S.world((0.003, 0.0035, 0.005), 1.0)
    # keep the low sun off the back wall and the jars' shelf: the background stays in the room's shade
    S.light_link(lights["sun"], exclude=[bpy.data.objects["WallN"]])

    # camera: 2 cm above the bench, 12 cm slide left -> right, focus travels with three hero heaps
    y_cam, z_cam = -0.25, 0.065
    p0, p1 = Vector((-0.075, y_cam, z_cam)), Vector((0.045, y_cam, z_cam))
    aim = Vector((0.0, 0.26, -0.058)).normalized()
    cam = C.add_camera("CAM_S02", lens=100, location=p0, target=p0 + aim, fstop=4.0, focus=0.27)
    C.move(cam, [(0, p0), (FRAMES - 1, p1)])
    focus_keys = [(0, (-0.075, 0.035, 0.008)), (24, (-0.022, 0.018, 0.008)), (44, (0.026, 0.026, 0.01)),
                  (FRAMES - 1, (0.054, -0.006, 0.008))]
    C.rack_focus(cam, focus_keys, breathing=0.01)
    C.breathe(cam, amplitude_deg=0.03, period_frames=80, seed=2)
    return dict(cam=cam)
