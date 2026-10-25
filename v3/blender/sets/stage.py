"""Set F -- the glass stage (S17-S20): the highball on the dark lacquered bar top, the lodge reduced to what the
glass reflects and refracts: the moon window (a cool, bright panel behind), the pink neon tubes (behind-left), warm
enamel pendant bokeh above, a dim back bar.  Everything except the glass is far out of focus.

    import stage as F
    F.stage(coll)                 # bar top, backdrop cards, lights
    hb = F.glass(coll, drink=...) # the highball (P.highball), centred at HB
"""
import math

import bpy
from mathutils import Vector

import scene as S
import materials as M
import props as P

HB = Vector((0.0, 0.0, 0.0))


def stage(coll, moon=True, neon=True):
    top = P.slab("BarTop", size=(1.6, 1.2, 0.05), location=(0, 0.2, 0.0), bevel=0.01,
                 material=M.wood("dark_table", name="StageBar", seed=3, plank_width=0.155, grain_axis="Y", value=0.8), coll=coll)
    wall = P.slab("BackWall", size=(4.0, 0.05, 2.0), location=(0, 2.0, 1.4), bevel=0.0,
                  material=M.backdrop("StageWall", (0.03, 0.018, 0.010)), coll=coll)
    out = dict(top=top)
    if moon:
        # the window: a cool, softly graded panel with the mullion cross (out of focus it is a big blue-silver glow)
        m, t = M.new_material("WindowPanel")
        g = t.texco("Generated")
        gx, gy, gz = t.xyz(g)
        col = t.ramp(gy, [(0.0, (0.05, 0.06, 0.12)), (0.45, (0.20, 0.22, 0.38)), (1.0, (0.10, 0.12, 0.30))])
        bars = t.math("MAXIMUM", t.math("LESS_THAN", t.math("ABSOLUTE", t.add(gx, -0.5)), 0.012),
                      t.math("LESS_THAN", t.math("ABSOLUTE", t.add(gy, -0.55)), 0.015))
        col = t.mixc(bars, col, (0.0, 0.0, 0.0))
        t.output(t.node("ShaderNodeEmission", {"Color": col, "Strength": 0.7}))
        bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0.25, 1.9, 0.78), rotation=(math.radians(90), 0, 0))
        win = bpy.context.active_object
        win.name = "WindowPanel"
        win.scale = (1.6, 0.9, 1)
        win.data.materials.append(m)
        S.link(win, coll)
        mm, mt = M.new_material("MoonDot")
        mt.output(mt.node("ShaderNodeEmission", {"Color": (1.0, 0.97, 0.9), "Strength": 12.0}))
        bpy.ops.mesh.primitive_circle_add(vertices=64, radius=0.06, fill_type="NGON", location=(-0.05, 1.88, 0.78),
                                          rotation=(math.radians(90), 0, 0))
        moon_ob = bpy.context.active_object
        moon_ob.name = "MoonDot"
        moon_ob.data.materials.append(mm)
        S.link(moon_ob, coll)
        out["window"] = win
    if neon:
        nm = M.emission(color=(1.0, 0.16, 0.48), strength=14.0, name="StageNeon")
        for k, (x0, z0, x1, z1) in enumerate(((-0.55, 0.30, -0.55, 0.55), (-0.45, 0.30, -0.30, 0.55), (-0.30, 0.55, -0.30, 0.30),
                                              (-0.2, 0.30, -0.05, 0.30))):
            cu = bpy.data.curves.new(f"StageNeon{k}", "CURVE")
            cu.dimensions = "3D"
            cu.bevel_depth = 0.006
            sp = cu.splines.new("POLY")
            sp.points.add(1)
            sp.points[0].co = (x0, 1.7, z0, 1)
            sp.points[1].co = (x1, 1.7, z1, 1)
            ob = bpy.data.objects.new(f"StageNeon{k}", cu)
            ob.data.materials.append(nm)
            S.link(ob, coll)
        sp = S.area_light("NeonSpill", size=(0.4, 0.3), power=3.0, color=(1.0, 0.16, 0.48), location=(-0.4, 1.5, 0.45),
                          target=HB + Vector((0, 0, 0.09)), coll=coll)
    warm = M.emission(kelvin=2600, strength=30.0, name="PendantBokeh")
    for k, (x, y, z) in enumerate(((0.5, 1.2, 0.9), (-0.6, 1.4, 1.0), (0.1, 1.6, 1.1))):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.035, location=(x, y, z))
        b = bpy.context.active_object
        b.name = f"PendantBokeh{k}"
        b.data.materials.append(warm)
        b.visible_shadow = False
        S.link(b, coll)
    # lights: the pendant straight above (the hero key on the drink), a cool rim from the window, a low warm fill
    out["pendant"] = S.spot_light("Pendant", power=40.0, kelvin=2700, location=HB + Vector((0.02, 0.05, 0.9)),
                                  target=HB + Vector((0, 0, 0.09)), angle_deg=26, blend=0.6, radius=0.05, coll=coll)
    out["rim"] = S.area_light("WindowRim", size=(0.6, 0.4), power=10.0, kelvin=9000, location=HB + Vector((0.15, 0.7, 0.25)),
                              target=HB + Vector((0, 0, 0.09)), coll=coll)
    out["fill"] = S.area_light("Fill", size=(0.5, 0.3), power=1.5, kelvin=3200, location=HB + Vector((-0.4, -0.6, 0.2)),
                               target=HB + Vector((0, 0, 0.09)), coll=coll, glossy_visible=False)
    # the product photographer's trick: a warm glow card right behind the glass so the drink lights up gold
    gm, gt = M.new_material("GlowCard")
    g = gt.texco("Generated")
    gx, gy, gz = gt.xyz(g)
    fall = gt.mul(gt.math("SUBTRACT", 1.0, gt.smooth(gt.math("ABSOLUTE", gt.add(gx, -0.5)), 0.12, 0.5)),
                  gt.math("SUBTRACT", 1.0, gt.smooth(gt.math("ABSOLUTE", gt.add(gy, -0.5)), 0.12, 0.5)))
    gt.output(gt.add_shader(gt.node("ShaderNodeBsdfTransparent"),
                            gt.node("ShaderNodeEmission", {"Color": (1.0, 0.78, 0.45), "Strength": gt.mul(fall, 1.5)})))
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=HB + Vector((0.0, 0.32, 0.075)), rotation=(math.radians(90), 0, 0))
    card = bpy.context.active_object
    card.name = "GlowCard"
    card.scale = (0.34, 0.26, 1)
    card.data.materials.append(gm)
    card.visible_shadow = False
    card.visible_diffuse = False
    S.link(card, coll)
    out["glow"] = card
    S.world((0.002, 0.002, 0.004), 1.0)
    return out


