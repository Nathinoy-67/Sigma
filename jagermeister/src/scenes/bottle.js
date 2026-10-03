import * as THREE from 'three';
import { FSPass, GLSL_COMMON } from '../gl.js';
import { buildStag, taper } from '../overlay.js';

// Act III: the bottle. A square-shouldered bottle built from a superellipse
// sweep, shaded with an analytic studio (strip lights, rim lights, warm
// backlight through dark herbal liqueur), ice-cold condensation, a foil label
// and a mirror floor.

const BODY = 0.17;
const LABEL = { hw: 0.124, y0: 0.085, y1: 0.535 };

function profile(y) {
  const r = 0.016;
  if (y < r) return [BODY - r + Math.sqrt(Math.max(0, r * r - (r - y) * (r - y))), 7];
  if (y < 0.595) return [BODY, 7];
  if (y < 0.705) {
    const s = (y - 0.595) / 0.11;
    const hw = 0.064 + (BODY - 0.064) * 0.5 * (1 + Math.cos(Math.PI * s));
    const n = 7 - 5 * Math.min(1, Math.max(0, (s - 0.05) / 0.75)) ** 0.8;
    return [hw, n];
  }
  return [0.064 - 0.004 * ((y - 0.705) / 0.245), 2];
}

function bottleGeometry() {
  const NT = 200;
  const ys = [];
  for (let i = 0; i <= 24; i++) ys.push((0.016 * i) / 24);
  for (let i = 1; i <= 120; i++) ys.push(0.016 + ((0.595 - 0.016) * i) / 120);
  for (let i = 1; i <= 110; i++) ys.push(0.595 + (0.11 * i) / 110);
  for (let i = 1; i <= 60; i++) ys.push(0.705 + (0.245 * i) / 60);
  const pos = [];
  for (const y of ys) {
    const [hw, n] = profile(y);
    const e = 2 / n;
    for (let k = 0; k < NT; k++) {
      const th = (k / NT) * Math.PI * 2;
      const c = Math.cos(th), s = Math.sin(th);
      pos.push(hw * Math.sign(c) * Math.pow(Math.abs(c), e), y, hw * Math.sign(s) * Math.pow(Math.abs(s), e));
    }
  }
  const idx = [];
  for (let j = 0; j < ys.length - 1; j++)
    for (let k = 0; k < NT; k++) {
      const a = j * NT + k, b = j * NT + ((k + 1) % NT), c = (j + 1) * NT + k, d = (j + 1) * NT + ((k + 1) % NT);
      idx.push(a, c, b, b, c, d);
    }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

function makeLabel() {
  const w = 900, h = Math.round((900 * (LABEL.y1 - LABEL.y0)) / (2 * LABEL.hw));
  const mk = () => {
    const c = document.createElement('canvas');
    c.width = w;
    c.height = h;
    return c;
  };
  const ca = mk(), cf = mk();
  const g = ca.getContext('2d'), f = cf.getContext('2d');
  const grd = g.createRadialGradient(w / 2, h * 0.4, 40, w / 2, h * 0.45, h * 0.75);
  grd.addColorStop(0, '#17271c');
  grd.addColorStop(1, '#060c08');
  g.fillStyle = grd;
  g.fillRect(0, 0, w, h);
  // paper fibre
  let seed = 7;
  const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < 9000; i++) {
    g.fillStyle = `rgba(255,240,210,${rnd() * 0.03})`;
    g.fillRect(rnd() * w, rnd() * h, 1 + rnd() * 2, 1);
  }
  f.fillStyle = '#000';
  f.fillRect(0, 0, w, h);
  const GOLDC = '#d9a75e';
  const both = (fn) => {
    fn(g, GOLDC);
    fn(f, '#fff');
  };
  // borders
  g.strokeStyle = '#ff6a13';
  g.lineWidth = 12;
  g.strokeRect(20, 20, w - 40, h - 40);
  both((x, c) => {
    x.strokeStyle = c;
    x.lineWidth = 3;
    x.strokeRect(46, 46, w - 92, h - 92);
  });
  // wordmark
  g.textAlign = 'center';
  g.fillStyle = '#efe3c8';
  g.font = '400 66px Frak';
  g.fillText('Jägermeister', w / 2, 168);
  both((x, c) => {
    x.fillStyle = c;
    x.fillRect(w / 2 - 210, 196, 420, 2);
  });
  // medallion with the stag
  const mx = w / 2, my = 560, mr = 300;
  both((x, c) => {
    x.strokeStyle = c;
    x.lineWidth = 7;
    x.beginPath();
    x.arc(mx, my, mr, 0, Math.PI * 2);
    x.stroke();
    x.lineWidth = 2;
    x.beginPath();
    x.arc(mx, my, mr - 18, 0, Math.PI * 2);
    x.stroke();
    for (let k = 0; k < 56; k++) {
      const a = (k / 56) * Math.PI * 2;
      x.beginPath();
      x.moveTo(mx + Math.cos(a) * (mr - 30), my + Math.sin(a) * (mr - 30));
      x.lineTo(mx + Math.cos(a) * (mr - 40), my + Math.sin(a) * (mr - 40));
      x.stroke();
    }
  });
  const st = buildStag();
  const sc = 0.5;
  const sy = my + 92;
  both((x, c) => {
    x.save();
    x.translate(mx, sy);
    x.scale(sc, sc);
    x.strokeStyle = c;
    x.fillStyle = c;
    x.lineWidth = 3.2;
    x.lineCap = 'round';
    for (const e of st.edges) {
      x.beginPath();
      x.moveTo(e.a[0], e.a[1]);
      x.lineTo(e.b[0], e.b[1]);
      x.stroke();
    }
    for (const m of [false, true]) {
      taper(x, st.beam, 13, 3.4, 1, m);
      for (const tn of st.tines) taper(x, tn.pts, tn.w0 + 2, tn.w1 + 1, 1, m);
    }
    // the star between the antlers
    const [sx0, sy0] = st.star;
    x.beginPath();
    const R1 = 46, R2 = 8;
    for (let k = 0; k < 8; k++) {
      const a = (k / 8) * Math.PI * 2 - Math.PI / 2;
      const rr = k % 2 === 0 ? (k === 4 ? R1 * 1.5 : R1) : R2;
      x.lineTo(sx0 + Math.cos(a) * rr, sy0 + Math.sin(a) * rr);
    }
    x.closePath();
    x.fill();
    x.restore();
  });
  // the hunter's verse (English)
  g.fillStyle = 'rgba(236,224,196,0.82)';
  g.font = '400 30px Frak';
  ["This is the hunter's badge of pride:", 'to guard and keep the wild beside,', 'to hunt with honour, as is due,', 'and in the creature, praise its Maker too.'].forEach((s, i) =>
    g.fillText(s, w / 2, 968 + i * 44),
  );
  g.fillStyle = '#ff6a13';
  g.font = '600 34px Mont';
  g.letterSpacing = '12px';
  g.fillText('HERBAL LIQUEUR', w / 2 + 6, 1210);
  both((x, c) => {
    x.fillStyle = c;
    x.fillRect(w / 2 - 150, 1240, 300, 2);
  });
  g.fillStyle = 'rgba(236,224,196,0.9)';
  g.font = '500 23px Mont';
  g.letterSpacing = '6px';
  g.fillText('56 BOTANICALS · 35% VOL · 0.7 L', w / 2 + 3, 1292);
  g.font = '500 19px Mont';
  g.fillStyle = 'rgba(236,224,196,0.6)';
  g.fillText('MADE IN GERMANY · SINCE 1934', w / 2 + 3, 1336);
  const tex = (c) => {
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.NoColorSpace;
    t.anisotropy = 8;
    t.generateMipmaps = true;
    t.minFilter = THREE.LinearMipmapLinearFilter;
    return t;
  };
  return { albedo: tex(ca), foil: tex(cf) };
}

