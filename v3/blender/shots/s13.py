"""S13 ARRIVAL (film frames 660-735, 75 local frames).

MATCH CUT on the bar 12 downbeat (the orchestra cuts dead): the mirrored disc becomes a full moon rising over the bare
granite ridges of the Carson Range, seen through the window of a dark lakeside lodge bar at summer blue hour; the
last alpenglow on the peaks, a mirror lake with a long moon glade, smudges and a faint pendant reflection on the glass.
50 mm at f/2.8 (wider than the treatment's 85 mm so the lake stays in frame), focused on the moon; the moon climbs
slowly.  On the beat at 28.75 s (local f30) the pink neon OPEN in the window buzzes, stutters twice and catches; it
reads backwards from inside, and focus racks to its tubes.
"""
import math

import bpy
from mathutils import Vector

import scene as S
import camera as C
import lodge as E

FRAMES = 75
PRESET = "default"
CAM = Vector((-0.05, 0.85, 1.30))
NEON = Vector((0.36, E.WIN_Y - 0.06, 1.36))


def build(res="look", samples=None, threshold=None, **kw):
    S.new_scene(res, PRESET, samples=samples, threshold=threshold, exposure=0.0)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 0, FRAMES - 1
    coll = S.collection("S13")
    moon_x = CAM.x + (E.PLATE_Y - 1.0 - CAM.y) * math.tan(math.radians(-6.0))
    moon_z0 = CAM.z + (E.PLATE_Y - 1.0 - CAM.y) * math.tan(math.radians(9.6))
    out = E.build_room(coll, moon_z=moon_z0, moon_x=moon_x, neon_c=NEON)
    moon = out["ext"]["moon"]
    moon.keyframe_insert("location", frame=0)
    moon.location.z += 0.55
    moon.keyframe_insert("location", frame=FRAMES - 1)
    C.set_interpolation(moon, "location", "LINEAR")
    E.key_neon(out["neon"], [(0, 0.0), (30, 0.7), (31, 0.1), (32, 0.0), (33, 0.9), (34, 0.05), (36, 1.0)])
    aim = CAM + Vector((math.tan(math.radians(3.0)), 1.0, math.tan(math.radians(4.2)))) * 10
    focus_moon = moon.location.copy()
    cam = C.add_camera("CAM_S13", lens=50, location=CAM, target=aim, fstop=2.8, focus=focus_moon)
    C.rack_focus(cam, [(0, focus_moon), (36, focus_moon), (50, NEON), (FRAMES - 1, NEON)], breathing=0.02)
    C.breathe(cam, amplitude_deg=0.03, period_frames=80, seed=13)
    return dict(cam=cam)
