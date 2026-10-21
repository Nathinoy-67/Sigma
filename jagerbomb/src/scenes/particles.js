import * as THREE from 'three';
import { rng } from '../gl.js';
import { CUE } from '../legacy.js';

// The Hubertus light bursts into ~40k botanicals that spiral together into a 3D "56"
// while the camera orbits it; then a gust carries them away. Each particle is drawn as a
// velocity-stretched streak (head at t, tail at t − trail), so the burst leaves light trails.

const VERT = /* glsl */ `
precision highp float;
in vec3 position;   // corner: x 0 = head … 1 = tail, y = side
in vec3 aTarget;
in vec3 aDir;
in vec4 aSeed;
in vec3 aColor;
uniform mat4 modelViewMatrix, projectionMatrix;
uniform float uTime, uFocus, uAperture, uDisperse, uGain, uFree, uTrail;
uniform vec2 uRes;
uniform vec3 uOrigin;
out vec3 vColor; out vec2 vLocal; out float vL; out float vR; out float vA;

float easeIO(float x){ return x < 0.5 ? 4.0*x*x*x : 1.0 - pow(-2.0*x + 2.0, 3.0) / 2.0; }
mat2 rot(float a){ float c = cos(a), s = sin(a); return mat2(c, s, -s, c); }

vec3 posAt(float t, bool free) {
  t = max(t, 0.0);
  // 1 — burst: decelerating explosion from the light
  float sp = mix(1.2, 5.6, pow(aSeed.x, 0.7));
  vec3 pb = uOrigin + aDir * sp * (1.0 - exp(-t * 2.4));
  pb.y -= 0.036 * t * t;
  pb += vec3(sin(t * 1.3 + aSeed.y * 30.0), cos(t * 1.1 + aSeed.z * 30.0), sin(t * 0.9 + aSeed.x * 30.0)) * 0.12 * min(t, 1.0);
  // 2 — gather: spiral onto the target
  float tg = 0.45 + aSeed.y * 0.95;
  float dur = 1.5 + aSeed.z * 0.7;
  float ge = easeIO(clamp((t - tg) / dur, 0.0, 1.0));
  vec3 d = pb - aTarget;
  float sw = (free ? 1.2 : 2.6) * (aSeed.x > 0.12 ? 1.0 : -1.0);
  d.xz = rot(ge * sw * 0.35) * d.xz;
  d.xy = rot(ge * sw) * d.xy;
  vec3 p = aTarget + d * (1.0 - ge);
  p += vec3(sin(aSeed.x * 40.0 + t * 2.0), sin(aSeed.y * 40.0 + t * 1.7), sin(aSeed.z * 40.0 + t * 1.3)) * 0.35 * ge * (1.0 - ge);
  // 3 — hold: a living shimmer
  p += vec3(sin(t * 2.3 + aSeed.x * 60.0), cos(t * 1.9 + aSeed.y * 60.0), sin(t * 1.4 + aSeed.z * 60.0)) * (free ? 0.08 : 0.006);
  if (free) p += vec3(0.06, 0.05, 0.0) * t;
  // 4 — disperse: a gust from the left
  float td = uDisperse + (aTarget.x + 2.5) * 0.09 + aSeed.y * 0.35;
  float u = max(t - td, 0.0);
  p += vec3(1.0, 0.18 + 0.3 * (aSeed.z - 0.5), 0.35 * (aSeed.x - 0.5)) * u * u * (3.0 + aSeed.w * 4.0);
  p += vec3(sin(u * 3.0 + aSeed.x * 20.0), cos(u * 2.6 + aSeed.y * 20.0), 0.0) * u * 0.25;
  return p;
}

void main(){
  float t = uTime;
  bool free = aSeed.w < uFree;
  vec4 c0 = projectionMatrix * modelViewMatrix * vec4(posAt(t, free), 1.0);
  vec4 c1 = projectionMatrix * modelViewMatrix * vec4(posAt(t - uTrail, free), 1.0);
  if (c0.w < 0.2 || c1.w < 0.2) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); vA = 0.0; return; }
  vec2 hr = 0.5 * uRes;
  vec2 s0 = c0.xy / c0.w * hr, s1 = c1.xy / c1.w * hr;
  float dz = c0.w;
  float focal = projectionMatrix[1][1] * hr.y; // px per unit at distance 1
  float base = mix(0.006, 0.014, aSeed.z) * (free ? 0.8 : 1.0);
  float sz = base * focal / dz;
  float coc = abs(1.0 / dz - 1.0 / uFocus) * uAperture * focal;
  float r = min(max(sz, 0.75) + coc, 0.026 * uRes.y);
  vec2 dd = s0 - s1;
  float L = min(length(dd), 0.25 * uRes.y);
  vec2 dir = L > 1e-3 ? dd / length(dd) : vec2(1.0, 0.0);
  vec2 nrm = vec2(-dir.y, dir.x);
  float ext = r + 1.5;
  float along = mix(L + ext, -ext, position.x);
  float across = position.y * ext;
  vec2 sp = s1 + dir * along + nrm * across;
  gl_Position = vec4(sp / hr, 0.0, 1.0);
  vLocal = vec2(along, across);
  vL = L; vR = r;
  float tw = 0.7 + 0.3 * sin(t * (3.0 + aSeed.w * 6.0) + aSeed.x * 50.0);
  float burstHeat = 1.0 + 3.0 * exp(-t * 3.0);
  float td = uDisperse + (aTarget.x + 2.5) * 0.09 + aSeed.y * 0.35;
  float fadeOut = 1.0 - smoothstep(0.6, 2.2, max(t - td, 0.0));
  // streaks spread the same light over a longer footprint
  float spread = (2.0 * r) / (2.0 * r + L);
  vA = uGain * tw * burstHeat * fadeOut * (max(sz, 0.75) * max(sz, 0.75)) / (r * r) * smoothstep(0.0, 0.05, t) * (free ? 0.6 : 1.0) * spread;
  vColor = aColor;
}`;

