import * as THREE from 'three';
import { FSPass, GLSL_COMMON, rng, getNoiseTexture } from '../gl.js';

// Act I: a camera flight along a winding trail through a night spruce forest
// (fog, glowing mist, embers), ending in a clearing where the Hubertus light ignites.
// The forest is 2.5D: planes of procedural spruce silhouettes every DZ units, recycled
// as the camera flies, composited front to back.

export const DZ = 2.8; // spacing of the tree planes
const NL = 14; // planes in view
const SPX = 2.5; // average tree spacing within a plane
const PATH = { a1: 1.7, w1: 0.105, p1: 0.7, a2: 0.55, w2: 0.29, p2: 2.1 };
export const pathX = (z) => PATH.a1 * Math.sin(z * PATH.w1 + PATH.p1) + PATH.a2 * Math.sin(z * PATH.w2 + PATH.p2);
export const pathSlope = (z) => PATH.a1 * PATH.w1 * Math.cos(z * PATH.w1 + PATH.p1) + PATH.a2 * PATH.w2 * Math.cos(z * PATH.w2 + PATH.p2);
const f = (x) => x.toFixed(4);
const PATH_GLSL = `float pathX(float z){ return ${f(PATH.a1)} * sin(z * ${f(PATH.w1)} + ${f(PATH.p1)}) + ${f(PATH.a2)} * sin(z * ${f(PATH.w2)} + ${f(PATH.p2)}); }`;

