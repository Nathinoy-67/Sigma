import * as THREE from 'three';
import { FSPass, makeRT, GLSL_COMMON } from './gl.js';

// HDR post chain: composite (scene + god rays + typography) → bloom mip chain →
// anamorphic streaks → filmic tonemap, grade, grain, letterbox.

const COMPOSITE = /* glsl */ `
uniform sampler2D uScene, uText, uGlow, uRays;
uniform float uTextGain, uGlowGain, uRaysStrength, uWhip;
uniform vec3 uRaysTint;
uniform vec2 uShake;
in vec2 vUv; out vec4 fragColor;
vec3 toLin(vec3 c){ return pow(max(c, 0.0), vec3(2.2)); }
void main(){
  vec2 uv = vUv + uShake;
  vec3 col;
  if (abs(uWhip) > 0.0005) {
    vec3 s = vec3(0.0); float ws = 0.0;
    for (int i = 0; i < 32; i++) {
      float f = float(i) / 31.0 - 0.5;
      float w = 1.0 - abs(f) * 1.4;
      s += texture(uScene, uv + vec2(f * uWhip, 0.0)).rgb * w; ws += w;
    }
    col = s / ws;
  } else col = texture(uScene, uv).rgb;
  col += texture(uRays, uv).rgb * uRaysTint * uRaysStrength;
  vec4 g = texture(uGlow, vUv);
  col += toLin(g.rgb) * uGlowGain;
  vec4 tx = texture(uText, vUv);
  col = col * (1.0 - tx.a) + toLin(tx.rgb) * uTextGain;
  fragColor = vec4(col, 1.0);
}`;

const RAYS = /* glsl */ `
${GLSL_COMMON}
uniform sampler2D uScene;
uniform vec2 uLightPos; uniform float uDensity, uDecay, uWeight, uThreshold;
in vec2 vUv; out vec4 fragColor;
void main(){
  vec2 delta = (vUv - uLightPos) * (uDensity / 56.0);
  vec2 c = vUv - delta * fh(gl_FragCoord.xy);
  float illum = 1.0; vec3 acc = vec3(0.0);
  for (int i = 0; i < 56; i++) {
    c -= delta;
    float s = max(texture(uScene, c).a - uThreshold, 0.0);
    acc += vec3(s) * illum; illum *= uDecay;
  }
  fragColor = vec4(acc * uWeight / 56.0, 1.0);
}`;

const DOWN13 = /* glsl */ `
uniform sampler2D uTex; uniform vec2 uTexel; uniform float uPrefilter; uniform float uThreshold, uKnee;
in vec2 vUv; out vec4 fragColor;
vec3 S(vec2 o){ return texture(uTex, vUv + o * uTexel).rgb; }
float lum(vec3 c){ return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
vec3 karis(vec3 a, vec3 b, vec3 c, vec3 d){
  float wa = 1.0/(1.0+lum(a)), wb = 1.0/(1.0+lum(b)), wc = 1.0/(1.0+lum(c)), wd = 1.0/(1.0+lum(d));
  return (a*wa + b*wb + c*wc + d*wd) / (wa+wb+wc+wd);
}
void main(){
  vec3 a = S(vec2(-2, 2)), b = S(vec2(0, 2)), c = S(vec2(2, 2));
  vec3 d = S(vec2(-2, 0)), e = S(vec2(0, 0)), f = S(vec2(2, 0));
  vec3 g = S(vec2(-2,-2)), h = S(vec2(0,-2)), i = S(vec2(2,-2));
  vec3 j = S(vec2(-1, 1)), k = S(vec2(1, 1)), l = S(vec2(-1,-1)), m = S(vec2(1,-1));
  vec3 col;
  if (uPrefilter > 0.5) {
    col = karis(j,k,l,m) * 0.5 + karis(a,b,d,e) * 0.125 + karis(b,c,e,f) * 0.125 + karis(d,e,g,h) * 0.125 + karis(e,f,h,i) * 0.125;
    float br = max(col.r, max(col.g, col.b));
    float rq = clamp(br - uThreshold + uKnee, 0.0, 2.0 * uKnee);
    rq = rq * rq / (4.0 * uKnee + 1e-5);
    col *= max(rq, br - uThreshold) / max(br, 1e-5);
  } else {
    col = e*0.125 + (a+c+g+i)*0.03125 + (b+d+f+h)*0.0625 + (j+k+l+m)*0.125;
  }
  fragColor = vec4(min(col, vec3(4000.0)), 1.0);
}`;

