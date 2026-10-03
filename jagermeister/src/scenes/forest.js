import * as THREE from 'three';
import { FSPass, GLSL_COMMON, rng, getNoiseTexture } from '../gl.js';

// Act I: a night forest of spruce silhouettes, drifting fog, moonlight and
// embers; the Hubertus light ignites in the clearing.

const FRAG = /* glsl */ `
${GLSL_COMMON}
uniform vec2 uRes;
uniform float uTime, uF, uTilt, uFog, uReveal, uClear, uLayerFade;
uniform vec3 uCam;
uniform vec4 uMoon, uStar;
uniform sampler2D uNoise;
in vec2 vUv; out vec4 fragColor;
float fbmT(vec2 p){ return texture(uNoise, p * 0.125).r; }

const float GROUND = -1.75;
const int NL = 9;
const vec3 FOGB = vec3(0.0045, 0.0095, 0.0085);
const vec3 GLOWC = vec3(0.42, 0.74, 0.58);

// glow of the light source deep in the clearing (uMoon: xy pos, z intensity, w core radius)
float glowAt(vec2 p) {
  vec2 d = (p - uMoon.xy) * vec2(0.55, 1.0);
  float r = length(d);
  return exp(-r * 3.4) * 0.10 + exp(-r * 8.5) * 0.42 + exp(-r * 26.0) * 1.1;
}

float conifer(vec2 q, float H, float tw, float cb, float seed, float aa, float detail) {
  if (q.y < -0.3 || q.y > H) return 0.0;
  // cheap reject: outside the widest possible crown / branch stubs
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

float layer(vec2 p, float z, float seed, float spacing, out float rim) {
  float dz = z - uCam.z;
  vec2 P = p * dz / uF + uCam.xy;
  float aa = dz / (uF * uRes.y) * 1.3;
  float cell = floor(P.x / spacing);
  float cov = 0.0; rim = 0.0;
  for (int k = -2; k <= 2; k++) {
    float c = cell + float(k);
    vec4 h = h42(vec2(c, seed * 17.0));
    float tx = (c + 0.5 + (h.x - 0.5) * 0.85) * spacing;
    float sx = (tx - uCam.x) * uF / dz;
    float H = mix(16.0, 28.0, h.y);
    float crown = (0.085 * H + 0.45) * uF / dz;
    float clr = uClear * (0.75 + 0.5 * h.z) + crown * 0.55;
    if (abs(sx) < clr) continue;
    float tw = mix(0.12, 0.27, h.z);
    float cb = mix(3.5, 9.0, h.w);
    vec2 q = vec2(P.x - tx, P.y - GROUND);
    float cv = conifer(q, H, tw, cb, fract(h.x * 13.7 + h.w), aa, step(dz, 18.0));
    float tww = tw * (1.0 - 0.6 * q.y / H);
    float facing = -sign(sx - uMoon.x) * q.x / max(tww, 1e-3);
    rim = max(rim, smoothstep(0.25, 1.0, facing) * cv * step(q.y, H * 0.5));
    cov = max(cov, cv);
  }
  return cov;
}

void main(){
  vec2 p = (gl_FragCoord.xy - 0.5 * uRes) / uRes.y;
  p.y += uTilt;
  float gl = glowAt(p);
  // sky: near-black overhead, glowing towards the light
  vec3 col = mix(vec3(0.008, 0.016, 0.015), vec3(0.0015, 0.003, 0.004), smoothstep(-0.05, 0.5, p.y));
  col += GLOWC * uMoon.z * gl * 1.2;
  vec3 fogL = FOGB * (0.6 + 0.5 * uFog) + GLOWC * uMoon.z * gl * 0.62;

  float dg = 1e6;
  float camH = uCam.y - GROUND;
  if (p.y < -0.0005) {
    dg = camH * uF / -p.y;
    vec2 gp = vec2(p.x * dg / uF + uCam.x, dg + uCam.z);
    float gn = fbmT(gp * 0.7);
    vec3 gc = vec3(0.0012, 0.0024, 0.002) * (0.5 + gn);
    float ff = 1.0 - exp(-dg * 0.05 * uFog);
    col = mix(gc, fogL, ff);
    float mist = fbmT(gp * vec2(0.16, 0.28) + vec2(uTime * 0.07, 0.0));
    col = mix(col, fogL * 1.3, smoothstep(0.38, 0.9, mist) * 0.5 * smoothstep(0.0, 3.0, dg));
  }

  float zs[NL] = float[NL](46.0, 35.0, 27.0, 20.5, 15.5, 11.5, 8.4, 6.1, 4.3);
  float sp[NL] = float[NL](1.7, 2.0, 2.3, 2.6, 3.0, 3.4, 3.9, 4.6, 5.6);
  for (int i = 0; i < NL; i++) {
    float z = zs[i];
    float dz = z - uCam.z;
    if (dz < 0.35 || dz > dg) continue;
    float rim;
    float cov = layer(p, z, float(i) + 1.0, sp[i], rim);
    float ff = 1.0 - exp(-dz * 0.052 * uFog);
    vec3 sil = vec3(0.0008, 0.0016, 0.0014);
    vec3 lc = mix(sil, fogL, ff);
    lc += GLOWC * rim * uMoon.z * 0.10 * (1.0 - ff) * (0.3 + gl * 2.0);
    cov *= smoothstep(0.35, 1.2, dz);
    col = mix(col, lc, cov);
    // drifting fog sheet just in front of this layer
    vec2 P = p * dz / uF + uCam.xy;
    float fn = fbmT(P * vec2(0.13, 0.30) + vec2(uTime * 0.06 + float(i) * 3.1, float(i) * 1.7));
    float hf = exp(-max(P.y - GROUND, 0.0) * 0.16);
    float fa = smoothstep(0.42, 0.92, fn) * hf * 0.32 * uFog * smoothstep(0.6, 2.5, dz);
    col = mix(col, fogL * 1.4, fa);
  }

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
  // alpha carries the light that may scatter into god rays (embers/particles add none)
  fragColor = vec4(col, luma(col));
}`;

