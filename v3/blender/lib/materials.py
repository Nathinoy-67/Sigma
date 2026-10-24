"""materials.py -- physically based, imperfect material library (Cycles).

    import materials as M
    M.glass(ior=1.52, smudge=0.05)            # clear glass, fingerprints/smudges in roughness
    M.glass(frost=0.85)                        # straight from the freezer (frost mask on outer faces)
    M.glass(fog_top=0.10)                      # condensation fog below z=10 cm (object space)
    M.jagermeister()  M.energy_drink()  M.water()  M.bubble()  M.foam()
    M.wood("dark_table")  M.wood("oak_scrubbed")  M.wood("fir_lacquer")
    M.metal("brass") M.metal("chrome") M.metal("steel_brushed") M.metal("iron")
    M.plastic(color, roughness)  M.paper(image=...)  M.label(image, ink_mask)  M.cork()
    M.chalk() M.brick() M.plaster() M.rubber() M.enamel(color) M.emission(color/kelvin, strength)
    M.matte_black()  M.flag()

Measured indices: glass 1.52, energy drink 1.34, Jagermeister 1.355, water 1.333, ice 1.31.
Volume colours follow Blender's convention: absorption coefficient = (1 - color) * density  [1/m].

Conventions used by the shaders:
  * procedural textures use Object coordinates in metres (so they scale with the real object);
  * glass reads the mesh attribute "inner" (1 on inner faces, 0 outside) built by props.lathe /
    props.loft so fingerprints, frost and fog only touch the outside;
  * every material takes `seed` so repeated objects never share the same pattern.

`Tree` is a tiny node-graph builder also used by props.py / botanicals.py and by set builders.
"""
import math
import os
import random

import bpy

import scene as S

# --------------------------------------------------------------------------- node builder


