#!/usr/bin/env python3
"""Chalk marks for the cask heads (no handwriting font is installed, so every digit is a hand-authored stroke list).

Each digit is a list of strokes; each stroke a list of (x, y) points in a 0..1 x 0..1.6 cell (y down).  Strokes are
drawn as Catmull-Rom curves with pressure-varying width, per-stroke jitter, and grainy chalk breakup (chalk skips over
the wood grain: the mask is multiplied by a horizontal-streaked noise).  Output (L, 2048 px square, 1 = chalk):

    textures/chalk_1934.png          '1934' with a loose circle around it (S06 hero cask: matches the GEHEIM stamp)
    textures/chalk_1935.png          '1934' struck through, '1935' beside it, fresh (S07)
    textures/chalk_<year>.png        background casks: 1931 .. 1936 with different hands
    python3 v3/blender/art/chalk.py
"""
import math, os, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(os.path.dirname(HERE), "textures")
N = 2048

DIGITS = {
    "1": [[(0.25, 0.35), (0.55, 0.05), (0.55, 1.55)]],
    "9": [[(0.85, 0.45), (0.6, 0.08), (0.2, 0.15), (0.12, 0.5), (0.4, 0.75), (0.78, 0.6), (0.86, 0.35)],
          [(0.86, 0.35), (0.82, 0.9), (0.66, 1.4), (0.3, 1.55)]],
    "3": [[(0.15, 0.25), (0.45, 0.05), (0.8, 0.2), (0.72, 0.62), (0.38, 0.75)],
          [(0.38, 0.75), (0.85, 0.95), (0.82, 1.35), (0.45, 1.58), (0.1, 1.4)]],
    "4": [[(0.62, 0.05), (0.08, 1.05), (0.95, 1.05)], [(0.68, 0.45), (0.66, 1.58)]],
    "5": [[(0.85, 0.08), (0.25, 0.1), (0.18, 0.7)], [(0.18, 0.7), (0.55, 0.62), (0.86, 0.9), (0.82, 1.32), (0.45, 1.58), (0.1, 1.45)]],
    "6": [[(0.8, 0.1), (0.35, 0.4), (0.12, 1.0), (0.3, 1.52), (0.75, 1.45), (0.82, 1.05), (0.45, 0.85), (0.15, 1.05)]],
    "2": [[(0.12, 0.35), (0.4, 0.05), (0.8, 0.2), (0.75, 0.65), (0.1, 1.55), (0.9, 1.52)]],
}


def catmull(pts, n=14):
    P = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = (np.array(P[j], float) for j in (i - 1, i, i + 1, i + 2))
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(np.array(P[-2], float))
    return out


class Hand:
    def __init__(self, seed, slant=0.12, width=0.10):
        self.r = random.Random(seed)
        self.slant, self.width = slant + self.r.uniform(-0.05, 0.05), width * self.r.uniform(0.85, 1.15)

    def stroke(self, d, pts, ox, oy, size, slant=True, wpx=None, jitter=0.025):
        r = self.r
        sl = self.slant if slant else 0.0
        jit = [(x + r.gauss(0, jitter), y + r.gauss(0, jitter)) for x, y in pts]
        curve = catmull(jit)
        L = len(curve)
        for k in range(L - 1):
            (x0, y0), (x1, y1) = curve[k], curve[k + 1]
            u = k / max(L - 1, 1)
            press = 0.65 + 0.35 * math.sin(math.pi * min(1.0, u * 1.3)) + r.uniform(-0.08, 0.08)
            w = max(1, int((wpx or self.width * size) * press))
            X0 = ox + (x0 - sl * y0) * size
            Y0 = oy + y0 * size
            X1 = ox + (x1 - sl * y1) * size
            Y1 = oy + y1 * size
            d.line([(X0, Y0), (X1, Y1)], fill=255, width=w)
            d.ellipse([X1 - w / 2, Y1 - w / 2, X1 + w / 2, Y1 + w / 2], fill=255)

    def write(self, d, text, x, y, size, spacing=0.92):
        cx = x
        for ch in text:
            if ch in DIGITS:
                yy = y + self.r.gauss(0, 0.03) * size
                for st in DIGITS[ch]:
                    self.stroke(d, st, cx, yy, size)
            cx += size * spacing * self.r.uniform(0.92, 1.08)
        return cx

    def line(self, d, p0, p1, wpx, wobble=6.0):
        pts = [(p0[0], p0[1]), ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2 + self.r.gauss(0, wobble)), (p1[0], p1[1])]
        self.stroke(d, pts, 0, 0, 1.0, slant=False, wpx=wpx, jitter=3.0)

    def circle(self, d, c, rad, wpx):
        a0 = self.r.uniform(0, 6.28)
        pts = []
        for k in range(15):
            a = a0 + 2 * math.pi * 1.08 * k / 14
            rr = rad * (1 + self.r.gauss(0, 0.012)) * (1 + 0.03 * k / 14)
            pts.append((c[0] + rr * math.cos(a), c[1] + rr * 0.94 * math.sin(a)))
        self.stroke(d, pts, 0, 0, 1.0, slant=False, wpx=wpx, jitter=4.0)


