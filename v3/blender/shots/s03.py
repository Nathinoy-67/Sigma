"""S03 BALANCE (film frames 135-180, 45 local frames).

A brass apothecary beam balance on the workbench, seen at eye level against the window (65 mm, f/2.8).  Left pan:
heaped juniper and star anise; right pan: stamped brass weights.  The beam sways in a damped oscillation: the pointer
crosses centre twice and settles dead centre on the last frame (bar 4 downbeat, the cut).  The dawn window blooms
behind; the brass is rim-lit by the low sun.
"""
import math

import bpy
from mathutils import Vector, Matrix

import scene as S
import camera as C
import materials as M
import props as P
import botanicals as B
import workroom as A

FRAMES = 45
PRESET = "default"
BASE = Vector((-0.42, 0.02, 0.0))      # balance centre on the bench
ARM = 0.125                            # half beam length
PIVOT_Z = 0.285
HANG = 0.155                           # pan hook below the beam end


def beam_angle(f):
    """Degrees.  Damped swing from 6.5 deg: crosses zero at f9 and f27, eased to rest at f44."""
    T, tau = 36.0, 26.0
    a = 6.5 * math.exp(-f / tau) * math.cos(2 * math.pi * f / T)
    w = 1.0 - max(0.0, min(1.0, (f - 30) / 14.0)) ** 2 * (3 - 2 * max(0.0, min(1.0, (f - 30) / 14.0)))
    return a * (w if f > 30 else 1.0)


def pan(name, coll, brass, loc):
    """Shallow brass pan with three suspension wires to a hook ring; origin at the hook (at `loc`).
    The dish is left unparented (a heap is settled on it first); see parent_keep()."""
    root = S.empty(name, loc, coll=coll)
    R, depth = 0.058, 0.013
    prof = [(0.0, 0.0), (R * 0.55, 0.0015), (R * 0.92, depth * 0.7), (R, depth), (R - 0.0012, depth),
            (R * 0.92 - 0.0012, depth * 0.7 + 0.001), (R * 0.55, 0.0025), (0.0, 0.001)]
    prof, tags = P.fillet(prof, [0, 0.01, 0.01, 0.0008, 0.0008, 0.01, 0.01, 0], steps=4)
    dish = P.lathe(name + "_dish", prof, 96, coll=coll, wobble=0.002, seed=hash(name) % 97)
    dish.data.materials.append(brass)
    dish.location = Vector(loc) + Vector((0, 0, -HANG))
    dish["collider"] = True
    for k in range(3):
        a = 2 * math.pi * k / 3 + math.pi / 2
        p0 = Vector((R * 0.97 * math.cos(a), R * 0.97 * math.sin(a), -HANG + depth))
        p1 = Vector((0, 0, -0.008))
        mid = (p0 + p1) / 2
        L = (p1 - p0).length
        bpy.ops.mesh.primitive_cylinder_add(radius=0.0005, depth=L, vertices=8, location=mid)
        wv = bpy.context.active_object
        wv.location = Vector(loc) + mid
        wv.name = f"{name}_wire{k}"
        wv.rotation_euler = (p1 - p0).to_track_quat("Z", "Y").to_euler()
        wv.data.materials.append(brass)
        S.link(wv, coll)
        parent_keep(wv, root)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.004, minor_radius=0.0008, location=(0, 0, -0.004),
                                     rotation=(math.radians(90), 0, 0))
    ring = bpy.context.active_object
    ring.location = Vector(loc) + Vector((0, 0, -0.004))
    ring.name = name + "_ring"
    ring.data.materials.append(brass)
    S.link(ring, coll)
    parent_keep(ring, root)
    return root, dish


def parent_keep(ob, par):
    bpy.context.view_layer.update()
    mw = ob.matrix_world.copy()
    ob.parent = par
    ob.matrix_parent_inverse = par.matrix_world.inverted()
    ob.matrix_world = mw


