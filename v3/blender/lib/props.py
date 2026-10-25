"""props.py -- hero props at true metric scale: shot glass, highball, square-shouldered bottle, coaster.

    import props as P
    sg = P.shot_glass("Shot", location=(0, 0, 0), frosted=True, fill=0.78, seed=1)
    hb = P.highball("Highball", location=(0.09, 0.03, 0), fill=0.62, seed=2, cond_facing_deg=-90)
    bt = P.bottle("Bottle", location=(-0.12, 0.08, 0), rotation_z_deg=12, seed=3, frosted=False)
    P.coaster("Coaster", location=(0.09, 0.03, 0))     # cork; put the glass at z = P.COASTER_H

Every builder returns a Prop: .root (empty you move/rotate/animate; the glass stands on its local
z = 0), named parts (.glass, .liquid, .bubbles, .foam, .drops, .label, .cap ...) and .info
(dimensions, fill height, volume).  All parts are parented to .root.

Geometry rules: real wall thickness, bevelled (filleted) profiles, smooth shading, per-seed
imperfection (radial wobble, glass waviness).  Liquids use the overlap method: the liquid mesh
reaches 0.2 mm INTO the glass wall so the glass/liquid interface refracts correctly in Cycles.
Glass meshes carry a point attribute "inner" (1 on the inside faces) used by the glass shader.
Low-level helpers (fillet, lathe, loft, mesh, gn_points_to_spheres, gn_instancer) are reusable
for any other turned or lofted object (jar, balance pans, stools, pendants...).
"""
import math
import os
import random

import bpy
import numpy as np
from mathutils import Matrix, Vector, noise as mnoise

import materials as M
import scene as S

OVERLAP = 0.0002          # liquid reaches 0.2 mm into the glass wall
COASTER_H = 0.004         # cork coaster thickness


class Prop:
    def __init__(self, root, info=None, **parts):
        self.root = root
        self.info = info or {}
        self.parts = parts
        for k, v in parts.items():
            setattr(self, k, v)

    def objects(self):
        out = [self.root]
        for v in self.parts.values():
            if isinstance(v, (list, tuple)):
                out += [o for o in v if o is not None]
            elif v is not None:
                out.append(v)
        return out

    def __repr__(self):
        return f"<Prop {self.root.name} {list(self.parts)} {self.info}>"


# =========================================================================== geometry helpers
def fillet(pts, radius, steps=8, tags=None):
    """Round the interior corners of a 2D polyline [(r, z), ...] with circular arcs.
    radius: float or per-point list (0 keeps the corner sharp).  Endpoints are kept.
    tags: optional per-point values carried onto the arc points.  Returns (points, tags)."""
    out, otags = [], []
    n = len(pts)
    for i, p in enumerate(pts):
        tg = tags[i] if tags is not None else 0
        rad = radius[i] if isinstance(radius, (list, tuple)) else radius
        if i == 0 or i == n - 1 or rad <= 0:
            out.append(tuple(p))
            otags.append(tg)
            continue
        b = np.array(p, float)
        u = np.array(pts[i - 1], float) - b
        v = np.array(pts[i + 1], float) - b
        lu, lv = np.linalg.norm(u), np.linalg.norm(v)
        u, v = u / lu, v / lv
        ang = math.acos(max(-1.0, min(1.0, float(u @ v))))
        if ang > math.pi - 1e-3 or ang < 1e-3:
            out.append(tuple(p))
            otags.append(tg)
            continue
        d = min(rad / math.tan(ang / 2), 0.48 * lu, 0.48 * lv)
        r_eff = d * math.tan(ang / 2)
        bis = (u + v) / np.linalg.norm(u + v)
        cen = b + bis * r_eff / math.sin(ang / 2)
        t1, t2 = b + u * d, b + v * d
        a1 = math.atan2(t1[1] - cen[1], t1[0] - cen[0])
        a2 = math.atan2(t2[1] - cen[1], t2[0] - cen[0])
        da = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
        for k in range(steps + 1):
            a = a1 + da * k / steps
            out.append((cen[0] + r_eff * math.cos(a), cen[1] + r_eff * math.sin(a)))
            otags.append(tg)
    return out, otags


def resample(pts, step, tags=None):
    """Insert points so no segment is longer than `step` (keeps originals)."""
    out, ot = [], []
    for i in range(len(pts) - 1):
        a, b = np.array(pts[i]), np.array(pts[i + 1])
        k = max(1, int(math.ceil(np.linalg.norm(b - a) / step)))
        for j in range(k):
            out.append(tuple(a + (b - a) * j / k))
            ot.append(tags[i] if tags else 0)
    out.append(tuple(pts[-1]))
    ot.append(tags[-1] if tags else 0)
    return out, ot


def circle_section(n):
    def sec(a, z, tag):
        th = np.linspace(0, 2 * math.pi, n, endpoint=False)
        return np.stack([a * np.cos(th), a * np.sin(th)], 1)
    return sec


def rounded_rect(a, rc, n, b=None):
    """n points of a rounded rectangle (half-widths a, b; corner radius rc), uniform in arc length,
    starting at (a, 0) going counter-clockwise.  rc = a (and b = a) gives a circle."""
    b = a if b is None else b
    rc = max(1e-6, min(rc, a, b))
    sx, sy = a - rc, b - rc
    q = 0.5 * math.pi * rc
    segs = [("L", (a, 0), (a, sy)), ("A", (sx, sy), 0.0), ("L", (sx, b), (-sx, b)), ("A", (-sx, sy), 0.5 * math.pi),
            ("L", (-a, sy), (-a, -sy)), ("A", (-sx, -sy), math.pi), ("L", (-sx, -b), (sx, -b)),
            ("A", (sx, -sy), 1.5 * math.pi), ("L", (a, -sy), (a, 0))]
    lens = [sy, q, 2 * sx, q, 2 * sy, q, 2 * sx, q, sy]
    total = sum(lens)
    cum = np.cumsum([0] + lens)
    s = np.linspace(0, total, n, endpoint=False)
    pts = np.zeros((n, 2))
    for i, si in enumerate(s):
        k = min(int(np.searchsorted(cum, si, side="right") - 1), len(segs) - 1)
        f = (si - cum[k]) / lens[k] if lens[k] > 0 else 0.0
        seg = segs[k]
        if seg[0] == "L":
            p0, p1 = np.array(seg[1]), np.array(seg[2])
            pts[i] = p0 + (p1 - p0) * f
        else:
            c, a0 = seg[1], seg[2]
            ang = a0 + f * 0.5 * math.pi
            pts[i] = (c[0] + rc * math.cos(ang), c[1] + rc * math.sin(ang))
    return pts


