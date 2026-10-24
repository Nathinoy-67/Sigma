"""Set C -- the hold of a 1970s freighter, North Atlantic, dusk (S09-S10).

The ship's side plating stands in the x-z plane at y = 0 (the sea is at y < 0); the hold is at y > 0.  Steel frames
every 0.6 m, riveted plate seams, chipped green paint over red primer over rust.  A riveted brass porthole at
PORT shows the grey Atlantic swell at dusk.  Slatted pine crates stencilled for export stand in front of the plating,
green bottle necks bedded in straw; a cargo net hangs on the right; a caged bulb swings on its flex.  The whole hold
rolls +-2 deg about the ship's long axis (x) on a 7 s period.
"""
import math
import os
import random

import bmesh
import bpy
import numpy as np
from mathutils import Vector, Matrix, noise as mn

import scene as S
import materials as M
import props as P

PORT = Vector((0.0, 0.0, 1.55))     # porthole centre on the plating
PORT_R = 0.16                       # clear glass radius (32 cm)
BULB = Vector((0.55, 1.15, 2.55))   # bulb rest position


# --------------------------------------------------------------------------- materials
def ship_paint(name="HullPaint", seed=0, green=(0.07, 0.15, 0.10), chips=0.5):
    """Chipped green gloss over red-oxide primer over rust over steel (noise chip masks, edge wear from AO)."""
    m, t = M.new_material(name)
    p = t.texco("Object")
    n1 = t.noise(p, scale=14.0, detail=10.0, rough=0.7)
    n2 = t.noise(p, scale=70.0, detail=6.0, rough=0.6)
    ao = t.node("ShaderNodeAmbientOcclusion", {"Distance": 0.02}, only_local=True).outputs["AO"]
    edge = t.math("SUBTRACT", 1.0, ao)
    chip = t.add(t.mul(n1, 0.7), t.mul(n2, 0.3))
    thr = 0.62 - chips * 0.12
    big = t.smooth(t.noise(p, scale=1.5, detail=3.0), 0.45, 0.65)      # wear concentrates in patches
    chip = t.add(chip, t.mul(big, 0.12))
    primer = t.smooth(chip, thr - 0.03, thr)                 # green gone, primer shows
    rust = t.smooth(chip, thr + 0.02, thr + 0.06)            # primer gone too
    streak = t.mul(t.smooth(t.noise(t.mapping(p, scale=(14.0, 14.0, 0.8)), scale=6.0, detail=4.0), 0.55, 0.8), 0.6)
    col = t.mixc(t.mul(t.noise(p, scale=2.0), 0.25), green, tuple(c * 0.7 for c in green))
    col = t.mixc(t.mul(streak, 0.5), col, (0.10, 0.05, 0.02))                  # rust streaks running down
    col = t.mixc(primer, col, (0.14, 0.045, 0.03))
    rc = t.ramp(t.noise(p, scale=120.0, detail=4.0), [(0.3, (0.07, 0.03, 0.012)), (0.7, (0.17, 0.075, 0.03))])
    col = t.mixc(rust, col, rc)
    col = t.mixc(t.mul(edge, 0.6), col, (0.05, 0.04, 0.035))
    rough = t.mixf(primer, 0.38, 0.7)
    rough = t.mixf(rust, rough, 0.9)
    h = t.add(t.mul(primer, 0.4), t.mul(rust, -0.3))
    h = t.add(h, t.mul(t.noise(p, scale=300.0, detail=3.0), t.mul(rust, 0.5)))
    t.output(t.principled(base=col, rough=rough, normal=t.bump(h, 0.6, 0.0015), coat=t.mul(t.math("SUBTRACT", 1.0, primer), 0.3),
                          coat_rough=0.25))
    return m