const FRAG = /* glsl */ `
${GLSL_COMMON}
uniform vec2 uRes;
uniform float uTime, uF, uTilt, uRoll, uYaw, uFog, uReveal;
uniform vec3 uCam;
uniform vec4 uMoon, uStar, uClearing;
uniform sampler2D uNoise;
in vec2 vUv; out vec4 fragColor;
float fbmT(vec2 p){ return texture(uNoise, p * 0.125).r; }
${PATH_GLSL}

const float GROUND = -1.75;
const int NL = ${NL};
const float DZ = ${f(DZ)};
const float SPX = ${f(SPX)};
const vec3 FOGB = vec3(0.0045, 0.0095, 0.0085);
const vec3 GLOWC = vec3(0.42, 0.74, 0.58);
const vec3 SIL = vec3(0.0008, 0.0016, 0.0014);
float cy, sy;

// glow of the light deep beyond the clearing (uMoon: xy pos, z intensity)
float glowAt(vec2 p) {
  vec2 d = (p - uMoon.xy) * vec2(0.55, 1.0);
  float r = length(d);
  return exp(-r * 3.4) * 0.06 + exp(-r * 8.5) * 0.40 + exp(-r * 26.0) * 1.1;
}

float conifer(vec2 q, float H, float tw, float cb, float seed, float aa, float detail) {
  if (q.y < -0.3 || q.y > H) return 0.0;
  if (abs(q.x) > max((0.085 * H + 0.45) * 1.75, 1.05) + aa) return 0.0;
  float flare = 1.0 + 1.2 * exp(-max(q.y, 0.0) * 2.2);
  float tww = tw * (1.0 - 0.6 * q.y / H) * flare;
  float trunk = smoothstep(tww + aa, tww - aa, abs(q.x));
  float c = 0.0;
  if (q.y > cb - 0.6) {
    float u = clamp((q.y - cb) / (H - cb), 0.0, 1.0);
    float tiers = 9.0 + floor(seed * 7.0);
    float wmax = (0.085 * H + 0.45);
    // drooping whorls: outer branch tips hang lower
    float tc = u * tiers + abs(q.x) * (0.55 * tiers / (H - cb)) + seed * 3.7;
    float ti = floor(tc);
    float tp = fract(tc);
    float tierW = 0.72 + 0.28 * h12(vec2(ti, seed * 91.0));
    float w = pow(1.0 - u, 0.95) * wmax * tierW;
    w *= mix(1.0, 0.30, pow(tp, 0.55));
    float n = vnoise(q * vec2(6.0, 2.2) + seed * 31.0) - 0.5;
    float nn = detail > 0.0 ? vnoise(q * vec2(22.0, 9.0) + seed * 7.0) - 0.5 : 0.0;
    w *= 1.0 + n * 0.6 + nn * 0.35;
    w *= smoothstep(cb - 0.6, cb + 0.4, q.y);
    w = max(w, 0.0);
    c = smoothstep(w + aa, w - aa, abs(q.x));
  }
  // a few bare, broken branch stubs below the crown
  if (q.y > 1.0 && q.y < cb) {
    float row = floor(q.y * 1.4 + seed * 9.0);
    vec2 hh = h22(vec2(row, seed * 113.0));
    if (hh.x > 0.5) {
      float side = hh.y > 0.5 ? 1.0 : -1.0;
      float bx = q.x * side;
      float len = 0.2 + 1.2 * (hh.x - 0.5);
      float yy = (fract(q.y * 1.4 + seed * 9.0) - 0.5) / 1.4 + bx * 0.22;
      float th = 0.018 * (1.0 - 0.7 * bx / len) + aa * 0.5;
      float br = smoothstep(th + aa, th - aa, abs(yy)) * step(0.0, bx) * smoothstep(len, len - 0.05, bx);
      c = max(c, br);
    }
  }
  return max(trunk, c);
}

// coverage of tree plane k at world point P on that plane (Z: plane depth from camera along world z)
float layer(vec2 P, float Z, float Zc, float k, out float rim) {
  float aa = Zc / (uF * uRes.y) * 1.3;
  float cell = floor(P.x / SPX);
  float zw = k * DZ;
  float px0 = pathX(zw);
  float cov = 0.0; rim = 0.0;
  for (int j = -2; j <= 2; j++) {
    float c = cell + float(j);
    vec4 h = h42(vec2(c, k * 17.0 + 3.0));
    float tx = (c + 0.5 + (h.x - 0.5) * 0.85) * SPX;
    float H = mix(16.0, 28.0, h.y);
    // keep the trail and the clearing open
    if (abs(tx - px0) < 1.2 + (0.085 * H + 0.45) * 0.3) continue;
    vec2 dc = (vec2(tx, zw) - uClearing.xy) / uClearing.zw;
    if (dot(dc, dc) < 1.0) continue;
    float tw = mix(0.12, 0.27, h.z);
    float cb = mix(3.5, 9.0, h.w);
    vec2 q = vec2(P.x - tx, P.y - GROUND);
    float cv = conifer(q, H, tw, cb, fract(h.x * 13.7 + h.w), aa, step(Zc, 18.0));
    if (cv <= 0.0) continue;
    float X = tx - uCam.x;
    float sx = uF * (X * cy - Z * sy) / (X * sy + Z * cy);
    float tww = tw * (1.0 - 0.6 * q.y / H);
    float facing = -sign(sx - uMoon.x) * q.x / max(tww, 1e-3);
    rim = max(rim, smoothstep(0.25, 1.0, facing) * cv * step(q.y, H * 0.5));
    cov = max(cov, cv);
  }
  return cov;
}

void main(){
  vec2 p = (gl_FragCoord.xy - 0.5 * uRes) / uRes.y;
  p = rot2(uRoll) * p;
  p.y += uTilt;
  cy = cos(uYaw); sy = sin(uYaw);
  // a pixel's ray hits the plane at world depth Z (from the camera) at X = Z * xk, view depth Zc = Z * zk
  float den = uF * cy - p.x * sy;
  float xk = (uF * sy + p.x * cy) / den;
  float zk = xk * sy + cy;
  float gl = glowAt(p);
  vec3 fogL = FOGB * (0.6 + 0.5 * uFog) + GLOWC * uMoon.z * gl * 0.62;
  float camH = uCam.y - GROUND;
  float dg = p.y < -0.0005 ? camH * uF / -p.y : 1e6;

  // tree planes, front to back
  vec3 acc = vec3(0.0);
  float T = 1.0;
  float k0 = floor(uCam.z / DZ) + 1.0;
  for (int i = 0; i < NL; i++) {
    float k = k0 + float(i);
    float Z = k * DZ - uCam.z;
    float Zc = Z * zk;
    if (Zc > dg || T < 0.004) break;
    vec2 P = vec2(Z * xk + uCam.x, p.y * Zc / uF + uCam.y);
    // drifting fog sheet just in front of this plane
    float fn = fbmT(P * vec2(0.13, 0.30) + vec2(uTime * 0.06 + k * 3.1, k * 1.7));
    float hf = exp(-max(P.y - GROUND, 0.0) * 0.16);
    float fa = smoothstep(0.42, 0.92, fn) * hf * 0.32 * uFog * smoothstep(0.6, 2.5, Zc);
    acc += T * fa * fogL * 1.4;
    T *= 1.0 - fa;
    float rim;
    float cov = layer(P, Z, Zc, k, rim);
    float ff = 1.0 - exp(-Zc * 0.052 * uFog);
    vec3 lc = mix(SIL, fogL, ff) + GLOWC * rim * uMoon.z * 0.10 * (1.0 - ff) * (0.3 + gl * 2.0);
    cov *= smoothstep(0.35, 1.2, Zc) * smoothstep(float(NL) * DZ, (float(NL) - 1.5) * DZ, Z);
    acc += T * cov * lc;
    T *= 1.0 - cov;
  }

  // what lies behind: the ground with its trail, or the sky glowing towards the light
  vec3 bg;
  if (p.y < -0.0005) {
    float xc = p.x * dg / uF;
    vec2 gp = vec2(xc * cy + dg * sy + uCam.x, -xc * sy + dg * cy + uCam.z);
    float gn = fbmT(gp * 0.7);
    float trail = exp(-pow((gp.x - pathX(gp.y)) / 0.75, 2.0));
    vec3 gc = vec3(0.0012, 0.0024, 0.002) * (0.5 + gn) * (1.0 + 2.2 * trail * smoothstep(0.35, 0.7, gn));
    float ff = 1.0 - exp(-dg * 0.05 * uFog);
    bg = mix(gc, fogL, ff);
    float mist = fbmT(gp * vec2(0.16, 0.28) + vec2(uTime * 0.07, 0.0));
    bg = mix(bg, fogL * 1.3, smoothstep(0.38, 0.9, mist) * 0.5 * smoothstep(0.0, 3.0, dg));
  } else {
    bg = mix(vec3(0.008, 0.016, 0.015), vec3(0.0015, 0.003, 0.004), smoothstep(-0.05, 0.5, p.y));
    bg += GLOWC * uMoon.z * gl * 1.2;
  }
  vec3 col = acc + T * bg;

  // Hubertus light: a four-pointed star whose lower arm runs longer — a quiet nod to the cross.
  if (uStar.z > 0.0) {
    vec2 d = p - uStar.xy;
    float s = uStar.w;
    float r = length(d);
    float core = exp(-r * r / (s * s * 0.00005));
    float halo = exp(-r / (s * 0.025)) * 0.25 + exp(-r / (s * 0.12)) * 0.035;
    float ax = abs(d.x), ay = abs(d.y);
    float rayH = exp(-ay / (s * 0.0016)) * exp(-ax / (s * 0.16));
    float rayV = exp(-ax / (s * 0.0016)) * exp(-ay / (s * (d.y < 0.0 ? 0.24 : 0.13)));
    vec2 dr = rot2(0.7853982) * d;
    float rayD = (exp(-abs(dr.x) / (s * 0.0011)) * exp(-abs(dr.y) / (s * 0.035)) + exp(-abs(dr.y) / (s * 0.0011)) * exp(-abs(dr.x) / (s * 0.035))) * 0.4;
    vec3 sc = vec3(1.0, 0.80, 0.52);
    col += sc * uStar.z * (core * 7.0 + halo * 0.7 + (rayH + rayV) * 1.6 + rayD);
  }

  col *= uReveal;
  // alpha carries the light that may scatter into god rays (embers add none)
  fragColor = vec4(col, luma(col));
}`;