def mesh(name, verts, faces, coll=None, smooth=True, uvs=None, point_attrs=None, materials=None):
    """Create a mesh object.  uvs: per-face list of per-corner (u, v).  point_attrs: {name: values}."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    if uvs is not None:
        uvl = me.uv_layers.new(name="UVMap")
        flat = [c for fu in uvs for uv in fu for c in uv]
        uvl.data.foreach_set("uv", flat)
    for an, vals in (point_attrs or {}).items():
        vals = np.asarray(vals)
        if vals.ndim == 1:
            at = me.attributes.new(an, "INT" if vals.dtype.kind == "i" else "FLOAT", "POINT")
            at.data.foreach_set("value", vals.ravel().tolist())
        else:
            at = me.attributes.new(an, "FLOAT_VECTOR", "POINT")
            at.data.foreach_set("vector", vals.astype(float).ravel().tolist())
    me.validate(clean_customdata=False)
    if smooth and len(me.polygons):
        me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    S.link(ob, coll)
    for m in materials or []:
        ob.data.materials.append(m)
    return ob


def loft(name, prof, section, tags=None, coll=None, smooth=True, displace=None):
    """Sweep cross-sections along a 2D profile [(a, z), ...].  section(a, z, tag) -> (n, 2) ring.
    Points with a == 0 become poles.  Face orientation: a profile that runs up the outside and
    back down the inside gives outward normals.  UV: u around, v = normalised profile arc length.
    displace(verts(N,3), ring_index(N), tag(N)) -> verts: optional imperfection pass.
    Returns the object (point attribute 'inner' = tag)."""
    tags = tags if tags is not None else [0] * len(prof)
    verts, vtag, vring, rings = [], [], [], []
    arc = [0.0]
    for i in range(1, len(prof)):
        arc.append(arc[-1] + math.dist(prof[i], prof[i - 1]))
    total = arc[-1] or 1.0
    n_ring = None
    for i, (a, z) in enumerate(prof):
        if a < 1e-7:
            rings.append(len(verts))
            verts.append((0.0, 0.0, z))
            vtag.append(tags[i])
            vring.append(i)
        else:
            ring = section(a, z, tags[i])
            n_ring = len(ring)
            idx = list(range(len(verts), len(verts) + n_ring))
            rings.append(idx)
            verts += [(x, y, z) for x, y in ring]
            vtag += [tags[i]] * n_ring
            vring += [i] * n_ring
    faces, uvs = [], []
    for i in range(len(prof) - 1):
        r0, r1 = rings[i], rings[i + 1]
        v0, v1 = arc[i] / total, arc[i + 1] / total
        if isinstance(r0, int) and isinstance(r1, int):
            continue
        if isinstance(r0, int):
            n = len(r1)
            for j in range(n):
                k = (j + 1) % n
                faces.append((r0, r1[k], r1[j]))
                uvs.append([((j + 0.5) / n, v0), ((j + 1) / n, v1), (j / n, v1)])
        elif isinstance(r1, int):
            n = len(r0)
            for j in range(n):
                k = (j + 1) % n
                faces.append((r0[j], r0[k], r1))
                uvs.append([(j / n, v0), ((j + 1) / n, v0), ((j + 0.5) / n, v1)])
        else:
            n = len(r0)
            for j in range(n):
                k = (j + 1) % n
                faces.append((r0[j], r0[k], r1[k], r1[j]))
                uvs.append([(j / n, v0), ((j + 1) / n, v0), ((j + 1) / n, v1), (j / n, v1)])
    V = np.array(verts, float)
    if displace is not None:
        V = displace(V, np.array(vring), np.array(vtag, float))
    return mesh(name, V, faces, coll, smooth, uvs, {"inner": np.array(vtag, float)})


def lathe(name, prof, segments=96, tags=None, coll=None, wobble=0.0, seed=0, smooth=True):
    """Revolve a 2D profile [(r, z), ...] around Z.  wobble: relative radial imperfection (e.g. 0.002)."""
    rng = random.Random(seed)
    harm = [(k, rng.uniform(0.3, 1.0) / k, rng.uniform(0, 6.28), rng.uniform(5, 40), rng.uniform(0, 6.28))
            for k in (2, 3, 5, 7)]
    th = np.linspace(0, 2 * math.pi, segments, endpoint=False)

    def sec(a, z, tag):
        rr = np.full(segments, a)
        if wobble:
            w = sum(amp * np.sin(k * th + ph) * (1 + 0.4 * math.sin(fz * z + pz)) for k, amp, ph, fz, pz in harm)
            rr = a * (1 + wobble * w)
        return np.stack([rr * np.cos(th), rr * np.sin(th)], 1)
    return loft(name, prof, sec, tags, coll, smooth)


def parent(child, par):
    child.parent = par
    child.matrix_parent_inverse = Matrix.Identity(4)
    return child


def _root(name, location, rotation_z_deg, coll):
    r = S.empty(name, location, size=0.03, coll=coll)
    r.rotation_euler = (0, 0, math.radians(rotation_z_deg))
    return r


def _profile_normals(pts):
    """Unit 2D normals (tz, -tx) of an (r, z) polyline (towards the glass for an inner profile
    that runs from the axis outwards/upwards)."""
    P = np.array(pts, float)
    T = np.zeros_like(P)
    T[1:-1] = P[2:] - P[:-2]
    T[0] = P[1] - P[0]
    T[-1] = P[-1] - P[-2]
    T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-12
    return np.stack([T[:, 1], -T[:, 0]], 1)


def _liquid_profile(inner_up, fill_z, meniscus=0.0012, men_len=0.0013, overlap=OVERLAP, flat_steps=4):
    """Liquid outline from an inner-cavity profile running from the axis outwards and up.
    Offsets it `overlap` into the glass, clips at fill_z and adds a concave meniscus."""
    N = _profile_normals(inner_up)
    P = np.array(inner_up, float) + N * overlap
    P[0, 0] = 0.0
    out = [tuple(P[0])]
    for i in range(1, len(P)):
        if P[i, 1] >= fill_z:
            a, b = P[i - 1], P[i]
            f = (fill_z - a[1]) / (b[1] - a[1] + 1e-12)
            out.append(tuple(a + (b - a) * f))
            break
        out.append(tuple(P[i]))
    r_wall = out[-1][0]
    # meniscus: z(d) = fill + m * exp(-d / L), d = distance from the wall
    men = []
    ds = [0.0, 0.00008, 0.0002, 0.0004, 0.0007, 0.0011, 0.0016, 0.0023, 0.0032, 0.0045, 0.0062]
    for d in ds:
        if d > r_wall * 0.6:
            break
        men.append((r_wall - d, fill_z + meniscus * math.exp(-d / men_len)))
    out[-1] = (r_wall, fill_z + meniscus)   # the contact line climbs the wall
    out += men[1:]
    last = men[-1][0] if men else r_wall
    for k in range(1, flat_steps + 1):
        out.append((last * (1 - k / flat_steps), fill_z))
    # densify long wall segments: with smooth shading a tall single face interpolates the normals of its corners
    # (tilted up at the meniscus, down at the floor fillet) and bends every ray through the drink vertically
    return resample(out, 0.002)[0]


def _vol_ml(prof_up):
    """Volume (ml) of a solid of revolution under a closed axis->...->axis profile (r, z)."""
    v = 0.0
    for (r0, z0), (r1, z1) in zip(prof_up[:-1], prof_up[1:]):
        v += math.pi * (r0 * r0 + r0 * r1 + r1 * r1) / 3.0 * (z1 - z0)
    return abs(v) * 1e6


# =========================================================================== geometry nodes
def gn_points_to_spheres():
    """Node group: mesh vertices -> Cycles point-cloud spheres, animated in closed form (no sim,
    so any frame range can render on any machine).  Per-point attributes:
      radius  sphere radius (m)          speed  rise speed (m/s, 0 = static)
      phase   0..1 start offset          zmin, zmax  rise range (object z)
      wob     wobble amplitude (m)       grow   radius growth factor over the rise
    Input 'Material' sets the material, 'Time Offset' (s) shifts the clock."""
    ng = bpy.data.node_groups.get("OYOS_PointSpheres")
    if ng:
        return ng
    ng = bpy.data.node_groups.new("OYOS_PointSpheres", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Material", in_out="INPUT", socket_type="NodeSocketMaterial")
    s = ng.interface.new_socket("Time Offset", in_out="INPUT", socket_type="NodeSocketFloat")
    s.default_value = 0.0
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    t = M.Tree(ng)
    gi = t.node("NodeGroupInput")
    go = t.node("NodeGroupOutput")

    def attr(nm):
        return t.node("GeometryNodeInputNamedAttribute", {"Name": nm}, data_type="FLOAT").outputs[0]
    pos = t.node("GeometryNodeInputPosition").outputs[0]
    x, y, z = t.xyz(pos)
    time = t.add(t.node("GeometryNodeInputSceneTime").outputs["Seconds"], gi.outputs["Time Offset"])
    zmin, zmax, spd, ph = attr("zmin"), attr("zmax"), attr("speed"), attr("phase")
    span = t.math("MAXIMUM", t.math("SUBTRACT", zmax, zmin), 1e-5)
    frac = t.math("FRACT", t.add(ph, t.math("DIVIDE", t.mul(time, spd), span)))
    moving = t.math("GREATER_THAN", spd, 0.0)
    znew = t.mixf(moving, z, t.add(zmin, t.mul(frac, span)))
    wob = attr("wob")
    ang = t.mul(t.add(t.mul(time, 9.0), t.mul(ph, 37.0)), 1.0)
    xn = t.add(x, t.mul(wob, t.math("SINE", ang)))
    yn = t.add(y, t.mul(wob, t.math("COSINE", t.mul(ang, 1.3))))
    rad = t.mul(attr("radius"), t.add(1.0, t.mul(attr("grow"), t.mixf(moving, 0.0, frac))))
    m2p = t.node("GeometryNodeMeshToPoints", {"Mesh": gi.outputs["Geometry"], "Position": t.combine(xn, yn, znew),
                                             "Radius": rad})
    sm = t.node("GeometryNodeSetMaterial", {"Geometry": m2p.outputs[0], "Material": gi.outputs["Material"]})
    t.link(sm.outputs[0], go.inputs[0])
    return ng


def gn_instancer():
    """Node group: instance a collection's children on mesh vertices.  Point attributes:
    rot (euler, FLOAT_VECTOR), scl (FLOAT_VECTOR), idx (INT: which child)."""
    ng = bpy.data.node_groups.get("OYOS_Instancer")
    if ng:
        return ng
    ng = bpy.data.node_groups.new("OYOS_Instancer", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Collection", in_out="INPUT", socket_type="NodeSocketCollection")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    t = M.Tree(ng)
    gi = t.node("NodeGroupInput")
    go = t.node("NodeGroupOutput")
    ci = t.node("GeometryNodeCollectionInfo", {"Collection": gi.outputs["Collection"], "Separate Children": True,
                                              "Reset Children": True}, transform_space="ORIGINAL")
    rot = t.node("GeometryNodeInputNamedAttribute", {"Name": "rot"}, data_type="FLOAT_VECTOR").outputs[0]
    scl = t.node("GeometryNodeInputNamedAttribute", {"Name": "scl"}, data_type="FLOAT_VECTOR").outputs[0]
    idx = t.node("GeometryNodeInputNamedAttribute", {"Name": "idx"}, data_type="INT").outputs[0]
    e2r = t.node("FunctionNodeEulerToRotation", {"Euler": rot})
    iop = t.node("GeometryNodeInstanceOnPoints", {"Points": gi.outputs["Geometry"], "Instance": ci.outputs[0],
                                                 "Pick Instance": True, "Instance Index": idx,
                                                 "Rotation": e2r.outputs[0], "Scale": scl})
    t.link(iop.outputs[0], go.inputs[0])
    return ng


def modifier_input(mod, socket_name, value):
    """Set a Geometry Nodes modifier input by its socket name (Blender 5: mod.properties.inputs)."""
    for it in mod.node_group.interface.items_tree:
        if getattr(it, "in_out", None) == "INPUT" and it.name == socket_name:
            props = getattr(mod, "properties", None)
            if props is not None and hasattr(props, "inputs"):
                getattr(props.inputs, it.identifier).value = value
            else:                                   # Blender 4.x
                mod[it.identifier] = value
            return
    raise KeyError(socket_name)


_modifier_input = modifier_input


def point_spheres(name, P, attrs, material, coll=None, time_offset=0.0):
    """Create a vertex-only mesh with per-point attributes rendered as spheres (see gn_points_to_spheres)."""
    ob = mesh(name, P, [], coll, smooth=False, point_attrs=attrs)
    mod = ob.modifiers.new("spheres", "NODES")
    mod.node_group = gn_points_to_spheres()
    _modifier_input(mod, "Material", material)
    _modifier_input(mod, "Time Offset", time_offset)
    return ob


def instanced_points(name, P, rot, scl, idx, templates_coll, coll=None):
    ob = mesh(name, P, [], coll, smooth=False,
              point_attrs={"rot": np.asarray(rot), "scl": np.asarray(scl), "idx": np.asarray(idx, dtype=np.int32)})
    mod = ob.modifiers.new("instances", "NODES")
    mod.node_group = gn_instancer()
    _modifier_input(mod, "Collection", templates_coll)
    return ob


# =========================================================================== droplets
def drop_templates(material=None):
    """Collection of 3 water-drop templates (base radius 1, base on z=0, +Y = downhill):
    0 small round (contact angle 50 deg), 1 medium sagging, 2 large sagging teardrop."""
    c = bpy.data.collections.get("OYOS_DropTemplates")
    if c and len(c.objects):
        return c
    c = S.collection("OYOS_DropTemplates")
    c.hide_render = True
    mat = material or M.water("CondensationWater")
    for i, (ca, sag, elong) in enumerate([(50, 0.0, 1.0), (60, 0.18, 1.08), (68, 0.35, 1.22)]):
        th = math.radians(ca)
        R = 1.0 / math.sin(th)
        zc = -R * math.cos(th)
        prof = [(0.0, 0.0), (0.97, 0.0)]
        for k in range(0, 13):
            r = 1.0 * math.cos(0.5 * math.pi * k / 12) ** 1.0
            r = 1.0 - (k / 12) ** 1.6
            z = math.sqrt(max(R * R - r * r, 0)) + zc
            prof.append((r, z))
        prof[2] = (1.0, 0.0)
        prof[-1] = (0.0, prof[-1][1])
        ob = lathe(f"drop_t{i}", prof, segments=20, coll=c)
        h = prof[-1][1]
        V = np.array([v.co[:] for v in ob.data.vertices])
        zz = V[:, 2] / max(h, 1e-6)
        V[:, 1] = V[:, 1] * np.where(V[:, 1] > 0, elong, 1.0)            # longer downhill
        V[:, 1] += sag * zz * (1 - zz) * 1.6                               # bulk slides downhill
        ob.data.vertices.foreach_set("co", V.ravel())
        ob.data.update()
        ob.data.materials.append(mat)
    return c


def _euler_from_normal(n, up=(0, 0, 1)):
    """Euler (XYZ) whose local Z = n and local -Y... +Y points downhill (gravity projected)."""
    n = Vector(n).normalized()
    g = Vector((0, 0, -1))
    yv = g - n * g.dot(n)
    if yv.length < 1e-6:
        yv = Vector((0, 1, 0)) - n * n.y
    yv.normalize()
    xv = yv.cross(n)
    m = Matrix((xv, yv, n)).transposed()
    return m.to_euler("XYZ")


def scatter_drops(name, surface_fn, n, rmin, rmax, alpha=2.4, seed=0, coll=None, sink=0.00003, material=None,
                  min_gap=0.15, extra=()):
    """Dart-throw non-overlapping water drops with a power-law size spread on a surface.
    surface_fn(rng) -> (point Vector, normal Vector) or None.  extra: pre-placed drops
    [(point, normal, radius, template_index, stretch_y), ...] (e.g. the bead at the end of a run).
    Returns an instancer object."""
    rng = random.Random(seed)
    tc = drop_templates(material)
    cells = {}
    cs = max(rmax, max([e[2] for e in extra], default=0)) * 2.2
    P, ROT, SCL, IDX = [], [], [], []
    for (p, nrm, r, k, st) in extra:
        p, nrm = Vector(p), Vector(nrm).normalized()
        cells.setdefault((int(p.x // cs), int(p.y // cs), int(p.z // cs)), []).append((p, r))
        P.append(tuple(p - nrm * sink))
        ROT.append(tuple(_euler_from_normal(nrm)))
        SCL.append((r, r * st, r * (0.9 if k == 2 else 0.75)))
        IDX.append(k)
    tries = 0
    while len(P) < n and tries < n * 30:
        tries += 1
        s = surface_fn(rng)
        if s is None:
            continue
        p, nrm = s
        u = rng.random()
        r = rmin * (1 - u * (1 - (rmin / rmax) ** (alpha - 1))) ** (-1.0 / (alpha - 1))
        key = (int(p.x // cs), int(p.y // cs), int(p.z // cs))
        ok = True
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for (q, rq) in cells.get((key[0] + dx, key[1] + dy, key[2] + dz), ()):
                        if (q - p).length < (r + rq) * (1 + min_gap):
                            ok = False
                            break
                    if not ok:
                        break
                if not ok:
                    break
        if not ok:
            continue
        cells.setdefault(key, []).append((p, r))
        P.append(tuple(p - nrm * sink))
        e = _euler_from_normal(nrm)
        ROT.append(tuple(e))
        k = 0 if r < rmax * 0.25 else (1 if r < rmax * 0.55 else 2)
        flat = rng.uniform(0.85, 1.1)
        SCL.append((r * rng.uniform(0.92, 1.08), r * rng.uniform(0.95, 1.12), r * flat))
        IDX.append(k)
    return instanced_points(name, P, ROT, SCL, IDX, tc, coll)


def drop_list(ob, n=None):
    """[(x, y, z, r), ...] of the drops of a scatter_drops() object, largest first (object space)."""
    me = ob.data
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    sc = np.zeros(len(me.vertices) * 3)
    me.attributes["scl"].data.foreach_get("vector", sc)
    co, sc = co.reshape(-1, 3), sc.reshape(-1, 3)
    order = np.argsort(-sc[:, 0])
    if n:
        order = order[:n]
    return [(float(co[i, 0]), float(co[i, 1]), float(co[i, 2]), float(sc[i, 0])) for i in order]


def frost_shell(src, name=None, coverage=0.8, wipes=1, radius=0.03, seed=0, offset=0.00012, coll=None, top_z=None,
                holes=(), density=0.8, track=None):
    """Freezer frost: a copy of the OUTER faces of a glass mesh (point attribute inner < 0.6) pushed
    out by `offset` along the normals, shaded with materials.frost_layer.  Parented like `src`."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(src.data)
    lay = bm.verts.layers.float.get("inner")
    if lay is not None:
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v[lay] > 0.6], context="VERTS")
    bm.normal_update()
    for v in bm.verts:
        v.co += v.normal * offset
    me = bpy.data.meshes.new((name or src.name + "_frost"))
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    ob = bpy.data.objects.new(me.name, me)
    S.link(ob, coll or (src.users_collection[0] if src.users_collection else None))
    ob.parent = src.parent
    ob.matrix_parent_inverse = src.matrix_parent_inverse.copy()
    ob.matrix_basis = src.matrix_basis.copy()
    ob.data.materials.append(M.frost_layer(me.name + "_Mat", coverage, wipes, radius, seed, top_z=top_z, holes=holes,
                                           density=density, track=track))
    return ob


