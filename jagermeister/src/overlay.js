import * as THREE from 'three';
import { CUE } from './timeline.js';
import { clamp, lerp, remap, ease, rng, smooth } from './gl.js';

// Typography + line-art layer. Two Canvas2D surfaces are uploaded as textures:
//   text — composited "over" the scene (crisp titles)
//   glow — added as light (line art, glints) so the bloom pass picks it up.

const GOLD = [236, 186, 108];
const CREAM = [239, 227, 200];
const ORANGE = [255, 106, 19];
const ICE = [226, 242, 248];
const rgba = (c, a = 1) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;

// --- the stag: a faceted, constellation-like head with procedural antlers ---------
export function catmull(points, samples) {
  const out = [];
  const n = points.length;
  for (let i = 0; i < n - 1; i++) {
    const p0 = points[Math.max(0, i - 1)], p1 = points[i], p2 = points[i + 1], p3 = points[Math.min(n - 1, i + 2)];
    for (let k = 0; k < samples; k++) {
      const t = k / samples, t2 = t * t, t3 = t2 * t;
      out.push([0, 1].map((j) =>
        0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2 + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3)));
    }
  }
  out.push(points[n - 1].slice());
  return out;
}

export function buildStag() {
  const R = {
    A: [0, -150], B: [38, -146], C: [66, -128], D: [182, -160], E: [142, -104], F: [82, -86],
    G: [94, -44], H: [60, -50], I: [80, 22], J: [50, 112], K: [42, 150], L: [28, 178], M: [0, 188],
    N: [0, -88], O: [0, -16], P: [0, 62], Q: [0, 138], Rr: [44, -6], S: [30, 80],
  };
  const pts = {};
  for (const [k, v] of Object.entries(R)) {
    pts[k] = v;
    if (v[0] !== 0) pts[k + "'"] = [-v[0], v[1]];
  }
  const triR = [
    ['A', 'B', 'N'], ['B', 'C', 'N'], ['C', 'F', 'N'], ['C', 'D', 'E'], ['C', 'E', 'F'], ['N', 'F', 'Rr'], ['F', 'G', 'Rr'],
    ['N', 'Rr', 'O'], ['G', 'I', 'Rr'], ['Rr', 'I', 'S'], ['O', 'Rr', 'P'], ['Rr', 'S', 'P'], ['I', 'J', 'S'], ['S', 'J', 'Q'],
    ['P', 'S', 'Q'], ['J', 'K', 'Q'], ['Q', 'K', 'M'], ['K', 'L', 'M'],
  ];
  const mir = (k) => (R[k][0] === 0 ? k : k + "'");
  const tris = [...triR, ...triR.map((t) => t.map(mir))];
  const edgeSet = new Map();
  for (const t of tris)
    for (let i = 0; i < 3; i++) {
      const a = t[i], b = t[(i + 1) % 3];
      const key = [a, b].sort().join('|');
      if (!edgeSet.has(key)) edgeSet.set(key, [a, b]);
    }
  const rand = rng(56);
  const edges = [...edgeSet.values()].map(([a, b]) => {
    const pa = pts[a], pb = pts[b];
    const midY = (pa[1] + pb[1]) / 2;
    // draw from the nose upward, outer facets slightly later
    const order = clamp((188 - midY) / 340) * 0.8 + (Math.abs(pa[0] + pb[0]) / 2 / 180) * 0.2 + rand() * 0.08;
    // start at the lower vertex
    return pa[1] > pb[1] ? { a: pa, b: pb, order } : { a: pb, b: pa, order };
  });
  const verts = Object.entries(pts).map(([k, p]) => ({ p, order: clamp((188 - p[1]) / 340) * 0.85 + rand() * 0.15, tw: rand() }));
  const facets = tris.map((t) => {
    const P = t.map((k) => pts[k]);
    const cx = (P[0][0] + P[1][0] + P[2][0]) / 3, cy = (P[0][1] + P[1][1] + P[2][1]) / 3;
    const shade = clamp(0.55 - cx / 420 - cy / 900 + (rand() - 0.5) * 0.35, 0.08, 1);
    return { P, shade, order: clamp((188 - cy) / 340) };
  });

  // antlers (right side; mirrored on draw)
  const beamPts = [[38, -146], [72, -190], [120, -236], [172, -288], [207, -354], [221, -432], [210, -508], [186, -572], [166, -628]];
  const beam = catmull(beamPts, 14);
  const tineDefs = [
    { pts: [[68, -185], [44, -214], [27, -252], [22, -290]], w: 6.5 },
    { pts: [[116, -232], [92, -262], [82, -300], [84, -338]], w: 6 },
    { pts: [[205, -346], [172, -376], [152, -412], [146, -450]], w: 5.5 },
    { pts: [[220, -458], [248, -494], [266, -540], [272, -588]], w: 5 },
    { pts: [[208, -512], [224, -552], [230, -596], [226, -642]], w: 4.5 },
  ];
  const tines = tineDefs.map((d) => {
    const s0 = d.pts[0];
    let best = 0, bd = 1e9;
    beam.forEach((p, i) => {
      const dd = (p[0] - s0[0]) ** 2 + (p[1] - s0[1]) ** 2;
      if (dd < bd) { bd = dd; best = i; }
    });
    const pts2 = [beam[best], ...d.pts.slice(1)];
    return { pts: catmull(pts2, 12), w0: d.w, w1: 1.3, anchor: best / (beam.length - 1) };
  });
  return { pts, edges, verts, facets, beam, tines, eye: R.H, star: [0, -404] };
}

