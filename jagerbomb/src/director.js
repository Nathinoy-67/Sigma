import * as THREE from 'three';
import { CUE } from './timeline.js';
import { CUE as L } from './legacy.js';
import { DEFAULT_POST } from './post.js';
import { clamp, lerp, remap, ease, noise1, smooth, FSPass, makeRT } from './gl.js';
import { pathX, pathSlope } from './scenes/forest.js';
import { IMPACT } from './scenes/shards.js';
import { stagPose, stagProjector } from './overlay.js';
import { GLASS, SHOT, GRAV } from './scenes/drop.js';

// The director decides, for any time t, what is on screen: which scenes render, where the
// cameras are, the post-processing look and what the typography layer draws.

const pulse = (t, t0, rise, fall) => (t < t0 ? Math.exp(-Math.pow((t - t0) / rise, 2)) : Math.exp(-(t - t0) / fall));
const after = (t, t0, fall) => (t < t0 ? 0 : Math.exp(-(t - t0) / fall));
const shake = (t, t0, amp, fall, freq = 38) => {
  const k = after(t, t0, fall) * amp;
  return [noise1(t * freq, 3) * k, noise1(t * freq + 11, 9) * k];
};
const addShake = (P, s) => {
  P.shake[0] += s[0];
  P.shake[1] += s[1];
};
// piecewise-linear map through [x, y] keys
const pl = (x, keys) => {
  if (x <= keys[0][0]) return keys[0][1] + (x - keys[0][0]);
  for (let i = 1; i < keys.length; i++)
    if (x <= keys[i][0]) return lerp(keys[i - 1][1], keys[i][1], (x - keys[i - 1][0]) / (keys[i][0] - keys[i - 1][0]));
  const k = keys[keys.length - 1];
  return k[1] + (x - k[0]);
};
const LETTERBOX = 0.128;
const orbit = (ang, dist, h, ty, fov = 30, roll = 0, cx = 0, cz = 0) => ({
  pos: [cx + Math.sin(ang) * dist, h, cz + Math.cos(ang) * dist],
  target: [cx, ty, cz],
  fov,
  roll,
});

// ---------------------------------------------------------------- ACT I timing
// The forest, stag and 56 run on The Hunter's Hour clock, re-timed to this film.
const MYTH_KEYS = [
  [CUE.forestIn - 0.5, L.forestIn - 0.5],
  [CUE.ignite, L.ignite],
  [CUE.burst, L.burst],
  [CUE.formDone, L.formDone],
  [CUE.disperse, L.disperse],
  [CUE.whip, L.whip],
];
export const mythT = (t) => pl(t, MYTH_KEYS);
// the bottle reveal runs a little faster than in the first film
const NIGHT_KEYS = [
  [CUE.bottleIn, L.bottleIn],
  [CUE.tahoe, L.bottleIn + (CUE.tahoe - CUE.bottleIn) * 1.18],
];

// --- the flight through the 1934 forest (legacy clock) ---------------------------
const FLY = { v: 3.1, accA: 3.4, accB: 5.4, decA: 9.4, decB: 12.6, creep: 0.2 };
const flyV = (t) =>
  FLY.v * smooth(remap(t, FLY.accA, FLY.accB)) * (1 - smooth(remap(t, FLY.decA, FLY.decB))) + FLY.creep * smooth(remap(t, FLY.decA, FLY.decB));
const Z_STEP = 1 / 240;
const Z_TABLE = (() => {
  const n = Math.ceil(L.whip / Z_STEP) + 2;
  const z = new Float64Array(n);
  for (let i = 1; i < n; i++) z[i] = z[i - 1] + 0.5 * (flyV((i - 1) * Z_STEP) + flyV(i * Z_STEP)) * Z_STEP;
  return z;
})();
const camZ = (t) => {
  const x = clamp(t, 0, L.whip) / Z_STEP;
  const i = Math.min(Z_TABLE.length - 2, Math.floor(x));
  return lerp(Z_TABLE[i], Z_TABLE[i + 1], x - i);
};
const STAG_Z = camZ(16.0) + 9.2;
const STAG = [pathX(STAG_Z), -0.82, STAG_Z];
const CLEARING = [pathX(STAG_Z + 1), STAG_Z + 1, 5.6, 6.6];

function forestCam(t) {
  const z = camZ(t);
  const arrive = smooth(remap(t, 9.2, 12.8));
  const yawAt = (tt) => {
    const zz = camZ(tt);
    const xx = pathX(zz) + 0.22 * Math.sin(tt * 0.37);
    const along = Math.atan(pathSlope(zz + 3.0)) * 0.85 + 0.03 * noise1(tt * 0.3, 4);
    const toStag = Math.atan2(STAG[0] - xx, STAG[2] - zz);
    return lerp(along, toStag, smooth(remap(tt, 9.2, 12.8)));
  };
  const yaw = yawAt(t);
  const roll = clamp(-0.5 * (yawAt(t + 0.15) - yawAt(t - 0.15)) / 0.3, -0.06, 0.06) * (1 - arrive * 0.8);
  const x = pathX(z) + 0.22 * Math.sin(t * 0.37);
  const y = lerp(-0.6, -0.08, smooth(remap(t, 4.0, 12.8))) + 0.035 * Math.sin(t * 1.9) * (flyV(t) / FLY.v);
  const tilt = lerp(0.045, 0.072, arrive) + 0.006 * noise1(t * 0.4, 12);
  return { cam: [x, y, z], yaw, roll, tilt };
}
const GLOW = (() => {
  const c = forestCam(15.0).cam;
  const k = (STAG_Z + 13 - c[2]) / (STAG_Z - c[2]);
  return [c[0] + (STAG[0] - c[0]) * k, 2.4, STAG_Z + 13];
})();