# =========================================================================== shot glass
def shot_glass(name="ShotGlass", location=(0, 0, 0), rotation_z_deg=0.0, frosted=False, fill=0.8,
               liquid="jager", seed=0, coll=None, melt_beads=90, smudge=0.06, segments=96, frost=0.85,
               frost_wipes=1, liquid_material=None, glass_material=None, frost_density=0.8):
    """Heavy-based straight shot glass: 60 mm tall, 44 mm across the rim, 2.6 mm wall, 16 mm base.
    fill: fraction of the cavity height (0.8 ~ 4 cl).  liquid: "jager" | None.
    frosted: freezer frost on the outside + `melt_beads` water beads."""
    H, Rt, Rb, t, B = 0.060, 0.0222, 0.0213, 0.0026, 0.016
    rng = random.Random(seed)
    root = _root(name, location, rotation_z_deg, coll)
    # outer: underside (slight push-up) -> foot -> wall -> rounded rim -> inner wall -> inner bottom
    ri_top, ri_bot = Rt - t, Rb - 0.0042
    rim_c = (Rt - t / 2, H - t / 2)
    outer = [(0.0, 0.0009), (Rb - 0.006, 0.00005), (Rb - 0.0015, 0.0), (Rb, 0.0016), (Rt, H - t / 2)]
    outer, otag = fillet(outer, [0, 0.004, 0.0012, 0.0009, 0], steps=6)
    rim = [(rim_c[0] + t / 2 * math.cos(a), rim_c[1] + t / 2 * math.sin(a))
           for a in np.linspace(0, math.pi, 13)[1:-1]]
    inner_dn = [(ri_top, H - t / 2), (ri_bot, B), (0.0, B)]
    inner_dn, itag = fillet(inner_dn, [0, 0.006, 0], steps=10)
    prof = outer + rim + inner_dn
    tags = otag + [0.5] * len(rim) + [1] * len(inner_dn)
    prof, tags = resample(prof, 0.003, tags)
    g = lathe(name + "_glass", prof, segments, tags, coll, wobble=0.0025, seed=seed)
    parent(g, root)
    gm = glass_material or M.glass(name + "_GlassMat", smudge=smudge, radius=Rt, seed=seed,
                                   roughness=0.02 if frosted else 0.0)
    g.data.materials.append(gm)
    info = dict(height=H, rim_radius=Rt, base=B, cavity_top=H - t / 2)
    parts = dict(glass=g, liquid=None, beads=None, frost=None)
    if frosted and melt_beads:
        def surf(r):
            a = r.uniform(0, 2 * math.pi)
            z = r.uniform(0.004, H - 0.006)
            rr = Rb + (Rt - Rb) * z / H
            n = Vector((math.cos(a), math.sin(a), (Rb - Rt) / H)).normalized()
            return Vector((rr * math.cos(a), rr * math.sin(a), z)), n
        parts["beads"] = scatter_drops(name + "_melt", surf, melt_beads, 0.0003, 0.0019, alpha=2.0, seed=seed + 7,
                                       coll=coll)
        parent(parts["beads"], root)
    if frosted:
        holes = drop_list(parts["beads"], 18) if parts["beads"] else ()
        parts["frost"] = frost_shell(g, coverage=frost, wipes=frost_wipes, radius=Rt, seed=seed, coll=coll, top_z=H,
                                     holes=holes, density=frost_density)
    if liquid:
        inner_up = list(reversed(inner_dn))
        fill_z = B + (H - t / 2 - B) * fill
        lp = _liquid_profile(inner_up, fill_z)
        lq = lathe(name + "_liquid", lp, segments, coll=coll, wobble=0.0025, seed=seed)
        parent(lq, root)
        lq.data.materials.append(liquid_material or M.jagermeister(name + "_Jager"))
        parts["liquid"] = lq
        info.update(fill_z=fill_z, volume_ml=round(_vol_ml(lp), 1))
    return Prop(root, info, **parts)


