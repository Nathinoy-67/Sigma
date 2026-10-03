import * as THREE from 'three';
import { rng } from '../gl.js';
import { CUE } from '../timeline.js';

// Act II opener: the Hubertus light bursts into ~28k botanicals that spiral
// together into a "56", then a gust of wind carries them away.

const VERT = /* glsl */ `
precision highp float;
in vec3 position;   // target
in vec3 aDir;
in vec4 aSeed;
in vec3 aColor;
uniform mat4 modelViewMatrix, projectionMatrix;
uniform float uTime, uFocus, uAperture, uRes, uDisperse, uGain, uFree;
uniform vec3 uOrigin;
out vec3 vColor; out float vR; out float vPS; out float vA;

float easeIO(float x){ return x < 0.5 ? 4.0*x*x*x : 1.0 - pow(-2.0*x + 2.0, 3.0) / 2.0; }
mat2 rot(float a){ float c = cos(a), s = sin(a); return mat2(c, s, -s, c); }

void main(){
  float t = uTime;
  bool free = aSeed.w < uFree;
  // 1 — burst: decelerating explosion from the light
  float sp = mix(1.2, 5.2, pow(aSeed.x, 0.7));
  vec3 pb = uOrigin + aDir * sp * (1.0 - exp(-t * 2.4));
  pb.y -= 0.12 * t * t * 0.3;
  pb += vec3(sin(t * 1.3 + aSeed.y * 30.0), cos(t * 1.1 + aSeed.z * 30.0), sin(t * 0.9 + aSeed.x * 30.0)) * 0.12 * min(t, 1.0);
  // 2 — gather: spiral onto the target
  float tg = 0.45 + aSeed.y * 0.95;
  float dur = 1.5 + aSeed.z * 0.7;
  float g = clamp((t - tg) / dur, 0.0, 1.0);
  float ge = easeIO(g);
  vec3 target = position;
  vec3 d = pb - target;
  float sw = (free ? 1.2 : 2.6) * (aSeed.x > 0.12 ? 1.0 : -1.0);
  d.xy = rot(ge * sw) * d.xy;
  vec3 p = target + d * (1.0 - ge);
  p += vec3(sin(aSeed.x * 40.0 + t * 2.0), sin(aSeed.y * 40.0 + t * 1.7), sin(aSeed.z * 40.0 + t * 1.3)) * 0.35 * ge * (1.0 - ge);
  // 3 — hold: a living shimmer
  p += vec3(sin(t * 2.3 + aSeed.x * 60.0), cos(t * 1.9 + aSeed.y * 60.0), sin(t * 1.4 + aSeed.z * 60.0)) * (free ? 0.08 : 0.006);
  if (free) p += vec3(0.06, 0.05, 0.0) * t;
  // 4 — disperse: a gust from the left
  float td = uDisperse + (target.x + 2.5) * 0.09 + aSeed.y * 0.35;
  float u = max(t - td, 0.0);
  p += vec3(1.0, 0.18 + 0.3 * (aSeed.z - 0.5), 0.35 * (aSeed.x - 0.5)) * u * u * (3.0 + aSeed.w * 4.0);
  p += vec3(sin(u * 3.0 + aSeed.x * 20.0), cos(u * 2.6 + aSeed.y * 20.0), 0.0) * u * 0.25;

  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;
  float dz = -mv.z;
  float focal = projectionMatrix[1][1] * 0.5 * uRes; // px per unit at distance 1
  float base = mix(0.006, 0.014, aSeed.z) * (free ? 0.8 : 1.0);
  float sz = base * focal / dz;
  float coc = abs(1.0 / dz - 1.0 / uFocus) * uAperture * focal;
  float r = min(max(sz, 0.75) + coc, 0.026 * uRes);
  vR = r; vPS = r * 2.0 + 3.0;
  gl_PointSize = vPS;
  float tw = 0.7 + 0.3 * sin(t * (3.0 + aSeed.w * 6.0) + aSeed.x * 50.0);
  float burstHeat = 1.0 + 3.0 * exp(-t * 3.0);
  float fadeOut = 1.0 - smoothstep(0.6, 2.2, u);
  vA = uGain * tw * burstHeat * fadeOut * (max(sz, 0.75) * max(sz, 0.75)) / (r * r) * smoothstep(0.0, 0.05, t) * (free ? 0.6 : 1.0);
  vColor = aColor;
}`;

