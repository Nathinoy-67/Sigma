import * as THREE from 'three';
import { FSPass, GLSL_COMMON } from '../gl.js';

// "A new kind of energy": a macro inside the golden drink. Streams of bubbles rise past the
// lens on several depth layers (sharp in the focal plane, soft bokeh in front and behind),
// light pours down from the surface, and the fastest bubbles leave glowing trails.

const FRAG = /* glsl */ `
${GLSL_COMMON}
uniform vec2 uRes;
uniform float uTime, uRise, uEnergy, uReveal, uFocus, uSurface;
in vec2 vUv; out vec4 fragColor;

// one layer of rising bubbles at depth z: returns premultiplied colour + coverage
vec4 bubbles(vec2 p, float z, float k, float aperture){
  float sc = 1.0 / z;
  vec2 q = p / sc;                  // world units on this layer
  q.y -= uRise / z * 0.0;           // (camera rise handled by the caller)
  float cs = 0.075;
  float ci = floor(q.x / cs);
  vec4 hc = h42(vec2(ci, k * 13.0 + 1.0));
  float blur0 = abs(1.0 / z - 1.0 / uFocus) * aperture * z;
  if (hc.x > (blur0 > 0.012 ? 0.16 : 0.42)) return vec4(0.0);
  float speed = 0.28 + 0.5 * hc.y;
  float sp = 0.07 + 0.16 * hc.z;
  float wob = sin(q.y * 9.0 + hc.w * 30.0 + uTime * 2.0) * 0.006;
  float yy = q.y - uTime * speed * (1.0 + 1.6 * uEnergy) + hc.w * 7.0;
  float ri = floor(yy / sp);
  vec4 hb = h42(vec2(ci * 2.31 + ri * 0.37, k + 5.0));
  if (hb.x > 0.6) return vec4(0.0);
  vec2 ctr = vec2((ci + 0.5 + (hc.w - 0.5) * 0.5) * cs + wob, (ri + 0.5) * sp);
  float rb = 0.006 + 0.016 * hb.z * hb.z;
  vec2 d = vec2(q.x, yy) - ctr;
  float blur = abs(1.0 / z - 1.0 / uFocus) * aperture / sc;  // circle of confusion in layer units
  float pix = z / uRes.y;
  float r = length(d);
  vec4 o = vec4(0.0);
  // the fastest bubbles streak (motion trail above them is below them on screen: they rise)
  float trail = 0.0;
  if (hb.y > 0.8 && blur < rb * 0.35) {
    float ty = d.y;
    float len = min(0.05 + 0.25 * uEnergy, sp * 0.8);
    trail = exp(-pow(d.x / (rb * 0.35 + pix), 2.0)) * smoothstep(-len, 0.0, ty) * step(ty, 0.0) * smoothstep(-sp * 0.5, -sp * 0.5 + 0.02, d.y + 0.0) * (0.35 + 0.65 * uEnergy);
  }
  if (blur > rb * 0.35) {
    float R = min(rb + blur, cs * 0.45);
    float disc = smoothstep(R + pix * 1.5, R - pix * 1.5, r);
    float rim = smoothstep(R * 0.55, R, r) * disc;
    float a = (rb * rb) / (R * R);
    a = clamp(a * 3.0, 0.0, 1.0) * 0.25;
    o = vec4(vec3(1.0, 0.7, 0.32) * (disc * 0.5 + rim * 0.7) * a * 1.2, disc * a * 0.3);
  } else {
    float u = r / rb;
    float aa = pix / rb * 1.5;
    float body = smoothstep(1.0 + aa, 1.0 - aa, u);
    float ring = smoothstep(0.55, 0.96, u) * body;
    vec2 hp = d / rb - vec2(-0.32, 0.38);
    float spec = exp(-dot(hp, hp) * 26.0);
    vec2 hp2 = d / rb - vec2(0.25, -0.45);
    float spec2 = exp(-dot(hp2, hp2) * 40.0) * 0.4;
    vec3 c = vec3(1.0, 0.86, 0.6) * ring * 0.9 + vec3(1.0, 0.95, 0.85) * (spec * 3.0 + spec2);
    // the inside of the bubble shows a dim, inverted image of the light above
    c += vec3(0.6, 0.38, 0.12) * body * (1.0 - ring) * smoothstep(0.2, -0.6, d.y / rb) * 0.4;
    o = vec4(c, body * (0.25 + 0.6 * ring));
  }
  o.rgb += vec3(1.0, 0.75, 0.35) * trail * 0.7;
  return o;
}

void main(){
  vec2 p = (gl_FragCoord.xy - 0.5 * uRes) / uRes.y;
  float y = p.y;
  // the drink: deep amber below, bright gold towards the surface light
  vec3 col = mix(vec3(0.025, 0.008, 0.001), vec3(0.62, 0.34, 0.07), pow(smoothstep(-0.7, 0.8, y), 1.6));
  col *= 0.85 + 0.15 * uEnergy;
  // light shafts slanting down from the surface
  float sh = 0.0;
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float x = p.x * (1.0 + 0.3 * fi) + y * (0.18 + 0.05 * fi) + uTime * (0.02 + 0.01 * fi) + fi * 3.7;
    sh += pow(vnoise(vec2(x * 7.0, fi * 5.0 + uTime * 0.3)), 3.0);
  }
  col += vec3(1.0, 0.7, 0.3) * sh * 0.12 * smoothstep(-0.5, 0.7, y);
  // fine suspended sparkle
  float sp = pow(fh(floor(gl_FragCoord.xy * 0.5) + floor(uTime * 12.0)), 300.0);
  col += vec3(1.0, 0.85, 0.6) * sp * 0.5;
  // the underside of the surface, a silvery wavy mirror at the top of frame
  float sy = uSurface + 0.012 * sin(p.x * 14.0 + uTime * 1.6) + 0.006 * sin(p.x * 31.0 - uTime * 2.3);
  float surf = smoothstep(sy - 0.004, sy + 0.004, y);
  col = mix(col, vec3(1.3, 1.05, 0.7) * (0.6 + 0.4 * vnoise(vec2(p.x * 20.0, uTime))), surf * 0.85);
  col += vec3(1.0, 0.85, 0.55) * exp(-abs(y - sy) / 0.006) * 0.8;
  // bubble layers, far to near
  for (int k = 0; k < 7; k++) {
    float fk = float(k);
    float z = mix(3.2, 0.42, fk / 6.0);
    vec2 pp = p + vec2(fk * 0.37, uRise / z);
    vec4 b = bubbles(pp, z, fk, 0.05);
    // further layers sit deeper in the drink
    float fog = exp(-z * 0.35);
    col = col * (1.0 - b.a) + b.rgb * fog * (0.45 + 0.8 * smoothstep(-0.5, 0.6, y));
  }
  col *= uReveal;
  fragColor = vec4(col, luma(col) * 0.5);
}`;

export class FizzScene {
  constructor(renderer, W, H) {
    this.r = renderer;
    const u = (v) => ({ value: v });
    this.pass = new FSPass(FRAG, {
      uRes: u(new THREE.Vector2(W, H)), uTime: u(0), uRise: u(0), uEnergy: u(0), uReveal: u(1), uFocus: u(1.0), uSurface: u(2),
    });
  }

  // s: { time, rise, energy, reveal, focus, surface }
  render(target, s) {
    const U = this.pass.uniforms;
    U.uTime.value = s.time;
    U.uRise.value = s.rise ?? 0;
    U.uEnergy.value = s.energy ?? 0;
    U.uReveal.value = s.reveal ?? 1;
    U.uFocus.value = s.focus ?? 1.0;
    U.uSurface.value = s.surface ?? 2;
    this.pass.render(this.r, target);
  }
}
