import * as THREE from 'three';

// ---------------------------------------------------------------------------
// Math / easing helpers (all animation is a pure function of time)
// ---------------------------------------------------------------------------
export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a, b, t) => a + (b - a) * t;
export const remap = (t, a, b) => clamp((t - a) / (b - a));
export const smooth = (t) => t * t * (3 - 2 * t);
export const smoother = (t) => t * t * t * (t * (t * 6 - 15) + 10);
export const ease = {
  inCubic: (t) => t * t * t,
  outCubic: (t) => 1 - Math.pow(1 - t, 3),
  inOutCubic: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
  outExpo: (t) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t)),
  inExpo: (t) => (t <= 0 ? 0 : Math.pow(2, 10 * t - 10)),
  inOutExpo: (t) =>
    t <= 0 ? 0 : t >= 1 ? 1 : t < 0.5 ? Math.pow(2, 20 * t - 10) / 2 : (2 - Math.pow(2, -20 * t + 10)) / 2,
  outQuart: (t) => 1 - Math.pow(1 - t, 4),
  inOutQuart: (t) => (t < 0.5 ? 8 * t * t * t * t : 1 - Math.pow(-2 * t + 2, 4) / 2),
  inOutSine: (t) => -(Math.cos(Math.PI * t) - 1) / 2,
  outBack: (t) => {
    const c1 = 1.4, c3 = c1 + 1;
    return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
  },
};
// window: 0 before a, ramps to 1 over [a, a+fi], holds, ramps down over [b-fo, b]
export const win = (t, a, b, fi = 0.5, fo = 0.5) => Math.min(remap(t, a, a + fi), 1 - remap(t, b - fo, b));

// Deterministic PRNG
export function rng(seed = 1) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Smooth 1D noise for camera drift / handheld feel
export function noise1(x, seed = 0) {
  const h = (n) => {
    const s = Math.sin(n * 127.1 + seed * 311.7) * 43758.5453;
    return s - Math.floor(s);
  };
  const i = Math.floor(x), f = x - i;
  const u = f * f * (3 - 2 * f);
  return lerp(h(i), h(i + 1), u) * 2 - 1;
}

// ---------------------------------------------------------------------------
// GL helpers
// ---------------------------------------------------------------------------
export function makeRT(w, h, opts = {}) {
  return new THREE.WebGLRenderTarget(Math.max(1, w | 0), Math.max(1, h | 0), {
    type: THREE.HalfFloatType,
    format: THREE.RGBAFormat,
    minFilter: THREE.LinearFilter,
    magFilter: THREE.LinearFilter,
    wrapS: THREE.ClampToEdgeWrapping,
    wrapT: THREE.ClampToEdgeWrapping,
    depthBuffer: false,
    stencilBuffer: false,
    generateMipmaps: false,
    ...opts,
  });
}

const fsGeom = new THREE.BufferGeometry();
fsGeom.setAttribute('position', new THREE.BufferAttribute(new Float32Array([-1, -1, 0, 3, -1, 0, -1, 3, 0]), 3));
export const fsCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);

export const FS_VERT = /* glsl */ `
in vec3 position;
out vec2 vUv;
void main(){ vUv = position.xy * 0.5 + 0.5; gl_Position = vec4(position.xy, 0.0, 1.0); }`;

export class FSPass {
  constructor(fragmentShader, uniforms = {}, opts = {}) {
    this.uniforms = uniforms;
    this.material = new THREE.RawShaderMaterial({
      glslVersion: THREE.GLSL3,
      vertexShader: FS_VERT,
      fragmentShader: `precision highp float;\nprecision highp int;\n${fragmentShader}`,
      uniforms,
      depthTest: false,
      depthWrite: false,
      transparent: !!opts.blending,
      blending: opts.blending === 'add' ? THREE.CustomBlending : opts.blending ?? THREE.NoBlending,
      blendSrc: THREE.OneFactor,
      blendDst: THREE.OneFactor,
      blendEquation: THREE.AddEquation,
    });
    this.mesh = new THREE.Mesh(fsGeom, this.material);
    this.mesh.frustumCulled = false;
    this.scene = new THREE.Scene();
    this.scene.add(this.mesh);
  }
  render(renderer, target) {
    renderer.setRenderTarget(target);
    renderer.render(this.scene, fsCamera);
  }
}

