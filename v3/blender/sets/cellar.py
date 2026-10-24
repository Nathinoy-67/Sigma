"""Set B -- the cask cellar (S06-S08; the end-slate background).

A whitewashed brick barrel vault, 4 m wide, 12 m deep, 3 m high, worn flagstones.  The vault axis runs along +y from
the entrance wall at y = 0 (with the round oculus high up) to the far end wall at y = 12.  Two rows of 300 l oak casks
lie on timber cradles along the side walls, heads to the aisle; the hero cask closes the aisle at its far end, head
towards the oculus.  The low sun through the oculus throws a disc of light down the vault.

    import cellar as B
    B.vault(); casks = B.casks(hero_chalk="1934"); light = B.oculus_sun(target=..., ...)
"""
import math
import os
import random

import bpy
import numpy as np
from mathutils import Vector

import scene as S
import materials as M
import props as P

W, D, SPRING, RAD = 4.0, 12.0, 1.0, 2.0          # width, depth, springing height, vault radius
OCULUS = Vector((0.0, 0.0, 2.45))                 # centre of the oculus in the entrance wall (y = 0)
OCULUS_R = 0.30
CASK_L, R_HEAD, R_BILGE, STAVE_T = 1.05, 0.355, 0.43, 0.03
CASK_Z = 0.15 + R_BILGE                           # axis height (on cradles)
HERO = Vector((0.0, 9.4, CASK_Z))                 # hero cask centre (axis along y, head towards -y)


# --------------------------------------------------------------------------- materials
def whitewash_brick(name="VaultBrick", seed=0, mapping="yz"):
    """Brick courses (Brick Texture) under a patchy limewash, damp and efflorescence near the floor, soot higher.
    mapping: 'yz' side walls, 'xz' end walls, 'vault' (courses along y, rows along the arc)."""
    m, t = M.new_material(name)
    p = t.texco("Object")
    x, y, z = t.xyz(p)
    if mapping == "xz":
        uv = t.combine(x, z, 0.0)
    elif mapping == "vault":
        arc = t.mul(t.math("ARCTAN2", t.add(z, -SPRING), x), RAD)
        uv = t.combine(y, arc, 0.0)
    else:
        uv = t.combine(y, z, 0.0)
    br = t.node("ShaderNodeTexBrick", {"Vector": uv, "Scale": 1.0, "Mortar Size": 0.009, "Mortar Smooth": 0.3,
                                       "Bias": 0.0, "Brick Width": 0.25, "Row Height": 0.075,
                                       "Color1": (0.45, 0.30, 0.22, 1), "Color2": (0.55, 0.38, 0.28, 1),
                                       "Mortar": (0.6, 0.58, 0.52, 1)}, offset=0.5, squash=1.0)
    mortar = br.outputs["Fac"]
    bcol = br.outputs["Color"]
    n1 = t.noise(p, scale=2.0, detail=6.0, rough=0.6)
    n2 = t.noise(p, scale=25.0, detail=4.0)
    n3 = t.noise(p, scale=7.0, detail=8.0, rough=0.7)
    wash = t.smooth(t.add(t.add(t.mul(n1, 0.7), t.mul(n2, 0.35)), t.mul(n3, 0.35)), 0.45, 0.75)
    col = t.mixc(wash, bcol, (0.62, 0.60, 0.55))
    grime = t.smooth(n3, 0.5, 0.8)
    col = t.mixc(t.mul(grime, 0.55), col, (0.10, 0.09, 0.075))
    col = t.mixc(t.mul(mortar, t.math("SUBTRACT", 1.0, wash)), col, (0.55, 0.53, 0.48))
    damp = t.math("SUBTRACT", 1.0, t.smooth(t.add(z, t.mul(n1, 0.5)), 0.2, 0.9))
    col = t.mixc(t.mul(damp, 0.5), col, (0.20, 0.18, 0.15))
    salt = t.mul(t.smooth(n2, 0.62, 0.7), t.mul(damp, 0.6))
    col = t.mixc(salt, col, (0.80, 0.80, 0.76))
    soot = t.mul(t.smooth(z, 1.8, 3.0), 0.5)
    col = t.mixc(t.mul(soot, t.smooth(n1, 0.3, 0.7)), col, (0.08, 0.07, 0.06))
    h = t.add(t.mul(t.math("SUBTRACT", 1.0, mortar), 1.0), t.mul(n2, 0.3))
    t.output(t.principled(base=col, rough=t.mixf(damp, 0.9, 0.6), normal=t.bump(h, 1.0, 0.012)))
    return m


