"""Set E -- a lakeside lodge bar on the west shore of Lake Tahoe, c. 1997, summer blue hour (S13-S16, S21-S22).

Knotty-pine room; a lacquered fir counter runs along y towards the east window (y = WIN_Y) that looks over the lake to
the Carson Range (the painted E-X plate on an emission card 30 m out; the moon is its own disc so it can rise).
A pink neon OPEN hangs inside the window, reading backwards from in here.  Enamel pendants over the bar, chrome stools
with cracked red vinyl, a back bar of out-of-focus bottles.  Bar top at z = BAR_Z.
"""
import math
import os
import random

import bmesh
import bpy
import numpy as np
from mathutils import Vector, noise as mn

import scene as S
import materials as M
import props as P

BAR_Z = 1.07
WIN_Y = 2.6
WIN = (2.4, 1.4)                 # window width x height
WIN_Z0 = 1.10                    # sill height (just above the bar top: the lake is the backdrop at bar level)
EYE_Z = 1.12                     # horizon height on the plate (eye level at the bar)
PLATE_Y = 32.0
NEON_C = Vector((0.55, WIN_Y - 0.06, 1.62))
MOON_R = 0.95                    # an exaggerated, telephoto-feeling moon (about 3.4 deg)
NEON_STRENGTH = 9.0


# --------------------------------------------------------------------------- materials
def knotty_pine(name="KnottyPine", seed=0):
    m, t = M.new_material(name)
    p = t.texco("Object")
    x, y, z = t.xyz(p)
    knots = t.voronoi(t.mapping(p, scale=(1.0, 1.0, 0.35)), scale=2.2, out="Distance", rand=1.0)
    kcore = t.math("SUBTRACT", 1.0, t.smooth(knots, 0.0, 0.045))
    dist = t.mul(t.math("SUBTRACT", 1.0, t.smooth(knots, 0.0, 0.25)), 6.0)
    rings = t.wave(t.mapping(p, scale=(1.0, 1.0, 0.25)), scale=9.0, kind="BANDS", direction="Z", distortion=t.add(4.0, dist),
                   detail=4.0)
    planks = t.math("FRACT", t.mul(t.add(x, y), 1 / 0.14))
    seam = t.mul(t.smooth(planks, 0.0, 0.02), t.math("SUBTRACT", 1.0, t.smooth(planks, 0.98, 1.0)))
    pid = t.white(None, w=t.math("FLOOR", t.mul(t.add(x, y), 1 / 0.14)), out="Value")
    base = t.mixc(pid, (0.40, 0.21, 0.08), (0.52, 0.29, 0.11))
    col = t.mixc(t.mul(rings, 0.45), base, (0.25, 0.11, 0.035))
    col = t.mixc(kcore, col, (0.07, 0.03, 0.012))
    col = t.mixc(t.math("SUBTRACT", 1.0, seam), col, (0.05, 0.025, 0.01))
    t.output(t.principled(base=col, rough=0.45, coat=0.4, coat_rough=0.2, normal=t.bump(t.add(t.mul(rings, 0.2), seam), 0.2, 0.003)))
    return m


def vinyl_red(name="RedVinyl", seed=0):
    m, t = M.new_material(name)
    p = t.texco("Object")
    wr = t.noise(p, scale=60.0, detail=6.0, rough=0.6)
    cr = t.voronoi(t.mapping(p, scale=(1, 1, 1)), scale=28.0, feature="DISTANCE_TO_EDGE", out="Distance", rand=0.9)
    crack = t.mul(t.math("SUBTRACT", 1.0, t.smooth(cr, 0.0, 0.02)), t.smooth(t.noise(p, scale=6.0), 0.5, 0.7))
    col = t.mixc(t.mul(wr, 0.3), (0.30, 0.012, 0.012), (0.18, 0.006, 0.008))
    col = t.mixc(crack, col, (0.35, 0.28, 0.22))
    t.output(t.principled(base=col, rough=t.mixf(crack, 0.28, 0.8), sheen=0.25, coat=0.3, coat_rough=0.15,
                          normal=t.bump(t.add(wr, t.mul(crack, -1.0)), 0.25, 0.002)))
    return m


