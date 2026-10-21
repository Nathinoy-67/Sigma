import * as THREE from 'three';
import { FSPass, GLSL_COMMON, getNoiseTexture } from '../gl.js';

// The Jägerbomb, ray-traced analytically in one full-screen pass: a heavy highball on a dark
// bar top, energy drink inside (golden, carbonated), a shot glass of Jägermeister that drops
// into it, the crown splash and droplets, the dark liqueur billowing through the drink, foam,
// and the pour that fills the glass. Glass walls, base and liquid surface refract properly
// (Fresnel, total internal reflection, Beer–Lambert absorption); the liquid is integrated as
// a volume; bubbles live on nested cylindrical shells so they get correct parallax.
// A second mode ("pool") is the macro of a single drop falling into dark liqueur.
//
// Units are the bottle scene's (1 ≈ 24 cm): the highball is 15 cm tall, the shot glass 6 cm.

export const GLASS = { ro: 0.145, ri: 0.137, h: 0.62, yb: 0.05 };
export const SHOT = { ro: 0.066, ri: 0.0565, h: 0.2, yb: 0.04 };
export const GRAV = 40.9; // 9.81 m/s² in scene units

const f = (x) => x.toFixed(5);


const STUDIO = /* glsl */ `
uniform vec4 uLights;
uniform vec2 uEnvRot;
uniform float uKeyAng;
// ---------------------------------------------------------------- the studio
float box(vec3 rd, float az, float el, float w, float h){
  float a = atan(rd.x, -rd.z);
  float e = asin(clamp(rd.y, -1.0, 1.0));
  float da = abs(mod(a - az + PI, TAU) - PI);
  return smoothstep(w, w * 0.55, da) * smoothstep(h, h * 0.55, abs(e - el));
}
// bar lights far behind, out of focus
vec3 bokeh(vec3 rd){
  float a = atan(rd.x, -rd.z);
  float e = rd.y / max(length(rd.xz), 1e-3);
  vec2 q = vec2(a * 6.0, e * 6.0 + 0.4);
  vec2 ci = floor(q);
  vec3 c = vec3(0.0);
  for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++) {
    vec2 cell = ci + vec2(float(i), float(j));
    vec4 h = h42(cell + 17.0);
    if (h.w > 0.5) continue;
    vec2 ctr = cell + 0.25 + 0.5 * h.xy;
    float R = 0.12 + 0.13 * h.z;
    float d = length(q - ctr);
    float disc = smoothstep(R, R - 0.04, d);
    float rim = smoothstep(R * 0.6, R, d) * disc;
    vec3 tint = h.z < 0.9 ? mix(vec3(1.0, 0.38, 0.08), vec3(1.0, 0.66, 0.3), h.x) : vec3(0.6, 0.72, 1.0) * 0.6;
    c += tint * (disc * 0.5 + rim * 0.55) * (0.35 + 0.65 * h.y);
  }
  return c * exp(-e * e * 2.5) * smoothstep(1.9, 0.5, abs(a));
}
// near-black room with a low warm haze behind the set (r: studio frame)
vec3 haze(vec3 r){
  float a = atan(r.x, -r.z);
  return (vec3(1.0, 0.42, 0.12) * exp(-a * a * 2.0 - (r.y - 0.02) * (r.y - 0.02) * 22.0) * 0.026 * uLights.z + vec3(0.001, 0.0008, 0.0006)) * smoothstep(-0.1, 0.0, r.y);
}
vec3 envBase(vec3 rd){
  // the studio turns with the camera, so the lights hold their place in frame as it orbits
  vec3 r = vec3(uEnvRot.x * rd.x - uEnvRot.y * rd.z, rd.y, uEnvRot.y * rd.x + uEnvRot.x * rd.z);
  vec3 c = bokeh(rd) * 0.16 * uLights.w;
  // key softbox front-left, two orange strips behind either side, a faint top light
  c += vec3(1.0, 0.95, 0.88) * 4.0 * uLights.x * box(r, -2.3, 0.3, 0.3, 0.45);
  c += vec3(0.9, 0.93, 1.0) * 1.2 * uLights.x * box(r, 2.5, 0.2, 0.25, 0.4);
  c += vec3(1.0, 0.5, 0.16) * 8.0 * uLights.y * box(r, -0.78, 0.12, 0.07, 0.8);
  c += vec3(1.0, 0.5, 0.16) * 8.0 * uLights.y * box(r, 0.78, 0.12, 0.07, 0.8);
  c += vec3(0.75, 0.85, 1.0) * 0.3 * uLights.x * smoothstep(0.7, 0.97, r.y);
  c = mix(c, vec3(0.0), smoothstep(0.0, -0.05, r.y));
  return c + haze(r);
}
`;

const BAKE = /* glsl */ `
${GLSL_COMMON}
${STUDIO}
in vec2 vUv; out vec4 fragColor;
void main(){
  float az = (vUv.x - 0.5) * TAU, el = (vUv.y - 0.5) * PI;
  vec3 rd = vec3(cos(el) * sin(az), sin(el), -cos(el) * cos(az));
  fragColor = vec4(envBase(rd), 1.0);
}`;

