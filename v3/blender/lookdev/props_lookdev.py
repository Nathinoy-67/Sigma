"""props_lookdev.py -- look-dev proof of the hero props (v3 "ONE YEAR. ONE SECOND.").

Renders four stills into v3/lookdev/ on a dark wooden table, one soft key + one cool rim, shallow DOF:
  1 props_01_frosted_shot.jpg   frosted shot glass of Jagermeister
  2 props_02_highball.jpg       highball of energy drink with condensation, bubbles, foam ring
  3 props_03_bottle.jpg         the square-shouldered bottle with our label
  4 props_04_botanicals.jpg     a heap of botanicals in macro

    nice -n 10 /home/user/tools/blender-venv/bin/python v3/blender/lookdev/props_lookdev.py \
        [--only 1,3] [--samples 32] [--res 640x268] [--blend]

Writes v3/lookdev/props_lookdev_timings.json (render seconds per image at that size).
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

import botanicals as B  # noqa: E402
import camera as C  # noqa: E402
import materials as M  # noqa: E402
import props as P  # noqa: E402
import scene as S  # noqa: E402


def stage(seed=0, wall_y=3.0):
    """Dark wooden table + an out-of-focus room behind it + a very dim world."""
    S.world((0.0018, 0.0016, 0.0015), 1.0)
    table = P.slab("Table", size=(2.4, 3.2, 0.045), location=(0, 1.1, 0),
                   material=M.wood("dark_table", seed=seed, dust=0.35, scratches=0.7))
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, wall_y, 0.6), rotation=(math.pi / 2, 0, 0))
    w = bpy.context.object
    w.name = "BackWall"
    w.scale = (8.0, 2.4, 1.0)
    w.data.materials.append(M.backdrop("Wall", color=(0.05, 0.035, 0.025), seed=seed))
    # a warm practical's pool of light on the back wall (motivated, out of focus)
    S.spot_light("WallPool", power=14.0, kelvin=2700, location=(0.35, wall_y - 0.8, 1.2), target=(0.2, wall_y, 0.55),
                 angle_deg=60, blend=0.8, radius=0.05)
    return table


def practicals(cam, seed=0, n=5, dist=(1.8, 2.8), size=0.008, strength=260.0):
    """Small warm practicals far behind the subject, inside the frame: oval anamorphic bokeh."""
    import random
    from mathutils import Vector
    rng = random.Random(seed)
    bpy.context.view_layer.update()
    mw = cam.matrix_world
    fwd, right, up = (mw.to_3x3() @ Vector(v) for v in ((0, 0, -1), (1, 0, 0), (0, 1, 0)))
    half_w = cam.data.sensor_width / cam.data.lens / 2
    half_h = half_w * bpy.context.scene.render.resolution_y / bpy.context.scene.render.resolution_x
    for i in range(n):
        d = rng.uniform(*dist)
        sx = rng.uniform(-0.9, 0.9) * half_w * d
        sy = rng.uniform(0.15, 0.85) * half_h * d
        p = mw.translation + fwd * d + right * sx + up * sy
        bpy.ops.mesh.primitive_uv_sphere_add(radius=size * rng.uniform(0.7, 1.3), location=p, segments=16, ring_count=8)
        b = bpy.context.object
        b.name = f"Practical{i}"
        b.data.materials.append(M.emission(kelvin=rng.choice([2400, 2700, 3000]), strength=strength * rng.uniform(0.4, 1.0),
                                           name=f"PracticalMat{i}"))
        b.visible_shadow = False
        b.visible_diffuse = False
        b.visible_glossy = False


def lights(subject, key_az=-55, key_el=32, key_dist=0.75, key_size=0.5, key_power=40.0, key_k=4200,
           rim_az=155, rim_el=18, rim_dist=0.65, rim_size=(0.12, 0.7), rim_power=30.0, rim_k=7000,
           rim_exclude=None):
    """One soft key (front-left softbox) + one cool rim strip behind (the 'moon window')."""
    sx, sy, sz = subject

    def pos(az, el, d):
        a, e = math.radians(az), math.radians(el)
        return (sx + d * math.sin(a) * math.cos(e), sy - d * math.cos(a) * math.cos(e), sz + d * math.sin(e))
    key = S.area_light("Key", size=(key_size, key_size), power=key_power, kelvin=key_k, location=pos(key_az, key_el, key_dist),
                       target=subject, spread_deg=110)
    rim = S.area_light("Rim", size=rim_size, power=rim_power, kelvin=rim_k, location=pos(rim_az, rim_el, rim_dist),
                       target=subject, spread_deg=90)
    rim_exclude = rim_exclude if rim_exclude is not None else [o for o in bpy.data.objects if o.name == "Table"]
    if rim_exclude:
        S.light_link(rim, exclude=rim_exclude)      # no rim streak across the glossy table top
    return key, rim


def still_frosted_shot(args):
    S.new_scene(res=args.res, preset="glass", samples=args.samples, threshold=0.03, exposure=0.0)
    stage(seed=1)
    P.shot_glass("Shot", location=(0, 0, 0), frosted=True, fill=0.80, seed=4, frost=0.9, frost_wipes=2,
                 melt_beads=110)
    # an out-of-focus frosted bottle behind for context
    P.bottle("BottleBG", location=(0.10, 0.20, 0), rotation_z_deg=-18, seed=2, frosted=True)
    lights((0, 0, 0.035), key_power=1.4, key_dist=0.6, key_az=-75, key_el=26, rim_power=2.4, rim_az=145, rim_el=20,
           rim_dist=0.5)
    cam = C.add_camera("CAM", lens=100, location=(-0.035, -0.45, 0.118), target=(0.004, 0, 0.034),
                       fstop=3.5, focus=(0, -0.020, 0.04))
    practicals(cam, seed=1)
    return cam


def still_highball(args):
    S.new_scene(res=args.res, preset="glass", samples=args.samples, threshold=0.03, exposure=0.0)
    stage(seed=2)
    P.highball("Highball", location=(0, 0, 0), fill=0.62, seed=5, cond_facing_deg=-100)
    lights((0, 0, 0.08), key_power=2.4, key_dist=0.7, key_az=-70, key_el=30, rim_power=2.2, rim_az=180, rim_el=22,
           rim_dist=0.55, rim_size=(0.05, 0.6))
    cam = C.add_camera("CAM", lens=100, location=(-0.07, -0.90, 0.118), target=(0.0, 0, 0.066),
                       fstop=4.0, focus=(0, -0.031, 0.08))
    practicals(cam, seed=2)
    return cam


def still_bottle(args):
    S.new_scene(res=args.res, preset="glass", samples=args.samples, threshold=0.03, exposure=0.0)
    stage(seed=3)
    P.bottle("Bottle", location=(0, 0, 0), rotation_z_deg=-16, seed=1)
    P.shot_glass("ShotBG", location=(0.125, -0.075, 0), frosted=False, fill=0.78, seed=9)
    lights((0, 0, 0.12), key_power=3.5, key_dist=0.85, key_size=0.7, key_az=-55, key_el=26, rim_power=14.0,
           rim_az=180, rim_el=6, rim_dist=0.55, rim_size=(0.6, 1.2))
    cam = C.add_camera("CAM", lens=85, location=(-0.10, -1.72, 0.19), target=(0.03, 0, 0.118),
                       fstop=4.0, focus=(0, -0.045, 0.10))
    practicals(cam, seed=3)
    return cam


def still_botanicals(args):
    S.new_scene(res=args.res, preset="default", samples=args.samples, threshold=0.03, exposure=0.0)
    stage(seed=4)
    B.heap(center=(0, 0, 0), radius=0.045, seed=7)
    lights((0, 0, 0.01), key_power=1.0, key_dist=0.45, key_size=0.4, key_az=-70, key_el=42, rim_power=1.0,
           rim_az=150, rim_el=25, rim_dist=0.4, rim_size=(0.1, 0.5))
    cam = C.add_camera("CAM", lens=100, location=(-0.05, -0.40, 0.19), target=(0.0, 0.0, 0.008),
                       fstop=11.0, focus=(0.0, -0.012, 0.014))
    practicals(cam, seed=4)
    return cam


STILLS = {
    1: ("props_01_frosted_shot.jpg", still_frosted_shot),
    2: ("props_02_highball.jpg", still_highball),
    3: ("props_03_bottle.jpg", still_bottle),
    4: ("props_04_botanicals.jpg", still_botanicals),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="1,2,3,4")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--res", default="640x268")
    ap.add_argument("--blend", action="store_true", help="also save the .blend next to the still")
    ap.add_argument("--out", default=S.LOOKDEV)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    args = ap.parse_args(argv)
    w, h = (int(v) for v in args.res.split("x"))
    args.res = (w, h)
    tpath = os.path.join(args.out, "props_lookdev_timings.json")
    timings = json.load(open(tpath)) if os.path.exists(tpath) else {}
    for k in [int(v) for v in args.only.split(",")]:
        fname, fn = STILLS[k]
        t0 = time.time()
        fn(args)
        tb = time.time() - t0
        path = os.path.join(args.out, fname)
        if args.blend:
            S.save_blend(path.replace(".jpg", ".blend"))
        dt = S.render_still(path)
        timings[fname] = dict(render_s=round(dt, 1), build_s=round(tb, 1), res=f"{w}x{h}", samples=args.samples)
        print(f"[lookdev] {fname}: build {tb:.1f}s  render {dt:.1f}s  ({w}x{h}, {args.samples} spp)", flush=True)
        json.dump(timings, open(tpath, "w"), indent=2)


if __name__ == "__main__":
    main()
