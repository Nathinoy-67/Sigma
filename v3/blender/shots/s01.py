"""S01 TYPEBAR (film frames 0-75, 75 local frames).

Extreme macro of the recipe card on the typewriter platen, 100 mm at f/4, from the front-right and a little below
the typing line, so the typed header recedes into soft focus to the left.  The low dawn sun finds the card over the
first 12 frames.  On f15, f30, f45 and f60 a typebar flicks up out of the dark (motion-blurred), the ribbon vibrator
lifts the black ribbon into the typing point, and '1', '9', '3', '4' complete 'WOLFENBÜTTEL 1934'; one frame later
the carriage escapes one 2.54 mm step to the left.  The new glyph is a hair blacker and glossier.  6 mm
motion-control drift right with a 3 mm push.
"""
import json
import math
import os

import bpy
import numpy as np
from mathutils import Vector

import scene as S
import camera as C
import materials as M
import props as P
import workroom as A

FRAMES = 75
STRIKES = [15, 30, 45, 60]
PRESET = "default"

R = 0.016                       # platen radius
RP = R + 0.00025                # paper surface radius
T = Vector((0.0, 0.0, 0.13))    # typing point (front of the platen), workroom coordinates
LAYOUT = json.load(open(os.path.join(S.TEXTURES, "card_layout.json")))
CARD_W, CARD_H = LAYOUT["size_mm"][0] / 1000, LAYOUT["size_mm"][1] / 1000
S_TP = (LAYOUT["top"] - 1.25) / 1000          # card arc length from the top edge to the typing point


def theta(s):
    return (S_TP - s) / RP


def card_point(x, s, center):
    """Point on the card for card coordinates x (m from the left edge, carriage frame) and s (m from the top)."""
    th = theta(s)
    if th >= -2.0:
        return Vector((x, center.y - RP * math.cos(th), center.z + RP * math.sin(th)))
    p0 = Vector((x, center.y - RP * math.cos(-2.0), center.z + RP * math.sin(-2.0)))
    ds = s - (S_TP + 2.0 * RP)
    return p0 + Vector((0, -math.sin(-2.0), -math.cos(-2.0))) * ds


def card_mesh(center, coll):
    nx, ns = 84, 420
    xs = np.linspace(0, CARD_W, nx)
    ss = np.concatenate([np.linspace(0, S_TP + 2.0 * RP, ns - 20), np.linspace(S_TP + 2.0 * RP, CARD_H, 21)[1:]])
    verts, faces, uvs = [], [], []
    for j, s in enumerate(ss):
        for x in xs:
            verts.append(card_point(x, s, center))
    for j in range(len(ss) - 1):
        for i in range(nx - 1):
            a, b = j * nx + i, j * nx + i + 1
            c, d = (j + 1) * nx + i + 1, (j + 1) * nx + i
            faces.append((a, d, c, b))
            u0, u1 = xs[i] / CARD_W, xs[i + 1] / CARD_W
            v0, v1 = 1 - ss[j] / CARD_H, 1 - ss[j + 1] / CARD_H
            uvs.append([(u0, v0), (u0, v1), (u1, v1), (u1, v0)])
    ob = P.mesh("Card", verts, faces, coll, True, uvs)
    sol = ob.modifiers.new("thickness", "SOLIDIFY")
    sol.thickness = 0.00025
    sol.offset = -1
    return ob