def flagstones(name="Flagstones", seed=0):
    m, t = M.new_material(name)
    p = t.texco("Object")
    v = t.voronoi(t.mapping(p, scale=(1.0, 0.8, 1.0)), scale=1.6, feature="DISTANCE_TO_EDGE", out="Distance", rand=0.7)
    cell = t.voronoi(t.mapping(p, scale=(1.0, 0.8, 1.0)), scale=1.6, out="Color", rand=0.7)
    joint = t.math("SUBTRACT", 1.0, t.smooth(v, 0.0, 0.025))
    n = t.noise(p, scale=8.0, detail=8.0, rough=0.65)
    fine = t.noise(p, scale=90.0, detail=3.0)
    base = t.mixc(t.xyz(cell)[0], (0.11, 0.10, 0.09), (0.19, 0.17, 0.15))
    col = t.mixc(t.mul(n, 0.5), base, (0.07, 0.065, 0.06))
    col = t.mixc(joint, col, (0.03, 0.028, 0.025))
    wet = t.smooth(t.noise(p, scale=0.9, detail=3.0), 0.55, 0.7)
    t.output(t.principled(base=col, rough=t.mixf(wet, 0.75, 0.25), normal=t.bump(t.add(t.mul(joint, -1.0), t.mul(fine, 0.3)), 0.5, 0.02)))
    return m