// --- Lake Tahoe: a flight through snowy pines towards the warm lights of a bar ---------
const TZ0 = 420;
const TV = 2.2;
function tahoeCam(t) {
  const u = t - CUE.tahoe;
  const z = TZ0 + TV * u + 0.25 * u * u;
  const x = pathX(z) + 0.15 * Math.sin(u * 0.5);
  const yaw = Math.atan(pathSlope(z + 3.0)) * 0.8 + 0.02 * noise1(u * 0.4, 7);
  const roll = clamp(-0.4 * (Math.atan(pathSlope(z + 3.4)) - Math.atan(pathSlope(z + 2.6))), -0.05, 0.05);
  return { cam: [x, -0.42 + 0.05 * u, z], yaw, roll, tilt: 0.05 + 0.004 * noise1(u * 0.5, 2) };
}
const BAR_Z = TZ0 + TV * 4.4 + 0.25 * 4.4 * 4.4 + 16;
const BAR = [pathX(BAR_Z), 0.3, BAR_Z];

// liquid act parameters (new clock)
function liquidParams(t) {
  const lt = t - CUE.whip;
  const fz = CUE.freeze - CUE.whip;
  const flow = lt < fz ? lt : fz + 1.1 * (1 - Math.exp(-(lt - fz) / 1.1));
  return {
    time: lt + 3.0,
    flow: flow + 3.0,
    freeze: ease.inOutSine(remap(t, CUE.freeze, CUE.freeze + 2.2)),
    frost: ease.inOutSine(remap(t, CUE.freeze + 0.2, CUE.freeze + 2.8)),
    frostText: remap(t, CUE.coldText, CUE.coldText + 1.6),
    push: lt + 3.0,
  };
}

// ---------------------------------------------------------------- the Jägerbomb
// Slow motion: physical time since the release, as a function of film time.
const HOVER_Y = 0.665; // bottom of the shot glass while it hovers, just above the rim
const FILL0 = 0.27; // drink level above the glass bottom before the drop
const YL0 = GLASS.yb + FILL0;
const T_HIT = Math.sqrt((2 * (HOVER_Y - YL0)) / GRAV); // physical fall time
const RATE_FALL = T_HIT / (CUE.hit - CUE.release);
const RATE_SLOW = 0.1;
const physRate = (t) => {
  if (t < CUE.release) return 0;
  if (t < CUE.hit) return RATE_FALL;
  return lerp(RATE_SLOW, 1.0, ease.inOutSine(remap(t, CUE.rampUp, CUE.rampUp + 1.4)));
};
const P_STEP = 1 / 240;
const P_TABLE = (() => {
  const n = Math.ceil((CUE.endcard + 1 - CUE.release) / P_STEP) + 2;
  const a = new Float64Array(n);
  for (let i = 1; i < n; i++) {
    const t0 = CUE.release + (i - 1) * P_STEP, t1 = t0 + P_STEP;
    a[i] = a[i - 1] + 0.5 * (physRate(t0 + 1e-6) + physRate(t1 - 1e-6)) * P_STEP;
  }
  return a;
})();
const physT = (t) => {
  if (t <= CUE.release) return 0;
  const x = (t - CUE.release) / P_STEP;
  const i = Math.min(P_TABLE.length - 2, Math.floor(x));
  return lerp(P_TABLE[i], P_TABLE[i + 1], x - i);
};

// The state of the drink τ physical seconds after the shot was let go from height y0.
function bombState(tau, y0 = HOVER_Y, opts = {}) {
  const fill0 = opts.fill0 ?? FILL0;
  const yl0 = GLASS.yb + fill0;
  const tHit = Math.sqrt((2 * (y0 - yl0)) / GRAV);
  const s = tau - tHit; // since impact
  let y, tilt = 0, dx = 0, shotFill = 0.13;
  if (s < 0) {
    y = y0 - 0.5 * GRAV * tau * tau;
    tilt = 0.02 * tau;
  } else {
    const v0 = GRAV * tHit;
    const a = 52;
    const sc = Math.min(s, v0 / a);
    const depth = v0 * sc - 0.5 * a * sc * sc;
    y = Math.max(GLASS.yb + 0.001, yl0 - depth);
    const landed = y <= GLASS.yb + 0.0011;
    // time since landing (approximate)
    const sl = landed ? s - (v0 - Math.sqrt(Math.max(0, v0 * v0 - 2 * a * (yl0 - GLASS.yb)))) / a : 0;
    if (landed) {
      tilt = 0.13 * (1 - Math.exp(-sl / 0.09)) + 0.03 * Math.exp(-sl / 0.25) * Math.sin(sl * 38);
      dx = 0.032 * (1 - Math.exp(-sl / 0.12));
      y += 0.004 * Math.exp(-sl / 0.06) * Math.abs(Math.sin(sl * 50));
    }
    shotFill = 0.13 - 0.1 * smooth(remap(s, 0.1, 2.2));
  }
  const sub = s > 0 ? smooth(remap(s, 0, 0.06)) : 0;
  return {
    shot: { on: true, pos: [dx, y, 0], axis: [Math.sin(tilt), Math.cos(tilt), 0], fill: shotFill, frost: 1 - 0.7 * sub },
    fill: fill0 + 0.028 * sub,
    splash: s > 0 ? [s, opts.strength ?? 1, 1, 0] : [0, 0, 0, 0],
    splashC: [0, 0, 0],
    plume: s > 0 ? [s, 1, 0.5 * smooth(remap(s, 0.2, 2.5)) + 0.2 * s, 2.5 * Math.exp(-s / 1.2)] : [0, 0, 0, 0],
    mix: s > 0 ? 0.8 * smooth(remap(s, 0.5, 4.0)) : 0,
    foam: 0.005 + (s > 0 ? 0.05 * smooth(remap(s, 0.05, 0.7)) - 0.018 * smooth(remap(s, 1.2, 4.0)) : 0),
    fizz: 0.5 + (s > 0 ? 2.0 * Math.exp(-s / 1.5) + 0.7 : 0),
    s,
  };
}