const FRAG = /* glsl */ `
precision highp float;
in vec3 vColor; in vec2 vLocal; in float vL; in float vR; in float vA;
out vec4 fragColor;
void main(){
  float a0 = vLocal.x;
  float d = length(vec2(max(max(-a0, a0 - vL), 0.0), vLocal.y));
  float a;
  if (vR < 2.2) a = exp(-d * d / max(vR * vR * 0.55, 0.35)) * 1.3;
  else {
    float disc = smoothstep(vR + 0.8, vR - 0.8, d);
    a = disc * (0.7 + 0.5 * smoothstep(vR * 0.5, vR, d));
  }
  // the head burns brightest; the trail fades out behind it
  float tail = vL > 0.5 ? mix(0.15, 1.0, clamp(a0 / vL, 0.0, 1.0)) : 1.0;
  fragColor = vec4(vColor * vA * a * tail, 0.0);
}`;

function sampleGlyphs(text, N, rand) {
  const c = document.createElement('canvas');
  c.width = 1200;
  c.height = 720;
  const g = c.getContext('2d');
  g.fillStyle = '#fff';
  g.font = '400 600px Cinzel';
  g.textAlign = 'center';
  g.textBaseline = 'alphabetic';
  g.letterSpacing = '-10px';
  g.fillText(text, 600, 600);
  const img = g.getImageData(0, 0, c.width, c.height).data;
  const pts = [];
  let minX = 1e9, maxX = -1e9, minY = 1e9, maxY = -1e9;
  for (let y = 0; y < c.height; y += 1)
    for (let x = 0; x < c.width; x += 1) {
      if (img[(y * c.width + x) * 4 + 3] > 140) {
        pts.push(x, y);
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      }
    }
  const count = pts.length / 2;
  const out = new Float32Array(N * 2);
  for (let i = 0; i < N; i++) {
    const k = Math.floor(rand() * count);
    out[i * 2] = pts[k * 2] + rand() - 0.5;
    out[i * 2 + 1] = pts[k * 2 + 1] + rand() - 0.5;
  }
  return { out, minX, maxX, minY, maxY };
}

