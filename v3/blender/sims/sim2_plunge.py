#!/usr/bin/env python3
"""SIM 2 -- the hero plunge: a full, heavy shot glass dropped into a highball of energy drink (Mantaflow FLIP).

Highball interior (r 27.5 mm, floor at z 8 mm) filled to z = FILL_Z; the shot glass (44 mm across, 60 mm tall,
treated as one solid with its contents) falls from the rim, breaks the surface on sim frame IMPACT and sinks to the
floor.  The 5 mm annulus between the shot and the wall is the whole show: the displaced drink shoots up the walls as
a crown and tears into spray.  Units are metres; one sim frame = 1/400 s (time_scale = 24/400).

    python sims/sim2_plunge.py --res 192 --frames 128 --cache v3/frames/sim2      (bake)
    python sims/sim2_plunge.py --res 64 --frames 40 --cache /tmp/sim2_test        (quick test)
Writes the shot-glass motion to <cache>/shot_motion.json so the render shots key the glass identically.
"""
import argparse
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import scene as S  # noqa: E402

R_IN = 0.0275          # highball inner radius
FLOOR = 0.008
RIM = 0.150
FILL_Z = 0.095
SHOT_R, SHOT_H = 0.0222, 0.060
SIM_FPS = 400.0
IMPACT = 12            # sim frame at which the shot's base meets the surface


def shot_motion(n):
    """Per sim frame (z of the shot's base, tilt deg).  Free fall from just above the rim, a hard deceleration on
    entry (added mass + drag), then a slower sink to the floor; a few degrees of tilt as it goes down."""
    g = 9.81
    dt = 1.0 / SIM_FPS
    v_imp = 1.05
    z_imp = FILL_Z
    out = []
    for f in range(n):
        t = (f - IMPACT) * dt
        if t < 0:
            z = z_imp - v_imp * t - 0.5 * g * t * t           # t < 0: still falling towards the surface
        else:
            # exponential approach to a terminal sink speed, then it lands on the floor
            v_t = 0.32
            k = 60.0
            z = z_imp - (v_t * t + (v_imp - v_t) / k * (1 - math.exp(-k * t)))
        z = max(z, FLOOR + 0.0005)
        tilt = 0.0 if t < 0 else min(7.0, 7.0 * t / 0.12)
        out.append((z, tilt))
    return out