def cask_material(name, chalk=None, chalk2=None, seed=0, chalk2_key=None, hero=False):
    """Staves (per-stave tone and roughness from the angle around the axis) + head boards with chalk.
    The lathe's point attribute 'inner' tags the parts: 0 staves, 0.5 chime/ends, 1 head."""
    m, t = M.new_material(name)
    p = t.texco("Object")
    x, y, z = t.xyz(p)
    tag = t.attr("inner")
    ang = t.math("ARCTAN2", y, x)
    stave = t.math("FLOOR", t.mul(t.add(ang, math.pi), 24 / (2 * math.pi)))
    rnd = t.white(t.combine(stave, seed * 0.37, 0.0), out="Value")
    grain = t.noise(t.combine(t.mul(ang, 40.0), t.mul(z, 3.0), 0.0), scale=6.0, detail=6.0, rough=0.6)
    rings = t.wave(t.combine(t.mul(ang, 300.0), t.mul(z, 2.0), 0.0), scale=0.4, distortion=4.0, kind="BANDS", direction="X")
    wine = t.smooth(t.noise(p, scale=3.0, detail=4.0), 0.55, 0.75)
    sc = t.mixc(rnd, (0.10, 0.065, 0.040), (0.19, 0.12, 0.07))
    sc = t.mixc(t.mul(grain, 0.5), sc, (0.06, 0.04, 0.025))
    sc = t.mixc(t.mul(rings, 0.25), sc, (0.05, 0.032, 0.02))
    sc = t.mixc(t.mul(wine, 0.4), sc, (0.07, 0.025, 0.02))
    # head: 5 boards across (seams along local x), grain along x, chalk
    hb = t.math("FRACT", t.mul(t.add(y, 0.5), 5 / 0.66))
    seam = t.math("SUBTRACT", 1.0, t.mul(t.smooth(hb, 0.0, 0.015), t.math("SUBTRACT", 1.0, t.smooth(hb, 0.985, 1.0))))
    hgrain = t.noise(t.combine(t.mul(x, 4.0), t.mul(y, 60.0), 0.0), scale=8.0, detail=6.0)
    hcol = t.mixc(t.mul(hgrain, 0.5), (0.14, 0.09, 0.055), (0.07, 0.045, 0.028))
    hcol = t.mixc(t.mul(seam, 0.7), hcol, (0.02, 0.012, 0.008))
    is_head = t.smooth(tag, 0.8, 0.95)
    col = t.mixc(is_head, sc, hcol)
    rough = t.add(t.mixf(rnd, 0.62, 0.8), t.mul(grain, 0.1))
    bmp = t.add(t.mul(grain, 0.4), t.mul(seam, -1.0))
    if chalk or chalk2:
        # chalk mapped on the head: screen right = local -y, screen up = local -x (see casks())
        if hero:     # head towards -y: screen right = local +x, screen up = local -y
            uvec = t.combine(t.add(0.5, t.mul(x, 1 / 0.66)), t.add(0.5, t.mul(y, -1 / 0.66)), 0.0)
        else:
            uvec = t.combine(t.add(0.5, t.mul(y, -1 / 0.66)), t.add(0.5, t.mul(x, -1 / 0.66)), 0.0)
        cm = 0.0
        for path, key in ((chalk, None), (chalk2, chalk2_key)):
            if not path:
                continue
            a = t.image(os.path.join(S.TEXTURES, f"chalk_{path}.png"), uvec, colorspace="Non-Color", extension="CLIP",
                        out="Color")
            a = t.xyz(a)[0]
            if key is not None:
                v = t.node("ShaderNodeValue")
                v.name = "ChalkReveal"
                for f, val in key:
                    v.outputs[0].default_value = val
                    v.outputs[0].keyframe_insert("default_value", frame=f)
                a = t.mul(a, v.outputs[0])
            cm = t.math("MAXIMUM", cm, a) if cm != 0.0 else a
        cm = t.mul(cm, is_head)
        col = t.mixc(cm, col, (0.78, 0.77, 0.72))
        rough = t.mixf(cm, rough, 0.95)
        bmp = t.add(bmp, t.mul(cm, 0.3))
    t.output(t.principled(base=col, rough=rough, normal=t.bump(bmp, 0.4, 0.004), sheen=0.15))
    return m


def iron_hoop_material():
    return M.metal("iron", name="HoopIron", seed=5, roughness=0.5, rust=0.22, smudge=0.3, color=(0.16, 0.155, 0.15))


# --------------------------------------------------------------------------- geometry
def vault(coll=None, depth=D):
    out = {}
    floor = P.slab("Floor", size=(W, depth, 0.1), location=(0, depth / 2, 0.0), bevel=0.0, material=flagstones(), coll=coll)
    out["floor"] = floor
    brick = whitewash_brick("BrickSide", mapping="yz")
    brick_v = whitewash_brick("BrickVault", mapping="vault")
    brick_e = whitewash_brick("BrickEnd", mapping="xz")
    for side in (-1, 1):
        out[f"wall{side}"] = P.slab(f"SideWall{side}", size=(0.3, depth, SPRING), location=(side * (W / 2 + 0.15), depth / 2, SPRING),
                                    bevel=0.0, material=brick, coll=coll)
    # barrel vault: half cylinder, normals inwards
    n, verts, faces = 64, [], []
    for i in range(n + 1):
        a = math.pi * i / n
        for yy in (0.0, depth):
            verts.append((RAD * math.cos(a), yy, SPRING + RAD * math.sin(a)))
    for i in range(n):
        faces.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
    v = P.mesh("Vault", verts, faces, coll, True)
    so = v.modifiers.new("t", "SOLIDIFY")
    so.thickness = 0.3
    v.data.materials.append(brick_v)
    out["vault"] = v
    # end walls: far wall plain, entrance wall with the oculus (a round hole + deep reveal + iron ring + glass)
    out["far"] = _end_wall("FarWall", depth, brick_e, coll, hole=False)
    out["near"] = _end_wall("EntranceWall", 0.0, brick_e, coll, hole=True)
    return out


