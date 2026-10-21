import * as THREE from 'three';
import { FSPass, rng } from '../gl.js';

// The frozen frame cracks from an impact point and explodes towards the camera as 3D
// shards of ice, revealing the next scene behind. The fracture is a Voronoi diagram
// whose shared edges are made jagged (identically for both neighbours), each shard is
// textured with the frozen image and lit like ice once it tumbles.

export const IMPACT = [0.0, 0.03]; // p-space (y up, units of screen height)

// clip a tagged polygon by the half-plane closer to si than sj (tag j on the new edge)
function clip(poly, si, sj, j) {
  const nx = sj[0] - si[0], ny = sj[1] - si[1];
  const mx = (si[0] + sj[0]) / 2, my = (si[1] + sj[1]) / 2;
  const side = (p) => (p[0] - mx) * nx + (p[1] - my) * ny; // <= 0 inside
  const out = [];
  const n = poly.length;
  for (let k = 0; k < n; k++) {
    const a = poly[k], b = poly[(k + 1) % n];
    const da = side(a.p), db = side(b.p);
    if (da <= 0) out.push({ p: a.p, tag: a.tag });
    if ((da <= 0) !== (db <= 0)) {
      const t = da / (da - db);
      const p = [a.p[0] + (b.p[0] - a.p[0]) * t, a.p[1] + (b.p[1] - a.p[1]) * t];
      out.push({ p, tag: da <= 0 ? j : a.tag });
    }
  }
  return out;
}

function hash2(a, b) {
  let h = (Math.imul(a, 73856093) ^ Math.imul(b, 19349663)) >>> 0;
  return rng(h || 1);
}

function buildFracture(aspect) {
  const rand = rng(1801);
  const N = 150;
  const seeds = [];
  for (let i = 0; i < N; i++) {
    const r = 0.012 + 1.2 * Math.pow(rand(), 1.85);
    const a = rand() * Math.PI * 2;
    seeds.push([IMPACT[0] + Math.cos(a) * r * 1.2, IMPACT[1] + Math.sin(a) * r]);
  }
  const X = aspect / 2 + 0.02, Y = 0.52;
  const cells = seeds.map((si, i) => {
    let poly = [[-X, -Y], [X, -Y], [X, Y], [-X, Y]].map((p) => ({ p, tag: -1 }));
    for (let j = 0; j < N; j++) if (j !== i && poly.length) poly = clip(poly, si, seeds[j], j);
    return poly;
  });
  // jagged shared edges: canonical orientation per neighbour pair, so both cells agree
  const out = [];
  cells.forEach((poly, i) => {
    if (poly.length < 3) return;
    const pts = [];
    for (let k = 0; k < poly.length; k++) {
      const a = poly[k].p, b = poly[(k + 1) % poly.length].p, j = poly[k].tag;
      pts.push(a);
      if (j < 0) continue;
      const lo = Math.min(i, j), hi = Math.max(i, j);
      const dx = seeds[hi][0] - seeds[lo][0], dy = seeds[hi][1] - seeds[lo][1];
      const fwd = (b[0] - a[0]) * -dy + (b[1] - a[1]) * dx >= 0;
      const A = fwd ? a : b, B = fwd ? b : a;
      const len = Math.hypot(B[0] - A[0], B[1] - A[1]);
      if (len < 1e-4) continue;
      const m = Math.max(1, Math.min(9, Math.round(len / 0.022)));
      const r = hash2(lo + 1, hi + 1);
      const amp = Math.min(0.0075, 0.14 * len) * (0.6 + 0.8 * r());
      const nx = -(B[1] - A[1]) / len, ny = (B[0] - A[0]) / len;
      const mid = [];
      for (let q = 1; q < m; q++) {
        const s = (q + (r() - 0.5) * 0.6) / m;
        const o = (r() - 0.5) * 2 * amp;
        mid.push([A[0] + (B[0] - A[0]) * s + nx * o, A[1] + (B[1] - A[1]) * s + ny * o]);
      }
      if (!fwd) mid.reverse();
      pts.push(...mid);
    }
    // area centroid
    let ar = 0, cx = 0, cy = 0;
    for (let k = 0; k < pts.length; k++) {
      const p = pts[k], q = pts[(k + 1) % pts.length];
      const c = p[0] * q[1] - q[0] * p[1];
      ar += c;
      cx += (p[0] + q[0]) * c;
      cy += (p[1] + q[1]) * c;
    }
    if (Math.abs(ar) < 1e-7) return;
    out.push({ pts, c: [cx / (3 * ar), cy / (3 * ar)] });
  });
  return out;
}