export class Director {
  constructor({ renderer, W, H, scenes, overlay, sceneRT, msaaRT }) {
    this.r = renderer;
    this.W = W;
    this.H = H;
    this.scenes = scenes;
    this.overlay = overlay;
    this.plainRT = sceneRT;
    this.msaaRT = msaaRT;
    this.rt = sceneRT;
    this.aspect = W / H;
    this.liquidRT = makeRT(W, H);
    this.copyRT = makeRT(W, H);
    this.liquidAt = null;
    this.black = new FSPass('out vec4 fragColor; void main(){ fragColor = vec4(0.0); }');
    this.copy = new FSPass('uniform sampler2D uImg; in vec2 vUv; out vec4 fragColor; void main(){ fragColor = texture(uImg, vUv); }', { uImg: { value: null } });
    this.bgDust = new FSPass(
      `uniform vec2 uRes; uniform float uAmt; in vec2 vUv; out vec4 fragColor;
       void main(){
         vec2 p = (gl_FragCoord.xy - 0.5 * uRes) / uRes.y;
         float g = exp(-dot(p - vec2(0.0, 0.08), p - vec2(0.0, 0.08)) * 3.0);
         vec3 c = vec3(0.010, 0.022, 0.017) * g + vec3(0.03, 0.016, 0.006) * exp(-dot(p - vec2(0.0, 0.1), p - vec2(0.0, 0.1)) * 9.0);
         fragColor = vec4(c * uAmt, 0.0);
       }`,
      { uRes: { value: new THREE.Vector2(W, H) }, uAmt: { value: 0 } },
      { blending: 'add' },
    );
  }

  clear() {
    this.black.render(this.r, this.rt);
    this.r.clear(false, true, false);
  }

  toUV(p) {
    return [0.5 + (p[0] * this.H) / this.W, 0.5 + p[1]];
  }
  // 1080p design px → uv
  pxUV(q) {
    return [q[0] / (1080 * this.aspect), 1 - q[1] / 1080];
  }

  frame(t) {
    const P = DEFAULT_POST();
    const info = {};
    this.overlay.begin();
    const bottle = (t >= CUE.shatter && t < CUE.tahoe) || t >= CUE.endcard;
    this.rt = bottle ? this.msaaRT : this.plainRT;
    this.clear();
    if (t < CUE.forestIn - 0.5) this.actOpen(t, P, info);
    else if (t < CUE.whip) this.actMyth(t, P, info);
    else if (t < CUE.shatter) this.actCraft(t, P, info);
    else if (t < CUE.tahoe) this.actNight(t, P, info);
    else if (t < CUE.fizz) this.actTahoe(t, P, info);
    else if (t < CUE.pour) this.actFizz(t, P, info);
    else if (t < CUE.endcard) this.actBomb(t, P, info);
    else this.actEnd(t, P, info);
    P.shake[0] += noise1(t * 0.35, 21) * 0.0016;
    P.shake[1] += noise1(t * 0.31, 42) * 0.0012;
    this.overlay.draw(t, info);
    return P;
  }

  // ------------------------------------------------------------------------
  // ACT 0: a single drop of liqueur falls into a dark pool; the title rises over the ripples
  actOpen(t, P, info) {
    const D = this.scenes.drop;
    const r = 0.011;
    const hit = CUE.dropHit;
    // the drop glides down in slow motion, accelerating into the surface
    const u = remap(t, 0.2, hit);
    const yc = lerp(0.16, r * 1.12, Math.pow(u, 1.35));
    const tau = t < hit ? 0 : (t - hit) * 0.26;
    const push = ease.inOutSine(remap(t, 0, 5.8));
    const cam = {
      pos: [lerp(0.05, 0.015, push), lerp(0.05, 0.034, push), lerp(0.36, 0.27, push)],
      target: [0, lerp(0.04, 0.012, push) + (t > hit ? 0 : 0.0), 0],
      fov: 22,
    };
    const fade = smooth(remap(t, CUE.openIn, CUE.openIn + 1.0)) * (1 - smooth(remap(t, 5.2, CUE.forestIn - 0.6)));
    D.render(this.rt, {
      mode: 'pool', cam, time: t, glass: false,
      drop: t < hit + 0.02 ? [0, yc, 0, r] : [0, 0, 0, 0],
      pool: [tau, 1, 0, 0],
      lights: [0.35, 1.5, 0.25, 0.7],
      keyAng: -0.7, reveal: fade, backY: 0.0, backSize: 0.1,
    });
    const hp = D.project([0, 0, 0]);
    const huv = this.pxUV(hp);
    if (t >= hit) {
      P.shock = [huv[0], huv[1], 0.7 * (t - hit), 0.7 * after(t, hit, 0.5)];
      P.shockLight = 0;
    }
    P.letterbox = LETTERBOX;
    P.bloom = 0.1;
    P.streak = 0.5;
    P.streakThreshold = 1.2;
    P.streakTint = [1.0, 0.6, 0.3];
    P.flashAmt = 0.14 * pulse(t, hit, 0.02, 0.14);
    P.flash = [1.0, 0.85, 0.65];
    P.ca = 0.012 + 0.03 * after(t, hit, 0.3);
    addShake(P, shake(t, hit, 0.004, 0.3));
    P.vignette = 0.7;
  }