def pine_crate_material(name, stencils, root, size, seed=0):
    """Rough-sawn pine with saw-mark bands; stencils projected on faces in the crate root's frame.
    stencils: {face: image name} with face in ('-y', '+y', '-x', '+x')."""
    m, t = M.new_material(name)
    tc = t.node("ShaderNodeTexCoord")
    tc.object = root
    p = tc.outputs["Object"]
    x, y, z = t.xyz(p)
    rnd = t.node("ShaderNodeObjectInfo").outputs["Random"]
    grain = t.noise(t.mapping(p, scale=(1.0, 1.0, 22.0)), scale=14.0, detail=8.0, rough=0.6)
    grain2 = t.noise(t.mapping(p, scale=(22.0, 1.0, 1.0)), scale=14.0, detail=8.0, rough=0.6)
    saw = t.wave(t.mapping(p, scale=(1, 1, 1)), scale=38.0, kind="BANDS", direction="X", distortion=6.0, detail=4.0)
    base = t.mixc(rnd, (0.42, 0.27, 0.13), (0.55, 0.38, 0.20))
    col = t.mixc(t.mul(t.add(grain, grain2), 0.3), base, (0.30, 0.18, 0.08))
    col = t.mixc(t.mul(saw, 0.06), col, (0.32, 0.20, 0.09))
    dirt = t.smooth(t.noise(p, scale=5.0, detail=5.0), 0.5, 0.8)
    col = t.mixc(t.mul(dirt, 0.5), col, (0.16, 0.10, 0.05))
    nrm_obj = t.geo("Normal")
    paint = 0.0
    sx, sy, sz = size
    for face, img in stencils.items():
        axis, sign = face[-1], (-1 if face[0] == "-" else 1)
        if axis == "y":
            u = t.add(0.5, t.mul(x, 1.0 / sx)) if sign < 0 else t.add(0.5, t.mul(x, -1.0 / sx))
            facing = t.math("GREATER_THAN", t.mul(t.xyz(nrm_obj)[1], sign), 0.5)
        else:
            u = t.add(0.5, t.mul(y, -1.0 / sy)) if sign < 0 else t.add(0.5, t.mul(y, 1.0 / sy))
            facing = t.math("GREATER_THAN", t.mul(t.xyz(nrm_obj)[0], sign), 0.5)
        v = t.add(0.5, t.mul(t.add(z, -sz / 2), 1.0 / (sz * 0.5)))
        a = t.image(os.path.join(S.TEXTURES, f"stencil_{img}.png"), t.combine(u, v, 0.0), colorspace="Non-Color",
                    extension="CLIP", out="Color")
        a = t.mul(t.xyz(a)[0], facing)
        paint = a if paint == 0.0 else t.math("MAXIMUM", paint, a)
    if paint != 0.0:
        col = t.mixc(paint, col, (0.02, 0.02, 0.022))
    t.output(t.principled(base=col, rough=0.85, normal=t.bump(t.add(grain, t.mul(saw, 0.3)), 0.5, 0.002)))
    return m


