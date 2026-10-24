#!/usr/bin/env python3
"""Recipe card artwork (A5 landscape index card, 210 x 148 mm), typed in Courier 10 Pitch.

One RGBA map per typing state, all non-colour data:
    R  black ribbon ink coverage (ribbon weave, per-strike density, slug unevenness, slight bleed)
    G  impression height (1 = untouched paper, lower = where a slug or the stamp pressed in)
    B  fresh ink (the last strikes: a hair blacker and glossier)
    A  red stamp ink (GEHEIM)
Writes textures/card_<state>.png.  States:
    head_4     the typed header only (S01 masks the last four digits until they are struck); no list, no stamp
    full       complete card with the overtyped list and the GEHEIM stamp (S05)
The layout (mm, from the card's top-left corner) is in card_layout.json so the Blender side can place the
typing point and the stamp.
    python3 v3/blender/art/card.py
"""
import json, math, os, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(os.path.dirname(HERE), "textures")
COURIER = "/usr/share/fonts/X11/Type1/c0419bt_.pfb"
LIBERATION_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
LIBERATION = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

PX = 24                      # px per mm
W_MM, H_MM = 210.0, 148.0
W, H = int(W_MM * PX), int(H_MM * PX)
PITCH = 2.54                 # 10 characters per inch
LINE = 4.233                 # single spacing, 6 lines per inch
EM = PITCH / 0.602           # Courier 10 Pitch advance is 0.602 em
LEFT = 16.0                  # left margin (mm)
TOP = 18.0                   # first baseline (mm from top)

HEADER = "KRÄUTERLIKÖR - REZEPTUR - C. MAST - WOLFENBÜTTEL 1934"
PREFIX = HEADER[:-4]          # S01 starts with '... WOLFENBÜTTEL ' typed; '1', '9', '3', '4' are struck on camera
# list: (number, ingredient word to be overtyped, quantity) -- the words are typed, then overtyped with X
ITEMS = [("Enzianwurzel", "4,0"), ("Sternanis", "2,5"), ("Zimtrinde", "3,2"), ("Kardamom", "1,8"),
         ("Wacholderbeeren", "6,0"), ("Safran", "0,2"), ("Kamillenblüten", "2,0"), ("Pomeranzenschale", "5,5"),
         ("Süßholzwurzel", "3,0"), ("Ingwer", "1,5"), ("Mohnsamen", "0,8"), ("Nelken", "0,6")]
STAMP_C = (152.0, 98.0)      # stamp centre (mm)
STAMP_R = 21.0               # outer radius (mm)


def mm(v):
    return int(round(v * PX))


def weave(rng):
    """Cloth-ribbon texture inside a strike: crossed threads at ~0.25 mm, dense but broken."""
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    f = 2 * math.pi / (0.26 * PX)
    a = 0.5 + 0.5 * np.sin(f * (x * 0.94 + y * 0.34) + rng.uniform(0, 6))
    b = 0.5 + 0.5 * np.sin(f * (x * -0.30 + y * 0.95) + rng.uniform(0, 6))
    w = 0.78 + 0.22 * np.minimum(a, b) ** 0.6
    return w.astype(np.float32)


def blurred_noise(rng, sigma_px, shape=(H, W)):
    small = (max(4, int(shape[0] / sigma_px)), max(4, int(shape[1] / sigma_px)))
    n = rng.random(small).astype(np.float32)
    im = Image.fromarray((n * 255).astype(np.uint8)).resize((shape[1], shape[0]), Image.BICUBIC)
    return np.asarray(im, np.float32) / 255.0