# --------------------------------------------------------------------------- exterior
def exterior(coll, moon_z=None, moon_x=-1.6):
    """The painted plate on an emission card, the moon disc and its glade on the lake."""
    plate_w = 64.0
    plate_h = plate_w * 2560 / 6144
    top = EYE_Z + 0.58 * plate_h
    m, t = M.new_material("TahoePlate")
    img = t.image(os.path.join(S.TEXTURES, "tahoe_plate.png"), t.node("ShaderNodeUVMap").outputs[0], extension="EXTEND")
    em = t.node("ShaderNodeEmission", {"Color": img, "Strength": 1.6})
    t.output(em)
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, PLATE_Y, top - plate_h / 2), rotation=(math.radians(90), 0, 0))
    card = bpy.context.active_object
    card.name = "TahoePlateCard"
    card.scale = (plate_w, plate_h, 1)
    card.data.materials.append(m)
    card.visible_shadow = False
    card.visible_diffuse = False
    S.link(card, coll)
    # moon: a softly textured disc (maria), slightly warm
    mm, mt = M.new_material("Moon")
    p = mt.texco("Object")
    maria = mt.smooth(mt.noise(p, scale=2.2, detail=6.0, rough=0.6), 0.45, 0.62)
    col = mt.mixc(mt.mul(maria, 0.28), (1.0, 0.97, 0.90), (0.62, 0.60, 0.58))
    rad = mt.vmath("LENGTH", p)
    limb = mt.map(rad, 0.0, MOON_R, 1.0, 0.82)
    mt.output(mt.node("ShaderNodeEmission", {"Color": mt.mixc(0.0, col, col), "Strength": mt.mul(limb, 9.0)}))
    bpy.ops.mesh.primitive_circle_add(vertices=128, radius=MOON_R, fill_type="NGON", location=(moon_x, PLATE_Y - 1.0, moon_z or 7.6),
                                      rotation=(math.radians(90), 0, 0))
    moon = bpy.context.active_object
    moon.name = "Moon"
    moon.data.materials.append(mm)
    moon.visible_shadow = False
    moon.visible_diffuse = False
    S.link(moon, coll)
    # glade: a broken vertical streak of moonlight on the water, below the moon
    gm, gt = M.new_material("MoonGlade")
    g = gt.texco("Generated")
    gx, gy, gz = gt.xyz(g)
    w = gt.math("POWER", gt.math("SUBTRACT", 1.0, gt.math("ABSOLUTE", gt.mul(gt.add(gx, -0.5), 2.0))), 3.0)
    rip = gt.noise(gt.mapping(gt.texco("Object"), scale=(3.0, 1.0, 40.0)), scale=2.0, detail=4.0, rough=0.6)
    spark = gt.smooth(rip, 0.52, 0.66)
    fade = gt.map(gy, 0.0, 1.0, 1.0, 0.35)
    gt.output(gt.add_shader(gt.node("ShaderNodeBsdfTransparent"),
                            gt.node("ShaderNodeEmission", {"Color": (1.0, 0.95, 0.85), "Strength": gt.mul(gt.mul(w, spark), gt.mul(fade, 3.5))})))
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(moon_x, PLATE_Y - 1.2, EYE_Z - 6.0), rotation=(math.radians(90), 0, 0))
    glade = bpy.context.active_object
    glade.name = "MoonGlade"
    glade.scale = (2.6, 12.0, 1)
    glade.data.materials.append(gm)
    glade.visible_shadow = False
    glade.visible_diffuse = False
    S.link(glade, coll)
    # blue-hour fill through the window
    sky = S.area_light("BlueHour", size=(WIN[0], WIN[1]), power=40.0, kelvin=11000, location=(0, WIN_Y - 0.1, WIN_Z0 + WIN[1] / 2),
                       target=(0, 0, 0.9), coll=coll)
    sky.visible_glossy = False
    sky.visible_transmission = False          # seen through the window glass it would read as a white sheet
    return dict(card=card, moon=moon, glade=glade, sky=sky)