def _end_wall(name, y, mat, coll, hole):
    """Wall filling the vault section at y (0.35 m thick).  With hole: the oculus opening."""
    import bmesh
    bm = bmesh.new()
    pts = [(-W / 2 - 0.3, 0.0), (W / 2 + 0.3, 0.0), (W / 2 + 0.3, SPRING)]
    for i in range(1, 64):
        a = math.pi * i / 64
        pts.append(((RAD + 0.3) * math.cos(a), SPRING + (RAD + 0.3) * math.sin(a)))
    pts.append((-W / 2 - 0.3, SPRING))
    bm.faces.new([bm.verts.new((x, 0, z)) for x, z in pts])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    S.link(ob, coll)
    ob.location = (0, y, 0)
    so = ob.modifiers.new("t", "SOLIDIFY")
    so.thickness = 0.36
    so.offset = 1.0 if y == 0.0 else -1.0
    ob.data.materials.append(mat)
    if hole:
        bpy.ops.mesh.primitive_cylinder_add(radius=OCULUS_R, depth=2.0, vertices=64, location=(OCULUS.x, 0, OCULUS.z),
                                            rotation=(math.radians(90), 0, 0))
        cutter = bpy.context.active_object
        cutter.name = "OculusCutter"
        cutter.hide_render = True
        cutter.hide_viewport = True
        bo = ob.modifiers.new("hole", "BOOLEAN")
        bo.operation = "DIFFERENCE"
        bo.object = cutter
        bo.solver = "EXACT"
        iron = M.metal("iron", name="OculusIron", seed=2, roughness=0.6, rust=0.3)
        bpy.ops.mesh.primitive_torus_add(major_radius=OCULUS_R - 0.01, minor_radius=0.018, location=(OCULUS.x, -0.12, OCULUS.z),
                                         rotation=(math.radians(90), 0, 0))
        ringo = bpy.context.active_object
        ringo.name = "OculusRing"
        ringo.data.materials.append(iron)
        S.link(ringo, coll)
        bpy.ops.mesh.primitive_circle_add(vertices=48, radius=OCULUS_R - 0.012, fill_type="NGON", location=(OCULUS.x, -0.12, OCULUS.z),
                                          rotation=(math.radians(90), 0, 0))
        g = bpy.context.active_object
        g.name = "OculusGlass"
        g.data.materials.append(M.glass("OldGlass", smudge=0.3, wavy=0.4, radius=0.3, seed=7))
        g.visible_shadow = False
        S.link(g, coll)
        # the sky outside, clipped to white-blue
        m, t = M.new_material("OculusSky")
        t.output(t.node("ShaderNodeEmission", {"Color": (0.75, 0.85, 1.0), "Strength": 8.0}))
        bpy.ops.mesh.primitive_plane_add(size=3.0, location=(OCULUS.x, -1.2, OCULUS.z + 0.3), rotation=(math.radians(90), 0, 0))
        sky = bpy.context.active_object
        sky.name = "OculusSkyCard"
        sky.data.materials.append(m)
        sky.visible_shadow = False
        sky.visible_diffuse = False
        S.link(sky, coll)
    return ob


def _loop_edges(bm, verts):
    vs = set(verts)
    return [e for e in bm.edges if e.verts[0] in vs and e.verts[1] in vs]