class Typist:
    """Strikes glyphs one by one into float layers (ink, solid glyph area for the impression, fresh)."""

    def __init__(self, seed=1934):
        self.rng = random.Random(seed)
        self.font = ImageFont.truetype(COURIER, mm(EM))
        self.strikes = []        # (char, x_mm, baseline_mm, density, dx, dy, rot, top_bias)

    def type(self, text, col, row, overtype=False):
        x0 = LEFT + col * PITCH
        y = TOP + row * LINE
        for i, ch in enumerate(text):
            if ch == " ":
                continue
            r = self.rng
            self.strikes.append(dict(ch=ch, x=x0 + i * PITCH, y=y, d=r.uniform(0.72, 1.0) * (0.92 if overtype else 1.0),
                                     dx=r.gauss(0, 0.05), dy=r.gauss(0, 0.06) + (0.04 if ch.isupper() else 0),
                                     rot=r.gauss(0, 0.5), bias=r.uniform(-0.35, 0.35), heavy=ch in "MW@#%&"))
        return len(self.strikes)

    def render(self, n_strikes, fresh_from, seed=7):
        """Ink and impression of the first n_strikes; strikes >= fresh_from are 'fresh'."""
        rng = np.random.default_rng(seed)
        ink = np.zeros((H, W), np.float32)
        solid = np.zeros((H, W), np.float32)
        fresh = np.zeros((H, W), np.float32)
        tile = mm(5.0)
        for k, s in enumerate(self.strikes[:n_strikes]):
            g = Image.new("L", (tile * 2, tile * 2), 0)
            d = ImageDraw.Draw(g)
            d.text((tile * 2 // 2, tile * 2 // 2), s["ch"], font=self.font, fill=255, anchor="ls")
            g = g.rotate(s["rot"], resample=Image.BICUBIC, center=(tile, tile))
            a = np.asarray(g, np.float32) / 255.0
            # the slug hits a little harder on one side (top/bottom), heavy glyphs fill in
            yy = np.linspace(-1, 1, a.shape[0])[:, None]
            a = a * np.clip(1.0 + s["bias"] * yy * 0.8, 0.45, 1.25)
            cx = mm(s["x"] + s["dx"]); cy = mm(s["y"] + s["dy"])
            y0, x0 = cy - tile, cx - tile
            sl = (slice(max(y0, 0), min(y0 + 2 * tile, H)), slice(max(x0, 0), min(x0 + 2 * tile, W)))
            a = a[sl[0].start - y0: sl[0].stop - y0, sl[1].start - x0: sl[1].stop - x0]
            ink[sl] = np.maximum(ink[sl], np.clip(a, 0, 1) * s["d"])
            solid[sl] = np.maximum(solid[sl], (a > 0.25).astype(np.float32))
            if k >= fresh_from:
                fresh[sl] = np.maximum(fresh[sl], np.clip(a, 0, 1))
        # slugs print a little bolder than the font outline (ink squeeze), then ribbon weave, wear and spread
        ink = np.asarray(Image.fromarray((ink * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)), np.float32) / 255.0
        ink = 1.0 - (1.0 - ink) ** 2.2
        ink *= weave(np.random.default_rng(seed))
        ink *= 0.82 + 0.18 * blurred_noise(rng, mm(1.2))
        spread = np.asarray(Image.fromarray((ink * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.9)),
                            np.float32) / 255.0
        ink = np.clip(np.maximum(ink, spread * 0.55), 0, 1)
        # the impression: a soft deboss under every slug (~0.05 mm deep, rounded edges)
        imp = np.asarray(Image.fromarray((solid * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.6)),
                         np.float32) / 255.0
        fresh = np.asarray(Image.fromarray((fresh * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6)),
                           np.float32) / 255.0
        return ink, imp, fresh


def stamp(seed=3):
    """Round red rubber stamp GEHEIM: double ring, ring text, centre word on a bar; ink breakup and edge pooling."""
    rng = np.random.default_rng(seed)
    size = mm(STAMP_R * 2 + 4)
    im = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(im)
    c = size / 2
    R = mm(STAMP_R)
    d.ellipse([c - R, c - R, c + R, c + R], outline=255, width=mm(1.3))
    r2 = R - mm(6.2)
    d.ellipse([c - r2, c - r2, c + r2, c + r2], outline=255, width=mm(0.6))
    # ring text, upper and lower arcs
    f_ring = ImageFont.truetype(LIBERATION_BOLD, mm(3.4))

    def arc_text(text, radius, center_deg, upper=True):
        widths = [f_ring.getlength(ch) for ch in text]
        total = sum(widths) * 1.12
        ang = math.radians(center_deg) + (total / 2) / radius * (1 if upper else -1)
        for ch, w in zip(text, widths):
            step = w * 1.12 / radius
            a = ang - step / 2 * (1 if upper else -1)
            g = Image.new("L", (mm(6), mm(6)), 0)
            ImageDraw.Draw(g).text((mm(3), mm(3)), ch, font=f_ring, fill=255, anchor="mm")
            rot = math.degrees(a) - 90 if upper else math.degrees(a) + 90
            g = g.rotate(rot, resample=Image.BICUBIC)
            px = c + radius * math.cos(a); py = c - radius * math.sin(a)
            im.paste(255, (int(px - mm(3)), int(py - mm(3))), g)
            ang -= step * (1 if upper else -1)

    rt = (R + r2) / 2
    arc_text("C. MAST  ·  WOLFENBÜTTEL", rt, 90, True)
    arc_text("· KRÄUTERLIKÖR ·", rt, 270, False)
    # centre bar + word
    f_big = ImageFont.truetype(LIBERATION_BOLD, mm(7.4))
    bw, bh = r2 * 2 - mm(1.5), mm(9.4)
    d.rectangle([c - bw / 2, c - bh / 2 - mm(0.7), c + bw / 2, c - bh / 2], fill=255)
    d.rectangle([c - bw / 2, c + bh / 2, c + bw / 2, c + bh / 2 + mm(0.7)], fill=255)
    d.text((c, c + mm(0.2)), "GEHEIM", font=f_big, fill=255, anchor="mm")
    a = np.asarray(im.rotate(-8.0, resample=Image.BICUBIC), np.float32) / 255.0
    # rubber stamp physics: uneven pressure (one side lighter), breakup, ink pooling at edges
    yy, xx = np.mgrid[0:size, 0:size] / size - 0.5
    press = np.clip(0.95 - 0.55 * (xx * 0.7 + yy * 0.5), 0.35, 1.0)
    brk = np.asarray(Image.fromarray((rng.random((size // 6, size // 6)) * 255).astype(np.uint8))
                     .resize((size, size), Image.BICUBIC), np.float32) / 255.0
    fine = rng.random((size, size)).astype(np.float32)
    keep = np.clip((brk * 0.7 + fine * 0.3 - (1 - press) * 0.9 - 0.12) * 4, 0, 1)
    blur = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(mm(0.25))),
                      np.float32) / 255.0
    edge = np.clip((a - blur) * 3 + 0.0, 0, 1)                       # ink pools along stroke edges
    ink = np.clip(a * (0.55 + 0.45 * keep) + edge * 0.35, 0, 1) * press
    ink = np.asarray(Image.fromarray((ink * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8)), np.float32) / 255
    return ink


def save(name, ink, imp, fresh, red=None):
    paper_h = 1.0 - 0.75 * imp
    if red is None:
        red = np.zeros_like(ink)
    rgba = np.stack([ink, paper_h, fresh, red], -1)
    Image.fromarray((np.clip(rgba, 0, 1) * 255).astype(np.uint8), "RGBA").save(os.path.join(TEX, f"card_{name}.png"),
                                                                               optimize=True)
    print("wrote", name, flush=True)


def main():
    os.makedirs(TEX, exist_ok=True)
    t = Typist()
    n_head = t.type(HEADER, 0, 0)
    n_prefix = len([c for c in PREFIX if c != " "])
    # S01: the complete header; the shot masks out the digits not yet struck (see shots/s01.py)
    ink, imp, fresh = t.render(n_head, fresh_from=n_head - 1)
    save(f"head_{n_head - n_prefix}", ink, imp, fresh)
    # full card: underline, numbered list, overtyped words and quantities, stamp
    t.type("=" * 53, 0, 1)
    for i, (word, qty) in enumerate(ITEMS):
        row = 3 + i
        t.type(f"{i + 1:2d}.", 0, row)
        t.type(word, 5, row)
        t.type("X" * (len(word) + 1), 5, row, overtype=True)
        t.type(qty + " g", 26, row)
        t.type("XXXXXX", 26, row, overtype=True)
    n_all = len(t.strikes)
    ink, imp, fresh = t.render(n_all, fresh_from=n_all)
    red = np.zeros((H, W), np.float32)
    st = stamp()
    cx, cy = mm(STAMP_C[0]), mm(STAMP_C[1])
    s = st.shape[0]
    red[cy - s // 2: cy - s // 2 + s, cx - s // 2: cx - s // 2 + s] = st
    imp = np.maximum(imp, (red > 0.2) * 0.25)
    save("full", ink, imp, fresh, red)
    layout = dict(px_per_mm=PX, size_mm=[W_MM, H_MM], pitch=PITCH, line=LINE, left=LEFT, top=TOP, header=HEADER,
                  prefix_chars=len(PREFIX), strike_x_mm=[LEFT + i * PITCH for i in range(len(PREFIX), len(HEADER))],
                  stamp_center_mm=list(STAMP_C), stamp_radius_mm=STAMP_R)
    json.dump(layout, open(os.path.join(TEX, "card_layout.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