# --------------------------------------------------------------------------- room
def room(coll):
    pine = knotty_pine()
    out = {}
    floor = P.slab("Floor", size=(5.0, 6.0, 0.05), location=(0, 0.0, 0.0), bevel=0.0,
                   material=M.wood("dark_table", name="FloorPlanks", seed=5, plank_width=0.12, scratches=1.0, value=0.8), coll=coll)
    # window wall with the opening (4 pieces), side walls, ceiling
    t = 0.15
    yw = WIN_Y + t / 2
    x0, x1, z0, z1 = -WIN[0] / 2, WIN[0] / 2, WIN_Z0, WIN_Z0 + WIN[1]
    for nm, sz, loc in (("WallWin_below", (5.0, t, z0), (0, yw, z0)), ("WallWin_above", (5.0, t, 3.0 - z1), (0, yw, 3.0)),
                        ("WallWin_left", (2.5 + x0, t, z1 - z0), ((-2.5 + x0) / 2, yw, z1)),
                        ("WallWin_right", (2.5 - x1, t, z1 - z0), ((2.5 + x1) / 2, yw, z1))):
        out[nm] = P.slab(nm, size=sz, location=loc, bevel=0.0, material=pine, coll=coll)
    out["wall_l"] = P.slab("WallLeft", size=(t, 6.0, 3.0), location=(-2.0, 0.0, 3.0), bevel=0.0, material=pine, coll=coll)
    out["wall_r"] = P.slab("WallRight", size=(t, 6.0, 3.0), location=(2.4, 0.0, 3.0), bevel=0.0, material=pine, coll=coll)
    out["ceil"] = P.slab("Ceiling", size=(5.0, 6.0, 0.05), location=(0, 0.0, 3.05), bevel=0.0, material=pine, coll=coll)
    # window frame: 2 x 2 panes, solidified glass with smudges
    frame_m = M.wood("fir_lacquer", name="WindowFrame", seed=8, value=0.5)
    fw = 0.07
    for nm, sz, loc in (("WinL", (fw, 0.09, WIN[1]), (x0 + fw / 2, WIN_Y, z1)), ("WinR", (fw, 0.09, WIN[1]), (x1 - fw / 2, WIN_Y, z1)),
                        ("WinB", (WIN[0], 0.11, fw), (0, WIN_Y, z0 + fw)), ("WinT", (WIN[0], 0.09, fw), (0, WIN_Y, z1)),
                        ("WinMidV", (0.05, 0.08, WIN[1]), (0, WIN_Y, z1)), ("WinMidH", (WIN[0], 0.08, 0.05), (0, WIN_Y, (z0 + z1) / 2 + 0.025))):
        P.slab(nm, size=sz, location=loc, bevel=0.004, material=frame_m, coll=coll)
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, WIN_Y + 0.01, (z0 + z1) / 2), rotation=(math.radians(90), 0, 0))
    g = bpy.context.active_object
    g.name = "WindowGlass"
    g.scale = (WIN[0], WIN[1], 1)
    so = g.modifiers.new("t", "SOLIDIFY")
    so.thickness = 0.004
    g.data.materials.append(M.glass("WindowGlassMat", smudge=0.18, wavy=0.03, radius=1.0, seed=6))
    g.visible_shadow = False
    S.link(g, coll)
    out["glass"] = g
    return out


def counter(coll, y0=-1.4, y1=2.15):
    top = P.slab("BarTop", size=(0.62, y1 - y0, 0.05), location=(0, (y0 + y1) / 2, BAR_Z), bevel=0.012,
                 material=M.wood("fir_lacquer", name="BarFir", seed=3, plank_width=0.155, grain_axis="Y", scratches=0.9, value=0.45), coll=coll)
    body = P.slab("BarBody", size=(0.5, y1 - y0, BAR_Z - 0.05), location=(-0.04, (y0 + y1) / 2, BAR_Z - 0.05), bevel=0.004,
                  material=knotty_pine("BarFront"), coll=coll)
    brass = M.metal("brass", name="RailBrass", roughness=0.2, seed=5, tarnish=0.2)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.025, depth=y1 - y0, vertices=32, location=(0.34, (y0 + y1) / 2, 0.22),
                                        rotation=(math.radians(90), 0, 0))
    rail = bpy.context.active_object
    rail.name = "FootRail"
    rail.data.materials.append(brass)
    S.link(rail, coll)
    return top