const VERT = /* glsl */ `
precision highp float;
in vec3 position;   // original p-space position of this vertex
in vec3 aCenter;    // shard centroid xy, distance from the impact
in vec4 aMotion;    // velocity xyz, launch delay
in vec4 aSpin;      // axis xyz, angular speed
in float aEdge;     // 1 at the centroid, 0 on the rim
uniform mat4 projectionMatrix;
uniform float uU, uD, uAspect;
out vec2 vUV; out float vEdge; out vec3 vN; out vec3 vP; out float vLaunch; out float vDist; out vec2 vOrig;
mat3 rotAxis(vec3 a, float ang){
  float c = cos(ang), s = sin(ang), t = 1.0 - c;
  return mat3(t*a.x*a.x + c, t*a.x*a.y + s*a.z, t*a.x*a.z - s*a.y,
              t*a.x*a.y - s*a.z, t*a.y*a.y + c, t*a.y*a.z + s*a.x,
              t*a.x*a.z + s*a.y, t*a.y*a.z - s*a.x, t*a.z*a.z + c);
}
void main(){
  float u = max(uU - aMotion.w, 0.0);
  // ease the launch in over a few frames so the cracks visibly open first
  float uu = u * smoothstep(0.0, 0.12, u);
  mat3 R = rotAxis(aSpin.xyz, aSpin.w * uu * (1.0 - 0.25 * min(uu, 1.0)));
  vec3 local = vec3(position.xy - aCenter.xy, 0.0);
  vec3 P = R * local + vec3(aCenter.xy, -uD) + aMotion.xyz * uu + vec3(0.0, -0.55 * uu * uu, 0.0);
  gl_Position = projectionMatrix * vec4(P, 1.0);
  vUV = vec2(position.x / uAspect + 0.5, position.y + 0.5);
  vEdge = aEdge;
  vN = R * vec3(0.0, 0.0, 1.0);
  vP = P;
  vLaunch = u;
  vDist = aCenter.z;
  vOrig = position.xy;
}`;

const FRAG = /* glsl */ `
precision highp float;
uniform sampler2D uImg;
uniform float uCrack, uU, uPx;
uniform vec2 uImpact;
in vec2 vUV; in float vEdge; in vec3 vN; in vec3 vP; in float vLaunch; in float vDist; in vec2 vOrig;
out vec4 fragColor;
void main(){
  vec3 base = texture(uImg, vUV).rgb;
  float e = vEdge / max(fwidth(vEdge), 1e-6) * uPx; // distance from the rim, in 720p pixels
  // the crack front races out from the impact
  float R = pow(uCrack, 0.85) * 1.35;
  float od = length(vOrig - uImpact);
  float front = smoothstep(R, R - 0.06, od);
  float fly = smoothstep(0.0, 0.3, vLaunch);
  vec3 V = normalize(-vP);
  vec3 N = normalize(vN);
  if (dot(N, V) < 0.0) N = -N;
  vec3 Lk = normalize(vec3(-0.45, 0.55, 0.7));
  vec3 Lb = normalize(vec3(0.25, 0.35, -1.0));
  float spec = pow(max(dot(N, normalize(Lk + V)), 0.0), 70.0);
  float back = pow(max(dot(-N, Lb), 0.0), 6.0);
  float fres = pow(1.0 - max(dot(N, V), 0.0), 3.0);
  // frozen picture → clear, glinting ice as the shard tumbles
  vec3 col = mix(base, base * 0.4 + vec3(0.01, 0.018, 0.026), fly * 0.7);
  col += vec3(0.85, 0.95, 1.0) * (spec * 7.0 + fres * 0.3) * fly;
  // hairline cracks (brightest near the impact) that become the shards' bevels
  float line = exp(-e * e * 1.1) + exp(-e * 0.7) * 0.18;
  float bevel = exp(-e * 0.45);
  float core = 1.0 - 0.55 * smoothstep(0.05, 0.9, od);
  col += vec3(0.82, 0.94, 1.0) * line * front * (1.4 + 2.6 * uCrack) * core * (1.0 - fly);
  col += vec3(0.82, 0.94, 1.0) * bevel * fly * (0.22 + 3.0 * spec);
  // the warm backlight only catches the bevels (a flat fill reads as cardboard)
  col += vec3(1.0, 0.62, 0.3) * back * (0.12 + 1.4 * bevel) * fly;
  float near = smoothstep(0.12, 0.45, -vP.z);
  float alpha = mix(1.0, 0.45, fly) * near * (1.0 - smoothstep(1.25, 1.9, vLaunch));
  fragColor = vec4(col * alpha, alpha);
}`;

