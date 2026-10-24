"""camera.py -- camera rig, focus empty, rack focus with lens breathing, motion-control easing.

    import camera as C
    cam = C.add_camera("CAM", lens=100, location=(0, -0.5, 0.06), target=(0, 0, 0.03),
                       fstop=2.8, focus=(0, -0.022, 0.035))        # focus: point, object or distance (m)
    C.rack_focus(cam, [(0, (0, -0.02, 0.03)), (24, (0, 0.05, 0.03))])   # keyed focus empty + 1.5 % breathing
    C.move(cam, [(0, (0, -0.5, 0.06)), (44, (0.03, -0.48, 0.06))])      # Bezier-eased slide (location only)
    C.breathe(cam, amplitude_deg=0.05, seed=3)                          # no frame is CG-still

Conventions: 36 mm sensor, horizontal fit, real focal lengths and f-stops, metric scene.
Anamorphic feel: dof.aperture_ratio = 1.5, 0 blades (vertical oval bokeh).
Frame numbers are shot-local (0 = first frame of the shot).
"""
import math

import bpy
from mathutils import Vector

import scene as S


def _vec(p):
    if hasattr(p, "matrix_world"):
        return p.matrix_world.translation.copy()
    return Vector(p)


def fcurves(id_data):
    """All F-curves of an ID's assigned action (Blender 5 layered actions)."""
    ad = id_data.animation_data
    if not ad or not ad.action:
        return []
    from bpy_extras import anim_utils
    cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    return list(cb.fcurves) if cb else []


def fcurve(id_data, data_path, index=0):
    for fc in fcurves(id_data):
        if fc.data_path == data_path and fc.array_index == index:
            return fc
    return None


def set_interpolation(id_data, data_path=None, interp="BEZIER", easing="AUTO", handles="AUTO_CLAMPED"):
    """Set interpolation of all keys (optionally one data_path) of an ID."""
    for fc in fcurves(id_data):
        if data_path and fc.data_path != data_path:
            continue
        for k in fc.keyframe_points:
            k.interpolation = interp
            k.easing = easing
            k.handle_left_type = handles
            k.handle_right_type = handles
        fc.update()


def add_camera(name="CAM", lens=50.0, location=(0, -1, 0.1), target=None, rotation_deg=None,
               fstop=2.8, focus=None, sensor=36.0, aperture_ratio=1.5, blades=0,
               clip=(0.005, 500.0), active=True, coll=None):
    """Create a camera.  `target` aims it (point/object).  `focus` is a point/object (a focus empty
    `<name>_FOCUS` is created/used) or a distance in metres.  Returns the camera object."""
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_fit = "HORIZONTAL"
    cd.sensor_width = sensor
    cd.sensor_height = sensor * 804.0 / 1920.0
    cd.clip_start, cd.clip_end = clip
    cd.dof.use_dof = fstop is not None
    if fstop:
        cd.dof.aperture_fstop = fstop
    cd.dof.aperture_blades = blades
    cd.dof.aperture_ratio = aperture_ratio
    cam = bpy.data.objects.new(name, cd)
    cam.location = location
    S.link(cam, coll)
    if target is not None:
        S.look_at(cam, _vec(target))
    elif rotation_deg is not None:
        cam.rotation_euler = [math.radians(a) for a in rotation_deg]
    if focus is not None:
        set_focus(cam, focus)
    elif target is not None:
        set_focus(cam, target)
    if active:
        bpy.context.scene.camera = cam
    return cam


def focus_empty(cam):
    """The camera's focus empty (created on demand at its current focus distance)."""
    e = cam.data.dof.focus_object
    if e is None:
        bpy.context.view_layer.update()
        e = S.empty(cam.name + "_FOCUS", size=0.01, coll=cam.users_collection[0] if cam.users_collection else None)
        fwd = cam.matrix_world.to_3x3() @ Vector((0, 0, -1))
        e.location = cam.location + fwd * max(cam.data.dof.focus_distance, 0.05)
        cam.data.dof.focus_object = e
    return e


def set_focus(cam, focus):
    """focus: point (x, y, z), object, or distance (float, metres)."""
    if isinstance(focus, (int, float)):
        cam.data.dof.focus_object = None
        cam.data.dof.focus_distance = float(focus)
        return None
    if hasattr(focus, "matrix_world"):
        cam.data.dof.focus_object = focus
        return focus
    e = focus_empty(cam)
    e.location = Vector(focus)
    return e


