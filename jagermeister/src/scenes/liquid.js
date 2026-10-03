import * as THREE from 'three';
import { FSPass, GLSL_COMMON } from '../gl.js';

// Act II: macro of the herbal liqueur swirling in backlight (365 days in oak),
// then it freezes: frost creeps in, "−18°C" crystallises, the ice cracks.

const FRAG = /* glsl */ `
${GLSL_COMMON}
uniform vec2 uRes;
uniform float uTime, uFlow, uFreeze, uFrost, uFrostText, uCrack, uPush;
uniform sampler2D uText;
in vec2 vUv; out vec4 fragColor;

float liquidH(vec2 p, float t, out vec2 warp) {
  vec2 q = p * 1.45;
  vec2 a = vec2(gfbm(q + vec2(0.0, t * 0.06), 4), gfbm(q + vec2(5.2, 1.3) - t * 0.05, 4));
  vec2 b = vec2(gfbm(q + 3.2 * a + vec2(1.7, 9.2) + t * 0.08, 4), gfbm(q + 3.2 * a + vec2(8.3, 2.8) - t * 0.07, 4));
  warp = b - a;
  return gfbm(q + 2.8 * b + vec2(t * 0.02, 0.0), 5);
}

// broad, smooth surface swell for the reflections (the colour uses the detailed field)
float surfH(vec2 p, float t) {
  vec2 q = p * 1.15;
  vec2 a = vec2(gfbm(q + vec2(0.0, t * 0.07), 3), gfbm(q + vec2(5.2, 1.3) - t * 0.06, 3));
  return gfbm(q + 1.7 * a + vec2(t * 0.035, 0.0), 3);
}

vec3 bubbles(vec2 p, float t) {
  vec3 acc = vec3(0.0);
  for (int l = 0; l < 2; l++) {
    float fl = float(l);
    float sc = l == 0 ? 5.0 : 9.0;
    vec2 q = p * sc;
    q.y -= t * (0.16 + 0.12 * fl) * sc;
    q.x += sin(q.y * 0.7 + fl) * 0.15;
    vec2 cell = floor(q);
    vec2 f = fract(q) - 0.5;
    vec4 h = h42(cell + fl * 37.0);
    if (h.w > 0.13) continue;
    vec2 c = (h.xy - 0.5) * 0.5;
    float rad = mix(0.035, 0.11, h.z) * (l == 0 ? 1.0 : 0.7);
    float d = length(f - c);
    float aa = 1.5 * sc / uRes.y;
    float disk = smoothstep(rad + aa, rad - aa, d);
    float ring = disk * smoothstep(rad * 0.6, rad, d);
    float spec = smoothstep(rad * 0.3, 0.0, length(f - c - vec2(-rad, rad) * 0.38));
    acc += vec3(1.0, 0.78, 0.5) * (ring * 0.18 + spec * 1.6) * (l == 0 ? 1.0 : 0.6);
  }
  return acc;
}

// frost: feathered ice needles radiating from scattered seed crystals, at three scales
float crystals(vec2 p, float scale, float density) {
  vec2 g = p * scale;
  vec2 cell = floor(g);
  vec2 f = fract(g);
  float px = scale / uRes.y;
  float acc = 0.0;
  for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++) {
    vec2 off = vec2(float(i), float(j));
    vec4 h = h42(cell + off);
    if (h.w > density) continue;
    vec2 c = off + 0.2 + 0.6 * h.xy - f;
    float ang0 = h.z * PI;
    float len = 0.5 + 0.65 * fract(h.x * 7.31);
    for (int k = 0; k < 3; k++) {
      float a = ang0 + float(k) * 1.0471976;
      vec2 dir = vec2(cos(a), sin(a));
      float along = abs(dot(-c, dir));
      float across = abs(dot(-c, vec2(-dir.y, dir.x)));
      if (along > len || across > 0.25) continue;
      float taper = 1.0 - along / len;
      float w = 0.010 * taper + px * 0.6;
      float spine = smoothstep(w + px, w - px * 0.5, across);
      float bp = fract(along * 8.0 + h.y * 3.0);
      float barb = smoothstep(px * 1.6, 0.0, abs(across - bp * 0.17 * taper)) * step(across, 0.17 * taper);
      acc += (spine + barb * 0.55) * (0.35 + 0.65 * taper);
    }
  }
  return acc;
}
float frostPattern(vec2 p) {
  float f = crystals(p, 5.0, 0.55);
  f += crystals(p * 1.07 + 3.1, 12.0, 0.6) * 0.7;
  f += crystals(p + 7.7, 27.0, 0.65) * 0.45;
  f += (fbm(p * 18.0, 3) - 0.35) * 0.25;
  return max(f, 0.0);
}

float angD(float a, float b){ return abs(atan(sin(a - b), cos(a - b))); }
// jagged radial fractures + broken concentric rings, grown out to radius R
float crackDist(vec2 p, float R) {
  float r = length(p);
  float a = atan(p.y, p.x);
  float d = 1e3;
  for (int i = 0; i < 15; i++) {
    float fi = float(i);
    vec2 hh = h22(vec2(fi, 17.0));
    float ai = (fi + hh.x * 0.8) / 15.0 * TAU;
    float x1 = r * 5.0, x2 = r * 17.0;
    float j1 = mix(h12(vec2(floor(x1), fi * 3.7)), h12(vec2(floor(x1) + 1.0, fi * 3.7)), fract(x1)) - 0.5;
    float j2 = mix(h12(vec2(floor(x2), fi * 1.3 + 50.0)), h12(vec2(floor(x2) + 1.0, fi * 1.3 + 50.0)), fract(x2)) - 0.5;
    float jit = j1 * 0.34 + j2 * 0.07;
    float len = mix(0.45, 1.0, hh.y) * R;
    float dd = angD(a, ai + jit * smoothstep(0.0, 0.12, r)) * r;
    dd += smoothstep(len - 0.04, len, r) * 1e3;
    d = min(d, dd);
  }
  for (int k = 0; k < 4; k++) {
    float fk = float(k);
    float rk = 0.07 + fk * 0.1 + (gnoise(vec2(a * 2.0, fk * 9.0)) - 0.5) * 0.04;
    float seg = smoothstep(0.40, 0.46, gnoise(vec2(a * 1.6 + fk * 7.0, fk * 3.0)));
    float dr = abs(r - rk) + (1.0 - seg) * 1e3 + step(R, rk) * 1e3;
    d = min(d, dr);
  }
  return d;
}

void main(){
  vec2 uv = vUv;
  float asp = uRes.x / uRes.y;
  vec2 p = (gl_FragCoord.xy - 0.5 * uRes) / uRes.y;
  p *= 1.0 - 0.012 * uPush;

  // --- liquid surface
  vec2 warp;
  float t = uFlow;
  float h = liquidH(p, t, warp);
  float e = 2.0 / uRes.y;
  float s0 = surfH(p, t);
  vec2 grad = vec2(surfH(p + vec2(e, 0.0), t) - s0, surfH(p + vec2(0.0, e), t) - s0) / e;
  vec3 N = normalize(vec3(-grad * 0.11, 1.0));
  vec3 R = reflect(vec3(0.0, 0.0, -1.0), N);
  // light through the liqueur: deep mahogany, glowing amber where it runs thin
  vec2 bl = p - vec2(0.0, 0.04);
  float back = 0.03 + 0.85 * exp(-dot(bl, bl) * 3.2);
  float thick = 0.4 + 1.9 * smoothstep(0.2, 0.8, h);
  vec3 sigma = vec3(2.2, 3.2, 6.0);
  vec3 col = vec3(1.0, 0.8, 0.56) * back * 1.9 * exp(-sigma * thick);
  col += vec3(0.5, 0.12, 0.02) * smoothstep(0.2, 0.7, length(warp)) * 0.03 * back;
  // glossy surface: a large softbox and a thin strip reflected in the moving liquid
  vec2 rb = R.xy;
  // glossy surface: broad soft highlight + a tighter hot spot from a key light up-left
  vec3 Lk = normalize(vec3(-0.45, 0.5, 0.75));
  float sp = max(dot(R, Lk), 0.0);
  col += vec3(1.0, 0.84, 0.66) * (pow(sp, 18.0) * 0.10 + pow(sp, 90.0) * 0.55);
  col += vec3(0.9, 0.55, 0.3) * pow(1.0 - N.z, 3.0) * 0.6 * back;
  col += bubbles(p, uTime) * (1.0 - uFreeze) * (0.25 + back);
  col *= 1.0 - 0.45 * smoothstep(0.25, 1.0, length(p * vec2(0.75, 1.0)));

  // --- freeze: the liquid cools and goes dark-glassy
  float l = luma(col);
  vec3 cold = vec3(l) * vec3(0.5, 0.82, 1.0) * 0.85 + vec3(0.0, 0.004, 0.008);
  col = mix(col, cold, uFreeze * 0.85);

  // --- frost creeping in from the frame edges
  vec2 eu = vec2(min(uv.x, 1.0 - uv.x) * asp, min(uv.y, 1.0 - uv.y));
  float ed = min(eu.x, eu.y);
  ed += (fbm(p * 2.6, 4) - 0.5) * 0.26 + (fbm(p * 10.0, 3) - 0.5) * 0.07;
  float front = uFrost * 0.22;
  float fmask = smoothstep(front + 0.03, front - 0.12, ed) * step(0.001, uFrost);
  float fp = frostPattern(p);
  vec3 iceC = vec3(0.70, 0.88, 1.0);
  col = mix(col, col * 0.45 + vec3(0.010, 0.018, 0.026), fmask * 0.75);
  col += iceC * fp * fmask * 0.42;
  col += iceC * 0.025 * fmask;
  vec2 gp = floor(gl_FragCoord.xy / 2.0);
  float gl = step(0.996, fh(gp)) * (0.5 + 0.5 * sin(uTime * 7.0 + fh(gp + 3.1) * 40.0));
  col += vec3(0.9, 0.97, 1.0) * gl * fmask * (0.4 + fp) * 3.5;

  // --- "−18°C" crystallising from the letter edges inwards
  if (uFrostText > 0.0) {
    vec4 tx = texture(uText, uv);
    float sd = (tx.g - 0.5) * 2.0;
    float aa = max(fwidth(sd), 1e-4);
    float grow = uFrostText * 1.1 + (fbm(p * 9.0, 3) - 0.5) * 0.2;
    float inside = smoothstep(-aa, aa, sd) * smoothstep(sd - 0.05, sd + 0.03, grow * 0.45);
    float edge = smoothstep(aa * 1.6, aa * 0.2, abs(sd)) * smoothstep(0.0, 0.25, uFrostText);
    float tp = frostPattern(p * 1.7 + 3.0);
    vec3 letters = iceC * (0.75 + tp * 0.7) * inside * 1.1;
    letters += vec3(0.85, 0.95, 1.0) * edge * 1.1;
    float lg = step(0.992, fh(gp + 7.0)) * (0.5 + 0.5 * sin(uTime * 9.0 + fh(gp) * 50.0));
    letters += vec3(1.0) * lg * inside * 6.0;
    float halo = smoothstep(-0.3, 0.0, sd) * (1.0 - step(0.0, sd)) * 0.06 * uFrostText;
    col = mix(col, col * 0.3, inside * 0.8);
    col += letters + iceC * halo;
  }

  // --- the ice cracks: lines of light racing out from the centre
  if (uCrack > 0.0) {
    vec2 cp = p - vec2(0.0, 0.03);
    float R = pow(uCrack, 0.55) * 1.25;
    float cd = crackDist(cp, R);
    float px = 1.0 / uRes.y;
    float line = smoothstep(1.3 * px, 0.2 * px, cd);
    col += vec3(0.82, 0.94, 1.0) * line * (2.0 + 6.0 * uCrack);
    col += vec3(0.5, 0.8, 1.0) * exp(-cd * 260.0) * 0.5 * uCrack;
  }

  fragColor = vec4(col, 0.0);
}`;

