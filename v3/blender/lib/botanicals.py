"""botanicals.py -- seeded generators for the Krauterlikor botanical kit (true scale, metres).

    import botanicals as B
    ob = B.star_anise(seed=3, location=(0, 0, 0.01))
    ob = B.make("cardamom", seed=12)                    # by kind name, see B.KINDS
    objs = B.heap(center=(0, 0, 0), radius=0.045, seed=7)   # rigid-body-settled pile + saffron on top
    objs = B.heap(counts={"juniper": 30, "star_anise": 4}, ...)

Kinds: star_anise, cinnamon, cardamom, juniper, orange_peel, chamomile, licorice, ginger, saffron.
Every call with the same seed gives the same object; different seeds give different size, shape,
curl, colour and wear.  Materials are physically plausible procedural shaders (one shared material
per kind, with per-object variation driven by Object Info > Random).

heap(): items are dropped with Bullet rigid bodies (convex hulls, simulated at 10x scale for
stability), then frozen; saffron threads are laid on the settled pile by ray casting.  The result
is deterministic for a given seed.
"""
import math
import random

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector, noise as mnoise

import materials as M
import scene as S

KINDS = ["star_anise", "cinnamon", "cardamom", "juniper", "orange_peel", "chamomile", "licorice", "ginger", "saffron"]

_MATS = {}


# =========================================================================== mesh helpers
def _obj_from_bmesh(name, bm, coll=None, smooth=True, recalc=True):
    if recalc:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    S.link(ob, coll)
    return ob


def _grid_bm(rings, cap0=None, cap1=None, closed=True, bm=None, mat=0):
    """Build faces between consecutive rings (list of (N,3) arrays).  closed: rings wrap around.
    cap0/cap1: pole points (3,) closing the first/last ring, or 'fill' for an n-gon."""
    bm = bm or bmesh.new()
    R = [[bm.verts.new(tuple(p)) for p in ring] for ring in rings]
    n = len(rings[0])
    m = n if closed else n - 1
    for i in range(len(R) - 1):
        for j in range(m):
            k = (j + 1) % n
            f = bm.faces.new((R[i][j], R[i][k], R[i + 1][k], R[i + 1][j]))
            f.material_index = mat
    for cap, ring, flip in ((cap0, R[0], True), (cap1, R[-1], False)):
        if cap is None:
            continue
        if isinstance(cap, str):
            f = bm.faces.new(ring if not flip else list(reversed(ring)))
            f.material_index = mat
        else:
            pv = bm.verts.new(tuple(cap))
            for j in range(m):
                k = (j + 1) % n
                f = bm.faces.new((ring[k], ring[j], pv) if flip else (ring[j], ring[k], pv))
                f.material_index = mat
    return bm


def _noise3(p, scale, seed, octaves=2):
    v = Vector(p) * scale + Vector((seed * 1.37, seed * 2.11, seed * 0.73))
    return mnoise.fractal(v, 0.5, 2.0, octaves, noise_basis="PERLIN_ORIGINAL")