# =========================================================================== highball
def highball(name="Highball", location=(0, 0, 0), rotation_z_deg=0.0, fill=0.62, drink="energy", seed=0,
             coll=None, bubbles=True, foam=True, condensation=True, cond_facing_deg=-90.0, cond_span_deg=230.0,
             n_drops=6000, smudge=0.05, segments=128, drink_material=None, n_streams=14, n_cling=260,
             n_free=120, fog=True, n_trails=5):
    """Straight-sided 340 ml highball: 150 mm tall, 61 mm across, 3 mm wall, 8 mm base.
    drink: "energy" | None.  fill: fraction of cavity height.
    bubbles: closed-form animated carbonation (streams from nucleation sites, wall-clinging bubbles,
    free bubbles) as Cycles point spheres.  foam: thin ring of tiny bubbles at the meniscus.
    condensation: instanced drops (power-law 0.15-2.4 mm) on the side facing cond_facing_deg
    (azimuth in the prop's frame; -90 = towards -Y) plus fogged roughness on the glass."""
    H, Rt, Rb, t, B = 0.150, 0.0305, 0.0298, 0.0030, 0.0080
    rng = random.Random(seed)
    root = _root(name, location, rotation_z_deg, coll)
    ri_top, ri_bot = Rt - t, Rb - t - 0.0002
    rim_c = (Rt - t / 2, H - t / 2)
    outer = [(0.0, 0.0012), (Rb - 0.008, 0.00005), (Rb - 0.002, 0.0), (Rb, 0.002), (Rt, H - t / 2)]
    outer, otag = fillet(outer, [0, 0.006, 0.0015, 0.0012, 0], steps=6)
    rim = [(rim_c[0] + t / 2 * math.cos(a), rim_c[1] + t / 2 * math.sin(a))
           for a in np.linspace(0, math.pi, 13)[1:-1]]
    inner_dn = [(ri_top, H - t / 2), (ri_bot, B), (0.0, B + 0.0006)]
    inner_dn, itag = fillet(inner_dn, [0, 0.005, 0], steps=10)
    prof = outer + rim + inner_dn
    tags = otag + [0.5] * len(rim) + [1] * len(inner_dn)
    prof, tags = resample(prof, 0.004, tags)
    fill_z = B + (H - t / 2 - B) * fill if drink else None
    fa, span = math.radians(cond_facing_deg), math.radians(cond_span_deg)
    trails = []
    if condensation and drink:
        for k in range(n_trails):
            a = fa + (rng.random() - 0.5) * span * 0.7
            z1 = rng.uniform(fill_z * 0.55, fill_z - 0.004)       # where the run started
            z0 = rng.uniform(0.012, z1 - 0.025)                    # where the bead stopped
            trails.append((a, z0, z1, rng.uniform(0.0008, 0.0013)))
    g = lathe(name + "_glass", prof, segments, tags, coll, wobble=0.002, seed=seed)
    parent(g, root)
    g.data.materials.append(M.glass(name + "_GlassMat", smudge=smudge, radius=Rt, seed=seed,
                                    fog_top=(fill_z + 0.004) if (condensation and fog and drink) else None,
                                    trails=trails))
    info = dict(height=H, rim_radius=Rt, base=B, cavity_top=H - t / 2)
    parts = dict(glass=g, liquid=None, bubbles=None, foam=None, drops=None)
    if drink:
        inner_up = list(reversed(inner_dn))
        lp = _liquid_profile(inner_up, fill_z, meniscus=0.0014, men_len=0.0015)
        lq = lathe(name + "_liquid", lp, segments, coll=coll, wobble=0.002, seed=seed)
        parent(lq, root)
        lq.data.materials.append(drink_material or M.energy_drink(name + "_Drink"))
        parts["liquid"] = lq
        info.update(fill_z=fill_z, volume_ml=round(_vol_ml(lp), 1))

        def r_in(z):
            return ri_bot + (ri_top - ri_bot) * (z - B) / (H - B)
        if bubbles:
            P, A = [], {k: [] for k in ("radius", "speed", "phase", "zmin", "zmax", "wob", "grow")}

            def add(p, radius, speed=0.0, phase=0.0, zmin=0.0, zmax=1.0, wob=0.0, grow=0.0):
                P.append(p)
                for k, v in zip(("radius", "speed", "phase", "zmin", "zmax", "wob", "grow"),
                                (radius, speed, phase, zmin, zmax, wob, grow)):
                    A[k].append(v)
            # nucleation streams: sites on the floor and lower walls
            for s in range(n_streams):
                if rng.random() < 0.4:
                    a, rr = rng.uniform(0, 2 * math.pi), rng.uniform(0.0, ri_bot - 0.004)
                    z0 = B + 0.0012
                else:
                    a = rng.uniform(0, 2 * math.pi)
                    z0 = rng.uniform(B + 0.003, fill_z - 0.03)
                    rr = r_in(z0) - 0.0006
                spd = rng.uniform(0.035, 0.075)
                nb = rng.randint(16, 30)
                rad = rng.uniform(0.00025, 0.00045)
                for k in range(nb):
                    add((rr * math.cos(a), rr * math.sin(a), z0), rad * rng.uniform(0.85, 1.15), spd,
                        (k + rng.uniform(-0.15, 0.15)) / nb, z0, fill_z - 0.0006, rng.uniform(0.0, 0.0004), 1.2)
            # bubbles clinging to the inner wall and floor
            for _ in range(n_cling):
                rad = 0.00022 + 0.0011 * rng.random() ** 2.5
                if rng.random() < 0.25:
                    a, rr = rng.uniform(0, 2 * math.pi), math.sqrt(rng.random()) * (ri_bot - 0.003)
                    z = B + 0.0006 + rad * 0.6
                else:
                    a, z = rng.uniform(0, 2 * math.pi), rng.uniform(B + 0.002, fill_z - 0.002)
                    rr = r_in(z) - rad * 0.55
                add((rr * math.cos(a), rr * math.sin(a), z), rad, zmin=z, zmax=z + 1.0)
            # free bubbles drifting up
            for _ in range(n_free):
                a, rr = rng.uniform(0, 2 * math.pi), math.sqrt(rng.random()) * (ri_bot - 0.002)
                z0 = B + 0.002
                add((rr * math.cos(a), rr * math.sin(a), z0), rng.uniform(0.00012, 0.00028), rng.uniform(0.03, 0.06),
                    rng.random(), z0, fill_z - 0.0006, rng.uniform(0.0002, 0.0008), 1.0)
            parts["bubbles"] = point_spheres(name + "_bubbles", P, {k: np.array(v, float) for k, v in A.items()},
                                             M.bubble(name + "_Bubble"), coll)
            parent(parts["bubbles"], root)
        if foam:
            P, R = [], []
            rw = r_in(fill_z)
            n_f = 1700
            for _ in range(n_f):
                a = rng.uniform(0, 2 * math.pi)
                d = abs(rng.gauss(0, 0.0011))
                if rng.random() < 0.08:              # a few islands drifting inward
                    d = rng.uniform(0.002, 0.007)
                rad = 0.0001 + 0.00035 * rng.random() ** 2.0
                rr = rw - d - rad * 0.4
                zs = fill_z + 0.0014 * math.exp(-d / 0.0015)
                P.append((rr * math.cos(a), rr * math.sin(a), zs + rad * rng.uniform(-0.5, 0.2)))
                R.append(rad)
            n = len(P)
            parts["foam"] = point_spheres(name + "_foam", P, {"radius": np.array(R), "speed": np.zeros(n),
                                                              "phase": np.zeros(n), "zmin": np.array([p[2] for p in P]),
                                                              "zmax": np.array([p[2] + 1 for p in P]),
                                                              "wob": np.zeros(n), "grow": np.zeros(n)},
                                          M.foam(name + "_Foam"), coll)
            parent(parts["foam"], root)
        if condensation:
            ztop = fill_z + 0.006

            def r_out(z):
                return Rb + (Rt - Rb) * z / H

            def in_trail(a, z, pad=1.25):
                for i, (ta, z0, z1, w) in enumerate(trails):
                    lat = abs(math.sin(a - ta) * r_out(z) + math.sin(z * 260.0 + i * 1.7) * w * 0.6)
                    if math.cos(a - ta) > 0 and lat < w * pad and z0 - 0.002 < z < z1 + 0.002:
                        return True
                return False

            def surf(r):
                a = fa + (r.random() - 0.5) * span
                z = r.uniform(0.003, ztop)
                if z > fill_z - 0.004 and r.random() < (z - (fill_z - 0.004)) / 0.01:
                    return None     # density falls off just above the liquid line
                if in_trail(a, z):
                    return None     # a run swept this channel clean
                rr = r_out(z)
                n = Vector((math.cos(a), math.sin(a), (Rb - Rt) / H)).normalized()
                return Vector((rr * math.cos(a), rr * math.sin(a), z)), n
            extra = []
            for i, (ta, z0, z1, w) in enumerate(trails):
                rb = w * rng.uniform(1.9, 2.5)
                z = z0 + rb * 0.6
                a0 = ta - math.sin(z * 260.0 + i * 1.7) * w * 0.6 / r_out(z)
                n = Vector((math.cos(a0), math.sin(a0), (Rb - Rt) / H)).normalized()
                extra.append((Vector((r_out(z) * math.cos(a0), r_out(z) * math.sin(a0), z)), n, rb, 2, 1.35))
                for k in range(rng.randint(3, 7)):          # residue left along the run
                    zz = rng.uniform(z0 + rb * 2.5, z1)
                    aa = ta - math.sin(zz * 260.0 + i * 1.7) * w * 0.6 / r_out(zz) + rng.uniform(-0.3, 0.3) * w / r_out(zz)
                    nn = Vector((math.cos(aa), math.sin(aa), (Rb - Rt) / H)).normalized()
                    rr = rng.uniform(0.00025, 0.0006)
                    extra.append((Vector((r_out(zz) * math.cos(aa), r_out(zz) * math.sin(aa), zz)), nn, rr, 1,
                                  rng.uniform(1.4, 2.4)))
            parts["drops"] = scatter_drops(name + "_drops", surf, n_drops, 0.00012, 0.0026, alpha=2.35,
                                           seed=seed + 11, coll=coll, extra=extra)
            parent(parts["drops"], root)
    return Prop(root, info, **parts)


