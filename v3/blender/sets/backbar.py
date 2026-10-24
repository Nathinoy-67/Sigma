"""Set D -- the 1980s back bar, tap-machine corner (S11-S12).

A tabletop corner: an unbranded stainless three-bottle ice-cold tap machine (only its lower front, the frosted spout
and the drip grille are ever in frame), a black studded rubber bar mat, a frosted heavy-based shot glass.  Cool 4000 K
fluorescent tube overhead, a red neon smear and warm back-bar points far behind (oval bokeh only), a round enamel
pendant straight above the glass (its reflection is the disc of S12).  Bar-top at z = 0; the glass stands at GLASS.
"""
import math
import random

import bmesh
import bpy
import numpy as np
from mathutils import Vector, noise as mn

import scene as S
import materials as M
import props as P

GLASS = Vector((0.0, 0.0, 0.006))           # shot glass base (on the mat)
SPOUT = Vector((0.0, 0.0, 0.098))           # spout tip (stream origin)
MACHINE_FRONT_Y = 0.055                     # the machine's front face (it stands behind the glass, +y)


def brushed_steel(name="Stainless", seed=0):
    return M.metal("steel_brushed", name=name, seed=seed, roughness=0.18, smudge=0.25, aniso=0.6)


def machine(coll):
    """Lower front of the tap machine: body, a recessed dispensing bay with the spout, the drip grille."""
    st = brushed_steel("MachineSteel", 1)
    body = P.slab("MachineBody", size=(0.40, 0.30, 0.42), location=(0, MACHINE_FRONT_Y + 0.15, 0.56), bevel=0.006, material=st, coll=coll)
    base = P.slab("MachineBase", size=(0.40, 0.30, 0.03), location=(0, MACHINE_FRONT_Y + 0.15, 0.03), bevel=0.004, material=st, coll=coll)
    back = P.slab("BayBack", size=(0.40, 0.02, 0.14), location=(0, MACHINE_FRONT_Y + 0.11, 0.17), bevel=0.003,
                  material=M.plastic((0.012, 0.012, 0.013), roughness=0.3, name="PowderCoat", scuffs=0.4), coll=coll)
    # spout: a short tube down from the bay roof, a collar, frost fur
    prof = [(0.0, 0.0), (0.0042, 0.0), (0.0046, 0.002), (0.0046, 0.03), (0.0075, 0.034), (0.0075, 0.042), (0.0, 0.042)]
    prof, _ = P.fillet(prof, [0, 0.0006, 0.0006, 0.001, 0.001, 0.001, 0], steps=4)
    sp = P.lathe("Spout", prof, 64, coll=coll)
    sp.location = SPOUT
    sp.data.materials.append(st)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.0028, depth=0.002, vertices=32, location=SPOUT + Vector((0, 0, -0.0005)))
    hole = bpy.context.active_object
    hole.name = "SpoutBore"
    hole.data.materials.append(M.matte_black("Bore", 0.002))
    S.link(hole, coll)
    frost_fur(coll, [(SPOUT + Vector((0, 0, z)), r) for z, r in ((0.004, 0.0048), (0.012, 0.0048), (0.022, 0.0049),
                                                                  (0.032, 0.0078), (0.038, 0.0078))], n=3500, seed=3)
    # drip grille in front: perforated plate over a tray
    grille = P.slab("DripGrille", size=(0.30, 0.05, 0.004), location=(0, MACHINE_FRONT_Y + 0.03, 0.0045), bevel=0.001,
                    material=perforated(st), coll=coll)
    return dict(body=body, spout=sp)


def perforated(base_mat):
    """Drip grille: steel with round holes (brick-texture alpha) showing a dark tray beneath."""
    m, t = M.new_material("Grille")
    p = t.texco("Object")
    v = t.voronoi(t.mapping(p, scale=(1, 1, 1)), scale=160.0, rand=0.0, out="Distance")
    holes = t.smooth(v, 0.30, 0.34)
    steel = t.principled(base=(0.55, 0.56, 0.57), metallic=1.0, rough=0.25)
    dark = t.principled(base=(0.01, 0.01, 0.01), rough=0.6)
    t.output(t.mix_shader(holes, dark, steel))
    return m


def frost_fur(coll, rings, n=3000, seed=0):
    """Ice-crystal flakes (0.2-1 mm) instanced on the surface of a stack of (centre, radius) rings."""
    tc = bpy.data.collections.get("FrostTemplates")
    if tc is None:
        tc = S.collection("FrostTemplates")
        tc.hide_render = True
        m, t = M.new_material("IceCrystal")
        t.output(t.principled(base=(0.9, 0.93, 0.97), rough=0.25, transmission=0.6, ior=1.31, sheen=0.4))
        for k in range(4):
            bm = bmesh.new()
            bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
            r = random.Random(k)
            for v in bm.verts:
                v.co.x *= r.uniform(0.15, 0.4)
                v.co.y *= r.uniform(0.6, 1.0)
                v.co.z *= r.uniform(0.8, 1.6)
            me = bpy.data.meshes.new(f"ice_t{k}")
            bm.to_mesh(me)
            bm.free()
            ob = bpy.data.objects.new(f"ice_t{k}", me)
            tc.objects.link(ob)
            ob.data.materials.append(m)
    rng = random.Random(seed)
    Pp, R, Sc, I = [], [], [], []
    for k in range(n):
        (c0, r0), (c1, r1) = rings[rng.randrange(len(rings) - 1)], rings[0]
        i = rng.randrange(len(rings) - 1)
        (ca, ra), (cb, rb) = rings[i], rings[i + 1]
        u = rng.random()
        c = ca.lerp(cb, u)
        r = ra + (rb - ra) * u
        a = rng.uniform(0, 2 * math.pi)
        nrm = Vector((math.cos(a), math.sin(a), 0))
        Pp.append(tuple(c + nrm * r))
        R.append((rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6) + math.pi / 2, a))
        s = 0.0001 + 0.0005 * rng.random() ** 2
        Sc.append((s, s, s))
        I.append(rng.randrange(4))
    return P.instanced_points("FrostFur", Pp, R, Sc, I, tc, coll)