  // ------------------------------------------------------------------------
  // ACT I: forest → stag → the light → 56 (The Hunter's Hour, on its own clock)
  actMyth(t, P, info) {
    const tl = mythT(t);
    info.tl = tl;
    const F = this.scenes.forest;
    const reveal = ease.inOutSine(remap(tl, L.forestIn - 0.5, L.forestIn + 1.6));
    const fc = forestCam(tl);
    const view = { cam: fc.cam, yaw: fc.yaw, roll: fc.roll, tilt: fc.tilt };
    const CXd = 960 * (this.aspect / (16 / 9));
    const sp = F.project(STAG, view);
    const designX = CXd + sp[0] * 1080;
    const designY = 540 - sp[1] * 1080;
    const scale = 7.4 / sp[2];
    info.stag = { x: designX, y: designY, scale, alpha: 1 };
    const so = stagProjector(stagPose(tl))(0, -404, false, -40);
    const starP = [(designX + so[0] * scale - CXd) / 1080, (540 - (designY + so[1] * scale)) / 1080];
    const cr = Math.cos(fc.roll), sr = Math.sin(fc.roll);
    const starRaw = [cr * starP[0] - sr * starP[1], sr * starP[0] + cr * starP[1] + fc.tilt];
    const glowRaw = F.projRaw(GLOW, view);
    const glowP = F.toScreen(glowRaw, view);

    let star = 0.0;
    star += 0.06 * smooth(remap(tl, L.stagDone - 0.6, L.ignite));
    star += 1.15 * (tl >= L.ignite ? Math.exp(-(tl - L.ignite) / 0.5) * 0.55 + 0.45 : 0) * (tl < L.burst ? 1 : 0);
    star *= tl < L.burst ? 1 - 0.55 * Math.exp(-Math.pow((tl - (L.burst - 0.05)) / 0.18, 2)) : 1;
    if (tl >= L.burst) star = 3.2 * Math.exp(-(tl - L.burst) / 0.22);
    star *= clamp(remap(tl, L.ignite - 0.05, L.ignite)) * 0.95 + 0.05;
    const starSize = 1.0 + 0.25 * after(tl, L.ignite, 0.6) + (tl >= L.burst ? 1.3 * (1 - Math.exp(-(tl - L.burst) / 0.15)) : 0);
    const moonI = (0.85 - 0.4 * smooth(remap(tl, L.stagStart, L.stagDone))) * (1 - 0.6 * smooth(remap(tl, L.ignite - 0.2, L.ignite + 0.4)));
    const dim = 1 - ease.inOutCubic(remap(tl, L.burst + 0.05, L.burst + 2.2));
    const fogMore = 1 + 0.5 * smooth(remap(tl, L.stagStart, L.ignite)) + 0.8 * smooth(remap(tl, L.burst, L.burst + 2));
    const forestOn = dim > 0.001;
    if (forestOn) {
      F.render(this.rt, {
        time: tl, ...view, fog: fogMore, reveal: reveal * dim,
        moon: [glowRaw[0], glowRaw[1], moonI, 0.02],
        star: [starRaw[0], starRaw[1], star, starSize],
        clearing: CLEARING,
        embers: (0.55 + 1.85 * reveal) * (1 - 0.6 * remap(tl, L.burst, L.burst + 2)) * smooth(remap(t, CUE.forestIn - 0.5, CUE.forestIn + 1.0)),
        focus: 6.0 + 3.0 * smooth(remap(tl, 9, 13)),
        emberFar: lerp(0.13, 0.035, reveal),
        snow: 0,
      });
    }
    if (tl >= L.burst - 0.02) {
      const bu = this.bgDust.uniforms;
      bu.uAmt.value = smooth(remap(tl, L.burst + 0.6, L.burst + 2.4));
      if (bu.uAmt.value > 0) this.bgDust.render(this.r, this.rt);
      this.scenes.particles.render(this.rt, { time: tl - L.burst, origin: starP, trail: 0.04 });
    }
    const starUV = this.toUV(starP);
    if (tl < L.ignite) {
      P.rays = forestOn ? 1.2 * reveal : 0;
      P.raysPos = this.toUV(glowP);
      P.raysDecay = 0.968;
      P.raysDensity = 0.95;
      P.raysThreshold = 0.04;
      P.raysTint = [0.8, 1.0, 0.9];
    } else {
      P.rays = 0.3 * after(tl, L.ignite, 1.0) * (tl < L.burst + 0.8 ? 1 : 0) + 0.25 * reveal * dim;
      P.raysPos = starUV;
      P.raysDecay = 0.97;
      P.raysDensity = 1.0;
      P.raysThreshold = 1.4;
      P.raysTint = [1.0, 0.75, 0.45];
    }
    if (tl >= L.ignite && tl < L.burst) P.shock = [starUV[0], starUV[1], 0.9 * (tl - L.ignite), 0.9 * after(tl, L.ignite, 0.45)];
    if (tl >= L.burst) P.shock = [starUV[0], starUV[1], 1.5 * (tl - L.burst), 1.6 * after(tl, L.burst, 0.55)];
    if (tl >= L.burst) P.radial = [starUV[0], starUV[1], 0.22 * after(tl, L.burst, 0.22)];
    P.ghosts = 0.3 * smooth(remap(tl, L.ignite - 0.1, L.ignite + 0.1)) * (1 - smooth(remap(tl, L.burst + 0.3, L.burst + 1.5)));
    P.glowGain = 2.4;
    P.bloom = 0.11 + 0.02 * after(tl, L.ignite, 0.8);
    P.streak = 0.55 * smooth(remap(tl, L.ignite - 0.05, L.ignite + 0.05)) + (tl > L.burst ? 0.35 : 0);
    P.streakThreshold = 1.4;
    P.streakTint = [1.0, 0.6, 0.28];
    P.flashAmt = 0.06 * pulse(tl, L.ignite, 0.04, 0.15) + 0.2 * pulse(tl, L.burst, 0.04, 0.16);
    P.flash = [1.0, 0.9, 0.75];
    P.ca = 0.012 + 0.04 * after(tl, L.ignite, 0.35) + 0.08 * after(tl, L.burst, 0.3);
    addShake(P, shake(tl, L.ignite, 0.005, 0.35));
    addShake(P, shake(tl, L.burst, 0.012, 0.4));
    P.letterbox = LETTERBOX;
    P.slope = [0.98, 1.02, 1.0];
    P.whip = 0.32 * ease.inCubic(remap(tl, L.whip - 0.32, L.whip));
  }