# --------------------------------------------------------------------------- geometry
def plating(coll, width=4.4, height=3.2):
    """Side plating with a gentle tumblehome, a porthole hole, frames and rivets."""
    nx, nz = 88, 64
    verts, faces = [], []
    for j in range(nz + 1):
        z = height * j / nz
        for i in range(nx + 1):
            x = -width / 2 + width * i / nx
            y = 0.06 * ((z - 1.6) / 1.6) ** 2 + 0.004 * mn.noise(Vector((x * 2, z * 2, 0.3)))   # dents
            verts.append((x, y, z))
    for j in range(nz):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + nx + 1, a + nx + 2, a + 1))
    ob = P.mesh("Plating", verts, faces, coll, True)
    so = ob.modifiers.new("t", "SOLIDIFY")
    so.thickness = 0.014
    so.offset = -1.0
    bpy.ops.mesh.primitive_cylinder_add(radius=PORT_R + 0.035, depth=1.0, vertices=64, location=PORT,
                                        rotation=(math.radians(90), 0, 0))
    cut = bpy.context.active_object
    cut.name = "PortCutter"
    cut.hide_render = cut.hide_viewport = True
    bo = ob.modifiers.new("port", "BOOLEAN")
    bo.operation, bo.object, bo.solver = "DIFFERENCE", cut, "EXACT"
    paint = ship_paint("HullPaint", seed=1)
    ob.data.materials.append(paint)
    # frames: L-section ribs every 0.6 m (skipping the porthole bay)
    rib_x = [x for x in np.arange(-2.1, 2.2, 0.6) if abs(x) > 0.25]
    for k, x in enumerate(rib_x):
        web = P.slab(f"RibWeb{k}", size=(0.012, 0.16, height), location=(x, 0.09, height), bevel=0.002, material=paint, coll=coll)
        fl = P.slab(f"RibFlange{k}", size=(0.08, 0.012, height), location=(x + 0.034, 0.17, height), bevel=0.002, material=paint, coll=coll)
    # rivets: domes along plate seams, rib roots and around the porthole
    pts = []
    for z in (0.95, 2.15):
        for x in np.arange(-2.15, 2.15, 0.055):
            if abs(x) > PORT_R + 0.06 or abs(z - PORT.z) > PORT_R + 0.06:
                pts.append((x, 0.0, z))
    for x in rib_x:
        for z in np.arange(0.05, height, 0.07):
            pts.append((x - 0.02, 0.0, z))
            pts.append((x + 0.02, 0.0, z))
    for a in np.linspace(0, 2 * math.pi, 16, endpoint=False):
        pts.append((PORT.x + (PORT_R + 0.1) * math.cos(a), 0.0, PORT.z + (PORT_R + 0.1) * math.sin(a)))
    tc = S.collection("RivetTemplate")
    tc.hide_render = True
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=6, radius=1.0)
    for v in bm.verts:
        if v.co.z < 0:
            v.co.z = 0.0
        v.co.z *= 0.6
    me = bpy.data.meshes.new("rivet")
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    rt = bpy.data.objects.new("rivet", me)
    tc.objects.link(rt)
    rt.data.materials.append(paint)
    P_, R_, S_, I_ = [], [], [], []
    for (x, y, z) in pts:
        yy = 0.06 * ((z - 1.6) / 1.6) ** 2 + 0.001
        P_.append((x, yy, z))
        R_.append((math.radians(-90), 0, 0))
        S_.append((0.009, 0.009, 0.009))
        I_.append(0)
    P.instanced_points("Rivets", P_, R_, S_, I_, tc, coll)
    return ob