def card_material(state):
    """Cream 200 gsm card; ink/impression from card_head_4.png with the not-yet-struck digits masked out by
    `state` (0..4, a keyed value), the last struck digit fresher (blacker, glossier)."""
    m, t = M.new_material("CardS01")
    uv = t.node("ShaderNodeUVMap").outputs[0]
    img = bpy.data.images.load(os.path.join(S.TEXTURES, "card_head_4.png"), check_existing=True)
    img.colorspace_settings.name = "Non-Color"
    tex = t.node("ShaderNodeTexImage", interpolation="Cubic", extension="CLIP")
    tex.image = img
    t.set(tex.inputs[0], uv)
    sep = t.node("ShaderNodeSeparateColor", {"Color": tex.outputs["Color"]})
    ink, height = sep.outputs[0], sep.outputs[1]
    u, v = t.xyz(uv)[0], t.xyz(uv)[1]
    st = t.node("ShaderNodeValue")
    st.name = "StrikeState"
    hidden = 0.0
    fresh = 0.0
    base_v = 1 - (LAYOUT["top"] - 1.2) / LAYOUT["size_mm"][1]
    band = t.mul(t.smooth(v, base_v - 0.026, base_v - 0.022), t.math("SUBTRACT", 1.0, t.smooth(v, base_v + 0.022, base_v + 0.026)))
    for k, xmm in enumerate(LAYOUT["strike_x_mm"]):
        u0, u1 = (xmm - 0.15) / LAYOUT["size_mm"][0], (xmm + LAYOUT["pitch"] - 0.15) / LAYOUT["size_mm"][0]
        inside = t.mul(t.mul(t.smooth(u, u0 - 0.0004, u0), t.math("SUBTRACT", 1.0, t.smooth(u, u1, u1 + 0.0004))), band)
        not_yet = t.math("LESS_THAN", st.outputs[0], k + 0.5)
        hidden = t.add(hidden, t.mul(inside, not_yet), clamp=True)
        is_last = t.mul(t.math("GREATER_THAN", st.outputs[0], k + 0.5), t.math("LESS_THAN", st.outputs[0], k + 1.5))
        fresh = t.add(fresh, t.mul(inside, is_last), clamp=True)
    keep = t.math("SUBTRACT", 1.0, hidden)
    ink = t.mul(ink, keep)
    height = t.math("SUBTRACT", 1.0, t.mul(t.math("SUBTRACT", 1.0, height), keep))
    fresh_ink = t.mul(fresh, ink)
    # paper: aged cream with fibre mottling; ink: warm black, fresh ink deeper and glossier
    p = t.texco("Object")
    fib = t.noise(t.mapping(p, scale=(1, 1, 3)), scale=2400.0, detail=3.0)
    fine = t.noise(t.mapping(p, scale=(2.5, 1, 1)), scale=7000.0, detail=2.0)
    cockle = t.noise(p, scale=260.0, detail=2.0)
    blot = t.noise(p, scale=90.0, detail=3.0)
    paper = t.mixc(t.add(t.mul(t.add(blot, -0.5), 0.5), 0.5), (0.66, 0.58, 0.40), (0.74, 0.66, 0.47))
    paper = t.mixc(t.mul(t.add(fib, -0.5), 0.22), paper, (0.0, 0.0, 0.0), blend="MULTIPLY")
    col = t.mixc(ink, paper, (0.022, 0.020, 0.022))
    col = t.mixc(fresh_ink, col, (0.008, 0.007, 0.009))
    rough = t.mixf(ink, 0.78, 0.6)
    rough = t.mixf(fresh_ink, rough, 0.32)
    h = t.add(t.add(t.mul(height, 1.0), t.mul(fib, 0.22)), t.add(t.mul(fine, 0.12), t.mul(cockle, 0.6)))
    nrm = t.bump(h, strength=0.5, distance=0.00006)
    bsdf = t.principled(base=col, rough=rough, normal=nrm, sheen=0.25, sheen_rough=0.6, spec=0.45)
    tl = t.node("ShaderNodeBsdfTranslucent", {"Color": t.mixc(ink, (0.8, 0.7, 0.5), (0.05, 0.05, 0.05))})
    t.output(t.mix_shader(0.08, bsdf, tl))
    for k, f in enumerate([0] + STRIKES):
        st.outputs[0].default_value = k
        st.outputs[0].keyframe_insert("default_value", frame=f)
    for fc in C.fcurves(m.node_tree):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"
    return m