// ---------------------------------------------------------------------------
// Shared GLSL: hashing, noise, fbm, voronoi
// ---------------------------------------------------------------------------
export const GLSL_COMMON = /* glsl */ `
#define PI 3.14159265359
#define TAU 6.28318530718
uint pcg(uint v){ uint s = v * 747796405u + 2891336453u; uint w = ((s >> ((s >> 28u) + 4u)) ^ s) * 277803737u; return (w >> 22u) ^ w; }
uvec2 cellU(vec2 p){ return uvec2(ivec2(floor(p)) + 1048576); }
float h12(vec2 p){ uvec2 q = cellU(p); return float(pcg(q.x + pcg(q.y))) * (1.0/4294967295.0); }
vec2 h22(vec2 p){ uvec2 q = cellU(p); uint a = pcg(q.x + pcg(q.y)); uint b = pcg(a ^ 0x9E3779B9u); return vec2(a, b) * (1.0/4294967295.0); }
vec4 h42(vec2 p){ uvec2 q = cellU(p); uint a = pcg(q.x + pcg(q.y)); uint b = pcg(a ^ 0x9E3779B9u); uint c = pcg(b ^ 0x85EBCA6Bu); uint d = pcg(c ^ 0xC2B2AE35u); return vec4(a, b, c, d) * (1.0/4294967295.0); }
float h13(vec3 p){ uvec3 q = uvec3(ivec3(floor(p)) + 1048576); return float(pcg(q.x + pcg(q.y + pcg(q.z)))) * (1.0/4294967295.0); }
// fast float hash for per-pixel grain/sparkle (not lattice-aligned)
float fh(vec2 p){ p = fract(p * vec2(443.897, 441.423)); p += dot(p, p.yx + 19.19); return fract((p.x + p.y) * p.x); }

float vnoise(vec2 p){
  vec2 i = floor(p), f = fract(p);
  vec2 u = f*f*f*(f*(f*6.0-15.0)+10.0);
  float a = h12(i), b = h12(i+vec2(1,0)), c = h12(i+vec2(0,1)), d = h12(i+vec2(1,1));
  return mix(mix(a,b,u.x), mix(c,d,u.x), u.y);
}
vec2 grad2(vec2 i){ float a = h12(i) * TAU; return vec2(cos(a), sin(a)); }
float gnoise(vec2 p){
  vec2 i = floor(p), f = fract(p);
  vec2 u = f*f*f*(f*(f*6.0-15.0)+10.0);
  float a = dot(grad2(i), f), b = dot(grad2(i+vec2(1,0)), f-vec2(1,0));
  float c = dot(grad2(i+vec2(0,1)), f-vec2(0,1)), d = dot(grad2(i+vec2(1,1)), f-vec2(1,1));
  return mix(mix(a,b,u.x), mix(c,d,u.x), u.y) * 1.4 * 0.5 + 0.5;
}
float vnoise3(vec3 p){
  vec3 i = floor(p), f = fract(p);
  vec3 u = f*f*(3.0-2.0*f);
  float n000 = h13(i), n100 = h13(i+vec3(1,0,0)), n010 = h13(i+vec3(0,1,0)), n110 = h13(i+vec3(1,1,0));
  float n001 = h13(i+vec3(0,0,1)), n101 = h13(i+vec3(1,0,1)), n011 = h13(i+vec3(0,1,1)), n111 = h13(i+vec3(1,1,1));
  return mix(mix(mix(n000,n100,u.x), mix(n010,n110,u.x), u.y), mix(mix(n001,n101,u.x), mix(n011,n111,u.x), u.y), u.z);
}
const mat2 ROT_OCT = mat2(1.6, 1.2, -1.2, 1.6);
float fbm(vec2 p, int oct){
  float s = 0.0, a = 0.5;
  for (int i = 0; i < 8; i++) { if (i >= oct) break; s += a * vnoise(p); p = ROT_OCT * p + 17.13; a *= 0.5; }
  return s;
}
float gfbm(vec2 p, int oct){
  float s = 0.0, a = 0.5;
  for (int i = 0; i < 8; i++) { if (i >= oct) break; s += a * gnoise(p); p = ROT_OCT * p + 17.13; a *= 0.5; }
  return s;
}
float fbm3(vec3 p, int oct){
  float s = 0.0, a = 0.5;
  for (int i = 0; i < 6; i++) { if (i >= oct) break; s += a * vnoise3(p); p = p * 2.03 + vec3(17.1, 31.7, 7.3); a *= 0.5; }
  return s;
}
// returns (F1 distance, F2 - F1 edge distance, cell id hash)
vec3 voronoi(vec2 p){
  vec2 n = floor(p), f = fract(p);
  vec2 mg, mr; float md = 8.0; vec2 mcell;
  for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++) {
    vec2 g = vec2(float(i), float(j));
    vec2 o = h22(n + g);
    vec2 r = g + o - f;
    float d = dot(r, r);
    if (d < md) { md = d; mr = r; mg = g; mcell = n + g; }
  }
  float ed = 8.0;
  for (int j = -2; j <= 2; j++) for (int i = -2; i <= 2; i++) {
    vec2 g = mg + vec2(float(i), float(j));
    vec2 o = h22(n + g);
    vec2 r = g + o - f;
    if (dot(mr - r, mr - r) > 0.00001) ed = min(ed, dot(0.5*(mr + r), normalize(r - mr)));
  }
  return vec3(sqrt(md), ed, h12(mcell + 0.5));
}
mat2 rot2(float a){ float c = cos(a), s = sin(a); return mat2(c, s, -s, c); }
float luma(vec3 c){ return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
`;