const FRAG = /* glsl */ `
${GLSL_COMMON}
uniform vec2 uRes;
uniform vec3 uCamPos, uCamR, uCamU, uCamF;
uniform float uTanFov, uTime, uMode, uFill, uFoam, uFizz, uMix, uGlassOn, uReveal, uKeyAng, uBgOn, uFloorOn;
uniform vec3 uGlassPos, uShotX, uShotY, uShotZ, uSplashC;
uniform vec4 uShotP, uShotQ, uPlume, uSplash, uPour, uDrop, uLights, uPool;
uniform vec2 uEnvRot, uBack;
uniform float uCold, uJet;
uniform sampler2D uNoise, uBg, uEnvMap;
uniform mat4 uViewProj;
in vec2 vUv; out vec4 fragColor;

const float RO = ${f(GLASS.ro)}, RI = ${f(GLASS.ri)}, HG = ${f(GLASS.h)}, YB = ${f(GLASS.yb)};
const float SRO = ${f(SHOT.ro)}, SRI = ${f(SHOT.ri)}, SH = ${f(SHOT.h)}, SB = ${f(SHOT.yb)};
const float GRAV = ${f(GRAV)};
const float IOR_G = 1.5, IOR_L = 1.34;
const int AIR = 0, GLS = 1, LIQ = 2;
const vec3 SIG_DRINK = vec3(0.6, 1.65, 6.5);    // energy drink: golden
const vec3 SIG_JAGER = vec3(30.0, 58.0, 120.0); // Jägermeister: deep red-brown
const vec3 SIG_MIXED = vec3(3.2, 7.8, 21.0);   // one shot in the glass, fully mixed: dark amber
const vec3 SIG_GLASS = vec3(1.2, 0.3, 0.7);
float yL;     // liquid level (glass-local y)
float pixK;   // pixel footprint per unit of distance
float gPanel = 1.0; // the backlight is held out of the direct view: only light through the glass sees it

float tn(vec2 p){ return texture(uNoise, p * 0.125).b; }
float tn2(vec2 p){ return texture(uNoise, p * 0.125).a; }
float n3(vec3 p){ return 0.5 * (tn(p.xy + p.z * vec2(0.71, 0.37)) + tn2(p.zy + p.x * vec2(-0.43, 0.83) + 3.7)); }
float fres(float c, float n1, float n2){ float r0 = (n1 - n2) / (n1 + n2); r0 *= r0; return r0 + (1.0 - r0) * pow(1.0 - clamp(c, 0.0, 1.0), 5.0); }
vec2 iCyl(vec3 ro, vec3 rd, vec2 c, float r){
  vec2 o = ro.xz - c, d = rd.xz;
  float a = dot(d, d);
  if (a < 1e-10) return vec2(-1.0);
  float b = dot(o, d), cc = dot(o, o) - r * r;
  float disc = b * b - a * cc;
  if (disc < 0.0) return vec2(-1.0);
  float s = sqrt(disc);
  return vec2((-b - s) / a, (-b + s) / a);
}
vec2 iSph(vec3 ro, vec3 rd, vec3 c, float r){
  vec3 o = ro - c;
  float b = dot(o, rd), cc = dot(o, o) - r * r;
  float disc = b * b - cc;
  if (disc < 0.0) return vec2(-1.0);
  float s = sqrt(disc);
  return vec2(-b - s, -b + s);
}

// the studio is baked once per frame into an equirectangular map; only the backlight
// (which some rays are not allowed to see) is evaluated per lookup
vec3 env(vec3 rd){
  vec2 uv = vec2(atan(rd.x, -rd.z) * (1.0 / TAU) + 0.5, asin(clamp(rd.y, -1.0, 1.0)) * (1.0 / PI) + 0.5);
  vec3 c = texture(uEnvMap, uv).rgb;
  vec3 r = vec3(uEnvRot.x * rd.x - uEnvRot.y * rd.z, rd.y, uEnvRot.y * rd.x + uEnvRot.x * rd.z);
  float a = atan(r.x, -r.z);  // 0: straight ahead of the camera, behind the glass
  // the backlight: a soft warm panel standing right behind the glass
  float pr = length(vec2(a * 1.1, r.y - uBack.x) / uBack.y);
  return c + vec3(1.0, 0.8, 0.52) * exp(-pr * pr) * 2.1 * uLights.z * gPanel;
}

// ---------------------------------------------------------------- the bar top
vec3 floorDiffuse(vec3 p){
  vec3 c = vec3(0.0035, 0.0028, 0.0024) * (0.7 + 0.6 * tn(p.xz * vec2(3.0, 40.0)));
  float r = length(p.xz);
  // golden caustic thrown forward by the backlight through the drink
  if (uFill > 0.0 && uGlassOn > 0.5) {
    vec2 q = (p.xz - vec2(0.0, RO * 1.9)) / vec2(0.2, 0.16);
    float e = exp(-dot(q, q) * 1.6);
    vec3 v = voronoi(p.xz * 30.0 + vec2(uTime * 0.25, 0.0));
    float net = smoothstep(0.08, 0.0, v.y) * 0.35 + 0.4;
    vec3 tint = exp(-mix(SIG_DRINK, SIG_MIXED, uMix) * 0.22);
    c += tint * e * net * 0.08 * uLights.z * smoothstep(0.0, 0.12, uFill);
    c *= 0.4 + 0.6 * smoothstep(RO * 0.9, RO * 1.15, r);
  }
  float dist = length(p - uCamPos + uGlassPos);
  vec3 rd = normalize(p - uCamPos + uGlassPos);
  vec3 rs = vec3(uEnvRot.x * rd.x - uEnvRot.y * rd.z, 0.0, uEnvRot.y * rd.x + uEnvRot.x * rd.z);
  return c * smoothstep(3.2, 0.9, dist);
}

vec3 droplet(vec2 q, float scale, float density){
  vec2 g = q * scale;
  vec2 cell = floor(g);
  vec3 best = vec3(0.0);
  for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++) {
    vec2 c = cell + vec2(float(i), float(j));
    vec4 h = h42(c + 0.37);
    if (h.w > density) continue;
    vec2 ctr = c + 0.15 + 0.7 * h.xy;
    float r = mix(0.14, 0.5, h.z * h.z);
    vec2 d = (g - ctr) / r;
    d.y *= 0.8;
    if (dot(d, d) < 1.0) best = vec3(d, 1.0);
  }
  return best;
}

// ---------------------------------------------------------------- shot glass
vec3 toShot(vec3 v){ return vec3(dot(v, uShotX), dot(v, uShotY), dot(v, uShotZ)); }
vec3 fromShot(vec3 v){ return v.x * uShotX + v.y * uShotY + v.z * uShotZ; }
// nearest hit with the shot glass (local frame); part: 0 side, 1 rim, 2 bottom, 3 inner wall (seen through the mouth), 4 liqueur surface
float hitShot(vec3 ro, vec3 rd, out vec3 n, out int part){
  float best = 1e9;
  vec2 c = iCyl(ro, rd, vec2(0.0), SRO);
  if (c.y < 0.0) return best;
  for (int j = 0; j < 2; j++) {
    float t = c[j];
    float y = ro.y + rd.y * t;
    if (t > 1e-4 && t < best && y > 0.0 && y < SH) { vec3 p = ro + rd * t; best = t; n = normalize(vec3(p.x, 0.0, p.z)); part = 0; }
  }
  if (abs(rd.y) > 1e-6) {
    float t = (SH - ro.y) / rd.y;
    vec3 p = ro + rd * t;
    float r = length(p.xz);
    if (t > 1e-4 && t < best && r > SRI && r < SRO) { best = t; n = vec3(0.0, 1.0, 0.0); part = 1; }
    t = -ro.y / rd.y;
    p = ro + rd * t;
    if (t > 1e-4 && t < best && length(p.xz) < SRO) { best = t; n = vec3(0.0, -1.0, 0.0); part = 2; }
    // through the mouth: the liqueur surface, or the inner wall above it
    float lv = SB + uShotQ.w;
    t = (lv - ro.y) / rd.y;
    p = ro + rd * t;
    if (uShotQ.w > 0.002 && t > 1e-4 && t < best && length(p.xz) < SRI && ro.y > lv) { best = t; n = vec3(0.0, 1.0, 0.0); part = 4; }
  }
  vec2 ci = iCyl(ro, rd, vec2(0.0), SRI);
  float t = ci.y;
  float y = ro.y + rd.y * t;
  if (t > 1e-4 && t < best && y > SB + max(uShotQ.w, 0.0) && y < SH && length((ro + rd * ci.x).xz) < SRI + 0.5) {
    vec3 p = ro + rd * t;
    vec3 pe = ro + rd * max(ci.x, 0.0);
    // only visible when the ray came in through the mouth
    if (pe.y >= SH - 1e-3 || ro.y > SH) { best = t; n = -normalize(vec3(p.x, 0.0, p.z)); part = 3; }
  }
  return best;
}
// what the outer medium looks like behind the shot
vec3 behind(vec3 d, float submerged){
  vec3 c = env(d);
  return submerged > 0.5 ? c * exp(-mix(SIG_DRINK, SIG_MIXED, uMix) * 0.3) : c;
}
vec3 shadeShot(vec3 p, vec3 rd, vec3 n, int part, float n1, float submerged){
  vec3 rdw = fromShot(rd);
  float lv = SB + max(uShotQ.w, 0.0);
  vec3 fillSig = submerged > 0.5 ? mix(SIG_DRINK, SIG_MIXED, uMix) : vec3(0.0);
  if (part == 4) {
    float F = fres(-rd.y, n1, IOR_L);
    vec3 deep = vec3(0.09, 0.012, 0.004) * uLights.z;
    return F * env(fromShot(reflect(rd, n))) + (1.0 - F) * deep;
  }
  if (part == 3) {
    float F = fres(abs(dot(rd, n)), 1.0, IOR_G);
    return F * env(fromShot(reflect(rd, n))) + (1.0 - F) * behind(rdw, submerged) * vec3(0.8, 0.9, 0.85);
  }
  if (part == 1) {
    float r = length(p.xz);
    float u = (r - SRI) / (SRO - SRI);
    vec2 rad = p.xz / max(r, 1e-4);
    vec3 nr = normalize(vec3(rad.x * (u - 0.5) * 1.8, 1.0, rad.y * (u - 0.5) * 1.8));
    float F = fres(abs(dot(rd, nr)), n1, IOR_G);
    return F * env(fromShot(reflect(rd, nr))) * 1.4 + (1.0 - F) * behind(rdw, submerged) * vec3(0.7, 0.85, 0.75);
  }
  if (part == 2) {
    float F = fres(abs(rd.y), n1, IOR_G);
    vec3 r1 = refract(rd, n, n1 / IOR_G);
    return F * env(fromShot(reflect(rd, n))) + (1.0 - F) * behind(fromShot(r1), submerged) * vec3(0.6, 0.78, 0.68);
  }
  // side wall, frosted from the freezer
  float frost = 0.0;
  if (uShotQ.x > 0.0) {
    float th = atan(p.z, p.x);
    vec2 su = vec2(th * SRO, p.y);
    vec3 dd = droplet(su + 3.3, 70.0, 0.3 * uShotQ.x);
    vec3 T = vec3(-sin(th), 0.0, cos(th));
    if (dd.z > 0.0) n = normalize(n + (T * dd.x + vec3(0.0, dd.y, 0.0)) * 0.7);
    frost = (tn(su * 90.0) * 0.7 + 0.3) * uShotQ.x * (1.0 - dd.z);
  }
  float ci = clamp(-dot(rd, n), 0.0, 1.0);
  float F = fres(ci, n1, IOR_G);
  vec3 col = F * env(fromShot(reflect(rd, n)));
  vec3 r1 = refract(rd, n, n1 / IOR_G);
  if (p.y < SB) {
    // the heavy base: a block of glass
    vec3 d2 = refract(r1, -n, IOR_G / n1);
    if (dot(d2, d2) < 1e-6) d2 = reflect(r1, -n);
    // light caught inside the thick base: brightest along its top and bottom edges
    float edge = exp(-p.y / 0.006) + exp(-(SB - p.y) / 0.008) * 0.6;
    vec3 inner = behind(fromShot(normalize(d2 + vec3(0.0, 0.25, 0.0))), submerged) * vec3(0.75, 0.88, 0.8);
    return col + (1.0 - F) * (inner * 0.8 + vec3(1.0, 0.8, 0.55) * edge * 0.25 * uLights.z);
  }
  vec2 c = iCyl(p, r1, vec2(0.0), SRI);
  vec3 tr;
  if (c.x > 0.0 && p.y + r1.y * c.x > SB) {
    vec3 q = p + r1 * c.x;
    vec3 nq = normalize(vec3(q.x, 0.0, q.z));
    float lowerIor = uShotQ.w > 0.002 && q.y < lv ? IOR_L : (submerged > 0.5 ? IOR_L : 1.0);
    vec3 d2 = refract(r1, nq, IOR_G / lowerIor);
    if (dot(d2, d2) < 1e-6) d2 = reflect(r1, nq);
    vec2 c2 = iCyl(q, d2, vec2(0.0), SRI);
    float L = max(c2.y, 0.0);
    float y0 = q.y, y1 = q.y + d2.y * L;
    // portion of the chord below the liqueur level
    float fj = 0.0;
    if (uShotQ.w > 0.002) {
      if (y0 < lv && y1 < lv) fj = 1.0;
      else if (y0 < lv || y1 < lv) fj = clamp((lv - min(y0, y1)) / max(abs(y1 - y0), 1e-5), 0.0, 1.0);
    }
    vec3 sig = SIG_JAGER * fj + fillSig * (1.0 - fj);
    gPanel = submerged > 0.5 ? 0.55 : 1.0;
    tr = exp(-sig * L) * behind(fromShot(d2), submerged) * (0.35 + 0.65 * ci);
    gPanel = 1.0;
    // a warm glow where the backlight passes through the thin edge of the liqueur
    tr += vec3(0.5, 0.06, 0.01) * fj * exp(-L * 22.0) * 0.6 * uLights.z;
    // meniscus line
    if (fj > 0.0 && fj < 1.0) tr += vec3(1.0, 0.55, 0.25) * 0.08 * uLights.y;
    tr *= vec3(0.9, 0.97, 0.93);
  } else {
    // grazing through the wall: green glass edge
    tr = behind(fromShot(r1), submerged) * vec3(0.45, 0.72, 0.58);
  }
  // frost scatters the backlight into a pale veil
  vec3 veil = vec3(0.62, 0.68, 0.72) * (0.02 * uLights.z + 0.012 * uLights.x) * frost;
  return col + (1.0 - F) * tr * (1.0 - 0.35 * frost) + veil;
}

// ---------------------------------------------------------------- splash
float crownTop(float th, float u){
  // irregular sheet: a few lobes, finer fingers, each rising and falling at its own pace
  float h = 0.55 + 0.25 * sin(th * 3.0 + 1.1) * sin(th * 2.0 + 0.4);
  float fing = pow(0.5 + 0.5 * cos(th * 17.0 + 2.0 * sin(th * 3.0)), 8.0);
  h += 0.45 * fing * (0.6 + 0.4 * sin(th * 5.0 + 2.0));
  h += 0.15 * (tn(vec2(th * 4.0, 3.0)) - 0.5);
  return h;
}
float hitCrown(vec3 ro, vec3 rd, out vec3 n, out float rim){
  float tau = uSplash.x;
  float T = 0.3;
  if (tau <= 0.0 || tau > T || uSplash.y <= 0.0) return 1e9;
  float u = tau / T;
  float rc = SRO + 0.004 + 0.05 * pow(u, 0.5);
  float hc = 0.11 * uSplash.y * sin(PI * pow(u, 0.55)) * (1.0 - 0.25 * u);
  vec2 c = iCyl(ro, rd, uSplashC.xz, rc);
  for (int j = 0; j < 2; j++) {
    float t = c[j];
    if (t <= 1e-4) continue;
    vec3 p = ro + rd * t;
    vec2 d = p.xz - uSplashC.xz;
    float th = atan(d.y, d.x);
    float top = yL + hc * crownTop(th, u);
    // the sheet thins and tears near the top as it collapses
    if (p.y > yL - 0.01 && p.y < top) {
      float tear = smoothstep(0.55, 0.9, u) * smoothstep(top - 0.03, top, p.y + 0.02 * tn(vec2(th * 9.0, u * 3.0)));
      if (tear > 0.5) continue;
      n = normalize(vec3(d.x, 0.0, d.y));
      n = normalize(n + vec3(0.0, 0.5, 0.0) * (p.y - yL) / max(hc, 1e-3));
      rim = smoothstep(top - 0.008, top - 0.001, p.y);
      return t;
    }
  }
  return 1e9;
}
float hitDrops(vec3 ro, vec3 rd, out vec3 n){
  float tau = uSplash.x;
  float best = 1e9;
  if (tau <= 0.0 || tau > 1.6 || uSplash.y <= 0.0) return best;
  // bounding cylinder of the splash
  vec2 bc = iCyl(ro, rd, uSplashC.xz, RI);
  if (bc.y < 0.0) return best;
  for (int i = 0; i < 44; i++) {
    vec4 h = h42(vec2(float(i), 5.0));
    vec4 g = h42(vec2(float(i), 9.0));
    float u = tau - (0.04 + 0.14 * h.x);
    if (u <= 0.0) continue;
    // most leave from the tips of the crown's fingers
    float ang = (floor(h.y * 17.0) + 0.5) * TAU / 17.0 - 2.0 * sin(((floor(h.y * 17.0) + 0.5) * TAU / 17.0) * 3.0) / 17.0 + (g.z - 0.5) * 0.12;
    vec2 dir = vec2(cos(ang), sin(ang));
    float vr = (0.12 + 0.4 * h.z) * uSplash.z;
    float vy = (1.4 + 2.4 * h.w) * uSplash.y;
    float r0 = SRO + 0.02;
    float rad = 0.0025 + 0.007 * g.y * g.y;
    vec2 xz = uSplashC.xz + dir * (r0 + vr * u);
    if (length(xz) > RI - rad) continue;
    vec3 c = vec3(xz.x, yL + 0.04 * uSplash.y + vy * u - 0.5 * GRAV * u * u, xz.y);
    if (c.y < yL) continue;
    // stretched along the velocity
    vec3 v = normalize(vec3(dir.x * vr, vy - GRAV * u, dir.y * vr));
    float st = 1.0 + 0.6 * smoothstep(0.0, 2.0, abs(vy - GRAV * u));
    vec3 o = ro - c;
    // scale space along v
    vec3 oo = o - v * dot(o, v) * (1.0 - 1.0 / st);
    vec3 dd = rd - v * dot(rd, v) * (1.0 - 1.0 / st);
    float a = dot(dd, dd), b = dot(oo, dd), cc = dot(oo, oo) - rad * rad;
    float disc = b * b - a * cc;
    if (disc < 0.0) continue;
    float t = (-b - sqrt(disc)) / a;
    if (t > 1e-4 && t < best) {
      best = t;
      vec3 q = oo + dd * t;
      n = normalize(q - v * dot(q, v) * (1.0 - 1.0 / st));
    }
  }
  return best;
}
vec3 shadeLiquidBall(vec3 rd, vec3 n, float rad, vec3 sig){
  float F = fres(-dot(rd, n), 1.0, IOR_L);
  // a ball lens: the room seen through it, bent towards the far side
  vec3 d2 = normalize(rd - 0.35 * (n - rd * dot(n, rd)));
  float ct = abs(dot(rd, n));
  gPanel = 0.3;
  vec3 tr = exp(-sig * rad * 9.0) * env(d2) * smoothstep(0.05, 0.6, ct);
  gPanel = 1.0;
  return F * env(reflect(rd, n)) * 1.5 + (1.0 - F) * tr;
}

// ---------------------------------------------------------------- the pour
float hitStream(vec3 ro, vec3 rd, out vec3 n){
  if (uPour.x <= 0.0) return 1e9;
  vec2 ctr = vec2(0.018, -0.01);
  float r = uPour.y;
  vec2 c = iCyl(ro, rd, ctr, r * 1.05);
  for (int j = 0; j < 2; j++) {
    float t = c[j];
    if (t <= 1e-4) continue;
    vec3 p = ro + rd * t;
    if (p.y < yL - 0.005 || p.y > uPour.z) continue;
    vec2 d = p.xz - ctr;
    float th = atan(d.y, d.x);
    float w = tn(vec2(th * 1.5, p.y * 9.0 + uPour.w * 14.0)) - 0.5;
    n = normalize(vec3(d.x, 0.0, d.y) + vec3(cos(th + 1.5) * w * 0.6, 0.0, sin(th + 1.5) * w * 0.6));
    return t;
  }
  return 1e9;
}

// ---------------------------------------------------------------- the liquid
float plume(vec3 p){
  float tau = uPlume.x;
  if (tau <= 0.0 || uPlume.y <= 0.0) return 0.0;
  vec3 m = uShotP.xyz + uShotY * (SH - 0.02);
  float grow = 1.0 - exp(-tau / 0.45);
  // the wake left by the falling shot and the clouds pouring from its mouth
  float rr = length(p.xz - m.xz);
  float above = smoothstep(m.y - 0.03, m.y + 0.02, p.y) * smoothstep(yL + 0.01, yL - 0.03, p.y);
  float rw = 0.03 + 0.07 * grow + 0.06 * max(p.y - m.y, 0.0) * grow;
  float wake = smoothstep(rw, rw * 0.2, rr) * above * (0.55 + 0.45 * exp(-tau / 2.0));
  float rc = 0.03 + 0.13 * grow;
  float cl = smoothstep(rc, rc * 0.25, length((p - m - vec3(0.0, 0.03 * grow, 0.0)) * vec3(1.0, 1.4, 1.0)));
  float e = max(wake, cl);
  // swirling, rising billows of ink: domain-warped ridged noise gives thin sheets and filaments
  float sw = uPlume.z * (1.0 + 4.0 * (p.y - YB));
  vec2 xz = rot2(sw) * (p.xz - m.xz);
  vec3 q = vec3(xz.x, p.y - m.y - tau * 0.05, xz.y);
  vec3 w = vec3(n3(q * 11.0 + vec3(0.0, -tau * 0.9, 0.0)), 0.0, n3(q * 11.0 + vec3(5.2, -tau * 0.9, 1.3))) - vec3(0.5, 0.0, 0.5);
  vec3 qw = q + w * 0.06 * (0.4 + grow);
  float r1 = 1.0 - abs(2.0 * n3(qw * 26.0 + vec3(0.0, -tau * 1.3, tau * 0.3)) - 1.0);
  float r2 = 1.0 - abs(2.0 * n3(qw * 61.0 + vec3(3.1, -tau * 2.0, 0.0)) - 1.0);
  float fil = r1 * 0.62 + r2 * 0.38;
  float d = e * smoothstep(0.5, 0.92, fil + (e - 0.55) * 0.7) + 0.25 * e * e;
  return d * uPlume.y;
}
float bubbleDens(vec3 p){
  float d = uFizz;
  // the shot's wake fizzes hard after the drop
  if (uPlume.x > 0.0) {
    vec3 m = uShotP.xyz + uShotY * (SH * 0.5);
    float rr = length(p.xz - m.xz);
    d += uPlume.w * exp(-rr * rr * 160.0) * smoothstep(m.y - 0.15, m.y, p.y);
  }
  if (uPour.x > 0.0) d += 1.2 * exp(-length(p.xz - vec2(0.018, -0.01)) * 22.0);
  return d;
}
vec4 bubbleAt(vec3 p, float rk, float k, float dens, float pix){
  float th = atan(p.z, p.x);
  float s = th * rk;
  float cs = 0.011;
  float ci = floor(s / cs);
  vec4 hc = h42(vec2(ci, k * 31.0 + 7.0));
  if (hc.x > dens * 0.14) return vec4(0.0);
  float speed = 0.22 + 0.4 * hc.y;
  float sp = 0.012 + 0.03 * hc.z;
  float yy = p.y - uTime * speed + hc.w * 9.0;
  float ri = floor(yy / sp);
  vec4 hb = h42(vec2(ci * 1.37 + ri * 0.71, k + 3.0));
  if (hb.x > 0.4 + 0.5 * min(dens, 1.0)) return vec4(0.0);
  vec2 ctr = vec2((ci + 0.5 + (hb.y - 0.5) * 0.35) * cs, (ri + 0.5) * sp);
  float rb = (0.0011 + 0.0022 * hb.z * hb.z) * (1.0 + 1.4 * (p.y - YB)) * (1.0 + 0.6 * min(dens - uFizz, 1.5));
  float fade = clamp(rb / (pix * 0.9), 0.0, 1.0);
  rb = max(rb, pix * 0.9);
  vec2 d = vec2(s, yy) - ctr;
  float u = length(d) / rb;
  if (u > 1.0) return vec4(0.0);
  float aa = pix / rb;
  float ring = smoothstep(0.5 - aa, 0.92, u) * smoothstep(1.0, 1.0 - aa - 0.08, u);
  vec2 hp = d / rb - vec2(-0.3, 0.35);
  float spec = exp(-dot(hp, hp) * 22.0);
  vec3 c = vec3(1.0, 0.88, 0.66) * (ring * 0.55 + spec * 2.2);
  return vec4(c * fade, (ring * 0.65 + spec * 0.25) * fade);
}
void liquidVolume(vec3 ro, vec3 rd, float len, int q, float dist0, inout vec3 col, inout vec3 thr){
  int N = q == 1 ? 18 : 5;
  float dt = len / float(N);
  float jit = fh(gl_FragCoord.xy + uTime * 7.0);
  // bubbles on nested shells
  float bt[10]; vec3 bc[10]; float ba[10];
  int nb = 0;
  if (q == 1) {
    for (int k = 0; k < 5; k++) {
      float rk = RI * (0.14 + 0.2 * float(k)) - 0.002;
      vec2 c = iCyl(ro, rd, vec2(0.0), rk);
      for (int j = 0; j < 2; j++) {
        float t = c[j];
        if (t <= 0.0 || t >= len) continue;
        vec3 p = ro + rd * t;
        if (p.y < YB || p.y > yL) continue;
        float dens = bubbleDens(p);
        if (dens <= 0.0) continue;
        vec4 b = bubbleAt(p, rk, float(k), dens, (dist0 + t) * pixK);
        if (b.a > 0.0 && nb < 10) { bt[nb] = t; bc[nb] = b.rgb; ba[nb] = b.a; nb++; }
      }
    }
  }
  vec3 sigBase = mix(SIG_DRINK, SIG_MIXED, uMix);
  for (int i = 0; i < 18; i++) {
    if (i >= N) break;
    float t0 = float(i) * dt;
    vec3 p = ro + rd * (t0 + jit * dt);
    float d = q == 1 ? plume(p) : plume(p) * 0.8;
    vec3 sig = sigBase + SIG_JAGER * d * 0.9;
    vec3 T = exp(-sig * dt);
    // light scattered in the drink (the backlight and the foam above), darker inside the billows
    float up = smoothstep(yL - 0.25, yL, p.y);
    vec3 emit = mix(vec3(1.0, 0.68, 0.22), vec3(0.75, 0.3, 0.07), uMix) * (0.05 + 0.05 * up) * uLights.z;
    emit = mix(emit, vec3(0.05, 0.008, 0.002) * uLights.z, smoothstep(0.0, 0.4, d));
    col += thr * emit * (1.0 - T);
    for (int b = 0; b < 10; b++) {
      if (b >= nb) break;
      if (bt[b] >= t0 && bt[b] < t0 + dt) {
        col += thr * bc[b] * (0.4 * uLights.z + 0.25 * uLights.y);
        thr *= 1.0 - ba[b] * 0.35;
      }
    }
    thr *= T;
  }
}
void foamSlab(vec3 ro, vec3 rd, float len, inout vec3 col, inout vec3 thr){
  if (uFoam <= 0.0 || uFill <= 0.0) return;
  float y0 = yL, y1 = yL + uFoam;
  float ta, tb;
  if (abs(rd.y) < 1e-6) { if (ro.y < y0 || ro.y > y1) return; ta = 0.0; tb = 1e9; }
  else { ta = (y0 - ro.y) / rd.y; tb = (y1 - ro.y) / rd.y; if (ta > tb) { float s = ta; ta = tb; tb = s; } }
  vec2 c = iCyl(ro, rd, vec2(0.0), RI - 0.0005);
  float t0 = max(0.0, max(ta, c.x)), t1 = min(len, min(tb, c.y));
  if (t1 <= t0) return;
  vec3 pe = ro + rd * t0;
  float th = atan(pe.z, pe.x);
  vec2 uv = abs(rd.y) > 0.6 ? pe.xz * 150.0 : vec2(th * RI, pe.y) * 150.0;
  vec3 v = voronoi(uv * 1.6 + uTime * 0.3);
  vec3 v2 = voronoi(uv * 3.7 - uTime * 0.2 + 5.0);
  float cells = (0.45 + 0.55 * smoothstep(0.0, 0.3, v.y)) * (0.7 + 0.3 * smoothstep(0.0, 0.3, v2.y)) * (0.75 + 0.25 * v.z);
  float glint = pow(smoothstep(0.25, 0.0, v.x), 3.0) * step(0.55, v.z);
  float rr = length(pe.xz);
  float foamy = max(smoothstep(RI - 0.008, RI - 0.001, rr) * (0.35 + 0.4 * tn(pe.xz * 40.0)), smoothstep(0.45, 0.75, tn(pe.xz * 14.0 + 3.0) + 0.25 * uMix + 2.0 * (uFoam - 0.01)));
  float a = (1.0 - exp(-130.0 * (t1 - t0) * (0.6 + 0.6 * smoothstep(y0, y1, pe.y)))) * foamy;
  vec3 fc = mix(vec3(1.0, 0.88, 0.62), vec3(0.72, 0.46, 0.24), uMix) * (0.25 + 0.75 * cells);
  fc *= 0.55 * uLights.z + 0.3 * uLights.x + 0.05;
  fc += vec3(1.0, 0.9, 0.75) * glint * (0.5 * uLights.x + 0.3 * uLights.y);
  col += thr * fc * a;
  thr *= 1.0 - a;
}

// ---------------------------------------------------------------- the glass
struct H { float t; vec3 n; int id; };
void consider(inout H h, float t, vec3 n, int id){ if (t > 1e-4 && t < h.t) { h.t = t; h.n = n; h.id = id; } }
H hitGlass(vec3 ro, vec3 rd){
  H h; h.t = 1e9; h.id = 0; h.n = vec3(0.0, 1.0, 0.0);
  if (uGlassOn < 0.5) return h;
  vec2 c = iCyl(ro, rd, vec2(0.0), RO);
  if (c.y < 0.0) return h;
  for (int j = 0; j < 2; j++) {
    vec3 p = ro + rd * c[j];
    if (p.y > 0.0 && p.y < HG) consider(h, c[j], normalize(vec3(p.x, 0.0, p.z)), 1);
  }
  c = iCyl(ro, rd, vec2(0.0), RI);
  for (int j = 0; j < 2; j++) {
    vec3 p = ro + rd * c[j];
    if (p.y > YB && p.y < HG) consider(h, c[j], normalize(vec3(p.x, 0.0, p.z)), 3);
  }
  if (abs(rd.y) > 1e-7) {
    float t = (HG - ro.y) / rd.y;
    vec3 p = ro + rd * t;
    float r = length(p.xz);
    if (r > RI && r < RO) consider(h, t, vec3(0.0, 1.0, 0.0), 2);
    t = (YB - ro.y) / rd.y;
    p = ro + rd * t;
    if (length(p.xz) < RI) consider(h, t, vec3(0.0, 1.0, 0.0), 4);
    t = -ro.y / rd.y;
    p = ro + rd * t;
    if (length(p.xz) < RO) consider(h, t, vec3(0.0, 1.0, 0.0), 5);
    if (uFill > 0.0) {
      t = (yL - ro.y) / rd.y;
      p = ro + rd * t;
      if (length(p.xz) < RI) consider(h, t, vec3(0.0, 1.0, 0.0), 6);
    }
  }
  return h;
}
vec3 liquidNormal(vec3 p, vec3 n){
  vec2 d = p.xz;
  float r = length(d);
  vec2 rad = d / max(r, 1e-4);
  vec2 g = vec2(0.0);
  // meniscus against the wall
  g += rad * 1.4 * exp(-(RI - r) / 0.004);
  // the fizz never quite lets the surface settle
  g += (vec2(tn(p.xz * 9.0 + uTime * 0.5), tn2(p.xz * 9.0 - uTime * 0.4)) - 0.5) * 0.12;
  // ripples running out from the impact
  float tau = uSplash.x;
  if (tau > 0.0 && tau < 3.0) {
    vec2 ds = p.xz - uSplashC.xz;
    float rs = length(ds);
    float k = 160.0;
    float w = sin(k * (rs - 0.09 - 0.35 * tau)) * exp(-tau * 1.4) * smoothstep(0.09 + 0.35 * tau + 0.02, 0.09 + 0.35 * tau - 0.04, rs);
    g += ds / max(rs, 1e-4) * w * 0.35 * uSplash.y;
  }
  if (uPour.x > 0.0) {
    vec2 ds = p.xz - vec2(0.018, -0.01);
    float rs = length(ds);
    g += ds / max(rs, 1e-4) * sin(rs * 220.0 - uPour.w * 40.0) * exp(-rs * 18.0) * 0.4;
    g += (vec2(tn(p.xz * 30.0 + uPour.w * 3.0), tn2(p.xz * 30.0 - uPour.w * 3.0)) - 0.5) * 0.5 * exp(-rs * 10.0);
  }
  vec3 nn = normalize(vec3(-g.x, 1.0, -g.y));
  return n.y < 0.0 ? -nn : nn;
}
vec3 rimNormal(vec3 p, vec3 n){
  float r = length(p.xz);
  float u = (r - RI) / (RO - RI) - 0.5;
  vec2 rad = p.xz / max(r, 1e-4);
  vec3 nn = normalize(vec3(rad.x * u * 2.2, 1.0, rad.y * u * 2.2));
  return dot(nn, n) < 0.0 ? -nn : nn;
}
float iorOf(int m){ return m == GLS ? IOR_G : (m == LIQ ? IOR_L : 1.0); }

vec3 background(vec3 ro, vec3 rd){
  if (uBgOn > 0.5) {
    vec4 c = uViewProj * vec4(ro + rd * 1.6 + uGlassPos, 1.0);
    vec2 uv = c.xy / c.w * 0.5 + 0.5;
    return texture(uBg, clamp(uv, 0.001, 0.999)).rgb;
  }
  return env(rd);
}

// One path through the scene, following refraction (reflections come from the environment).
// q: 1 full quality, 0 cheap (reflection rays). Returns colour; reports a hit on the bar top.
vec3 trace(vec3 ro, vec3 rd, int q, out vec3 floorP, out vec3 floorThr, out float hitObj){
  vec3 col = vec3(0.0), thr = vec3(1.0);
  floorThr = vec3(0.0);
  floorP = vec3(0.0);
  hitObj = 0.0;
  int med = AIR;
  float dist = 0.0;
  float wet = 0.0;
  int maxI = q == 1 ? 11 : 6;
  for (int i = 0; i < 11; i++) {
    if (i >= maxI || max(thr.r, max(thr.g, thr.b)) < 0.003) break;
    H h = hitGlass(ro, rd);
    vec3 n;
    int part;
    if (med != GLS && uShotP.w > 0.5) {
      vec3 sro = toShot(ro - uShotP.xyz), srd = toShot(rd);
      float ts = hitShot(sro, srd, n, part);
      if (ts < h.t) { h.t = ts; h.id = 8; h.n = n; }
    }
    if (med == AIR) {
      float td = hitDrops(ro, rd, n);
      if (td < h.t) { h.t = td; h.id = 9; h.n = n; }
      td = hitStream(ro, rd, n);
      if (td < h.t) { h.t = td; h.id = 10; h.n = n; }
      float rim;
      td = hitCrown(ro, rd, n, rim);
      if (td < h.t) { h.t = td; h.id = 11; h.n = n; }
      if (rd.y < 0.0 && uFloorOn > 0.5 && wet < 0.5) {
        float tf = -ro.y / rd.y;
        vec3 pf = ro + rd * tf;
        if (tf < h.t && (uGlassOn < 0.5 || length(pf.xz) > RO - 1e-3)) { h.t = tf; h.id = 12; }
      }
    }
    float seg = min(h.t, 4.0);
    if (med == LIQ) { liquidVolume(ro, rd, seg, q, dist, col, thr); wet = 1.0; }
    else if (med == GLS) thr *= exp(-SIG_GLASS * seg);
    else foamSlab(ro, rd, seg, col, thr);
    dist += seg;
    if (h.id == 0) { gPanel = wet > 0.5 ? 1.0 : (hitObj > 0.5 ? 0.15 : 0.035); col += thr * background(ro, rd); gPanel = 1.0; break; }
    vec3 p = ro + rd * h.t;
    if (h.id != 12 && h.id != 0) hitObj = 1.0;
    if (h.id == 12) { floorP = p; floorThr = thr; col += thr * floorDiffuse(p); break; }
    if (h.id == 5) {
      float rr = length(p.xz) / RO;
      vec3 glow = exp(-mix(SIG_DRINK, SIG_MIXED, uMix) * 0.3) * (0.05 + 0.25 * smoothstep(0.6, 1.0, rr)) * uLights.z * smoothstep(0.0, 0.1, uFill);
      col += thr * (floorDiffuse(p) * 0.6 + glow);
      break;
    }
    if (h.id == 8) {
      vec3 sro = toShot(ro - uShotP.xyz), srd = toShot(rd);
      float ts = hitShot(sro, srd, n, part);
      col += thr * shadeShot(sro + srd * ts, srd, n, part, iorOf(med), med == LIQ ? 1.0 : 0.0);
      break;
    }
    if (h.id == 9) { col += thr * shadeLiquidBall(rd, h.n, 0.006, mix(SIG_DRINK, SIG_MIXED, uMix)); break; }
    if (h.id == 10) {
      vec3 nn = h.n;
      float F = fres(-dot(rd, nn), 1.0, IOR_L);
      vec3 d1 = refract(rd, nn, 1.0 / IOR_L);
      vec2 c2 = iCyl(p, d1, vec2(0.018, -0.01), uPour.y);
      float L = max(c2.y, 0.0);
      vec3 q2 = p + d1 * L;
      vec3 n2 = -normalize(vec3(q2.x - 0.018, 0.0, q2.z + 0.01));
      vec3 d2 = refract(d1, n2, IOR_L);
      if (dot(d2, d2) < 1e-6) d2 = reflect(d1, n2);
      col += thr * (F * env(reflect(rd, nn)) * 1.3 + (1.0 - F) * exp(-SIG_DRINK * L * 1.5) * env(d2) * 1.15);
      break;
    }
    if (h.id == 11) {
      float rim;
      vec3 nn = h.n;
      hitCrown(ro, rd, nn, rim);
      if (dot(nn, rd) > 0.0) nn = -nn;
      float F = fres(-dot(rd, nn), 1.0, IOR_L);
      vec3 sig = mix(SIG_DRINK, SIG_MIXED, uMix);
      float edge = pow(1.0 - abs(dot(rd, nn)), 2.0);
      col += thr * (F * env(reflect(rd, nn)) * 1.6 + vec3(1.0, 0.72, 0.32) * (rim * 0.5 + edge * 0.25) * (0.3 * uLights.y + 0.3 * uLights.z));
      thr *= (1.0 - F) * exp(-sig * (0.02 + 0.05 * edge)) * (1.0 - 0.5 * rim);
      ro = p + rd * 2e-4;
      continue;
    }
    // a glass or liquid interface
    vec3 nf = dot(h.n, rd) > 0.0 ? -h.n : h.n;
    int nm = med;
    if (h.id == 1 || h.id == 2) nm = med == GLS ? AIR : GLS;
    else if (h.id == 3 || h.id == 4) nm = med == GLS ? (p.y < yL && uFill > 0.0 ? LIQ : AIR) : GLS;
    else if (h.id == 6) nm = med == LIQ ? AIR : LIQ;
    if (h.id == 6) nf = liquidNormal(p, nf);
    if (h.id == 1 && uCold > 0.0) {
      // condensation: the glass is ice cold below the drink line
      float th = atan(p.z, p.x);
      vec2 su = vec2(th * RO, p.y);
      float dens = smoothstep(yL + 0.05, yL - 0.06, p.y) * uCold;
      vec3 d1 = droplet(su, 55.0, 0.13 * dens);
      vec3 d2 = droplet(su + 7.31, 170.0, 0.2 * dens);
      vec3 T = vec3(-sin(th), 0.0, cos(th));
      vec3 sgn = med == AIR ? nf : -nf;
      if (d1.z > 0.0) nf = normalize(nf + (T * d1.x + vec3(0.0, d1.y, 0.0)) * 0.75 * sign(dot(sgn, nf)));
      else if (d2.z > 0.0) nf = normalize(nf + (T * d2.x + vec3(0.0, d2.y, 0.0)) * 0.4 * sign(dot(sgn, nf)));
      if (med == AIR) {
        float frost = (tn(su * vec2(60.0, 60.0)) * 0.6 + 0.4) * dens;
        col += thr * vec3(0.6, 0.66, 0.7) * 0.012 * frost * (uLights.x + uLights.z);
        thr *= 1.0 - 0.08 * frost;
      }
    }
    if (h.id == 2) nf = rimNormal(p, nf);
    float n1 = iorOf(med), n2 = iorOf(nm);
    float ci = clamp(-dot(rd, nf), 0.0, 1.0);
    float F = fres(ci, n1, n2);
    vec3 rt = refract(rd, nf, n1 / n2);
    if (dot(rt, rt) < 1e-6) {
      rd = reflect(rd, nf);
      ro = p + rd * 2e-4;
      continue;
    }
    vec3 rr = reflect(rd, nf);
    vec3 ref = env(rr);
    // the liquid seen from below mirrors the drink, not the room
    if (med == LIQ && h.id == 6) ref = env(rr) * exp(-mix(SIG_DRINK, SIG_MIXED, uMix) * 0.15);
    col += thr * F * ref;
    thr *= 1.0 - F;
    rd = rt;
    med = nm;
    ro = p + rd * 2e-4;
  }
  return col;
}

// ---------------------------------------------------------------- pool mode (the opening drop)
// Worthington jet: a round cone rising from the centre, its tip pinching into a droplet
float sdJet(vec3 p, float h, float r0, float r1){
  vec2 q = vec2(length(p.xz), p.y);
  float b = (r0 - r1) / h;
  float a = sqrt(1.0 - b * b);
  float k = dot(q, vec2(-b, a));
  if (k < 0.0) return length(q) - r0;
  if (k > a * h) return length(q - vec2(0.0, h)) - r1;
  return dot(q, vec2(a, b)) - r0;
}
vec3 poolSurface(vec3 ro, vec3 rd, float tau, out float tHit){
  tHit = 1e9;
  if (rd.y >= 0.0) return env(rd) * 0.6;
  float t = -ro.y / rd.y;
  tHit = t;
  vec3 p = ro + rd * t;
  float r = length(p.xz);
  vec2 g = vec2(0.0);
  if (tau > 0.0) {
    for (int k = 0; k < 3; k++) {
      float sp = 0.16 + 0.05 * float(k);
      float rr = r - sp * tau - 0.01 * float(k);
      float w = cos(rr * (260.0 - 50.0 * float(k))) * exp(-rr * rr * 900.0) * exp(-tau * 0.9) * uPool.y;
      g += p.xz / max(r, 1e-4) * w * 0.25;
    }
    g += p.xz / max(r, 1e-4) * exp(-r * 70.0) * exp(-tau * 3.0) * -0.6 * uPool.y;
  }
  g += (vec2(tn(p.xz * 14.0 + uTime * 0.05), tn2(p.xz * 14.0 - uTime * 0.04)) - 0.5) * 0.025;
  vec3 ns = normalize(vec3(-g.x, 1.0, -g.y));
  float F = fres(-dot(rd, ns), 1.0, IOR_L);
  vec3 col = F * env(reflect(rd, ns)) * 1.2 + (1.0 - F) * vec3(0.012, 0.002, 0.0006) * uLights.z;
  return col * smoothstep(4.0, 0.6, t);
}
vec3 liquidSkin(vec3 rd, vec3 n, float thick, vec3 behindCol){
  float F = fres(abs(dot(rd, n)), 1.0, IOR_L);
  float edge = pow(1.0 - abs(dot(rd, n)), 2.0);
  vec3 T = exp(-SIG_JAGER * 1.1 * thick * (1.0 + 3.0 * edge));
  vec3 glow = vec3(0.6, 0.12, 0.02) * edge * edge * 0.25 * uLights.y;
  return F * env(reflect(rd, n)) * vec3(1.0, 0.62, 0.36) * 0.9 + (1.0 - F) * (T * behindCol + glow);
}
vec3 pool(vec3 ro, vec3 rd){
  float tau = uPool.x;
  float ts;
  vec3 surf = poolSurface(ro, rd, tau, ts);
  vec3 col = surf;
  // the falling drop (or the droplet the jet throws off)
  vec3 dc = uDrop.xyz;
  float dr = uDrop.w;
  float best = ts;
  if (dr > 0.0) {
    vec3 o = ro - dc;
    vec3 sc = vec3(1.0, 1.0 / 1.12, 1.0);
    vec3 oo = o * sc, dd = rd * sc;
    float a = dot(dd, dd), b = dot(oo, dd), cc = dot(oo, oo) - dr * dr;
    float disc = b * b - a * cc;
    if (disc > 0.0) {
      float t = (-b - sqrt(disc)) / a;
      if (t > 0.0 && t < best) {
        best = t;
        vec3 n = normalize((oo + dd * t) * sc);
        vec3 d2 = normalize(rd - 0.35 * (n - rd * dot(n, rd)));
        float F = fres(-dot(rd, n), 1.0, IOR_L);
        vec3 tr = exp(-SIG_JAGER * 1.1 * dr * 1.6) * env(d2) * 1.4;
        tr += vec3(0.6, 0.08, 0.01) * pow(1.0 - abs(dot(rd, n)), 2.0) * 0.4 * uLights.z;
        col = F * env(reflect(rd, n)) * 1.3 + (1.0 - F) * tr;
      }
    }
  }
  if (tau > 0.0) {
    // the crown: a thin sheet of liqueur, translucent over the pool behind it
    float u = tau / 0.32;
    if (u < 1.0) {
      float rc = 0.011 + 0.026 * pow(u, 0.5);
      float hc = 0.024 * sin(PI * pow(u, 0.6)) * uPool.y;
      vec2 c = iCyl(ro, rd, vec2(0.0), rc);
      // back wall first, then the front wall over it
      for (int j = 1; j >= 0; j--) {
        float t = c[j];
        vec3 p = ro + rd * t;
        float th = atan(p.z, p.x);
        float top = hc * crownTop(th * 0.8, u);
        float tear = smoothstep(0.6, 0.9, u) * smoothstep(top - 0.006, top, p.y + 0.004 * tn(vec2(th * 9.0, u * 3.0)));
        if (t > 0.0 && t < best && p.y > 0.0 && p.y < top && tear < 0.5) {
          vec3 n = normalize(vec3(p.x, 0.0, p.z) + vec3(0.0, 0.6, 0.0) * p.y / max(hc, 1e-3));
          float rim = smoothstep(top - 0.0025, top - 0.0004, p.y);
          col = liquidSkin(rd, n, 0.002, col) + vec3(1.0, 0.6, 0.3) * rim * 0.25 * uLights.y;
        }
      }
    }
    float uj = (tau - 0.18) / 0.5;
    if (uJet > 0.5 && uj > 0.0 && uj < 1.0) {
      float hj = 0.034 * sin(PI * pow(uj, 0.7)) * uPool.y;
      float r0 = 0.0062 * (1.0 - 0.3 * uj), r1 = 0.0028 * (1.0 + 0.3 * uj);
      vec2 bc = iCyl(ro, rd, vec2(0.0), r0 + 0.002);
      if (bc.y > 0.0 && hj > 0.004) {
        float t = max(bc.x, 0.0);
        for (int i = 0; i < 40; i++) {
          vec3 p = ro + rd * t;
          float d = sdJet(p, hj, r0, r1);
          if (d < 0.00005) {
            if (t < best && p.y > 0.0) {
              vec2 e = vec2(0.00005, 0.0);
              vec3 n = normalize(vec3(sdJet(p + e.xyy, hj, r0, r1) - sdJet(p - e.xyy, hj, r0, r1), sdJet(p + e.yxy, hj, r0, r1) - sdJet(p - e.yxy, hj, r0, r1), sdJet(p + e.yyx, hj, r0, r1) - sdJet(p - e.yyx, hj, r0, r1)));
              col = liquidSkin(rd, n, 0.006, surf * 0.6);
            }
            break;
          }
          t += d;
          if (t > bc.y + 0.01) break;
        }
      }
    }
  }
  return col;
}

void main(){
  vec2 p = (gl_FragCoord.xy - 0.5 * uRes) / uRes.y;
  vec3 rd = normalize(uCamF + (p.x * uCamR + p.y * uCamU) * 2.0 * uTanFov);
  vec3 ro = uCamPos - uGlassPos;
  pixK = 2.0 * uTanFov / uRes.y;
  yL = YB + uFill;
  vec3 col;
  float a = 1.0;
  if (uMode > 0.5) col = pool(ro, rd);
  else {
    vec3 fp, ft;
    float hit;
    col = trace(ro, rd, 1, fp, ft, hit);
    if (max(ft.r, max(ft.g, ft.b)) > 0.0) {
      // the lacquered bar top mirrors the glass
      vec3 rr = reflect(rd, vec3(0.0, 1.0, 0.0));
      rr = normalize(rr + vec3(tn(fp.xz * 9.0) - 0.5, 0.0, tn2(fp.xz * 9.0) - 0.5) * 0.03);
      float F = 0.03 + 0.6 * pow(1.0 - clamp(-rd.y, 0.0, 1.0), 5.0);
      vec3 f2, t2;
      float h2;
      vec3 rc = trace(fp + rr * 1e-3, rr, 0, f2, t2, h2);
      col += ft * rc * F * smoothstep(3.0, 0.8, length(fp.xz));
    }
    if (uBgOn > 0.5 && hit < 0.5) a = 0.0;
  }
  col *= uReveal;
  fragColor = vec4(col, uBgOn > 0.5 ? a : luma(col) * 0.6);
}`;