def cask(name, location, axis="x", chalk=None, chalk2=None, chalk2_key=None, seed=0, coll=None, hoop_mat=None):
    """Oak cask lying on its side.  axis 'x' (head towards -x), '-x' (head towards +x) or 'y' (head towards -y).
    Staves are real geometry: 24 staves with slightly different radii and V-grooves at the joints."""
    rng = random.Random(seed)
    L, Rh, Rb, T = CASK_L * rng.uniform(0.97, 1.03), R_HEAD, R_BILGE * rng.uniform(0.98, 1.02), STAVE_T
    recess = 0.032
    nz = 28
    prof, tags = [(0.0, -L / 2 + recess)], [1.0]
    prof += [(Rh - T, -L / 2 + recess)]
    tags += [1.0]
    prof += [(Rh - T, -L / 2 + 0.004), (Rh - T + 0.006, -L / 2)]
    tags += [0.5, 0.5]
    for i in range(nz + 1):
        zz = -L / 2 + L * i / nz
        prof.append((Rh + (Rb - Rh) * (1 - (2 * zz / L) ** 2), zz))
        tags.append(0.0)
    prof += [(Rh - T + 0.006, L / 2), (Rh - T, L / 2 - 0.004), (Rh - T, L / 2 - recess), (0.0, L / 2 - recess)]
    tags += [0.5, 0.5, 1.0, 1.0]
    nseg = 24 * 8
    offs = [rng.uniform(-0.0018, 0.0018) for _ in range(24)]
    th = np.linspace(0, 2 * math.pi, nseg, endpoint=False)

    def sec(a, zz, tag):
        rr = np.full(nseg, a)
        if tag < 0.25 and a > 0:
            k = (np.floor(th / (2 * math.pi / 24))).astype(int)
            frac = (th / (2 * math.pi / 24)) % 1.0
            groove = np.where((frac < 0.06) | (frac > 0.94), -0.0022, 0.0)
            rr = a + np.array([offs[i] for i in k]) + groove
        return np.stack([rr * np.cos(th), rr * np.sin(th)], 1)
    ob = P.loft(name, prof, sec, tags, coll, True)
    ob.data.materials.append(cask_material(name + "_Mat", chalk, chalk2, seed, chalk2_key, hero=(axis == "y")))
    # hoops: 3 per side (head hoop, quarter hoop, bilge hoop)
    hoop_mat = hoop_mat or iron_hoop_material()
    parts = [ob]
    for zz in (0.035, 0.16, 0.36):
        for sgn in (-1, 1):
            zc = sgn * (L / 2 - zz)
            r = Rh + (Rb - Rh) * (1 - (2 * zc / L) ** 2) + 0.0035
            hp = [(r - 0.0005, zc - 0.022), (r + 0.003, zc - 0.021), (r + 0.003, zc + 0.021), (r - 0.0005, zc + 0.022)]
            h = P.lathe(f"{name}_hoop", hp, 96, coll=coll, wobble=0.003, seed=seed + int(zz * 100))
            h.data.materials.append(hoop_mat)
            parts.append(h)
    root = S.empty(name + "_root", location, coll=coll)
    for pt in parts:
        pt.parent = root
    if axis == "x":
        root.rotation_euler = (0, math.radians(90), 0)
    elif axis == "-x":
        root.rotation_euler = (0, math.radians(90), math.radians(180))
    else:  # 'y': head (local -z) towards -y, screen up = world z
        root.rotation_euler = (math.radians(-90), 0, 0)
        root.rotation_euler.rotate_axis("Z", math.radians(0))
    return root, ob


def cradle(name, x, y0, y1, coll, mat):
    """Two long timber rails with chocks under a row of casks."""
    for k, dx in enumerate((-0.28, 0.28)):
        P.slab(f"{name}_rail{k}", size=(0.12, y1 - y0, 0.15), location=(x + dx, (y0 + y1) / 2, 0.15), bevel=0.006, material=mat, coll=coll)