def ribbon_material():
    """Two-tone cloth ribbon: black over red, inked, a crossed weave, slight sheen."""
    m, t = M.new_material("Ribbon")
    p = t.texco("Object")
    x, y, z = t.xyz(p)
    a = t.wave(t.mapping(p, rot=(0, 0, 0.785)), scale=2600.0, kind="BANDS", direction="X", distortion=0.6)
    b = t.wave(t.mapping(p, rot=(0, 0, -0.785)), scale=2600.0, kind="BANDS", direction="X", distortion=0.6)
    weave = t.math("MINIMUM", a, b)
    red = t.smooth(z, -0.0003, 0.0003)     # local z < 0: red lower half
    red = t.math("SUBTRACT", 1.0, red)
    wear = t.noise(p, scale=300.0, detail=4.0)
    col = t.mixc(red, (0.012, 0.011, 0.012), (0.09, 0.004, 0.007))
    col = t.mixc(t.mul(t.smooth(wear, 0.55, 0.8), 0.4), col, (0.03, 0.025, 0.03))
    t.output(t.principled(base=col, rough=t.mixf(weave, 0.55, 0.75), sheen=0.45, sheen_rough=0.35,
                          normal=t.bump(weave, 0.5, 0.00008)))
    return m


def typebar(name, phi_deg, coll, steel):
    """Typebar fanned by phi around the typing axis; returns its pivot empty (AXIS_ANGLE, angle 0 = strike)."""
    u0 = Vector((0.0, 0.876, 0.482)).normalized()
    ph = math.radians(phi_deg)
    u = Vector((math.sin(ph) * 0.876, math.cos(ph) * 0.876, 0.482)).normalized()
    L = 0.105
    face = T + Vector((0, -0.0011, 0))           # slug face stops just in front of the paper (ribbon between)
    piv = face - u * L
    axis = u.cross(Vector((0, 0, 1))).normalized()
    pe = S.empty(name, piv, size=0.005, coll=coll)
    pe.rotation_mode = "AXIS_ANGLE"
    # bar (1.2 mm x 3.4 mm) and slug (2.6 x 4.2 x 3 mm), built along u in world space then parented
    verts, faces = [], []

    def box(c, ex, ey, ez, xa, ya, za):
        base = len(verts)
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    verts.append(c + xa * ex * sx + ya * ey * sy + za * ez * sz)
        for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            faces.append(tuple(base + i for i in f))
    side = axis
    up = side.cross(u).normalized()
    box(piv + u * (L * 0.5 - 0.002), 0.0006, L * 0.5 - 0.003, 0.0017, side, u, up)
    box(face - u * 0.0016, 0.0013, 0.0016, 0.0021, side, u, up)
    ob = P.mesh(name + "_bar", [tuple(v - piv) for v in verts], faces, coll, smooth=False)
    ob.data.materials.append(steel)
    bev = ob.modifiers.new("bev", "BEVEL")
    bev.width, bev.segments = 0.0002, 2
    P.parent(ob, pe)
    pe.rotation_axis_angle = (math.radians(-105), axis.x, axis.y, axis.z)
    return pe, axis


def key_strike(pe, axis, f):
    """Rest -> strike at frame f -> rest (rest = -105 deg about the pivot axis, 0 = touching)."""
    curve = [(-6, -105), (-3, -105), (-2, -62), (-1, -18), (0, 0), (1, -14), (2, -48), (3, -86), (5, -105)]
    for df, a in curve:
        pe.rotation_axis_angle = (math.radians(a), axis.x, axis.y, axis.z)
        pe.keyframe_insert("rotation_axis_angle", frame=f + df)


