import * as THREE from 'three';
import { CUE } from './timeline.js';
import { CUE as L } from './legacy.js';
import { VO } from './vo-lines.js';
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
  const verts = Object.entries(pts).map(([k, p]) => ({ p, order: clamp((188 - p[1]) / 340) * 0.85 + rand() * 0.15, tw: rand(), sp: [rand(), rand(), rand(), rand()] }));
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

// 3D pose of the constellation: the head turns towards us as it forms.
export function stagPose(t) {
  const u = ease.outCubic(remap(t, L.stagStart - 0.4, L.stagDone + 0.6));
  return { yaw: lerp(0.62, 0.0, u) + 0.018 * Math.sin(t * 0.9), pitch: lerp(0.16, 0.0, u) };
}
// stag design space (y down) → posed and projected; returns [x, y, X, Y, Z] (Z towards the viewer)
export function stagProjector(pose, D = 1700) {
  const cy = Math.cos(pose.yaw), sy = Math.sin(pose.yaw), cp = Math.cos(pose.pitch), sp = Math.sin(pose.pitch);
  return (x, y, antler, zOverride) => {
    const ax = Math.abs(x);
    const z = zOverride ?? (antler ? -0.3 * ax - 0.18 * Math.max(0, -150 - y) : 45 * clamp((y + 150) / 338) - 0.42 * ax);
    const X = x * cy + z * sy;
    const Z1 = -x * sy + z * cy;
    const Y = y * cp + Z1 * sp;
    const Z = -y * sp + Z1 * cp;
    const k = D / (D - Z);
    return [X * k, Y * k, X, Y, Z];
  };
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
    this.mk = () => {
      const c = document.createElement('canvas');
      c.width = W;
      c.height = H;
      return c;
    };
    this.tc = this.mk();
    this.gc = this.mk();
    this.sc = this.mk();
    this.t = this.tc.getContext('2d');
    this.g = this.gc.getContext('2d');
    this.s = this.sc.getContext('2d');
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
    this.subTex = tex(this.sc);
    this.usedText = this.usedGlow = this.usedSub = false;
    this.dirtyText = this.dirtyGlow = this.dirtySub = true;
    this.stag = buildStag();
  }

  begin() {
    // Fresh canvases instead of clearing: in Chromium, a full-canvas clear (clearRect, reset()
    // or a width reset) right after the canvas was uploaded as a WebGL texture can be dropped,
    // which leaves the previous frame's typography behind.
    if (this.dirtyText) {
      this.tc = this.mk();
      this.t = this.tc.getContext('2d');
      this.textTex.image = this.tc;
    }
    if (this.dirtyGlow) {
      this.gc = this.mk();
      this.g = this.gc.getContext('2d');
      this.glowTex.image = this.gc;
    }
    if (this.dirtySub) {
      this.sc = this.mk();
      this.s = this.sc.getContext('2d');
      this.subTex.image = this.sc;
    }
    this.usedText = this.usedGlow = this.usedSub = false;
  }
  upload() {
    if (this.usedText) this.textTex.needsUpdate = true;
    if (this.usedGlow) this.glowTex.needsUpdate = true;
    if (this.usedSub) this.subTex.needsUpdate = true;
    this.dirtyText = this.usedText;
    this.dirtyGlow = this.usedGlow;
    this.dirtySub = this.usedSub;
  }
  ctx(glow) {
    if (glow === 'sub') {
      this.usedSub = true;
      return this.s;
    }
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
  // The stag constellation, posed in 3D. u: 0..1 build progress (with sub-phases),
  // cx/cy/scale in design px, o.pose = { yaw, pitch }.
  stagFigure(u, cx, cy, scale, o = {}) {
    const S = this.S;
    const g = this.ctx(true);
    const st = this.stag;
    const bright = o.bright ?? 1;
    const time = o.time ?? 0;
    const pr = stagProjector(o.pose || { yaw: 0, pitch: 0 });
    g.save();
    g.translate(cx * S, cy * S);
    g.scale(scale * S, scale * S);
    g.lineJoin = 'round';
    g.lineCap = 'round';

    // facets, shaded by their 3D orientation (they turn with the head)
    const fu = remap(u, 0.45, 0.85);
    if (fu > 0) {
      for (const f of st.facets) {
        const P = f.P.map((p) => pr(p[0], p[1], false));
        const ux = P[1][2] - P[0][2], uy = P[1][3] - P[0][3], uz = P[1][4] - P[0][4];
        const vx = P[2][2] - P[0][2], vy = P[2][3] - P[0][3], vz = P[2][4] - P[0][4];
        let nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
        const nl = Math.hypot(nx, ny, nz) || 1;
        if (nz < 0) { nx = -nx; ny = -ny; nz = -nz; }
        const lit = Math.max(0, (nx * -0.42 + ny * -0.68 + nz * 0.6) / nl);
        const a = smooth(remap(fu, f.order * 0.6, f.order * 0.6 + 0.4)) * (0.1 + 0.9 * lit) * 0.2 * bright;
        if (a <= 0.003) continue;
        g.fillStyle = rgba(GOLD, a);
        g.beginPath();
        g.moveTo(P[0][0], P[0][1]);
        g.lineTo(P[1][0], P[1][1]);
        g.lineTo(P[2][0], P[2][1]);
        g.closePath();
        g.fill();
      }
    }
    // edges
    const eu = remap(u, 0.12, 0.62);
    g.lineWidth = 1.6 / scale;
    g.strokeStyle = rgba(GOLD, 0.85 * bright);
    for (const e of st.edges) {
      const p = ease.outCubic(remap(eu, e.order * 0.7, e.order * 0.7 + 0.3));
      if (p <= 0) continue;
      const a = pr(e.a[0], e.a[1], false), b = pr(e.b[0], e.b[1], false);
      g.beginPath();
      g.moveTo(a[0], a[1]);
      g.lineTo(lerp(a[0], b[0], p), lerp(a[1], b[1], p));
      g.stroke();
    }
    // vertices — twinkle in like stars
    const vu = remap(u, 0.0, 0.4);
    for (const v of st.verts) {
      const a = remap(vu, v.order * 0.75, v.order * 0.75 + 0.25);
      if (a <= 0) continue;
      const q = pr(v.p[0], v.p[1], false);
      const pop = Math.exp(-Math.pow((a - 0.15) * 4.0, 2)) * 2.2;
      const tw = 0.75 + 0.25 * Math.sin(time * (3 + v.tw * 5) + v.tw * 30);
      const r = (2.1 + pop * 2.4) / scale;
      g.fillStyle = rgba([255, 232, 190], clamp(a * 3) * tw * bright);
      g.beginPath();
      g.arc(q[0], q[1], r, 0, Math.PI * 2);
      g.fill();
    }
    // antlers, growing like branches
    const au = remap(u, 0.25, 0.92);
    const beamP = ease.inOutCubic(remap(au, 0, 0.8));
    const tips = [];
    for (const side of [1, -1]) {
      const P = (pts) => pts.map(([x, y]) => pr(side * x, y, true));
      const beam = P(st.beam);
      const tines = st.tines.map((tn) => ({ ...tn, pts: P(tn.pts) }));
      g.fillStyle = rgba([226, 160, 82], 0.95 * bright);
      const tip = taper(g, beam, 11, 2.6, beamP, false);
      if (tip && beamP < 0.999) tips.push(tip);
      for (const tn of tines) {
        const tp = ease.outCubic(remap(beamP, tn.anchor, Math.min(1, tn.anchor + 0.32)));
        const tp2 = Math.min(tp, remap(au, 0, 1) * 1.5);
        const tt = taper(g, tn.pts, tn.w0, tn.w1, tp2, false);
        if (tt && tp2 < 0.999) tips.push(tt);
      }
      // bright filament core
      g.fillStyle = rgba([255, 230, 180], 0.9 * bright);
      taper(g, beam, 3.2, 0.8, beamP, false);
      for (const tn of tines) {
        const tp = ease.outCubic(remap(beamP, tn.anchor, Math.min(1, tn.anchor + 0.32)));
        taper(g, tn.pts, 1.8, 0.5, Math.min(tp, remap(au, 0, 1) * 1.5), false);
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
      const [sx, sy] = pr(st.star[0], st.star[1], false, -40);
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
        const [ex, ey] = pr(st.eye[0] * sx, st.eye[1], false);
        g.fillStyle = rgba([255, 150, 50], eyeA * bright);
        g.beginPath();
        g.ellipse(ex, ey, 9, 4.2, sx * -0.18, 0, Math.PI * 2);
        g.fill();
        g.fillStyle = rgba([255, 235, 200], eyeA * bright);
        g.beginPath();
        g.arc(ex, ey, 2.2, 0, Math.PI * 2);
        g.fill();
      }
    }
    g.restore();
  }

  // Sparks of light streaking in from the forest to become the stag's vertices.
  stagSparks(t, cx, cy, scale, pose, bright) {
    const S = this.S;
    const g = this.ctx(true);
    const pr = stagProjector(pose);
    const span = L.stagDone - L.stagStart;
    g.save();
    g.lineCap = 'round';
    for (const v of this.stag.verts) {
      const tArr = L.stagStart + span * 0.3 * v.order;
      const dur = 0.75 + 0.35 * v.sp[3];
      const s0 = (t - (tArr - dur)) / dur;
      if (s0 <= 0 || s0 > 1.35) continue;
      const q = pr(v.p[0], v.p[1], false);
      const ex = cx + q[0] * scale, ey = cy + q[1] * scale;
      const ang = Math.PI / 2 + (v.sp[0] - 0.5) * 2.6;
      const dist = 380 + 520 * v.sp[1];
      const sx = ex + Math.cos(ang) * dist * 1.3, sy = ey + Math.sin(ang) * dist;
      const curl = (v.sp[2] - 0.5) * 0.9 * dist;
      const mx = (sx + ex) / 2 - Math.sin(ang) * curl, my = (sy + ey) / 2 + Math.cos(ang) * curl;
      const at = (s) => {
        const e = ease.inOutCubic(clamp(s));
        const a = (1 - e) * (1 - e), b = 2 * (1 - e) * e, c = e * e;
        return [a * sx + b * mx + c * ex, a * sy + b * my + c * ey];
      };
      const fade = 1 - smooth(remap(s0, 1.0, 1.35));
      let prev = at(s0);
      for (let k = 1; k <= 10; k++) {
        const p = at(s0 - k * 0.035);
        const w = (1 - k / 11) * 2.6;
        g.strokeStyle = rgba([255, 196, 120], (1 - k / 11) * 0.9 * fade * bright);
        g.lineWidth = Math.max(0.4, w) * S;
        g.beginPath();
        g.moveTo(prev[0] * S, prev[1] * S);
        g.lineTo(p[0] * S, p[1] * S);
        g.stroke();
        prev = p;
      }
      if (s0 < 1.0) {
        const h = at(s0);
        g.fillStyle = rgba([255, 240, 214], 0.95 * bright);
        g.beginPath();
        g.arc(h[0] * S, h[1] * S, 2.4 * S, 0, Math.PI * 2);
        g.fill();
      }
    }
    g.restore();
  }

  // ---------------------------------------------------------------------------
  draw(t, info) {
    const W1 = 1920 * (this.W / this.H) / (1920 / 1080); // design width at 1080p height
    const CX = W1 / 2;

    // ACT 0 — title over the ripples
    if (t > CUE.titleIn - 0.1 && t < CUE.titleOut + 0.2) this.title(t, CX);

    // ACT I — Wolfenbüttel, 1934
    if (t > CUE.locIn && t < CUE.locOut + 0.1) this.location(t, CX, CUE.locIn, CUE.locOut, 'WOLFENBÜTTEL · GERMANY', '1934');

    // ACT I — the stag (on The Hunter's Hour clock)
    if (info.tl !== undefined && info.stag && info.tl > L.stagStart - 1.2 && info.tl < L.burst + 0.5) {
      const tl = info.tl;
      const u = remap(tl, L.stagStart, L.stagDone);
      const igniteFade = 1 - 0.75 * smooth(remap(tl, L.ignite + 0.15, L.burst - 0.1)) - 0.25 * smooth(remap(tl, L.burst - 0.1, L.burst + 0.15));
      const flare = Math.exp(-Math.pow((tl - L.ignite - 0.05) * 5, 2)) * 0.8;
      const pose = stagPose(tl);
      const sg = info.stag;
      this.stagSparks(tl, sg.x, sg.y, sg.scale, pose, sg.alpha);
      if (u > 0) this.stagFigure(u, sg.x, sg.y, sg.scale, { bright: (0.85 + flare) * igniteFade * sg.alpha, time: tl, pose });
    }

    // ACT I — 56 botanicals, a year in oak
    if (t > CUE.burst + 0.8 && t < CUE.whip) {
      const out = 1 - smooth(remap(t, CUE.disperse - 0.2, CUE.disperse + 0.4));
      const t0 = CUE.vo.botanicals + 0.2;
      const a = smooth(remap(t, t0, t0 + 0.8)) * out;
      const tr = lerp(1.6, 0.85, ease.outQuart(remap(t, t0, t0 + 2.2)));
      this.text('BOTANICALS', { x: CX, y: 790, family: 'Mont', weight: 500, size: 19, tracking: tr, color: CREAM, alpha: a });
      const t1 = CUE.vo.botanicals + 1.7;
      const b = smooth(remap(t, t1, t1 + 0.7)) * out;
      this.text('365 days in oak', { x: CX, y: 842, family: 'Corm', style: 'italic', weight: 400, size: 30, color: [226, 206, 166], alpha: b, blur: (1 - b) * 4 });
    }

    // ACT I — ice cold
    if (t > CUE.coldText + 0.4 && t < CUE.shatter) {
      const t0 = CUE.coldText + 0.6;
      const a = smooth(remap(t, t0, t0 + 0.9)) * (1 - smooth(remap(t, CUE.crack + 0.1, CUE.crack + 0.5)));
      const tr = lerp(1.5, 0.8, ease.outQuart(remap(t, t0, t0 + 2.2)));
      this.text('SERVED ICE COLD', { x: CX, y: 708, family: 'Mont', weight: 500, size: 18, tracking: tr, color: ICE, alpha: a });
    }

    // ACT II — Lake Tahoe
    if (t > CUE.tahoeLocIn && t < CUE.tahoeLocOut + 0.1) this.location(t, CX, CUE.tahoeLocIn, CUE.tahoeLocOut, 'LAKE TAHOE · CALIFORNIA', 'circa 1997');

    // ACT III — the slam and the recipe
    if (t > CUE.slam - 0.05 && t < CUE.cuts[1] + 0.05) this.slam(t, CX);
    if (info.callout) this.callout(t, info.callout);

    // END
    if (t > CUE.endcard - 0.05) this.endcard(t, info);

    // subtitles over everything
    this.subtitles(t, CX, info);
  }

  location(t, CX, t0, t1, line1, line2) {
    const a = smooth(remap(t, t0, t0 + 1.0)) * (1 - smooth(remap(t, t1 - 0.8, t1)));
    const tr = lerp(1.15, 0.6, ease.outCubic(remap(t, t0, t0 + 2.8)));
    this.text(line1, { x: CX, y: 812, family: 'Mont', weight: 500, size: 15, tracking: tr, color: CREAM, alpha: a * 0.92 });
    const lw = 46 * ease.inOutCubic(remap(t, t0 + 0.4, t0 + 1.4));
    this.line(CX - lw, 838, CX + lw, 838, { color: ORANGE, width: 1.2, alpha: a });
    this.text(line2, { x: CX, y: 880, family: 'Corm', style: 'italic', weight: 400, size: 30, color: [214, 200, 170], alpha: a * smooth(remap(t, t0 + 0.6, t0 + 1.6)) });
  }

  title(t, CX) {
    const S = this.S;
    const out = 1 - smooth(remap(t, CUE.titleOut - 0.7, CUE.titleOut));
    const y = 560;
    const str = 'THE DROP';
    const n = str.length;
    const per = (i) => {
      const fromC = Math.abs(i - (n - 1) / 2) / ((n - 1) / 2);
      const t0 = CUE.titleIn + fromC * 0.45;
      const lt = remap(t, t0, t0 + 1.1);
      const o = remap(t, CUE.titleOut - 0.8 + fromC * 0.25, CUE.titleOut - 0.1 + fromC * 0.2);
      return { a: smooth(lt) * (1 - smooth(o)), blur: (1 - lt) * 10 + o * 8, dy: (1 - ease.outCubic(lt)) * 12 - o * 6 };
    };
    const tr = lerp(0.62, 0.48, ease.outCubic(remap(t, CUE.titleIn, CUE.titleOut)));
    this.text(str, { x: CX, y, family: 'Cinzel', weight: 400, size: 104, tracking: tr, color: [238, 226, 198], perChar: per });
    const sweep = remap(t, CUE.titleIn + 1.0, CUE.titleIn + 2.4);
    this.text(str, {
      x: CX, y, family: 'Cinzel', weight: 400, size: 104, tracking: tr, color: [255, 150, 60], glow: true,
      perChar: (i) => {
        const c = per(i);
        const sx = i / (n - 1);
        const band = Math.exp(-Math.pow((sx - lerp(-0.2, 1.2, sweep)) / 0.1, 2)) * (sweep > 0 && sweep < 1 ? 1 : 0);
        return { a: c.a * (0.2 + 0.9 * band), blur: 2 + c.blur, dy: c.dy };
      },
    });
    const rw = 130 * ease.inOutCubic(remap(t, CUE.titleIn + 0.6, CUE.titleIn + 1.8));
    const ra = out * smooth(remap(t, CUE.titleIn + 0.5, CUE.titleIn + 1.2));
    this.line(CX - rw, 600, CX + rw, 600, { color: ORANGE, width: 1.2, alpha: ra * 0.9 });
    const sa = out * smooth(remap(t, CUE.titleIn + 0.9, CUE.titleIn + 1.9));
    this.text('the legend of the Jägerbomb', {
      x: CX, y: 650, family: 'Corm', style: 'italic', weight: 400, size: 30, color: [214, 200, 170], alpha: sa, blur: (1 - sa) * 5,
    });
  }

  // JÄGERBOMB, slammed onto the first beat
  slam(t, CX) {
    const u = remap(t, CUE.slam, CUE.slam + 0.35);
    const out = 1 - smooth(remap(t, CUE.cuts[1] - 0.35, CUE.cuts[1]));
    const sc = lerp(1.35, 1.0, ease.outExpo(u));
    const a = smooth(remap(t, CUE.slam - 0.02, CUE.slam + 0.08)) * out;
    const y = 470;
    const S = this.S;
    const ctx = this.ctx(false);
    ctx.save();
    ctx.translate(CX * S, y * S);
    ctx.scale(sc, sc);
    ctx.font = `400 ${168 * S}px Frak`;
    ctx.textAlign = 'center';
    ctx.globalAlpha = a;
    ctx.shadowColor = 'rgba(0,0,0,0.55)';
    ctx.shadowBlur = 30 * S;
    ctx.fillStyle = 'rgb(240,228,202)';
    ctx.fillText('Jägerbomb', 0, 0);
    ctx.restore();
    // hot glow that fades after the hit
    const g = this.ctx(true);
    g.save();
    g.translate(CX * S, y * S);
    g.scale(sc, sc);
    g.font = `400 ${168 * S}px Frak`;
    g.textAlign = 'center';
    g.globalAlpha = a * (0.25 + 0.75 * Math.exp(-(t - CUE.slam) / 0.35));
    g.fillStyle = 'rgb(255,120,30)';
    g.fillText('Jägerbomb', 0, 0);
    g.restore();
    const la = smooth(remap(t, CUE.slam + 0.2, CUE.slam + 0.7)) * out;
    const lw = 190 * ease.outCubic(remap(t, CUE.slam + 0.15, CUE.slam + 0.8));
    this.line(CX - lw, y + 48, CX + lw, y + 48, { color: ORANGE, width: 1.4, alpha: la });
    const tr = lerp(1.2, 0.62, ease.outQuart(remap(t, CUE.slam + 0.3, CUE.slam + 2.0)));
    this.text('A LEGEND IN ONE DROP', { x: CX, y: y + 92, family: 'Mont', weight: 500, size: 16, tracking: tr, color: CREAM, alpha: la });
  }

  // recipe callouts on "One shot." / "Ice cold." / "Drop it."
  callout(t, c) {
    const S = this.S;
    const CALL = [
      { value: '1 SHOT', label: 'JÄGERMEISTER' },
      { value: '−18°C', label: 'STRAIGHT FROM THE FREEZER' },
      { value: 'DROP IT', label: 'INTO HALF A GLASS OF ENERGY DRINK' },
    ][c.i];
    const t0 = CUE.callouts[c.i];
    const u = remap(t, t0 - 0.05, t0 + 0.6);
    if (u <= 0) return;
    if (c.i === 1) {
      // over the bright macro: a centred super with a shadow instead of a leader line
      const W1 = 1920 * (this.W / this.H) / (1920 / 1080);
      const a = smooth(remap(u, 0.0, 0.6)) * (1 - smooth(remap(t, CUE.cuts[3] - 0.25, CUE.cuts[3])));
      const tr = lerp(0.5, 0.2, ease.outCubic(remap(u, 0, 1)));
      // a soft dark scrim so the type reads over the bright drink
      const S = this.S;
      const sc = this.ctx(false);
      sc.save();
      sc.translate((W1 / 2) * S, 600 * S);
      sc.scale(1, 0.42);
      const rg = sc.createRadialGradient(0, 0, 0, 0, 0, 520 * S);
      rg.addColorStop(0, `rgba(10,5,0,${0.6 * a})`);
      rg.addColorStop(0.55, `rgba(10,5,0,${0.38 * a})`);
      rg.addColorStop(1, 'rgba(10,5,0,0)');
      sc.fillStyle = rg;
      sc.fillRect(-520 * S, -520 * S, 1040 * S, 1040 * S);
      sc.restore();
      this.text(CALL.value, { x: W1 / 2, y: 590, family: 'Cinzel', weight: 400, size: 150, tracking: tr * 0.3, color: [246, 250, 252], alpha: a, shadow: 'rgba(40,20,0,0.75)', shadowBlur: 40, blur: (1 - a) * 8 });
      this.text(CALL.label, { x: W1 / 2, y: 660, family: 'Mont', weight: 600, size: 16, tracking: lerp(1.0, 0.45, ease.outQuart(u)), color: [255, 246, 228], alpha: a, shadow: 'rgba(40,20,0,0.8)', shadowBlur: 16 });
      return;
    }
    const side = c.side;
    const [ax, ay] = c.anchor;
    // "Drop it." sits over a big top-down glass: a long leader, and the label set clear of it
    const wide = c.i === 2;
    const ex = ax + side * (wide ? 330 : 80), ey = ay - 60;
    const lx = ex + side * (wide ? 40 : 210);
    const pu = ease.outCubic(remap(u, 0, 0.45));
    const pu2 = ease.outCubic(remap(u, 0.3, 0.8));
    const ta = smooth(remap(u, 0.45, 1.0));
    const ring = ease.outBack(remap(u, 0, 0.35));
    const g = this.ctx(true);
    g.save();
    g.strokeStyle = rgba([255, 160, 70], 1);
    g.lineWidth = 1.4 * S;
    g.beginPath();
    g.arc(ax * S, ay * S, 8 * ring * S, 0, Math.PI * 2);
    g.stroke();
    g.fillStyle = rgba([255, 225, 190], 1);
    g.beginPath();
    g.arc(ax * S, ay * S, 2.4 * S, 0, Math.PI * 2);
    g.fill();
    g.restore();
    this.line(ax + side * 6, ay - 6, lerp(ax, ex, pu), lerp(ay, ey, pu), { color: CREAM, alpha: 0.75, width: 1 });
    if (pu2 > 0) this.line(ex, ey, lerp(ex, lx, pu2), ey, { color: CREAM, alpha: 0.75, width: 1 });
    const align = wide ? (side > 0 ? 'left' : 'right') : side > 0 ? 'right' : 'left';
    const slide = (1 - ease.outCubic(remap(u, 0.45, 1.0))) * 18;
    this.text(CALL.value, { x: lx - side * slide, y: ey - 16, family: 'Cinzel', weight: 400, size: 50, color: CREAM, alpha: ta, align });
    this.text(CALL.label, { x: lx - side * slide * 0.6, y: ey + 28, family: 'Mont', weight: 600, size: 13, tracking: 0.32, color: [255, 176, 110], alpha: ta, align });
  }

  endcard(t, info) {
    const W1 = 1920 * (this.W / this.H) / (1920 / 1080);
    const cx = info.endX ?? W1 * 0.32;
    const out = 1 - smooth(remap(t, CUE.fadeOut, CUE.fadeDone));
    const eu = remap(t, CUE.endcard - 0.05, CUE.endcard + 1.1);
    this.stagFigure(Math.pow(eu, 0.7), cx, 262, 0.25, { bright: 0.9 * out, time: t, eyes: 1, star: smooth(remap(t, CUE.endcard + 0.7, CUE.endcard + 1.5)) * out });
    const wy = 512;
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
    const la = ease.inOutCubic(remap(t, CUE.tagline - 0.4, CUE.tagline + 0.6));
    this.line(cx - 160 * la, 566, cx + 160 * la, 566, { color: ORANGE, width: 1.3, alpha: out, glow: false });
    const ta = smooth(remap(t, CUE.tagline, CUE.tagline + 1.0)) * out;
    const tr = lerp(1.0, 0.5, ease.outQuart(remap(t, CUE.tagline, CUE.tagline + 2.6)));
    this.text('BORN IN THE FOREST', { x: cx, y: 616, family: 'Mont', weight: 500, size: 15, tracking: tr, color: CREAM, alpha: ta });
    this.text('DROPPED INTO LEGEND', { x: cx, y: 648, family: 'Mont', weight: 500, size: 15, tracking: tr, color: [255, 128, 40], alpha: smooth(remap(t, CUE.tagline + 1.3, CUE.tagline + 2.1)) * out });
    const lg = smooth(remap(t, CUE.legal, CUE.legal + 1.0)) * out;
    this.text('THE JÄGERBOMB  ·  ONE ICE-COLD SHOT OF JÄGERMEISTER, DROPPED INTO ENERGY DRINK', { x: cx, y: 724, family: 'Mont', weight: 400, size: 9.5, tracking: 0.3, color: [200, 186, 158], alpha: lg * 0.8 });
    this.text('PLEASE ENJOY RESPONSIBLY', { x: W1 / 2, y: 1040, family: 'Mont', weight: 400, size: 9.5, tracking: 0.42, color: [200, 190, 170], alpha: lg * 0.55 });
  }

  // burned-in subtitles, timed to the voice-over
  subtitles(t, CX, info) {
    const keys = Object.keys(CUE.vo).sort((a, b) => CUE.vo[a] - CUE.vo[b]);
    for (let i = 0; i < keys.length; i++) {
      const k = keys[i];
      const t0 = CUE.vo[k] - 0.05;
      const next = i + 1 < keys.length ? CUE.vo[keys[i + 1]] - 0.1 : 1e9;
      const t1 = Math.min(CUE.vo[k] + VO[k].dur + 0.45, next);
      if (t < t0 || t > t1) continue;
      const a = smooth(remap(t, t0, t0 + 0.14)) * (1 - smooth(remap(t, t1 - 0.2, t1)));
      // in the letterbox bar while it is there, just above the frame edge after
      const y = 1022;
      this.text(VO[k].sub, {
        x: CX, y, family: 'Mont', weight: 500, size: 31, tracking: 0.02, color: [242, 234, 216], alpha: a, glow: 'sub',
        shadow: 'rgba(0,0,0,0.85)', shadowBlur: 10,
      });
    }
  }
}