def chalkify(img, seed, fresh=False):
    """Grainy chalk: the stroke mask broken by wood-grain-streaked noise, soft dust halo; fresh = denser."""
    rng = np.random.default_rng(seed)
    a = np.asarray(img, np.float32) / 255.0
    streak = rng.random((N // 2, N // 16)).astype(np.float32)
    streak = np.asarray(Image.fromarray((streak * 255).astype(np.uint8)).resize((N, N), Image.BICUBIC), np.float32) / 255
    fine = rng.random((N, N)).astype(np.float32)
    grain = 0.55 * streak + 0.45 * fine
    keep = np.clip((grain - (0.30 if fresh else 0.42)) * 3.0, 0, 1)
    edge = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3)), np.float32) / 255
    dust = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(14)), np.float32) / 255
    m = a * keep * (0.75 + 0.25 * edge) + dust * (0.10 if fresh else 0.05)
    return np.clip(m * (1.15 if fresh else 0.95), 0, 1)


def save(name, arr):
    Image.fromarray((arr * 255).astype(np.uint8), "L").save(os.path.join(TEX, f"chalk_{name}.png"), optimize=True)
    print("wrote", name)


def main():
    os.makedirs(TEX, exist_ok=True)
    S = 260   # digit cell size (px) on a 2048 px head (head ~0.75 m -> 1 px ~ 0.37 mm; digits ~ 15 cm tall)
    # hero: 1934 in a loose circle
    img = Image.new("L", (N, N), 0)
    d = ImageDraw.Draw(img)
    h = Hand(1934)
    x0 = N / 2 - 2.0 * S * 0.92
    h.write(d, "1934", x0, N / 2 - 0.8 * S, S)
    h.circle(d, (N / 2 + 0.05 * S, N / 2), 2.45 * S, 0.085 * S)
    save("1934", chalkify(img, 1))
    # S07: 1934 struck through (older, fainter) + fresh 1935 beside it
    old = Image.new("L", (N, N), 0)
    d = ImageDraw.Draw(old)
    h = Hand(1933)
    h.write(d, "1934", N / 2 - 3.9 * S, N / 2 - 0.8 * S, S * 0.85)
    h.line(d, (N / 2 - 4.1 * S, N / 2 + 0.05 * S), (N / 2 - 0.5 * S, N / 2 - 0.25 * S), 0.09 * S)
    new = Image.new("L", (N, N), 0)
    d = ImageDraw.Draw(new)
    h2 = Hand(1935)
    h2.write(d, "1935", N / 2 + 0.2 * S, N / 2 - 0.95 * S, S * 0.95)
    a_old, a_new = chalkify(old, 2), chalkify(new, 3, fresh=True)
    save("1934_struck", a_old)
    save("1935_new", a_new)
    # background casks
    for i, yr in enumerate(["1931", "1932", "1933", "1935", "1936", "1934"]):
        img = Image.new("L", (N, N), 0)
        d = ImageDraw.Draw(img)
        h = Hand(100 + i, slant=0.18 if i % 2 else 0.05)
        h.write(d, yr, N / 2 - 1.9 * S * 0.9, N / 2 - 0.7 * S, S * 0.9)
        if i % 3 == 0:
            h.line(d, (N / 2 - 1.9 * S, N / 2 + 0.9 * S), (N / 2 + 1.8 * S, N / 2 + 0.85 * S), 0.045 * S)
        save(f"bg{i}", chalkify(img, 10 + i))


if __name__ == "__main__":
    main()