const EMBER_VERT = /* glsl */ `
in vec3 position;
in vec4 aSeed;
uniform float uTime, uF, uTilt, uIntensity, uFocus, uAperture;
uniform vec3 uCam; uniform vec2 uRes;
out float vAlpha; out vec3 vColor; out float vR; out float vPS;
void main(){
  vec3 P = position;
  float t = uTime;
  P.y += t * (0.05 + 0.10 * aSeed.x);
  P.x += sin(t * (0.25 + aSeed.z * 0.35) + aSeed.w * 6.28) * 0.35;
  P.z += cos(t * (0.18 + aSeed.x * 0.25) + aSeed.y * 6.28) * 0.30;
  float dz = P.z - uCam.z;
  if (dz < 0.25) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); gl_PointSize = 0.0; vAlpha = 0.0; return; }
  vec2 p = (P.xy - uCam.xy) * uF / dz;
  p.y -= uTilt;
  gl_Position = vec4(p.x * 2.0 * uRes.y / uRes.x, p.y * 2.0, 0.0, 1.0);
  float sz = 0.016 * uF / dz * uRes.y;
  float coc = abs(1.0 / dz - 1.0 / uFocus) * uAperture * uRes.y;
  float r = min(max(sz, 0.9) + coc, 0.03 * uRes.y);
  vR = r;
  vPS = r * 2.0 + 4.0;
  gl_PointSize = vPS;
  float flick = 0.55 + 0.45 * sin(t * (1.7 + aSeed.w * 4.0) + aSeed.x * 40.0);
  flick *= 0.7 + 0.3 * sin(t * (5.3 + aSeed.y * 3.0) + aSeed.z * 17.0);
  vAlpha = uIntensity * flick * (max(sz, 0.9) * max(sz, 0.9)) / (r * r) * smoothstep(0.25, 1.0, dz);
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
      uRes: u(new THREE.Vector2(W, H)), uTime: u(0), uF: u(this.F), uTilt: u(0.06), uFog: u(1), uReveal: u(1),
      uClear: u(0.2), uLayerFade: u(1), uCam: u(new THREE.Vector3(0, 0, 0)),
      uMoon: u(new THREE.Vector4(0.05, 0.3, 1.0, 0.035)), uStar: u(new THREE.Vector4(0, 0.2, 0, 1)),
      uNoise: u(getNoiseTexture(renderer)),
    });

    // embers / fireflies
    const N = 170;
    const rand = rng(1934);
    const pos = new Float32Array(N * 3);
    const seed = new Float32Array(N * 4);
    for (let i = 0; i < N; i++) {
      pos[i * 3] = (rand() - 0.5) * 9;
      pos[i * 3 + 1] = -1.7 + rand() * 3.4;
      pos[i * 3 + 2] = 1.2 + Math.pow(rand(), 0.8) * 20;
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
        uTime: u(0), uF: u(this.F), uTilt: u(0.06), uIntensity: u(1), uFocus: u(9), uAperture: u(0.012),
        uCam: u(new THREE.Vector3()), uRes: u(new THREE.Vector2(W, H)),
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

  // s: { time, cam:[x,y,z], tilt, fog, reveal, clear, moon:[x,y,i,r], star:[x,y,i,size], embers, focus }
  render(target, s) {
    const U = this.pass.uniforms;
    U.uTime.value = s.time;
    U.uCam.value.set(...s.cam);
    U.uTilt.value = s.tilt;
    U.uFog.value = s.fog;
    U.uReveal.value = s.reveal;
    U.uClear.value = s.clear;
    U.uMoon.value.set(...s.moon);
    U.uStar.value.set(...s.star);
    this.pass.render(this.r, target);
    if (s.embers > 0) {
      const E = this.emberMat.uniforms;
      E.uTime.value = s.time;
      E.uCam.value.set(...s.cam);
      E.uTilt.value = s.tilt;
      E.uIntensity.value = s.embers;
      E.uFocus.value = s.focus;
      this.r.setRenderTarget(target);
      this.r.render(this.emberScene, this.camera);
    }
  }

  // project a forest-world point to p-space (y up, units of screen height)
  project(P, s) {
    const dz = P[2] - s.cam[2];
    return [((P[0] - s.cam[0]) * this.F) / dz, ((P[1] - s.cam[1]) * this.F) / dz - s.tilt];
  }
}
