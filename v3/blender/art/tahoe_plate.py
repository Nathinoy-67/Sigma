#!/usr/bin/env python3
"""E-X exterior plate: Lake Tahoe from the west shore under a full moon, looking east over the lake to the
Carson Range.  Painted procedurally (numpy), saved as 16-bit-quality 8-bit sRGB PNG for the emission card; the moon
is NOT in the plate (it is its own object so it can rise).

Layers, top to bottom: night sky, deep at the zenith and paler towards the horizon, with a faint warm glow behind the
range and small stars; three ridges in aerial perspective (the farthest palest and bluest, with moonlit snow lying in
the couloirs of the high peaks; the nearest dark, lit from the moon side); a band of haze low over the water; the
far-shore conifers as individual spires; the lake: a mirror of all of it, broken into horizontal ripple streaks
that grow towards the viewer, darker where the view looks steeply down (Fresnel).

    python3 v3/blender/art/tahoe_plate.py      -> textures/tahoe_plate.png (6144 x 2560)
"""
import os

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, uniform_filter1d

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(os.path.dirname(HERE), "textures")
W, H = 6144, 2560
HORIZON = 0.58          # shoreline height (fraction from top)


def profile(n, seed, base, octaves, gain=0.5, ridged=False, warp=0.0):
    """1D fractal profile in 0..1, cubic-smooth at every octave (no straight segments)."""
    rng = np.random.default_rng(seed)
    x = np.linspace(0, 1, n)
    if warp:
        x = np.clip(x + warp * (profile(n, seed + 99, 3, 3) - 0.5), 0, 1)
    out = np.zeros(n)
    amp, freq, norm = 1.0, base, 0.0
    for _ in range(octaves):
        pts = rng.random(freq + 4)
        xs = np.linspace(-1.0 / freq, 1 + 1.0 / freq, freq + 4)
        v = np.interp(x, xs, pts)
        v = gaussian_filter(v, sigma=max(1.0, 0.35 * n / freq))
        v = (v - v.min()) / max(1e-6, v.max() - v.min())
        if ridged:
            v = 1 - np.abs(v * 2 - 1)
        out += amp * v
        norm += amp
        amp *= gain
        freq *= 2
    out /= norm
    return (out - out.min()) / (out.max() - out.min())


def noise2d(h, w, seed, base, octaves, stretch=(1.0, 1.0), gain=0.5):
    """2D fbm in -0.5..0.5; stretch=(sy, sx) elongates the features (sy > 1: taller features)."""
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp = 1.0
    for o in range(octaves):
        f = base * 2 ** o
        gh = max(2, int(f / stretch[0]) + 1)
        gw = max(2, int(f * w / h / stretch[1]) + 1)
        g = rng.random((gh, gw)).astype(np.float32)
        img = Image.fromarray(g, "F").resize((w, h), Image.BICUBIC)
        out += amp * (np.asarray(img, np.float32) - 0.5)
        amp *= gain
    return out


def mdp(n, seed, rough=0.6, peaks=1.0, levels=13):
    """1D midpoint displacement (a real fractal mountain profile), resampled to n, 0..1; peaks > 1 sharpens summits."""
    rng = np.random.default_rng(seed)
    m = 2 ** levels + 1
    v = np.zeros(m)
    v[0], v[-1] = rng.random(), rng.random()
    step, amp = m - 1, 1.0
    while step > 1:
        half = step // 2
        mids = np.arange(half, m - 1, step)
        v[mids] = 0.5 * (v[mids - half] + v[mids + half]) + amp * (rng.random(len(mids)) - 0.5)
        step, amp = half, amp * 2 ** (-rough)
    v = (v - v.min()) / (v.max() - v.min())
    v = np.interp(np.linspace(0, m - 1, n), np.arange(m), v)
    return v ** peaks


def sample(tex, depth, scale):
    """Look a (rows, W) texture up by crest-relative depth (rows below the crest) times scale."""
    r = np.clip((depth * scale).astype(np.int32), 0, tex.shape[0] - 1)
    return np.take_along_axis(tex, r, axis=0)