def porthole(coll):
    """Brass ring with bolts, thick glass, the sea and dusk sky outside."""
    brass = M.metal("brass", name="PortBrass", seed=4, roughness=0.32, smudge=0.3, tarnish=0.6, color=(0.62, 0.42, 0.18))
    prof = [(PORT_R - 0.004, -0.05), (PORT_R + 0.07, -0.05), (PORT_R + 0.08, -0.04), (PORT_R + 0.08, -0.025),
            (PORT_R + 0.02, -0.02), (PORT_R + 0.015, 0.05), (PORT_R - 0.004, 0.05)]
    prof, _ = P.fillet(prof, [0, 0.004, 0.006, 0.004, 0.006, 0.004, 0], steps=4)
    ring = P.lathe("PortRing", prof, 96, coll=coll, wobble=0.002, seed=3)
    ring.data.materials.append(brass)
    ring.location = PORT + Vector((0, 0.06, 0))
    ring.rotation_euler = (math.radians(-90), 0, 0)
    for k in range(10):
        a = 2 * math.pi * k / 10 + 0.3
        bpy.ops.mesh.primitive_cylinder_add(radius=0.011, depth=0.012, vertices=6,
                                            location=PORT + Vector(((PORT_R + 0.05) * math.cos(a), 0.118, (PORT_R + 0.05) * math.sin(a))),
                                            rotation=(math.radians(90), 0, 0))
        b = bpy.context.active_object
        b.name = "PortBolt"
        b.data.materials.append(brass)
        S.link(b, coll)
    bpy.ops.mesh.primitive_cylinder_add(radius=PORT_R + 0.002, depth=0.018, vertices=64, location=PORT + Vector((0, 0.045, 0)),
                                        rotation=(math.radians(90), 0, 0))
    g = bpy.context.active_object
    g.name = "PortGlass"
    g.data.materials.append(M.glass("PortGlass", smudge=0.35, wavy=0.1, radius=PORT_R, seed=8, absorb=(0.85, 0.95, 0.9), density=4.0))
    g.visible_shadow = False
    S.link(g, coll)
    # outside: the sea and the sky (only ever seen out of focus through the glass)
    m, t = M.new_material("DuskSky")
    z = t.xyz(t.texco("Generated"))[1]
    col = t.ramp(z, [(0.0, (0.55, 0.50, 0.50)), (0.25, (0.42, 0.45, 0.55)), (1.0, (0.12, 0.17, 0.30))])
    t.output(t.node("ShaderNodeEmission", {"Color": col, "Strength": 3.0}))
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, -60, 10), rotation=(math.radians(90), 0, 0))
    sky = bpy.context.active_object
    sky.name = "DuskSkyCard"
    sky.scale = (200, 60, 1)
    sky.data.materials.append(m)
    sky.visible_shadow = False
    S.link(sky, coll)
    # sea: a big grid with an animated swell (4D noise, W keyed) + fine chop in the shader
    nx, ny = 240, 140
    verts, faces = [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            verts.append((-40 + 80 * i / nx, -1.0 - 59.0 * (j / ny) ** 1.6, 0.0))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    sea = P.mesh("Sea", verts, faces, coll, True)
    sea.location = (0, 0, 0.55)
    tex = bpy.data.textures.new("Swell", "CLOUDS")
    tex.noise_scale = 6.0
    tex.noise_depth = 2
    dm = sea.modifiers.new("swell", "DISPLACE")
    dm.texture = tex
    dm.strength = 1.6
    dm.mid_level = 0.5
    dm.texture_coords = "GLOBAL"
    sm, st = M.new_material("Sea")
    p = st.texco("Object")
    w = st.node("ShaderNodeValue")
    w.name = "SeaTime"
    chop = st.noise(st.mapping(p, scale=(1.0, 1.0, 1.0)), scale=1.8, detail=6.0, w=w.outputs[0], dims="4D")
    st.output(st.principled(base=(0.010, 0.016, 0.020), rough=0.22, spec=0.6, normal=st.bump(chop, 0.4, 0.15)))
    sea.data.materials.append(sm)
    for f, val in ((0, 0.0), (200, 3.0)):
        w.outputs[0].default_value = val
        w.outputs[0].keyframe_insert("default_value", frame=f)
    # the swell moves: slide the displacement texture space through the frames
    emp = S.empty("SwellSpace", (0, 0, 0), coll=coll)
    dm.texture_coords = "OBJECT"
    dm.texture_coords_object = emp
    emp.keyframe_insert("location", frame=0)
    emp.location = (1.2, -6.0, 0.0)
    emp.keyframe_insert("location", frame=200)
    return ring


def crate(name, loc, size=(0.62, 0.42, 0.36), rot_z=0.0, stencils=None, coll=None, seed=0, bottles=True, lid=False):
    """Slatted pine crate (planks with gaps, corner posts, nails), straw and green bottle necks inside."""
    rng = random.Random(seed)
    root = S.empty(name, loc, coll=coll)
    root.rotation_euler = (0, 0, math.radians(rot_z))
    sx, sy, sz = size
    mat = pine_crate_material(name + "_Pine", stencils or {}, root, size, seed)
    nail = M.metal("iron", name="Nail", seed=9, roughness=0.5, rust=0.4)
    t = 0.016
    slat_h, gap = 0.085, 0.022
    obs = []
    zs = []
    z = 0.0
    while z + slat_h <= sz + 0.001:
        zs.append(z)
        z += slat_h + gap
    for z0 in zs:
        for face, (cx, cy, w, d) in {"-y": (0, -sy / 2 + t / 2, sx, t), "+y": (0, sy / 2 - t / 2, sx, t),
                                     "-x": (-sx / 2 + t / 2, 0, t, sy - 2 * t), "+x": (sx / 2 - t / 2, 0, t, sy - 2 * t)}.items():
            o = P.slab(f"{name}_slat", size=(w * rng.uniform(0.995, 1.0), d, slat_h * rng.uniform(0.97, 1.0)),
                       location=(cx + rng.uniform(-0.002, 0.002), cy, z0 + slat_h), bevel=0.0025, material=mat, coll=coll)
            obs.append(o)
    for sxs in (-1, 1):
        for sys_ in (-1, 1):
            o = P.slab(f"{name}_post", size=(0.04, 0.04, sz), location=(sxs * (sx / 2 - 0.03), sys_ * (sy / 2 - 0.03), sz),
                       bevel=0.003, material=mat, coll=coll)
            obs.append(o)
    if lid:
        for k in range(4):
            o = P.slab(f"{name}_lid", size=(sx, 0.085, t), location=(0, -sy / 2 + 0.05 + k * 0.105, sz + t), bevel=0.002,
                       material=mat, coll=coll)
            obs.append(o)
    for o in obs:
        o.parent = root
    # nail heads on the front slats
    for z0 in zs:
        for xx in (-sx / 2 + 0.03, sx / 2 - 0.03):
            bpy.ops.mesh.primitive_cylinder_add(radius=0.0035, depth=0.002, vertices=10,
                                                location=(xx, sy / 2 + 0.001, z0 + slat_h / 2), rotation=(math.radians(90), 0, 0))
            nh = bpy.context.active_object
            nh.data.materials.append(nail)
            S.link(nh, coll)
            nh.parent = root
    if bottles:
        green = M.glass("BottleGreen", absorb=(0.10, 0.45, 0.12), density=90.0, smudge=0.2, radius=0.04, seed=seed)
        prof = [(0.0, 0.0), (0.040, 0.0), (0.040, 0.16), (0.034, 0.19), (0.016, 0.225), (0.015, 0.27), (0.017, 0.28),
                (0.0, 0.282)]
        prof, _ = P.fillet(prof, [0, 0.004, 0.01, 0.02, 0.008, 0.002, 0.001, 0], steps=4)
        for i in range(3):
            for j in range(2 if sy < 0.5 else 3):
                bx = -sx / 2 + sx * (i + 0.5) / 3 + rng.uniform(-0.01, 0.01)
                by = -sy / 2 + sy * (j + 0.5) / (2 if sy < 0.5 else 3) + rng.uniform(-0.01, 0.01)
                b = P.lathe(f"{name}_bottle", prof, 48, coll=coll)
                b.data.materials.append(green)
                b.parent = root
                b.location = (bx, by, sz - 0.24 + rng.uniform(-0.01, 0.01))
                b.rotation_euler = (rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05), 0)
        # straw: instanced bent stalks bedded around the necks, poking out between the slats
        stc = bpy.data.collections.get("StrawTemplates")
        if stc is None:
            stc = S.collection("StrawTemplates")
            stc.hide_render = True
            sm, stt = M.new_material("Straw")
            n = stt.noise(stt.mapping(stt.texco("Object"), scale=(1, 1, 30)), scale=40.0, detail=3.0)
            stt.output(stt.principled(base=stt.mixc(n, (0.55, 0.42, 0.18), (0.38, 0.28, 0.12)), rough=0.5, sheen=0.4,
                                      normal=stt.bump(n, 0.4, 0.001)))
            for k in range(4):
                cu = bpy.data.curves.new(f"straw_t{k}", "CURVE")
                cu.dimensions = "3D"
                cu.bevel_depth = 0.0011
                cu.bevel_resolution = 1
                spl = cu.splines.new("BEZIER")
                spl.bezier_points.add(2)
                L = 0.05 + 0.015 * k
                for q, bp in enumerate(spl.bezier_points):
                    bp.co = (0, 0.012 * math.sin(q * 1.7 + k) * (q > 0), L * q / 2)
                    bp.handle_left_type = bp.handle_right_type = "AUTO"
                so = bpy.data.objects.new(f"straw_t{k}", cu)
                stc.objects.link(so)
                so.data.materials.append(sm)
        Pp, R, Sc, I = [], [], [], []
        for k in range(1400):
            xx, yy = rng.uniform(-sx / 2 + 0.02, sx / 2 - 0.02), rng.uniform(-sy / 2 + 0.02, sy / 2 - 0.02)
            zz = rng.uniform(sz - 0.13, sz - 0.07)
            Pp.append((xx, yy, zz))
            R.append((rng.uniform(1.2, 1.95), rng.uniform(-0.3, 0.3), rng.uniform(0, 6.28)))
            s = rng.uniform(0.6, 1.2)
            Sc.append((s, s, s))
            I.append(rng.randrange(4))
        so = P.instanced_points(f"{name}_straw", Pp, R, Sc, I, stc, coll)
        so.visible_shadow = False         # the hard bulb turns every stalk into a long scratch-like shadow
        so.parent = root
    return root


