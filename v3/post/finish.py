#!/usr/bin/env python3
"""Post: edit, finish and title "ONE YEAR. ONE SECOND." -> 1440 frames of 1920x1080 (2.39:1 picture letterboxed).

For every film frame: fetch the shot's picture (rendered sequence, or a high-resolution still moved in 2D, or a
composite), upscale it to 1920x804, finish it like a cinema-camera image (gentle grade, halation, bloom on practicals,
vignette, a hair of chromatic aberration, per-frame grain), letterbox it, and lay the type on top: era supers, the
title card, the tagline, subtitles in the bottom bar, the end card.  Missing shots render as labelled placeholders.

    python3 v3/post/finish.py [--range 0-1439] [--scale 0.5] [--out v3/post/frames]
    python3 v3/post/finish.py --encode        (ffmpeg: frames + audio/mix/final_mix.wav -> v3/out/*.mp4)
"""
import argparse
import json
import math
import os
import subprocess
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy.ndimage import gaussian_filter

HERE = os.path.dirname(os.path.abspath(__file__))
V3 = os.path.dirname(HERE)
FR = os.path.join(V3, "frames")
OUT = os.path.join(HERE, "frames")
W, H, PH = 1920, 1080, 804          # master, picture height
TOP = (H - PH) // 2                  # 138
FPS = 24
F_I = "/usr/share/fonts/opentype/inter/"
FONT = {
    "courier": "/usr/share/fonts/X11/Type1/c0419bt_.pfb",
    "disp_semibold": F_I + "InterDisplay-SemiBold.otf",
    "disp_light": F_I + "InterDisplay-Light.otf",
    "inter_medium": F_I + "Inter-Medium.otf",
    "mono_light": "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Light.ttf",
}
BONE = (236, 230, 218)

# shot table: name, first film frame, end (exclusive)
SHOTS = [("s01", 0, 75), ("s02", 75, 135), ("s03", 135, 180), ("s04", 180, 225), ("s05", 225, 300), ("s06", 300, 390),
         ("s07", 390, 450), ("s08", 450, 480), ("s09", 480, 555), ("s10", 555, 585), ("s11", 585, 630), ("s12", 630, 660),
         ("s13", 660, 735), ("s14", 735, 795), ("s15", 795, 870), ("s16", 870, 930), ("s17", 930, 1005),
         ("s18", 1005, 1050), ("s19", 1050, 1080), ("s20", 1080, 1140), ("s21", 1140, 1320), ("s22", 1320, 1350),
         ("s23", 1350, 1440)]