  // ------------------------------------------------------------------------
  // ACT I: a year in oak → ice cold → the ice cracks
  actCraft(t, P, info) {
    const Lq = this.scenes.liquid;
    const lp = liquidParams(t);
    const freeze = lp.freeze;
    if (t < CUE.crack) Lq.render(this.rt, lp);
    else {
      Lq.render(this.liquidRT, lp);
      this.liquidAt = t;
      this.scenes.shards.render(this.rt, { image: this.liquidRT.texture, u: t - CUE.shatter, crack: remap(t, CUE.crack, CUE.shatter) });
    }
    P.whip = -0.32 * (1 - ease.outCubic(remap(t, CUE.whip, CUE.whip + 0.4)));
    P.letterbox = LETTERBOX;
    P.bloom = 0.1 + 0.05 * freeze;
    P.bloomThreshold = 0.9;
    P.streak = 0.32 + 0.4 * freeze + 1.2 * smooth(remap(t, CUE.crack, CUE.shatter));
    P.streakThreshold = 1.4;
    P.streakTint = [lerp(1.0, 0.55, freeze), lerp(0.62, 0.85, freeze), lerp(0.3, 1.0, freeze)];
    P.glowGain = 2.0;
    P.slope = [lerp(1.0, 0.94, freeze), 1.0, lerp(1.0, 1.08, freeze)];
    P.highTint = [lerp(0.014, -0.01, freeze), 0.004, lerp(-0.012, 0.016, freeze)];
    P.sat = lerp(1.04, 0.92, freeze);
    P.ca = 0.012 + 0.04 * smooth(remap(t, CUE.crack, CUE.shatter));
    P.ghosts = 0.12 * smooth(remap(t, CUE.crack, CUE.shatter));
    addShake(P, shake(t, CUE.crack + 0.05, 0.004, 0.5, 30));
    P.flashAmt = 0.12 * pulse(t, CUE.crack + 0.02, 0.02, 0.12);
    P.flash = [0.92, 0.97, 1.0];
  }

  // ------------------------------------------------------------------------
  // ACT I: the ice explodes and reveals the bottle, then a whip-pan to America
  actNight(t, P, info) {
    const B = this.scenes.bottle;
    const tb = pl(t, NIGHT_KEYS);
    const u = ease.inOutCubic(remap(tb, L.bottleIn - 0.3, L.drop + 0.4));
    const ang = lerp(1.25, -0.4, u);
    const rad = lerp(0.95, 2.35, u);
    const h = lerp(0.42, 0.52, u) + 0.12 * Math.sin(Math.PI * u);
    const cam = { pos: [Math.sin(ang) * rad, h, Math.cos(ang) * rad], target: [0, lerp(0.7, 0.52, u), 0], fov: lerp(24, 30, u) };
    const rotY = lerp(0.25, 0.0, u);
    const reveal = smooth(remap(t, CUE.bottleIn + 0.05, CUE.bottleIn + 1.0));
    const keyAng = lerp(-2.2, 0.9, ease.inOutSine(remap(tb, L.bottleIn, L.drop)));
    const back = 0.25 + 0.5 * smooth(remap(t, CUE.bottleIn + 0.4, CUE.tahoe - 0.5));
    const swirl = 0.45 * (tb - L.bottleIn);
    const orb = 0.5 * smooth(remap(t, CUE.bottleIn + 0.5, CUE.bottleIn + 2.5));
    B.render(this.rt, { time: tb, cam, rotY, reveal, keyAng, sweep: -1, back, beat: 0, smoke: 1.0, swirl, orbit: orb * 0.75, rise: 0 });
    const su = t - CUE.shatter;
    if (su < 2.0) {
      if (this.liquidAt !== CUE.shatter) {
        this.scenes.liquid.render(this.liquidRT, liquidParams(CUE.shatter));
        this.liquidAt = CUE.shatter;
      }
      this.scenes.shards.render(this.rt, { image: this.liquidRT.texture, u: su, crack: 1 });
    }
    const impactUV = this.toUV(IMPACT);
    if (su < 1.5) {
      P.shock = [impactUV[0], impactUV[1], 1.3 * su, 1.2 * after(t, CUE.shatter, 0.5)];
      P.shockLight = 0;
      P.radial = [impactUV[0], impactUV[1], 0.07 * after(t, CUE.shatter, 0.2)];
    }
    P.rays = 0.9 * reveal;
    P.raysPos = B.glowUV;
    P.raysDecay = 0.965;
    P.raysDensity = 0.9;
    P.raysThreshold = 0.03;
    P.raysTint = [1.0, 0.72, 0.42];
    P.letterbox = LETTERBOX;
    P.flashAmt = 0.16 * pulse(t, CUE.shatter, 0.02, 0.1);
    P.flash = [0.92, 0.97, 1.0];
    P.bloom = 0.09;
    P.bloomThreshold = 1.1;
    P.streak = 0.45 + 0.8 * after(t, CUE.shatter, 0.5);
    P.streakThreshold = 2.0;
    P.streakTint = t < CUE.shatter + 1.0 ? [0.7, 0.85, 1.0] : [1.0, 0.66, 0.36];
    P.ghosts = 0.1 + 0.15 * after(t, CUE.shatter, 0.6);
    P.glowGain = 1.8;
    P.ca = 0.01 + 0.07 * after(t, CUE.shatter, 0.3);
    addShake(P, shake(t, CUE.shatter, 0.012, 0.35));
    P.whip = 0.32 * ease.inCubic(remap(t, CUE.tahoe - 0.32, CUE.tahoe));
  }