# =========================================================================== bottle
def label_art(seed=0, px_per_mm=25, size_mm=(64.0, 86.0)):
    """Draw OUR bottle label with PIL (no stag, crest or logo; not a copy of real artwork):
    bone paper, Jaeger-orange edge band, 'JAGERMEISTER' / 'Krauterlikor' / '35% vol' / '0,7 L'.
    Returns (rgba_path, ink_mask_path) in textures/."""
    cpath = os.path.join(S.TEXTURES, f"label_{seed}.png")
    ipath = os.path.join(S.TEXTURES, f"label_{seed}_ink.png")
    if os.path.exists(cpath) and os.path.exists(ipath):
        return cpath, ipath
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops
    os.makedirs(S.TEXTURES, exist_ok=True)
    rng = np.random.default_rng(500 + seed)
    W, H = int(size_mm[0] * px_per_mm), int(size_mm[1] * px_per_mm)
    mm = px_per_mm

    def font(key, size_mm_):
        return ImageFont.truetype(S.FONTS[key], int(size_mm_ * mm))

    def noise(sigma, shape=(H, W)):
        a = Image.fromarray((rng.random(shape) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(sigma))
        x = np.asarray(a).astype(np.float32)
        return (x - x.mean()) / (x.std() + 1e-6)

    paper = np.array([0.905, 0.862, 0.765], np.float32)            # warm bone stock
    orange = np.array([0.910, 0.376, 0.110], np.float32)           # #E8601C
    black = np.array([0.075, 0.060, 0.050], np.float32)
    brown = np.array([0.28, 0.16, 0.08], np.float32)
    # layers drawn as masks (L images) then composited
    ink_black = Image.new("L", (W, H), 0)
    ink_orange = Image.new("L", (W, H), 0)
    ink_brown = Image.new("L", (W, H), 0)
    db, do, dbr = ImageDraw.Draw(ink_black), ImageDraw.Draw(ink_orange), ImageDraw.Draw(ink_brown)
    cut = 5.0 * mm                                                   # chamfered corners

    def octagon(inset):
        c = max(cut - inset * 0.4, 0)
        x0, y0, x1, y1 = inset, inset, W - 1 - inset, H - 1 - inset
        return [(x0 + c, y0), (x1 - c, y0), (x1, y0 + c), (x1, y1 - c), (x1 - c, y1), (x0 + c, y1), (x0, y1 - c),
                (x0, y0 + c)]
    # shape alpha
    alpha = Image.new("L", (W, H), 0)
    ImageDraw.Draw(alpha).polygon(octagon(0), fill=255)
    # orange edge band (3.2 mm) with a fine keyline inside it
    do.polygon(octagon(0), fill=255)
    do.polygon(octagon(3.2 * mm), fill=0)
    db.line(octagon(3.6 * mm) + [octagon(3.6 * mm)[0]], fill=255, width=max(2, int(0.28 * mm)))
    db.line(octagon(4.4 * mm) + [octagon(4.4 * mm)[0]], fill=255, width=max(1, int(0.12 * mm)))
    cx = W // 2

    def text(d, s, key, size, y, anchor="mm", track=0.0, x=None):
        f = font(key, size)
        x = cx if x is None else x
        if not track:
            d.text((x, y), s, font=f, fill=255, anchor=anchor)
            return
        widths = [f.getlength(ch) for ch in s]
        total = sum(widths) + track * mm * (len(s) - 1)
        xx = x - total / 2 if anchor[0] == "m" else x
        for ch, w in zip(s, widths):
            d.text((xx, y), ch, font=f, fill=255, anchor="l" + anchor[1])
            xx += w + track * mm
    # header rule pair
    y = 11.0 * mm
    db.line([(9 * mm, y), (W - 9 * mm, y)], fill=255, width=int(0.35 * mm))
    db.line([(9 * mm, y + 0.9 * mm), (W - 9 * mm, y + 0.9 * mm)], fill=255, width=max(1, int(0.12 * mm)))
    text(dbr, "KRÄUTER · LIKÖR · SPIRITUOSE", "inter_semibold", 1.9, 15.0 * mm, track=0.55)
    # the name
    name = "JÄGERMEISTER"
    size = 7.6
    while size > 3.0:       # largest size that fits with +0.45 mm tracking inside the rules
        w_name = font("display_black", size).getlength(name) + 0.45 * mm * (len(name) - 1)
        if w_name <= W - 15.0 * mm:
            break
        size -= 0.1
    text(db, name, "display_black", size, 25.5 * mm, track=0.45)
    text(dbr, "Kräuterlikör", "display_light_italic", 6.4, 36.5 * mm)
    # guilloche band (our own pattern): interleaved sine lines between two orange rules
    y0, y1 = 44.0 * mm, 56.0 * mm
    do.line([(8 * mm, y0), (W - 8 * mm, y0)], fill=255, width=int(0.3 * mm))
    do.line([(8 * mm, y1), (W - 8 * mm, y1)], fill=255, width=int(0.3 * mm))
    xs = np.linspace(8 * mm, W - 8 * mm, 900)
    for k in range(9):
        ph = k * 2 * math.pi / 9
        ys = (y0 + y1) / 2 + (y1 - y0) * 0.36 * np.sin(xs / (3.1 * mm) + ph) * np.cos(xs / (17 * mm) + ph * 0.3)
        do.line(list(zip(xs.tolist(), ys.tolist())), fill=255, width=max(1, int(0.13 * mm)))
    text(db, "Blüten · Wurzeln · Rinden · Früchte", "inter_medium", 2.15, 61.5 * mm)
    text(dbr, "gereift in Eichenfässern", "display_italic", 2.4, 66.0 * mm)
    # bottom rule and declarations
    y = 72.0 * mm
    db.line([(9 * mm, y), (W - 9 * mm, y)], fill=255, width=int(0.3 * mm))
    text(db, "35% vol", "inter_semibold", 3.4, 77.2 * mm, anchor="lm", x=10.0 * mm)
    text(db, "0,7 L", "inter_semibold", 3.4, 77.2 * mm, anchor="rm", x=W - 10.0 * mm)

    def arr(im):
        return np.asarray(im).astype(np.float32) / 255.0
    kb, ko, kbr = arr(ink_black), arr(ink_orange), arr(ink_brown)
    # misregistration of the orange plate (~0.08 mm) and ink density breakup
    sh = int(round(0.08 * mm))
    ko = np.roll(np.roll(ko, sh, axis=1), -sh, axis=0)
    dens = np.clip(0.95 + 0.035 * noise(2.0) + 0.025 * noise(0.7), 0.8, 1.0)
    kb, ko, kbr = kb * dens, ko * np.clip(dens + 0.03, 0, 1), kbr * dens
    # paper: mottling + fibres
    fib = 0.016 * noise(1.2) + 0.010 * noise(30) + 0.006 * noise(6)
    col = np.ones((H, W, 3), np.float32) * paper[None, None]
    col *= (1 + fib)[..., None]
    for k, c in ((ko, orange), (kbr, brown), (kb, black)):
        col = col * (1 - k[..., None]) + c[None, None] * k[..., None]
    # edge wear: scuffed paper near the edges + corners, light dirt in the lower third
    a = arr(alpha)
    dist = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.6 * mm)))
    dist = dist.astype(np.float32) / 255.0
    edge = np.clip((0.75 - dist) * 3.0, 0, 1) * a
    scuff = np.clip(noise(3.0) * 0.7 + noise(0.8) * 0.4 - 0.55, 0, 1) * edge
    col = col * (1 - scuff[..., None] * 0.55) + np.array([0.95, 0.93, 0.88])[None, None] * scuff[..., None] * 0.55
    ink_total = np.clip(kb + ko + kbr, 0, 1) * (1 - scuff * 0.8)
    yy = np.linspace(0, 1, H)[:, None]
    dirt = np.clip(noise(25) * 0.5 + 0.2, 0, 1) * np.clip((yy - 0.6) * 2.5, 0, 1) * 0.06
    col *= (1 - dirt)[..., None]
    # alpha: slightly eroded corners
    er = np.clip(noise(1.5) * 0.5 + 0.5, 0, 1)
    a = np.where((dist < 0.32) & (er < 0.25), 0.0, a)
    rgba = np.dstack([np.clip(col, 0, 1), a])
    Image.fromarray((rgba * 255).astype(np.uint8), "RGBA").save(cpath)
    Image.fromarray((np.clip(ink_total, 0, 1) * 255).astype(np.uint8), "L").save(ipath)
    return cpath, ipath


