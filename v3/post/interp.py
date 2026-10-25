#!/usr/bin/env python3
"""Fill the in-between frames of shots rendered on twos with motion-compensated interpolation (ffmpeg minterpolate).

    python3 v3/post/interp.py s07 s13 ...     -> v3/frames/<shot>_24/####.png (full 24 fps, local frame numbers)
Even frames are the renders themselves; odd frames are interpolated.  Time-lapse shots (s04) keep the hold instead.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FR = os.path.join(os.path.dirname(HERE), "frames")


def interp(shot):
    src = os.path.join(FR, shot)
    frames = sorted(int(f[:4]) for f in os.listdir(src) if f.endswith(".png") and f[:4].isdigit())
    evens = [f for f in frames if f % 2 == 0]
    if len(evens) < 2:
        print(shot, "not enough frames")
        return
    tmp = tempfile.mkdtemp(prefix=f"interp_{shot}_")
    for i, f in enumerate(evens):
        os.symlink(os.path.join(src, f"{f:04d}.png"), os.path.join(tmp, f"{i:04d}.png"))
    out = os.path.join(FR, f"{shot}_24")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "12", "-i", os.path.join(tmp, "%04d.png"),
                    "-vf", "minterpolate=fps=24:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1:scd=none",
                    "-pix_fmt", "rgb48be", "-start_number", str(evens[0]), os.path.join(out, "%04d.png")], check=True)
    # the renders themselves stay authoritative on even frames
    for f in evens:
        shutil.copyfile(os.path.join(src, f"{f:04d}.png"), os.path.join(out, f"{f:04d}.png"))
    shutil.rmtree(tmp)
    print(shot, "->", len(os.listdir(out)), "frames")


if __name__ == "__main__":
    for s in sys.argv[1:]:
        interp(s)