def casks(coll=None, hero_chalk="1934", s07_chalk=True, rows=6, y0=1.6, pitch=1.0):
    """Two rows of casks along the side walls + the hero cask closing the aisle.  Returns dict."""
    out = {}
    hoop = iron_hoop_material()
    timber = M.wood("oak_cask", name="CradleOak", seed=4, value=0.5, scratches=1.0)
    bg = ["bg0", "bg1", "bg2", "bg3", "bg4", "bg5"]
    for side in (-1, 1):
        x = side * (W / 2 - CASK_L / 2 - 0.12)
        cradle(f"Cradle{side}", x, y0 - 0.6, y0 + rows * pitch, coll, timber)
        for i in range(rows):
            y = y0 + i * pitch
            ch, ch2, key = bg[(i + (side > 0) * 3) % 6], None, None
            if s07_chalk and side > 0 and i == rows - 1:
                ch, ch2 = "1934_struck", "1935_new"
                key = [(0, 0.0), (29, 0.0), (30, 1.0)]
            root, ob = cask(f"Cask{side}_{i}", (x, y, CASK_Z), axis="x" if side > 0 else "-x", chalk=ch, chalk2=ch2,
                            chalk2_key=key, seed=side * 100 + i, coll=coll, hoop_mat=hoop)
            out[(side, i)] = root
    cradle("CradleHero", 0.0, HERO.y - 0.45, HERO.y + 0.45, coll, timber)
    root, ob = cask("HeroCask", HERO, axis="y", chalk=hero_chalk, seed=7, coll=coll, hoop_mat=hoop)
    # hero lies across the aisle: its rails run along x
    for k in (0, 1):
        r = bpy.data.objects[f"CradleHero_rail{k}"]
        r.rotation_euler = (0, 0, math.radians(90))
        r.location = (0.0, HERO.y + (-0.28, 0.28)[k], 0.15)
        r.scale = (1, 1, 1)
    out["hero"] = root
    return out


def oculus_sun(target, strength=8.0, kelvin=5200, coll=None, shaft=True):
    """Sun lamp aimed through the oculus at `target`; an area light at the oculus for the bounce; an optional faked
    light shaft (a thin emissive card along the beam).  Returns dict(sun, bounce, shaft)."""
    d = (Vector(target) - OCULUS).normalized()
    sun = S.sun_light("OculusSun", strength=strength, kelvin=kelvin, coll=coll, angle_deg=0.53)
    sun.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    b = S.area_light("OculusBounce", size=(0.6, 0.6), power=30.0, kelvin=6000, location=OCULUS + Vector((0, 1.2, -0.3)),
                     target=OCULUS + Vector((0, 4.0, -1.8)), shape="DISK", coll=coll, spread_deg=70.0)
    out = dict(sun=sun, bounce=b, dir=d)
    if shaft:
        m, t = M.new_material("Shaft")
        g = t.xyz(t.texco("Generated"))
        along = g[0]
        across = t.math("ABSOLUTE", t.add(g[1], -0.5))
        dens = t.mul(t.mul(t.smooth(along, 0.0, 0.08), t.math("SUBTRACT", 1.0, t.smooth(along, 0.4, 1.0))),
                     t.math("SUBTRACT", 1.0, t.smooth(across, 0.3, 0.5)))
        dens = t.mul(dens, t.add(0.7, t.mul(t.noise(scale=3.0, detail=3.0), 0.6)))
        em = t.node("ShaderNodeEmission", {"Color": (1.0, 0.95, 0.85), "Strength": 0.06})
        t.set(em.inputs["Strength"], t.mul(dens, 0.06))
        tr = t.node("ShaderNodeBsdfTransparent")
        t.output(t.add_shader(tr, em))
        length = 9.0
        for k, roll in enumerate((0.0, 90.0)):
            bpy.ops.mesh.primitive_plane_add(size=1.0, location=OCULUS + d * length / 2)
            sh = bpy.context.active_object
            sh.name = f"LightShaft{k}"
            sh.scale = (length, OCULUS_R * 2.2, 1)
            sh.rotation_euler = d.to_track_quat("X", "Z").to_euler()
            sh.rotation_euler.rotate_axis("X", math.radians(roll))
            sh.data.materials.append(m)
            sh.visible_shadow = False
            sh.visible_diffuse = False
            sh.visible_glossy = False
            S.link(sh, coll)
            out[f"shaft{k}"] = sh
    return out