def energy_drink():
    return M.energy_drink("StageDrink", density=14.0)


def glass(coll, drink=None, fill=0.62, bubbles=True, seed=5, cond_facing_deg=-90.0, n_drops=6000):
    return P.highball("Highball", location=HB, fill=fill, seed=seed, coll=coll, drink_material=drink or energy_drink(),
                      bubbles=bubbles, cond_facing_deg=cond_facing_deg, n_drops=n_drops)


def plume(coll, clock_keys, fill_z, mouth=Vector((0.0, 0.0, 0.069)), mix_keys=((0, 0.0),), name="Plume"):
    """The Jägermeister plume: an absorption volume (cylinder filling the drink) whose density is an animated,
    domain-warped plume rising and spiralling out of the sunken shot glass's mouth, plus a uniform 'mixed' term.
    clock_keys: [(frame, plume time 0..1+)]; mix_keys: [(frame, uniform density)]."""
    m, t = M.new_material(name)
    p = t.texco("Object")
    x, y, z = t.xyz(p)
    clk = t.node("ShaderNodeValue")
    clk.name = "PlumeClock"
    for f, v in clock_keys:
        clk.outputs[0].default_value = v
        clk.outputs[0].keyframe_insert("default_value", frame=f)
    T = clk.outputs[0]
    h = t.add(z, -mouth.z)
    # warp: large slow swirl + finer turbulence, both growing with height
    w1 = t.noise(t.mapping(p, scale=(40.0, 40.0, 25.0)), scale=1.0, detail=2.0, w=t.mul(T, 1.6), dims="4D", out="Color")
    w2 = t.noise(t.mapping(p, scale=(160.0, 160.0, 120.0)), scale=1.0, detail=3.0, w=t.mul(T, 3.0), dims="4D", out="Color")
    grow = t.math("MINIMUM", t.mul(t.math("MAXIMUM", h, 0.0), 30.0), 1.0)
    warp = t.vmath("ADD", t.vmath("SCALE", t.vmath("SUBTRACT", w1, (0.5, 0.5, 0.5)), scale=0.016),
                   t.vmath("SCALE", t.vmath("SUBTRACT", w2, (0.5, 0.5, 0.5)), scale=0.005))
    wx, wy, wz = t.xyz(warp)
    # spiral: the axis drifts round as it rises
    ang = t.add(t.mul(h, 90.0), t.mul(T, 2.5))
    ax = t.mul(t.mul(t.math("SINE", ang), 0.008), grow)
    ay = t.mul(t.mul(t.math("COSINE", ang), 0.008), grow)
    dx = t.add(t.add(x, t.mul(wx, grow)), t.mul(ax, -1.0))
    dy = t.add(t.add(y, t.mul(wy, grow)), t.mul(ay, -1.0))
    rad = t.math("SQRT", t.add(t.mul(dx, dx), t.mul(dy, dy)))
    R = t.add(0.006, t.add(t.mul(t.math("MAXIMUM", h, 0.0), 0.25), t.mul(T, 0.004)))
    core = t.math("SUBTRACT", 1.0, t.smooth(t.math("DIVIDE", rad, R), 0.25, 1.0))
    front = t.math("SUBTRACT", 1.0, t.smooth(h, t.mul(T, 0.05), t.add(t.mul(T, 0.05), 0.01)))
    start = t.smooth(h, -0.004, 0.003)
    turb = t.noise(t.mapping(p, scale=(300.0, 300.0, 200.0)), scale=1.0, detail=4.0, w=t.mul(T, 2.0), dims="4D")
    lace = t.math("POWER", t.math("MAXIMUM", t.add(turb, -0.3), 0.0), 2.0)
    dens = t.mul(t.mul(t.mul(core, front), start), t.add(0.15, t.mul(lace, 6.0)))
    mixv = t.node("ShaderNodeValue")
    mixv.name = "PlumeMix"
    for f, v in mix_keys:
        mixv.outputs[0].default_value = v
        mixv.outputs[0].keyframe_insert("default_value", frame=f)
    total = t.add(t.mul(dens, 380.0), mixv.outputs[0])
    vol = t.node("ShaderNodeVolumeAbsorption", {"Color": (0.42, 0.11, 0.04), "Density": total})
    t.output(None, vol)
    import camera as C
    for fc in C.fcurves(m.node_tree):
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
    bpy.ops.mesh.primitive_cylinder_add(radius=0.0262, depth=fill_z - 0.009 - 0.0012, vertices=96,
                                        location=HB + Vector((0, 0, 0.009 + (fill_z - 0.009 - 0.0012) / 2)))
    ob = bpy.context.active_object
    bpy.ops.object.transform_apply(location=True)          # object space = highball space (the plume field uses z)
    ob.name = name
    ob.data.materials.append(m)
    S.link(ob, coll)
    return ob