def bottle(name="Bottle", location=(0, 0, 0), rotation_z_deg=0.0, frosted=False, fill=0.93, label=True, cap=True,
           seed=0, coll=None, n_around=128, frost=0.8, liquid_material=None, glass_color=(0.13, 0.30, 0.13),
           glass_density=180.0, frost_track=None, frost_density=0.8):
    """Square-shouldered green glass bottle, ~0.7 L proportions: 72 mm square body with 11 mm corner
    radius, flat shoulders into a round neck, black knurled screw cap; 3.5 mm walls, 9 mm base.
    Total height ~243 mm.  The label faces -Y (before rotation_z_deg).
    fill: fraction of the body+shoulder height (0.93 ~ into the shoulder).
    frosted: freezer frost on the glass and a damp, frosted label."""
    A, RC, ZS, ZN, RN, ZL = 0.036, 0.011, 0.168, 0.186, 0.0148, 0.2335
    tw, tb = 0.0035, 0.009
    rng = random.Random(seed)
    root = _root(name, location, rotation_z_deg - 90.0, coll)     # +X face -> -Y after the -90 deg turn

    def rc_out(a, z):
        if z < 0.03:                      # base bevel: offset curve of the body section
            return max(RC - (A - a), 0.002)
        s = min(max((A - a) / (A - RN), 0.0), 1.0)
        s = s ** 0.8
        return min(RC + s * (RN - RC), a)

    def section_for(inner):
        def sec(a, z, tag):
            if inner:
                ao = a + tw
                rc = rc_out(ao, z) - tw
                rc = max(rc, 0.0015) if a > RN - tw + 1e-4 else a
                rc = min(rc, a)
            else:
                rc = rc_out(a, z)
            return rounded_rect(a, rc, n_around)
        return sec
    # outer profile (a = half width)
    outer = [(0.0, 0.0022), (A - 0.012, 0.0002), (A - 0.0045, 0.0), (A, 0.0055), (A, ZS), (RN + 0.0012, ZN),
             (RN, ZN + 0.004), (RN - 0.0003, ZL - 0.004), (RN - 0.0011, ZL)]
    outer, otag = fillet(outer, [0, 0.008, 0.002, 0.003, 0.011, 0.004, 0.003, 0.0, 0], steps=8)
    # lip: rounded top of the finish
    lip_c = (RN - 0.0011 - 0.0022, ZL)
    lip = [(lip_c[0] + 0.0022 * math.cos(a), lip_c[1] + 0.0016 * math.sin(a)) for a in np.linspace(0, math.pi, 9)[1:-1]]
    rb = RN - 0.0011 - 0.0044
    inner_dn = [(rb, ZL), (rb, ZN + 0.002), (A - tw, ZS - 0.001), (A - tw, tb + 0.004), (A - tw - 0.006, tb), (0.0, tb + 0.0012)]
    inner_dn, itag = fillet(inner_dn, [0, 0.006, 0.010, 0.004, 0.003, 0], steps=8)
    o_res, o_t = resample(outer, 0.004)
    i_res, i_t = resample(inner_dn, 0.004)

    def disp(V, ring, tag):
        # glass waviness: low-frequency bumps of ~0.12 mm on the walls (not the lip/base)
        out = V.copy()
        off = Vector((rng.uniform(0, 100), rng.uniform(0, 100), rng.uniform(0, 100)))
        for i, v in enumerate(V):
            if 0.01 < v[2] < ZN:
                p = Vector(v) * 38.0 + off
                d = mnoise.noise(p) * 0.00012 + mnoise.noise(p * 3.1) * 0.00004
                rxy = math.hypot(v[0], v[1]) + 1e-9
                out[i, 0] += v[0] / rxy * d
                out[i, 1] += v[1] / rxy * d
        return out
    # build outer + lip + inner as one loft (sections switch with the 'inner' tag)
    prof = o_res + lip + i_res
    tags = [0] * len(o_res) + [0.5] * len(lip) + [1] * len(i_res)
    sec_o, sec_i = section_for(False), section_for(True)

    def sec(a, z, tag):
        if tag >= 1:
            return sec_i(a, z, tag)
        if tag > 0:
            return circle_section(n_around)(a, z, tag)
        return sec_o(a, z, tag)
    g = loft(name + "_glass", prof, sec, tags, coll, displace=disp)
    parent(g, root)
    g.data.materials.append(M.glass(name + "_GlassMat", absorb=glass_color, density=glass_density, smudge=0.05,
                                    radius=A, seed=seed, shadow=(0.25, 0.4, 0.25)))
    info = dict(height=ZL + 0.0016, body_half_width=A, shoulder_z=ZS, neck_z=ZN)
    parts = dict(glass=g, liquid=None, label=None, cap=None, frost=None)
    if frosted:
        parts["frost"] = frost_shell(g, coverage=frost, wipes=2, radius=A, seed=seed, offset=0.00015, coll=coll,
                                     track=frost_track, density=frost_density)
    # liquid
    if fill:
        inner_up = list(reversed(i_res))
        fill_z = tb + (ZN + 0.01 - tb) * fill
        lp = _liquid_profile(inner_up, fill_z, meniscus=0.0008, men_len=0.001)

        def sec_l(a, z, tag):
            return sec_i(a, z, 1)
        lq = loft(name + "_liquid", lp, sec_l, None, coll)
        parent(lq, root)
        lq.data.materials.append(liquid_material or M.jagermeister(name + "_Jager"))
        parts["liquid"] = lq
        info["fill_z"] = fill_z
    # label on the +X face (wraps onto the corner radii)
    if label:
        cpath, ipath = label_art(seed % 3)
        lw, lh, zc = 0.064, 0.086, 0.088
        nu, nv = 72, 40
        ring = rounded_rect(A, RC, 4096)
        per = np.linalg.norm(np.diff(np.vstack([ring, ring[:1]]), axis=0), axis=1)
        cum = np.concatenate([[0], np.cumsum(per)])
        P_ = np.vstack([ring, ring[:1]])
        total = cum[-1]

        def at(s):
            s = s % total
            k = int(np.searchsorted(cum, s, side="right") - 1)
            f = (s - cum[k]) / (per[k] + 1e-12)
            p = P_[k] + (P_[k + 1] - P_[k]) * f
            tvec = (P_[k + 1] - P_[k]) / (per[k] + 1e-12)
            return p, np.array([tvec[1], -tvec[0]])
        verts, faces, uvs = [], [], []
        for j in range(nv + 1):
            z = zc - lh / 2 + lh * j / nv
            for i in range(nu + 1):
                s = -lw / 2 + lw * i / nu
                p, n = at(s)
                bulge = 0.00035 + 0.00006 * math.sin(i * 0.7 + j * 0.3)
                verts.append((p[0] + n[0] * bulge, p[1] + n[1] * bulge, z))
        for j in range(nv):
            for i in range(nu):
                a_ = j * (nu + 1) + i
                faces.append((a_, a_ + 1, a_ + nu + 2, a_ + nu + 1))
                uvs.append([(i / nu, j / nv), ((i + 1) / nu, j / nv), ((i + 1) / nu, (j + 1) / nv), (i / nu, (j + 1) / nv)])
        lb = mesh(name + "_label", verts, faces, coll, True, uvs)
        parent(lb, root)
        lm = M.label(cpath, ipath, name + "_LabelMat", seed=seed, wet=0.6 if frosted else 0.0,
                     frost=0.5 if frosted else 0.0)
        _label_alpha(lm, cpath)
        lb.data.materials.append(lm)
        parts["label"] = lb
    if cap:
        parts["cap"] = screw_cap(name + "_cap", z0=ZL - 0.031, radius=RN + 0.0014, height=0.0335, seed=seed, coll=coll)
        parent(parts["cap"], root)
    return Prop(root, info, **parts)