export class DropScene {
  constructor(renderer, W, H) {
    this.r = renderer;
    this.W = W;
    this.H = H;
    const u = (v) => ({ value: v });
    const v3 = () => new THREE.Vector3();
    const v4 = () => new THREE.Vector4();
    this.pass = new FSPass(
      FRAG,
      {
        uRes: u(new THREE.Vector2(W, H)), uCamPos: u(v3()), uCamR: u(v3()), uCamU: u(v3()), uCamF: u(v3()),
        uTanFov: u(0.25), uTime: u(0), uMode: u(0), uFill: u(0.28), uFoam: u(0.006), uFizz: u(0.6), uMix: u(0),
        uGlassOn: u(1), uReveal: u(1), uKeyAng: u(-0.7), uBgOn: u(0), uFloorOn: u(1),
        uGlassPos: u(v3()), uShotX: u(new THREE.Vector3(1, 0, 0)), uShotY: u(new THREE.Vector3(0, 1, 0)), uShotZ: u(new THREE.Vector3(0, 0, 1)),
        uSplashC: u(v3()), uShotP: u(v4()), uShotQ: u(v4()), uPlume: u(v4()), uSplash: u(v4()), uPour: u(v4()), uDrop: u(v4()),
        uLights: u(new THREE.Vector4(1, 1, 1, 1)), uPool: u(v4()), uEnvRot: u(new THREE.Vector2(1, 0)), uBack: u(new THREE.Vector2(0, 0.1)), uCold: u(1), uJet: u(0), uEnvMap: u(null),
        uNoise: u(getNoiseTexture(renderer)), uBg: u(null), uViewProj: u(new THREE.Matrix4()),
      },
      // composite mode blends over the frame already in the target (alpha = glass coverage)
    );
    this.blendMat = this.pass.material.clone();
    this.blendMat.transparent = true;
    this.blendMat.blending = THREE.CustomBlending;
    this.blendMat.blendSrc = THREE.SrcAlphaFactor;
    this.blendMat.blendDst = THREE.OneMinusSrcAlphaFactor;
    this.blendMat.blendSrcAlpha = THREE.ZeroFactor;
    this.blendMat.blendDstAlpha = THREE.OneFactor;
    this.blendMat.uniforms = this.pass.uniforms;
    this.camera = new THREE.PerspectiveCamera(30, W / H, 0.01, 50);
    this.envRT = new THREE.WebGLRenderTarget(1536, 768, {
      type: THREE.HalfFloatType, format: THREE.RGBAFormat, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter,
      wrapS: THREE.RepeatWrapping, wrapT: THREE.ClampToEdgeWrapping, depthBuffer: false, generateMipmaps: false,
    });
    this.pass.uniforms.uEnvMap.value = this.envRT.texture;
    this.bake = new FSPass(BAKE, this.pass.uniforms);
  }