def stool(name, loc, coll, chrome, vinyl, seed=0):
    root = S.empty(name, loc, coll=coll)
    prof = [(0.0, 0.0), (0.21, 0.0), (0.21, 0.012), (0.05, 0.03), (0.03, 0.06), (0.03, 0.66), (0.05, 0.68), (0.0, 0.69)]
    prof, _ = P.fillet(prof, [0, 0.004, 0.004, 0.02, 0.01, 0.01, 0.006, 0], steps=4)
    base = P.lathe(name + "_base", prof, 64, coll=coll)
    base.data.materials.append(chrome)
    base.parent = root
    bpy.ops.mesh.primitive_torus_add(major_radius=0.17, minor_radius=0.011, location=(0, 0, 0.32))
    ring = bpy.context.active_object
    ring.name = name + "_footring"
    ring.data.materials.append(chrome)
    S.link(ring, coll)
    ring.parent = root
    seat = S.empty(name + "_seat", (0, 0, 0.69), coll=coll)
    seat.parent = root
    sp = [(0.0, 0.0), (0.18, 0.0), (0.185, 0.03), (0.18, 0.075), (0.15, 0.095), (0.0, 0.1)]
    sp, _ = P.fillet(sp, [0, 0.01, 0.02, 0.03, 0.04, 0], steps=6)
    cush = P.lathe(name + "_cushion", sp, 96, coll=coll, wobble=0.004, seed=seed)
    cush.data.materials.append(vinyl)
    cush.parent = seat
    band = P.lathe(name + "_band", [(0.17, -0.005), (0.188, -0.005), (0.19, 0.03), (0.17, 0.03)], 96, coll=coll)
    band.data.materials.append(chrome)
    band.parent = seat
    return root, seat


def back_bar(coll, x=-1.85, y0=-1.2, y1=1.8):
    """Two shelves of bottles along the left wall (only ever out of focus)."""
    rng = random.Random(9)
    shelf_m = M.wood("dark_table", name="ShelfWood", seed=21)
    glass_cols = [(0.35, 0.18, 0.05), (0.10, 0.30, 0.10), (0.6, 0.6, 0.6), (0.45, 0.25, 0.10), (0.15, 0.20, 0.35)]
    for k, z in enumerate((1.25, 1.62)):
        P.slab(f"Shelf{k}", size=(0.25, y1 - y0, 0.025), location=(x, (y0 + y1) / 2, z), bevel=0.003, material=shelf_m, coll=coll)
        y = y0 + 0.08
        while y < y1 - 0.05:
            h = rng.uniform(0.24, 0.33)
            r = rng.uniform(0.032, 0.042)
            prof = [(0.0, 0.0), (r, 0.0), (r, h * 0.62), (r * 0.45, h * 0.8), (r * 0.36, h), (0.0, h)]
            prof, _ = P.fillet(prof, [0, 0.004, 0.01, 0.01, 0.002, 0], steps=3)
            b = P.lathe("BackBottle", prof, 32, coll=coll)
            b.location = (x + rng.uniform(-0.04, 0.04), y, z)
            c = glass_cols[rng.randrange(len(glass_cols))]
            b.data.materials.append(M.glass(f"BB_{k}_{y:.2f}", absorb=c, density=60.0, smudge=0.1, radius=r, seed=int(y * 100)))
            y += 2 * r + rng.uniform(0.01, 0.05)
    # a mirror behind the bottles (bars have them): doubles the pendants and the neon in the bokeh
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(-1.93, (y0 + y1) / 2, 1.5), rotation=(0, math.radians(90), 0))
    mir = bpy.context.active_object
    mir.name = "BackMirror"
    mir.scale = (0.7, y1 - y0, 1)
    mm, mt = M.new_material("OldMirror")
    n = mt.noise(scale=30.0, detail=4.0)
    mt.output(mt.principled(base=(0.6, 0.58, 0.52), metallic=1.0, rough=mt.add(0.04, mt.mul(n, 0.08))))
    mir.data.materials.append(mm)
    S.link(mir, coll)