  // ------------------------------------------------------------------------
  // ACT II: decades later, snowy pines by Lake Tahoe; the warm lights of a bar ahead
  actTahoe(t, P, info) {
    const F = this.scenes.forest;
    const fc = tahoeCam(t);
    const view = { cam: fc.cam, yaw: fc.yaw, roll: fc.roll, tilt: fc.tilt };
    const glowRaw = F.projRaw(BAR, view);
    const glowP = F.toScreen(glowRaw, view);
    const u = t - CUE.tahoe;
    const toLight = smooth(remap(t, CUE.fizz - 1.0, CUE.fizz));
    F.render(this.rt, {
      time: 40 + u, ...view, fog: 1.25, reveal: 1,
      moon: [glowRaw[0], glowRaw[1], 0.75 + 0.6 * smooth(remap(u, 1.5, 4.2)), 0.02],
      star: [0, 0, 0, 1],
      clearing: [BAR[0], BAR[2] + 2, 4.0, 5.0],
      embers: 1.6,
      focus: 5.0,
      emberFar: 0.02,
      snow: 1,
    });
    P.rays = 0.7 + 0.6 * toLight;
    P.raysPos = this.toUV(glowP);
    P.raysDecay = 0.97;
    P.raysDensity = 0.95;
    P.raysThreshold = 0.04;
    P.raysTint = [1.0, 0.72, 0.42];
    P.letterbox = LETTERBOX;
    P.bloom = 0.12;
    P.streak = 0.25;
    P.streakThreshold = 1.2;
    P.slope = [0.95, 1.0, 1.06];
    P.shadowTint = [-0.004, 0.0, 0.008];
    P.highTint = [0.014, 0.004, -0.01];
    P.whip = -0.32 * (1 - ease.outCubic(remap(t, CUE.tahoe, CUE.tahoe + 0.4)));
    // into the light
    P.exposure = 1.0 + 1.6 * ease.inCubic(toLight);
    P.flashAmt = 0.5 * ease.inCubic(remap(t, CUE.fizz - 0.35, CUE.fizz));
    P.flash = [1.0, 0.85, 0.6];
  }

  // ------------------------------------------------------------------------
  // ACT II: a new kind of energy — inside the golden drink
  actFizz(t, P, info) {
    const u = t - CUE.fizz;
    const span = CUE.pour - CUE.fizz;
    const energy = 0.15 + 0.85 * smooth(remap(t, CUE.vo.energy + 0.9, CUE.vo.energy + 1.6));
    this.scenes.fizz.render(this.rt, {
      time: u * 0.9 + 0.4 * Math.max(0, u - 1.0) ** 2,
      rise: u * 0.12,
      energy,
      reveal: 1,
      focus: 1.0,
      surface: lerp(0.95, 0.36, ease.inOutSine(remap(u, 0.6, span))),
    });
    P.rays = 0.9;
    P.raysPos = [0.5, 1.15];
    P.raysDecay = 0.975;
    P.raysDensity = 1.0;
    P.raysThreshold = 0.25;
    P.raysTint = [1.0, 0.78, 0.42];
    P.letterbox = LETTERBOX;
    P.bloom = 0.14;
    P.bloomThreshold = 0.8;
    P.streak = 0.5;
    P.streakThreshold = 1.0;
    P.streakTint = [1.0, 0.72, 0.36];
    P.flashAmt = 0.5 * Math.exp(-u / 0.25) + 0.35 * ease.inCubic(remap(t, CUE.pour - 0.25, CUE.pour));
    P.flash = [1.0, 0.86, 0.6];
    P.ca = 0.02;
    P.vignette = 0.7;
    P.sat = 1.08;
  }