def cargo_net(coll, origin=Vector((1.85, 0.35, 2.5)), w=1.0, h=1.6, cell=0.2):
    """Rope net hanging from two hooks: a sagging grid turned into rope by a Wireframe modifier."""
    nx, nz = int(w / cell), int(h / cell)
    verts, faces = [], []
    for j in range(nz + 1):
        for i in range(nx + 1):
            u, v = i / nx, j / nz
            x = origin.x - w / 2 + w * u
            z = origin.z - h * v + 0.18 * math.sin(math.pi * u) * (1 - v) ** 0.5
            y = origin.y + 0.10 * v ** 1.5 + 0.03 * mn.noise(Vector((u * 3, v * 3, 0.2)))
            verts.append((x, y, z))
    for j in range(nz):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    ob = P.mesh("CargoNet", verts, faces, coll, False)
    wf = ob.modifiers.new("rope", "WIREFRAME")
    wf.thickness = 0.007
    wf.use_even_offset = False
    sub = ob.modifiers.new("sub", "SUBSURF")
    sub.levels = sub.render_levels = 1
    m, t = M.new_material("Rope")
    p = t.texco("Object")
    tw = t.wave(t.mapping(p, rot=(0.7, 0.7, 0)), scale=180.0, kind="BANDS", distortion=1.0)
    t.output(t.principled(base=t.mixc(tw, (0.32, 0.24, 0.13), (0.20, 0.14, 0.07)), rough=0.9, sheen=0.4,
                          normal=t.bump(tw, 0.6, 0.002)))
    ob.data.materials.append(m)
    return ob


