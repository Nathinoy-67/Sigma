"""S06 THE YEAR (film frames 300-390, 90 local frames).

MATCH CUT from the GEHEIM stamp: the chalk circle round '1934' on the hero cask's head fills the stamp's circle at
the same size and position (30 % of picture height, centred).  Motion-control dolly back 2.5 m with a 40 cm boom up,
35 mm at f/4, revealing the whitewashed barrel vault, the two rows of casks on their cradles, the flagstones.
Time-lapse: the disc of sun from the oculus behind camera sweeps across the cask heads once per beat (15 frames),
six 'days' each standing for two months; its colour runs winter blue-white, pale spring, hard white summer, amber
autumn, blue again.  Small per-frame exposure jitter (time-lapse flicker).  Everything outside the light falls to
near black.
"""
import math
import random

import bpy
from mathutils import Vector

import scene as S
import camera as C
import materials as M
import cellar as B

FRAMES = 90
PRESET = "default"
SEASONS = [(9000, 0.85), (6500, 1.0), (5600, 1.15), (4200, 1.0), (3400, 0.9), (9500, 0.8)]   # (K, strength)


def head_plane_y():
    return B.HERO.y - B.CASK_L / 2 + 0.032


def key_sun(sun, frames, target_fn, base=9.0, seed=6, phase=0.0):
    """Per-frame sun: sweep `target_fn(u)` (u = 0..1 within each 15-frame day), season colour, flicker."""
    rng = random.Random(seed)
    for f in range(frames):
        day, u = divmod(f + 7.5 + phase, 15)    # f0: the disc sits centred on the hero head (match cut)
        day = int(day)
        u = u / 15
        K, k = SEASONS[min(day, len(SEASONS) - 1)]
        tgt = target_fn(u)
        d = (tgt - B.OCULUS).normalized()
        sun.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        env = math.sin(math.pi * u) ** 0.35
        sun.data.energy = base * k * env * (1 + rng.uniform(-0.05, 0.05))
        sun.data.color = S.kelvin(K)
        sun.keyframe_insert("rotation_euler", frame=f)
        sun.data.keyframe_insert("energy", frame=f)
        sun.data.keyframe_insert("color", frame=f)
    for idb in (sun, sun.data):
        for fc in C.fcurves(idb):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"


def build(res="look", samples=None, threshold=None, **kw):
    S.new_scene(res, PRESET, samples=samples, threshold=threshold, exposure=-0.6)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 0, FRAMES - 1
    coll = S.collection("S06")
    B.vault(coll)
    B.casks(coll)
    hy = head_plane_y()
    lights = B.oculus_sun(target=Vector((0, hy, B.CASK_Z)), strength=9.0, coll=coll, shaft=False)
    sun = lights["sun"]
    key_sun(sun, FRAMES, lambda u: Vector((-1.5 + 3.0 * u, hy - 0.4, B.CASK_Z + 0.25 * math.sin(math.pi * u))))
    lights["bounce"].data.energy = 70.0
    S.world((0.0015, 0.0017, 0.002), 1.0)
    # camera: start framing the chalk circle (0.41 m) at 30 % of picture height
    h0 = 0.41 / 0.30
    lens = 35.0
    d0 = h0 * (1920 / 804) * lens / 36.0
    tgt = Vector((0.0, hy, B.CASK_Z))
    p0 = tgt - Vector((0, d0, 0))
    p1 = p0 - Vector((0, 2.5, 0)) + Vector((0, 0, 0.40))
    cam = C.add_camera("CAM_S06", lens=lens, location=p0, target=tgt, fstop=4.0, focus=tgt)
    C.move(cam, [(0, p0), (FRAMES - 1, p1)])
    C.aim_keys(cam, [(0, tgt), (FRAMES - 1, tgt + Vector((0, 0, 0.12)))])
    C.breathe(cam, amplitude_deg=0.03, period_frames=90, seed=6)
    return dict(cam=cam)