  // ------------------------------------------------------------------------
  // ACT II/III: the pour, the hover, the drop, the beat
  actBomb(t, P, info) {
    const D = this.scenes.drop;
    const base = { time: t, cold: 1, lights: [1, 1, 1, 1], keyAng: -0.7 };
    let s, cam;
    P.letterbox = LETTERBOX;
    P.bloom = 0.1;
    P.bloomThreshold = 1.0;
    P.streak = 0.45;
    P.streakThreshold = 1.5;
    P.streakTint = [1.0, 0.64, 0.32];
    P.vignette = 0.62;
    P.glowGain = 1.6;
    if (t < CUE.hover) {
      // the pour
      const u = remap(t, CUE.pour, CUE.hover);
      const stop = CUE.hover - 0.6;
      const top = t < stop ? 1.4 : 1.4 - 0.5 * GRAV * 0.04 * (t - stop) ** 2 * 10;
      const fill = lerp(0.12, FILL0, ease.outCubic(u));
      s = {
        ...base, fill, foam: 0.008 + 0.01 * u, fizz: 0.9 + 0.5 * u, mix: 0,
        pour: t < CUE.hover - 0.1 ? [1, 0.011, Math.max(top, GLASS.yb + fill + 0.002), t] : [0, 0, 0, 0],
      };
      cam = orbit(lerp(-0.42, -0.2, ease.inOutSine(u)), lerp(2.15, 1.95, u), lerp(0.3, 0.36, u), lerp(0.33, 0.35, u), 30);
      P.flashAmt = 0.3 * Math.exp(-(t - CUE.pour) / 0.2);
    } else if (t < CUE.slam) {
      const tau = physT(t);
      const st = bombState(tau);
      if (t < CUE.release) {
        // the shot glass is lowered into frame and hangs over the glass
        const u = ease.outCubic(remap(t, CUE.hover, CUE.hover + 2.4));
        const y = lerp(1.2, HOVER_Y, u) + 0.004 * Math.sin(t * 1.3);
        st.shot.pos = [0.003 * Math.sin(t * 0.9), y, 0.002 * Math.cos(t * 1.1)];
        st.shot.axis = [0.015 * Math.sin(t * 0.8 + 1), 1, 0.01 * Math.sin(t * 0.6)];
      }
      s = { ...base, ...st };
      // camera: a slow push towards the shot, following it down, then orbiting the impact in slow motion
      if (t < CUE.hit) {
        const u = ease.inOutSine(remap(t, CUE.hover, CUE.release));
        const fall = ease.inOutSine(remap(t, CUE.release - 0.3, CUE.hit + 0.2));
        cam = orbit(lerp(0.14, 0.0, u), lerp(2.75, 2.35, u) - 0.75 * fall, lerp(0.47, 0.46, u) - 0.04 * fall, lerp(0.44, 0.43, u) - 0.06 * fall, 30);
      } else if (t < CUE.rampUp) {
        const u = ease.inOutSine(remap(t, CUE.hit, CUE.rampUp));
        cam = orbit(lerp(0.0, 0.95, u), lerp(1.45, 1.2, u), lerp(0.46, 0.44, u), lerp(0.4, 0.37, u), 30);
      } else {
        const u = ease.inOutSine(remap(t, CUE.rampUp, CUE.slam));
        cam = orbit(lerp(0.95, 1.25, u), lerp(1.2, 1.75, u), lerp(0.44, 0.38, u), lerp(0.37, 0.33, u), 30);
      }
      const hp = D.project([0, YL0, 0]);
      const huv = this.pxUV(hp);
      const ss = st.s;
      if (t >= CUE.hit) {
        P.shock = [huv[0], huv[1], 0.5 * (t - CUE.hit), 0.6 * after(t, CUE.hit, 0.5)];
        P.shockLight = 0;
      }
      P.flashAmt = 0.25 * pulse(t, CUE.hit, 0.02, 0.18);
      P.flash = [1.0, 0.86, 0.66];
      P.streak = 0.45 + 0.6 * after(t, CUE.hit, 0.8);
      P.ca = 0.012 + 0.05 * after(t, CUE.hit, 0.4);
      addShake(P, shake(t, CUE.hit, 0.006, 0.4));
      s.lights = [1, 1 + 1.2 * after(t, CUE.hit, 0.6), 1, 1];
      if (ss > 0) s.fizz += 0.5;
    } else {
      // the beat: a montage cut to the music
      const k = CUE.cuts.findIndex((c, i) => t >= c && (i === CUE.cuts.length - 1 || t < CUE.cuts[i + 1]));
      const c0 = CUE.cuts[k];
      const u = remap(t, c0, k < CUE.cuts.length - 1 ? CUE.cuts[k + 1] : CUE.endcard);
      const bt = ((t - CUE.slam) * CUE.bpm) / 60;
      const beat = Math.exp(-((bt % 1) / 0.12));
      info.beat = beat;
      if (k === 0) {
        // JÄGERBOMB: a low hero orbit of the finished drink
        const st = bombState(physT(t));
        s = { ...base, ...st };
        cam = orbit(lerp(-0.5, -0.1, ease.outCubic(u)), lerp(1.55, 1.7, u), 0.16, 0.34, 30);
      } else if (k === 1) {
        // "One shot." — the frosted shot glass, alone on the bar
        s = { ...base, glass: false, fill: 0, shot: { on: true, pos: [0, 0, 0], axis: [0, 1, 0], fill: 0.13, frost: 1 }, mix: 0, fizz: 0 };
        cam = orbit(lerp(0.35, 0.1, ease.inOutSine(u)), lerp(1.12, 1.0, u), lerp(0.22, 0.19, u), 0.11, 26);
        s.backY = 0.1;
        s.backSize = 0.16;
        info.callout = { i: 0, u, anchor: D.project([0.055, 0.15, 0.03]), side: 1 };
      } else if (k === 2) {
        // "Ice cold." — condensation on the glass, in macro
        s = { ...base, fill: FILL0, foam: 0.006, fizz: 1.0, mix: 0, lights: [0.8, 1, 0.7, 1] };
        cam = orbit(lerp(-0.25, -0.12, u), 0.36, lerp(0.22, 0.25, u), lerp(0.22, 0.24, u), 26);
        info.callout = { i: 1, u, anchor: [1080 * this.aspect * 0.52, 640], side: 1 };
      } else if (k === 3) {
        // "Drop it." — from above: the shot plunges into the gold
        const th = Math.sqrt((2 * (0.95 - YL0)) / GRAV);
        const tau = th - 0.025 + (t - c0) * 0.13;
        const st = bombState(tau, 0.95);
        s = { ...base, ...st };
        cam = { pos: [0.04, 1.45 - 0.08 * u, 0.62], target: [0, 0.3, 0], fov: 24, roll: 0.0 };
        s.backY = 0.0;
        info.callout = { i: 2, u, anchor: D.project([0, YL0, 0]), side: -1 };
      } else {
        // the finished Jägerbomb, the camera rising
        const st = bombState(physT(t));
        s = { ...base, ...st };
        cam = orbit(lerp(0.3, 0.5, u), lerp(1.8, 2.0, u), lerp(0.3, 0.55, ease.inOutSine(u)), lerp(0.33, 0.36, u), 30);
      }
      const lb = s.lights ? s.lights[2] : 1;
      s.lights = [1, 1 + 0.8 * beat, lb * (1 + 0.15 * beat), 1];
      P.flashAmt = 0.55 * pulse(t, CUE.slam, 0.02, 0.2) + 0.18 * pulse(t, c0, 0.01, 0.08) * (k > 0 ? 1 : 0) + 0.35 * ease.inCubic(remap(t, CUE.endcard - 0.2, CUE.endcard));
      P.flash = [1.0, 0.86, 0.66];
      P.letterbox = LETTERBOX * (1 - ease.outExpo(remap(t, CUE.slam, CUE.slam + 0.45)));
      P.exposure = 1.0 + 0.1 * beat;
      P.ca = 0.012 + 0.06 * after(t, CUE.slam, 0.3) + 0.03 * after(t, c0, 0.15);
      P.streak = 0.55 + 0.4 * after(t, CUE.slam, 0.6);
      addShake(P, shake(t, CUE.slam, 0.01, 0.3));
      addShake(P, [noise1(t * 40, 1) * 0.0012 * beat, noise1(t * 40, 2) * 0.0012 * beat]);
      if (k === 0) P.radial = [0.5, 0.45, 0.12 * after(t, CUE.slam, 0.2)];
    }
    s.cam = cam;
    D.render(this.rt, s);
    if (t < CUE.slam && t >= CUE.hover) info.shotUV = this.pxUV(D.project(s.shot.pos));
  }