def build(res="look", samples=None, threshold=None, **kw):
    S.new_scene(res, PRESET, samples=samples, threshold=threshold, exposure=0.0)
    sc = bpy.context.scene
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.5
    sc.frame_start, sc.frame_end = 0, FRAMES - 1
    coll = S.collection("S01")
    A.room(coll, floor=False)
    lights = A.dawn(target=T, azimuth_deg=24.0, elevation_deg=10.0, strength=9.0, kelvin=3500, sky_strength=0.15,
                    bounce=0.08, coll=coll, bar_through=T + Vector((-0.15, 0, 0)),
                    transom_through=T + Vector((0, 0, 0.026)))
    S.world((0.004, 0.0045, 0.006), 1.0)

    # carriage: platen + card + paper bail move together
    car = S.empty("Carriage", (0, 0, 0), coll=coll)
    center = Vector((0.0, T.y + RP, T.z))
    rubber = M.rubber("PlatenRubber", color=(0.010, 0.010, 0.011), roughness=0.42, seed=4)
    bpy.ops.mesh.primitive_cylinder_add(radius=R, depth=0.34, vertices=192, location=(0, center.y, center.z),
                                        rotation=(0, math.radians(90), 0))
    platen = bpy.context.active_object
    platen.name = "Platen"
    platen.data.materials.append(rubber)
    for poly in platen.data.polygons:
        poly.use_smooth = True
    S.link(platen, coll)
    card = card_mesh(Vector((0, center.y, center.z)), coll)
    card.data.materials.append(card_material(0))
    chrome = M.metal("chrome", name="Chrome", seed=2, smudge=0.12)
    nickel = M.metal("chrome", name="Nickel", seed=3, roughness=0.32, smudge=0.3)
    nickel.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.12, 0.115, 0.11, 1)
    # paper bail rod + rubber rollers, above the card's top edge
    th_b = 1.30
    bail_c = (0, center.y - (R + 0.0045) * math.cos(th_b), center.z + (R + 0.0045) * math.sin(th_b))
    bpy.ops.mesh.primitive_cylinder_add(radius=0.0021, depth=0.30, vertices=48, location=bail_c,
                                        rotation=(0, math.radians(90), 0))
    bail = bpy.context.active_object
    bail.name = "PaperBail"
    bail.data.materials.append(chrome)
    S.link(bail, coll)
    for poly in bail.data.polygons:
        poly.use_smooth = True
    for xo in (-0.05, 0.035):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.0042, depth=0.011, vertices=48,
                                            location=(xo, bail_c[1], bail_c[2]), rotation=(0, math.radians(90), 0))
        rl = bpy.context.active_object
        rl.name = "BailRoller"
        rl.data.materials.append(rubber)
        S.link(rl, coll)
        for poly in rl.data.polygons:
            poly.use_smooth = True
        P.parent(rl, car)
    for ob in (platen, card, bail):
        P.parent(ob, car)
    # card x: the next digit k sits at the typing point
    xs = LAYOUT["strike_x_mm"]
    pitch = LAYOUT["pitch"] / 1000

    def card_x(k):
        return -(xs[0] / 1000 + pitch / 2) - k * pitch
    car.location = (card_x(0), 0, 0)
    car.keyframe_insert("location", frame=0)
    for k, f in enumerate(STRIKES):
        # strike: the carriage jolts back 0.06 mm, then escapes one step to the left one frame later
        car.location = (card_x(k), 0, 0)
        car.keyframe_insert("location", frame=f - 1)
        car.location = (card_x(k), 0.00006, 0)
        car.keyframe_insert("location", frame=f)
        car.location = (card_x(k + 1), 0.00002, 0)
        car.keyframe_insert("location", frame=f + 1)
        car.location = (card_x(k + 1), 0, 0)
        car.keyframe_insert("location", frame=f + 3)
    C.set_interpolation(car, "location", "LINEAR")

    # ribbon + vibrator (lifted into the typing point on each strike)
    rib_root = S.empty("RibbonLift", (0, 0, 0), coll=coll)
    th_r = -0.30
    rc = Vector((0, center.y - (RP + 0.0016) * math.cos(th_r), center.z + (RP + 0.0016) * math.sin(th_r)))
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=rc)
    rb = bpy.context.active_object
    rb.name = "Ribbon"
    rb.scale = (0.18, 0.0127, 1)
    rb.rotation_euler = (math.radians(90) + th_r, 0, 0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    rb.rotation_euler = (math.radians(90) + th_r, 0, 0)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    so = rb.modifiers.new("t", "SOLIDIFY")
    so.thickness = 0.00012
    rb.data.materials.append(ribbon_material())
    S.link(rb, coll)
    P.parent(rb, rib_root)
    # vibrator: a bent steel fork either side of the typing point
    blk = M.metal("iron", name="BluedSteel", roughness=0.3, seed=6)
    for side in (-1, 1):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(T.x + side * 0.0062, rc.y - 0.0005, rc.z - 0.0015))
        pr = bpy.context.active_object
        pr.name = f"VibratorProng{side}"
        pr.scale = (0.0007, 0.0003, 0.0118)
        pr.rotation_euler = (th_r, 0, 0)
        pr.data.materials.append(blk)
        S.link(pr, coll)
        P.parent(pr, rib_root)
        b = pr.modifiers.new("b", "BEVEL")
        b.width, b.segments = 0.0002, 2
    lift = 0.0078
    rib_root.location = (0, 0, 0)
    rib_root.keyframe_insert("location", frame=0)
    for f in STRIKES:
        for df, z in ((-3, 0.0), (-1, lift * 0.8), (0, lift), (1, lift * 0.7), (3, 0.0)):
            rib_root.location = (0, -0.0002 * z / lift, z)
            rib_root.keyframe_insert("location", frame=f + df)

    # typebars: one per digit, fanned like the basket
    steel = M.metal("steel_brushed", name="TypebarSteel", roughness=0.28, seed=8)
    for k, (f, phi) in enumerate(zip(STRIKES, (-26.0, 14.0, -7.0, 31.0))):
        pe, axis = typebar(f"Typebar{k}", phi, coll, steel)
        pe.keyframe_insert("rotation_axis_angle", frame=0)
        key_strike(pe, axis, f)

    # dust on the card (moves with the carriage)
    rng = np.random.default_rng(34)
    dust = M.new_material("Dust")
    dm, dt = dust
    dt.output(dt.principled(base=(0.25, 0.23, 0.21), rough=0.9, sheen=0.6))
    for i in range(36):
        x = xs[0] / 1000 + rng.uniform(-0.035, 0.03)
        s = S_TP + rng.uniform(-0.012, 0.004)
        p = card_point(x, s, Vector((0, center.y, center.z)))
        r = rng.uniform(0.00002, 0.00008)
        bpy.ops.mesh.primitive_ico_sphere_add(radius=r, subdivisions=1, location=p)
        d = bpy.context.active_object
        d.name = "DustSpeck"
        d.scale = (rng.uniform(0.6, 2.5), rng.uniform(0.6, 1.5), 0.5)
        d.data.materials.append(dm)
        S.link(d, coll)
        d.parent = car

    # dawn finds the scene over the first 12 frames
    sun, sky = lights["sun"], lights["sky"]
    full_sun, full_sky = sun.data.energy, sky.data.energy
    for f, k in ((0, 0.0), (3, 0.04), (7, 0.35), (12, 1.0)):
        sun.data.energy = full_sun * k
        sun.data.keyframe_insert("energy", frame=f)
        sky.data.energy = full_sky * (0.15 + 0.85 * k)
        sky.data.keyframe_insert("energy", frame=f)
    C.set_interpolation(sun.data, "energy", "BEZIER")

    # camera: front-right, a little below the typing line; 6 mm drift right + 3 mm push
    yaw, pitch_deg, dist = math.radians(20), math.radians(-6), 0.125
    dvec = Vector((math.sin(yaw) * math.cos(pitch_deg), -math.cos(yaw) * math.cos(pitch_deg), math.sin(pitch_deg)))
    look = T + Vector((-0.003, 0, 0.0036))
    cam = C.add_camera("CAM_S01", lens=100, location=look + dvec * dist, target=look, fstop=4.0, focus=T)
    p0 = cam.location.copy()
    C.move(cam, [(0, p0), (FRAMES - 1, p0 + Vector((0.004, 0, 0)) - dvec * 0.002)])
    C.breathe(cam, amplitude_deg=0.02, period_frames=70, seed=1)
    return dict(cam=cam)