def ink_tendrils(coll, grow_keys, fill_z, mouth=Vector((0.0, 0.0, 0.069)), n=52, seed=7, name="Ink", spin_deg=40.0,
                 frames=60):
    """The Jägermeister leaving the sunken shot glass as ink-like filaments: tapered tubes spiralling up from the lip,
    curling over at the top like a vortex ring.  The tubes carry a HOMOGENEOUS absorption volume only (no surface),
    which Cycles integrates analytically -- far cheaper than a ray-marched plume.  grow_keys: [(frame, 0..1)]."""
    import random as _r
    rng = _r.Random(seed)
    m, t = M.new_material(name)
    t.output(None, t.node("ShaderNodeVolumeAbsorption", {"Color": (0.42, 0.11, 0.04), "Density": 380.0}))
    # every filament carries a soft halo: the liqueur already diffusing into the drink around its core
    m3, t3 = M.new_material(name + "Halo")
    t3.output(None, t3.node("ShaderNodeVolumeAbsorption", {"Color": (0.66, 0.34, 0.14), "Density": 26.0}))
    m2, t2 = M.new_material(name + "Haze")
    t2.output(None, t2.node("ShaderNodeVolumeAbsorption", {"Color": (0.55, 0.22, 0.08), "Density": 60.0}))
    root = S.empty(name + "Root", HB, coll=coll)
    obs = []
    top = fill_z - 0.004
    for k in range(n):
        a0 = rng.uniform(0, 2 * math.pi)
        r0 = rng.uniform(0.012, 0.019)
        hz = rng.uniform(0.55, 1.0) * (top - mouth.z)
        turns = rng.uniform(0.25, 0.9) * rng.choice([-1, 1])
        pts = []
        steps = 28
        for i in range(steps + 1):
            u = i / steps
            z = mouth.z + hz * (u ** 0.85)
            a = a0 + turns * 2 * math.pi * u
            r = r0 * (1 - 0.55 * math.sin(math.pi * min(u * 1.2, 1.0))) + 0.004 * math.sin(7 * u + k)
            # curl over at the top (a vortex ring rolling outwards)
            if u > 0.75:
                c = (u - 0.75) / 0.25
                r += 0.010 * math.sin(c * math.pi * 0.9)
                z -= 0.006 * (1 - math.cos(c * math.pi * 0.9))
            pts.append((r * math.cos(a), r * math.sin(a), z - HB.z))
        cu = bpy.data.curves.new(f"{name}{k}", "CURVE")
        cu.dimensions = "3D"
        thick = rng.uniform(0.0004, 0.0016) if k % 5 else rng.uniform(0.002, 0.0035)
        cu.bevel_depth = thick
        cu.bevel_resolution = 3
        cu.use_fill_caps = True
        cu.bevel_factor_mapping_end = "SPLINE"
        sp = cu.splines.new("NURBS")
        sp.points.add(len(pts) - 1)
        for i, p in enumerate(pts):
            sp.points[i].co = (*p, 1)
            sp.points[i].radius = 0.5 + 0.9 * math.sin(math.pi * min(i / steps * 1.1, 1.0))
        sp.use_endpoint_u = True
        sp.order_u = 4
        ob = bpy.data.objects.new(f"{name}{k}", cu)
        ob.data.materials.append(m if k % 5 else m2)
        S.link(ob, coll)
        ob.parent = root
        delay = rng.uniform(0.0, 0.25)
        for f, g in grow_keys:
            cu.bevel_factor_end = max(0.0, min(1.0, (g - delay) / (1 - delay)))
            cu.keyframe_insert("bevel_factor_end", frame=f)
        obs.append(ob)
        halo = bpy.data.objects.new(f"{name}Halo{k}", cu.copy())
        halo.data.bevel_depth = thick * 3.0 + 0.0018
        halo.data.materials.clear()
        halo.data.materials.append(m3)
        S.link(halo, coll)
        halo.parent = root
        obs.append(halo)
    # the whole cloud turns slowly as it rises
    root.rotation_euler = (0, 0, 0)
    root.keyframe_insert("rotation_euler", frame=0)
    root.rotation_euler = (0, 0, math.radians(spin_deg))
    root.keyframe_insert("rotation_euler", frame=frames - 1)
    return obs