const UP_TENT = /* glsl */ `
uniform sampler2D uLow, uHigh; uniform vec2 uTexel; uniform float uRadius;
in vec2 vUv; out vec4 fragColor;
void main(){
  vec4 d = uTexel.xyxy * vec4(1, 1, -1, 0) * uRadius;
  vec3 s = texture(uLow, vUv - d.xy).rgb;
  s += texture(uLow, vUv - d.wy).rgb * 2.0;
  s += texture(uLow, vUv - d.zy).rgb;
  s += texture(uLow, vUv + d.zw).rgb * 2.0;
  s += texture(uLow, vUv).rgb * 4.0;
  s += texture(uLow, vUv + d.xw).rgb * 2.0;
  s += texture(uLow, vUv + d.zy).rgb;
  s += texture(uLow, vUv + d.wy).rgb * 2.0;
  s += texture(uLow, vUv + d.xy).rgb;
  fragColor = vec4(texture(uHigh, vUv).rgb + s / 16.0, 1.0);
}`;

const STREAK_PRE = /* glsl */ `
uniform sampler2D uTex; uniform float uThreshold; uniform vec2 uTexel;
in vec2 vUv; out vec4 fragColor;
void main(){
  vec3 c = texture(uTex, vUv).rgb * 0.5 + texture(uTex, vUv + vec2(0.0, uTexel.y)).rgb * 0.25 + texture(uTex, vUv - vec2(0.0, uTexel.y)).rgb * 0.25;
  float br = max(c.r, max(c.g, c.b));
  c *= max(br - uThreshold, 0.0) / max(br, 1e-4);
  fragColor = vec4(c, 1.0);
}`;

const STREAK_BLUR = /* glsl */ `
uniform sampler2D uTex; uniform vec2 uTexel; uniform float uStep;
in vec2 vUv; out vec4 fragColor;
void main(){
  vec3 s = vec3(0.0); float ws = 0.0;
  for (int i = -7; i <= 7; i++) {
    float x = float(i);
    float w = exp(-x * x / 18.0);
    s += texture(uTex, vUv + vec2(x * uStep * uTexel.x, 0.0)).rgb * w; ws += w;
  }
  fragColor = vec4(s / ws, 1.0);
}`;

const FINAL = /* glsl */ `
${GLSL_COMMON}
uniform sampler2D uComp, uBloom, uS1, uS2, uS3, uS4;
uniform vec2 uRes;
uniform float uExposure, uBloomStrength, uStreakStrength, uCA, uVignette, uGrain, uFrame;
uniform float uLetterbox, uFade, uSat, uContrast, uFlashAmt;
uniform vec3 uStreakTint, uFlash, uSlope, uOffset, uPower, uShadowTint, uHighTint;
in vec2 vUv; out vec4 fragColor;

const mat3 ACESIn = mat3(vec3(0.59719, 0.07600, 0.02840), vec3(0.35458, 0.90834, 0.13383), vec3(0.04823, 0.01566, 0.83777));
const mat3 ACESOut = mat3(vec3(1.60475, -0.10208, -0.00327), vec3(-0.53108, 1.10813, -0.07276), vec3(-0.07367, -0.00605, 1.07602));
vec3 rrt(vec3 v){ vec3 a = v * (v + 0.0245786) - 0.000090537; vec3 b = v * (0.983729 * v + 0.4329510) + 0.238081; return a / b; }
vec3 aces(vec3 c){ c = ACESIn * (c / 0.6); c = rrt(c); c = ACESOut * c; return clamp(c, 0.0, 1.0); }

void main(){
  vec2 uv = vUv;
  vec2 d = uv - 0.5;
  vec2 off = d * dot(d, d) * uCA;
  vec3 col;
  col.r = texture(uComp, uv - off).r;
  col.g = texture(uComp, uv - off * 0.35).g;
  col.b = texture(uComp, uv + off * 0.6).b;
  vec3 bloom = texture(uBloom, uv).rgb;
  vec3 streak = texture(uS1, uv).rgb * 0.40 + texture(uS2, uv).rgb * 0.30 + texture(uS3, uv).rgb * 0.20 + texture(uS4, uv).rgb * 0.10;
  col += bloom * uBloomStrength + streak * uStreakTint * uStreakStrength;
  col *= uExposure;
  float vr = length(d * vec2(uRes.x / uRes.y, 1.0));
  col *= 1.0 - uVignette * smoothstep(0.25, 1.05, vr);
  col = aces(col);
  col = pow(col, vec3(1.0 / 2.2));
  // ASC-CDL style grade + split toning
  col = pow(max(col * uSlope + uOffset, 0.0), uPower);
  float l = luma(col);
  col += uShadowTint * (1.0 - smoothstep(0.0, 0.45, l)) + uHighTint * smoothstep(0.45, 1.0, l);
  col = (col - 0.5) * uContrast + 0.5;
  l = luma(col);
  col = mix(vec3(l), col, uSat);
  col = mix(col, uFlash, uFlashAmt);
  // soft film grain, strongest in the mid-tones
  vec2 gp = gl_FragCoord.xy * 0.72 + vec2(uFrame * 37.13, uFrame * 91.71);
  float gr = vnoise(gp) + vnoise(gp * 1.9 + 7.7) * 0.5 - 0.75;
  float lw = 4.0 * l * (1.0 - l) * 0.75 + 0.25;
  col += gr * uGrain * lw;
  col += (fh(gl_FragCoord.xy + uFrame * 1.618) - 0.5) / 255.0;
  float y = gl_FragCoord.y / uRes.y;
  float bar = step(y, uLetterbox) + step(1.0 - uLetterbox, y);
  col *= 1.0 - clamp(bar, 0.0, 1.0);
  col *= 1.0 - uFade;
  fragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}`;