def pendants(coll, ys=(-0.5, 0.55, 1.6), z=1.95, power=60.0):
    out = []
    enamel = M.enamel((0.10, 0.20, 0.14), name="PendantGreen", chips=0.1)
    for i, y in enumerate(ys):
        prof = [(0.0, 0.16), (0.012, 0.16), (0.02, 0.13), (0.06, 0.07), (0.15, 0.0), (0.155, -0.004), (0.145, 0.002),
                (0.055, 0.068), (0.016, 0.125), (0.0, 0.13)]
        prof, _ = P.fillet(prof, [0, 0.002, 0.01, 0.03, 0.004, 0.001, 0.004, 0.03, 0.01, 0], steps=4)
        sh = P.lathe(f"Pendant{i}", prof, 96, coll=coll)
        sh.location = (0.0, y, z)
        sh.data.materials.append(enamel)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.04, location=(0.0, y, z + 0.05))
        bulb = bpy.context.active_object
        bulb.name = f"PendantBulb{i}"
        bulb.data.materials.append(M.emission(kelvin=2600, strength=30.0, name=f"PendantBulbGlow{i}"))
        bulb.visible_shadow = False
        S.link(bulb, coll)
        L = S.spot_light(f"PendantLight{i}", power=power, kelvin=2600, location=(0.0, y, z + 0.03), target=(0.0, y, 0.0),
                         angle_deg=95, blend=0.6, radius=0.03, coll=coll)
        bpy.ops.mesh.primitive_cylinder_add(radius=0.003, depth=3.05 - z - 0.16, vertices=8,
                                            location=(0.0, y, z + 0.16 + (3.05 - z - 0.16) / 2))
        cord = bpy.context.active_object
        cord.data.materials.append(M.rubber("Cord"))
        S.link(cord, coll)
        out.append(L)
    return out


GLYPHS = {   # block letters as seen from OUTSIDE; (u, v) in a 1 x 1.3 cell; each stroke a polyline
    "O": [[(0.2, 0.0), (0.8, 0.0), (1.0, 0.2), (1.0, 1.1), (0.8, 1.3), (0.2, 1.3), (0.0, 1.1), (0.0, 0.2), (0.2, 0.0)]],
    "P": [[(0.0, 0.0), (0.0, 1.3), (0.75, 1.3), (1.0, 1.1), (1.0, 0.85), (0.75, 0.65), (0.0, 0.65)]],
    "E": [[(1.0, 1.3), (0.0, 1.3), (0.0, 0.0), (1.0, 0.0)], [(0.0, 0.65), (0.75, 0.65)]],
    "N": [[(0.0, 0.0), (0.0, 1.3), (1.0, 0.0), (1.0, 1.3)]],
}


def neon_open(coll, center=None, size=0.15, color=(1.0, 0.16, 0.48)):
    """Pink neon OPEN, mounted inside the glass facing out (reads backwards from the room).  Returns the
    emission node (key its Strength for flicker) and the spill light."""
    center = Vector(center) if center is not None else NEON_C
    m, t = M.new_material("NeonPink")
    em = t.node("ShaderNodeEmission", {"Color": color, "Strength": NEON_STRENGTH})
    core = t.node("ShaderNodeEmission", {"Color": (1.0, 0.45, 0.70), "Strength": NEON_STRENGTH})
    lw = t.node("ShaderNodeLayerWeight", {"Blend": 0.35})
    t.output(t.mix_shader(lw.outputs["Facing"], core, em))
    adv = size * 1.25
    text = "OPEN"
    x_start = center.x + adv * len(text) / 2 - (adv - size) / 2
    for k, ch in enumerate(text):
        x0 = x_start - k * adv          # from outside, letters run towards -x
        for stroke in GLYPHS[ch]:
            cu = bpy.data.curves.new(f"neon_{ch}{k}", "CURVE")
            cu.dimensions = "3D"
            cu.bevel_depth = 0.0055
            cu.bevel_resolution = 4
            sp = cu.splines.new("POLY")
            sp.points.add(len(stroke) - 1)
            for i, (u, v) in enumerate(stroke):
                sp.points[i].co = (x0 - u * size, center.y, center.z - 0.65 * size + v * size, 1)
            ob = bpy.data.objects.new(f"Neon_{ch}{k}", cu)
            ob.data.materials.append(m)
            S.link(ob, coll)
    spill = S.point_light("NeonSpill", power=5.0, color=color, location=center + Vector((0, -0.15, 0)), radius=0.15, coll=coll)
    spill.visible_camera = False
    spill.visible_glossy = False
    spill.visible_transmission = False
    return dict(emission=(em, core), spill=spill, material=m)