export class ParticleScene {
  constructor(renderer, W, H) {
    this.r = renderer;
    this.W = W;
    this.H = H;
    this.camera = new THREE.PerspectiveCamera(32, W / H, 0.1, 100);
    const N = 40000;
    const FREE = 0.12;
    const rand = rng(56);
    const glyph = sampleGlyphs('56', N, rand);
    const height = 2.2;
    const cy = 0.52;
    const k = height / (glyph.maxY - glyph.minY);
    const gcx = (glyph.minX + glyph.maxX) / 2, gcy = (glyph.minY + glyph.maxY) / 2;
    const tgt = new Float32Array(N * 3);
    const dir = new Float32Array(N * 3);
    const seed = new Float32Array(N * 4);
    const col = new Float32Array(N * 3);
    const palette = [
      [0.45, [1.0, 0.6, 0.24]],
      [0.25, [1.0, 0.33, 0.07]],
      [0.12, [1.0, 0.84, 0.62]],
      [0.12, [0.38, 0.62, 0.22]],
      [0.06, [0.85, 0.12, 0.04]],
    ];
    for (let i = 0; i < N; i++) {
      for (let j = 0; j < 4; j++) seed[i * 4 + j] = rand();
      const free = seed[i * 4 + 3] < FREE;
      if (free) {
        tgt[i * 3] = (rand() - 0.5) * 11;
        tgt[i * 3 + 1] = (rand() - 0.5) * 6 + 0.4;
        tgt[i * 3 + 2] = (rand() - 0.5) * 9 + 0.5;
      } else {
        tgt[i * 3] = (glyph.out[i * 2] - gcx) * k;
        tgt[i * 3 + 1] = -(glyph.out[i * 2 + 1] - gcy) * k + cy;
        // a slab of light: dense faces, a few particles inside
        const zz = rand() < 0.7 ? (rand() < 0.5 ? -1 : 1) * (0.16 + 0.06 * rand()) : (rand() - 0.5) * 0.36;
        tgt[i * 3 + 2] = zz;
      }
      // burst direction: a flattened sphere, biased outwards in the screen plane
      let x, y, z, l;
      do {
        x = rand() * 2 - 1;
        y = rand() * 2 - 1;
        z = rand() * 2 - 1;
        l = x * x + y * y + z * z;
      } while (l > 1 || l < 0.02);
      l = Math.sqrt(l);
      dir[i * 3] = (x / l) * 1.15;
      dir[i * 3 + 1] = (y / l) * 0.9;
      dir[i * 3 + 2] = (z / l) * 0.8;
      let r = rand(), acc = 0;
      let c = palette[0][1];
      for (const [w, cc] of palette) {
        acc += w;
        if (r <= acc) {
          c = cc;
          break;
        }
      }
      const v = 0.75 + rand() * 0.5;
      col[i * 3] = c[0] * v;
      col[i * 3 + 1] = c[1] * v;
      col[i * 3 + 2] = c[2] * v;
    }
    const geo = new THREE.InstancedBufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array([0, -1, 0, 0, 1, 0, 1, -1, 0, 1, 1, 0]), 3));
    geo.setIndex([0, 2, 1, 1, 2, 3]);
    geo.setAttribute('aTarget', new THREE.InstancedBufferAttribute(tgt, 3));
    geo.setAttribute('aDir', new THREE.InstancedBufferAttribute(dir, 3));
    geo.setAttribute('aSeed', new THREE.InstancedBufferAttribute(seed, 4));
    geo.setAttribute('aColor', new THREE.InstancedBufferAttribute(col, 3));
    geo.instanceCount = N;
    const u = (v) => ({ value: v });
    this.mat = new THREE.RawShaderMaterial({
      glslVersion: THREE.GLSL3,
      vertexShader: VERT,
      fragmentShader: FRAG,
      uniforms: {
        uTime: u(0), uFocus: u(9), uAperture: u(0.025), uRes: u(new THREE.Vector2(W, H)),
        uDisperse: u(CUE.disperse - 0.3 - CUE.burst), uGain: u(0.55), uFree: u(FREE), uTrail: u(0.06),
        uOrigin: u(new THREE.Vector3()),
      },
      blending: THREE.CustomBlending,
      blendSrc: THREE.OneFactor,
      blendDst: THREE.OneFactor,
      blendEquation: THREE.AddEquation,
      depthTest: false,
      depthWrite: false,
      transparent: true,
      side: THREE.DoubleSide,
    });
    this.mesh = new THREE.Mesh(geo, this.mat);
    this.mesh.frustumCulled = false;
    this.scene = new THREE.Scene();
    this.scene.add(this.mesh);
  }

  // the camera orbits the 56 as it forms, then drifts while it holds
  setCamera(time) {
    const span = CUE.whip - CUE.burst;
    const u = Math.min(1, Math.max(0, time / span));
    // half ease-out, half linear: the orbit keeps travelling while the 56 holds
    const e = 0.5 * (1 - Math.pow(1 - u, 2.2)) + 0.5 * u;
    const ang = 0.62 - 1.1 * e;
    const rad = 9.8 - 1.9 * e;
    this.camera.position.set(Math.sin(ang) * rad, 0.35 - 0.3 * e, Math.cos(ang) * rad);
    this.camera.lookAt(0.0, 0.42, 0);
    this.camera.updateMatrixWorld();
  }

  render(target, s) {
    // place the burst origin where the Hubertus light was on screen at the burst
    this.setCamera(0);
    const ndc = new THREE.Vector3((s.origin[0] * 2 * this.H) / this.W, s.origin[1] * 2, 0.5).unproject(this.camera);
    const ro = this.camera.position.clone();
    const rd = ndc.sub(ro).normalize();
    const k = -ro.z / rd.z;
    const origin = ro.add(rd.multiplyScalar(k));
    this.setCamera(s.time);
    const U = this.mat.uniforms;
    U.uTime.value = s.time;
    U.uTrail.value = s.trail ?? 0.06;
    U.uOrigin.value.copy(origin);
    U.uFocus.value = this.camera.position.distanceTo(new THREE.Vector3(0, 0.42, 0));
    this.r.setRenderTarget(target);
    this.r.render(this.scene, this.camera);
  }
}
