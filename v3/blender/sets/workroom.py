"""Set A -- Curt Mast's workroom, Wolfenbüttel, a winter dawn in 1934 (S01-S05).

Only what the lenses see: the scrubbed-oak workbench, the corner of two lime-plaster walls and the east window
(3 x 4 panes, oak glazing bars) with the low dawn sun coming through it, so its bars throw long diagonal shadows
across the bench.  Workroom coordinates: bench top at z = 0, the bench runs along x, the east wall (window) is
on the -x side, the north wall behind the bench at +y.

    import workroom as A
    A.room()                                   # bench, walls, window, floor
    A.dawn(target=(0, 0, 0.12), strength=1)    # sun through the window + skylight, aimed so a bar shadow
                                               #   crosses near `target` (offset, never a centred cross)
"""
import math

import bpy
from mathutils import Vector

import scene as S
import materials as M
import props as P

WALL_X = -0.95            # east wall plane (window wall)
NORTH_Y = 0.55            # north wall plane (behind the bench)
SILL_Z = 0.18             # window sill above the bench top
PANE = (0.21, 0.27)       # pane width (y) x height (z)
BAR = 0.024               # glazing bar width
FRAME = 0.055             # outer frame width
COLS, ROWS = 3, 4


def _box(name, size, loc, mat, coll=None, bevel=0.002):
    ob = P.slab(name, size=size, location=loc, bevel=bevel, material=mat, coll=coll)
    return ob


def window(center_y=-0.05, coll=None, glass=True, exterior=True, exterior_strength=6.0):
    """The east window in the plane x = WALL_X: frame, glazing bars, crown-glass panes, sill.
    Returns (window_root, opening (y0, y1, z0, z1))."""
    w = COLS * PANE[0] + (COLS - 1) * BAR + 2 * FRAME
    h = ROWS * PANE[1] + (ROWS - 1) * BAR + 2 * FRAME
    y0, z0 = center_y - w / 2, SILL_Z
    oak = M.wood("oak_scrubbed", name="WindowOak", seed=11, grain_axis="Z", value=0.55, dust=0.3)
    root = S.empty("Window", (WALL_X, 0, 0), coll=coll)
    d = 0.06    # depth of the frame members
    parts = []
    # outer frame
    parts.append(_box("WinFrameL", (d, FRAME, h), (WALL_X, y0 + FRAME / 2, z0 + h / 2), oak, coll))
    parts.append(_box("WinFrameR", (d, FRAME, h), (WALL_X, y0 + w - FRAME / 2, z0 + h / 2), oak, coll))
    parts.append(_box("WinFrameB", (d * 1.6, w, FRAME), (WALL_X + 0.012, center_y, z0 + FRAME / 2), oak, coll))
    parts.append(_box("WinFrameT", (d, w, FRAME), (WALL_X, center_y, z0 + h - FRAME / 2), oak, coll))
    # glazing bars
    for c in range(1, COLS):
        y = y0 + FRAME + c * PANE[0] + (c - 0.5) * BAR
        parts.append(_box(f"WinBarV{c}", (d * 0.7, BAR, h - 2 * FRAME), (WALL_X, y, z0 + h / 2), oak, coll, 0.004))
    for r in range(1, ROWS):
        z = z0 + FRAME + r * PANE[1] + (r - 0.5) * BAR
        parts.append(_box(f"WinBarH{r}", (d * 0.7, w - 2 * FRAME, BAR), (WALL_X, center_y, z), oak, coll, 0.004))
    if glass:
        gm = M.glass("CrownGlass", smudge=0.12, wavy=0.25, radius=0.3, seed=5)
        bpy.ops.mesh.primitive_plane_add(size=1.0, location=(WALL_X - 0.008, center_y, z0 + h / 2),
                                         rotation=(0, math.radians(90), 0))
        g = bpy.context.active_object
        g.name = "WindowGlass"
        g.scale = (h, w, 1)
        g.data.materials.append(gm)
        S.link(g, coll)
        g.visible_shadow = False         # thin panes: let the sun through unchanged
    if exterior:
        # winter dawn outside: pale cold sky, warmer towards the horizon; only ever seen out of focus
        m, t = M.new_material("DawnSky")
        z = t.math("SUBTRACT", 1.0, t.xyz(t.texco("Generated"))[0])     # the card is turned: local x runs down
        col = t.ramp(z, [(0.0, (1.0, 0.52, 0.24)), (0.3, (0.95, 0.74, 0.55)), (0.6, (0.62, 0.66, 0.78)), (1.0, (0.36, 0.48, 0.78))])
        t.output(t.node("ShaderNodeEmission", {"Color": col, "Strength": exterior_strength}))
        bpy.ops.mesh.primitive_plane_add(size=1.0, location=(WALL_X - 1.5, center_y, z0 + h / 2),
                                         rotation=(0, math.radians(90), 0))
        sky = bpy.context.active_object
        sky.name = "DawnSkyCard"
        sky.scale = (h * 3, w * 3, 1)
        sky.data.materials.append(m)
        sky.visible_shadow = False
        sky.visible_diffuse = False      # the skylight is done by the area light, keep the card out of GI
        S.link(sky, coll)
    return root, (y0 + FRAME, y0 + w - FRAME, z0 + FRAME, z0 + h - FRAME)