def _label_alpha(mat, cpath):
    """Cut the label outline with the artwork's alpha (mix to Transparent)."""
    t = M.Tree(mat)
    nt = mat.node_tree
    out = [n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial"][0]
    surf = out.inputs["Surface"].links[0].from_socket
    a = t.image(cpath, t.texco("UV"), out="Alpha")
    tr = t.node("ShaderNodeBsdfTransparent")
    mix = t.node("ShaderNodeMixShader")
    t.link(a, mix.inputs[0])
    t.link(tr, mix.inputs[1])
    nt.links.new(surf, mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])


def screw_cap(name="Cap", z0=0.0, radius=0.0162, height=0.0335, ridges=96, seed=0, coll=None, material=None):
    """Black knurled screw cap (closed solid), base at z0.  Vertical ridges 0.25 mm deep."""
    n = ridges * 4
    th = np.linspace(0, 2 * math.pi, n, endpoint=False)
    kn = 0.5 + 0.5 * np.cos(ridges * th)
    kn = np.clip(kn * 1.6 - 0.3, 0, 1)
    prof = [(radius - 0.0042, 0.0), (radius - 0.0006, 0.0), (radius, 0.0008), (radius, height - 0.0035),
            (radius - 0.0006, height - 0.0005), (radius - 0.003, height), (0.0, height + 0.0004)]
    prof, tags = fillet(prof, [0, 0.0004, 0.0006, 0.0012, 0.0008, 0.002, 0], steps=5)
    prof, tags = resample(prof, 0.0015, tags)
    # inner bottom closes the solid (hidden against the neck)
    prof = [(0.0, 0.0015)] + prof

    def sec(a, z, tag):
        rr = np.full(n, a)
        if a >= radius - 0.00001 and 0.002 < z < height - 0.004:
            fade = min(1.0, (z - 0.002) / 0.0015, (height - 0.004 - z) / 0.0015)
            rr = a - 0.00025 * (1 - kn) * fade
        return np.stack([rr * np.cos(th), rr * np.sin(th)], 1)
    prof_shift = [(a, z + z0) for a, z in prof]
    ob = loft(name, prof_shift, lambda a, z, t: sec(a, z - z0, t), None, coll)
    ob.data.materials.append(material or M.plastic((0.012, 0.012, 0.012), 0.32, name + "_Mat", seed=seed, scuffs=0.4,
                                                   coat=0.3))
    return ob