// Euclidean distance transform (Felzenszwalb & Huttenlocher) for the text SDF
function edt1d(f, n) {
  const d = new Float32Array(n), v = new Int32Array(n), z = new Float32Array(n + 1);
  let k = 0;
  v[0] = 0;
  z[0] = -1e20;
  z[1] = 1e20;
  for (let q = 1; q < n; q++) {
    let s = (f[q] + q * q - (f[v[k]] + v[k] * v[k])) / (2 * q - 2 * v[k]);
    while (s <= z[k]) {
      k--;
      s = (f[q] + q * q - (f[v[k]] + v[k] * v[k])) / (2 * q - 2 * v[k]);
    }
    k++;
    v[k] = q;
    z[k] = s;
    z[k + 1] = 1e20;
  }
  k = 0;
  for (let q = 0; q < n; q++) {
    while (z[k + 1] < q) k++;
    d[q] = (q - v[k]) * (q - v[k]) + f[v[k]];
  }
  return d;
}
function edt(grid, w, h) {
  const out = new Float32Array(w * h);
  const col = new Float32Array(h);
  for (let x = 0; x < w; x++) {
    for (let y = 0; y < h; y++) col[y] = grid[y * w + x];
    const d = edt1d(col, h);
    for (let y = 0; y < h; y++) out[y * w + x] = d[y];
  }
  const row = new Float32Array(w);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) row[x] = out[y * w + x];
    const d = edt1d(row, w);
    for (let x = 0; x < w; x++) out[y * w + x] = Math.sqrt(d[x]);
  }
  return out;
}