export function taper(ctx, pts, w0, w1, prog, mirror) {
  const n = pts.length;
  const m = prog * (n - 1);
  if (m <= 0.01) return null;
  const k = Math.floor(m), f = m - k;
  const P = pts.slice(0, k + 1);
  if (k < n - 1) P.push([lerp(pts[k][0], pts[k + 1][0], f), lerp(pts[k][1], pts[k + 1][1], f)]);
  const L = [], Rt = [];
  for (let i = 0; i < P.length; i++) {
    const a = P[Math.max(0, i - 1)], b = P[Math.min(P.length - 1, i + 1)];
    const dx = b[0] - a[0], dy = b[1] - a[1];
    const l = Math.hypot(dx, dy) || 1;
    const nx = -dy / l, ny = dx / l;
    const s = Math.min(1, i / (n - 1));
    const w = lerp(w0, w1, Math.pow(s, 0.8)) / 2;
    L.push([P[i][0] + nx * w, P[i][1] + ny * w]);
    Rt.push([P[i][0] - nx * w, P[i][1] - ny * w]);
  }
  const sx = mirror ? -1 : 1;
  ctx.beginPath();
  ctx.moveTo(L[0][0] * sx, L[0][1]);
  for (const p of L) ctx.lineTo(p[0] * sx, p[1]);
  for (let i = Rt.length - 1; i >= 0; i--) ctx.lineTo(Rt[i][0] * sx, Rt[i][1]);
  ctx.closePath();
  ctx.fill();
  const tip = P[P.length - 1];
  return [tip[0] * sx, tip[1]];
}

// Soft-focus text without ctx.filter (which is very slow on a software canvas): draw the
// glyphs far off-canvas and let their blurred shadow land in place.
function blurText(ctx, str, x, y, blurPx) {
  if (blurPx < 0.15) {
    ctx.fillText(str, x, y);
    return;
  }
  const sc = ctx.shadowColor, sb = ctx.shadowBlur, sx = ctx.shadowOffsetX;
  ctx.shadowColor = typeof ctx.fillStyle === 'string' ? ctx.fillStyle : 'rgb(236,224,196)';
  ctx.shadowBlur = blurPx * 2;
  ctx.shadowOffsetX = 20000;
  ctx.fillText(str, x - 20000, y);
  ctx.shadowColor = sc;
  ctx.shadowBlur = sb;
  ctx.shadowOffsetX = sx;
}

export class Overlay {
  constructor(W, H) {
    this.W = W;
    this.H = H;
    this.S = H / 1080;
    const mk = () => {
      const c = document.createElement('canvas');
      c.width = W;
      c.height = H;
      return c;
    };
    this.tc = mk();
    this.gc = mk();
    this.t = this.tc.getContext('2d');
    this.g = this.gc.getContext('2d');
    const tex = (c) => {
      const tx = new THREE.CanvasTexture(c);
      tx.premultiplyAlpha = true;
      tx.generateMipmaps = false;
      tx.minFilter = THREE.LinearFilter;
      tx.magFilter = THREE.LinearFilter;
      tx.colorSpace = THREE.NoColorSpace;
      return tx;
    };
    this.textTex = tex(this.tc);
    this.glowTex = tex(this.gc);
    this.usedText = this.usedGlow = false;
    this.dirtyText = this.dirtyGlow = true;
    this.stag = buildStag();
  }