def build(res, frames, cache):
    S.new_scene("look", "default")
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, frames
    sc.render.fps = 24
    sc.gravity = (0, 0, -9.81)
    # domain
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    dom = bpy.context.active_object
    dom.name = "Domain"
    w = 2 * (R_IN + 0.004)
    z0, z1 = FLOOR - 0.004, 0.205
    dom.scale = (w, w, z1 - z0)
    dom.location = (0, 0, (z0 + z1) / 2)
    bpy.ops.object.transform_apply(scale=True)
    md = dom.modifiers.new("Fluid", "FLUID")
    md.fluid_type = "DOMAIN"
    d = md.domain_settings
    d.domain_type = "LIQUID"
    d.resolution_max = res
    d.time_scale = 24.0 / SIM_FPS
    d.use_adaptive_timesteps = True
    d.cfl_condition = 2.0
    d.timesteps_max = 8
    d.timesteps_min = 2
    d.simulation_method = "FLIP"
    d.flip_ratio = 0.97
    d.particle_radius = 1.2
    d.particle_band_width = 3.0
    d.surface_tension = 0.0
    d.use_mesh = True
    d.mesh_scale = 2
    d.mesh_smoothen_pos = 1
    d.mesh_smoothen_neg = 1
    d.mesh_concave_upper = 3.5
    d.mesh_concave_lower = 0.4
    d.use_spray_particles = True
    d.use_foam_particles = True
    d.use_bubble_particles = True
    d.sndparticle_potential_max_wavecrest = 1.5
    d.sndparticle_potential_min_wavecrest = 0.15
    d.sndparticle_potential_max_energy = 4.0
    d.sndparticle_life_max = 60.0
    d.cache_directory = os.path.abspath(cache)
    d.cache_type = "ALL"
    d.cache_frame_start, d.cache_frame_end = 1, frames
    d.cache_data_format = "OPENVDB"
    d.cache_mesh_format = "BOBJECT"
    d.use_diffusion = True
    d.viscosity_base = 1.0
    d.viscosity_exponent = 6         # water-like (1e-6 m^2/s)
    # border collisions: closed box (the glass is an effector inside anyway)
    for k in ("use_collision_border_front", "use_collision_border_back", "use_collision_border_right",
              "use_collision_border_left", "use_collision_border_top", "use_collision_border_bottom"):
        setattr(d, k, True)
    # the highball wall + floor as a collision effector (a thick tube)
    bpy.ops.mesh.primitive_cylinder_add(radius=R_IN + 0.006, depth=RIM - FLOOR + 0.004, vertices=96,
                                        location=(0, 0, (RIM + FLOOR) / 2 - 0.002))
    outer = bpy.context.active_object
    bpy.ops.mesh.primitive_cylinder_add(radius=R_IN, depth=RIM - FLOOR + 0.02, vertices=96,
                                        location=(0, 0, (RIM + FLOOR) / 2 + 0.01 + 0.0))
    inner = bpy.context.active_object
    inner.location.z = FLOOR + (RIM - FLOOR + 0.02) / 2
    bo = outer.modifiers.new("hollow", "BOOLEAN")
    bo.operation, bo.object, bo.solver = "DIFFERENCE", inner, "EXACT"
    bpy.context.view_layer.objects.active = outer
    bpy.ops.object.modifier_apply(modifier="hollow")
    bpy.data.objects.remove(inner, do_unlink=True)
    outer.name = "GlassWall"
    em = outer.modifiers.new("Fluid", "FLUID")
    em.fluid_type = "EFFECTOR"
    em.effector_settings.effector_type = "COLLISION"
    em.effector_settings.surface_distance = 0.0
    em.effector_settings.use_effector = True
    # the drink
    bpy.ops.mesh.primitive_cylinder_add(radius=R_IN - 0.0004, depth=FILL_Z - FLOOR, vertices=96,
                                        location=(0, 0, (FILL_Z + FLOOR) / 2))
    liq = bpy.context.active_object
    liq.name = "Drink"
    fm = liq.modifiers.new("Fluid", "FLUID")
    fm.fluid_type = "FLOW"
    fs = fm.flow_settings
    fs.flow_type = "LIQUID"
    fs.flow_behavior = "GEOMETRY"
    fs.flow_source = "MESH"
    fs.surface_distance = 0.0
    fs.volume_density = 1.0
    # the shot glass (solid): outer profile, closed
    bpy.ops.mesh.primitive_cylinder_add(radius=SHOT_R, depth=SHOT_H, vertices=96, location=(0, 0, SHOT_H / 2))
    shot = bpy.context.active_object
    shot.name = "ShotSolid"
    bpy.ops.object.transform_apply(location=True)
    sm = shot.modifiers.new("Fluid", "FLUID")
    sm.fluid_type = "EFFECTOR"
    sm.effector_settings.effector_type = "COLLISION"
    sm.effector_settings.use_effector = True
    sm.effector_settings.surface_distance = 0.0
    sm.effector_settings.subframes = 2
    motion = shot_motion(frames + 1)
    for f in range(1, frames + 1):
        z, tilt = motion[f]
        shot.location = (0.0, 0.0, z)
        shot.rotation_euler = (math.radians(tilt), math.radians(-tilt * 0.6), 0)
        shot.keyframe_insert("location", frame=f)
        shot.keyframe_insert("rotation_euler", frame=f)
    os.makedirs(cache, exist_ok=True)
    json.dump(dict(sim_fps=SIM_FPS, impact=IMPACT, frames=frames, res=res,
                   motion=[(f, motion[f][0], motion[f][1]) for f in range(1, frames + 1)]),
              open(os.path.join(cache, "shot_motion.json"), "w"), indent=0)
    return dom


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", type=int, default=64)
    ap.add_argument("--frames", type=int, default=40)
    ap.add_argument("--cache", default="/tmp/sim2_test")
    ap.add_argument("--blend", default=None)
    a = ap.parse_args()
    dom = build(a.res, a.frames, a.cache)
    bpy.context.view_layer.objects.active = dom
    for o in bpy.context.selected_objects:
        o.select_set(False)
    dom.select_set(True)
    t0 = time.time()
    with bpy.context.temp_override(object=dom, active_object=dom, selected_objects=[dom]):
        bpy.ops.fluid.bake_all()
    print(f"[sim2] baked {a.frames} frames at res {a.res} in {time.time() - t0:.0f}s -> {a.cache}", flush=True)
    if a.blend:
        S.save_blend(a.blend)


if __name__ == "__main__":
    main()