export const DEFAULT_POST = () => ({
  exposure: 1.0,
  bloom: 0.12,
  bloomThreshold: 1.0,
  bloomKnee: 0.6,
  streak: 0.0,
  streakThreshold: 1.6,
  streakTint: [1.0, 0.62, 0.3],
  rays: 0.0,
  raysPos: [0.5, 0.8],
  raysDecay: 0.965,
  raysDensity: 0.9,
  raysThreshold: 0.25,
  raysTint: [1, 1, 1],
  textGain: 1.0,
  glowGain: 1.0,
  ca: 0.0,
  vignette: 0.55,
  grain: 0.045,
  whip: 0.0,
  shake: [0, 0],
  flash: [1, 1, 1],
  flashAmt: 0.0,
  letterbox: 0.128,
  fade: 0.0,
  sat: 1.0,
  contrast: 1.04,
  slope: [1, 1, 1],
  offset: [0, 0, 0],
  power: [1, 1, 1],
  shadowTint: [-0.006, 0.006, 0.002],
  highTint: [0.012, 0.004, -0.012],
});

export class Post {
  constructor(renderer, W, H) {
    this.r = renderer;
    this.W = W;
    this.H = H;
    this.comp = makeRT(W, H);
    this.rays = makeRT(W / 2, H / 2);
    this.down = [];
    this.up = [];
    let w = W / 2, h = H / 2;
    for (let i = 0; i < 6; i++) {
      this.down.push(makeRT(w, h));
      this.up.push(makeRT(w, h));
      w = Math.max(2, Math.floor(w / 2));
      h = Math.max(2, Math.floor(h / 2));
    }
    const sw = W / 4, sh = H / 8;
    this.s = [0, 1, 2, 3, 4].map(() => makeRT(sw, sh));

    const u = (v) => ({ value: v });
    this.pComp = new FSPass(COMPOSITE, {
      uScene: u(null), uText: u(null), uGlow: u(null), uRays: u(null),
      uTextGain: u(1), uGlowGain: u(1), uRaysStrength: u(0), uWhip: u(0),
      uRaysTint: u(new THREE.Vector3(1, 1, 1)), uShake: u(new THREE.Vector2()),
    });
    this.pRays = new FSPass(RAYS, {
      uScene: u(null), uLightPos: u(new THREE.Vector2(0.5, 0.5)), uDensity: u(0.9), uDecay: u(0.96), uWeight: u(1), uThreshold: u(0.3),
    });
    this.pDown = new FSPass(DOWN13, { uTex: u(null), uTexel: u(new THREE.Vector2()), uPrefilter: u(0), uThreshold: u(1), uKnee: u(0.5) });
    this.pUp = new FSPass(UP_TENT, { uLow: u(null), uHigh: u(null), uTexel: u(new THREE.Vector2()), uRadius: u(1) });
    this.pSPre = new FSPass(STREAK_PRE, { uTex: u(null), uThreshold: u(2), uTexel: u(new THREE.Vector2()) });
    this.pSBlur = new FSPass(STREAK_BLUR, { uTex: u(null), uTexel: u(new THREE.Vector2()), uStep: u(1) });
    this.pFinal = new FSPass(FINAL, {
      uComp: u(null), uBloom: u(null), uS1: u(null), uS2: u(null), uS3: u(null), uS4: u(null),
      uRes: u(new THREE.Vector2(W, H)),
      uExposure: u(1), uBloomStrength: u(0.1), uStreakStrength: u(0), uCA: u(0), uVignette: u(0.5), uGrain: u(0.04), uFrame: u(0),
      uLetterbox: u(0), uFade: u(0), uSat: u(1), uContrast: u(1), uFlashAmt: u(0),
      uStreakTint: u(new THREE.Vector3()), uFlash: u(new THREE.Vector3()), uSlope: u(new THREE.Vector3(1, 1, 1)),
      uOffset: u(new THREE.Vector3()), uPower: u(new THREE.Vector3(1, 1, 1)), uShadowTint: u(new THREE.Vector3()), uHighTint: u(new THREE.Vector3()),
    });
    this.black = new THREE.DataTexture(new Uint8Array([0, 0, 0, 0]), 1, 1);
    this.black.needsUpdate = true;
  }

