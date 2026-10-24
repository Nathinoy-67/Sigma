#!/usr/bin/env python3
"""SIM 2 -- the hero plunge, as a 3D MLS-MPM liquid (Taichi, CPU).  Mantaflow does not run in the bpy module.

A highball (inner radius 27.5 mm, floor at 8 mm) holds energy drink up to FILL_Z; a full shot glass (a 44 x 60 mm
solid cylinder, prescribed motion) drops from the rim, breaks the surface at T_IMPACT and sinks to the floor.  The
5 mm annulus between shot and wall throws the displaced drink up the walls as a crown that tears into spray.

Weakly compressible fluid (p = K (1 - J)), APIC transfer, 1 mm grid, ~4 particles per cell.  Grid boundary conditions:
slip at the glass wall (below the rim) and floor, no-slip inside the moving shot.

Output schedule (film-facing): S18 = 48 frames at 1/400 s, then S19 = 30 frames at 1/150 s.
Writes <out>/p_####.npy (float16 positions in metres, N x 3) and <out>/meta.json (shot motion per output frame).
    /home/user/tools/bpy45-venv/bin/python v3/blender/sims/mpm_plunge.py --out v3/frames/sim2
"""
import argparse
import json
import math
import os
import time

import numpy as np
import taichi as ti

R_IN, FLOOR, RIM, FILL_Z = 0.0275, 0.008, 0.150, 0.095
SHOT_R, SHOT_H = 0.0222, 0.060
V_IMP = 1.05
T_IMPACT = 0.030                         # s after the start: the shot meets the surface
DX = 0.001
ORIGIN = np.array([-0.034, -0.034, 0.0])
NX, NY, NZ = 68, 68, 210
RHO, K_BULK = 1000.0, 7.0e4
G = 9.81


def shot_z(t):
    """Base height of the shot at time t (s) and its vertical velocity."""
    tt = t - T_IMPACT
    if tt < 0:
        z = FILL_Z - V_IMP * tt - 0.5 * G * tt * tt
        v = -(V_IMP + G * tt)
    else:
        vt, k = 0.32, 60.0
        z = FILL_Z - (vt * tt + (V_IMP - vt) / k * (1 - math.exp(-k * tt)))
        v = -(vt + (V_IMP - vt) * math.exp(-k * tt))
    if z <= FLOOR + 0.0004:
        return FLOOR + 0.0004, 0.0
    return z, v