const VERT = /* glsl */ `
out vec3 vW; out vec3 vN; out vec3 vO;
void main(){
  vO = position;
  vec4 w = modelMatrix * vec4(position, 1.0);
  vW = w.xyz;
  vN = normalize(mat3(modelMatrix) * normal);
  gl_Position = projectionMatrix * viewMatrix * w;
}`;

const ENV = /* glsl */ `
uniform float uKeyAng, uBack, uSweep, uReveal, uMirror, uTime, uBeat;
// a tall softbox standing at a real distance from the bottle: reflections slide across
// flat faces as bands instead of lighting the whole face at once
float strip(vec3 P, vec3 R, float ang, float dist, float hw, float y0, float y1) {
  vec3 dir = vec3(sin(ang), 0.0, cos(ang));
  vec3 c = dir * dist;
  float dn = dot(R, -dir);
  if (dn > -1e-3) return 0.0;
  float t = dot(c - P, -dir) / dn;
  if (t <= 0.0) return 0.0;
  vec3 h = P + R * t;
  float u = dot(h - c, vec3(cos(ang), 0.0, -sin(ang)));
  return smoothstep(hw, hw * 0.8, abs(u)) * smoothstep(y0, y0 + 0.2, h.y) * smoothstep(y1, y1 - 0.2, h.y);
}
vec3 env(vec3 P, vec3 R) {
  vec3 c = vec3(0.0);
  c += vec3(1.0, 0.94, 0.86) * 9.0 * strip(P, R, uKeyAng, 1.7, 0.09, -0.3, 1.8);
  c += vec3(0.82, 0.9, 1.0) * 2.0 * strip(P, R, uKeyAng - 2.05, 1.9, 0.3, -0.2, 1.6);
  vec3 rimC = vec3(1.0, 0.6, 0.3) * (4.0 + 6.0 * uBeat) * uBack;
  c += rimC * strip(P, R, 3.14159 - 0.62, 1.4, 0.07, -0.1, 1.5);
  c += rimC * strip(P, R, 3.14159 + 0.62, 1.4, 0.07, -0.1, 1.5);
  c += vec3(0.85, 0.92, 1.0) * 0.6 * smoothstep(0.55, 0.97, R.y);
  c += vec3(0.010, 0.008, 0.006) * (1.0 - smoothstep(-0.25, 0.0, R.y));
  return c;
}`;