def caged_bulb(coll, swing_deg=11.0, period=50.0, phase=0.0, frames=120):
    """A bare 40 W bulb in a wire cage on a 1 m flex from the deck; a real point light so the cage throws hard
    moving shadows.  Swings as a damped-free pendulum about its hook."""
    hook = BULB + Vector((0, 0, 1.0))
    piv = S.empty("BulbPivot", hook, coll=coll)
    root = S.empty("BulbRoot", (0, 0, -1.0), coll=coll)
    root.parent = piv
    wire = M.metal("steel_brushed", name="CageWire", roughness=0.4, seed=3)
    # flex
    bpy.ops.mesh.primitive_cylinder_add(radius=0.003, depth=0.92, vertices=8, location=(0, 0, 0.5))
    fl = bpy.context.active_object
    fl.name = "BulbFlex"
    fl.data.materials.append(M.rubber("Flex", color=(0.01, 0.01, 0.01), roughness=0.5))
    S.link(fl, coll)
    fl.parent = root
    # holder, glass, filament, light
    bpy.ops.mesh.primitive_cylinder_add(radius=0.018, depth=0.05, vertices=24, location=(0, 0, 0.05))
    hd = bpy.context.active_object
    hd.name = "BulbHolder"
    hd.data.materials.append(M.plastic((0.02, 0.018, 0.015), roughness=0.4, name="Bakelite"))
    S.link(hd, coll)
    hd.parent = root
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.03, location=(0, 0, -0.01))
    gl = bpy.context.active_object
    gl.name = "BulbGlass"
    gl.scale = (1, 1, 1.25)
    gl.data.materials.append(M.glass("BulbGlass", smudge=0.1, radius=0.03, seed=2))
    gl.visible_shadow = False
    S.link(gl, coll)
    gl.parent = root
    bpy.ops.mesh.primitive_torus_add(major_radius=0.006, minor_radius=0.0007, location=(0, 0, -0.012))
    fi = bpy.context.active_object
    fi.name = "Filament"
    fi.data.materials.append(M.emission(kelvin=2400, strength=400.0, name="FilamentGlow"))
    fi.visible_shadow = False
    S.link(fi, coll)
    fi.parent = root
    lamp = S.point_light("BulbLight", power=160.0, kelvin=2600, location=(0, 0, -0.012), radius=0.008, coll=coll)
    lamp.parent = root
    # cage: 6 meridians + 2 rings
    for k in range(6):
        a = math.pi * k / 6
        bpy.ops.mesh.primitive_torus_add(major_radius=0.05, minor_radius=0.0012, location=(0, 0, -0.012),
                                         rotation=(math.radians(90), 0, a))
        c = bpy.context.active_object
        c.name = "CageWire"
        c.scale = (0.95, 0.95, 1.25)
        c.data.materials.append(wire)
        S.link(c, coll)
        c.parent = root
    for zz, rr in ((-0.012, 0.048), (0.025, 0.038)):
        bpy.ops.mesh.primitive_torus_add(major_radius=rr, minor_radius=0.0013, location=(0, 0, zz))
        c = bpy.context.active_object
        c.name = "CageRing"
        c.data.materials.append(wire)
        S.link(c, coll)
        c.parent = root
    for f in range(frames):
        a = math.radians(swing_deg) * math.sin(2 * math.pi * f / period + phase)
        b = math.radians(swing_deg * 0.35) * math.sin(2 * math.pi * f / (period * 1.13) + phase * 0.7 + 1.0)
        piv.rotation_euler = (a, b, 0)
        piv.keyframe_insert("rotation_euler", frame=f)
    return dict(pivot=piv, light=lamp)