function makeTextSDF(W, H) {
  const w = W, h = H;
  const S = h / 1080; // 1080p design px → canvas px
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  const g = c.getContext('2d');
  g.fillStyle = '#fff';
  g.font = `400 ${300 * S}px Cinzel`;
  g.textAlign = 'center';
  g.textBaseline = 'alphabetic';
  g.fillText('−18°C', w / 2, 575 * S);
  const img = g.getImageData(0, 0, w, h).data;
  const INF = 1e20;
  const inside = new Float32Array(w * h), outside = new Float32Array(w * h);
  for (let i = 0; i < w * h; i++) {
    const a = img[i * 4 + 3] / 255;
    inside[i] = a > 0.5 ? 0 : INF; // distance to nearest inside pixel (for outside pixels)
    outside[i] = a > 0.5 ? INF : 0;
  }
  const dOut = edt(inside, w, h);
  const dIn = edt(outside, w, h);
  const maxD = 30 * S;
  const data = new Uint8Array(w * h * 4);
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) {
      const i = y * w + x;
      const j = (h - 1 - y) * w + x; // flip for GL
      const sd = dIn[i] - dOut[i];
      data[j * 4] = img[i * 4 + 3];
      data[j * 4 + 1] = Math.max(0, Math.min(255, Math.round((0.5 + sd / (2 * maxD)) * 255)));
      data[j * 4 + 2] = 0;
      data[j * 4 + 3] = 255;
    }
  const tex = new THREE.DataTexture(data, w, h, THREE.RGBAFormat);
  tex.minFilter = THREE.LinearFilter;
  tex.magFilter = THREE.LinearFilter;
  tex.needsUpdate = true;
  return tex;
}

export class LiquidScene {
  constructor(renderer, W, H) {
    this.r = renderer;
    const u = (v) => ({ value: v });
    this.pass = new FSPass(FRAG, {
      uRes: u(new THREE.Vector2(W, H)), uTime: u(0), uFlow: u(0), uFreeze: u(0), uFrost: u(0), uFrostText: u(0),
      uCrack: u(0), uPush: u(0), uText: u(makeTextSDF(W, H)),
    });
  }
  render(target, s) {
    const U = this.pass.uniforms;
    U.uTime.value = s.time;
    U.uFlow.value = s.flow;
    U.uFreeze.value = s.freeze;
    U.uFrost.value = s.frost;
    U.uFrostText.value = s.frostText;
    U.uCrack.value = s.crack;
    U.uPush.value = s.push;
    this.pass.render(this.r, target);
  }
}
