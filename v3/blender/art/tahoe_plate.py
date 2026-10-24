#!/usr/bin/env python3
"""E-X exterior plate: Lake Tahoe from the west shore at summer blue hour, looking east over the lake to the bare
granite ridges of the Carson Range.  Painted procedurally (numpy), linear-light float EXR-like data saved as 16-bit
PNG in sRGB for the emission card; the moon is NOT in the plate (it is its own object so it can rise).

Layers, top to bottom: indigo sky with a faint warm afterglow band low in the east-facing view and a few stars; a far
ridge (hazier, bluer) and a near ridge (granite, dark slate) whose highest crests catch the last pink alpenglow; a
ragged conifer line along the far shore; the lake: a rippled mirror of all of it, darkening towards the viewer.

    python3 v3/blender/art/tahoe_plate.py      -> textures/tahoe_plate.png (6144 x 2560)
"""
import os
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(os.path.dirname(HERE), "textures")
W, H = 6144, 2560
HORIZON = 0.58          # shoreline height (fraction from top)


def fbm1d(n, octaves, seed, base=8, ridged=False):
    rng = np.random.default_rng(seed)
    x = np.linspace(0, 1, n)
    out = np.zeros(n)
    amp, freq = 1.0, base
    for _ in range(octaves):
        pts = rng.random(freq + 2)
        xs = np.linspace(0, 1, freq + 2)
        v = np.interp(x, xs, pts)
        if ridged:
            v = 1 - np.abs(v * 2 - 1)
        out += amp * v
        amp *= 0.5
        freq *= 2
    return out / out.max()


def fbm2d(h, w, octaves, seed, base=4):
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp = 1.0
    for o in range(octaves):
        gh, gw = base * 2 ** o + 1, base * 2 ** o * w // h + 1
        g = rng.random((gh, gw)).astype(np.float32)
        img = Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        out += amp * (np.asarray(img, np.float32) / 255 - 0.5)
        amp *= 0.5
    return out


def srgb(x):
    x = np.clip(x, 0, None)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def main():
    os.makedirs(TEX, exist_ok=True)
    y = np.linspace(0, 1, H)[:, None]
    x = np.linspace(0, 1, W)[None, :]
    hz = int(H * HORIZON)
    img = np.zeros((H, W, 3), np.float32)
    # --- sky (linear radiance, about 0..1)
    t = np.clip(np.linspace(0, 1, H) / HORIZON, 0, 1)[:, None]          # (H, 1)
    top = np.array([0.010, 0.016, 0.055])
    mid = np.array([0.040, 0.055, 0.15])
    low = np.array([0.16, 0.13, 0.22])
    glow = np.array([0.30, 0.18, 0.20])
    sky = top * (1 - t) ** 2 + mid * 2 * t * (1 - t) + low * t ** 2       # (H, 3)
    sky = sky + glow * np.exp(-((t - 0.93) / 0.05) ** 2) * 0.6
    img[:] = sky[:, None, :]
    rng = np.random.default_rng(5)
    for _ in range(260):     # faint stars, only high up
        sx, sy = rng.integers(0, W), rng.integers(0, int(hz * 0.55))
        b = rng.uniform(0.05, 0.35) * (1 - sy / (hz * 0.55))
        img[sy:sy + 2, sx:sx + 2] += b
    # --- ridges (heights in px above the shoreline)
    far = (0.20 + 0.55 * fbm1d(W, 7, 11, base=5, ridged=True) + 0.06 * fbm1d(W, 6, 12, base=160)) * H * 0.20
    near = (0.10 + 0.70 * fbm1d(W, 8, 23, base=3, ridged=True) ** 1.4 + 0.08 * fbm1d(W, 7, 24, base=90, ridged=True)
            + 0.03 * fbm1d(W, 5, 25, base=700)) * H * 0.26
    rows = np.arange(H)[:, None]
    far_top = hz - far[None, :]
    near_top = hz - near[None, :]
    rock = fbm2d(H, W, 6, 3, base=6)
    # gullies: vertically stretched noise (rock structure running down the slopes)
    g = fbm2d(H // 8, W, 5, 4, base=2)
    gully = np.abs(np.asarray(Image.fromarray(((g + 0.5) * 255).clip(0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC),
                              np.float32) / 255 - 0.5) * 2
    m_far = rows >= far_top
    m_near = rows >= near_top
    far_col = np.array([0.050, 0.060, 0.12])
    img[m_far] = (far_col + 0.02 * rock[..., None] * np.array([1, 1, 1.4]))[m_far]
    granite = np.array([0.026, 0.028, 0.046]) * (1 + 0.5 * rock[..., None]) * (1 - 0.25 * gully[..., None])
    img[m_near] = granite[m_near]
    # alpenglow: the top 2-4 % of each ridge, stronger on the highest crests
    for top_row, hgt, k in ((near_top, near, 1.0), (far_top, far, 0.6)):
        depth = rows - top_row
        crest = (hgt / hgt.max())[None, :] ** 3
        a = np.clip(1 - depth / (H * 0.012 * (0.5 + crest)), 0, 1) * (depth >= 0) * crest * k
        img += a[..., None] * np.array([0.30, 0.12, 0.10]) * (0.8 + 0.4 * rock[..., None])
    # --- forest along the far shore: ragged conifer tops
    tree_h = (0.010 + 0.020 * fbm1d(W, 9, 31, base=60)) * H
    jag = np.abs(np.sin(np.linspace(0, W / 7.0, W) * np.pi)) ** 0.5 * H * 0.008
    tree_top = hz - tree_h - jag
    m_tree = (rows >= tree_top[None, :]) & (rows <= hz)
    img[m_tree] = np.array([0.008, 0.011, 0.016])
    # --- lake: mirror of everything above the shoreline, rippled, darker and bluer towards the viewer
    depth = H - hz
    src = img[hz - depth:hz][::-1].copy() if hz - depth >= 0 else img[:hz][::-1]
    lake = np.zeros((depth, W, 3), np.float32)
    rip = fbm2d(depth, W, 5, 7, base=40)
    for r in range(depth):
        f = r / depth
        shift = (rip[r] * (6 + 60 * f)).astype(int)
        line = np.roll(src[min(r, len(src) - 1)], 0, axis=0)
        idx = np.clip(np.arange(W) + shift, 0, W - 1)
        row = line[idx]
        # vertical smearing increases towards the viewer (wind ripples)
        lake[r] = row * (0.72 - 0.35 * f) + np.array([0.004, 0.006, 0.012]) * f
    # thin bright line where the far shore meets the water (calm strip)
    lake[:3] += np.array([0.02, 0.02, 0.035])
    img[hz:] = lake
    rgb8 = np.clip(srgb(np.clip(img, 0, 1)) * 255 + rng.random(img.shape) - 0.5, 0, 255).astype(np.uint8)
    Image.fromarray(rgb8, "RGB").save(os.path.join(TEX, "tahoe_plate.png"), optimize=True)
    Image.fromarray(rgb8, "RGB").resize((W // 4, H // 4)).save(os.path.join(TEX, "tahoe_plate_preview.jpg"))
    print("wrote tahoe_plate.png", W, H, "horizon row", hz)


if __name__ == "__main__":
    main()