def weight(name, loc, h, r, coll, brass):
    """Stamped cylindrical brass weight with a knob."""
    prof = [(0.0, 0.0), (r, 0.0), (r, h), (r * 0.45, h + 0.0005), (r * 0.35, h + r * 0.5), (r * 0.5, h + r * 0.9),
            (0.0, h + r * 1.05)]
    prof, tags = P.fillet(prof, [0, 0.0006, 0.0008, 0.0006, 0.001, 0.002, 0], steps=4)
    ob = P.lathe(name, prof, 64, coll=coll, wobble=0.003, seed=int(h * 1e5) % 91)
    ob.location = loc
    ob.data.materials.append(brass)
    return ob


def build(res="look", samples=None, threshold=None, **kw):
    S.new_scene(res, PRESET, samples=samples, threshold=threshold, exposure=-0.9)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 0, FRAMES - 1
    coll = S.collection("S03")
    A.room(coll, floor=False, window_y=BASE.y + 0.03, exterior_strength=2.2)
    A.kraft_sheet("Kraft", size=(0.40, 0.30), center=(-0.30, 0.05, 0.0), rotation_z_deg=-6.0, seed=5, coll=coll)
    brass = M.metal("brass", name="Brass", seed=3, roughness=0.28, smudge=0.3, tarnish=0.5, color=(0.70, 0.46, 0.19))
    oak = M.wood("oak_scrubbed", name="BalanceOak", seed=21, value=0.45, scratches=0.8)
    # base box with a drawer and a knob
    P.slab("BalanceBase", size=(0.15, 0.34, 0.055), location=BASE + Vector((0, 0, 0.055)), bevel=0.003, material=oak,
           coll=coll)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.006, location=BASE + Vector((0.077, 0, 0.028)))
    knob = bpy.context.active_object
    knob.name = "DrawerKnob"
    knob.data.materials.append(brass)
    S.link(knob, coll)
    # column
    col_prof = [(0.0, 0.0), (0.028, 0.0), (0.028, 0.006), (0.018, 0.012), (0.009, 0.02), (0.0075, 0.03),
                (0.0065, PIVOT_Z - 0.03), (0.010, PIVOT_Z - 0.022), (0.006, PIVOT_Z - 0.012), (0.0, PIVOT_Z - 0.012)]
    col_prof, _ = P.fillet(col_prof, [0, 0.001, 0.003, 0.004, 0.004, 0.002, 0.002, 0.002, 0.001, 0], steps=4)
    column = P.lathe("Column", col_prof, 64, coll=coll)
    column.location = BASE + Vector((0, 0, 0.055))
    column.data.materials.append(brass)
    # beam (rotates about x, the axis towards the camera)
    pivot = S.empty("BeamPivot", BASE + Vector((0, 0, PIVOT_Z)), coll=coll)
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    beam = bpy.context.active_object
    beam.name = "Beam"
    beam.scale = (0.007, 2 * ARM + 0.012, 0.011)
    bpy.ops.object.transform_apply(scale=True)
    tp = beam.modifiers.new("taper", "SIMPLE_DEFORM")
    tp.deform_method, tp.deform_axis, tp.factor = "TAPER", "Y", -0.0
    bv = beam.modifiers.new("bev", "BEVEL")
    bv.width, bv.segments = 0.0012, 3
    beam.data.materials.append(brass)
    S.link(beam, coll)
    P.parent(beam, pivot)
    for side in (-1, 1):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.0045, depth=0.012, vertices=32,
                                            location=(0, side * ARM, 0), rotation=(0, math.radians(90), 0))
        boss = bpy.context.active_object
        boss.name = f"BeamEnd{side}"
        boss.data.materials.append(brass)
        S.link(boss, coll)
        P.parent(boss, pivot)
    # pointer (down from the pivot, in front of a small scale arc)
    bpy.ops.mesh.primitive_cone_add(radius1=0.0016, radius2=0.0003, depth=0.14, vertices=12,
                                    location=(0.0125, 0, -0.07), rotation=(math.radians(180), 0, 0))
    ptr = bpy.context.active_object
    ptr.name = "Pointer"
    ptr.data.materials.append(M.metal("steel_brushed", name="PointerSteel", roughness=0.3, seed=4))
    S.link(ptr, coll)
    P.parent(ptr, pivot)
    P.slab("IndexPlate", size=(0.0015, 0.034, 0.012), location=BASE + Vector((0.0105, 0, PIVOT_Z - 0.128)),
           bevel=0.0004, material=brass, coll=coll)
    # pans
    lp, ldish = pan("PanL", coll, brass, BASE + Vector((0, -ARM, PIVOT_Z)))
    rp, rdish = pan("PanR", coll, brass, BASE + Vector((0, ARM, PIVOT_Z)))
    bpy.context.view_layer.update()
    # botanicals on the left pan, weights on the right (built at the level pose, then parented)
    floor_l = lp.location.z - HANG + 0.002
    items = B.heap(center=(lp.location.x, lp.location.y, floor_l), radius=0.032, counts={"juniper": 60, "star_anise": 8},
                   seed=77, coll=coll, n_crumbs=0, height=0.03, spread=0.25)
    keep = []
    for ob in items:        # anything that rolled off the dish during the settle goes
        if (Vector(ob.matrix_world.translation[:2]) - Vector(lp.location[:2])).length > 0.05 or \
                ob.matrix_world.translation.z < floor_l - 0.003:
            bpy.data.objects.remove(ob, do_unlink=True)
        else:
            keep.append(ob)
    for ob in keep + [ldish]:
        parent_keep(ob, lp)
    parent_keep(rdish, rp)
    floor_r = rp.location.z - HANG + 0.0025
    for i, (dx, dy, h, r) in enumerate(((0.012, -0.014, 0.022, 0.0105), (-0.016, 0.004, 0.016, 0.0085),
                                         (0.006, 0.02, 0.011, 0.0065), (-0.004, -0.028, 0.008, 0.0055))):
        w = weight(f"Weight{i}", (rp.location.x + dx, rp.location.y + dy, floor_r), h, r, coll, brass)
        parent_keep(w, rp)
    # animation: beam angle per frame; pans hang plumb from the beam ends with a little pendulum lag
    for f in range(FRAMES):
        a = math.radians(beam_angle(f))
        pivot.rotation_euler = (a, 0, 0)
        pivot.keyframe_insert("rotation_euler", frame=f)
        lag = math.radians(beam_angle(max(f - 3, 0)) - beam_angle(f)) * 0.25
        for root, side in ((lp, -1), (rp, 1)):
            end = Matrix.Rotation(a, 3, "X") @ Vector((0, side * ARM, 0))
            root.location = pivot.location + end
            root.rotation_euler = (lag, 0, 0)
            root.keyframe_insert("location", frame=f)
            root.keyframe_insert("rotation_euler", frame=f)
    # light: low sun from the window behind the balance (rim), warm room fill from camera side
    lights = A.dawn(target=BASE + Vector((0, 0, 0.15)), azimuth_deg=10.0, elevation_deg=9.0, strength=7.0,
                    kelvin=3300, sky_strength=0.8, bounce=0.35, coll=coll,
                    align_window=False)
    S.world((0.004, 0.0045, 0.006), 1.0)
    cam_t = BASE + Vector((0, 0, 0.205))
    cam_p = cam_t + Vector((0.86, -0.07, 0.01))
    cam = C.add_camera("CAM_S03", lens=65, location=cam_p, target=cam_t, fstop=2.0,
                       focus=BASE + Vector((0.006, 0, PIVOT_Z - 0.06)))
    C.move(cam, [(0, cam_p), (FRAMES - 1, cam_p + (cam_t - cam_p).normalized() * 0.02)])
    C.breathe(cam, amplitude_deg=0.04, period_frames=60, seed=3)
    return dict(cam=cam)