# =========================================================================== small props
def coaster(name="Coaster", location=(0, 0, 0), radius=0.05, seed=0, coll=None):
    """Cork coaster, 100 mm x 4 mm with 1 mm rounded edges.  Stand glasses at z = COASTER_H."""
    prof = [(0.0, 0.0), (radius, 0.0), (radius, COASTER_H), (0.0, COASTER_H)]
    prof, tags = fillet(prof, [0, 0.001, 0.001, 0], steps=5)
    ob = lathe(name, prof, 96, coll=coll, wobble=0.004, seed=seed)
    ob.location = location
    ob.data.materials.append(M.cork(name + "_Cork", seed=seed))
    return ob


def slab(name="Table", size=(1.2, 0.8, 0.04), location=(0, 0, 0), bevel=0.003, material=None, coll=None):
    """Bevelled box whose TOP face sits at location z (table tops, bar counters, shelves)."""
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    ob = bpy.context.object
    ob.name = name
    ob.scale = size
    ob.location = (location[0], location[1], location[2] - size[2] / 2)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    md = ob.modifiers.new("bevel", "BEVEL")
    md.width = bevel
    md.segments = 3
    md.limit_method = "NONE"
    S.link(ob, coll)
    for p in ob.data.polygons:
        p.use_smooth = False
    if material:
        ob.data.materials.append(material)
    return ob