// ---------------------------------------------------------------------------
// A baked, tileable noise texture (period = 8 noise units). Sampling it replaces
// dozens of procedural noise evaluations per pixel in the soft, foggy passes.
//   r: value fbm (3 oct)   g: value fbm (4 oct)   b: gradient fbm (4 oct)   a: gradient fbm (5 oct)
const NOISE_BAKE = /* glsl */ `
${GLSL_COMMON}
in vec2 vUv; out vec4 fragColor;
float hp(vec2 i, float per){ return h12(mod(i, per)); }
float vnP(vec2 p, float per){
  vec2 i = floor(p), f = fract(p);
  vec2 u = f*f*f*(f*(f*6.0-15.0)+10.0);
  return mix(mix(hp(i, per), hp(i+vec2(1,0), per), u.x), mix(hp(i+vec2(0,1), per), hp(i+vec2(1,1), per), u.x), u.y);
}
vec2 gP(vec2 i, float per){ float a = hp(i, per) * TAU; return vec2(cos(a), sin(a)); }
float gnP(vec2 p, float per){
  vec2 i = floor(p), f = fract(p);
  vec2 u = f*f*f*(f*(f*6.0-15.0)+10.0);
  float a = dot(gP(i, per), f), b = dot(gP(i+vec2(1,0), per), f-vec2(1,0));
  float c = dot(gP(i+vec2(0,1), per), f-vec2(0,1)), d = dot(gP(i+vec2(1,1), per), f-vec2(1,1));
  return mix(mix(a,b,u.x), mix(c,d,u.x), u.y) * 1.4 * 0.5 + 0.5;
}
float fbmV(vec2 p, int oct){ float s = 0.0, a = 0.5, per = 8.0; for (int i = 0; i < 6; i++){ if (i >= oct) break; s += a * vnP(p + vec2(float(i) * 3.0, float(i) * 5.0), per); p *= 2.0; per *= 2.0; a *= 0.5; } return s; }
float fbmG(vec2 p, int oct){ float s = 0.0, a = 0.5, per = 8.0; for (int i = 0; i < 6; i++){ if (i >= oct) break; s += a * gnP(p + vec2(float(i) * 7.0, float(i) * 2.0), per); p *= 2.0; per *= 2.0; a *= 0.5; } return s; }
void main(){
  vec2 p = vUv * 8.0;
  fragColor = vec4(fbmV(p, 3), fbmV(p + 2.0, 4), fbmG(p, 4), fbmG(p + 5.0, 5));
}`;

let noiseTex = null;
export function getNoiseTexture(renderer) {
  if (noiseTex) return noiseTex;
  const rt = new THREE.WebGLRenderTarget(1024, 1024, {
    type: THREE.HalfFloatType,
    format: THREE.RGBAFormat,
    wrapS: THREE.RepeatWrapping,
    wrapT: THREE.RepeatWrapping,
    minFilter: THREE.LinearMipmapLinearFilter,
    magFilter: THREE.LinearFilter,
    generateMipmaps: true,
    depthBuffer: false,
  });
  new FSPass(NOISE_BAKE).render(renderer, rt);
  noiseTex = rt.texture;
  return noiseTex;
}