  setCamera(c) {
    const cam = this.camera;
    cam.fov = c.fov;
    cam.aspect = this.W / this.H;
    cam.position.set(...c.pos);
    cam.up.set(Math.sin(c.roll || 0), Math.cos(c.roll || 0), 0);
    cam.lookAt(...c.target);
    cam.updateProjectionMatrix();
    cam.updateMatrixWorld();
  }

  // world point → 1080p design pixels
  project(p) {
    const v = new THREE.Vector3(...p).project(this.camera);
    const W1 = 1080 * (this.W / this.H);
    return [(v.x * 0.5 + 0.5) * W1, (0.5 - v.y * 0.5) * 1080, v.z];
  }

  // s: { cam{pos,target,fov,roll}, time, mode, fill, foam, fizz, mix, glass, glassPos, shot{pos, axis, fill, on},
  //      plume[tau, amt, swirl, fizz], splash[tau, strength, spread], splashC, pour[on, r, top, t], drop[x,y,z,r], pool[tau, strength],
  //      lights[key, rim, back, bokeh], keyAng, reveal, bg (texture) }
  render(target, s) {
    this.setCamera(s.cam);
    const U = this.pass.uniforms;
    const cam = this.camera;
    const e = cam.matrixWorld.elements;
    U.uCamR.value.set(e[0], e[1], e[2]);
    U.uCamU.value.set(e[4], e[5], e[6]);
    U.uCamF.value.set(-e[8], -e[9], -e[10]);
    U.uCamPos.value.copy(cam.position);
    U.uTanFov.value = Math.tan((s.cam.fov * Math.PI) / 360);
    U.uTime.value = s.time;
    U.uMode.value = s.mode === 'pool' ? 1 : 0;
    U.uFill.value = s.fill ?? 0.28;
    U.uFoam.value = s.foam ?? 0.006;
    U.uFizz.value = s.fizz ?? 0.6;
    U.uMix.value = s.mix ?? 0;
    U.uGlassOn.value = s.glass === false ? 0 : 1;
    U.uReveal.value = s.reveal ?? 1;
    U.uKeyAng.value = s.keyAng ?? -0.7;
    U.uFloorOn.value = s.floor === false ? 0 : 1;
    U.uCold.value = s.cold ?? 1;
    U.uGlassPos.value.set(...(s.glassPos || [0, 0, 0]));
    const sh = s.shot;
    if (sh && sh.on) {
      const Y = new THREE.Vector3(...sh.axis).normalize();
      const X = new THREE.Vector3(0, 0, 1).cross(Y).normalize();
      if (X.lengthSq() < 1e-6) X.set(1, 0, 0);
      const Z = new THREE.Vector3().crossVectors(X, Y).normalize();
      U.uShotX.value.copy(X);
      U.uShotY.value.copy(Y);
      U.uShotZ.value.copy(Z);
      U.uShotP.value.set(sh.pos[0], sh.pos[1], sh.pos[2], 1);
      U.uShotQ.value.set(sh.frost ?? 1, 0, 0, sh.fill ?? 0.13);
    } else U.uShotP.value.set(0, 0, 0, 0);
    U.uPlume.value.set(...(s.plume || [0, 0, 0, 0]));
    U.uSplash.value.set(...(s.splash || [0, 0, 0, 0]));
    U.uSplashC.value.set(...(s.splashC || [0, 0, 0]));
    U.uPour.value.set(...(s.pour || [0, 0, 0, 0]));
    U.uDrop.value.set(...(s.drop || [0, 0, 0, 0]));
    U.uPool.value.set(...(s.pool || [0, 0, 0, 0]));
    U.uLights.value.set(...(s.lights || [1, 1, 1, 1]));
    // studio lights follow the camera; the backlight sits behind the liquid as seen from it
    const gp = s.glassPos || [0, 0, 0];
    const fx = s.cam.target[0] - s.cam.pos[0], fz = s.cam.target[2] - s.cam.pos[2];
    const fl = Math.hypot(fx, fz) || 1;
    U.uEnvRot.value.set(-fz / fl, -fx / fl);
    const bc = new THREE.Vector3(gp[0], gp[1] + (s.backY ?? 0.24), gp[2]).sub(cam.position).normalize();
    U.uBack.value.set(bc.y, s.backSize ?? 0.12);
    this.bake.render(this.r, this.envRT);
    if (s.bg) {
      U.uBgOn.value = 1;
      U.uBg.value = s.bg;
      U.uViewProj.value.multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse);
      this.pass.mesh.material = this.blendMat;
    } else {
      U.uBgOn.value = 0;
      this.pass.mesh.material = this.pass.material;
    }
    this.pass.render(this.r, target);
  }
}
