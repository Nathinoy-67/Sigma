"""S11 ICE COLD (film frames 585-630, 45 local frames, SIM 1 faked).

100 mm macro at f/4, low angle, a slow 3 cm push.  The frost-furred stainless spout of an unbranded tap machine
releases a thin dark rope of ice-cold Jägermeister into a frosted, heavy-based shot glass on a black rubber mat.  The
stream's thin edges glow ruby against a near-black core (the brushed-steel bay behind it, lit by a small bay light,
is what it refracts).  Cool 4000 K fluorescent top light; a red neon smear in the oval bokeh.  2x slow motion: the
stream's ripples travel down at half speed and the glass fills from 40 % to 78 %.
"""
import math

import bpy
from mathutils import Vector

import scene as S
import camera as C
import materials as M
import props as P
import backbar as D

FRAMES = 45
PRESET = "glass"


def stream(coll, top, bottom_z, r0=0.0019, r1=0.0012, seg=40, rows=220):
    """A vertical liquid rope from `top` down to bottom_z: necking as it accelerates, with travelling ripples and a
    slight sway (two Displace modifiers whose texture spaces scroll down through the shot)."""
    L = top.z - bottom_z
    verts, faces = [], []
    for j in range(rows + 1):
        u = j / rows
        z = top.z - L * u
        r = r0 * (1.0 / math.sqrt(1.0 + 9.0 * u)) ** 0.5 + (r1 - r0) * 0.0
        for i in range(seg):
            a = 2 * math.pi * i / seg
            verts.append((top.x + r * math.cos(a), top.y + r * math.sin(a), z))
    for j in range(rows):
        for i in range(seg):
            a, b = j * seg + i, j * seg + (i + 1) % seg
            faces.append((a, a + seg, b + seg, b))       # outward normals (the volume is inside)
    ob = P.mesh("Stream", verts, faces, coll, True)
    space = S.empty("StreamSpace", (0, 0, 0), coll=coll)
    t1 = bpy.data.textures.new("StreamRipple", "CLOUDS")
    t1.noise_scale = 0.012
    d1 = ob.modifiers.new("ripple", "DISPLACE")
    d1.texture, d1.direction, d1.strength, d1.mid_level = t1, "NORMAL", 0.0012, 0.5
    d1.texture_coords, d1.texture_coords_object = "OBJECT", space
    t2 = bpy.data.textures.new("StreamSway", "CLOUDS")
    t2.noise_scale = 0.05
    d2 = ob.modifiers.new("sway", "DISPLACE")
    d2.texture, d2.direction, d2.strength, d2.mid_level = t2, "X", 0.0016, 0.5
    d2.texture_coords, d2.texture_coords_object = "OBJECT", space
    # the texture space scrolls up -> features travel down the stream (2x slow motion: ~0.5 m/s on screen)
    space.location = (0, 0, 0)
    space.keyframe_insert("location", frame=0)
    space.location = (0, 0, 0.024 * FRAMES / 2)
    space.keyframe_insert("location", frame=FRAMES)
    C.set_interpolation(space, "location", "LINEAR")
    return ob


def build(res="look", samples=None, threshold=None, **kw):
    S.new_scene(res, PRESET, samples=samples, threshold=threshold, exposure=-0.2)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 0, FRAMES - 1
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.5
    coll = S.collection("S11")
    D.counter(coll)
    D.bar_mat(coll)
    D.machine(coll)
    D.background(coll)
    L = D.lights(coll, pendant=True)
    S.area_light("BayLight", size=(0.12, 0.03), power=2.5, kelvin=4200, location=(0, D.MACHINE_FRONT_Y + 0.07, 0.135),
                 target=(0, D.MACHINE_FRONT_Y + 0.1, 0.04), coll=coll)
    jager = M.jagermeister("JagerS11", density=520.0)
    g = P.shot_glass("Shot", location=D.GLASS, frosted=True, fill=0.82, seed=11, coll=coll, frost=0.72, frost_density=0.7,
                     melt_beads=70, liquid_material=jager)
    lq = g.liquid
    B = g.info["base"]
    me = lq.data
    for v in me.vertices:
        v.co.z -= B
    lq.location.z += B
    full = g.info["fill_z"] - B
    for f, fill in ((0, 0.40), (FRAMES - 1, 0.78)):
        h = (g.info["cavity_top"] - B) * fill
        lq.scale = (1, 1, h / full)
        lq.keyframe_insert("scale", frame=f)
    C.set_interpolation(lq, "scale", "LINEAR")
    stream(coll, D.SPOUT + Vector((0, 0, -0.0005)), D.GLASS.z + B + 0.004, seg=40)
    lq.data.materials[0] = jager
    bpy.data.objects["Stream"].data.materials.append(jager)
    S.world((0.001, 0.001, 0.0012), 1.0)
    # the red neon off to the left: a coloured smear along the frost and the stream's edge
    S.area_light("NeonSpill", size=(0.5, 0.05), power=3.5, color=(1.0, 0.05, 0.04), location=(-0.40, 0.30, 0.20),
                 target=D.GLASS + Vector((0, 0, 0.05)), coll=coll)
    # camera: low, a little to the left; 3 cm push
    tgt = Vector((0.0, 0.0, 0.058))
    p0 = tgt + Vector((-0.12, -0.60, -0.004))
    cam = C.add_camera("CAM_S11", lens=100, location=p0, target=tgt, fstop=4.0, focus=Vector((0, 0, 0.07)))
    C.move(cam, [(0, p0), (FRAMES - 1, p0 + (tgt - p0).normalized() * 0.03)])
    C.breathe(cam, amplitude_deg=0.02, period_frames=60, seed=11)
    return dict(cam=cam)