  // ------------------------------------------------------------------------
  // END: the bottle and the Jägerbomb; the wordmark
  actEnd(t, P, info) {
    const B = this.scenes.bottle;
    const u = ease.outCubic(remap(t, CUE.endcard, CUE.fadeDone + 1));
    const off = -0.64 * (this.aspect / (16 / 9));
    const cam = { pos: [off, 0.42, lerp(3.25, 3.0, u)], target: [off, lerp(0.48, 0.5, u), 0], fov: 30 };
    const rotY = lerp(-0.32, -0.2, u);
    const sweep = remap(t, CUE.endcard + 0.1, CUE.endcard + 1.6);
    B.render(this.rt, { time: t, cam, rotY, reveal: 1, keyAng: 0.9, sweep, back: 0.8, beat: 0, smoke: 1.0, swirl: 0.45 * (t - CUE.endcard) + 4, orbit: 0.15, rise: 0 });
    // the finished drink stands in front of the bottle, composited over it
    this.copy.uniforms.uImg.value = this.rt.texture;
    this.copy.render(this.r, this.copyRT);
    const st = bombState(6 + (t - CUE.endcard));
    this.scenes.drop.render(this.rt, {
      ...st, time: t, cam, cold: 1, lights: [0.9, 1.1, 0.85, 0.6], keyAng: -0.7,
      glassPos: [0.34, 0, 0.3], bg: this.copyRT.texture, reveal: smooth(remap(t, CUE.endcard - 0.05, CUE.endcard + 0.5)),
    });
    info.endX = 960 * (this.aspect / (16 / 9)) - 360;
    P.rays = 0.6;
    P.raysPos = B.glowUV;
    P.raysDecay = 0.965;
    P.raysDensity = 0.9;
    P.raysThreshold = 0.03;
    P.raysTint = [1.0, 0.72, 0.42];
    P.letterbox = 0;
    P.flashAmt = 0.3 * pulse(t, CUE.endcard, 0.02, 0.25);
    P.flash = [1.0, 0.86, 0.7];
    P.bloom = 0.09;
    P.bloomThreshold = 1.1;
    P.streak = 0.4;
    P.streakThreshold = 2.0;
    P.ghosts = 0.08;
    P.glowGain = 1.8;
    P.ca = 0.01 + 0.04 * after(t, CUE.endcard, 0.3);
    addShake(P, shake(t, CUE.endcard, 0.004, 0.3));
    P.vignette = 0.7;
    P.fade = smooth(remap(t, CUE.fadeOut, CUE.fadeDone));
  }
}