def srgb(x):
    x = np.clip(x, 0, None)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def main():
    os.makedirs(TEX, exist_ok=True)
    hz = int(H * HORIZON)
    rows = np.arange(H, dtype=np.float32)[:, None]
    img = np.zeros((H, W, 3), np.float32)

    # --- sky: zenith navy to a paler moonlit blue at the horizon, a faint warm glow behind the range
    t = np.clip(np.arange(H) / hz, 0, 1)[:, None]
    zen = np.array([0.006, 0.010, 0.032])
    hor = np.array([0.090, 0.100, 0.190])
    sky = zen + (hor - zen) * t ** 2.2
    sky = sky + np.array([0.040, 0.026, 0.030]) * np.exp(-((1 - t) / 0.07) ** 2)
    img[:] = sky[:, None, :]
    rng = np.random.default_rng(5)
    stars = np.zeros((hz, W), np.float32)
    n = 900
    sx, sy = rng.integers(0, W, n), (rng.random(n) ** 1.6 * hz * 0.75).astype(int)
    stars[sy, sx] = rng.random(n) ** 3 * 2.2 * (1 - sy / (hz * 0.75))
    stars = gaussian_filter(stars, 1.1) * 7
    img[:hz] += stars[..., None] * np.array([0.85, 0.9, 1.0])

    # --- ridges in aerial perspective (heights in rows above the shoreline)
    far = (0.12 + 0.88 * mdp(W, 11, rough=0.62, peaks=1.6)) * H * 0.15
    mid = (0.15 + 0.85 * mdp(W, 21, rough=0.58, peaks=1.2)) * H * 0.075
    near = (0.25 + 0.75 * mdp(W, 31, rough=0.55)) * H * 0.032
    layers = [  # (heights, base colour, lit colour, snow, haze amount)
        (far, np.array([0.052, 0.060, 0.118]), np.array([0.080, 0.090, 0.155]), 1.0, 0.45),
        (mid, np.array([0.026, 0.031, 0.062]), np.array([0.042, 0.049, 0.090]), 0.3, 0.30),
        (near, np.array([0.012, 0.015, 0.028]), np.array([0.019, 0.023, 0.040]), 0.0, 0.15),
    ]
    xs = np.arange(W)
    for li, (hgt, base, lit, snow_k, haze) in enumerate(layers):
        top = hz - hgt[None, :]
        m = rows >= top
        # crest-relative coordinates (against a smoothed crest, so texture follows the range, not every notch)
        depth = np.clip(rows - top, 0, None)                                     # rows below the crest
        sdepth = np.clip(rows - (hz - gaussian_filter(hgt, 60)[None, :]) + H * 0.02, 0, None)
        # moonlight: faces turned towards the moon (upper left) are lit.  Spurs broaden down the slope, so the
        # facet orientation comes from the silhouette smoothed more and more with depth below the crest.
        lv = np.clip(np.log2(1 + depth / 6.0), 0, 4).astype(np.float32)
        face = np.zeros((H, W), np.float32)
        for i, sig in enumerate((2, 6, 18, 54, 160)):
            w = np.clip(1 - np.abs(lv - i), 0, 1)
            face += w * np.clip(0.45 - np.gradient(gaussian_filter(hgt, sig)) * 1.4, 0, 1).astype(np.float32)[None, :]
        rock = sample(noise2d(1024, W, 50 + li, 12, 6, stretch=(1.5, 1.0)), sdepth, 1024 / (H * 0.2))
        k = np.clip(face * np.exp(-depth / (H * 0.06)) + 0.8 * rock, 0, 1)
        col = base + (lit - base) * k[..., None]
        col = col * (1 + 0.25 * rock[..., None])
        if snow_k:
            # snow fields and couloirs on the high crests: broken patches hanging from the ridge line
            crest = np.clip((hgt / hgt.max() - 0.35) / 0.45, 0, 1)[None, :]
            sn = sample(noise2d(1024, W, 60 + li, 20, 6, stretch=(1.8, 1.0), gain=0.6), sdepth, 1024 / (H * 0.2))
            reach = H * (0.012 + 0.05 * crest)
            snow = np.clip((sn + 0.10 - depth / reach * 0.35) / 0.06, 0, 1) * (depth < reach) * crest * snow_k
            snow *= np.clip(depth / 3.0, 0, 1)                                    # no white outline on the crest
            col = col + snow[..., None] * (np.array([0.12, 0.13, 0.20]) * (0.55 + 0.6 * face[..., None]) - col)
        # aerial haze: the foot of each range sinks into the air over the lake
        hz_band = np.exp(-((hz - rows) / (H * 0.03)) ** 2) * haze
        col = col + (hor - col) * hz_band[..., None] * 0.8
        img = np.where(m[..., None], col, img)

    # --- haze band low over the water
    band = np.exp(-((hz - rows) / (H * 0.018)) ** 2) * (rows <= hz)
    img = img + (hor * 0.9 - img) * (band[..., None] * 0.35)

    # --- far-shore conifers: individual spires along the shoreline
    tree = np.zeros(W, np.float32)
    density = profile(W, 70, 12, 4)
    pos = 0.0
    while pos < W:
        h = (0.004 + 0.014 * rng.random() ** 1.5) * H * (0.6 + 0.8 * density[int(pos)])
        w = h * rng.uniform(0.18, 0.28)
        x0 = int(pos)
        lo, hi = max(0, x0 - int(w) - 1), min(W, x0 + int(w) + 2)
        spire = h * np.clip(1 - np.abs(xs[lo:hi] - pos) / w, 0, 1) ** 0.85
        tree[lo:hi] = np.maximum(tree[lo:hi], spire)
        pos += w * rng.uniform(0.35, 1.1)
    tree = np.maximum(tree, (0.003 + 0.002 * profile(W, 71, 200, 3)) * H)      # undergrowth
    m_tree = rows >= (hz - tree[None, :])
    img = np.where(m_tree[..., None], np.array([0.007, 0.009, 0.015]), img)

    # --- lake: rippled mirror of the rows above the shoreline
    depth = H - hz
    r = np.arange(depth, dtype=np.float32)[:, None]
    f = r / depth
    rip = noise2d(depth, W, 7, 6, 6, stretch=(1.0, 14.0), gain=0.6)              # long horizontal ripples
    dy = rip * (1.5 + 0.10 * r)
    dx = noise2d(depth, W, 8, 10, 4, stretch=(1.0, 6.0)) * (2 + 30 * f)
    src_r = np.clip(np.round(hz - 1 - r + dy), 0, hz - 1).astype(np.int32)
    src_x = np.clip(np.round(np.arange(W)[None, :] + dx), 0, W - 1).astype(np.int32)
    refl = img[src_r, src_x]
    # ripples smear the reflection sideways, more so close to the viewer
    out = np.empty_like(refl)
    edges = np.linspace(0, depth, 9).astype(int)
    for i in range(8):
        a, b = edges[i], edges[i + 1]
        out[a:b] = uniform_filter1d(refl[a:b], size=3 + 6 * i, axis=1)
    fres = (0.80 - 0.55 * f ** 0.7)[..., None]
    water = np.array([0.003, 0.005, 0.010])
    lake = out * fres + water * (1 - fres)
    lake[:2] += np.array([0.010, 0.012, 0.022])           # the calm strip under the far shore
    img[hz:] = lake

    rgb8 = np.clip(srgb(np.clip(img, 0, 1)) * 255 + rng.random(img.shape) - 0.5, 0, 255).astype(np.uint8)
    Image.fromarray(rgb8, "RGB").save(os.path.join(TEX, "tahoe_plate.png"), optimize=True)
    Image.fromarray(rgb8, "RGB").resize((W // 4, H // 4)).save(os.path.join(TEX, "tahoe_plate_preview.jpg"))
    print("wrote tahoe_plate.png", W, H, "horizon row", hz)


if __name__ == "__main__":
    main()