  begin() {
    if (this.dirtyText) this.t.clearRect(0, 0, this.W, this.H);
    if (this.dirtyGlow) this.g.clearRect(0, 0, this.W, this.H);
    this.usedText = this.usedGlow = false;
  }
  upload() {
    if (this.usedText) this.textTex.needsUpdate = true;
    if (this.usedGlow) this.glowTex.needsUpdate = true;
    this.dirtyText = this.usedText;
    this.dirtyGlow = this.usedGlow;
  }
  ctx(glow) {
    if (glow) this.usedGlow = true;
    else this.usedText = true;
    return glow ? this.g : this.t;
  }

  // Generic text: x,y in 1080p design pixels. perChar(i, n) → {a, dx, dy, blur}
  text(str, o) {
    const S = this.S;
    const ctx = this.ctx(o.glow);
    ctx.save();
    ctx.font = `${o.style || 'normal'} ${o.weight || 400} ${o.size * S}px ${o.family}`;
    const ls = (o.tracking || 0) * o.size * S;
    ctx.letterSpacing = `${ls}px`;
    ctx.textBaseline = o.baseline || 'alphabetic';
    ctx.fillStyle = o.fill || rgba(o.color || CREAM, 1);
    const total = ctx.measureText(str).width - ls;
    let x0 = o.x * S;
    if ((o.align || 'center') === 'center') x0 -= total / 2;
    else if (o.align === 'right') x0 -= total;
    const y = o.y * S;
    const alpha = o.alpha ?? 1;
    if (o.shadow) {
      ctx.shadowColor = o.shadow;
      ctx.shadowBlur = (o.shadowBlur || 20) * S;
    }
    if (!o.perChar) {
      ctx.globalAlpha = clamp(alpha);
      blurText(ctx, str, x0, y, (o.blur || 0) * S);
    } else {
      const n = str.length;
      for (let i = 0; i < n; i++) {
        const ch = str[i];
        if (ch === ' ') continue;
        const c = o.perChar(i, n);
        if (c.a <= 0.002) continue;
        const xi = ctx.measureText(str.slice(0, i)).width;
        ctx.globalAlpha = clamp(c.a * alpha);
        blurText(ctx, ch, x0 + xi + (c.dx || 0) * S, y + (c.dy || 0) * S, (c.blur || 0) * S);
      }
    }
    ctx.restore();
    return { x: x0 / S, w: total / S };
  }

  line(x0, y0, x1, y1, o) {
    const S = this.S;
    const ctx = this.ctx(o.glow);
    ctx.save();
    ctx.strokeStyle = rgba(o.color || GOLD, o.alpha ?? 1);
    ctx.lineWidth = (o.width || 1) * S;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(x0 * S, y0 * S);
    ctx.lineTo(x1 * S, y1 * S);
    ctx.stroke();
    ctx.restore();
  }