// Embers / fireflies drifting along the trail. They are recycled through a band of
// depth ahead of the camera, so the flight streams through them.
const EMBER_VERT = /* glsl */ `
in vec3 position;
in vec4 aSeed;
uniform float uTime, uF, uTilt, uRoll, uYaw, uIntensity, uFocus, uAperture, uRange, uFar;
uniform vec3 uCam; uniform vec2 uRes;
out float vAlpha; out vec3 vColor; out float vR; out float vPS;
${PATH_GLSL}
void main(){
  vec3 P = position;
  float t = uTime;
  P.y = -1.8 + mod(P.y + 1.8 + t * (0.05 + 0.10 * aSeed.x), 4.6);
  P.x += sin(t * (0.25 + aSeed.z * 0.35) + aSeed.w * 6.28) * 0.35;
  P.z += cos(t * (0.18 + aSeed.x * 0.25) + aSeed.y * 6.28) * 0.30;
  float Z = mod(P.z - uCam.z, uRange) + 0.3;
  float X = P.x + pathX(uCam.z + Z) - uCam.x;
  float Y = P.y - uCam.y;
  float cy = cos(uYaw), sy = sin(uYaw);
  float Zc = X * sy + Z * cy;
  if (Zc < 0.25) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); gl_PointSize = 0.0; vAlpha = 0.0; return; }
  vec2 p = vec2(X * cy - Z * sy, Y) * uF / Zc;
  p.y -= uTilt;
  float c = cos(-uRoll), s = sin(-uRoll);
  p = vec2(c * p.x - s * p.y, s * p.x + c * p.y);
  gl_Position = vec4(p.x * 2.0 * uRes.y / uRes.x, p.y * 2.0, 0.0, 1.0);
  float sz = (0.010 + 0.012 * aSeed.y) * uF / Zc * uRes.y;
  float coc = abs(1.0 / Zc - 1.0 / uFocus) * uAperture * uRes.y;
  float r = min(max(sz, 0.9) + coc, 0.035 * uRes.y);
  vR = r;
  vPS = r * 2.0 + 4.0;
  gl_PointSize = vPS;
  float flick = 0.55 + 0.45 * sin(t * (1.7 + aSeed.w * 4.0) + aSeed.x * 40.0);
  flick *= 0.7 + 0.3 * sin(t * (5.3 + aSeed.y * 3.0) + aSeed.z * 17.0);
  float fadeZ = smoothstep(0.25, 1.0, Zc) * smoothstep(uRange, uRange - 4.0, Z) * exp(-Zc * uFar);
  vAlpha = uIntensity * flick * (max(sz, 0.9) * max(sz, 0.9)) / (r * r) * fadeZ;
  vColor = mix(vec3(1.0, 0.36, 0.08), vec3(1.0, 0.68, 0.30), aSeed.z);
}`;