def schedule():
    ts = [i / 400.0 for i in range(48)]
    t0 = ts[-1]
    ts += [t0 + (i + 1) / 150.0 for i in range(30)]
    return ts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="v3/frames/sim2")
    ap.add_argument("--ppc", type=float, default=4.0, help="particles per cell")
    ap.add_argument("--frames", type=int, default=None, help="only the first n output frames (test)")
    ap.add_argument("--dx", type=float, default=0.001)
    a = ap.parse_args()
    global DX, NX, NY, NZ
    DX = a.dx
    NX = NY = int(round(0.068 / DX))
    NZ = int(round(0.210 / DX))
    os.makedirs(a.out, exist_ok=True)
    ti.init(arch=ti.cpu, default_fp=ti.f32, cpu_max_num_threads=4)

    # --- particles: the drink column
    sp = DX / a.ppc ** (1 / 3)
    rng = np.random.default_rng(1)
    xs = np.arange(-R_IN + sp / 2, R_IN, sp)
    zs = np.arange(FLOOR + sp / 2, FILL_Z, sp)
    gx, gy, gz = np.meshgrid(xs, xs, zs, indexing="ij")
    pts = np.stack([gx.ravel(), gy.ravel(), gz.ravel()], 1)
    pts = pts[(pts[:, 0] ** 2 + pts[:, 1] ** 2) < (R_IN - 0.0004) ** 2]
    pts += rng.uniform(-0.3, 0.3, pts.shape) * sp
    n = len(pts)
    print(f"[mpm] {n} particles, spacing {sp * 1000:.2f} mm, grid {NX}x{NY}x{NZ}", flush=True)
    p_vol = sp ** 3
    p_mass = RHO * p_vol
    x = ti.Vector.field(3, ti.f32, n)
    v = ti.Vector.field(3, ti.f32, n)
    C = ti.Matrix.field(3, 3, ti.f32, n)
    J = ti.field(ti.f32, n)
    gv = ti.Vector.field(3, ti.f32, (NX, NY, NZ))
    gm = ti.field(ti.f32, (NX, NY, NZ))
    x.from_numpy((pts - ORIGIN).astype(np.float32))
    J.fill(1.0)
    inv_dx = 1.0 / DX
    org = ti.Vector(list(ORIGIN))
    hi = ti.Vector([(NX - 3) * DX, (NY - 3) * DX, (NZ - 3) * DX])

    @ti.kernel
    def p2g(dt: ti.f32):
        for I in ti.grouped(gm):
            gv[I] = ti.Vector([0.0, 0.0, 0.0])
            gm[I] = 0.0
        for p in x:
            base = (x[p] * inv_dx - 0.5).cast(int)
            fx = x[p] * inv_dx - base.cast(float)
            w = [0.5 * (1.5 - fx) ** 2, 0.75 - (fx - 1) ** 2, 0.5 * (fx - 0.5) ** 2]
            stress = -dt * 4 * inv_dx * inv_dx * p_vol * K_BULK * (J[p] - 1.0)
            affine = ti.Matrix.identity(ti.f32, 3) * stress + p_mass * C[p]
            for i, j, k in ti.static(ti.ndrange(3, 3, 3)):
                off = ti.Vector([i, j, k])
                dpos = (off.cast(float) - fx) * DX
                wt = w[i][0] * w[j][1] * w[k][2]
                idx = base + off
                if 0 <= idx[0] < NX and 0 <= idx[1] < NY and 0 <= idx[2] < NZ:
                    gv[idx] += wt * (p_mass * v[p] + affine @ dpos)
                    gm[idx] += wt * p_mass

    @ti.kernel
    def grid_op(dt: ti.f32, sz: ti.f32, svz: ti.f32):
        for i, j, k in gm:
            if gm[i, j, k] > 0:
                vel = gv[i, j, k] / gm[i, j, k]
                vel[2] -= dt * G
                pos = ti.Vector([i, j, k]).cast(float) * DX + org
                r = ti.sqrt(pos[0] ** 2 + pos[1] ** 2)
                # glass wall (below the rim): slip, may separate
                if r >= R_IN and pos[2] < RIM:
                    nrm = ti.Vector([pos[0] / r, pos[1] / r, 0.0])
                    vn = vel.dot(nrm)
                    if vn > 0:
                        vel -= vn * nrm
                if pos[2] <= FLOOR and vel[2] < 0:
                    vel[2] = 0.0
                # the shot glass: no-slip with the moving solid
                if r <= SHOT_R and pos[2] >= sz and pos[2] <= sz + SHOT_H:
                    vel = ti.Vector([0.0, 0.0, svz])
                # domain box
                if i < 2 and vel[0] < 0:
                    vel[0] = 0.0
                if i > NX - 3 and vel[0] > 0:
                    vel[0] = 0.0
                if j < 2 and vel[1] < 0:
                    vel[1] = 0.0
                if j > NY - 3 and vel[1] > 0:
                    vel[1] = 0.0
                if k < 2 and vel[2] < 0:
                    vel[2] = 0.0
                if k > NZ - 3 and vel[2] > 0:
                    vel[2] = 0.0
                gv[i, j, k] = vel

    @ti.kernel
    def g2p(dt: ti.f32):
        for p in x:
            base = (x[p] * inv_dx - 0.5).cast(int)
            fx = x[p] * inv_dx - base.cast(float)
            w = [0.5 * (1.5 - fx) ** 2, 0.75 - (fx - 1) ** 2, 0.5 * (fx - 0.5) ** 2]
            nv = ti.Vector([0.0, 0.0, 0.0])
            nC = ti.Matrix.zero(ti.f32, 3, 3)
            for i, j, k in ti.static(ti.ndrange(3, 3, 3)):
                off = ti.Vector([i, j, k])
                dpos = off.cast(float) - fx
                idx = base + off
                if 0 <= idx[0] < NX and 0 <= idx[1] < NY and 0 <= idx[2] < NZ:
                    g = gv[idx]
                    wt = w[i][0] * w[j][1] * w[k][2]
                    nv += wt * g
                    nC += 4 * inv_dx * wt * g.outer_product(dpos)
            v[p] = nv
            C[p] = nC
            J[p] *= 1 + dt * nC.trace()
            J[p] = ti.max(0.6, ti.min(1.4, J[p]))
            x[p] += dt * nv
            # keep particles inside the grid
            for d in ti.static(range(3)):
                x[p][d] = ti.max(2.5 * DX, ti.min(x[p][d], hi[d]))

    c = math.sqrt(K_BULK / RHO)
    times = schedule()
    if a.frames:
        times = times[:a.frames]
    t, f_out = 0.0, 0
    meta = dict(times=times, shot=[], n=n, dx=DX)
    t_wall = time.time()
    steps = 0
    vmax = 1.0
    while f_out < len(times):
        if t >= times[f_out] - 1e-9:
            P = x.to_numpy() + ORIGIN.astype(np.float32)
            np.save(os.path.join(a.out, f"p_{f_out:04d}.npy"), P.astype(np.float16))
            z, vz = shot_z(t)
            meta["shot"].append((t, z, vz))
            json.dump(meta, open(os.path.join(a.out, "meta.json"), "w"))
            print(f"[mpm] frame {f_out} t={t * 1000:.1f} ms  steps {steps}  {time.time() - t_wall:.0f}s", flush=True)
            f_out += 1
            continue
        if steps % 50 == 0:
            vmax = float(np.abs(v.to_numpy()).max())
        dt = min(0.3 * DX / (c + vmax), times[f_out] - t)
        dt = max(dt, 1e-7)
        sz, svz = shot_z(t + dt)
        p2g(dt)
        grid_op(dt, sz, svz)
        g2p(dt)
        t += dt
        steps += 1
    json.dump(meta, open(os.path.join(a.out, "meta.json"), "w"))
    print(f"[mpm] done: {len(times)} frames, {steps} steps, {time.time() - t_wall:.0f}s", flush=True)


if __name__ == "__main__":
    main()