export class ShardScene {
  constructor(renderer, W, H) {
    this.r = renderer;
    this.W = W;
    this.H = H;
    const aspect = W / H;
    const fov = 40;
    this.D = 0.5 / Math.tan(((fov / 2) * Math.PI) / 180);
    this.camera = new THREE.PerspectiveCamera(fov, aspect, 0.02, 20);
    this.camera.position.set(0, 0, 0);
    this.camera.lookAt(0, 0, -1);
    this.camera.updateMatrixWorld();
    this.camera.updateProjectionMatrix();

    const shards = buildFracture(aspect);
    const rand = rng(77);
    const pos = [], center = [], motion = [], spin = [], edge = [];
    this.shards = [];
    let v = 0;
    for (const s of shards) {
      const dist = Math.hypot(s.c[0] - IMPACT[0], s.c[1] - IMPACT[1]);
      const o = [s.c[0] - IMPACT[0], s.c[1] - IMPACT[1]];
      const ol = Math.hypot(o[0], o[1]) || 1;
      const near = Math.exp(-dist * 2.6);
      const vz = (0.55 + 1.5 * rand()) * (1.0 + 1.6 * near);
      const vo = (0.12 + 0.42 * rand()) * (1.0 + 0.9 * near);
      const mo = [(o[0] / ol) * vo, (o[1] / ol) * vo + 0.08, vz, dist * 0.2];
      let ax = [rand() - 0.5, rand() - 0.5, rand() - 0.5];
      const al = Math.hypot(...ax) || 1;
      ax = ax.map((x) => x / al);
      const sp = [...ax, (2.0 + 6.0 * rand()) * (rand() < 0.5 ? -1 : 1)];
      const base = v;
      const push = (p, e) => {
        pos.push(p[0], p[1], 0);
        center.push(s.c[0], s.c[1], dist);
        motion.push(...mo);
        spin.push(...sp);
        edge.push(e);
        v++;
      };
      push(s.c, 1);
      for (const p of s.pts) push(p, 0);
      const idx = [];
      const n = s.pts.length;
      for (let k = 0; k < n; k++) idx.push(base, base + 1 + k, base + 1 + ((k + 1) % n));
      this.shards.push({ idx, vz, delay: mo[3] });
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    geo.setAttribute('aCenter', new THREE.Float32BufferAttribute(center, 3));
    geo.setAttribute('aMotion', new THREE.Float32BufferAttribute(motion, 4));
    geo.setAttribute('aSpin', new THREE.Float32BufferAttribute(spin, 4));
    geo.setAttribute('aEdge', new THREE.Float32BufferAttribute(edge, 1));
    const total = this.shards.reduce((a, s) => a + s.idx.length, 0);
    this.index = new THREE.BufferAttribute(new Uint32Array(total), 1);
    this.index.setUsage(THREE.DynamicDrawUsage);
    geo.setIndex(this.index);
    const u = (x) => ({ value: x });
    this.mat = new THREE.RawShaderMaterial({
      glslVersion: THREE.GLSL3,
      vertexShader: VERT,
      fragmentShader: FRAG,
      uniforms: {
        uImg: u(null), uU: u(0), uD: u(this.D), uAspect: u(aspect), uCrack: u(0), uPx: u(720 / H),
        uImpact: u(new THREE.Vector2(...IMPACT)),
      },
      side: THREE.DoubleSide,
      depthTest: false,
      depthWrite: false,
      transparent: true,
      blending: THREE.CustomBlending,
      blendEquation: THREE.AddEquation,
      blendSrc: THREE.OneFactor,
      blendDst: THREE.OneMinusSrcAlphaFactor,
      blendSrcAlpha: THREE.ZeroFactor,
      blendDstAlpha: THREE.OneMinusSrcAlphaFactor,
    });
    this.mesh = new THREE.Mesh(geo, this.mat);
    this.mesh.frustumCulled = false;
    this.scene = new THREE.Scene();
    this.scene.add(this.mesh);
    this.copy = new FSPass(
      `uniform sampler2D uImg; in vec2 vUv; out vec4 fragColor; void main(){ fragColor = vec4(texture(uImg, vUv).rgb, 0.0); }`,
      { uImg: u(null) },
    );
  }

  // s: { image (texture of the frozen frame), u (seconds since the shatter, ≤ 0 before), crack (0..1) }
  render(target, s) {
    if (s.u <= 0.02) {
      // the intact sheet: lay the picture down underneath so no seam can show through
      this.copy.uniforms.uImg.value = s.image;
      this.copy.render(this.r, target);
    }
    // draw far shards first
    const order = this.shards
      .map((sh, i) => [sh.vz * Math.max(0, s.u - sh.delay), i])
      .sort((a, b) => a[0] - b[0]);
    const arr = this.index.array;
    let o = 0;
    for (const [, i] of order) for (const x of this.shards[i].idx) arr[o++] = x;
    this.index.needsUpdate = true;
    const U = this.mat.uniforms;
    U.uImg.value = s.image;
    U.uU.value = s.u;
    U.uCrack.value = s.crack;
    this.r.setRenderTarget(target);
    this.r.render(this.scene, this.camera);
  }
}