def room(coll=None, bench=True, walls=True, floor=True, window_y=-0.05, glass=True, exterior_strength=6.0):
    """Bench + plaster walls with the window opening + plank floor.  Returns dict of objects."""
    out = {}
    if bench:
        oak = M.wood("oak_scrubbed", name="BenchOak", seed=3, plank_width=0.2, dust=0.5, scratches=0.9)
        out["bench"] = _box("Bench", (2.0, 0.8, 0.07), (0.1, 0.05, -0.035), oak, coll, 0.002)
    if walls:
        pl = M.plaster("WallPlaster", seed=2, damp=0.5)
        win, (wy0, wy1, wz0, wz1) = window(window_y, coll, glass=glass, exterior_strength=exterior_strength)
        out["window"] = win
        H, z_floor = 2.6, -0.9
        # east wall around the opening (4 pieces), 0.3 m thick reveal
        t = 0.3
        x = WALL_X - t / 2 + 0.03
        out["wall_e1"] = _box("WallE_below", (t, 2.4, wz0 - z_floor), (x, 0.0, (wz0 + z_floor) / 2), pl, coll, 0.01)
        out["wall_e2"] = _box("WallE_above", (t, 2.4, z_floor + H - wz1), (x, 0.0, (wz1 + z_floor + H) / 2), pl, coll, 0.01)
        out["wall_e3"] = _box("WallE_left", (t, wy0 + 1.2, wz1 - wz0), (x, (wy0 - 1.2) / 2, (wz0 + wz1) / 2), pl, coll, 0.01)
        out["wall_e4"] = _box("WallE_right", (t, 1.2 - wy1, wz1 - wz0), (x, (wy1 + 1.2) / 2, (wz0 + wz1) / 2), pl, coll, 0.01)
        out["wall_n"] = _box("WallN", (3.0, 0.2, H), (WALL_X + 1.5, NORTH_Y + 0.1, z_floor + H / 2), pl, coll, 0.01)
    if floor:
        fl = M.wood("dark_table", name="FloorPlanks", seed=9, plank_width=0.18, dust=0.6, scratches=1.0, value=0.6)
        out["floor"] = _box("Floor", (4.0, 4.0, 0.03), (0.5, -0.8, -0.915), fl, coll, 0.0)
    return out


def sun_direction(azimuth_deg=28.0, elevation_deg=9.0):
    """Direction the sunlight travels (into the room, from the east window at -x)."""
    a, e = math.radians(azimuth_deg), math.radians(elevation_deg)
    return Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), -math.sin(e)))


def dawn(target=(0, 0, 0.1), azimuth_deg=28.0, elevation_deg=9.0, strength=4.0, kelvin=3300, sky_strength=1.5,
         sky_kelvin=9500, bounce=0.25, coll=None, bar_through=None, transom_through=None, align_window=True):
    """Low dawn sun through the window + cool skylight from the opening + a faint warm room bounce.
    The window is slid along the wall so that the shadow of a vertical glazing bar passes through the
    point `bar_through` and that of a horizontal bar through `transom_through` (default: near `target`,
    offset so they never cross dead centre).  Returns dict(sun, sky, bounce)."""
    d = sun_direction(azimuth_deg, elevation_deg)
    T = Vector(target)

    def wall_hit(pt):
        pt = Vector(pt)
        return pt - d * ((pt.x - WALL_X) / d.x)        # where the sun ray through pt crosses the wall plane
    hit = wall_hit(T)
    hv = wall_hit(bar_through if bar_through is not None else T + Vector((-0.05, 0, 0)))
    hh = wall_hit(transom_through if transom_through is not None else T + Vector((0, 0, 0.08)))
    sun = S.sun_light("DawnSun", strength=strength, kelvin=kelvin, azimuth_deg=0, elevation_deg=0, coll=coll)
    sun.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sun.data.angle = math.radians(0.53)
    # the window: put a vertical bar a little off the hit point
    win = bpy.data.objects.get("Window")
    out = dict(sun=sun, hit=hit)
    if win is not None and align_window:
        col_y = -0.05 - (COLS * PANE[0] + (COLS - 1) * BAR) / 2 + FRAME / 2 + PANE[0] + BAR / 2
        row_z = SILL_Z + FRAME + 2 * PANE[1] + 1.5 * BAR
        dy = hv.y - col_y
        dz = hh.z - row_z
        for ob in bpy.data.objects:
            if ob.name.startswith(("WinFrame", "WinBar", "WindowGlass", "DawnSkyCard", "WallE_")):
                ob.location.y += dy
                ob.location.z += dz
        out["window_shift"] = (dy, dz)
    sky = S.area_light("Skylight", size=(0.9, 1.2), power=sky_strength * 60, kelvin=sky_kelvin,
                       location=(WALL_X + 0.05, hit.y, hit.z), target=T, coll=coll)
    sky.data.shape = "RECTANGLE"
    sky.visible_camera = False
    out["sky"] = sky
    if bounce:
        b = S.area_light("RoomBounce", size=(1.5, 1.0), power=bounce * 40, kelvin=3000,
                         location=(T.x + 1.2, T.y - 0.9, T.z + 0.3), target=T, coll=coll)
        b.visible_camera = False
        b.visible_glossy = False
        out["bounce"] = b
    return out