def _apply_mods(ob):
    """Bake modifiers into the mesh (needed before rigid bodies / to keep files simple)."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old)
    return ob


def _center_origin(ob):
    """Move the mesh so its bounding-box centre is the object origin (rigid bodies use the origin as
    centre of mass: an off-centre origin makes a cinnamon quill stand up like a weighted pole)."""
    me = ob.data
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    c = (co.min(0) + co.max(0)) / 2
    co -= c
    me.vertices.foreach_set("co", co.ravel())
    me.update()
    return Vector(c)


def _finish(ob, mats, location, rotation, scale=1.0):
    _center_origin(ob)
    for m in mats:
        ob.data.materials.append(m)
    ob.location = location
    ob.rotation_euler = rotation
    if scale != 1.0:
        ob.scale = (scale,) * 3
    return ob


def _mat(kind):
    """Shared materials per kind (rebuilt after scene.new_scene() wiped the data)."""
    try:
        ok = kind in _MATS and all(m.name in bpy.data.materials for m in _MATS[kind])
    except ReferenceError:
        ok = False
    if not ok:
        _MATS[kind] = MATERIALS[kind]()
    return _MATS[kind]


# =========================================================================== materials
def _rand_tint(t, a, b, amount=1.0):
    """Mix two colours by Object Info random (per-object variation)."""
    r = t.node("ShaderNodeObjectInfo").outputs["Random"]
    return t.mixc(t.mul(r, amount), a, b)


def _mat_star_anise():
    m, t = M.new_material("Bot_StarAnise")
    p = t.texco()
    wr = t.noise(p, scale=650.0, detail=6.0, rough=0.65, distortion=0.4)
    big = t.noise(p, scale=120.0, detail=3.0)
    base = _rand_tint(t, (0.20, 0.075, 0.028), (0.28, 0.12, 0.05))
    col = t.mixc(t.smooth(big, 0.35, 0.75), base, (0.11, 0.04, 0.016))
    col = t.mixc(t.mul(t.smooth(wr, 0.55, 0.8), 0.6), col, (0.36, 0.19, 0.09))
    ao = t.node("ShaderNodeAmbientOcclusion", {"Distance": 0.0015}, only_local=True).outputs["AO"]
    col = t.mixc(t.math("SUBTRACT", 1.0, ao), col, (0.03, 0.012, 0.006))
    nrm = t.bump(t.add(wr, t.mul(big, 0.4)), strength=1.0, distance=0.0005)
    body = t.principled(base=col, rough=t.map(wr, 0.3, 0.7, 0.62, 0.85), normal=nrm, sheen=0.15)
    t.output(body)
    s, ts = M.new_material("Bot_StarAniseSeed")
    n = ts.noise(scale=900.0, detail=2.0)
    ts.output(ts.principled(base=ts.mixc(ts.mul(n, 0.4), (0.42, 0.22, 0.08), (0.30, 0.14, 0.05)), rough=0.16,
                            coat=0.6, coat_rough=0.08, normal=ts.bump(n, 0.05, 0.0002)))
    return [m, s]


def _mat_cinnamon():
    mats = []
    for nm, c1, c2, r0, st in (("Outer", (0.10, 0.042, 0.020), (0.22, 0.10, 0.045), 0.85, 1.0),
                               ("Inner", (0.22, 0.09, 0.035), (0.31, 0.14, 0.055), 0.65, 0.6),
                               ("Rim", (0.34, 0.19, 0.09), (0.42, 0.25, 0.12), 0.9, 1.0)):
        m, t = M.new_material("Bot_Cinnamon" + nm)
        p = t.mapping(t.texco(), scale=(1.0, 14.0, 14.0))        # quill runs along X: fibres along X
        f = t.noise(p, scale=90.0, detail=6.0, rough=0.65)
        stri = t.noise(t.mapping(t.texco(), scale=(1.0, 40.0, 40.0)), scale=60.0, detail=3.0)   # fine grooves
        cracks = t.voronoi(t.mapping(t.texco(), scale=(0.35, 3.0, 3.0)), scale=260.0, feature="DISTANCE_TO_EDGE",
                           out="Distance", rand=0.85)
        crack = t.math("SUBTRACT", 1.0, t.smooth(cracks, 0.0, 0.035))
        blot = t.noise(t.texco(), scale=60.0, detail=3.0)
        col = t.mixc(t.smooth(f, 0.3, 0.7), _rand_tint(t, c1, c2, 0.6), c1)
        col = t.mixc(t.mul(t.smooth(stri, 0.45, 0.65), 0.5), col, (c1[0] * 0.6, c1[1] * 0.55, c1[2] * 0.5))
        col = t.mixc(t.mul(t.smooth(blot, 0.55, 0.75), 0.55), col, (c2[0] * 1.25, c2[1] * 1.2, c2[2] * 1.15))
        if nm == "Outer":
            col = t.mixc(t.mul(crack, 0.45), col, (0.05, 0.022, 0.01))
        h = t.add(t.add(t.mul(f, 0.5), t.mul(stri, 0.8)), t.mul(crack, -0.35 if nm == "Outer" else 0.0))
        t.output(t.principled(base=col, rough=r0, normal=t.bump(h, st, 0.0006), sheen=0.25, sheen_rough=0.5))
        mats.append(m)
    return mats


def _mat_cardamom():
    m, t = M.new_material("Bot_Cardamom")
    p = t.texco()
    n = t.noise(p, scale=300.0, detail=4.0)
    blot = t.noise(p, scale=80.0, detail=2.0)
    base = _rand_tint(t, (0.24, 0.30, 0.12), (0.36, 0.36, 0.17), 0.8)
    col = t.mixc(t.mul(t.smooth(blot, 0.5, 0.8), 0.7), base, (0.55, 0.50, 0.30))
    col = t.mixc(t.mul(n, 0.25), col, (0.20, 0.26, 0.10))
    t.output(t.principled(base=col, rough=0.6, sss=0.25, sss_radius=(0.002, 0.003, 0.001), sss_scale=1.0,
                          normal=t.bump(n, 0.7, 0.0004), sheen=0.3, sheen_tint=(0.8, 0.9, 0.7)))
    return [m]


def _mat_juniper():
    m, t = M.new_material("Bot_Juniper")
    p = t.texco()
    n = t.noise(p, scale=700.0, detail=4.0)
    rub = t.smooth(t.noise(p, scale=180.0, detail=3.0), 0.58, 0.72)   # bloom rubbed off
    base = _rand_tint(t, (0.030, 0.035, 0.065), (0.07, 0.035, 0.07), 0.9)
    col = t.mixc(t.mul(n, 0.4), base, (0.02, 0.02, 0.03))
    bloom = t.mul(t.math("SUBTRACT", 1.0, rub), 0.85)
    t.output(t.principled(base=col, rough=t.mixf(bloom, 0.32, 0.62), sheen=t.mul(bloom, 1.0),
                          sheen_rough=0.4, sheen_tint=(0.6, 0.65, 0.8), coat=t.mul(t.math("SUBTRACT", 1.0, bloom), 0.3),
                          coat_rough=0.2, normal=t.bump(n, 0.35, 0.0002)))
    return [m]


def _mat_orange_peel():
    mats = []
    m, t = M.new_material("Bot_OrangeZest")
    p = t.texco()
    pores = t.voronoi(p, scale=700.0, rand=0.9, out="Distance")
    blot = t.noise(p, scale=90.0, detail=4.0)
    base = _rand_tint(t, (0.36, 0.11, 0.012), (0.46, 0.17, 0.025), 0.8)
    col = t.mixc(t.mul(t.smooth(blot, 0.45, 0.8), 0.7), base, (0.15, 0.04, 0.01))
    col = t.mixc(t.mul(t.math("SUBTRACT", 1.0, t.smooth(pores, 0.05, 0.25)), 0.4), col, (0.18, 0.04, 0.01))
    h = t.add(t.smooth(pores, 0.0, 0.35), t.mul(blot, 0.3))
    t.output(t.principled(base=col, rough=t.map(blot, 0.3, 0.7, 0.45, 0.7), sss=0.05,
                          sss_radius=(0.002, 0.0008, 0.0003), normal=t.bump(h, 1.0, 0.0005), coat=0.25, coat_rough=0.3))
    mats.append(m)
    for nm, c in (("Pith", (0.55, 0.47, 0.30)), ("PithRim", (0.50, 0.40, 0.24))):
        m, t = M.new_material("Bot_Orange" + nm)
        sp = t.noise(t.texco(), scale=1500.0, detail=3.0)
        v = t.voronoi(t.texco(), scale=900.0, out="Distance")
        col = t.mixc(t.mul(sp, 0.4), c, (c[0] * 0.7, c[1] * 0.65, c[2] * 0.55))
        t.output(t.principled(base=col, rough=0.92, sss=0.05, sss_radius=(0.002, 0.0015, 0.001),
                              normal=t.bump(t.add(sp, v), 1.0, 0.0004)))
        mats.append(m)
    return mats


def _mat_chamomile():
    mats = []
    m, t = M.new_material("Bot_ChamomileDisc")
    v = t.voronoi(t.texco(), scale=2600.0, rand=0.8, out="Distance")
    n = t.noise(t.texco(), scale=400.0, detail=3.0)
    col = t.mixc(t.smooth(v, 0.05, 0.4), (0.42, 0.26, 0.03), _rand_tint(t, (0.80, 0.55, 0.07), (0.70, 0.50, 0.10)))
    col = t.mixc(t.mul(n, 0.3), col, (0.35, 0.22, 0.04))
    t.output(t.principled(base=col, rough=0.75, normal=t.bump(t.math("SUBTRACT", 1.0, v), 0.6, 0.0003), sss=0.1,
                          sss_radius=(0.001, 0.0008, 0.0002)))
    mats.append(m)
    m, t = M.new_material("Bot_ChamomilePetal")
    n = t.noise(t.mapping(t.texco(), scale=(1, 1, 1)), scale=900.0, detail=3.0)
    col = t.mixc(t.mul(n, 0.5), _rand_tint(t, (0.62, 0.57, 0.40), (0.52, 0.45, 0.28)), (0.40, 0.33, 0.20))
    bs = t.principled(base=col, rough=0.6, normal=t.bump(n, 0.2, 0.0002))
    tl = t.node("ShaderNodeBsdfTranslucent", {"Color": col})
    t.output(t.mix_shader(0.3, bs, tl))
    mats.append(m)
    m, t = M.new_material("Bot_ChamomileStem")
    t.output(t.principled(base=(0.30, 0.32, 0.15), rough=0.7))
    mats.append(m)
    return mats


def _mat_licorice():
    mats = []
    m, t = M.new_material("Bot_LicoriceBark")
    p = t.mapping(t.texco(), scale=(1.0, 10.0, 10.0))
    f = t.noise(p, scale=70.0, detail=6.0, rough=0.65)
    blot = t.noise(t.texco(), scale=50.0, detail=3.0)
    base = _rand_tint(t, (0.11, 0.07, 0.045), (0.17, 0.11, 0.07), 0.8)
    col = t.mixc(t.smooth(f, 0.3, 0.7), (0.045, 0.028, 0.018), base)
    col = t.mixc(t.mul(t.smooth(blot, 0.55, 0.8), 0.5), col, (0.24, 0.20, 0.15))
    t.output(t.principled(base=col, rough=0.88, normal=t.bump(f, 1.0, 0.0008)))
    mats.append(m)
    m, t = M.new_material("Bot_LicoriceCut")
    x, y, z = t.xyz(t.texco())
    ang = t.math("ARCTAN2", z, y)
    rad = t.math("SQRT", t.add(t.mul(y, y), t.mul(z, z)))
    fib = t.noise(t.combine(t.mul(ang, 6.0), t.mul(rad, 300.0), 0.0), scale=8.0, detail=4.0)
    rings = t.wave(t.combine(0, y, z), scale=120.0, kind="RINGS", direction="X", distortion=8.0, detail=3.0)
    speck = t.smooth(t.noise(t.texco(), scale=2500.0, detail=2.0), 0.6, 0.75)
    col = t.mixc(t.smooth(fib, 0.3, 0.7), (0.42, 0.28, 0.09), (0.66, 0.50, 0.19))
    col = t.mixc(t.mul(rings, 0.12), col, (0.38, 0.25, 0.08))
    col = t.mixc(t.mul(speck, 0.5), col, (0.25, 0.15, 0.06))
    t.output(t.principled(base=col, rough=0.8, normal=t.bump(t.add(fib, rings), 0.6, 0.0003)))
    mats.append(m)
    return mats


def _mat_ginger():
    mats = []
    m, t = M.new_material("Bot_GingerFlesh")
    p = t.texco()
    x, y, z = t.xyz(p)
    rad = t.math("SQRT", t.add(t.mul(x, x), t.mul(y, y)))
    ang = t.math("ARCTAN2", y, x)
    fib = t.noise(t.combine(t.mul(ang, 4.0), t.mul(rad, 160.0), z), scale=6.0, detail=5.0)
    dots = t.smooth(t.voronoi(p, scale=500.0, out="Distance"), 0.0, 0.18)
    ring = t.smooth(t.math("ABSOLUTE", t.add(t.noise(p, scale=120.0), -0.5)), 0.0, 0.05)
    base = _rand_tint(t, (0.50, 0.40, 0.22), (0.42, 0.31, 0.15), 0.8)
    col = t.mixc(t.mul(fib, 0.5), base, (0.33, 0.24, 0.11))
    col = t.mixc(t.mul(t.math("SUBTRACT", 1.0, dots), 0.4), col, (0.48, 0.36, 0.17))
    col = t.mixc(t.mul(t.math("SUBTRACT", 1.0, ring), 0.3), col, (0.45, 0.34, 0.16))
    fine = t.noise(t.combine(t.mul(ang, 30.0), t.mul(rad, 900.0), z), scale=3.0, detail=4.0)
    col = t.mixc(t.mul(t.smooth(fine, 0.5, 0.8), 0.35), col, (0.30, 0.21, 0.09))
    t.output(t.principled(base=col, rough=0.8, sss=0.12, sss_radius=(0.0015, 0.001, 0.0005),
                          normal=t.bump(t.add(t.add(fib, t.mul(dots, 0.5)), t.mul(fine, 0.8)), 1.0, 0.0006)))
    mats.append(m)
    m, t = M.new_material("Bot_GingerSkin")
    n = t.noise(t.texco(), scale=500.0, detail=5.0, rough=0.7)
    t.output(t.principled(base=t.mixc(n, (0.30, 0.20, 0.11), (0.48, 0.36, 0.22)), rough=0.85,
                          normal=t.bump(n, 0.8, 0.0003)))
    mats.append(m)
    return mats


def _mat_saffron():
    m, t = M.new_material("Bot_Saffron")
    n = t.noise(t.texco(), scale=2000.0, detail=3.0)
    col = t.mixc(t.mul(n, 0.5), _rand_tint(t, (0.42, 0.02, 0.008), (0.30, 0.012, 0.006)), (0.20, 0.008, 0.004))
    t.output(t.principled(base=col, rough=0.42, sss=0.35, sss_radius=(0.0012, 0.0002, 0.0001), sss_scale=1.0,
                          normal=t.bump(n, 0.2, 0.0001), coat=0.2, coat_rough=0.3))
    s, ts = M.new_material("Bot_SaffronStyle")
    ts.output(ts.principled(base=(0.75, 0.55, 0.16), rough=0.5, sss=0.2, sss_radius=(0.001, 0.0008, 0.0002)))
    return [m, s]


MATERIALS = {
    "star_anise": _mat_star_anise, "cinnamon": _mat_cinnamon, "cardamom": _mat_cardamom, "juniper": _mat_juniper,
    "orange_peel": _mat_orange_peel, "chamomile": _mat_chamomile, "licorice": _mat_licorice, "ginger": _mat_ginger,
    "saffron": _mat_saffron,
}


# =========================================================================== generators
def star_anise(seed=0, location=(0, 0, 0), rotation=(0, 0, 0), coll=None, name=None):
    """8 (6-10) radial boat-shaped carpels, split along the top, with glossy seeds; 25-34 mm across."""
    rng = random.Random(seed)
    nc = rng.choice([7, 8, 8, 8, 8, 9])
    R = rng.uniform(0.0125, 0.0165)
    bm = bmesh.new()
    nu, nv = 26, 22
    for c in range(nc):
        a0 = 2 * math.pi * c / nc + rng.uniform(-0.08, 0.08)
        L = R * rng.uniform(0.85, 1.05)
        W = L * rng.uniform(0.34, 0.42)
        Hh = L * rng.uniform(0.40, 0.50)
        gape = rng.uniform(0.25, 0.75)              # how far the carpel has split open
        droop = rng.uniform(-0.15, 0.25)
        rings = []
        for i in range(1, nu):
            u = i / nu
            w = W * 0.5 * math.sin(math.pi * u ** 0.85) ** 0.7
            h = Hh * math.sin(math.pi * (0.12 + 0.88 * u)) ** 0.55
            beak = 0.25 * Hh * max(0.0, (u - 0.75) / 0.25) ** 2      # tip curls up
            zc = h * 0.5 + beak - droop * Hh * u * u
            ring = []
            for j in range(nv):
                ph = 2 * math.pi * j / nv
                yy = w * math.cos(ph)
                zz = 0.5 * h * math.sin(ph)
                top = math.exp(-((ph - math.pi / 2) / 0.45) ** 2)       # suture groove on top
                zz -= top * h * (0.35 + 0.35 * gape) * math.sin(math.pi * u) ** 0.5
                yy *= 1 + 0.25 * gape * top
                x = L * u
                p = Vector((x, yy, zz + zc))
                d = _noise3(p, 900.0, seed + c, 3) * 0.00025 + _noise3(p, 250.0, seed + c, 2) * 0.0003
                p += Vector((0, math.cos(ph), math.sin(ph))) * d
                ring.append(Matrix.Rotation(a0, 3, "Z") @ p)
            rings.append(ring)
        tip = Matrix.Rotation(a0, 3, "Z") @ Vector((L * 1.02, 0, Hh * 0.25 + 0.25 * Hh - droop * Hh))
        base = Matrix.Rotation(a0, 3, "Z") @ Vector((0.0, 0, Hh * 0.35))
        _grid_bm(rings, cap0=base, cap1=tip, bm=bm, mat=0)
        # seed in the open suture
        if gape > 0.35:
            sc = Matrix.Rotation(a0, 3, "Z") @ Vector((L * 0.5, 0, Hh * (0.55 - 0.18 * gape) + 0.5 * Hh * 0.5 - droop * Hh * 0.25))
            ret = bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=8, radius=1.0)
            sv = ret["verts"]
            M_ = Matrix.Translation(sc) @ Matrix.Rotation(a0, 4, "Z") @ Matrix.Diagonal((L * 0.22, W * 0.24, W * 0.2, 1.0))
            bmesh.ops.transform(bm, matrix=M_, verts=sv)
            for f in {f for v in sv for f in v.link_faces}:
                f.material_index = 1
    # central column + stalk stub
    ret = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=R * 0.16, radius2=R * 0.10, depth=R * 0.55)
    bmesh.ops.translate(bm, verts=ret["verts"], vec=(0, 0, R * 0.12))
    ob = _obj_from_bmesh(name or f"StarAnise_{seed}", bm, coll)
    return _finish(ob, _mat("star_anise"), location, rotation)


def cinnamon(seed=0, location=(0, 0, 0), rotation=(0, 0, 0), coll=None, name=None):
    """Cassia-style quill: bark sheet rolled 1.2-1.9 turns, 45-75 mm long, ~1.2 mm thick, broken ends."""
    rng = random.Random(seed)
    L = rng.uniform(0.045, 0.075)
    r0 = rng.uniform(0.0050, 0.0068)
    turns = rng.uniform(1.15, 1.9)
    th_t = rng.uniform(0.0006, 0.0010)
    double = rng.random() < 0.35            # scroll rolled from both edges
    nu, nv = 40, 70
    bend = rng.uniform(-0.04, 0.04)
    grid = []
    jag0 = [rng.uniform(0, 0.004) for _ in range(nv + 1)]
    jag1 = [rng.uniform(0, 0.005) for _ in range(nv + 1)]
    for k in range(1, nv):   # smooth the jags a little
        jag0[k] = (jag0[k - 1] + 2 * jag0[k] + jag0[k + 1]) / 4
        jag1[k] = (jag1[k - 1] + 2 * jag1[k] + jag1[k + 1]) / 4
    for i in range(nu + 1):
        row = []
        for j in range(nv + 1):
            v = j / nv
            if double:
                s = (v - 0.5) * 2
                th = abs(s) * turns * math.pi
                rr = r0 * (1 - 0.32 * abs(s) * turns / 1.6)
                sign = 1 if s >= 0 else -1
                y, z = sign * rr * math.sin(th) * 0.92, rr * math.cos(th) - r0 * 0.15
                y += sign * r0 * 0.55
            else:
                th = v * turns * 2 * math.pi
                rr = r0 * (1 - 0.15 * v * turns)
                y, z = rr * math.cos(th), rr * math.sin(th)
            u = i / nu
            x = jag0[j] + (L - jag1[j] - jag0[j]) * u
            z += bend * (x - L / 2) ** 2 / L
            p = Vector((x, y, z))
            p += Vector((0, y, z)).normalized() * (_noise3(p, 180.0, seed, 2) * 0.0003) if (y * y + z * z) > 0 else Vector()
            row.append(p)
        grid.append(row)
    bm = bmesh.new()
    V = [[bm.verts.new(tuple(p)) for p in row] for row in grid]
    for i in range(nu):
        for j in range(nv):
            bm.faces.new((V[i][j], V[i][j + 1], V[i + 1][j + 1], V[i + 1][j]))
    ob = _obj_from_bmesh(name or f"Cinnamon_{seed}", bm, coll, recalc=False)
    sol = ob.modifiers.new("solidify", "SOLIDIFY")
    sol.thickness = th_t
    sol.offset = -1.0
    sol.use_rim = True
    sol.use_even_offset = True
    sol.material_offset = 1
    sol.material_offset_rim = 2
    for m in _mat("cinnamon"):
        ob.data.materials.append(m)
    _apply_mods(ob)
    ob.data.shade_smooth()
    _center_origin(ob)
    ob.location, ob.rotation_euler = location, rotation
    return ob


def cardamom(seed=0, location=(0, 0, 0), rotation=(0, 0, 0), coll=None, name=None):
    """Green cardamom pod: three-lobed ellipsoid 12-18 mm with fine ridges, pointed tip, stalk stub."""
    rng = random.Random(seed)
    L = rng.uniform(0.012, 0.018)
    R = L * rng.uniform(0.26, 0.33)
    lobe = rng.uniform(0.08, 0.16)
    rot = rng.uniform(0, 2)
    nu, nv = 30, 81
    rings = []
    for i in range(1, nu):
        u = i / nu
        rr = R * math.sin(math.pi * u) ** 0.75 * (1 - 0.18 * u)
        ring = []
        for j in range(nv):
            ph = 2 * math.pi * j / nv
            f = 1 + lobe * math.cos(3 * ph + rot) + 0.04 * math.cos(27 * ph) * math.sin(math.pi * u)
            p = Vector((L * u - L / 2, rr * f * math.cos(ph), rr * f * math.sin(ph)))
            p += Vector((0, math.cos(ph), math.sin(ph))) * _noise3(p, 500.0, seed, 2) * 0.00025
            ring.append(p)
        rings.append(ring)
    bm = _grid_bm(rings, cap0=(-L / 2 - 0.0006, 0, 0), cap1=(L / 2 + 0.0012, 0, 0))
    ret = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.0006, radius2=0.0004, depth=0.0016)
    bmesh.ops.rotate(bm, verts=ret["verts"], matrix=Matrix.Rotation(math.pi / 2, 3, "Y"), cent=(0, 0, 0))
    bmesh.ops.translate(bm, verts=ret["verts"], vec=(-L / 2 - 0.0012, 0, 0))
    ob = _obj_from_bmesh(name or f"Cardamom_{seed}", bm, coll)
    return _finish(ob, _mat("cardamom"), location, rotation)


def juniper(seed=0, location=(0, 0, 0), rotation=(0, 0, 0), coll=None, name=None):
    """Juniper berry 6-9 mm, blue-black with waxy bloom, three-rayed scar on top, stem nub, some wrinkled."""
    rng = random.Random(seed)
    R = rng.uniform(0.0030, 0.0045)
    wr = 0.015 + rng.random() * 0.07              # wrinkling from drying
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=26, radius=R)
    for v in bm.verts:
        p = v.co.copy()
        n = p.normalized()
        d = _noise3(p, 300.0, seed, 3) * R * 0.06 + _noise3(p, 1100.0, seed, 3) * R * wr \
            + _noise3(p, 2600.0, seed + 3, 2) * R * wr * 0.4
        top = max(0.0, n.z)
        az = math.atan2(n.y, n.x)
        groove = math.exp(-(math.sin(1.5 * (az + seed)) / 0.25) ** 2) * math.exp(-((1 - top) / 0.18) ** 2)
        d -= groove * R * 0.06 + math.exp(-((1 - top) / 0.03) ** 2) * R * 0.05
        if n.z < -0.9:
            d += R * 0.08 * (n.z + 0.9) / -0.1     # stem nub
        v.co = p + n * d
    ob = _obj_from_bmesh(name or f"Juniper_{seed}", bm, coll)
    ob.scale = (1.0, rng.uniform(0.95, 1.05), rng.uniform(0.9, 1.0))
    return _finish(ob, _mat("juniper"), location, rotation)


def orange_peel(seed=0, location=(0, 0, 0), rotation=(0, 0, 0), coll=None, name=None):
    """Dried bitter-orange peel: curled irregular strip 40-70 x 14-24 mm, 2-3.5 mm thick, pores, white pith."""
    rng = random.Random(seed)
    L = rng.uniform(0.040, 0.068)
    W = rng.uniform(0.014, 0.024)
    thick = rng.uniform(0.002, 0.0035)
    curl = rng.uniform(1.6, 2.8) / 0.03          # bending around the long axis (1/m)
    roll = rng.uniform(-0.6, 0.6) / 0.05         # bending along the length
    twist = rng.uniform(-0.8, 0.8)
    nu, nv = 44, 18
    grid = []
    for i in range(nu + 1):
        u = i / nu
        x = (u - 0.5) * L
        half = W * 0.5 * (math.sin(math.pi * u) ** 0.35) * (1 + 0.15 * _noise3((x, 0, 0), 60.0, seed, 2))
        row = []
        for j in range(nv + 1):
            s = (j / nv - 0.5) * 2
            yy = s * max(half, 0.0012)
            # curl around X (peel came from a sphere) and along X
            a = yy * curl
            y = math.sin(a) / curl if curl else yy
            z = (1 - math.cos(a)) / curl if curl else 0.0
            b = x * roll
            xx = math.sin(b) / roll if roll else x
            z += (1 - math.cos(b)) / roll if roll else 0.0
            p = Vector((xx, y, z))
            p = Matrix.Rotation(twist * x / L, 3, "X") @ p
            p.z += _noise3(p, 120.0, seed, 2) * 0.0007
            row.append(p)
        grid.append(row)
    bm = bmesh.new()
    V = [[bm.verts.new(tuple(p)) for p in row] for row in grid]
    for i in range(nu):
        for j in range(nv):
            bm.faces.new((V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1]))
    ob = _obj_from_bmesh(name or f"OrangePeel_{seed}", bm, coll, recalc=False)
    sol = ob.modifiers.new("solidify", "SOLIDIFY")
    sol.thickness = thick
    sol.offset = 1.0
    sol.use_rim = True
    sol.use_even_offset = True
    sol.material_offset = 1
    sol.material_offset_rim = 2
    for m in _mat("orange_peel"):
        ob.data.materials.append(m)
    _apply_mods(ob)
    ob.data.shade_smooth()
    _center_origin(ob)
    ob.location, ob.rotation_euler = location, rotation
    return ob


def chamomile(seed=0, location=(0, 0, 0), rotation=(0, 0, 0), coll=None, name=None):
    """Dried chamomile head: golden conical disc 6-9 mm with florets, 12-20 shrivelled ivory petals, stem stub."""
    rng = random.Random(seed)
    Rd = rng.uniform(0.003, 0.0045)
    Hd = Rd * rng.uniform(0.7, 1.1)
    bm = bmesh.new()
    # disc (dome): rings from rim to apex
    nv = 24
    rings = []
    for i in range(0, 10):
        u = i / 10
        rr = Rd * math.cos(u * math.pi / 2) ** 0.8
        z = Hd * math.sin(u * math.pi / 2) ** 1.3
        ring = []
        for j in range(nv):
            ph = 2 * math.pi * j / nv
            p = Vector((rr * math.cos(ph), rr * math.sin(ph), z))
            p.z += _noise3(p, 2000.0, seed, 1) * 0.00012
            ring.append(p)
        rings.append(ring)
    _grid_bm(rings, cap0=(0, 0, -Hd * 0.25), cap1=(0, 0, Hd * 1.02), bm=bm, mat=0)
    # petals: thin curled strips (two-sided via solidify later is costly; use a thin closed slab)
    npet = rng.randint(12, 20)
    for k in range(npet):
        a = 2 * math.pi * k / npet + rng.uniform(-0.1, 0.1)
        pl = rng.uniform(0.0045, 0.007) * (0.6 if rng.random() < 0.25 else 1.0)   # some broken
        pw = rng.uniform(0.0013, 0.002)
        droop = rng.uniform(0.6, 1.6)
        curl = rng.uniform(-0.6, 0.6)
        segs = 8
        top, bot = [], []
        for i in range(segs + 1):
            u = i / segs
            ang = -droop * u
            x = Rd * 0.85 + pl * u * math.cos(droop * u * 0.6)
            z = Hd * 0.05 + pl * math.sin(ang * 0.6) * u
            w = pw * 0.5 * (math.sin(math.pi * (0.15 + 0.85 * u)) ** 0.5) * (1 - 0.2 * u)
            for sgn, lst in ((1, top), (-1, bot)):
                rowp = []
                for s in (-1, 0, 1):
                    yy = s * w
                    zz = z + abs(s) * curl * w * 0.6 + sgn * 0.00006
                    p = Matrix.Rotation(a, 3, "Z") @ Vector((x, yy, zz))
                    rowp.append(p)
                lst.append(rowp)
        Vt = [[bm.verts.new(tuple(p)) for p in r] for r in top]
        Vb = [[bm.verts.new(tuple(p)) for p in r] for r in bot]
        for i in range(segs):
            for j in range(2):
                f = bm.faces.new((Vt[i][j], Vt[i][j + 1], Vt[i + 1][j + 1], Vt[i + 1][j]))
                f.material_index = 1
                f = bm.faces.new((Vb[i][j + 1], Vb[i][j], Vb[i + 1][j], Vb[i + 1][j + 1]))
                f.material_index = 1
        for i in range(segs):   # side walls
            for j0 in (0, 2):
                f = bm.faces.new((Vt[i][j0], Vt[i + 1][j0], Vb[i + 1][j0], Vb[i][j0]))
                f.material_index = 1
        f = bm.faces.new((Vt[-1][0], Vt[-1][1], Vt[-1][2], Vb[-1][2], Vb[-1][1], Vb[-1][0]))
        f.material_index = 1
    ret = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.0006, radius2=0.0005,
                                depth=rng.uniform(0.002, 0.006))
    bmesh.ops.translate(bm, verts=ret["verts"], vec=(0, 0, -Hd * 0.25 - 0.001))
    for f in {f for v in ret["verts"] for f in v.link_faces}:
        f.material_index = 2
    ob = _obj_from_bmesh(name or f"Chamomile_{seed}", bm, coll, recalc=False)
    return _finish(ob, _mat("chamomile"), location, rotation)


def licorice(seed=0, location=(0, 0, 0), rotation=(0, 0, 0), coll=None, name=None):
    """Cut licorice root: 6-12 mm thick, 18-45 mm long, fibrous wrinkled bark, yellow fibrous cut ends."""
    rng = random.Random(seed)
    L = rng.uniform(0.018, 0.045)
    R = rng.uniform(0.003, 0.006)
    bend = rng.uniform(-0.15, 0.15)
    nu, nv = 30, 28
    cut0, cut1 = rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5)
    rings = []
    for i in range(nu + 1):
        u = i / nu
        ring = []
        for j in range(nv):
            ph = 2 * math.pi * j / nv
            y, z = R * math.cos(ph), R * math.sin(ph)
            x = (u - 0.5) * L + (cut0 * y if i == 0 else 0) + (cut1 * y if i == nu else 0)
            p = Vector((x, y, z))
            d = _noise3(Vector((x * 0.15, y, z)), 900.0, seed, 3) * R * 0.08 + 0.04 * R * math.sin(13 * ph + seed)
            if 0 < i < nu:
                p += Vector((0, math.cos(ph), math.sin(ph))) * d
            p.z += bend * (x * x) / L
            ring.append(p)
        rings.append(ring)
    bm = bmesh.new()
    _grid_bm(rings, bm=bm, mat=0)
    for ring_i in (0, nu):
        vs = [v for v in bm.verts][ring_i * nv:(ring_i + 1) * nv]
        f = bm.faces.new(vs if ring_i else list(reversed(vs)))
        f.material_index = 1
    ob = _obj_from_bmesh(name or f"Licorice_{seed}", bm, coll)
    bev = ob.modifiers.new("bevel", "BEVEL")
    bev.width = 0.0004
    bev.segments = 2
    bev.limit_method = "ANGLE"
    for m in _mat("licorice"):
        ob.data.materials.append(m)
    _apply_mods(ob)
    ob.data.shade_smooth()
    _center_origin(ob)
    ob.location, ob.rotation_euler = location, rotation
    return ob


def ginger(seed=0, location=(0, 0, 0), rotation=(0, 0, 0), coll=None, name=None):
    """Dried ginger slice: irregular oval 25-40 mm, 2-3.5 mm thick, warped, brown skin edge."""
    rng = random.Random(seed)
    a, b = rng.uniform(0.012, 0.02), rng.uniform(0.009, 0.014)
    th = rng.uniform(0.002, 0.0035)
    n = 64
    nr = 10
    warp = rng.uniform(0.0012, 0.0028)
    bm = bmesh.new()
    outline = []
    for j in range(n):
        ph = 2 * math.pi * j / n
        f = 1 + 0.16 * _noise3((math.cos(ph), math.sin(ph), 0), 1.6, seed, 2) + 0.06 * math.sin(3 * ph + seed) \
            + 0.03 * _noise3((math.cos(ph), math.sin(ph), 5), 9.0, seed, 2)
        outline.append((a * f * math.cos(ph), b * f * math.sin(ph)))

    def zf(x, y, top):
        w = warp * _noise3((x, y, 0), 70.0, seed, 2) + 0.00035 * _noise3((x, y, 1), 500.0, seed, 2) \
            + 0.00012 * _noise3((x * 0.3, y * 3.0, 2), 2500.0, seed, 1)
        return w + (th / 2 if top else -th / 2) * (1 - 0.2 * _noise3((x, y, 3), 200.0, seed, 1))
    tops, bots = [], []
    for k in range(1, nr + 1):
        s = k / nr
        tops.append([Vector((x * s, y * s, zf(x * s, y * s, True))) for x, y in outline])
        bots.append([Vector((x * s, y * s, zf(x * s, y * s, False))) for x, y in outline])
    _grid_bm(tops, cap0=Vector((0, 0, zf(0, 0, True))), bm=bm, mat=0)
    _grid_bm(bots, cap0=Vector((0, 0, zf(0, 0, False))), bm=bm, mat=0)
    # skin edge: join the outermost rings (ring verts come first, then the pole, per surface)
    bm.verts.ensure_lookup_table()
    nt = nr * n + 1
    top_edge = [bm.verts[(nr - 1) * n + j] for j in range(n)]
    bot_edge = [bm.verts[nt + (nr - 1) * n + j] for j in range(n)]
    for j in range(n):
        k = (j + 1) % n
        f = bm.faces.new((top_edge[j], bot_edge[j], bot_edge[k], top_edge[k]))
        f.material_index = 1
    ob = _obj_from_bmesh(name or f"Ginger_{seed}", bm, coll)
    return _finish(ob, _mat("ginger"), location, rotation)


def saffron(seed=0, location=(0, 0, 0), rotation=(0, 0, 0), coll=None, name=None, path=None):
    """One saffron stigma: 18-30 mm thread, ~0.4 mm thick, flaring to a 1.5-2 mm frilled trumpet.
    path: optional list of points to follow (e.g. draped over a heap); else a random gentle curve."""
    rng = random.Random(seed)
    L = rng.uniform(0.018, 0.030)
    ns, nv = 40, 8
    if path is None:
        pts = []
        d = Vector((1, 0, 0))
        p = Vector((0, 0, 0))
        for i in range(ns + 1):
            pts.append(p.copy())
            d = (Matrix.Rotation(rng.gauss(0, 0.12), 3, "Z") @ Matrix.Rotation(rng.gauss(0, 0.05), 3, "Y") @ d).normalized()
            p = p + d * (L / ns)
    else:
        pts = [Vector(q) for q in path]
        ns = len(pts) - 1
    style = rng.random() < 0.35
    bm = bmesh.new()
    rings = []
    for i, p in enumerate(pts):
        u = i / ns
        tvec = (pts[min(i + 1, ns)] - pts[max(i - 1, 0)]).normalized()
        nvec = tvec.cross(Vector((0, 0, 1)))
        if nvec.length < 1e-6:
            nvec = Vector((1, 0, 0))
        nvec.normalize()
        bvec = tvec.cross(nvec)
        r = 0.00024 + 0.00055 * max(0.0, (u - 0.72) / 0.28) ** 1.8
        ring = []
        for j in range(nv):
            ph = 2 * math.pi * j / nv
            frill = 1 + (0.25 * math.sin(5 * ph + seed) if u > 0.9 else 0)
            fl = 0.55 if u < 0.9 else 0.8                       # flattened ribbon
            ring.append(p + (nvec * math.cos(ph) + bvec * math.sin(ph) * fl) * r * frill)
        rings.append(ring)
    _grid_bm(rings, cap0=pts[0] - (pts[1] - pts[0]) * 0.3, cap1="fill", bm=bm, mat=0)
    if style:
        for f in bm.faces:
            c = f.calc_center_median()
            if (c - pts[0]).length < L * 0.12:
                f.material_index = 1
    ob = _obj_from_bmesh(name or f"Saffron_{seed}", bm, coll)
    c = _center_origin(ob)
    ob = _finish(ob, _mat("saffron"), location, rotation)
    if path is not None:     # path was in world space: keep the geometry where it was draped
        ob.location = Vector(location) + c
    return ob


GENERATORS = {"star_anise": star_anise, "cinnamon": cinnamon, "cardamom": cardamom, "juniper": juniper,
              "orange_peel": orange_peel, "chamomile": chamomile, "licorice": licorice, "ginger": ginger,
              "saffron": saffron}


def make(kind, seed=0, **kw):
    """Generate one botanical by kind name."""
    return GENERATORS[kind](seed=seed, **kw)


# =========================================================================== heaps
DEFAULT_COUNTS = {"star_anise": 6, "cinnamon": 3, "cardamom": 14, "juniper": 24, "orange_peel": 3, "chamomile": 9,
                  "licorice": 5, "ginger": 3, "saffron": 18}


REST = {   # natural resting orientation per kind: (x-roll choices, y-tilt sigma, upside-down chance)
    "star_anise": ("flat", 0.12, 0.3), "cinnamon": ("roll", 0.05, 0.0), "cardamom": ("roll", 0.1, 0.0),
    "juniper": ("any", 0.0, 0.0), "orange_peel": ("flat", 0.25, 0.12), "chamomile": ("flat", 0.6, 0.25),
    "licorice": ("roll", 0.06, 0.0), "ginger": ("flat", 0.15, 0.5),
}


def _rest_rotation(kind, rng):
    mode, tilt, flip = REST.get(kind, ("any", 0.0, 0.0))
    yaw = rng.uniform(0, 2 * math.pi)
    if mode == "any":
        return (rng.uniform(0, 6.28), rng.uniform(0, 6.28), yaw)
    if mode == "roll":
        return (rng.uniform(0, 2 * math.pi), rng.gauss(0, tilt), yaw)
    return ((math.pi if rng.random() < flip else 0.0) + rng.gauss(0, tilt), rng.gauss(0, tilt), yaw)


def heap(center=(0, 0, 0), radius=0.045, counts=None, seed=0, coll=None, settle=True, frames=40, floor_z=None,
         scale_sim=10.0, spread=0.32, height=None, repose_deg=33.0, n_crumbs=450):
    """A settled pile of botanicals on a surface at center z (or floor_z).  Returns list of objects.
    1) items (largest first) are stacked one by one: each gets its natural resting orientation and is
       lowered by ray casting onto the table / the items already placed (gaussian positions, sigma =
       spread * radius), sliding outwards until it sits under a cone of `height` and `repose_deg`;  2) a short Bullet settle (convex hulls, 10x scale, high friction) lets them
       slump into stable contact;  3) saffron threads are draped on top by ray casting.
    Existing mesh objects flagged obj['collider'] = True act as passive colliders in the settle."""
    counts = counts or DEFAULT_COUNTS
    rng = random.Random(seed)
    height = height if height is not None else radius * 0.7
    repose = math.tan(math.radians(repose_deg))
    cx, cy, cz = center
    fz = cz if floor_z is None else floor_z
    coll = coll or S.collection("Botanicals")
    order = []
    for k, n in counts.items():
        if k != "saffron":
            order += [k] * n
    rng.shuffle(order)
    size_rank = {"orange_peel": 0, "cinnamon": 1, "ginger": 2, "licorice": 3, "star_anise": 4, "chamomile": 5,
                 "cardamom": 6, "juniper": 7}
    order.sort(key=lambda k: size_rank.get(k, 8) + rng.random() * 3.0)
    items = []
    sc = bpy.context.scene
    for i, k in enumerate(order):
        ob = make(k, seed=seed * 1000 + i, location=(cx, cy, fz + 2.0), rotation=_rest_rotation(k, rng), coll=coll)
        ob["botanical"] = k
        r = abs(rng.gauss(0, spread * radius))
        a = rng.uniform(0, 2 * math.pi)
        for attempt in range(40):          # slide outwards until it sits under the angle of repose
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            ob.location = (x, y, fz + 2.0)
            bpy.context.view_layer.update()
            _drop_onto(ob, fz, sc, rng)
            top = max((ob.matrix_world @ Vector(c)).z for c in ob.bound_box) - fz
            if top <= height - r * repose + 0.004 or r > radius * 1.6:
                break
            r += 0.003
        items.append(ob)
    if settle:
        _settle(items, fz, (cx, cy), radius, frames, scale_sim)
    ns = counts.get("saffron", 0)
    if ns:
        items += drape_saffron(items, ns, center=(cx, cy), radius=radius * 0.75, seed=seed + 99, coll=coll, floor_z=fz)
    if n_crumbs:
        items.append(crumbs((cx, cy, fz), radius * 1.4, n_crumbs, seed + 7, coll, fz))
    return items


def _drop_onto(ob, floor_z, sc, rng, samples=80, gap=0.0002):
    """Lower `ob` (currently high above the scene) straight down until it rests on whatever is below."""
    dg = bpy.context.evaluated_depsgraph_get()
    mw = ob.matrix_world.copy()
    verts = ob.data.vertices
    idx = range(len(verts)) if len(verts) <= samples else rng.sample(range(len(verts)), samples)
    lift = -1e9
    for i in idx:
        w = mw @ verts[i].co
        hit, loc, nrm, fi, hob, hmw = sc.ray_cast(dg, Vector((w.x, w.y, floor_z + 0.6)), Vector((0, 0, -1)))
        surf = loc.z if hit else floor_z
        lift = max(lift, surf - (w.z - ob.location.z))
    ob.location.z = lift + gap
    bpy.context.view_layer.update()


def _settle(items, floor_z, center, radius, frames, k):
    """Bullet settle at k x scale (small objects are unstable at true scale), then freeze."""
    sc = bpy.context.scene
    saved = sc.frame_current
    if sc.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    rbw = sc.rigidbody_world
    rbw.substeps_per_frame = 20
    rbw.solver_iterations = 30
    rbw.point_cache.frame_start = 1
    rbw.point_cache.frame_end = frames + 1
    # floor (+ low rim so nothing rolls off the table forever)
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    floor = bpy.context.object
    floor.name = "_settle_floor"
    floor.scale = (radius * 8 * k, radius * 8 * k, 0.02 * k)
    floor.location = (center[0] * k, center[1] * k, floor_z * k - 0.01 * k)
    temp = [floor]
    colliders = [o for o in bpy.data.objects if o.get("collider")]
    orig = {}
    for ob in items + colliders:
        orig[ob.name] = (ob.location.copy(), ob.scale.copy())
        ob.location = ob.location * k
        ob.scale = ob.scale * k
    for ob, kind in [(floor, "PASSIVE")] + [(o, "PASSIVE") for o in colliders] + [(o, "ACTIVE") for o in items]:
        with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
            bpy.ops.rigidbody.object_add(type=kind)
        rb = ob.rigid_body
        rb.collision_shape = "BOX" if ob is floor else ("MESH" if kind == "PASSIVE" else "CONVEX_HULL")
        rb.friction = 1.0
        rb.restitution = 0.05
        rb.use_margin = True
        rb.collision_margin = 0.0004 * k
        if kind == "ACTIVE":
            rb.mass = 0.002 * k ** 3
            rb.linear_damping = 0.6
            rb.angular_damping = 0.85
    for f in range(1, frames + 2):
        sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    mats = {ob.name: ob.evaluated_get(dg).matrix_world.copy() for ob in items}
    for ob in items + colliders:
        with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
            bpy.ops.rigidbody.object_remove()
    for ob in items:
        mw = mats[ob.name]
        loc, rot, scl = mw.decompose()
        ob.location = loc / k
        ob.rotation_mode = "QUATERNION"
        ob.rotation_quaternion = rot
        ob.rotation_mode = "XYZ"
        ob.scale = scl / k
    for ob in colliders:
        ob.location, ob.scale = orig[ob.name]
    for ob in temp:
        bpy.data.objects.remove(ob, do_unlink=True)
    bpy.ops.rigidbody.world_remove()
    sc.frame_set(saved)


def crumbs(center=(0, 0, 0), radius=0.06, n=400, seed=0, coll=None, floor_z=None):
    """Botanical debris around a heap: tiny broken bits (0.4-2.5 mm) of bark, seed and petal, dropped by
    ray casting onto the table/heap and instanced from a few rough templates (GN instancer)."""
    import props as P
    rng = random.Random(seed)
    cx, cy, cz = center
    fz = cz if floor_z is None else floor_z
    tc = bpy.data.collections.get("OYOS_CrumbTemplates")
    if tc is None or not len(tc.objects):
        tc = S.collection("OYOS_CrumbTemplates")
        tc.hide_render = True
        mats = [_mat("cinnamon")[0], _mat("star_anise")[0], _mat("star_anise")[1], _mat("cardamom")[0],
                _mat("orange_peel")[1], _mat("chamomile")[1]]
        for i, m in enumerate(mats):
            bm = bmesh.new()
            bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
            for v in bm.verts:
                v.co += v.co.normalized() * _noise3(v.co, 1.7, i * 7, 2) * 0.45
                v.co.z *= 0.45 if i in (0, 4, 5) else 0.8      # flakes vs grains
            ob = _obj_from_bmesh(f"crumb_t{i}", bm, tc)
            ob.data.materials.append(m)
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    Pp, ROT, SCL, IDX = [], [], [], []
    for i in range(n):
        r = radius * math.sqrt(rng.random())
        a = rng.uniform(0, 2 * math.pi)
        x, y = cx + r * math.cos(a), cy + r * math.sin(a)
        hit, loc, nrm, fi, hob, hmw = sc.ray_cast(dg, Vector((x, y, fz + 0.5)), Vector((0, 0, -1)))
        z = loc.z if hit else fz
        s_ = 0.0002 + 0.0011 * rng.random() ** 2.2
        Pp.append((x, y, z + s_ * 0.3))
        ROT.append((rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), rng.uniform(0, 6.28)))
        SCL.append((s_ * rng.uniform(0.7, 1.6), s_ * rng.uniform(0.7, 1.3), s_))
        IDX.append(rng.randrange(6))
    return P.instanced_points("BotanicalCrumbs", Pp, ROT, SCL, IDX, tc, coll)


def drape_saffron(items, n, center, radius, seed=0, coll=None, floor_z=0.0):
    """Lay n saffron threads on top of the settled items by ray casting straight down."""
    rng = random.Random(seed)
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for i in range(n):
        a = rng.uniform(0, 2 * math.pi)
        if rng.random() < 0.4:            # some fell off the heap onto the table around it
            r = radius * rng.uniform(0.9, 1.5)
        else:
            r = radius * math.sqrt(rng.random())
        p0 = Vector((center[0] + r * math.cos(a), center[1] + r * math.sin(a), 0))
        d = Vector((math.cos(rng.uniform(0, 6.28)), math.sin(rng.uniform(0, 6.28)), 0)).normalized()
        L = rng.uniform(0.012, 0.022)
        bend = rng.gauss(0, 0.08)
        pts, surf = [], []
        q = p0.copy()
        for k in range(25):
            hit, loc, nrm, idx, ob, mw = sc.ray_cast(dg, Vector((q.x, q.y, floor_z + 0.3)), Vector((0, 0, -1)))
            z = loc.z if hit else floor_z
            surf.append(z + 0.0003)
            pts.append(Vector((q.x, q.y, z + 0.0003)))
            d = (Matrix.Rotation(bend + rng.gauss(0, 0.16), 3, "Z") @ d).normalized()
            q = q + d * (L / 24)
        # light thread: drapes into dips, may bridge at most ~1.2 mm above the surface
        zs = [p.z for p in pts]
        for _ in range(3):
            zs = [zs[0]] + [(zs[j - 1] + zs[j] + zs[j + 1]) / 3 for j in range(1, len(zs) - 1)] + [zs[-1]]
            zs = [min(max(z, sz), sz + 0.0012) for z, sz in zip(zs, surf)]
        pts = [Vector((p.x, p.y, z)) for p, z in zip(pts, zs)]
        out.append(saffron(seed=seed * 100 + i, coll=coll, path=pts))
    return out
