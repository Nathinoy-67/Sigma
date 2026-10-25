"""S20 THE BLOOM (film frames 1080-1140, 60 local frames).  On the bar 19 downbeat the score turns major.

A side view, 85 mm at f/4, through the condensation-beaded outer wall: a mahogany plume unfurls out of the sunken shot
glass and spirals through the gold like ink in water, bubbles streaming past.  From local f30 (film f1110) a speed ramp
returns to real time, carried by a fizz rush; the colour settles to a warm amber-brown.
"""
import math

import bpy
from mathutils import Vector

import scene as S
import camera as C
import materials as M
import props as P
import stage as F

FRAMES = 60
PRESET = "glass"


def eff_time(f):
    """Plume clock (0..1.6): slow motion until f30, then a ramp to real time."""
    if f <= 30:
        return 0.55 * f / 30.0
    u = (f - 30) / 29.0
    return 0.55 + 1.05 * (u ** 1.6)


def build(res="look", samples=None, threshold=None, **kw):
    S.new_scene(res, PRESET, samples=samples, threshold=threshold, exposure=-0.25)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 0, FRAMES - 1
    sc.cycles.volume_step_rate = 5.0
    sc.cycles.volume_max_steps = 64
    coll = S.collection("S20")
    F.stage(coll)
    drink = M.liquid("BloomDrink", 1.34, (0.86, 0.92, 0.10), 14.0)
    hb = P.highball("Highball", location=F.HB, fill=0.66, seed=5, coll=coll, drink_material=drink, cond_facing_deg=-90.0,
                    n_streams=22, n_drops=1800, n_cling=160, n_free=80)
    fz = hb.info["fill_z"]
    # the drink warms from gold to amber-brown as the plume mixes in
    va = [n for n in drink.node_tree.nodes if n.bl_idname == "ShaderNodeVolumeAbsorption"][0]
    for f, c, d in ((0, (0.86, 0.92, 0.10), 12.0), (30, (0.86, 0.82, 0.14), 12.0), (FRAMES - 1, (0.84, 0.55, 0.16), 16.0)):
        va.inputs["Color"].default_value = (*c, 1)
        va.inputs["Density"].default_value = d
        va.inputs["Color"].keyframe_insert("default_value", frame=f)
        va.inputs["Density"].keyframe_insert("default_value", frame=f)
    # bubbles: speed ramp through the GN clock offset (effective time = slow, then real time)
    if hb.bubbles is not None:
        mod = hb.bubbles.modifiers[0]
        for f in range(FRAMES):
            teff = 0.25 * min(f, 30) / 24.0 + (max(f - 30, 0) / 24.0) * (0.25 + 0.75 * min((f - 30) / 20.0, 1.0) if f > 30 else 0)
            P.modifier_input(mod, "Time Offset", teff - f / 24.0)
            mod.keyframe_insert(f'["{[it.identifier for it in mod.node_group.interface.items_tree if getattr(it, "name", "") == "Time Offset"][0]}"]', frame=f) if not hasattr(mod, "properties") else None
    # the sunken shot glass, tilted on the floor
    shot = P.shot_glass("SunkShot", location=F.HB + Vector((0.002, 0.0, hb.info["base"] + 0.0004)), frosted=False,
                        fill=0.9, seed=22, coll=coll, liquid_material=M.jagermeister("JagerSunk", density=420.0))
    shot.root.rotation_euler = (math.radians(6.0), math.radians(-4.0), 0)
    shot.root.scale = (0.93, 0.93, 0.93)
    F.plume(coll, [(f, eff_time(f)) for f in range(0, FRAMES, 3)] + [(FRAMES - 1, eff_time(FRAMES - 1))], fz,
            mix_keys=[(0, 0.0), (30, 1.0), (FRAMES - 1, 6.0)])
    tgt = F.HB + Vector((0.0, 0.0, 0.074))
    cam = C.add_camera("CAM_S20", lens=100, location=tgt + Vector((0.0, -0.55, 0.004)), target=tgt, fstop=4.0,
                       focus=F.HB + Vector((0, -0.006, 0.076)))
    C.breathe(cam, amplitude_deg=0.02, period_frames=60, seed=20)
    return dict(cam=cam)