def ease(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def ease_io(u, p=2.2):
    u = min(max(u, 0.0), 1.0)
    return u ** p / (u ** p + (1 - u) ** p)


# --------------------------------------------------------------------------- sources
@lru_cache(maxsize=8)
def load(path):
    im = Image.open(path)
    a = np.asarray(im)
    if a.dtype == np.uint16:
        a = a.astype(np.float32) / 65535.0
    else:
        a = a.astype(np.float32) / 255.0
    if a.ndim == 2:
        a = np.stack([a] * 3, -1)
    return a[..., :3]


def to_picture(a):
    """Any-size RGB float -> 1920x804 (Lanczos via PIL in 16-bit)."""
    h, w = a.shape[:2]
    if (w, h) == (W, PH):
        return a
    chans = [Image.fromarray(np.clip(a[..., c] * 65535, 0, 65535).astype(np.uint16).astype(np.int32), "I").convert("F")
             for c in range(3)]
    out = [np.asarray(ch.resize((W, PH), Image.LANCZOS), np.float32) / 65535.0 for ch in chans]
    return np.clip(np.stack(out, -1), 0, 1)


def crop_move(a, cx, cy, cw):
    """Crop a window of width cw (px, aspect 1920:804) centred at (cx, cy) from still a, resampled to the picture."""
    h, w = a.shape[:2]
    ch = cw * PH / W
    if cw > w or ch > h:                   # window larger than the still: extend it with a soft mirrored border
        px, py = int(max(0, cw - w) / 2) + 2, int(max(0, ch - h) / 2) + 2
        pad = np.pad(a, ((py, py), (px, px), (0, 0)), mode="reflect")
        soft = gaussian_filter(pad, (12, 12, 0))
        inner = np.zeros(pad.shape[:2], np.float32)
        inner[py:py + h, px:px + w] = 1.0
        inner = gaussian_filter(inner, 8)[..., None]
        a, cx, cy = pad * inner + soft * (1 - inner), cx + px, cy + py
        h, w = a.shape[:2]
    x0, y0 = cx - cw / 2, cy - ch / 2
    x0 = min(max(x0, 0), w - cw)
    y0 = min(max(y0, 0), h - ch)
    img = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    box = (x0, y0, x0 + cw, y0 + ch)
    out = img.resize((W, PH), Image.LANCZOS, box=box)
    return np.asarray(out, np.float32) / 255.0


def detect_disc(a, q=0.995):
    """Centre and radius (px) of the brightest round thing: pixels above the q-quantile of luminance."""
    lum = a.mean(-1)
    thr = max(np.quantile(lum, q), 0.6)
    ys, xs = np.nonzero(lum >= thr * 0.92)
    if len(xs) < 20:
        return a.shape[1] / 2, a.shape[0] / 2, a.shape[0] * 0.1
    return float(xs.mean()), float(ys.mean()), float(math.sqrt(len(xs) / math.pi))


def seq_path(shot, local, sub=None):
    d = os.path.join(FR, shot if sub is None else f"{shot}_{sub}")
    return os.path.join(d, f"{local:04d}.png")


def placeholder(shot, local):
    img = Image.new("RGB", (W, PH), (18, 16, 14))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT["inter_medium"], 40)
    d.text((W / 2, PH / 2), f"{shot.upper()}  f{local}", font=f, fill=(90, 85, 80), anchor="mm")
    return np.asarray(img, np.float32) / 255.0


@lru_cache(maxsize=1)
@lru_cache(maxsize=2)
def soft_plate(path):
    """The end-slate wood, thrown well out of focus: a calm, dark ground for the type."""
    return gaussian_filter(load(path), (5, 5, 0)) * 0.85


def match_targets():
    """Screen positions for the circle match cuts, measured on the renders themselves."""
    t = {}
    p = seq_path("s09", 0)
    if os.path.exists(p):
        a = to_picture(load(p))
        t["porthole"] = detect_disc(a, 0.98)
    p = seq_path("s13", 0)
    if os.path.exists(p):
        a = to_picture(load(p))
        t["moon"] = detect_disc(a, 0.997)
    return t


def picture(f):
    for shot, f0, f1 in SHOTS:
        if f0 <= f < f1:
            break
    local = f - f0
    n = f1 - f0
    if shot == "s04":                      # time-lapse, rendered on twos
        local -= local % 2
    if shot == "s05":
        return still_s05(local, n)
    if shot == "s08":
        return still_push("s08", local, n, "porthole", end_frac=0.61)
    if shot == "s12":
        return still_push("s12", local, n, "moon", end_frac=None)
    if shot == "s21":
        return comp_s21(local, n)
    if shot == "s22":
        return comp_s22(local)
    if shot == "s23":
        p = os.path.join(FR, "s23", "s23_0000.png")
        if os.path.exists(p):
            a = soft_plate(p)
            u = local / n
            return crop_move(a, a.shape[1] * (0.5 + 0.02 * u), a.shape[0] * 0.5, a.shape[1] * (0.97 - 0.03 * u))
        return np.full((PH, W, 3), 0.02, np.float32)
    p = seq_path(shot, local)
    if shot in TWOS:
        q = seq_path(shot, local, "24")
        if os.path.exists(q):
            p = q
        elif not os.path.exists(p):
            p = seq_path(shot, local - local % 2)             # not interpolated yet: hold the render
    if not os.path.exists(p):
        return placeholder(shot, local)
    return to_picture(load(p))