def roll(coll_root_objs, frames=120, amp_deg=2.0, period=168.0, phase=0.0):
    """Parent the given objects to a roll empty that rocks about the ship's long axis (x) through the hold."""
    r = S.empty("ShipRoll", (0, 0.8, 0.0))
    for ob in coll_root_objs:
        if ob.parent is None and ob is not r:
            mw = ob.matrix_world.copy()
            ob.parent = r
            ob.matrix_parent_inverse = r.matrix_world.inverted()
    for f in range(frames):
        r.rotation_euler = (math.radians(amp_deg) * math.sin(2 * math.pi * f / period + phase), 0, 0)
        r.keyframe_insert("rotation_euler", frame=f)
    return r


def build_hold(coll, frames=120):
    out = {}
    plate = plating(coll)
    porthole(coll)
    deck = P.slab("TankTop", size=(4.4, 3.6, 0.02), location=(0, 1.8, 0.0), bevel=0.0, material=ship_paint("DeckPaint", 4, (0.09, 0.08, 0.06), chips=0.8), coll=coll)
    over = P.slab("DeckHead", size=(4.4, 3.6, 0.02), location=(0, 1.8, 3.25), bevel=0.0, material=ship_paint("DeckHeadPaint", 5, (0.06, 0.07, 0.06), chips=0.6), coll=coll)
    out["crates"] = [
        crate("CrateA", (-0.55, 0.42, 0.0), stencils={"+y": "made"}, coll=coll, seed=1, rot_z=-2.0),
        crate("CrateB", (0.20, 0.40, 0.0), stencils={"+y": "fragile"}, coll=coll, seed=2, rot_z=3.0),
        crate("CrateC", (-0.20, 0.48, 0.38), stencils={"+y": "consignee"}, coll=coll, seed=3, rot_z=-4.0, lid=False),
        crate("CrateD", (0.95, 0.55, 0.0), stencils={"+y": "kraeuter"}, coll=coll, seed=4, rot_z=8.0),
        crate("CrateE", (-1.25, 0.50, 0.0), stencils={"+y": "consignee"}, coll=coll, seed=5, rot_z=-6.0),
    ]
    cargo_net(coll)
    out["bulb"] = caged_bulb(coll, frames=frames)
    out["port_glow"] = S.area_light("PortGlow", size=(0.34, 0.34), power=14.0, kelvin=8500, location=PORT + Vector((0, 0.1, 0)),
                                    target=PORT + Vector((0, 2.0, -0.6)), shape="DISK", spread_deg=100.0, coll=coll)
    return out