  render(sceneTex, textTex, glowTex, P, frame) {
    const r = this.r;
    const v3 = (dst, a) => dst.set(a[0], a[1], a[2]);

    // god rays from the raw scene
    if (P.rays > 0) {
      const U = this.pRays.uniforms;
      U.uScene.value = sceneTex;
      U.uLightPos.value.set(P.raysPos[0], P.raysPos[1]);
      U.uDensity.value = P.raysDensity;
      U.uDecay.value = P.raysDecay;
      U.uWeight.value = 1.0;
      U.uThreshold.value = P.raysThreshold;
      this.pRays.render(r, this.rays);
    }

    // composite
    {
      const U = this.pComp.uniforms;
      U.uScene.value = sceneTex;
      U.uText.value = textTex || this.black;
      U.uGlow.value = glowTex || this.black;
      U.uRays.value = P.rays > 0 ? this.rays.texture : this.black;
      U.uRaysStrength.value = P.rays;
      v3(U.uRaysTint.value, P.raysTint);
      U.uTextGain.value = P.textGain;
      U.uGlowGain.value = P.glowGain;
      U.uWhip.value = P.whip;
      U.uShake.value.set(P.shake[0], P.shake[1]);
      this.pComp.render(r, this.comp);
    }

    // bloom: prefilter + 13-tap downsample chain, tent upsample chain
    {
      const U = this.pDown.uniforms;
      let src = this.comp;
      for (let i = 0; i < this.down.length; i++) {
        U.uTex.value = src.texture;
        U.uTexel.value.set(1 / src.width, 1 / src.height);
        U.uPrefilter.value = i === 0 ? 1 : 0;
        U.uThreshold.value = P.bloomThreshold;
        U.uKnee.value = P.bloomKnee;
        this.pDown.render(r, this.down[i]);
        src = this.down[i];
      }
      const UU = this.pUp.uniforms;
      const n = this.down.length;
      let low = this.down[n - 1];
      for (let i = n - 2; i >= 0; i--) {
        UU.uLow.value = low.texture;
        UU.uHigh.value = this.down[i].texture;
        UU.uTexel.value.set(1 / low.width, 1 / low.height);
        UU.uRadius.value = 1.0;
        this.pUp.render(r, this.up[i]);
        low = this.up[i];
      }
    }

    // anamorphic streaks from the quarter-res bloom level
    if (P.streak > 0) {
      const U = this.pSPre.uniforms;
      U.uTex.value = this.down[1].texture;
      U.uThreshold.value = P.streakThreshold;
      U.uTexel.value.set(1 / this.down[1].width, 1 / this.down[1].height);
      this.pSPre.render(r, this.s[0]);
      const B = this.pSBlur.uniforms;
      const steps = [1, 4, 14, 40];
      for (let i = 0; i < 4; i++) {
        B.uTex.value = this.s[i].texture;
        B.uTexel.value.set(1 / this.s[i].width, 1 / this.s[i].height);
        B.uStep.value = steps[i];
        this.pSBlur.render(r, this.s[i + 1]);
      }
    }

    // final grade
    {
      const U = this.pFinal.uniforms;
      U.uComp.value = this.comp.texture;
      U.uBloom.value = this.up[0].texture;
      const sb = P.streak > 0;
      U.uS1.value = sb ? this.s[1].texture : this.black;
      U.uS2.value = sb ? this.s[2].texture : this.black;
      U.uS3.value = sb ? this.s[3].texture : this.black;
      U.uS4.value = sb ? this.s[4].texture : this.black;
      U.uExposure.value = P.exposure;
      U.uBloomStrength.value = P.bloom;
      U.uStreakStrength.value = P.streak;
      v3(U.uStreakTint.value, P.streakTint);
      U.uCA.value = P.ca;
      U.uVignette.value = P.vignette;
      U.uGrain.value = P.grain;
      U.uFrame.value = frame % 997;
      U.uLetterbox.value = P.letterbox;
      U.uFade.value = P.fade;
      U.uSat.value = P.sat;
      U.uContrast.value = P.contrast;
      v3(U.uFlash.value, P.flash);
      U.uFlashAmt.value = P.flashAmt;
      v3(U.uSlope.value, P.slope);
      v3(U.uOffset.value, P.offset);
      v3(U.uPower.value, P.power);
      v3(U.uShadowTint.value, P.shadowTint);
      v3(U.uHighTint.value, P.highTint);
      this.pFinal.render(r, null);
    }
  }
}