const EMBER_FRAG = /* glsl */ `
in float vAlpha; in vec3 vColor; in float vR; in float vPS;
out vec4 fragColor;
void main(){
  vec2 c = (gl_PointCoord - 0.5) * vPS;
  float r = length(c);
  float disc = smoothstep(vR + 0.9, vR - 0.9, r);
  float rim = smoothstep(vR * 0.55, vR, r) * disc;
  float core = exp(-r * r / max(vR * vR * 0.35, 0.3));
  float a = vR < 2.5 ? core * 1.6 : disc * (0.75 + 0.6 * rim);
  fragColor = vec4(vColor * vAlpha * a, 0.0);
}`;

export class ForestScene {
  constructor(renderer, W, H) {
    this.r = renderer;
    this.W = W;
    this.H = H;
    const u = (v) => ({ value: v });
    this.F = 1 / (2 * Math.tan((50 * Math.PI) / 360));
    this.pass = new FSPass(FRAG, {
      uRes: u(new THREE.Vector2(W, H)), uTime: u(0), uF: u(this.F), uTilt: u(0.06), uRoll: u(0), uYaw: u(0),
      uFog: u(1), uReveal: u(1), uCam: u(new THREE.Vector3(0, 0, 0)),
      uMoon: u(new THREE.Vector4(0.05, 0.3, 1.0, 0.035)), uStar: u(new THREE.Vector4(0, 0.2, 0, 1)),
      uClearing: u(new THREE.Vector4(0, 30, 5, 6)), uNoise: u(getNoiseTexture(renderer)),
    });

    const N = 900;
    this.range = 24;
    const rand = rng(1934);
    const pos = new Float32Array(N * 3);
    const seed = new Float32Array(N * 4);
    for (let i = 0; i < N; i++) {
      pos[i * 3] = (rand() - 0.5) * 9;
      pos[i * 3 + 1] = -1.7 + rand() * 4.4;
      pos[i * 3 + 2] = rand() * this.range;
      for (let k = 0; k < 4; k++) seed[i * 4 + k] = rand();
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    g.setAttribute('aSeed', new THREE.BufferAttribute(seed, 4));
    this.emberMat = new THREE.RawShaderMaterial({
      glslVersion: THREE.GLSL3,
      vertexShader: 'precision highp float;\n' + EMBER_VERT,
      fragmentShader: 'precision highp float;\n' + EMBER_FRAG,
      uniforms: {
        uTime: u(0), uF: u(this.F), uTilt: u(0.06), uRoll: u(0), uYaw: u(0), uIntensity: u(1), uFocus: u(9), uAperture: u(0.014),
        uRange: u(this.range), uFar: u(0.03), uCam: u(new THREE.Vector3()), uRes: u(new THREE.Vector2(W, H)),
      },
      blending: THREE.CustomBlending,
      blendSrc: THREE.OneFactor,
      blendDst: THREE.OneFactor,
      blendEquation: THREE.AddEquation,
      depthTest: false,
      depthWrite: false,
      transparent: true,
    });
    this.embers = new THREE.Points(g, this.emberMat);
    this.embers.frustumCulled = false;
    this.emberScene = new THREE.Scene();
    this.emberScene.add(this.embers);
    this.camera = new THREE.Camera();
  }

  // s: { time, cam:[x,y,z], yaw, roll, tilt, fog, reveal, moon:[x,y,i,r], star:[x,y,i,size], clearing:[x,z,rx,rz], embers, focus }
  render(target, s) {
    const U = this.pass.uniforms;
    U.uTime.value = s.time;
    U.uCam.value.set(...s.cam);
    U.uYaw.value = s.yaw;
    U.uRoll.value = s.roll;
    U.uTilt.value = s.tilt;
    U.uFog.value = s.fog;
    U.uReveal.value = s.reveal;
    U.uMoon.value.set(...s.moon);
    U.uStar.value.set(...s.star);
    U.uClearing.value.set(...s.clearing);
    // before the forest fades in only the embers are drawn
    if (s.reveal > 0.001) this.pass.render(this.r, target);
    if (s.embers > 0) {
      const E = this.emberMat.uniforms;
      E.uTime.value = s.time;
      E.uCam.value.set(...s.cam);
      E.uYaw.value = s.yaw;
      E.uRoll.value = s.roll;
      E.uTilt.value = s.tilt;
      E.uIntensity.value = s.embers;
      E.uFocus.value = s.focus;
      E.uFar.value = s.emberFar ?? 0.03;
      this.r.setRenderTarget(target);
      this.r.render(this.emberScene, this.camera);
    }
  }

  // world point → projection space (what the shader compares uMoon/uStar against: no tilt, no roll)
  projRaw(P, s) {
    const X = P[0] - s.cam[0], Y = P[1] - s.cam[1], Z = P[2] - s.cam[2];
    const cy = Math.cos(s.yaw), sy = Math.sin(s.yaw);
    const Zc = X * sy + Z * cy;
    return [((X * cy - Z * sy) * this.F) / Zc, (Y * this.F) / Zc, Zc];
  }
  // projection space → screen p-space (y up, units of screen height, origin at the centre)
  toScreen(q, s) {
    const x = q[0], y = q[1] - s.tilt;
    const c = Math.cos(-s.roll), sn = Math.sin(-s.roll);
    return [c * x - sn * y, sn * x + c * y];
  }
  project(P, s) {
    const q = this.projRaw(P, s);
    return [...this.toScreen(q, s), q[2]];
  }
}
