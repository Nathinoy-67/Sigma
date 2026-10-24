#!/usr/bin/env python3
"""Crate stencils (Liberation Sans Bold cut into stencil letters: bridges through every counter and bowl), sprayed:
soft overspray halo, paint starvation where the stencil lifted, and fine speckle.  L images, 1 = paint.

    textures/stencil_made.png        MADE IN WEST GERMANY
    textures/stencil_fragile.png     ZERBRECHLICH · FRAGILE  + a wine-glass symbol
    textures/stencil_consignee.png   CONSIGNEE: / SIDNEY FRANK IMPORTING CO. · NEW YORK
    textures/stencil_kraeuter.png    KRÄUTERLIKÖR  12 x 0,7 L
    python3 v3/blender/art/stencils.py
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(os.path.dirname(HERE), "textures")
BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
COND = "/usr/share/fonts/truetype/liberation/LiberationSansNarrow-Bold.ttf"


def stencil_text(lines, size, W, H, font=BOLD, track=0.12, glass=False):
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(font if os.path.exists(font) else BOLD, size)
    total_h = len(lines) * size * 1.25
    y = (H - total_h) / 2 + size * 0.1
    for line, scale in lines:
        fl = ImageFont.truetype(font if os.path.exists(font) else BOLD, int(size * scale))
        widths = [fl.getlength(c) for c in line]
        tw = sum(widths) + track * size * scale * (len(line) - 1)
        x = (W - tw) / 2
        for c, w in zip(line, widths):
            d.text((x, y), c, font=fl, fill=255)
            # stencil bridges: a vertical gap through the middle of letters with counters
            if c in "ABDOPQRØ0689G":
                bx = x + w * 0.5
                d.rectangle([bx - size * scale * 0.035, y + size * scale * 0.05, bx + size * scale * 0.035,
                             y + size * scale * 0.95], fill=0)
            x += w + track * size * scale
        y += size * scale * 1.25
    if glass:   # wine glass: bowl, stem, foot (with a stencil bridge)
        cx, cy, s = W * 0.045, H * 0.5, size * 1.1
        d.chord([cx - s * 0.35, cy - s * 0.9, cx + s * 0.35, cy - s * 0.1], 0, 180, fill=255)
        d.rectangle([cx - s * 0.35, cy - s * 0.9, cx + s * 0.35, cy - s * 0.5], fill=255)
        d.rectangle([cx - s * 0.04, cy - s * 0.12, cx + s * 0.04, cy + s * 0.55], fill=255)
        d.rectangle([cx - s * 0.25, cy + s * 0.52, cx + s * 0.25, cy + s * 0.62], fill=255)
        d.rectangle([cx - s * 0.4, cy - s * 0.82, cx + s * 0.4, cy - s * 0.76], fill=0)
    return img


def spray(img, seed):
    rng = np.random.default_rng(seed)
    a = np.asarray(img, np.float32) / 255
    halo = np.asarray(img.filter(ImageFilter.GaussianBlur(6)), np.float32) / 255
    soft = np.asarray(img.filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255
    h, w = a.shape
    lift = np.asarray(Image.fromarray((rng.random((h // 40, w // 40)) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC),
                      np.float32) / 255
    speck = rng.random((h, w)).astype(np.float32)
    paint = soft * np.clip(0.55 + 0.7 * lift, 0, 1) * (0.85 + 0.15 * speck)
    over = halo * 0.22 * (speck > 0.55)
    return np.clip(np.maximum(paint, over), 0, 1)


def save(name, arr):
    Image.fromarray((arr * 255).astype(np.uint8), "L").save(os.path.join(TEX, f"stencil_{name}.png"), optimize=True)
    print("wrote", name)


def main():
    os.makedirs(TEX, exist_ok=True)
    W, H = 2400, 600
    save("made", spray(stencil_text([("MADE IN WEST GERMANY", 1.0)], 150, W, H), 1))
    save("fragile", spray(stencil_text([("   ZERBRECHLICH · FRAGILE", 1.0)], 125, W, H, glass=True), 2))
    save("consignee", spray(stencil_text([("CONSIGNEE:", 0.7), ("SIDNEY FRANK IMPORTING CO. · NEW YORK", 0.78)], 120, W, H,
                                          font=COND, track=0.08), 3))
    save("kraeuter", spray(stencil_text([("KRÄUTERLIKÖR   12 × 0,7 L", 1.0)], 120, W, H), 4))


if __name__ == "__main__":
    main()