TWOS = {"s09", "s10", "s13", "s15", "s16", "s17", "s20"}


def still_s05(local, n):
    p = os.path.join(FR, "s05", "s05_0000.png")
    if not os.path.exists(p):
        return placeholder("s05", local)
    a = load(p)
    info = json.load(open(os.path.join(V3, "lookdev", "s05_frame.json")))
    h, w = a.shape[:2]
    cov = info["cover_m"]
    ppm = w / cov[0]
    cx0, cy0 = info["centre"]

    def px(xy):
        return (xy[0] - (cx0 - cov[0] / 2)) * ppm, ((cy0 + cov[1] / 2) - xy[1]) * ppm
    start, end = px(info["card_header"]), px(info["stamp"])
    cw_end = info["stamp_diameter_m"] / 0.30 * (W / PH) * ppm      # stamp = 30 % of picture height at the end
    u = ease_io(local / (n - 6), 2.0)
    cx = start[0] + (end[0] - start[0]) * u
    cy = start[1] + (end[1] - start[1]) * u
    cw = cw_end * (1.18 - 0.18 * u)
    return crop_move(a, cx, cy, cw)


def still_push(shot, local, n, target, end_frac=None):
    p = os.path.join(FR, shot, f"{shot}_0000.png")
    if not os.path.exists(p):
        return placeholder(shot, local)
    a = load(p)
    h, w = a.shape[:2]
    dx, dy, dr = detect_disc(a, 0.99 if shot == "s08" else 0.995)
    tg = match_targets().get(target)
    if tg is None:      # fall back: centre the disc
        tx, ty, tr = W / 2, PH / 2, PH * (end_frac or 0.3) / 2
    else:
        tx, ty, tr = tg
    if end_frac:
        tr = PH * end_frac / 2
    # end window: disc radius dr (still px) must become tr (picture px), disc centre lands on (tx, ty)
    cw_end = W * dr / tr
    sc = cw_end / W
    cx_end = dx + (W / 2 - tx) * sc
    cy_end = dy + (PH / 2 - ty) * sc
    cw0 = min(w, h * W / PH)
    u = ease_io(local / (n - 1), 1.8)
    cw = cw0 * (cw_end / cw0) ** u
    cx = w / 2 + (cx_end - w / 2) * u
    cy = h / 2 + (cy_end - h / 2) * u
    return crop_move(a, cx, cy, cw)


S21_REGIONS = {"fizz": (0.25, 0.49, 0.04, 0.88), "bead": (0.56, 0.80, 0.50, 0.97)}    # as blender/shots/s21.py


def comp_s21(local, n):
    p = os.path.join(FR, "s21", "s21_still_0000.png")
    if not os.path.exists(p):
        return placeholder("s21", local)
    base = load(p).copy()
    h, w = base.shape[:2]
    for variant, f_lo, f_hi in (("fizz", 0, n), ("bead", 56, 97)):
        if not (f_lo <= local < f_hi):
            continue
        q = os.path.join(FR, f"s21_{variant}", f"{local:04d}.png")
        if not os.path.exists(q):
            q = os.path.join(FR, f"s21_{variant}", f"{local - local % 2:04d}.png")     # fizz rendered on twos
        if not os.path.exists(q):
            continue
        im = Image.open(q)
        has_alpha = im.mode in ("RGBA", "LA")
        r = np.asarray(im.convert("RGBA").resize((w, h), Image.LANCZOS), np.float32) / 255.0
        if has_alpha:
            al = r[..., 3] > 0.99
        else:                               # saved without alpha: the border rectangle itself (inset 4 px)
            x0, x1, y0, y1 = S21_REGIONS[variant]
            al = np.zeros((h, w), bool)
            al[int((1 - y1) * h) + 4:int((1 - y0) * h) - 4, int(x0 * w) + 4:int(x1 * w) - 4] = True
        al = gaussian_filter(al.astype(np.float32), 6)[..., None]                 # feather the border-render edge
        base = base * (1 - al) + r[..., :3] * al
    u = ease_io(local / (n - 1), 1.5)
    return crop_move(base, w / 2, h * (0.5 + 0.01 * u), w * (1.0 - 0.06 * u))


