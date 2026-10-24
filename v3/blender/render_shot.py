#!/usr/bin/env python3
"""Build one shot and render frames (shot-local frame numbers).

    /home/user/tools/blender-venv/bin/python v3/blender/render_shot.py --shot s01 --res look --frames 20,40
    ... --shot s01 --res hd --range 0-74 [--step 2] [--samples 48] [--out v3/frames/s01]
    ... --shot s01 --blend /tmp/s01.blend          # just build and save for inspection

--res: look 640x268 | previs 960x402 | hd 1280x536 | final 1920x804 | WxH.
Look-dev stills go to v3/lookdev/<shot>_<frame>.jpg unless --out is given; ranges go to v3/frames/<shot>/####.png.
Every shot is deterministic (fixed seeds), so ranges can be rendered on different machines and spliced.
"""
import argparse
import importlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
for d in ("lib", "sets", "shots"):
    sys.path.insert(0, os.path.join(HERE, d))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import scene as S  # noqa: E402

RES = {"look": (640, 268), "previs": (960, 402), "hd": (1280, 536), "final": (1920, 804)}
DEFAULT_Q = {"look": (16, 0.05), "previs": (12, 0.1), "hd": (40, 0.03), "final": (64, 0.025)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", required=True)
    ap.add_argument("--res", default="look")
    ap.add_argument("--frames", default=None, help="comma list of single frames (stills)")
    ap.add_argument("--range", default=None, help="a-b inclusive")
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--samples", type=int, default=None)
    ap.add_argument("--threshold", type=float, default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--blend", default=None)
    ap.add_argument("--variant", default=None, help="shot-specific option (e.g. a still state)")
    ap.add_argument("--fmt", default="jpg")
    a = ap.parse_args()
    shot = importlib.import_module(a.shot.lower())
    res = RES.get(a.res) or tuple(int(v) for v in a.res.split("x"))
    q = DEFAULT_Q.get(a.res, (32, 0.03))
    samples = a.samples or q[0]
    thr = a.threshold or q[1]
    t0 = time.time()
    info = shot.build(res=res, samples=samples, threshold=thr, variant=a.variant) or {}
    S.set_resolution(res)
    S.set_quality(samples, thr, min(8, samples))
    t_build = time.time() - t0
    print(f"[build] {a.shot} {res[0]}x{res[1]} {samples} spp thr {thr}: {t_build:.1f}s", flush=True)
    if a.blend:
        S.save_blend(a.blend)
    times = {}
    if a.frames:
        for f in [int(v) for v in a.frames.split(",")]:
            tag = f"_{a.variant}" if a.variant else ""
            out = a.out or os.path.join(S.LOOKDEV, f"{a.shot.lower()}{tag}_{f:04d}.{a.fmt}")
            if a.out and os.path.isdir(a.out):
                out = os.path.join(a.out, f"{a.shot.lower()}{tag}_{f:04d}.{a.fmt}")
            times[f] = S.render_still(out, frame=f, quiet=False)
    if a.range:
        f0, f1 = (int(v) for v in a.range.split("-"))
        out_dir = a.out or os.path.join(S.FRAMES, a.shot.lower() + (f"_{a.variant}" if a.variant else ""))
        times.update(S.render_frames(out_dir, f0, f1, a.step, fmt="PNG"))
    if times:
        v = list(times.values())
        print(f"[done] {len(v)} frames, mean {sum(v)/len(v):.1f}s, build {t_build:.1f}s", flush=True)


if __name__ == "__main__":
    main()