def kraft_sheet(name="Kraft", size=(0.42, 0.30), center=(0, 0, 0), rotation_z_deg=0.0, seed=0, coll=None, res=4e-3):
    """Brown kraft paper lying on the bench: soft cockling + a few sharp fold creases, fibre shader."""
    import numpy as np
    from mathutils import noise as mn
    rng = np.random.default_rng(seed)
    nx, ny = int(size[0] / res) + 1, int(size[1] / res) + 1
    xs, ys = np.linspace(-size[0] / 2, size[0] / 2, nx), np.linspace(-size[1] / 2, size[1] / 2, ny)
    folds = [(rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.05, 0.05), rng.uniform(0.0004, 0.0012))
             for _ in range(3)]
    verts, faces = [], []
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            z = 0.0007 * mn.noise(Vector((x * 18 + seed, y * 18, 0.3))) + 0.00025 * mn.noise(Vector((x * 70, y * 70 + seed, 1.7)))
            for a, b, c, h in folds:      # a crease: a ridge along the line a*x + b*y = c
                d = abs(a * x + b * y - c) / math.hypot(a, b)
                z += h * max(0.0, 1 - d / 0.012) ** 2
            z = max(z, 0.0) + 0.00005
            verts.append((x, y, z))
    for j in range(ny - 1):
        for i in range(nx - 1):
            a = j * nx + i
            faces.append((a, a + 1, a + nx + 1, a + nx))
    ob = P.mesh(name, verts, faces, coll, True)
    ob.location = center
    ob.rotation_euler = (0, 0, math.radians(rotation_z_deg))
    m, t = M.new_material(name + "_Mat")
    p = t.texco("Object")
    fib = t.noise(t.mapping(p, scale=(1, 4, 1)), scale=1800.0, detail=4.0)
    blot = t.noise(p, scale=40.0, detail=4.0)
    spk = t.smooth(t.noise(p, scale=900.0, detail=2.0), 0.68, 0.74)
    col = t.mixc(t.add(t.mul(t.add(blot, -0.5), 0.6), 0.5), (0.20, 0.12, 0.060), (0.27, 0.17, 0.085))
    col = t.mixc(t.mul(t.add(fib, -0.5), 0.3), col, (0.0, 0.0, 0.0), blend="MULTIPLY")
    col = t.mixc(t.mul(spk, 0.5), col, (0.09, 0.05, 0.025))
    t.output(t.principled(base=col, rough=0.82, sheen=0.3, sheen_rough=0.5, normal=t.bump(t.add(fib, t.mul(blot, 0.5)), 0.35, 0.0002)))
    ob.data.materials.append(m)
    ob["collider"] = True
    return ob


def apothecary_jar(name, location, height=0.14, radius=0.035, seed=0, coll=None, tint=(0.55, 0.30, 0.08), fill=0.7):
    """Amber glass apothecary jar with dark contents and a ground-glass stopper (only ever seen out of focus)."""
    H, R = height, radius
    prof = [(0.0, 0.0), (R * 0.9, 0.0), (R, 0.006), (R, H * 0.72), (R * 0.82, H * 0.82), (R * 0.42, H * 0.86),
            (R * 0.42, H * 0.92), (R * 0.5, H * 0.94), (R * 0.5, H), (0.0, H * 1.08)]
    prof, tags = P.fillet(prof, [0, 0.003, 0.004, 0.01, 0.008, 0.003, 0.001, 0.001, 0.002, 0], steps=5)
    ob = P.lathe(name, prof, 72, coll=coll, wobble=0.003, seed=seed)
    ob.location = location
    ob.data.materials.append(M.glass(name + "_Glass", absorb=tint, density=40.0, smudge=0.15, radius=R, seed=seed))
    inner = [(0.0, 0.004), (R * 0.9, 0.004), (R * 0.92, H * 0.72 * fill), (0.0, H * 0.72 * fill)]
    c = P.lathe(name + "_contents", inner, 48, coll=coll)
    c.location = location
    mc, tc = M.new_material(name + "_Contents")
    n = tc.noise(scale=400.0, detail=3.0)
    tc.output(tc.principled(base=tc.mixc(n, (0.05, 0.03, 0.015), (0.12, 0.07, 0.03)), rough=0.8))
    c.data.materials.append(mc)
    return ob