class Tree:
    """Minimal node-graph builder.  Values passed as inputs may be numbers/tuples (set as
    default) or sockets/nodes (linked).  Inputs may be addressed by name or index."""

    def __init__(self, owner):
        self.nt = owner.node_tree if hasattr(owner, "node_tree") else owner
        self._tc = None
        self._geo = None

    # -- raw
    def node(self, kind, inputs=None, **props):
        n = self.nt.nodes.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        for k, v in (inputs or {}).items():
            self.set(n.inputs[k], v)
        return n

    def set(self, sock, v):
        if v is None:
            return
        if isinstance(v, bpy.types.Node):
            v = v.outputs[0]
        if isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v, sock)
            return
        dv = sock.default_value
        try:
            n = len(dv)
        except TypeError:
            n = 0
        if n == 4 and isinstance(v, (tuple, list)) and len(v) == 3:
            v = (*v, 1.0)
        elif n in (3, 4) and isinstance(v, (int, float)):
            v = tuple([float(v)] * n)
        sock.default_value = v

    def link(self, a, b):
        if isinstance(a, bpy.types.Node):
            a = a.outputs[0]
        self.nt.links.new(a, b)

    # -- coordinates
    def texco(self, kind="Object"):
        if self._tc is None:
            self._tc = self.node("ShaderNodeTexCoord")
        return self._tc.outputs[kind]

    def geo(self, kind="Position"):
        if self._geo is None:
            self._geo = self.node("ShaderNodeNewGeometry")
        return self._geo.outputs[kind]

    def mapping(self, vec=None, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
        return self.node("ShaderNodeMapping", {"Vector": vec if vec is not None else self.texco(),
                                               "Location": loc, "Rotation": rot, "Scale": scale}).outputs[0]

    def xyz(self, vec):
        n = self.node("ShaderNodeSeparateXYZ", {0: vec})
        return n.outputs[0], n.outputs[1], n.outputs[2]

    def combine(self, x=0.0, y=0.0, z=0.0):
        return self.node("ShaderNodeCombineXYZ", {0: x, 1: y, 2: z}).outputs[0]

    def attr(self, name, out="Factor"):
        return self.node("ShaderNodeAttribute", attribute_name=name).outputs[out]

    # -- math
    def math(self, op, a, b=0.0, c=0.0, clamp=False):
        return self.node("ShaderNodeMath", {0: a, 1: b, 2: c}, operation=op, use_clamp=clamp).outputs[0]

    def add(self, a, b, clamp=False):
        return self.math("ADD", a, b, clamp=clamp)

    def mul(self, a, b, clamp=False):
        return self.math("MULTIPLY", a, b, clamp=clamp)

    def vmath(self, op, a, b=(0, 0, 0), scale=1.0):
        n = self.node("ShaderNodeVectorMath", {0: a, 1: b}, operation=op)
        if op == "SCALE":
            n.inputs["Scale"].default_value = scale
        return n.outputs["Value"] if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else n.outputs[0]

    def map(self, v, a, b, c=0.0, d=1.0, clamp=True, interp="LINEAR"):
        return self.node("ShaderNodeMapRange", {0: v, 1: a, 2: b, 3: c, 4: d},
                         clamp=clamp, interpolation_type=interp).outputs[0]

    def smooth(self, v, a, b):
        """smoothstep(a, b, v) -> 0..1"""
        return self.map(v, a, b, 0.0, 1.0, True, "SMOOTHSTEP")

    def mixf(self, fac, a, b):
        return self.node("ShaderNodeMix", {0: fac, 2: a, 3: b}, data_type="FLOAT").outputs[0]

    def mixc(self, fac, a, b, blend="MIX", clamp=False):
        n = self.node("ShaderNodeMix", {0: fac, 6: a, 7: b}, data_type="RGBA", blend_type=blend)
        n.clamp_result = clamp
        return n.outputs[2]

    def mixv(self, fac, a, b):
        return self.node("ShaderNodeMix", {0: fac, 4: a, 5: b}, data_type="VECTOR").outputs[1]

    def ramp(self, fac, stops, interp="LINEAR"):
        """stops = [(pos, (r, g, b)), ...] -> color socket"""
        n = self.node("ShaderNodeValToRGB", {0: fac})
        cr = n.color_ramp
        cr.interpolation = interp
        els = cr.elements
        while len(els) > len(stops):
            els.remove(els[-1])
        while len(els) < len(stops):
            els.new(0.5)
        for e, (p, c) in zip(els, stops):
            e.position = p
            e.color = (*c[:3], 1.0) if len(c) == 3 else c
        return n.outputs[0]

    # -- textures
    def noise(self, vec=None, scale=5.0, detail=4.0, rough=0.5, distortion=0.0, w=None, kind="FBM",
              lac=2.0, out="Factor", dims=None):
        dims = dims or ("4D" if w is not None else "3D")
        n = self.node("ShaderNodeTexNoise", {0: vec if vec is not None else self.texco(), 2: scale, 3: detail,
                                             4: rough, 5: lac, 8: distortion},
                      noise_dimensions=dims, noise_type=kind)
        if w is not None:
            self.set(n.inputs[1], w)
        return n.outputs[0 if out == "Factor" else 1]

    def voronoi(self, vec=None, scale=5.0, rand=1.0, feature="F1", metric="EUCLIDEAN", out="Distance",
                w=None, smooth=None, detail=0.0):
        dims = "4D" if w is not None else "3D"
        n = self.node("ShaderNodeTexVoronoi", {0: vec if vec is not None else self.texco(), 2: scale, 3: detail,
                                               8: rand},
                      voronoi_dimensions=dims, feature=feature, distance=metric)
        if w is not None:
            self.set(n.inputs[1], w)
        if smooth is not None:
            self.set(n.inputs[6], smooth)
        return n.outputs[out]

    def wave(self, vec=None, scale=5.0, distortion=0.0, detail=2.0, dscale=1.0, drough=0.5, kind="BANDS",
             direction="X", profile="SIN", phase=0.0, out="Factor"):
        n = self.node("ShaderNodeTexWave", {0: vec if vec is not None else self.texco(), 1: scale, 2: distortion,
                                            3: detail, 4: dscale, 5: drough, 6: phase},
                      wave_type=kind, wave_profile=profile)
        if kind == "BANDS":
            n.bands_direction = direction
        else:
            n.rings_direction = direction
        return n.outputs[1 if out == "Factor" else 0]

    def white(self, vec=None, w=None, out="Value"):
        dims = "1D" if vec is None else ("4D" if w is not None else "3D")
        n = self.node("ShaderNodeTexWhiteNoise", {0: vec if vec is not None else (0, 0, 0)}, noise_dimensions=dims)
        if w is not None:
            self.set(n.inputs[1], w)
        return n.outputs[out]

    def image(self, path, vec=None, colorspace="sRGB", interp="Cubic", extension="REPEAT", out="Color"):
        img = bpy.data.images.load(path, check_existing=True)
        img.colorspace_settings.name = colorspace
        n = self.node("ShaderNodeTexImage", interpolation=interp, extension=extension)
        n.image = img
        if vec is not None:
            self.set(n.inputs[0], vec)
        return n.outputs[out]

    def bump(self, height, strength=0.2, distance=0.001, normal=None):
        n = self.node("ShaderNodeBump", {"Height": height, "Strength": strength, "Distance": distance})
        if normal is not None:
            self.set(n.inputs["Normal"], normal)
        return n.outputs[0]

    # -- shaders
    def principled(self, **inp):
        mapping = {"base": "Base Color", "color": "Base Color", "metallic": "Metallic", "rough": "Roughness",
                   "roughness": "Roughness", "ior": "IOR", "alpha": "Alpha", "normal": "Normal",
                   "transmission": "Transmission Weight", "coat": "Coat Weight", "coat_rough": "Coat Roughness",
                   "coat_ior": "Coat IOR", "coat_tint": "Coat Tint", "coat_normal": "Coat Normal",
                   "sheen": "Sheen Weight", "sheen_rough": "Sheen Roughness", "sheen_tint": "Sheen Tint",
                   "sss": "Subsurface Weight", "sss_radius": "Subsurface Radius", "sss_scale": "Subsurface Scale",
                   "sss_aniso": "Subsurface Anisotropy", "spec": "Specular IOR Level", "spec_tint": "Specular Tint",
                   "aniso": "Anisotropic", "aniso_rot": "Anisotropic Rotation", "tangent": "Tangent",
                   "emission": "Emission Color", "emission_strength": "Emission Strength",
                   "thin_film": "Thin Film Thickness", "diffuse_rough": "Diffuse Roughness"}
        n = self.node("ShaderNodeBsdfPrincipled")
        for k, v in inp.items():
            self.set(n.inputs[mapping.get(k, k)], v)
        return n

    def mix_shader(self, fac, a, b):
        n = self.node("ShaderNodeMixShader")
        self.set(n.inputs[0], fac)
        self.link(a, n.inputs[1])
        self.link(b, n.inputs[2])
        return n

    def add_shader(self, a, b):
        n = self.node("ShaderNodeAddShader")
        self.link(a, n.inputs[0])
        self.link(b, n.inputs[1])
        return n

    def output(self, surface=None, volume=None, displacement=None):
        out = self.node("ShaderNodeOutputMaterial", target="ALL")
        if surface is not None:
            self.link(surface, out.inputs["Surface"])
        if volume is not None:
            self.link(volume, out.inputs["Volume"])
        if displacement is not None:
            self.link(displacement, out.inputs["Displacement"])
        return out


def new_material(name):
    m = bpy.data.materials.new(name)
    if m.node_tree is None:
        m.use_nodes = True
    m.node_tree.nodes.clear()
    return m, Tree(m)


def assign(obj, mat, slot=None):
    """Append (or replace slot index) a material on an object."""
    if slot is None:
        obj.data.materials.append(mat)
    else:
        while len(obj.data.materials) <= slot:
            obj.data.materials.append(None)
        obj.data.materials[slot] = mat
    return mat


def _rnd(seed, salt=0):
    r = random.Random(seed * 7919 + salt * 104729 + 17)
    return r


def _seed_vec(t, seed, salt=0):
    """Offset Object coordinates by a seed-specific vector so patterns differ per object."""
    r = _rnd(seed, salt)
    return t.mapping(t.texco(), loc=(r.uniform(-50, 50), r.uniform(-50, 50), r.uniform(-50, 50)))


def _outer_mask(t):
    """1 on outside faces, 0 on inner faces (mesh attribute 'inner')."""
    return t.math("SUBTRACT", 1.0, t.attr("inner"), clamp=True)


def _shadow_mix(t, surface, transmit):
    """Glass/liquid shadow trick (caustics are off): shadow rays see a tinted Transparent BSDF."""
    if transmit is None:
        return surface
    tr = t.node("ShaderNodeBsdfTransparent", {0: transmit})
    lp = t.node("ShaderNodeLightPath")
    return t.mix_shader(lp.outputs["Is Shadow Ray"], surface, tr)


# --------------------------------------------------------------------------- textures (PIL / numpy)
def smudge_texture(seed=0, size=(2048, 1024)):
    """Greasy smudges, cloth-wipe arcs and partial fingerprints as a grey roughness mask
    (0 = clean).  The image represents a 0.20 m x 0.10 m patch of glass (10 px/mm).
    Cached in textures/smudge_<seed>.png."""
    path = os.path.join(S.TEXTURES, f"smudge_{seed}.png")
    if os.path.exists(path):
        return path
    import numpy as np
    from PIL import Image, ImageFilter
    os.makedirs(S.TEXTURES, exist_ok=True)
    W, H = size
    rng = np.random.default_rng(1000 + seed)

    def blurred_noise(sigma, amp=1.0):
        a = Image.fromarray((rng.random((H, W)) * 255).astype(np.uint8))
        a = a.filter(ImageFilter.GaussianBlur(sigma))
        x = np.asarray(a).astype(np.float32) / 255.0
        x = (x - x.mean()) / (x.std() + 1e-6)
        return x * amp

    out = np.zeros((H, W), np.float32)
    # greasy haze
    haze = blurred_noise(60) + 0.5 * blurred_noise(18)
    out += np.clip(haze * 0.18 - 0.05, 0, 1)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    # cloth wipe arcs: faint parallel striations along big circular arcs
    for _ in range(3):
        cx, cy = rng.uniform(0, W), rng.uniform(-H, 2 * H)
        R = rng.uniform(0.6, 1.4) * H
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        band = np.exp(-((d - R) / rng.uniform(40, 90)) ** 2)
        stri = 0.5 + 0.5 * np.sin(d * rng.uniform(0.6, 1.2) + blurred_noise(4, 1.5))
        out += band * stri * rng.uniform(0.12, 0.25)
    # fingerprints (ridge spacing ~0.45 mm = 4.5 px)
    warp = blurred_noise(25, 6.0)
    for _ in range(int(rng.integers(5, 9))):
        cx, cy = rng.uniform(0, W), rng.uniform(0, H)
        a_, b_ = rng.uniform(55, 80), rng.uniform(75, 110)
        th = rng.uniform(0, math.pi)
        x = (xx - cx) * math.cos(th) + (yy - cy) * math.sin(th)
        y = -(xx - cx) * math.sin(th) + (yy - cy) * math.cos(th)
        dn = np.sqrt((x / a_) ** 2 + (y / b_) ** 2)
        # loop-style core: shift rings upward on one side
        phase = np.sqrt(x ** 2 + (y * a_ / b_) ** 2 + 0.0) / 4.6 + 0.35 * np.tanh(x / 30.0) * (y < 0) * 3 + warp
        ridges = 0.5 + 0.5 * np.cos(2 * math.pi * phase)
        m = np.clip((1.0 - dn) * 3.0, 0, 1) * np.clip(blurred_noise(10) * 0.6 + 0.7, 0, 1)
        if rng.random() < 0.5:   # partial / smeared print
            m *= np.clip((x * rng.choice([-1, 1])) / (a_ * 0.6) + 0.6, 0, 1)
        out += ridges * m * rng.uniform(0.35, 0.6)
    out = np.clip(out, 0, 1)
    Image.fromarray((out * 255).astype(np.uint8)).save(path)
    return path


def _smudge_mask(t, seed, radius=0.03, patch=(0.20, 0.10), z0=0.0):
    """Cylindrical projection of the smudge texture around the object's Z axis."""
    x, y, z = t.xyz(t.texco())
    ang = t.math("ARCTAN2", y, x)
    u = t.math("MULTIPLY", ang, radius / patch[0])
    r = _rnd(seed, 3)
    v = t.math("MULTIPLY", t.add(z, r.uniform(0, 0.1) - z0), 1.0 / patch[1])
    vec = t.combine(t.add(u, r.uniform(0, 1)), v, 0.0)
    return t.image(smudge_texture(seed % 4), vec, colorspace="Non-Color", out="Color")


# --------------------------------------------------------------------------- glass
def glass(name="Glass", ior=1.52, roughness=0.0, color=(1.0, 1.0, 1.0), absorb=None, density=0.0,
          smudge=0.06, radius=0.03, wavy=0.02, frost=0.0, frost_wipes=0, fog_top=None, fog=0.13,
          shadow=(0.85, 0.85, 0.85), seed=0, trails=()):
    """Dielectric glass.
    absorb/density : body tint by volume absorption (e.g. green bottle glass) -- thickness dependent.
    smudge         : extra roughness from fingerprints/grease on the outside (0 = spotless).
    radius         : object radius (m) for the cylindrical smudge projection.
    wavy           : bump strength of the slight unevenness of pressed/blown glass.
    frost          : 0..1 coverage of freezer frost on the outside (1 = fully white-frosted).
    frost_wipes    : number of clear finger-wiped patches in the frost.
    fog_top        : z (object space, m) below which the outside is fogged by micro-condensation.
    trails         : [(azimuth_rad, z_bottom, z_top, half_width), ...] runs that swept the fog clean.
    shadow         : transparent colour seen by shadow rays (None = opaque shadows)."""
    m, t = new_material(name)
    outer = _outer_mask(t)
    sm = t.mul(_smudge_mask(t, seed, radius), smudge)
    sm = t.mul(sm, outer)
    rough = t.add(roughness, sm)
    # unevenness of the glass surface (very low frequency ripples)
    p = _seed_vec(t, seed, 1)
    ripple = t.noise(p, scale=18.0, detail=2.0, rough=0.4)
    nrm = t.bump(ripple, strength=wavy, distance=0.002) if wavy else None
    surf_mask = None
    if fog_top is not None:
        # fog: micro-droplets make the outside rough below the cold liquid line, broken by run trails
        x, y, z = t.xyz(t.texco())
        edge = t.noise(p, scale=60.0, detail=3.0)
        below = t.math("SUBTRACT", 1.0, t.smooth(t.add(z, t.mul(t.add(edge, -0.5), 0.006)), fog_top - 0.004, fog_top + 0.002))
        trails_vec = t.mapping(p, scale=(220.0, 220.0, 6.0))
        clear = t.mul(t.smooth(t.noise(trails_vec, scale=1.0, detail=1.0), 0.70, 0.74), 0.6)
        for i, (ta, z0, z1, w) in enumerate(trails):
            ca, sa = math.cos(ta), math.sin(ta)
            wob = t.mul(t.math("SINE", t.add(t.mul(z, 260.0), i * 1.7)), w * 0.6)
            lat = t.math("ABSOLUTE", t.add(t.add(t.mul(x, -sa), t.mul(y, ca)), wob))
            front = t.smooth(t.add(t.mul(x, ca), t.mul(y, sa)), 0.0, 0.004)
            taper = t.map(z, z0, z1, w, w * 0.55)
            ch = t.math("SUBTRACT", 1.0, t.smooth(t.math("DIVIDE", lat, taper), 0.7, 1.0))
            ch = t.mul(ch, t.mul(front, t.mul(t.smooth(z, z0, z0 + 0.002), t.math("SUBTRACT", 1.0, t.smooth(z, z1, z1 + 0.004)))))
            clear = t.math("MAXIMUM", clear, ch)
        fogm = t.mul(t.mul(below, t.math("SUBTRACT", 1.0, clear)), outer)
        fogm = t.mul(fogm, t.map(t.noise(p, scale=300.0, detail=2.0), 0.3, 0.7, 0.55, 1.0))
        fogm = t.mul(fogm, t.map(t.noise(p, scale=25.0, detail=3.0), 0.35, 0.65, 0.5, 1.0))
        rough = t.add(rough, t.mul(fogm, fog))
        surf_mask = fogm
    bsdf = t.principled(base=color, transmission=1.0, rough=rough, ior=ior, normal=nrm)
    surface = bsdf
    if frost > 0:
        fm = frost_mask(t, seed, frost, frost_wipes, radius)
        fm = t.mul(fm, outer)
        surface = t.mix_shader(fm, bsdf, frost_shader(t, seed))
    surface = _shadow_mix(t, surface, shadow)
    vol = None
    if absorb is not None and density > 0:
        vol = t.node("ShaderNodeVolumeAbsorption", {"Color": absorb, "Density": density})
    t.output(surface, vol)
    return m


def frost_mask(t, seed, coverage=0.85, wipes=0, radius=0.03):
    """0..1 mask of freezer frost: patchy veil (partial values = thin frost), heavier towards the
    foot, thinning at the rim, with optional clear finger-wiped patches.  coverage ~ frosted area."""
    p = _seed_vec(t, seed, 5)
    x, y, z = t.xyz(t.texco())
    n1 = t.noise(p, scale=90.0, detail=6.0, rough=0.6)
    n2 = t.noise(p, scale=14.0, detail=3.0, rough=0.5)
    n = t.add(t.mul(n1, 0.45), t.mul(n2, 0.55))
    thr = 0.5 + (0.5 - coverage) * 0.45
    m = t.smooth(n, thr - 0.12, thr + 0.12)
    m = t.mul(m, t.map(n1, 0.3, 0.7, 0.55, 1.0))                  # thickness variation inside the veil
    m = t.mul(m, t.map(z, 0.0, 0.25, 0.92, 0.7))                    # a little lighter higher up
    if wipes:
        r = _rnd(seed, 11)
        for i in range(wipes):
            # elliptical clear patch where a finger touched the cold glass
            ang = r.uniform(-math.pi, math.pi)
            c = (math.cos(ang) * radius, math.sin(ang) * radius, r.uniform(0.02, 0.05))
            d = t.vmath("SUBTRACT", t.texco(), c)
            d = t.vmath("MULTIPLY", d, (1.0 / 0.014, 1.0 / 0.014, 1.0 / 0.02))
            l = t.add(t.vmath("LENGTH", d), t.mul(t.add(n1, -0.5), 0.5))
            m = t.mul(m, t.smooth(l, 0.75, 1.0))
    return m


def frost_shader(t, seed, transmission=0.93):
    """White hoarfrost as ONE Principled lobe set (keeps the closure count low): rough ice
    transmission with a diffuse-white share for the scattering crystals + crystal bump."""
    p = _seed_vec(t, seed, 6)
    cr = t.voronoi(p, scale=2600.0, rand=1.0, feature="F1", out="Distance")
    fine = t.noise(p, scale=900.0, detail=3.0)
    h = t.add(t.mul(cr, 0.6), t.mul(fine, 0.4))
    nrm = t.bump(h, strength=0.6, distance=0.0002)
    col = t.mixc(t.noise(p, scale=40.0), (0.82, 0.86, 0.90), (0.95, 0.97, 0.98))
    return t.principled(base=col, transmission=transmission, rough=0.36, ior=1.31, normal=nrm)


def frost_layer(name="Frost", coverage=0.8, wipes=0, radius=0.03, seed=0, top_z=None, density=0.8, holes=(), track=None):
    """Hoarfrost as a separate thin shell over the glass (see props.frost_shell): white ice crystals
    with partial coverage over CLEAR glass, so the liquid behind keeps its colour where the frost is
    thin.  Opacity grows at grazing angles (longer path through the layer); thinner within 4 mm of
    top_z (the rim).  Alpha-mixed with Transparent; shadow rays see it as mostly transparent."""
    m, t = new_material(name)
    mask = frost_mask(t, seed, coverage, wipes, radius)
    if track:
        # a melt bead's run: clear glass in a wavy channel from z_top down to the keyed value 'MeltFront' (object space)
        x, y, z = t.xyz(t.texco())
        v = t.node("ShaderNodeValue")
        v.name = "MeltFront"
        v.outputs[0].default_value = track["z_top"]
        wob = t.mul(t.math("SINE", t.mul(z, 700.0)), track["width"] * 0.25)
        lat = t.math("ABSOLUTE", t.add(t.add(y, -track["y"]), wob))
        w = t.map(z, track["z_top"] - 0.03, track["z_top"], track["width"] * 1.25, track["width"] * 0.7)
        ch = t.math("SUBTRACT", 1.0, t.smooth(t.math("DIVIDE", lat, w), 0.75, 1.0))
        ch = t.mul(ch, t.math("GREATER_THAN", x, track["x_min"]))
        ch = t.mul(ch, t.mul(t.math("LESS_THAN", z, track["z_top"]), t.smooth(z, v.outputs[0], t.add(v.outputs[0], 0.001))))
        mask = t.mul(mask, t.math("SUBTRACT", 1.0, ch))
    if top_z is not None:
        z = t.xyz(t.texco())[2]
        mask = t.mul(mask, t.map(z, top_z - 0.005, top_z, 1.0, 0.35))
    p = _seed_vec(t, seed, 8)
    grain = t.noise(p, scale=2600.0, detail=3.0, rough=0.6)                      # ~0.4 mm clumps
    soft = t.noise(p, scale=160.0, detail=4.0, rough=0.5)                        # gentle thickness drift
    a0 = t.mul(t.mul(mask, density), t.add(t.add(0.72, t.mul(grain, 0.35)), t.mul(t.add(soft, -0.5), 0.5)),
               clamp=True)
    # grazing angles: 1 - (1 - a)^(1 / cos)
    cosv = t.math("ABSOLUTE", t.vmath("DOT_PRODUCT", t.geo("Normal"), t.geo("Incoming")))
    alpha = t.math("SUBTRACT", 1.0, t.math("POWER", t.math("SUBTRACT", 1.0, a0), t.math("DIVIDE", 1.0, t.math("MAXIMUM", cosv, 0.12))))
    # crystal facets: each ~0.25 mm cell gets its own random normal -> glints in the key light
    cellc = t.voronoi(p, scale=4000.0, rand=1.0, out="Color")
    facet = t.vmath("NORMALIZE", t.vmath("ADD", t.geo("Normal"),
                                          t.vmath("SCALE", t.vmath("SUBTRACT", cellc, (0.5, 0.5, 0.5)), scale=1.6)))
    col = t.mixc(t.noise(p, scale=60.0), (0.82, 0.86, 0.90), (0.94, 0.96, 0.98))
    ice = t.principled(base=col, rough=0.55, transmission=0.3, ior=1.31, sheen=0.3, sheen_rough=0.4,
                       coat=0.35, coat_rough=0.12, coat_ior=1.31, coat_normal=facet)
    tr = t.node("ShaderNodeBsdfTransparent", {"Color": (1, 1, 1)})
    surf = t.mix_shader(alpha, tr, ice)
    lp = t.node("ShaderNodeLightPath")
    tr2 = t.node("ShaderNodeBsdfTransparent", {"Color": t.mixc(t.mul(alpha, 0.5), (1, 1, 1), (0, 0, 0))})
    t.output(t.mix_shader(lp.outputs["Is Shadow Ray"], surf, tr2))
    return m


# --------------------------------------------------------------------------- liquids
def liquid(name, ior, absorb, density, scatter=0.0, scatter_color=(1, 1, 1), anisotropy=0.3,
           roughness=0.0, shadow=(1.0, 1.0, 1.0), surface_color=(1.0, 1.0, 1.0)):
    """Clear liquid: refractive surface + homogeneous volume absorption (+ optional faint scatter).
    shadow: the shadow ray sees a transparent surface (volume absorption still tints the shadow)."""
    m, t = new_material(name)
    bsdf = t.principled(base=surface_color, transmission=1.0, rough=roughness, ior=ior)
    surface = _shadow_mix(t, bsdf, shadow)
    vol = t.node("ShaderNodeVolumeAbsorption", {"Color": absorb, "Density": density})
    if scatter > 0:
        sc = t.node("ShaderNodeVolumeScatter", {"Color": scatter_color, "Density": scatter, "Anisotropy": anisotropy})
        vol = t.add_shader(vol, sc)
    t.output(surface, vol)
    return m


def jagermeister(name="Jagermeister", density=260.0):
    """Mahogany-black core, ruby at thin edges.  IOR 1.355."""
    return liquid(name, 1.355, (0.45, 0.10, 0.04), density)


def energy_drink(name="EnergyDrink", density=12.0, scatter=0.0):
    """Pale gold-green energy drink, IOR 1.34.  Through 6 cm: ~85 % red, 88 % green, 20 % blue survive.
    scatter > 0 adds a faint haze (Volume Scatter; costly and closure-hungry, keep 0 unless needed)."""
    return liquid(name, 1.34, (0.86, 0.92, 0.10), density, scatter=scatter, scatter_color=(0.95, 0.95, 0.8),
                  anisotropy=0.6)


def water(name="Water", roughness=0.0):
    """Condensation / melt water.  IOR 1.333, transparent to shadow rays."""
    m, t = new_material(name)
    bsdf = t.principled(base=(1, 1, 1), transmission=1.0, rough=roughness, ior=1.333)
    t.output(_shadow_mix(t, bsdf, (0.97, 0.97, 0.97)))
    return m


def bubble(name="Bubble", brightness=1.0):
    """Cheap gas bubble inside a liquid: thin glossy (Fresnel-weighted, strong at the rim) + transparent."""
    m, t = new_material(name)
    lw = t.node("ShaderNodeLayerWeight", {"Blend": 0.35})
    fac = t.math("POWER", lw.outputs["Facing"], 1.6, clamp=True)
    gl = t.node("ShaderNodeBsdfGlossy", {"Color": (brightness,) * 3, "Roughness": 0.03})
    tr = t.node("ShaderNodeBsdfTransparent", {"Color": (1, 1, 1)})
    t.output(t.mix_shader(t.add(t.mul(fac, 0.85), 0.08), tr, gl))
    return m


def foam(name="Foam"):
    """Tiny packed bubbles at the meniscus: brighter, a little diffuse-white."""
    m, t = new_material(name)
    lw = t.node("ShaderNodeLayerWeight", {"Blend": 0.4})
    gl = t.node("ShaderNodeBsdfGlossy", {"Color": (1, 1, 1), "Roughness": 0.05})
    tr = t.node("ShaderNodeBsdfTransparent", {"Color": (0.97, 0.97, 0.92)})
    tl = t.node("ShaderNodeBsdfTranslucent", {"Color": (0.9, 0.9, 0.82)})
    a = t.mix_shader(0.25, tr, tl)
    t.output(t.mix_shader(t.add(t.mul(lw.outputs["Facing"], 0.8), 0.1), a, gl))
    return m


# --------------------------------------------------------------------------- wood
WOODS = {
    # name: (late wood, early wood, ring density [rings/m], roughness, coat, coat roughness, pore strength)
    "dark_table": ((0.016, 0.008, 0.0045), (0.070, 0.037, 0.018), 260.0, 0.45, 0.6, 0.10, 0.8),
    "oak_scrubbed": ((0.17, 0.12, 0.085), (0.31, 0.24, 0.175), 220.0, 0.72, 0.0, 0.5, 0.9),
    "fir_lacquer": ((0.21, 0.085, 0.030), (0.50, 0.27, 0.11), 160.0, 0.35, 1.0, 0.04, 0.2),
    "oak_cask": ((0.075, 0.045, 0.025), (0.21, 0.14, 0.08), 240.0, 0.62, 0.0, 0.5, 0.9),
    "pine_crate": ((0.36, 0.22, 0.11), (0.62, 0.48, 0.30), 120.0, 0.75, 0.0, 0.5, 0.2),
}


def wood(kind="dark_table", name=None, seed=0, plank_width=0.14, grain_axis="X", dust=0.0, scratches=0.6,
         rings_strength=1.0, value=1.0, seams=True):
    """Procedural plank wood in Object space (metres).  kinds: dark_table, oak_scrubbed, fir_lacquer,
    oak_cask, pine_crate.  Planks run along `grain_axis` (X or Y), each with its own log geometry:
    the pith axis lies below the surface with a slight tilt, so growth rings cut by the face give
    straight grain and cathedral arches; plus pores, per-plank hue, seams, varnish scratches, dust."""
    late, early, dens0, rough0, coat, coat_rough, pore_k = WOODS[kind]
    m, t = new_material(name or f"Wood_{kind}")
    co = t.texco()
    if grain_axis == "Y":
        co = t.mapping(co, rot=(0, 0, math.pi / 2))
    x, y, z = t.xyz(co)
    # plank id + seam
    yp = t.math("DIVIDE", t.add(y, seed * 0.0371), plank_width)
    pid = t.math("FLOOR", yp)
    frac = t.math("FRACT", yp)
    seam = t.math("MINIMUM", t.smooth(frac, 0.0, 0.004), t.math("SUBTRACT", 1.0, t.smooth(frac, 0.996, 1.0)))
    if not seams:
        seam = 1.0
    rnd = t.white(None, w=t.add(pid, seed * 13.17), out="Color")
    rnd2 = t.white(None, w=t.add(pid, seed * 13.17 + 71.3), out="Color")
    rx, ry, rz = t.xyz(rnd)
    qx, qy, qz = t.xyz(rnd2)
    # log geometry per plank: pith offset across (v0), depth below the face (w0), tilt along the grain
    v = t.mul(t.add(frac, -0.5), plank_width)
    v0 = t.mul(t.add(rx, -0.5), plank_width * 1.6)
    w0 = t.add(-0.03, t.mul(ry, -0.25))
    tilt = t.mul(t.add(rz, -0.5), 0.10)
    u = t.add(x, t.mul(qx, 7.0))
    warp = t.noise(t.combine(t.mul(u, 1.5), t.mul(v, 12.0), t.mul(z, 12.0)), scale=1.0, detail=3.0, rough=0.5)
    dv = t.add(t.math("SUBTRACT", v, v0), t.mul(t.add(warp, -0.5), 0.010))
    dw = t.add(t.math("SUBTRACT", z, w0), t.mul(u, tilt))
    rdist = t.math("SQRT", t.add(t.mul(dv, dv), t.mul(dw, dw)))
    dens = t.mul(dens0, t.add(0.75, t.mul(qy, 0.5)))
    ring = t.add(t.mul(rdist, dens), t.mul(t.noise(t.combine(t.mul(u, 0.8), t.mul(v, 40.0), z), scale=1.0, detail=2.0), 1.2))
    f = t.math("FRACT", ring)
    late_band = t.mul(t.smooth(f, 0.55, 0.80), t.math("SUBTRACT", 1.0, t.smooth(f, 0.93, 1.0)))
    late_band = t.mul(late_band, rings_strength)
    # pores / fine streaks running with the grain
    pv = t.combine(t.mul(u, 6.0), t.mul(v, 2200.0), t.mul(z, 2200.0))
    pores = t.smooth(t.noise(pv, scale=1.0, detail=2.0), 0.60, 0.72)
    pores = t.mul(pores, pore_k)
    streak = t.noise(t.combine(t.mul(u, 3.0), t.mul(v, 180.0), t.mul(z, 180.0)), scale=1.0, detail=4.0)
    tone = t.add(t.mul(late_band, 0.8), t.mul(t.add(streak, -0.5), 0.5))
    base = t.ramp(t.math("MAXIMUM", t.math("MINIMUM", t.add(tone, 0.25), 1.0), 0.0), [(0.0, early), (1.0, late)])
    # per-plank hue/value shift
    base = t.mixc(t.mul(qz, 0.35), base, tuple(c * 0.65 for c in late))
    base = t.mixc(t.mul(pores, 0.5), base, tuple(c * 0.5 for c in late))
    base = t.mixc(t.math("SUBTRACT", 1.0, seam), base, (0.004, 0.003, 0.002))
    if value != 1.0:
        base = t.mixc(1.0, base, (value, value, value), blend="MULTIPLY")
    rough = t.add(t.add(rough0, t.mul(late_band, -0.08)), t.mul(pores, 0.1))
    # scratches in the varnish/coat
    scr = 0.0
    if scratches:
        acc = None
        r = _rnd(seed, 21)
        for i in range(3):
            vv = t.mapping(t.texco(), loc=(r.uniform(0, 9), r.uniform(0, 9), 0), rot=(0, 0, r.uniform(0, math.pi)),
                           scale=(3.0, 260.0, 3.0))
            n = t.noise(vv, scale=4.0, detail=1.0)
            line = t.math("SUBTRACT", 1.0, t.smooth(t.math("ABSOLUTE", t.add(n, -0.5)), 0.0, 0.012))
            gate = t.smooth(t.noise(t.mapping(t.texco(), loc=(i * 3.1, 0, 0)), scale=9.0), 0.48, 0.6)
            line = t.mul(line, gate)
            acc = line if acc is None else t.math("MAXIMUM", acc, line)
        scr = t.mul(acc, scratches)
    # smudges/wipe marks in the coat
    wipe = t.noise(_seed_vec(t, seed, 23), scale=6.0, detail=3.0)
    # dust on up-facing surfaces
    nz = t.xyz(t.geo("Normal"))[2]
    up = t.smooth(nz, 0.6, 0.95)
    dmask = 0.0
    if dust:
        dn = t.noise(_seed_vec(t, seed, 22), scale=220.0, detail=4.0)
        dmask = t.mul(t.mul(up, t.smooth(dn, 0.50, 0.78)), dust)
        base = t.mixc(dmask, base, (0.30, 0.28, 0.25))
    seam_n = t.mul(t.math("SUBTRACT", 1.0, seam), -1.0)
    h = t.add(t.add(t.mul(late_band, 0.3), t.mul(pores, -0.8)), seam_n)
    nrm = t.bump(h, strength=0.12, distance=0.0006)
    coat_r = t.add(t.add(t.add(coat_rough, t.mul(scr, 0.3)), t.mul(dmask, 0.6)), t.mul(t.smooth(wipe, 0.4, 0.8), 0.08))
    coat_w = t.mul(coat, t.math("SUBTRACT", 1.0, t.mul(dmask, 0.7)))
    bsdf = t.principled(base=base, rough=t.add(rough, t.mul(dmask, 0.4)), normal=nrm,
                        coat=coat_w, coat_rough=coat_r, coat_ior=1.5)
    t.output(bsdf)
    return m


# --------------------------------------------------------------------------- metals
METALS = {
    # base colour (F0), roughness
    "brass": ((0.85, 0.62, 0.32), 0.25),
    "chrome": ((0.55, 0.56, 0.57), 0.08),
    "steel_brushed": ((0.56, 0.57, 0.58), 0.22),
    "iron": ((0.36, 0.35, 0.34), 0.45),
    "aluminium": ((0.91, 0.92, 0.92), 0.2),
    "copper": ((0.95, 0.64, 0.54), 0.25),
}


def metal(kind="brass", name=None, seed=0, roughness=None, smudge=0.15, aniso=None, tarnish=0.0, rust=0.0, color=None):
    """Metal with fingerprint/smudge roughness breakup.  aniso: brushed (0..1, tangent around Z).
    tarnish: olive tarnish in cavities (brass).  rust: noise-masked rust layer (iron hoops, hull)."""
    col, r0 = METALS[kind]
    if color is not None:
        col = color
    if roughness is not None:
        r0 = roughness
    if aniso is None:
        aniso = 0.7 if kind == "steel_brushed" else 0.0
    m, t = new_material(name or f"Metal_{kind}")
    p = _seed_vec(t, seed, 31)
    n = t.noise(p, scale=35.0, detail=5.0, rough=0.6)
    rough = t.add(r0, t.mul(t.add(n, -0.5), smudge))
    base = t.mixc(t.mul(t.noise(p, scale=8.0), 0.25), col, tuple(c * 0.8 for c in col))
    nrm = None
    if aniso:
        sc = t.noise(t.mapping(p, scale=(1.0, 1.0, 400.0)), scale=30.0, detail=2.0)
        nrm = t.bump(sc, strength=0.05, distance=0.0002)
    metallic = 1.0
    if tarnish:
        ao = t.node("ShaderNodeAmbientOcclusion", {"Distance": 0.004}, only_local=True).outputs["AO"]
        tm = t.mul(t.math("SUBTRACT", 1.0, ao), tarnish * 2.0, clamp=True)
        tm = t.math("MAXIMUM", tm, t.mul(t.smooth(n, 0.55, 0.75), tarnish * 0.5))
        base = t.mixc(tm, base, (0.12, 0.11, 0.05))
        rough = t.mixf(tm, rough, 0.6)
    if rust:
        rn = t.noise(p, scale=25.0, detail=8.0, rough=0.65)
        rm = t.mul(t.smooth(rn, 0.62 - rust * 0.2, 0.66 - rust * 0.2), 1.0)
        rc = t.ramp(t.noise(p, scale=120.0, detail=3.0), [(0.3, (0.12, 0.04, 0.015)), (0.7, (0.30, 0.11, 0.035))])
        base = t.mixc(rm, base, rc)
        rough = t.mixf(rm, rough, 0.85)
        metallic = t.math("SUBTRACT", 1.0, rm)
        rb = t.bump(t.mul(rm, rn), strength=0.4, distance=0.0005, normal=nrm)
        nrm = rb
    bsdf = t.principled(base=base, metallic=metallic, rough=rough, normal=nrm, aniso=aniso)
    t.output(bsdf)
    return m


# --------------------------------------------------------------------------- dielectrics / misc
def plastic(color=(0.01, 0.01, 0.01), roughness=0.35, name="Plastic", seed=0, scuffs=0.3, coat=0.0):
    """Moulded plastic (bottle cap, powder coat): roughness breakup + fine scuffs."""
    m, t = new_material(name)
    p = _seed_vec(t, seed, 41)
    n = t.noise(p, scale=60.0, detail=4.0)
    sc = t.smooth(t.noise(t.mapping(p, scale=(1, 1, 30)), scale=40.0, detail=2.0), 0.6, 0.7)
    rough = t.add(t.add(roughness, t.mul(t.add(n, -0.5), 0.12)), t.mul(sc, scuffs * 0.3))
    base = t.mixc(t.mul(sc, scuffs * 0.5), color, tuple(min(c * 3 + 0.03, 1) for c in color))
    nrm = t.bump(t.noise(p, scale=900.0, detail=2.0), strength=0.04, distance=0.0002)
    t.output(t.principled(base=base, rough=rough, normal=nrm, coat=coat, coat_rough=0.1))
    return m


def paper(color=(0.78, 0.74, 0.64), image=None, name="Paper", roughness=0.62, seed=0, translucency=0.1,
          bump=0.08, vec=None):
    """Paper / card stock with fibre bump and slight translucency; `image` = colour artwork (UV)."""
    m, t = new_material(name)
    p = _seed_vec(t, seed, 51)
    fib = t.noise(t.mapping(p, scale=(1, 3, 1)), scale=2500.0, detail=3.0)
    col = t.image(image, vec) if image else color
    col = t.mixc(t.mul(t.add(fib, -0.5), 0.15), col, (0.0, 0.0, 0.0), blend="MULTIPLY")
    nrm = t.bump(fib, strength=bump, distance=0.0002)
    bsdf = t.principled(base=col, rough=roughness, normal=nrm, sheen=0.2, sheen_rough=0.6)
    if translucency:
        tl = t.node("ShaderNodeBsdfTranslucent", {"Color": col})
        bsdf = t.mix_shader(translucency, bsdf, tl)
    t.output(bsdf)
    return m


def label(image, ink_mask=None, name="Label", seed=0, roughness=0.42, wet=0.0, frost=0.0):
    """Printed bottle label: colour artwork via UV, ink areas slightly embossed and glossier,
    paper fibre bump, edge wear.  wet: darkened damp paper (from a freezer bottle).
    frost: 0..1 thin frost over the label."""
    m, t = new_material(name)
    uv = t.texco("UV")
    p = _seed_vec(t, seed, 61)
    col = t.image(image, uv)
    fib = t.noise(t.mapping(p, scale=(1, 2.5, 1)), scale=2200.0, detail=3.0)
    h = t.mul(fib, 0.4)
    rough = t.add(roughness, t.mul(t.add(fib, -0.5), 0.1))
    if ink_mask:
        ink = t.image(ink_mask, uv, colorspace="Non-Color")
        ink = t.xyz(ink)[0]
        h = t.add(h, t.mul(ink, 1.5))
        rough = t.mixf(ink, rough, roughness * 0.7)
    if wet:
        col = t.mixc(wet * 0.35, col, (0.0, 0.0, 0.0))
        rough = t.mixf(wet, rough, 0.25)
    nrm = t.bump(h, strength=0.12, distance=0.00015)
    bsdf = t.principled(base=col, rough=rough, normal=nrm, sheen=0.15)
    if frost:
        fm = t.mul(frost_mask(t, seed, frost), 0.8)
        bsdf = t.mix_shader(fm, bsdf, frost_shader(t, seed))
    t.output(bsdf)
    return m


def cork(name="Cork", seed=0, color=(0.36, 0.22, 0.12)):
    m, t = new_material(name)
    p = _seed_vec(t, seed, 71)
    v = t.voronoi(p, scale=900.0, rand=1.0, out="Distance")
    n = t.noise(p, scale=300.0, detail=6.0, rough=0.7)
    pits = t.smooth(t.noise(p, scale=140.0, detail=2.0), 0.66, 0.72)
    tone = t.add(t.mul(v, 0.5), t.mul(n, 0.5))
    col = t.ramp(tone, [(0.2, (color[0] * 0.55, color[1] * 0.5, color[2] * 0.45)), (0.8, color)])
    col = t.mixc(t.mul(pits, 0.8), col, (0.05, 0.03, 0.015))
    nrm = t.bump(t.add(tone, t.mul(pits, -1.0)), strength=0.5, distance=0.0006)
    t.output(t.principled(base=col, rough=0.85, normal=nrm))
    return m


def chalk(name="Chalk", color=(0.85, 0.84, 0.80)):
    m, t = new_material(name)
    n = t.noise(scale=1800.0, detail=4.0)
    t.output(t.principled(base=t.mixc(t.mul(n, 0.3), color, (0.6, 0.6, 0.58)), rough=0.95,
                          normal=t.bump(n, 0.3, 0.0003)))
    return m


def plaster(name="LimePlaster", color=(0.62, 0.58, 0.50), seed=0, damp=0.4):
    """Lime plaster: two-scale noise colour + bump, damp mottling near the floor (z < 0.6 m)."""
    m, t = new_material(name)
    p = _seed_vec(t, seed, 81)
    n1 = t.noise(p, scale=3.0, detail=6.0, rough=0.6)
    n2 = t.noise(p, scale=80.0, detail=4.0)
    z = t.xyz(t.texco())[2]
    dm = t.mul(t.math("SUBTRACT", 1.0, t.smooth(t.add(z, t.mul(n1, 0.3)), 0.25, 0.75)), damp)
    col = t.mixc(t.mul(n1, 0.3), color, tuple(c * 0.75 for c in color))
    col = t.mixc(dm, col, tuple(c * 0.55 for c in color))
    t.output(t.principled(base=col, rough=0.9, normal=t.bump(t.add(t.mul(n1, 0.5), n2), 0.25, 0.002)))
    return m


def brick(name="Brick", seed=0, color=(0.55, 0.50, 0.44), whitewash=0.7):
    """Per-object brick (use with instanced bricks: Object Info random drives colour/roughness jitter)."""
    m, t = new_material(name)
    p = _seed_vec(t, seed, 91)
    oi = t.node("ShaderNodeObjectInfo").outputs["Random"]
    n = t.noise(p, scale=30.0, detail=6.0)
    z = t.xyz(t.texco("Generated"))[2]
    col = t.mixc(t.mul(oi, 0.4), color, (0.45, 0.30, 0.22))
    col = t.mixc(t.mul(t.smooth(n, 0.4, 0.6), whitewash), col, (0.82, 0.80, 0.75))
    t.output(t.principled(base=col, rough=t.add(0.8, t.mul(oi, 0.15)), normal=t.bump(n, 0.4, 0.002)))
    return m


def rubber(name="Rubber", color=(0.02, 0.02, 0.02), roughness=0.55, seed=0):
    m, t = new_material(name)
    p = _seed_vec(t, seed, 101)
    n = t.noise(p, scale=200.0, detail=3.0)
    t.output(t.principled(base=color, rough=t.add(roughness, t.mul(t.add(n, -0.5), 0.15)),
                          normal=t.bump(n, 0.08, 0.0003), sheen=0.2))
    return m


def enamel(color=(0.15, 0.3, 0.2), name="Enamel", seed=0, chips=0.15):
    """Glossy enamel with chips showing dark iron."""
    m, t = new_material(name)
    p = _seed_vec(t, seed, 111)
    ch = t.smooth(t.noise(p, scale=40.0, detail=6.0, rough=0.7), 0.72 - chips * 0.2, 0.74 - chips * 0.2)
    col = t.mixc(ch, color, (0.03, 0.025, 0.02))
    t.output(t.principled(base=col, rough=t.mixf(ch, 0.12, 0.6), coat=t.math("SUBTRACT", 1.0, ch),
                          coat_rough=0.05, normal=t.bump(ch, 0.3, 0.0005)))
    return m


def emission(color=None, strength=10.0, kelvin=None, name="Emission"):
    m, t = new_material(name)
    c = S.kelvin(kelvin) if kelvin else (color or (1, 1, 1))
    t.output(t.node("ShaderNodeEmission", {"Color": c, "Strength": strength}))
    return m


def matte_black(name="MatteBlack", value=0.01):
    """Black flag / duvetyne: absorbs, slight sheen."""
    m, t = new_material(name)
    t.output(t.principled(base=(value, value, value), rough=0.95, sheen=0.3, spec=0.2))
    return m


flag = matte_black


def backdrop(name="Backdrop", color=(0.02, 0.016, 0.012), seed=0):
    """Out-of-focus room wall: low-frequency mottled diffuse."""
    m, t = new_material(name)
    p = _seed_vec(t, seed, 121)
    n = t.noise(p, scale=1.5, detail=3.0)
    t.output(t.principled(base=t.mixc(t.mul(n, 0.6), color, tuple(c * 0.5 for c in color)), rough=0.85))
    return m
