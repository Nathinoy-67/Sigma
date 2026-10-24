"""S04 MACERATION TIME-LAPSE (film frames 180-225, 45 local frames, rendered on twos).

85 mm at f/4, locked off on the shoulder of a tall maceration jar by the window.  A linen bag of botanicals hangs
on a string in clear spirit.  Three days flicker past in under two seconds: the window-bar shadows swing across the
bench, two brief blue nights, and the spirit deepens from clear to amber to dark mahogany.  Real time-lapse
exposure flicker (per-frame jitter of the sun).
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

FRAMES = 45
STEP = 2                          # time-lapse: render on twos
PRESET = "glass"
JAR = Vector((-0.30, 0.10, 0.0))

# time of day per frame: (day index, phase 0..1 within daylight) or night
#   day 1: f0-13, night f14-17, day 2: f18-31, night f32-35, day 3: f36-44
SCHEDULE = [(0, 14), (18, 32), (36, 50)]


def time_at(f):
    """('day', u) with u = 0 (sunrise) .. 1 (sunset) or ('night', v)."""
    for a, b in SCHEDULE:
        if a <= f < b:
            return "day", (f - a) / (b - a - 1)
    return "night", 0.0


def jar(coll, seed=3):
    """Tall cylindrical maceration jar: 300 mm, 180 mm across, 4.5 mm wall, thick base, wide rolled lip."""
    H, R, t, Bz = 0.30, 0.09, 0.0045, 0.012
    outer = [(0.0, 0.0015), (R - 0.02, 0.0), (R - 0.004, 0.0), (R, 0.006), (R, H - 0.03), (R - 0.004, H - 0.012),
             (R - 0.004, H - 0.004)]
    outer, ot = P.fillet(outer, [0, 0.01, 0.003, 0.004, 0.012, 0.004, 0], steps=6)
    lip = [(R - 0.004 + 0.003 * math.cos(a), H - 0.004 + 0.003 * math.sin(a)) for a in np.linspace(0, math.pi, 9)[1:-1]]
    inner_dn = [(R - 0.004 - 0.006, H - 0.004), (R - t - 0.004, H - 0.03), (R - t, H - 0.04), (R - t, Bz + 0.004),
                (0.0, Bz)]
    inner_dn, it = P.fillet(inner_dn, [0, 0.01, 0.008, 0.008, 0], steps=8)
    prof = outer + lip + inner_dn
    tags = ot + [0.5] * len(lip) + [1] * len(inner_dn)
    prof, tags = P.resample(prof, 0.004, tags)
    g = P.lathe("Jar_glass", prof, 160, tags, coll, wobble=0.004, seed=seed)
    g.location = JAR
    g.data.materials.append(M.glass("JarGlass", smudge=0.18, radius=R, seed=seed, wavy=0.08,
                                    absorb=(0.92, 0.97, 0.94), density=2.0))
    fill_z = 0.235
    lp = P._liquid_profile(list(reversed(inner_dn)), fill_z, meniscus=0.0018, men_len=0.002)
    lq = P.lathe("Jar_spirit", lp, 160, coll=coll, wobble=0.004, seed=seed)
    lq.location = JAR
    return g, lq, fill_z


def spirit_material():
    """Spirit whose absorption is keyed: near clear -> amber -> mahogany (Volume Absorption colour + density)."""
    m, t = M.new_material("Spirit")
    bsdf = M._shadow_mix(t, t.principled(base=(1, 1, 1), transmission=1.0, rough=0.0, ior=1.36), (1, 1, 1))
    va = t.node("ShaderNodeVolumeAbsorption", {"Color": (0.98, 0.97, 0.9), "Density": 1.0})
    sc = t.node("ShaderNodeVolumeScatter", {"Color": (0.9, 0.7, 0.4), "Density": 0.0, "Anisotropy": 0.5})
    t.output(bsdf, t.add_shader(va, sc))
    keys = [(0, (0.98, 0.96, 0.86), 2.0, 0.0), (14, (0.95, 0.82, 0.55), 5.0, 0.05), (24, (0.85, 0.52, 0.22), 9.0, 0.12),
            (34, (0.62, 0.26, 0.09), 16.0, 0.2), (44, (0.45, 0.13, 0.04), 30.0, 0.25)]
    for f, c, d, scd in keys:
        va.inputs["Color"].default_value = (*c, 1)
        va.inputs["Density"].default_value = d
        sc.inputs["Density"].default_value = scd
        va.inputs["Color"].keyframe_insert("default_value", frame=f)
        va.inputs["Density"].keyframe_insert("default_value", frame=f)
        sc.inputs["Density"].keyframe_insert("default_value", frame=f)
    return m


def mn_noise(a):
    from mathutils import noise as mn
    return mn.noise(Vector((math.cos(a) * 2, math.sin(a) * 2, 0.5)))


def linen_bag(coll, top, seed=5):
    """A lumpy linen sachet full of botanicals hanging from a string; gathered and tied at the neck."""
    import bmesh
    from mathutils import noise as mn
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=5, radius=1.0)
    rng = random.Random(seed)
    lumps = [(Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 0.6))).normalized(), rng.uniform(0.05, 0.14))
             for _ in range(26)]
    for v in bm.verts:
        p = v.co.copy()
        # teardrop: wide at the bottom, gathered to a neck at the top
        z = p.z
        w = 0.033 * (1.0 - 0.8 * max(0.0, z) ** 1.5) if z > 0 else 0.033 * (1.0 - 0.18 * (-z) ** 2)
        q = Vector((p.x * w, p.y * w, z * 0.042 - 0.004 * max(0.0, -z)))
        bump = sum(a * max(0.0, p.dot(d) - 0.78) * 6 for d, a in lumps)
        q += Vector((p.x, p.y, 0.3 * p.z)).normalized() * 0.006 * bump
        q += p * 0.0016 * mn.noise(p * 6 + Vector((seed, 0, 0)))
        q += p * 0.0007 * mn.noise(p * 23 + Vector((0, seed, 0)))      # cloth wrinkles
        # gathered pleats running down from the neck
        if z > -0.2:
            ang = math.atan2(p.y, p.x)
            k = ((z + 0.2) / 1.2) ** 1.5
            pl = 0.0028 * k * (math.cos(11 * ang + 0.6 * mn.noise(p * 3)) + 0.5 * math.cos(17 * ang + 1.3))
            rr = math.hypot(p.x, p.y) + 1e-6
            q.x += pl * p.x / rr
            q.y += pl * p.y / rr
        v.co = q
    me = bpy.data.meshes.new("LinenBag")
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    bag = bpy.data.objects.new("LinenBag", me)
    S.link(bag, coll)
    bag.location = top + Vector((0, 0, -0.05))
    m, t = M.new_material("Linen")
    p = t.texco("Object")
    wa = t.wave(t.mapping(p, rot=(0, 0, 0)), scale=1400.0, kind="BANDS", direction="X", distortion=0.4)
    wb = t.wave(t.mapping(p, rot=(0, 0, 0)), scale=1400.0, kind="BANDS", direction="Z", distortion=0.4)
    weave = t.math("MAXIMUM", wa, wb)
    stain = t.noise(p, scale=30.0, detail=4.0)
    col = t.mixc(t.mul(t.smooth(stain, 0.4, 0.75), 0.6), (0.62, 0.55, 0.42), (0.36, 0.26, 0.14))
    bsdf = t.principled(base=col, rough=0.85, sheen=0.4, normal=t.bump(weave, 0.4, 0.0003))
    tl = t.node("ShaderNodeBsdfTranslucent", {"Color": t.mixc(0.5, col, (0.3, 0.2, 0.1))})
    t.output(t.mix_shader(0.25, bsdf, tl))
    bag.data.materials.append(m)
    # tie + string up to the rim and over the lip
    neck = bag.location + Vector((0, 0, 0.042 + 0.002))
    twine = M.new_material("Twine")
    tw, tt = twine
    n = tt.noise(tt.mapping(tt.texco("Object"), scale=(1, 1, 8)), scale=600.0, detail=3.0)
    tt.output(tt.principled(base=tt.mixc(n, (0.42, 0.33, 0.2), (0.3, 0.22, 0.12)), rough=0.9, sheen=0.5,
                            normal=tt.bump(n, 0.6, 0.0003)))
    # the gathered cloth ends above the tie: a short ruffled flare
    import bmesh
    bm = bmesh.new()
    rings = []
    for i in range(7):
        u = i / 6
        r = 0.0045 + 0.010 * u ** 1.4
        ring = []
        for j in range(72):
            a = 2 * math.pi * j / 72
            rr = r * (1 + 0.35 * u * math.cos(13 * a + 2 * mn_noise(a)) )
            ring.append((rr * math.cos(a), rr * math.sin(a), 0.016 * u - 0.002 * u * u * math.cos(7 * a)))
        rings.append(ring)
    verts = [v for ring in rings for v in ring]
    faces = [(i * 72 + j, i * 72 + (j + 1) % 72, (i + 1) * 72 + (j + 1) % 72, (i + 1) * 72 + j) for i in range(6) for j in range(72)]
    ruff = P.mesh("BagRuffle", verts, faces, coll, True)
    ruff.location = neck - Vector((0, 0, 0.002))
    so = ruff.modifiers.new("t", "SOLIDIFY")
    so.thickness = 0.0005
    ruff.data.materials.append(m)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.0055, minor_radius=0.0012, location=neck - Vector((0, 0, 0.004)))
    tie = bpy.context.active_object
    tie.name = "BagTie"
    tie.data.materials.append(tw)
    S.link(tie, coll)
    pts = [neck, neck + Vector((0.004, -0.01, 0.05)), JAR + Vector((0.035, -0.07, 0.24)), JAR + Vector((0.05, -0.085, 0.297)),
           JAR + Vector((0.055, -0.093, 0.302)), JAR + Vector((0.058, -0.099, 0.27))]
    cu = bpy.data.curves.new("String", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.0007
    cu.bevel_resolution = 3
    sp = cu.splines.new("NURBS")
    sp.points.add(len(pts) - 1)
    for i, q in enumerate(pts):
        sp.points[i].co = (*q, 1)
    sp.use_endpoint_u = True
    sp.order_u = 3
    sob = bpy.data.objects.new("String", cu)
    S.link(sob, coll)
    sob.data.materials.append(tw)
    return bag


def build(res="look", samples=None, threshold=None, **kw):
    S.new_scene(res, PRESET, samples=samples, threshold=threshold, exposure=-0.6)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 0, FRAMES - 1
    sc.cycles.volume_bounces = 1
    coll = S.collection("S04")
    A.room(coll, floor=False, window_y=JAR.y - 0.05, exterior_strength=2.5)
    g, lq, fill_z = jar(coll)
    lq.data.materials.append(spirit_material())
    bag = linen_bag(coll, JAR + Vector((0, 0.0, 0.205)))
    # sediment: a few botanical crumbs on the jar floor
    B.crumbs((JAR.x, JAR.y, JAR.z + 0.013), 0.06, 160, seed=4, coll=coll)
    # cork lid leaning against the jar, a few botanicals on the bench
    lid = P.coaster("CorkLid", location=(JAR.x + 0.13, JAR.y - 0.05, 0.0), radius=0.07, seed=2, coll=coll)
    lid.scale = (1, 1, 4)
    B.heap(center=(JAR.x + 0.16, JAR.y - 0.13, 0.0), radius=0.03, counts={"star_anise": 4, "juniper": 18, "cardamom": 6},
           seed=31, coll=coll, n_crumbs=80)
    # sun: keyed per frame (time-lapse), sky colour and strength keyed (day warm/white, night blue)
    lights = A.dawn(target=JAR + Vector((0, 0, 0.15)), azimuth_deg=20.0, elevation_deg=12.0, strength=6.0,
                    kelvin=4200, sky_strength=1.2, bounce=0.9, coll=coll, align_window=False)
    sun, sky, bounce = lights["sun"], lights["sky"], lights.get("bounce")
    rng = random.Random(7)
    for f in range(FRAMES):
        kind, u = time_at(f)
        jitter = 1.0 + rng.uniform(-0.06, 0.06)
        if kind == "day":
            az = -5.0 + 55.0 * u
            el = 6.0 + 26.0 * math.sin(math.pi * u)
            d = A.sun_direction(az, el)
            sun.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
            sun.data.energy = 7.0 * min(1.0, math.sin(math.pi * u) * 3.0) * jitter
            warm = 1.0 - math.sin(math.pi * u)
            K = 3000 + 2600 * (1 - warm)
            sun.data.color = S.kelvin(K)
            sky.data.energy = 70.0 * (0.4 + 0.6 * math.sin(math.pi * u)) * jitter
            sky.data.color = S.kelvin(9000)
        else:
            sun.data.energy = 0.0
            sky.data.energy = 14.0 * jitter
            sky.data.color = (0.35, 0.5, 1.0)
        for ob, path in ((sun, "rotation_euler"),):
            ob.keyframe_insert(path, frame=f)
        sun.data.keyframe_insert("energy", frame=f)
        sun.data.keyframe_insert("color", frame=f)
        sky.data.keyframe_insert("energy", frame=f)
        sky.data.keyframe_insert("color", frame=f)
    for idb in (sun, sun.data, sky.data):
        for fc in C.fcurves(idb):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"
    # the night sky outside the window: dim it with the sky light (the card itself is keyed too)
    skycard = bpy.data.materials["DawnSky"].node_tree.nodes["Emission"]
    for f in range(FRAMES):
        kind, u = time_at(f)
        skycard.inputs["Strength"].default_value = 2.5 * (0.5 + 0.5 * math.sin(math.pi * u)) if kind == "day" else 0.12
        skycard.inputs["Strength"].keyframe_insert("default_value", frame=f)
    for fc in C.fcurves(bpy.data.materials["DawnSky"].node_tree):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"
    S.world((0.003, 0.0035, 0.005), 1.0)
    # camera: locked off on the jar's shoulder, window behind-left so the spirit glows
    tgt = JAR + Vector((0.0, 0.0, 0.185))
    cam_p = tgt + Vector((0.40, -0.56, 0.17))
    cam = C.add_camera("CAM_S04", lens=85, location=cam_p, target=tgt, fstop=4.0,
                       focus=JAR + Vector((0.0, -0.0, 0.18)))
    C.breathe(cam, amplitude_deg=0.01, period_frames=90, seed=4)
    return dict(cam=cam)