def key_neon(neon, keys):
    """keys: [(frame, level 0..1), ...] constant steps (a stuttering transformer)."""
    em, core = neon["emission"]
    sp = neon["spill"]
    p0 = sp.data.energy
    for f, k in keys:
        for node in (em, core):
            node.inputs["Strength"].default_value = NEON_STRENGTH * k
            node.inputs["Strength"].keyframe_insert("default_value", frame=f)
        sp.data.energy = p0 * k
        sp.data.keyframe_insert("energy", frame=f)
    import camera as C
    for idb in (neon["material"].node_tree, sp.data):
        for fc in C.fcurves(idb):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"


def build_room(coll, stools_y=(-0.9, -0.2, 0.5, 1.2), moon_z=None, moon_x=-1.6, neon_c=None):
    """Everything common to the lodge shots.  Returns dict."""
    out = {}
    out.update(room(coll))
    out["bar"] = counter(coll)
    out["ext"] = exterior(coll, moon_z, moon_x)
    chrome = M.metal("chrome", name="StoolChrome", roughness=0.08, smudge=0.2, seed=4)
    vinyl = vinyl_red()
    out["stools"] = [stool(f"Stool{i}", (0.62, y, 0.0), coll, chrome, vinyl, seed=i) for i, y in enumerate(stools_y)]
    back_bar(coll)
    out["pendants"] = pendants(coll)
    out["neon"] = neon_open(coll, neon_c)
    S.world((0.002, 0.0025, 0.006), 1.0)
    return out


def bar_towel(name, loc, coll, rot_z=0.0, seed=0):
    """A folded cotton bar towel: a soft, slightly lumpy slab with a woven stripe pattern."""
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (0.20, 0.12, 0.018)
    bpy.ops.object.transform_apply(scale=True)
    bv = ob.modifiers.new("b", "BEVEL")
    bv.width, bv.segments = 0.007, 4
    sub = ob.modifiers.new("s", "SUBSURF")
    sub.levels = sub.render_levels = 3
    tex = bpy.data.textures.new(name + "_lumps", "CLOUDS")
    tex.noise_scale = 0.03
    dp = ob.modifiers.new("d", "DISPLACE")
    dp.texture, dp.strength = tex, 0.002
    ob.location = Vector(loc) + Vector((0, 0, 0.009))
    ob.rotation_euler = (0, 0, math.radians(rot_z))
    m, t = M.new_material(name + "_Cotton")
    p = t.texco("Object")
    x, y, z = t.xyz(p)
    stripe = t.smooth(t.math("ABSOLUTE", t.math("SINE", t.mul(x, 70.0))), 0.85, 0.9)
    weave = t.wave(t.mapping(p, rot=(0, 0, 0.78)), scale=1500.0, kind="BANDS", distortion=0.5)
    col = t.mixc(stripe, (0.62, 0.60, 0.55), (0.10, 0.16, 0.30))
    t.output(t.principled(base=col, rough=0.9, sheen=0.6, sheen_rough=0.4, normal=t.bump(weave, 0.4, 0.0004)))
    ob.data.materials.append(m)
    S.link(ob, coll)
    return ob