  dot(x, y, r, color, alpha, glow = true) {
    const S = this.S;
    const ctx = this.ctx(glow);
    ctx.save();
    ctx.globalAlpha = clamp(alpha);
    ctx.fillStyle = rgba(color);
    ctx.beginPath();
    ctx.arc(x * S, y * S, Math.max(0.3, r) * S, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  // ---------------------------------------------------------------------------
  // The stag constellation. u: 0..1 build progress (with sub-phases), cx/cy/scale in design px
  stagFigure(u, cx, cy, scale, o = {}) {
    const S = this.S;
    const g = this.ctx(true);
    const st = this.stag;
    const bright = o.bright ?? 1;
    const time = o.time ?? 0;
    g.save();
    g.translate(cx * S, cy * S);
    g.scale(scale * S, scale * S);
    g.lineJoin = 'round';
    g.lineCap = 'round';

    // facets
    const fu = remap(u, 0.45, 0.85);
    if (fu > 0) {
      for (const f of st.facets) {
        const a = smooth(remap(fu, f.order * 0.6, f.order * 0.6 + 0.4)) * f.shade * 0.16 * bright;
        if (a <= 0.003) continue;
        g.fillStyle = rgba(GOLD, a);
        g.beginPath();
        g.moveTo(f.P[0][0], f.P[0][1]);
        g.lineTo(f.P[1][0], f.P[1][1]);
        g.lineTo(f.P[2][0], f.P[2][1]);
        g.closePath();
        g.fill();
      }
    }
    // edges
    const eu = remap(u, 0.12, 0.62);
    g.lineWidth = 1.5 / scale;
    for (const e of st.edges) {
      const p = ease.outCubic(remap(eu, e.order * 0.7, e.order * 0.7 + 0.3));
      if (p <= 0) continue;
      g.strokeStyle = rgba(GOLD, 0.85 * bright);
      g.beginPath();
      g.moveTo(e.a[0], e.a[1]);
      g.lineTo(lerp(e.a[0], e.b[0], p), lerp(e.a[1], e.b[1], p));
      g.stroke();
    }
    // vertices — twinkle in like stars
    const vu = remap(u, 0.0, 0.4);
    for (const v of st.verts) {
      const a = remap(vu, v.order * 0.75, v.order * 0.75 + 0.25);
      if (a <= 0) continue;
      const pop = Math.exp(-Math.pow((a - 0.15) * 4.0, 2)) * 2.2;
      const tw = 0.75 + 0.25 * Math.sin(time * (3 + v.tw * 5) + v.tw * 30);
      const r = (2.1 + pop * 2.4) / scale;
      g.fillStyle = rgba([255, 232, 190], clamp(a * 3) * tw * bright);
      g.beginPath();
      g.arc(v.p[0], v.p[1], r, 0, Math.PI * 2);
      g.fill();
    }
    // antlers
    const au = remap(u, 0.25, 0.92);
    const beamP = ease.inOutCubic(remap(au, 0, 0.8));
    const tips = [];
    for (const mirror of [false, true]) {
      g.fillStyle = rgba([226, 160, 82], 0.95 * bright);
      const tip = taper(g, st.beam, 11, 2.6, beamP, mirror);
      if (tip && beamP < 0.999) tips.push(tip);
      for (const tn of st.tines) {
        const tp = ease.outCubic(remap(beamP, tn.anchor, Math.min(1, tn.anchor + 0.32)));
        const tp2 = Math.min(tp, remap(au, 0, 1) * 1.5);
        const tt = taper(g, tn.pts, tn.w0, tn.w1, tp2, mirror);
        if (tt && tp2 < 0.999) tips.push(tt);
      }
      // bright filament core
      g.fillStyle = rgba([255, 230, 180], 0.9 * bright);
      taper(g, st.beam, 3.2, 0.8, beamP, mirror);
      for (const tn of st.tines) {
        const tp = ease.outCubic(remap(beamP, tn.anchor, Math.min(1, tn.anchor + 0.32)));
        taper(g, tn.pts, 1.8, 0.5, Math.min(tp, remap(au, 0, 1) * 1.5), mirror);
      }
    }
    // sparks at the growing tips
    for (const tp of tips) {
      g.fillStyle = rgba([255, 240, 210], 1 * bright);
      g.beginPath();
      g.arc(tp[0], tp[1], 3.4 / scale + 2, 0, Math.PI * 2);
      g.fill();
    }
    // the Hubertus star between the antlers (end card emblem)
    if (o.star > 0) {
      const [sx, sy] = st.star;
      const k = o.star;
      const tw = 0.85 + 0.15 * Math.sin(time * 6.0);
      const rg = g.createRadialGradient(sx, sy, 0, sx, sy, 60);
      rg.addColorStop(0, rgba([255, 240, 210], 0.9 * k * tw));
      rg.addColorStop(0.25, rgba([255, 190, 110], 0.35 * k * tw));
      rg.addColorStop(1, rgba([255, 160, 80], 0));
      g.fillStyle = rg;
      g.beginPath();
      g.arc(sx, sy, 60, 0, Math.PI * 2);
      g.fill();
      g.fillStyle = rgba([255, 236, 200], k);
      g.beginPath();
      for (let i = 0; i < 8; i++) {
        const a = (i / 8) * Math.PI * 2 - Math.PI / 2;
        const rr = i % 2 === 0 ? (i === 4 ? 78 : 52) * (0.6 + 0.4 * k) : 6;
        g.lineTo(sx + Math.cos(a) * rr, sy + Math.sin(a) * rr);
      }
      g.closePath();
      g.fill();
    }
    // eyes
    const eyeA = remap(u, 0.86, 1.0) * (o.eyes ?? 1);
    if (eyeA > 0) {
      for (const sx of [1, -1]) {
        const [ex, ey] = st.eye;
        g.fillStyle = rgba([255, 150, 50], eyeA * bright);
        g.beginPath();
        g.ellipse(ex * sx, ey, 9, 4.2, sx * -0.18, 0, Math.PI * 2);
        g.fill();
        g.fillStyle = rgba([255, 235, 200], eyeA * bright);
        g.beginPath();
        g.arc(ex * sx, ey, 2.2, 0, Math.PI * 2);
        g.fill();
      }
    }
    g.restore();
  }

  // ---------------------------------------------------------------------------
  draw(t, info) {
    const W1 = 1920 * (this.W / this.H) / (1920 / 1080); // design width at 1080p height
    const CX = W1 / 2;

    // ACT I — epigraph
    if (t > CUE.poemIn && t < CUE.poemOut + 0.7) {
      const out = 1 - smooth(remap(t, CUE.poemOut - 0.2, CUE.poemOut + 0.6));
      const lines = ['Das ist des Jägers Ehrenschild,', 'daß er beschützt und hegt sein Wild'];
      lines.forEach((s, li) => {
        const t0 = CUE.poemIn + li * 0.75;
        const y = 498 + li * 74;
        const per = (i, n) => {
          const lt = remap(t, t0 + i * 0.032, t0 + i * 0.032 + 0.7);
          return { a: smooth(lt) * out, blur: (1 - lt) * 7, dy: (1 - ease.outCubic(lt)) * 8 };
        };
        this.text(s, { x: CX, y, family: 'Frak', size: 58, color: [233, 214, 172], perChar: per });
        this.text(s, {
          x: CX, y, family: 'Frak', size: 58, color: [255, 170, 80], glow: true, alpha: 0.6,
          perChar: (i, n) => {
            const lt = remap(t, t0 + i * 0.032, t0 + i * 0.032 + 0.7);
            return { a: Math.sin(Math.PI * clamp(lt)) * out, blur: 3 };
          },
        });
      });
      const ta = smooth(remap(t, CUE.poemIn + 1.7, CUE.poemIn + 2.6)) * out;
      this.text("THIS IS THE HUNTER'S BADGE OF HONOUR — THAT HE GUARDS AND TENDS HIS GAME", {
        x: CX, y: 652, family: 'Mont', weight: 500, size: 11.5, tracking: 0.42, color: [190, 176, 146], alpha: ta * 0.85,
      });
    }

    // ACT I — location
    if (t > CUE.locIn && t < CUE.locOut + 0.1) {
      const a = smooth(remap(t, CUE.locIn, CUE.locIn + 1.0)) * (1 - smooth(remap(t, CUE.locOut - 0.9, CUE.locOut)));
      const tr = lerp(1.15, 0.72, ease.outCubic(remap(t, CUE.locIn, CUE.locIn + 2.6)));
      this.text('WOLFENBÜTTEL', { x: CX, y: 842, family: 'Mont', weight: 500, size: 15, tracking: tr, color: CREAM, alpha: a * 0.92 });
      const lw = 46 * ease.inOutCubic(remap(t, CUE.locIn + 0.4, CUE.locIn + 1.4));
      this.line(CX - lw, 862, CX + lw, 862, { color: ORANGE, width: 1.2, alpha: a });
      this.text('Lower Saxony · 1934', {
        x: CX, y: 900, family: 'Corm', style: 'italic', weight: 400, size: 27, color: [214, 200, 170], alpha: a * smooth(remap(t, CUE.locIn + 0.6, CUE.locIn + 1.6)),
      });
    }

    // ACT I — the stag
    if (t > CUE.stagStart && t < CUE.burst + 0.5 && info.stag) {
      const u = remap(t, CUE.stagStart, CUE.stagDone);
      const igniteFade = 1 - smooth(remap(t, CUE.ignite + 0.15, CUE.burst + 0.1));
      const flare = Math.exp(-Math.pow((t - CUE.ignite - 0.05) * 5, 2)) * 0.8;
      this.stagFigure(u, info.stag.x, info.stag.y, info.stag.scale, { bright: (0.85 + flare) * igniteFade * info.stag.alpha, time: t });
    }

    // ACT II — 56 botanicals
    if (t > CUE.botText && t < CUE.whip) {
      const out = 1 - smooth(remap(t, CUE.disperse - 0.1, CUE.disperse + 0.5));
      const a = smooth(remap(t, CUE.botText, CUE.botText + 0.9)) * out;
      const tr = lerp(1.6, 0.85, ease.outQuart(remap(t, CUE.botText, CUE.botText + 2.4)));
      this.text('BOTANICALS', { x: CX, y: 790, family: 'Mont', weight: 500, size: 19, tracking: tr, color: CREAM, alpha: a });
      const words = ['citrus peel', 'licorice', 'anise', 'poppy seed', 'saffron', 'ginger', 'juniper', 'ginseng'];
      const str = words.join('  ·  ');
      const starts = [];
      let idx = 0;
      words.forEach((w, i) => {
        starts.push([idx, idx + w.length, CUE.ingredients + i * 0.22]);
        idx += w.length + 5;
      });
      this.text(str, {
        x: CX, y: 846, family: 'Corm', style: 'italic', weight: 400, size: 28, color: [226, 206, 166], alpha: out,
        perChar: (i) => {
          let st = null;
          for (const s of starts) if (i < s[1] + 5) { st = s; break; }
          if (!st) st = starts[starts.length - 1];
          const lt = remap(t, st[2] + (i - st[0]) * 0.012, st[2] + (i - st[0]) * 0.012 + 0.55);
          return { a: smooth(lt), blur: (1 - lt) * 4, dy: (1 - ease.outCubic(lt)) * 6 };
        },
      });
      const sa = smooth(remap(t, CUE.ingredients + 1.9, CUE.ingredients + 2.7)) * out;
      this.text('AND FORTY-EIGHT MORE · A SECRET SINCE 1934', { x: CX, y: 888, family: 'Mont', weight: 500, size: 10.5, tracking: 0.5, color: [255, 140, 60], alpha: sa });
    }

    // ACT II — 365 days in oak
    if (t > CUE.countStart - 0.6 && t < CUE.freeze + 0.6) {
      const out = 1 - smooth(remap(t, CUE.freeze - 0.3, CUE.freeze + 0.5));
      const cy = 500;
      const ringA = smooth(remap(t, CUE.countStart - 0.6, CUE.countStart + 0.2)) * out;
      const prog = ease.outQuart(remap(t, CUE.countStart, CUE.countEnd));
      const n = Math.max(1, Math.round(prog * 365));
      // year ring with week ticks
      const g = this.ctx(false);
      const S = this.S;
      g.save();
      g.translate(CX * S, cy * S);
      g.strokeStyle = rgba(CREAM, 0.16 * ringA);
      g.lineWidth = 1 * S;
      g.beginPath();
      g.arc(0, 0, 236 * S, 0, Math.PI * 2);
      g.stroke();
      for (let k = 0; k < 52; k++) {
        const ang = -Math.PI / 2 + (k / 52) * Math.PI * 2;
        const major = k % 13 === 0;
        const on = k / 52 <= prog;
        const len = major ? 14 : 6;
        g.strokeStyle = on ? rgba(GOLD, (major ? 0.95 : 0.7) * ringA) : rgba(CREAM, 0.22 * ringA);
        g.lineWidth = (major ? 1.6 : 1) * S;
        g.beginPath();
        g.moveTo(Math.cos(ang) * (250) * S, Math.sin(ang) * 250 * S);
        g.lineTo(Math.cos(ang) * (250 + len) * S, Math.sin(ang) * (250 + len) * S);
        g.stroke();
      }
      g.restore();
      // progress arc on glow
      const gg = this.ctx(true);
      gg.save();
      gg.translate(CX * S, cy * S);
      gg.strokeStyle = rgba([255, 170, 80], 0.95 * ringA);
      gg.lineWidth = 2.2 * S;
      gg.lineCap = 'round';
      gg.beginPath();
      gg.arc(0, 0, 236 * S, -Math.PI / 2, -Math.PI / 2 + Math.max(0.001, prog) * Math.PI * 2);
      gg.stroke();
      const ha = -Math.PI / 2 + prog * Math.PI * 2;
      gg.fillStyle = rgba([255, 230, 190], ringA);
      gg.beginPath();
      gg.arc(Math.cos(ha) * 236 * S, Math.sin(ha) * 236 * S, 3.2 * S, 0, Math.PI * 2);
      gg.fill();
      gg.restore();
      // digits in fixed slots
      const digits = String(n).padStart(3, '0');
      const da = smooth(remap(t, CUE.countStart - 0.2, CUE.countStart + 0.4)) * out;
      const slot = 118;
      for (let k = 0; k < 3; k++) {
        const isLead = digits.slice(0, k + 1).split('').every((c) => c === '0') && k < 2;
        this.text(digits[k], { x: CX + (k - 1) * slot, y: cy + 62, family: 'Cinzel', weight: 400, size: 176, color: CREAM, alpha: da * (isLead ? 0.18 : 1) });
      }
      const ca = smooth(remap(t, CUE.daysText, CUE.daysText + 0.8)) * out;
      const ctr = lerp(1.4, 0.75, ease.outQuart(remap(t, CUE.daysText, CUE.daysText + 2.2)));
      this.text('DAYS IN OAK', { x: CX, y: cy + 128, family: 'Mont', weight: 500, size: 16, tracking: ctr, color: [255, 150, 70], alpha: ca });
      const ia = smooth(remap(t, CUE.daysText + 0.7, CUE.daysText + 1.5)) * out;
      this.text('a full year at rest, before a single bottle is filled', { x: CX, y: 826, family: 'Corm', style: 'italic', weight: 400, size: 27, color: [222, 204, 170], alpha: ia });
    }

    // ACT II — ice cold
    if (t > CUE.coldText && t < CUE.shatter) {
      const a = smooth(remap(t, CUE.coldText, CUE.coldText + 1.0)) * (1 - smooth(remap(t, CUE.crack + 0.1, CUE.crack + 0.5)));
      const tr = lerp(1.5, 0.8, ease.outQuart(remap(t, CUE.coldText, CUE.coldText + 2.5)));
      this.text('SERVED ICE COLD', { x: CX, y: 708, family: 'Mont', weight: 500, size: 18, tracking: tr, color: ICE, alpha: a });
      this.text('straight from the freezer · in one shot', { x: CX, y: 752, family: 'Corm', style: 'italic', weight: 400, size: 27, color: [206, 228, 236], alpha: a * smooth(remap(t, CUE.coldText + 0.6, CUE.coldText + 1.4)) });
    }

    // ACT III — callouts around the bottle
    if (info.callouts) this.callouts(t, info.callouts);

    // ACT III — end card
    if (t > CUE.endcard - 0.05) this.endcard(t, info);
  }

  callouts(t, list) {
    const S = this.S;
    const fadeAll = 1 - smooth(remap(t, CUE.beatEnd - 0.5, CUE.beatEnd + 0.1));
    if (fadeAll <= 0) return;
    list.forEach((c, i) => {
      const t0 = CUE.callouts[i];
      const u = remap(t, t0 - 0.05, t0 + 0.6);
      if (u <= 0) return;
      const side = c.side;
      const [ax, ay] = c.anchor;
      const ex = ax + side * 70, ey = ay - 46;
      const lx = ex + side * 190;
      const pu = ease.outCubic(remap(u, 0, 0.45));
      const pu2 = ease.outCubic(remap(u, 0.3, 0.8));
      const ta = smooth(remap(u, 0.45, 1.0)) * fadeAll;
      const ring = ease.outBack(remap(u, 0, 0.35));
      // anchor ring
      const gctx = this.ctx(true);
      gctx.save();
      gctx.strokeStyle = rgba([255, 160, 70], fadeAll);
      gctx.lineWidth = 1.4 * S;
      gctx.beginPath();
      gctx.arc(ax * S, ay * S, 7 * ring * S, 0, Math.PI * 2);
      gctx.stroke();
      gctx.fillStyle = rgba([255, 225, 190], fadeAll);
      gctx.beginPath();
      gctx.arc(ax * S, ay * S, 2.2 * S, 0, Math.PI * 2);
      gctx.fill();
      gctx.restore();
      // leader line
      const mx = lerp(ax, ex, pu), my = lerp(ay, ey, pu);
      this.line(ax + side * 7 * 0.7, ay - 7 * 0.7, mx, my, { color: CREAM, alpha: 0.7 * fadeAll, width: 1 });
      if (pu2 > 0) this.line(ex, ey, lerp(ex, lx, pu2), ey, { color: CREAM, alpha: 0.7 * fadeAll, width: 1 });
      // label
      const align = side > 0 ? 'right' : 'left';
      const tx = lx;
      const slide = (1 - ease.outCubic(remap(u, 0.45, 1.0))) * 18;
      this.text(c.value, { x: tx - side * slide, y: ey - 14, family: 'Cinzel', weight: 400, size: 46, color: CREAM, alpha: ta, align });
      this.text(c.label, { x: tx - side * slide * 0.6, y: ey + 27, family: 'Mont', weight: 600, size: 13, tracking: 0.36, color: [255, 176, 110], alpha: ta, align });
    });
  }

  endcard(t, info) {
    const W1 = 1920 * (this.W / this.H) / (1920 / 1080);
    const cx = info.endX ?? W1 * 0.34;
    const out = 1 - smooth(remap(t, CUE.fadeOut, CUE.fadeDone));
    // emblem
    const eu = remap(t, CUE.endcard - 0.05, CUE.endcard + 1.1);
    this.stagFigure(Math.pow(eu, 0.7), cx, 268, 0.255, { bright: 0.9 * out, time: t, eyes: 1, star: smooth(remap(t, CUE.endcard + 0.7, CUE.endcard + 1.5)) * out });
    // wordmark with a travelling light sweep
    const wy = 520;
    const wa = smooth(remap(t, CUE.endcard, CUE.endcard + 0.5)) * out;
    const sweep = remap(t, CUE.endcard + 0.1, CUE.endcard + 1.8);
    const S = this.S;
    const ctx = this.ctx(false);
    ctx.save();
    ctx.font = `400 ${150 * S}px Frak`;
    const w = ctx.measureText('Jägermeister').width;
    const x0 = cx * S - w / 2;
    const grad = ctx.createLinearGradient(x0 - 200 * S, 0, x0 + w + 200 * S, 0);
    const sp = lerp(-0.15, 1.15, ease.inOutCubic(sweep));
    const c0 = 'rgba(236,224,196,1)';
    grad.addColorStop(0, c0);
    grad.addColorStop(clamp(sp - 0.12), c0);
    grad.addColorStop(clamp(sp), 'rgba(255,246,226,1)');
    grad.addColorStop(clamp(sp + 0.12), c0);
    grad.addColorStop(1, c0);
    ctx.fillStyle = grad;
    ctx.globalAlpha = wa;
    const rise = (1 - ease.outCubic(remap(t, CUE.endcard, CUE.endcard + 1.2))) * 16;
    blurText(ctx, 'Jägermeister', x0, (wy + rise) * S, (1 - smooth(remap(t, CUE.endcard, CUE.endcard + 0.7))) * 10 * S);
    ctx.restore();
    // glow pass for the sweep highlight
    const g = this.ctx(true);
    g.save();
    g.font = `400 ${150 * S}px Frak`;
    const gr2 = g.createLinearGradient(x0 - 200 * S, 0, x0 + w + 200 * S, 0);
    gr2.addColorStop(0, 'rgba(255,150,60,0)');
    gr2.addColorStop(clamp(sp - 0.06), 'rgba(255,150,60,0)');
    gr2.addColorStop(clamp(sp), 'rgba(255,200,130,0.9)');
    gr2.addColorStop(clamp(sp + 0.06), 'rgba(255,150,60,0)');
    gr2.addColorStop(1, 'rgba(255,150,60,0)');
    g.fillStyle = gr2;
    g.globalAlpha = wa * (sweep > 0 && sweep < 1 ? 1 : 0);
    g.fillText('Jägermeister', x0, (wy + rise) * S);
    g.restore();
    // rule + tagline
    const la = ease.inOutCubic(remap(t, CUE.tagline - 0.4, CUE.tagline + 0.6));
    this.line(cx - 160 * la, 572, cx + 160 * la, 572, { color: ORANGE, width: 1.3, alpha: out, glow: false });
    const ta = smooth(remap(t, CUE.tagline, CUE.tagline + 1.0)) * out;
    const tr = lerp(1.0, 0.5, ease.outQuart(remap(t, CUE.tagline, CUE.tagline + 2.6)));
    this.text('BORN IN THE FOREST', { x: cx, y: 622, family: 'Mont', weight: 500, size: 15, tracking: tr, color: CREAM, alpha: ta });
    this.text('MADE FOR THE NIGHT', { x: cx, y: 654, family: 'Mont', weight: 500, size: 15, tracking: tr, color: [255, 128, 40], alpha: smooth(remap(t, CUE.tagline + 0.35, CUE.tagline + 1.3)) * out });
    const lg = smooth(remap(t, CUE.legal, CUE.legal + 1.0)) * out;
    this.text('56 BOTANICALS  ·  35% VOL  ·  SINCE 1934', { x: cx, y: 730, family: 'Mont', weight: 400, size: 10, tracking: 0.38, color: [200, 186, 158], alpha: lg * 0.8 });
    this.text('PLEASE ENJOY RESPONSIBLY', { x: W1 / 2, y: 1032, family: 'Mont', weight: 400, size: 9.5, tracking: 0.42, color: [200, 190, 170], alpha: lg * 0.55 });
  }
}