NEON22 = [(0, 1.0), (5, 0.15), (6, 1.0), (10, 0.0), (11, 0.8), (15, 0.0)]


def comp_s22(local):
    pa, pb = (os.path.join(FR, "s22", f"s22_{v}_0000.png") for v in ("on", "off"))
    if not (os.path.exists(pa) and os.path.exists(pb)):
        return placeholder("s22", local)
    k = 0.0
    for f, v in NEON22:
        if local >= f:
            k = v
    a = load(pa) * k + load(pb) * (1 - k)
    return to_picture(a)


# --------------------------------------------------------------------------- finishing
@lru_cache(maxsize=1)
def vignette():
    yy, xx = np.mgrid[0:PH, 0:W].astype(np.float32)
    r2 = ((xx - W / 2) / (W / 2)) ** 2 + ((yy - PH / 2) / (W / 2)) ** 2
    return (1 - 0.22 * np.clip(r2, 0, 1.6) ** 1.4)[..., None].astype(np.float32)


def finish(pic, f, rng):
    x = pic
    lum = x @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    # halation: the brightest highlights bleed a warm red into the emulsion around them
    hi = np.clip((lum - 0.72) / 0.28, 0, 1)[..., None] * x
    small = hi[::4, ::4]
    bl = np.stack([gaussian_filter(small[..., c], 6) for c in range(3)], -1)
    bl = gaussian_filter(np.repeat(np.repeat(bl, 4, 0), 4, 1)[:PH, :W], (2, 2, 0))
    x = x + bl * np.array([0.30, 0.10, 0.05], np.float32) + bl * 0.10
    # gentle filmic grade: a touch of contrast around the mid-greys, lifted blacks, warm highlights / cool shadows
    x = np.clip(x, 0, 1)
    x = x + 0.06 * (x - 0.5) * (1 - np.abs(x - 0.5) * 2)
    x = 0.012 + x * 0.988
    l2 = (x @ np.array([0.2126, 0.7152, 0.0722], np.float32))[..., None]
    x = x + (l2 - 0.5) * np.array([0.012, 0.0, -0.012], np.float32)
    x = x * vignette()
    # a hair of lateral chromatic aberration at the edges
    x[..., 0] = np.roll(x[..., 0], 1, axis=1) * 0.5 + x[..., 0] * 0.5
    x[..., 2] = np.roll(x[..., 2], -1, axis=1) * 0.5 + x[..., 2] * 0.5
    # grain: luminance-weighted, slightly coloured, fresh every frame
    g = rng.standard_normal((PH, W)).astype(np.float32)
    g = gaussian_filter(g, 0.7)
    gc = rng.standard_normal((PH // 2, W // 2, 3)).astype(np.float32).repeat(2, 0).repeat(2, 1)[:PH, :W] * 0.25
    lw = (0.25 + 0.75 * np.sin(np.clip(l2, 0, 1) * math.pi)) * 0.030
    x = x + (g[..., None] + gc) * lw
    return np.clip(x, 0, 1)


# --------------------------------------------------------------------------- type
@lru_cache(maxsize=32)
def font(key, size):
    return ImageFont.truetype(FONT[key], size)


def tracked(d, xy, text, fnt, fill, track_em=0.0, anchor="ls", center=False):
    """Draw text with tracking (in em).  center: xy is the centre of the line (baseline y)."""
    widths = [fnt.getlength(c) for c in text]
    total = sum(widths) + track_em * fnt.size * (len(text) - 1)
    x, y = xy
    if center:
        x -= total / 2
    for c, w in zip(text, widths):
        d.text((x, y), c, font=fnt, fill=fill, anchor=anchor)
        x += w + track_em * fnt.size
    return total


SUPERS = [(3.00, 5.50, "WOLFENBÜTTEL · GERMANY", "1934", None, None),
          (16.40, 18.70, "OAK CASK", "1934", "1935", 420),
          (20.40, 22.90, "NORTH ATLANTIC", "1970s", None, None),
          (24.45, 26.20, "UNITED STATES", "1980s", None, None),
          (28.10, 30.50, "LAKE TAHOE (ALLEGEDLY)", "c. 1997", None, None)]


def overlay(f, lines):
    """RGBA overlay for the 1920x1080 master (type only)."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    t = f / FPS
    pic_bottom = TOP + PH
    # era supers: typed on at 2 frames per character; the year field rolls like an odometer
    for t0, t1, label, year, year2, roll_f in SUPERS:
        if not (t0 <= t < t1):
            continue
        k = int((t - t0) * FPS)
        fade = 1.0 if t < t1 - 6 / FPS else (t1 - t) * FPS / 6
        txt = label[: k // 2]
        fnt = font("courier", 28)
        a = int(255 * 0.88 * fade)
        w = tracked(d, (96, pic_bottom - 40), txt, fnt, (*BONE, a), 0.08)
        if k // 2 >= len(label):
            # year in brackets after the label, rolling in vertically
            yx = 96 + tracked(d, (-1000, -1000), label + "  ", fnt, (0, 0, 0, 0), 0.08)
            years = [year] if year2 is None else [year, year2]
            if year2 is not None and roll_f is not None:
                u = min(max((f - (roll_f - 10)) / 10.0, 0.0), 1.0)
            else:
                u = 0.0
            base_y = pic_bottom - 40
            for i, yv in enumerate(years):
                off = (i - u) * 34
                if abs(off) > 34:
                    continue
                al = int(a * (1 - abs(off) / 34))
                tracked(d, (yx, base_y + off), f"[{yv}]", fnt, (*BONE, al), 0.08)
    # title card
    if 1140 <= f < 1200:
        fade = min(1.0, (f - 1140) / 8.0) * (1.0 if t < 49.6 else max(0.0, (50.0 - t) / 0.4))
        y = TOP + int(PH * 0.62)
        tracked(d, (W / 2, y), "THE JÄGERBOMB", font("disp_semibold", 60), (*BONE, int(255 * fade)), 0.26, center=True)
        tracked(d, (W / 2, y + 44), "* Origin disputed. Usually credited to bars around Lake Tahoe, c. 1997.",
                font("courier", 20), (*BONE, int(255 * 0.7 * fade)), 0.02, center=True)
    # tagline
    for ts, txt, row in ((50.6, "A YEAR IN OAK.", 0), (52.3, "A SECOND IN GLASS.", 1)):
        if ts <= t < 55.0:
            fade = min(1.0, (t - ts) * FPS / 10) * (1.0 if t < 54.4 else max(0.0, (55.0 - t) / 0.6))
            tr = 0.32 - 0.06 * ease((t - 50.6) / 3.0)
            y = TOP + int(PH * 0.26) + row * 62
            tracked(d, (W / 2, y), txt, font("disp_light", 44), (*BONE, int(255 * fade)), tr, center=True)
    # end card
    if f >= 1380:
        y = TOP + int(PH * 0.45)
        tracked(d, (W / 2, y), "JÄGERMEISTER", font("disp_semibold", 72), (*BONE, 255), 0.30, center=True)
        d.rectangle([W / 2 - 60, y + 30, W / 2 + 60, y + 32], fill=(232, 96, 28, 255))
        tracked(d, (W / 2, y + 70), "KRÄUTERLIKÖR · 35% VOL.", font("courier", 20), (*BONE, int(255 * 0.7)), 0.12, center=True)
        if t >= 58.1:
            fa = min(1.0, (t - 58.1) * FPS / 8)
            tracked(d, (W / 2, TOP + int(PH * 0.86)), "PLEASE ENJOY RESPONSIBLY. NEVER DRINK AND DRIVE.",
                    font("inter_medium", 26), (*BONE, int(255 * 0.8 * fa)), 0.04, center=True)
        legal = ("Unofficial spec film. Not produced, commissioned or endorsed by Mast-Jägermeister SE. "
                 "Energy drink shown is unbranded. For adults of legal drinking age only.")
        tracked(d, (W / 2, H - 52), legal, font("mono_light", 14), (242, 242, 242, int(255 * 0.55)), 0.0, center=True)
    # subtitles in the bottom bar (none for the end card's own word)
    for ln in lines:
        if ln["key"] == "10":
            continue
        a0 = ln["start"] - 2 / FPS
        a1 = ln["start"] + ln["dur"] + 6 / FPS
        if a0 <= t < a1:
            tracked(d, (W / 2, 1020), ln["text"], font("inter_medium", 32), (242, 242, 242, int(255 * 0.92)), 0.0, center=True)
    return ov


def frame(f, lines, scale=1.0):
    rng = np.random.default_rng(f * 7919 + 13)
    pic = finish(picture(f), f, rng)
    if f >= 1432:                                    # the last 8 frames fade to black
        pic = pic * (1440 - f) / 8.0
    if f < 2:
        pic = pic * 0.0                              # black, then the first hit
    master = np.zeros((H, W, 3), np.float32)
    master[TOP:TOP + PH] = pic
    img = Image.fromarray((master * 255 + 0.5).astype(np.uint8))
    img = Image.alpha_composite(img.convert("RGBA"), overlay(f, lines)).convert("RGB")
    if scale != 1.0:
        img = img.resize((int(W * scale), int(H * scale)), Image.LANCZOS)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--range", default="0-1439")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--encode", action="store_true")
    ap.add_argument("--name", default="one-year-one-second")
    a = ap.parse_args()
    if a.encode:
        encode(a.out, a.name)
        return
    os.makedirs(a.out, exist_ok=True)
    lines = json.load(open(os.path.join(V3, "audio", "vo", "lines.json")))["lines"]
    f0, f1 = (int(v) for v in a.range.split("-"))
    for f in range(f0, f1 + 1):
        frame(f, lines, a.scale).save(os.path.join(a.out, f"{f:04d}.jpg"), quality=95, subsampling=0)
        if f % 48 == 0:
            print("[post]", f, flush=True)


def encode(src, name):
    out = os.path.join(V3, "out")
    os.makedirs(out, exist_ok=True)
    audio = os.path.join(V3, "audio", "mix", "final_mix.wav")
    base = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(src, "%04d.jpg"), "-i", audio]
    subprocess.run(base + ["-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", "-profile:v", "high",
                           "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", "-shortest",
                           os.path.join(out, f"{name}.mp4")], check=True)
    subprocess.run(base + ["-c:v", "libx265", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-tag:v", "hvc1",
                           "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", "-shortest",
                           os.path.join(out, f"{name}-hevc.mp4")], check=True)
    # a lighter 1080p copy for phones and messaging
    subprocess.run(base + ["-c:v", "libx264", "-preset", "slow", "-crf", "22", "-maxrate", "6M", "-bufsize", "12M",
                           "-pix_fmt", "yuv420p", "-profile:v", "high", "-c:a", "aac", "-b:a", "192k",
                           "-movflags", "+faststart", "-shortest", os.path.join(out, f"{name}-share.mp4")], check=True)
    # sidecar subtitles (the burned-in ones, as SRT) and a poster frame from the hero shot
    lines = json.load(open(os.path.join(V3, "audio", "vo", "lines.json")))["lines"]

    def ts(t):
        ms = int(round(t * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    with open(os.path.join(out, f"{name}.en.srt"), "w") as fh:
        for i, ln in enumerate(lines, 1):
            fh.write(f"{i}\n{ts(ln['start'] - 2 / FPS)} --> {ts(ln['start'] + ln['dur'] + 6 / FPS)}\n{ln['text']}\n\n")
    Image.open(os.path.join(src, "1290.jpg")).save(os.path.join(out, "poster.jpg"), quality=92)
    print("[encode] done", out)


if __name__ == "__main__":
    main()