def bar_mat(coll, size=(0.36, 0.22)):
    """Black studded rubber bar mat (studs instanced on a grid)."""
    rub = M.rubber("BarMat", color=(0.012, 0.012, 0.013), roughness=0.5, seed=2)
    mat = P.slab("BarMatBase", size=(size[0], size[1], 0.003), location=(0, -0.01, 0.003), bevel=0.0012, material=rub, coll=coll)
    tc = S.collection("StudTemplate")
    tc.hide_render = True
    bpy.ops.mesh.primitive_cylinder_add(radius=1.0, depth=1.0, vertices=16)
    stud = bpy.context.active_object
    stud.name = "stud"
    for c in list(stud.users_collection):
        c.objects.unlink(stud)
    tc.objects.link(stud)
    bv = stud.modifiers.new("b", "BEVEL")
    bv.width, bv.segments = 0.25, 2
    stud.data.materials.append(rub)
    Pp, R, Sc, I = [], [], [], []
    for i in range(int(size[0] / 0.009)):
        for j in range(int(size[1] / 0.009)):
            x = -size[0] / 2 + 0.0045 + i * 0.009
            y = -0.01 - size[1] / 2 + 0.0045 + j * 0.009
            if (x - GLASS.x) ** 2 + (y - GLASS.y) ** 2 < 0.022 ** 2:
                continue
            Pp.append((x, y, 0.0045))
            R.append((0, 0, 0))
            Sc.append((0.0022, 0.0022, 0.003))
            I.append(0)
    P.instanced_points("Studs", Pp, R, Sc, I, tc, coll)
    return mat


def counter(coll):
    top = P.slab("Counter", size=(1.6, 0.9, 0.04), location=(0, 0.1, 0.0), bevel=0.003,
                 material=M.wood("dark_table", name="CounterWood", seed=12, scratches=0.8), coll=coll)
    return top


def background(coll):
    """Out-of-focus back bar: a red neon smear and warm points, a dark wall."""
    wall = P.slab("BackWall", size=(4.0, 0.05, 2.0), location=(0, 2.2, 1.6), bevel=0.0, material=M.backdrop("BackWallMat", (0.015, 0.012, 0.01)), coll=coll)
    wall.rotation_euler = (math.radians(90), 0, 0)
    wall.location = (0, 2.2, 0.6)
    neon = M.emission(color=(1.0, 0.04, 0.03), strength=30.0, name="RedNeon")
    pts = [(-0.35, 1.9, 0.20), (-0.1, 1.9, 0.30), (0.2, 1.9, 0.22), (0.42, 1.9, 0.33)]
    cu = bpy.data.curves.new("NeonTube", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.006
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    for bp, q in zip(sp.bezier_points, pts):
        bp.co = q
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    ob = bpy.data.objects.new("RedNeon", cu)
    S.link(ob, coll)
    ob.data.materials.append(neon)
    rng = random.Random(4)
    warm = M.emission(kelvin=2600, strength=25.0, name="BackBarPoints")
    for k in range(9):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.008, location=(rng.uniform(-0.8, 0.8), rng.uniform(1.4, 2.0), rng.uniform(0.05, 0.5)))
        b = bpy.context.active_object
        b.name = "BackBarPoint"
        b.data.materials.append(warm)
        b.visible_shadow = False
        S.link(b, coll)


def lights(coll, pendant=True):
    tube = S.area_light("Fluorescent", size=(1.2, 0.04), power=80.0, kelvin=4000, location=(0.0, 0.25, 0.75),
                        target=(0.0, 0.05, 0.0), coll=coll)
    tube.visible_glossy = True
    rim = S.area_light("BackRim", size=(0.5, 0.2), power=25.0, kelvin=4500, location=(0.25, 0.6, 0.25), target=GLASS, coll=coll)
    out = dict(tube=tube, rim=rim)
    if pendant:
        # round enamel pendant straight above the glass; the diffuser disc is what the liquid mirrors in S12
        pz = 1.45
        shade_prof = [(0.0, 0.10), (0.03, 0.10), (0.05, 0.08), (0.11, 0.01), (0.12, 0.0), (0.118, -0.002), (0.108, 0.008),
                      (0.045, 0.078), (0.0, 0.088)]
        shade_prof, _ = P.fillet(shade_prof, [0, 0.01, 0.02, 0.02, 0.003, 0.001, 0.01, 0.02, 0], steps=4)
        sh = P.lathe("PendantShade", shade_prof, 96, coll=coll)
        sh.location = GLASS + Vector((0, 0, pz))
        sh.data.materials.append(M.enamel((0.55, 0.53, 0.48), name="PendantEnamel", chips=0.05))
        bpy.ops.mesh.primitive_circle_add(vertices=96, radius=0.1, fill_type="NGON", location=GLASS + Vector((0, 0, pz + 0.006)))
        d = bpy.context.active_object
        d.name = "PendantDiffuser"
        d.data.materials.append(M.emission(kelvin=3000, strength=22.0, name="PendantGlow"))
        S.link(d, coll)
        out["pendant"] = d
    return out