const FRAG = /* glsl */ `
precision highp float;
in vec3 vColor; in float vR; in float vPS; in float vA;
out vec4 fragColor;
void main(){
  vec2 c = (gl_PointCoord - 0.5) * vPS;
  float r = length(c);
  float a;
  if (vR < 2.2) a = exp(-r * r / max(vR * vR * 0.55, 0.35)) * 1.3;
  else {
    float disc = smoothstep(vR + 0.8, vR - 0.8, r);
    a = disc * (0.7 + 0.5 * smoothstep(vR * 0.5, vR, r));
  }
  fragColor = vec4(vColor * vA * a, 0.0);
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
    const N = 28000;
    const FREE = 0.12;
    const rand = rng(56);
    const glyph = sampleGlyphs('56', N, rand);
    const height = 2.2;
    const cy = 0.52;
    const k = height / (glyph.maxY - glyph.minY);
    const gcx = (glyph.minX + glyph.maxX) / 2, gcy = (glyph.minY + glyph.maxY) / 2;
    const pos = new Float32Array(N * 3);
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
        pos[i * 3] = (rand() - 0.5) * 11;
        pos[i * 3 + 1] = (rand() - 0.5) * 6 + 0.4;
        pos[i * 3 + 2] = (rand() - 0.5) * 9 + 0.5;
      } else {
        pos[i * 3] = (glyph.out[i * 2] - gcx) * k;
        pos[i * 3 + 1] = -(glyph.out[i * 2 + 1] - gcy) * k + cy;
        pos[i * 3 + 2] = (rand() - 0.5) * 0.14;
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
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setAttribute('aDir', new THREE.BufferAttribute(dir, 3));
    geo.setAttribute('aSeed', new THREE.BufferAttribute(seed, 4));
    geo.setAttribute('aColor', new THREE.BufferAttribute(col, 3));
    const u = (v) => ({ value: v });
    this.mat = new THREE.RawShaderMaterial({
      glslVersion: THREE.GLSL3,
      vertexShader: VERT,
      fragmentShader: FRAG,
      uniforms: {
        uTime: u(0), uFocus: u(9), uAperture: u(0.04), uRes: u(H), uDisperse: u(CUE.disperse - 0.3 - CUE.burst),
        uGain: u(0.55), uFree: u(FREE), uOrigin: u(new THREE.Vector3()),
      },
      blending: THREE.CustomBlending,
      blendSrc: THREE.OneFactor,
      blendDst: THREE.OneFactor,
      blendEquation: THREE.AddEquation,
      depthTest: false,
      depthWrite: false,
      transparent: true,
    });
    this.points = new THREE.Points(geo, this.mat);
    this.points.frustumCulled = false;
    this.scene = new THREE.Scene();
    this.scene.add(this.points);
  }

  setCamera(time) {
    const u = Math.min(1, Math.max(0, time / 7.2));
    const e = u * u * (3 - 2 * u);
    this.camera.position.set(0.7 - 1.2 * e, 0.1 - 0.12 * e, 9.6 - 1.1 * e);
    this.camera.lookAt(0, 0.38, 0);
    this.camera.updateMatrixWorld();
  }

  render(target, s) {
    this.setCamera(s.time);
    // place the burst origin where the Hubertus light was on screen (at the burst moment)
    const cam0 = this.camera.clone();
    this.setCamera(0);
    const ndc = new THREE.Vector3((s.origin[0] * 2 * this.H) / this.W, s.origin[1] * 2, 0.5).unproject(this.camera);
    const ro = this.camera.position.clone();
    const rd = ndc.sub(ro).normalize();
    const k = -ro.z / rd.z;
    const origin = ro.add(rd.multiplyScalar(k));
    this.camera.copy(cam0);
    this.setCamera(s.time);
    const U = this.mat.uniforms;
    U.uTime.value = s.time;
    U.uOrigin.value.copy(origin);
    U.uFocus.value = this.camera.position.length();
    this.r.setRenderTarget(target);
    this.r.render(this.scene, this.camera);
  }
}
