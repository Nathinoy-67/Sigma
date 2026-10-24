"""S17 HELD BREATH (film frames 930-1005, 75 local frames).

100 mm side profile at the rim: the frosted shot glass, full of near-black Jägermeister, is held a centimetre above
the highball (an unseen hand) and trembles a millimetre or two; below it the gold drink fizzes, bubbles bursting at
the meniscus.  With each heartbeat on local f0, f30 and f60 fine concentric ripples tremble across the surface (and
the hand flinches).  On the last frames the glass is let go and drops out of frame.  Cut (total silence).
(A side view rather than the treatment's three-quarter view down into the glass: it reads instantly, it sets up the
S18 profile, and it renders at a third of the cost.)
"""
import math

import bpy
from mathutils import Vector

import scene as S
import camera as C
import materials as M
import props as P
import stage as F

FRAMES = 75
PRESET = "glass"
BEATS = [0, 30, 60]


def rippled_drink(name, fill_z):
    """Energy drink whose top surface carries heartbeat ripples (shader bump, keyed clock)."""
    m, t = M.new_material(name)
    p = t.texco("Object")
    x, y, z = t.xyz(p)
    clock = t.node("ShaderNodeValue")
    clock.name = "Clock"
    clock.outputs[0].default_value = 0.0
    clock.outputs[0].keyframe_insert("default_value", frame=0)
    clock.outputs[0].default_value = FRAMES / 24.0
    clock.outputs[0].keyframe_insert("default_value", frame=FRAMES)
    r = t.math("SQRT", t.add(t.mul(x, x), t.mul(y, y)))
    h = 0.0
    for b in BEATS:
        dt = t.add(clock.outputs[0], -b / 24.0)
        on = t.math("GREATER_THAN", dt, 0.0)
        env = t.mul(on, t.math("EXPONENT", t.mul(t.math("MAXIMUM", dt, 0.0), -3.0)))
        front = t.math("LESS_THAN", r, t.add(t.mul(dt, 0.09), 0.004))
        wave = t.math("SINE", t.add(t.mul(r, 2400.0), t.mul(dt, -95.0)))
        term = t.mul(t.mul(env, front), wave)
        h = term if h == 0.0 else t.add(h, term)
    top = t.smooth(z, fill_z - 0.0015, fill_z - 0.0004)
    nrm = t.bump(t.mul(h, top), strength=0.35, distance=0.00004)
    bsdf = t.principled(base=(1, 1, 1), transmission=1.0, rough=0.0, ior=1.34, normal=nrm)
    t.output(M._shadow_mix(t, bsdf, (1, 1, 1)), t.node("ShaderNodeVolumeAbsorption", {"Color": (0.86, 0.92, 0.10), "Density": 14.0}))
    return m


def build(res="look", samples=None, threshold=None, **kw):
    S.new_scene(res, PRESET, samples=samples, threshold=threshold, exposure=-0.2)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 0, FRAMES - 1
    sc.render.use_motion_blur = False
    coll = S.collection("S17")
    L = F.stage(coll)
    hb = P.highball("Highball", location=F.HB, fill=0.62, seed=5, coll=coll, cond_facing_deg=-90.0, n_streams=14,
                    n_drops=3000, n_cling=140, n_free=70)
    fz = hb.info["fill_z"]
    hb.liquid.data.materials[0] = rippled_drink("RippleDrink", fz)
    # the lifted shot glass, out of frame above: only its shadow (and a little ruby light) reaches the surface
    shot = P.shot_glass("Shot", location=F.HB + Vector((0.0, 0.0, 0.163)), frosted=True, fill=0.84, seed=12, coll=coll,
                        frost=0.68, frost_density=0.62, liquid_material=M.jagermeister("JagerHeld", density=520.0))
    hold = F.HB + Vector((0.0015, 0.0, 0.163))
    for f in range(0, FRAMES - 3):                               # the unseen hand trembles, flinching on each beat
        flinch = sum(0.0012 * math.exp(-(f - b) / 4.0) for b in BEATS if f >= b)
        shot.root.location = hold + Vector((0.0009 * math.sin(f * 1.7), 0.0006 * math.sin(f * 2.3 + 1),
                                            0.0004 * math.sin(f * 3.1) + flinch))
        shot.root.rotation_euler = (0.0, math.radians(0.6 * math.sin(f * 0.9)), 0.0)
        shot.root.keyframe_insert("location", frame=f)
        shot.root.keyframe_insert("rotation_euler", frame=f)
    for f, dz in ((FRAMES - 3, 0.0), (FRAMES - 1, -0.045)):       # let go
        shot.root.location = hold + Vector((0, 0, dz))
        shot.root.keyframe_insert("location", frame=f)
    tgt = F.HB + Vector((0.0, 0.0, 0.127))
    cam = C.add_camera("CAM_S17", lens=100, location=tgt + Vector((0.0, -0.70, 0.004)), target=tgt, fstop=5.6,
                       focus=F.HB + Vector((0, -0.02, 0.13)))
    C.breathe(cam, amplitude_deg=0.03, period_frames=60, seed=17)
    return dict(cam=cam)