const GLASS_FRAG = /* glsl */ `
${GLSL_COMMON}
${ENV}
uniform sampler2D uLabel, uFoil;
in vec3 vW; in vec3 vN; in vec3 vO;
out vec4 fragColor;
const float LHW = ${LABEL.hw.toFixed(4)}, LY0 = ${LABEL.y0.toFixed(4)}, LY1 = ${LABEL.y1.toFixed(4)};

vec3 droplet(vec2 q, float scale, float density) {
  vec2 g = q * scale;
  vec2 cell = floor(g);
  vec3 best = vec3(0.0);
  for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++) {
    vec2 c = cell + vec2(float(i), float(j));
    vec4 h = h42(c);
    if (h.w > density) continue;
    vec2 ctr = c + 0.15 + 0.7 * h.xy;
    float r = mix(0.14, 0.48, h.z * h.z);
    vec2 d = (g - ctr) / r;
    d.y *= 0.82;
    if (dot(d, d) < 1.0) best = vec3(d, 1.0);
  }
  return best;
}

void main(){
  vec3 N0 = normalize(vN);
  vec3 V = normalize(cameraPosition - vW);
  vec3 T = normalize(cross(vec3(0.0, 1.0, 0.0), N0) + vec3(1e-5));
  vec3 B = cross(N0, T);
  float th = atan(vO.z, vO.x);
  vec2 suv = vec2(th * 0.17, vO.y);
  vec2 luv = vec2(vO.x / (2.0 * LHW) + 0.5, (vO.y - LY0) / (LY1 - LY0));
  float fw = fwidth(luv.x) + fwidth(luv.y);
  float inLabel = vO.z > 0.12 ? smoothstep(0.0, fw * 1.5, luv.x) * smoothstep(1.0, 1.0 - fw * 1.5, luv.x) * smoothstep(0.0, fw * 1.5, luv.y) * smoothstep(1.0, 1.0 - fw * 1.5, luv.y) : 0.0;
  float neck = smoothstep(0.795, 0.797, vO.y) * smoothstep(0.862, 0.86, vO.y);

  // condensation: dense near the base, thinning towards the shoulder
  float dens = smoothstep(0.95, 0.15, vO.y) * (1.0 - inLabel) * (1.0 - neck);
  vec3 d1 = droplet(suv, 40.0, 0.30 * dens);
  vec3 d2 = droplet(suv + 7.31, 120.0, 0.55 * dens);
  vec3 N = N0;
  float wet = 0.0;
  if (d1.z > 0.0) { N = normalize(N0 + (T * d1.x + B * d1.y) * 0.6); wet = 1.0; }
  else if (d2.z > 0.0) { N = normalize(N0 + (T * d2.x + B * d2.y) * 0.45); wet = 0.6; }

  float NV = max(dot(N, V), 0.0);
  float F = 0.04 + 0.96 * pow(1.0 - NV, 5.0);
  vec3 R = reflect(-V, N);
  vec3 col = env(vW, R) * F;
  // warm light through dark liqueur and green glass: thin at the edges, deep in the middle
  float NV0 = max(dot(N0, V), 0.0);
  float filled = smoothstep(0.935, 0.925, vO.y);
  float thick = 0.15 + 1.7 * NV0;
  // two passes through dark green glass, one through the reddish-brown liqueur
  vec3 glassT = vec3(0.16, 0.62, 0.22);
  thick = 0.2 + 2.2 * NV0;
  vec3 liqT = mix(vec3(1.0), exp(-vec3(1.6, 2.2, 5.0) * thick), filled);
  float backView = smoothstep(-0.2, 0.9, -dot(normalize(vec3(V.x, 0.0, V.z)), vec3(0.0, 0.0, -1.0)));
  vec3 trans = uBack * vec3(1.0, 0.66, 0.36) * 0.95 * glassT * liqT * mix(0.35, 1.0, filled);
  col += trans * (1.0 - F) * (0.3 + 0.7 * backView);
  col += vec3(0.002, 0.006, 0.003);
  // frosty bloom on the cold glass
  float frost = (fbm(suv * vec2(30.0, 30.0), 3) * 0.7 + 0.3) * smoothstep(0.75, 0.05, vO.y);
  col += vec3(0.55, 0.66, 0.72) * 0.012 * frost * (1.0 - inLabel);
  col *= 1.0 - wet * 0.25 * (1.0 - F);

  // neck band
  if (neck > 0.0) {
    float nl = smoothstep(0.004, 0.0, abs(vO.y - 0.802)) + smoothstep(0.004, 0.0, abs(vO.y - 0.855));
    vec3 nb = vec3(1.0, 0.24, 0.02) * (0.05 + 0.35 * max(dot(N0, normalize(vec3(sin(uKeyAng), 0.3, cos(uKeyAng)))), 0.0));
    vec3 g = vec3(1.0, 0.7, 0.35) * (env(vW, reflect(-V, N0)) * 0.8 + 0.05);
    col = mix(col, mix(nb, g, nl), neck);
  }
  // label: paper + gold foil, swept by a moving light bar
  if (inLabel > 0.0) {
    vec3 alb = pow(texture(uLabel, luv).rgb, vec3(2.2));
    float foil = texture(uFoil, luv).r;
    vec3 Lk = normalize(vec3(sin(uKeyAng), 0.35, cos(uKeyAng)));
    float dif = max(dot(N0, Lk), 0.0) * 0.5 + 0.12;
    float sp = mix(-0.35, 1.35, uSweep);
    float band = exp(-pow((luv.x + (luv.y - 0.5) * 0.35 - sp) / 0.07, 2.0)) * step(0.0, uSweep) * step(uSweep, 1.0);
    vec3 Rl = reflect(-V, N0);
    vec3 gold = vec3(1.0, 0.70, 0.34);
    vec3 foilC = gold * (env(vW, Rl) * 0.7 + 0.12 + band * 7.0) + gold * dif * 0.35;
    vec3 paper = alb * (dif * 1.1 + band * 0.6);
    vec3 lab = mix(paper, foilC, foil);
    lab += env(vW, Rl) * 0.012;
    col = mix(col, lab, inLabel);
  }
  if (uMirror > 0.5) col *= 0.32 * exp(vW.y * 4.5);
  col *= uReveal;
  fragColor = vec4(col, 0.0);
}`;