def focus_distance(cam, point):
    """Distance along the view axis from cam to point (what Cycles focuses on)."""
    bpy.context.view_layer.update()
    m = cam.matrix_world
    fwd = m.to_3x3() @ Vector((0, 0, -1))
    return (Vector(point) - m.translation).dot(fwd)


def rack_focus(cam, keys, breathing=0.015, interp="BEZIER"):
    """Keyframe a rack focus.  keys = [(frame, point_or_object), ...] (shot-local frames).
    The focus empty is keyed at each point; the focal length breathes by up to `breathing`
    (1.5 %) linearly in diopters between the nearest and farthest focus key, so a near->far
    rack shortens the lens slightly like real glass."""
    e = focus_empty(cam)
    base = cam.data.lens
    pts = [(f, _vec(p)) for f, p in keys]
    diopt = [1.0 / max(focus_distance(cam, p), 1e-3) for _, p in pts]
    d0, dmin, dmax = diopt[0], min(diopt), max(diopt)
    span = max(dmax - dmin, 1e-6)
    for (f, p), dp in zip(pts, diopt):
        e.location = p
        e.keyframe_insert("location", frame=f)
        cam.data.lens = base * (1.0 + breathing * (dp - d0) / span)
        cam.data.keyframe_insert("lens", frame=f)
    cam.data.lens = base
    set_interpolation(e, "location", interp)
    set_interpolation(cam.data, "lens", interp)
    return e


def move(obj, keys, rotations_deg=None, interp="BEZIER", easing="AUTO"):
    """Motion-control move: keys = [(frame, location), ...]; optional rotations_deg =
    [(frame, (rx, ry, rz)), ...].  Bezier with auto-clamped handles = eased start/stop and
    no overshoot.  To keep a subject framed while sliding, use aim_keys() instead of rotations."""
    for f, loc in keys:
        obj.location = Vector(loc)
        obj.keyframe_insert("location", frame=f)
    for f, rot in (rotations_deg or []):
        obj.rotation_euler = [math.radians(a) for a in rot]
        obj.keyframe_insert("rotation_euler", frame=f)
    set_interpolation(obj, None, interp, easing)
    return obj


def aim_keys(obj, keys, interp="BEZIER"):
    """Keyframe rotation so obj looks at a moving target: keys = [(frame, point_or_object), ...].
    Use together with move() for slides that keep a subject framed."""
    for f, tgt in keys:
        bpy.context.scene.frame_set(f)
        S.look_at(obj, _vec(tgt))
        obj.keyframe_insert("rotation_euler", frame=f)
    set_interpolation(obj, "rotation_euler", interp)
    return obj


def slide(obj, frame0, frame1, offset, interp="BEZIER"):
    """Eased linear slide of `offset` metres between two shot-local frames."""
    a = obj.location.copy()
    return move(obj, [(frame0, a), (frame1, a + Vector(offset))], interp=interp)


def breathe(obj, amplitude_deg=0.05, period_frames=60.0, seed=0):
    """Add tiny seeded noise to rotation (and nothing else), so no frame is CG-still.
    amplitude_deg is the approximate peak deviation."""
    if fcurve(obj, "rotation_euler", 0) is None:
        obj.keyframe_insert("rotation_euler", frame=bpy.context.scene.frame_start)
    for i in range(3):
        fc = fcurve(obj, "rotation_euler", i)
        m = fc.modifiers.new("NOISE")
        m.scale = period_frames
        m.strength = math.radians(amplitude_deg) * 2.0 * (0.6 if i == 1 else 1.0)
        m.phase = 13.7 * (seed + 1) + 41.3 * i
        m.depth = 1
    return obj


def frame_width(cam, distance):
    """Width (m) of the field of view at `distance` from the lens (horizontal fit)."""
    return cam.data.sensor_width / cam.data.lens * distance


def dof_depth(cam, distance, coc_mm=0.025):
    """Approximate total depth of field (m) at a focus distance (thin-lens, 0.025 mm CoC)."""
    f = cam.data.lens / 1000.0
    N = cam.data.dof.aperture_fstop
    c = coc_mm / 1000.0
    return 2.0 * N * c * distance ** 2 / (f ** 2)