const CAP_FRAG = /* glsl */ `
${GLSL_COMMON}
${ENV}
in vec3 vW; in vec3 vN; in vec3 vO;
out vec4 fragColor;
void main(){
  vec3 N = normalize(vN);
  vec3 V = normalize(cameraPosition - vW);
  float side = 1.0 - step(0.05, vO.y);
  vec3 T = normalize(cross(vec3(0.0, 1.0, 0.0), N) + vec3(1e-5));
  float th = atan(vO.z, vO.x);
  N = normalize(N + T * sin(th * 110.0) * 0.18 * side * step(-0.036, vO.y));
  float NV = max(dot(N, V), 0.0);
  vec3 R = reflect(-V, N);
  float F = 0.55 + 0.45 * pow(1.0 - NV, 5.0);
  vec3 base = vec3(0.10, 0.11, 0.10);
  float ring = side * (1.0 - step(-0.036, vO.y));
  vec3 tint = mix(base, vec3(1.0, 0.68, 0.32), ring);
  vec3 col = env(vW, R) * tint * F * 1.2 + tint * 0.02;
  if (uMirror > 0.5) col *= 0.32 * exp(vW.y * 4.5);
  col *= uReveal;
  fragColor = vec4(col, 0.0);
}`;

const FLOOR_VERT = /* glsl */ `
out vec3 vW;
void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
const FLOOR_FRAG = /* glsl */ `
${GLSL_COMMON}
uniform float uReveal, uBack, uTime;
in vec3 vW; out vec4 fragColor;
void main(){
  float r = length(vW.xz * vec2(1.0, 1.4));
  vec3 col = vec3(0.0025, 0.003, 0.0025);
  col += vec3(1.0, 0.58, 0.28) * 0.07 * exp(-r * r * 5.0) * (0.3 + uBack);
  col += vec3(1.0, 0.55, 0.25) * 0.05 * exp(-pow(vW.x * 3.0, 2.0)) * smoothstep(0.0, -1.5, vW.z) * uBack;
  float n = fbm(vW.xz * 6.0, 3);
  col *= 0.8 + 0.4 * n;
  col *= uReveal;
  float far = smoothstep(1.6, 4.5, length(vW.xz));
  fragColor = vec4(col, (0.66 + 0.2 * smoothstep(0.5, 2.5, r)) * (1.0 - far));
}`;

const BG_FRAG = /* glsl */ `
${GLSL_COMMON}
uniform vec2 uRes, uGlow;
uniform float uBack, uTime, uReveal, uBeat;
in vec2 vUv; out vec4 fragColor;
void main(){
  vec2 p = (gl_FragCoord.xy - 0.5 * uRes) / uRes.y;
  vec2 d = (p - uGlow) * vec2(0.75, 1.0);
  float r = length(d);
  float glow = exp(-r * 3.4) * 0.14 + exp(-r * 9.0) * 0.42 + exp(-r * 24.0) * 0.45;
  vec3 col = vec3(1.0, 0.5, 0.18) * glow * uBack * (0.75 + 0.5 * uBeat);
  float t = uTime;
  float s1 = fbm(vec2(p.x * 1.3 + t * 0.035, p.y * 2.2 - t * 0.05), 5);
  float s2 = fbm(p * 2.6 + vec2(-t * 0.045, t * 0.025) + s1 * 1.6, 4);
  float smoke = smoothstep(0.38, 0.95, s2);
  col += vec3(1.0, 0.58, 0.28) * smoke * glow * 0.55 * uBack;
  col += vec3(0.004, 0.011, 0.008) * smoke;
  col += vec3(0.002, 0.005, 0.004) * (1.0 - smoothstep(0.0, 0.8, length(p)));
  col *= uReveal;
  fragColor = vec4(col, luma(col) * 1.6);
}`;

// Botanicals orbiting the bottle in a slow vortex; depth-tested so they pass behind it.
const ORBIT_VERT = /* glsl */ `
in vec4 aSeed;
uniform float uTime, uSwirl, uGain, uFocus, uAperture, uRes, uBeat, uRise;
out vec3 vColor; out float vR; out float vPS; out float vA;
void main(){
  float rad = position.x, h = position.y;
  float spd = (0.55 + 0.9 * aSeed.x) * (0.45 / (rad + 0.12));
  float ang = position.z + uSwirl * spd;
  float y = h + 0.035 * sin(uTime * (0.7 + aSeed.z) + aSeed.w * 6.28) + uRise * (0.15 + 0.5 * aSeed.y);
  vec3 p = vec3(cos(ang) * rad, y, sin(ang) * rad);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;
  float dz = -mv.z;
  float focal = projectionMatrix[1][1] * 0.5 * uRes;
  float sz = mix(0.0018, 0.0042, aSeed.z * aSeed.z) * focal / dz;
  float coc = abs(1.0 / dz - 1.0 / uFocus) * uAperture * focal;
  float r = min(max(sz, 0.7) + coc, 0.03 * uRes);
  vR = r; vPS = r * 2.0 + 3.0;
  gl_PointSize = vPS;
  float tw = 0.6 + 0.4 * sin(uTime * (2.0 + aSeed.w * 5.0) + aSeed.x * 40.0);
  vA = uGain * tw * (1.0 + 1.5 * uBeat * aSeed.y) * (max(sz, 0.7) * max(sz, 0.7)) / (r * r) * smoothstep(0.0, 0.08, y) ;
  vColor = aSeed.w < 0.14 ? vec3(0.45, 0.75, 0.25) : mix(vec3(1.0, 0.42, 0.1), vec3(1.0, 0.78, 0.45), aSeed.z);
}`;
const ORBIT_FRAG = /* glsl */ `
in vec3 vColor; in float vR; in float vPS; in float vA;
out vec4 fragColor;
void main(){
  vec2 c = (gl_PointCoord - 0.5) * vPS;
  float r = length(c);
  float a;
  if (vR < 2.2) a = exp(-r * r / max(vR * vR * 0.55, 0.35)) * 1.3;
  else a = smoothstep(vR + 0.8, vR - 0.8, r) * (0.7 + 0.5 * smoothstep(vR * 0.5, vR, r));
  fragColor = vec4(vColor * vA * a, 0.0);
}`;

function orbitGeometry() {
  let seed = 4021;
  const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  const N = 1300;
  const pos = new Float32Array(N * 3), sd = new Float32Array(N * 4);
  for (let i = 0; i < N; i++) {
    const band = rnd();
    pos[i * 3] = band < 0.88 ? 0.25 + 0.36 * Math.pow(rnd(), 0.75) : 0.62 + 0.36 * rnd();
    pos[i * 3 + 1] = 0.03 + Math.pow(rnd(), 1.15) * 1.12;
    pos[i * 3 + 2] = rnd() * Math.PI * 2;
    for (let k = 0; k < 4; k++) sd[i * 4 + k] = rnd();
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('aSeed', new THREE.BufferAttribute(sd, 4));
  return g;
}

export class BottleScene {
  constructor(renderer, W, H) {
    this.r = renderer;
    this.W = W;
    this.H = H;
    this.camera = new THREE.PerspectiveCamera(30, W / H, 0.05, 50);
    const label = makeLabel();
    const u = (v) => ({ value: v });
    this.shared = {
      uKeyAng: u(0.9), uBack: u(1), uSweep: u(-1), uReveal: u(1), uTime: u(0), uBeat: u(0),
    };
    const mkMat = (frag, mirror, extra = {}) =>
      new THREE.ShaderMaterial({
        glslVersion: THREE.GLSL3,
        vertexShader: VERT,
        fragmentShader: frag,
        uniforms: { ...this.shared, uMirror: u(mirror ? 1 : 0), ...extra },
      });
    const geo = bottleGeometry();
    const capGeo = new THREE.CylinderGeometry(0.071, 0.071, 0.11, 160, 1, false);
    const labelU = { uLabel: u(label.albedo), uFoil: u(label.foil) };

    const makeBottle = (mirror) => {
      const grp = new THREE.Group();
      const glass = new THREE.Mesh(geo, mkMat(GLASS_FRAG, mirror, labelU));
      const cap = new THREE.Mesh(capGeo, mkMat(CAP_FRAG, mirror));
      cap.position.y = 0.925 + 0.055;
      grp.add(glass, cap);
      return grp;
    };
    this.bottle = makeBottle(false);
    this.mirror = makeBottle(true);
    this.mirrorRoot = new THREE.Group();
    this.mirrorRoot.scale.y = -1;
    this.mirrorRoot.add(this.mirror);

    this.floorMat = new THREE.ShaderMaterial({
      glslVersion: THREE.GLSL3,
      vertexShader: FLOOR_VERT,
      fragmentShader: FLOOR_FRAG,
      uniforms: { uReveal: this.shared.uReveal, uBack: this.shared.uBack, uTime: this.shared.uTime },
      transparent: true,
      depthWrite: false,
      blending: THREE.CustomBlending,
      blendEquation: THREE.AddEquation,
      blendSrc: THREE.SrcAlphaFactor,
      blendDst: THREE.OneMinusSrcAlphaFactor,
      blendSrcAlpha: THREE.ZeroFactor,
      blendDstAlpha: THREE.ZeroFactor,
    });
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(30, 30), this.floorMat);
    floor.rotation.x = -Math.PI / 2;

    this.orbitMat = new THREE.ShaderMaterial({
      glslVersion: THREE.GLSL3,
      vertexShader: ORBIT_VERT,
      fragmentShader: ORBIT_FRAG,
      uniforms: {
        uTime: this.shared.uTime, uBeat: this.shared.uBeat, uSwirl: u(0), uGain: u(0), uFocus: u(2.5), uAperture: u(0.011),
        uRes: u(H), uRise: u(0),
      },
      transparent: true,
      depthTest: true,
      depthWrite: false,
      blending: THREE.CustomBlending,
      blendEquation: THREE.AddEquation,
      blendSrc: THREE.OneFactor,
      blendDst: THREE.OneFactor,
    });
    const og = orbitGeometry();
    this.orbit = new THREE.Points(og, this.orbitMat);
    this.orbit.frustumCulled = false;
    this.orbit.renderOrder = 2;
    this.orbitMirror = new THREE.Points(og, this.orbitMat);
    this.orbitMirror.frustumCulled = false;
    this.orbitMirror.renderOrder = 0;
    this.mirrorRoot.add(this.orbitMirror);
    floor.renderOrder = 1;

    this.scene = new THREE.Scene();
    this.scene.add(this.mirrorRoot, floor, this.bottle, this.orbit);

    this.bg = new FSPass(BG_FRAG, {
      uRes: u(new THREE.Vector2(W, H)), uGlow: u(new THREE.Vector2(0, 0.1)), uBack: this.shared.uBack, uTime: this.shared.uTime,
      uReveal: this.shared.uReveal, uBeat: this.shared.uBeat,
    });
    this.rotY = 0;
  }

  setCamera(c) {
    this.camera.fov = c.fov;
    this.camera.aspect = this.W / this.H;
    this.camera.position.set(...c.pos);
    this.camera.lookAt(...c.target);
    this.camera.updateProjectionMatrix();
    this.camera.updateMatrixWorld();
  }

  // world point (in bottle space) → 1080p design pixels
  project(p) {
    const v = new THREE.Vector3(...p).applyAxisAngle(new THREE.Vector3(0, 1, 0), this.rotY);
    v.project(this.camera);
    const W1 = 1080 * (this.W / this.H);
    return [(v.x * 0.5 + 0.5) * W1, (0.5 - v.y * 0.5) * 1080];
  }

  render(target, s) {
    this.setCamera(s.cam);
    this.rotY = s.rotY;
    this.bottle.rotation.y = s.rotY;
    this.mirror.rotation.y = s.rotY;
    const S = this.shared;
    S.uKeyAng.value = s.keyAng;
    S.uBack.value = s.back;
    S.uSweep.value = s.sweep;
    S.uReveal.value = s.reveal;
    S.uTime.value = s.time;
    S.uBeat.value = s.beat;
    const O = this.orbitMat.uniforms;
    O.uSwirl.value = s.swirl ?? 0;
    O.uGain.value = s.orbit ?? 0;
    O.uRise.value = s.rise ?? 0;
    O.uFocus.value = this.camera.position.distanceTo(new THREE.Vector3(0, 0.5, 0));
    this.orbit.visible = this.orbitMirror.visible = O.uGain.value > 0;
    // backlight glow sits behind the bottle
    const g = new THREE.Vector3(0, 0.62, -1.2).project(this.camera);
    this.bg.uniforms.uGlow.value.set((g.x * 0.5 * this.W) / this.H, g.y * 0.5);
    this.glowUV = [g.x * 0.5 + 0.5, g.y * 0.5 + 0.5];
    this.bg.render(this.r, target);
    this.r.setRenderTarget(target);
    this.r.render(this.scene, this.camera);
  }
}
