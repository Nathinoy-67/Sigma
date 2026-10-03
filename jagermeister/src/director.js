import * as THREE from 'three';
import { CUE } from './timeline.js';
import { DEFAULT_POST } from './post.js';
import { clamp, lerp, remap, ease, noise1, smooth, FSPass, makeRT } from './gl.js';
import { pathX, pathSlope } from './scenes/forest.js';
import { IMPACT } from './scenes/shards.js';
import { stagPose, stagProjector } from './overlay.js';

// The director decides, for any time t, what is on screen: which scenes render,
// where the cameras are, the post-processing look and what the typography layer draws.

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
const LETTERBOX = 0.128;

// --- the flight through the forest -------------------------------------------------
const FLY = { v: 3.1, accA: 3.4, accB: 5.4, decA: 9.4, decB: 12.6, creep: 0.2 };
const flyV = (t) =>
  FLY.v * smooth(remap(t, FLY.accA, FLY.accB)) * (1 - smooth(remap(t, FLY.decA, FLY.decB))) + FLY.creep * smooth(remap(t, FLY.decA, FLY.decB));
const Z_STEP = 1 / 240;
const Z_TABLE = (() => {
  const n = Math.ceil(CUE.whip / Z_STEP) + 2;
  const z = new Float64Array(n);
  for (let i = 1; i < n; i++) z[i] = z[i - 1] + 0.5 * (flyV((i - 1) * Z_STEP) + flyV(i * Z_STEP)) * Z_STEP;
  return z;
})();
const camZ = (t) => {
  const x = clamp(t, 0, CUE.whip) / Z_STEP;
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

// the light glows deep beyond the clearing, on the line of sight through the stag
const GLOW = (() => {
  const c = forestCam(15.0).cam;
  const k = (STAG_Z + 13 - c[2]) / (STAG_Z - c[2]);
  return [c[0] + (STAG[0] - c[0]) * k, 2.4, STAG_Z + 13];
})();

// liquid act parameters as a function of time
function liquidParams(t) {
  const lt = t - CUE.whip;
  const fz = CUE.freeze - CUE.whip;
  const flow = lt < fz ? lt : fz + 1.1 * (1 - Math.exp(-(lt - fz) / 1.1));
  return {
    time: lt,
    flow,
    freeze: ease.inOutSine(remap(t, CUE.freeze, CUE.freeze + 2.6)),
    frost: ease.inOutSine(remap(t, CUE.freeze + 0.2, CUE.freeze + 3.4)),
    frostText: remap(t, CUE.frostText, CUE.frostText + 1.9),
    push: lt,
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
    this.liquidAt = null;
    this.black = new FSPass('out vec4 fragColor; void main(){ fragColor = vec4(0.0); }');
    // soft, dark green haze behind the 56 (additive)
    this.bgDust = new FSPass(
      `uniform vec2 uRes; uniform float uAmt, uTime; in vec2 vUv; out vec4 fragColor;
       void main(){
         vec2 p = (gl_FragCoord.xy - 0.5 * uRes) / uRes.y;
         float g = exp(-dot(p - vec2(0.0, 0.08), p - vec2(0.0, 0.08)) * 3.0);
         vec3 c = vec3(0.010, 0.022, 0.017) * g + vec3(0.03, 0.016, 0.006) * exp(-dot(p - vec2(0.0, 0.1), p - vec2(0.0, 0.1)) * 9.0);
         fragColor = vec4(c * uAmt, 0.0);
       }`,
      { uRes: { value: new THREE.Vector2(W, H) }, uAmt: { value: 0 }, uTime: { value: 0 } },
      { blending: 'add' },
    );
  }

  clear() {
    // a black full-screen pass (rather than clear()) so the MSAA target is always resolved
    this.black.render(this.r, this.rt);
    this.r.clear(false, true, false);
  }

  // p-space (y up, units of screen height) → uv
  toUV(p) {
    return [0.5 + (p[0] * this.H) / this.W, 0.5 + p[1]];
  }

  frame(t) {
    const P = DEFAULT_POST();
    const info = {};
    this.overlay.begin();
    // only the bottle needs multisampling; the procedural acts render single-sampled
    this.rt = t >= CUE.shatter ? this.msaaRT : this.plainRT;
    this.clear();
    if (t < CUE.whip) this.actMyth(t, P, info);
    else if (t < CUE.shatter) this.actCraft(t, P, info);
    else this.actNight(t, P, info);
    // gentle handheld drift for the whole film
    P.shake[0] += noise1(t * 0.35, 21) * 0.0016;
    P.shake[1] += noise1(t * 0.31, 42) * 0.0012;
    this.overlay.draw(t, info);
    return P;
  }

  // ------------------------------------------------------------------------
  // ACT 0 + I: title → flight through the forest → stag → Hubertus light → burst into 56 botanicals
  actMyth(t, P, info) {
    const F = this.scenes.forest;
    const reveal = ease.inOutSine(remap(t, CUE.forestIn - 0.5, CUE.forestIn + 1.6));
    const fc = forestCam(t);
    const view = { cam: fc.cam, yaw: fc.yaw, roll: fc.roll, tilt: fc.tilt };
    const CXd = 960 * (this.aspect / (16 / 9));

    // the stag stands in the clearing
    const sp = F.project(STAG, view);
    const designX = CXd + sp[0] * 1080;
    const designY = 540 - sp[1] * 1080;
    const scale = 7.4 / sp[2];
    info.stag = { x: designX, y: designY, scale, alpha: 1 };
    // the Hubertus light ignites between its antlers
    const so = stagProjector(stagPose(t))(0, -404, false, -40);
    const starP = [(designX + so[0] * scale - CXd) / 1080, (540 - (designY + so[1] * scale)) / 1080];
    const cr = Math.cos(fc.roll), sr = Math.sin(fc.roll);
    const starRaw = [cr * starP[0] - sr * starP[1], sr * starP[0] + cr * starP[1] + fc.tilt];
    info.starP = starP;
    const glowRaw = F.projRaw(GLOW, view);
    const glowP = F.toScreen(glowRaw, view);

    // Hubertus light envelope
    let star = 0.0;
    star += 0.06 * smooth(remap(t, CUE.stagDone - 0.6, CUE.ignite));
    star += 1.15 * (t >= CUE.ignite ? Math.exp(-(t - CUE.ignite) / 0.5) * 0.55 + 0.45 : 0) * (t < CUE.burst ? 1 : 0);
    star *= t < CUE.burst ? 1 - 0.55 * Math.exp(-Math.pow((t - (CUE.burst - 0.05)) / 0.18, 2)) : 1; // inhale before the burst
    if (t >= CUE.burst) star = 3.2 * Math.exp(-(t - CUE.burst) / 0.22);
    star *= clamp(remap(t, CUE.ignite - 0.05, CUE.ignite)) * 0.95 + 0.05;
    const starSize = 1.0 + 0.25 * after(t, CUE.ignite, 0.6) + (t >= CUE.burst ? 1.3 * (1 - Math.exp(-(t - CUE.burst) / 0.15)) : 0);
    const moonI = (0.85 - 0.4 * smooth(remap(t, CUE.stagStart, CUE.stagDone))) * (1 - 0.6 * smooth(remap(t, CUE.ignite - 0.2, CUE.ignite + 0.4)));

    const dim = 1 - ease.inOutCubic(remap(t, CUE.burst + 0.05, CUE.burst + 2.2));
    const fogMore = 1 + 0.5 * smooth(remap(t, CUE.stagStart, CUE.ignite)) + 0.8 * smooth(remap(t, CUE.burst, CUE.burst + 2));
    const forestOn = dim > 0.001;
    if (forestOn) {
      F.render(this.rt, {
        time: t,
        ...view,
        fog: fogMore,
        reveal: reveal * dim,
        moon: [glowRaw[0], glowRaw[1], moonI, 0.02],
        star: [starRaw[0], starRaw[1], star, starSize],
        clearing: CLEARING,
        embers: (0.55 + 1.85 * reveal) * (1 - 0.6 * remap(t, CUE.burst, CUE.burst + 2)) * smooth(remap(t, 0.3, 2.0)),
        focus: 6.0 + 3.0 * smooth(remap(t, 9, 13)),
        // far embers bunch up at the vanishing point: keep them faint while the title is up
        emberFar: lerp(0.13, 0.035, reveal),
      });
    }

    // botanicals: particle burst from the light, forming "56"
    if (t >= CUE.burst - 0.02) {
      const bu = this.bgDust.uniforms;
      bu.uAmt.value = smooth(remap(t, CUE.burst + 0.6, CUE.burst + 2.4));
      bu.uTime.value = t;
      if (bu.uAmt.value > 0) this.bgDust.render(this.r, this.rt);
      this.scenes.particles.render(this.rt, { time: t - CUE.burst, origin: starP, trail: 0.04 });
    }

    // ---- post
    const starUV = this.toUV(starP);
    if (t < CUE.ignite) {
      P.rays = forestOn ? 1.2 * reveal : 0;
      P.raysPos = this.toUV(glowP);
      P.raysDecay = 0.968;
      P.raysDensity = 0.95;
      P.raysThreshold = 0.04;
      P.raysTint = [0.8, 1.0, 0.9];
    } else {
      P.rays = 0.3 * after(t, CUE.ignite, 1.0) * (t < CUE.burst + 0.8 ? 1 : 0) + 0.25 * reveal * dim;
      P.raysPos = starUV;
      P.raysDecay = 0.97;
      P.raysDensity = 1.0;
      P.raysThreshold = 1.4;
      P.raysTint = [1.0, 0.75, 0.45];
    }
    // shockwaves from the light: one on ignition, a bigger one on the burst
    if (t >= CUE.ignite && t < CUE.burst) P.shock = [starUV[0], starUV[1], 0.9 * (t - CUE.ignite), 0.9 * after(t, CUE.ignite, 0.45)];
    if (t >= CUE.burst) P.shock = [starUV[0], starUV[1], 1.5 * (t - CUE.burst), 1.6 * after(t, CUE.burst, 0.55)];
    if (t >= CUE.burst) P.radial = [starUV[0], starUV[1], 0.22 * after(t, CUE.burst, 0.22)];
    P.ghosts = 0.3 * smooth(remap(t, CUE.ignite - 0.1, CUE.ignite + 0.1)) * (1 - smooth(remap(t, CUE.burst + 0.3, CUE.burst + 1.5)));
    P.glowGain = 2.4;
    P.bloom = 0.11 + 0.02 * after(t, CUE.ignite, 0.8);
    P.streak = 0.55 * smooth(remap(t, CUE.ignite - 0.05, CUE.ignite + 0.05)) + (t > CUE.burst ? 0.35 : 0);
    P.streakThreshold = 1.4;
    P.streakTint = [1.0, 0.6, 0.28];
    P.flashAmt = 0.06 * pulse(t, CUE.ignite, 0.04, 0.15) + 0.2 * pulse(t, CUE.burst, 0.04, 0.16);
    P.flash = [1.0, 0.9, 0.75];
    P.ca = 0.012 + 0.04 * after(t, CUE.ignite, 0.35) + 0.08 * after(t, CUE.burst, 0.3);
    addShake(P, shake(t, CUE.ignite, 0.005, 0.35));
    addShake(P, shake(t, CUE.burst, 0.012, 0.4));
    P.letterbox = LETTERBOX;
    P.slope = [0.98, 1.02, 1.0];
    P.exposure = 1.0;
    // whip-pan out of the 56
    P.whip = 0.32 * ease.inCubic(remap(t, CUE.whip - 0.32, CUE.whip));
    P.fade = 0;
  }

  // ------------------------------------------------------------------------
  // ACT II: 365 days in oak (liquid) → ice cold (frost) → the ice cracks
  actCraft(t, P, info) {
    const L = this.scenes.liquid;
    const lp = liquidParams(t);
    const freeze = lp.freeze;
    if (t < CUE.crack) L.render(this.rt, lp);
    else {
      // the frame is now a sheet of ice: render it once more, then crack it
      L.render(this.liquidRT, lp);
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
    P.slope = [lerp(1.0, 0.94, freeze), lerp(1.0, 1.0, freeze), lerp(1.0, 1.08, freeze)];
    P.highTint = [lerp(0.014, -0.01, freeze), 0.004, lerp(-0.012, 0.016, freeze)];
    P.sat = lerp(1.04, 0.92, freeze);
    P.ca = 0.012 + 0.04 * smooth(remap(t, CUE.crack, CUE.shatter));
    P.ghosts = 0.12 * smooth(remap(t, CUE.crack, CUE.shatter));
    addShake(P, shake(t, CUE.crack + 0.05, 0.004, 0.5, 30));
    P.flashAmt = 0.12 * pulse(t, CUE.crack + 0.02, 0.02, 0.12);
    P.flash = [0.92, 0.97, 1.0];
  }

  // ------------------------------------------------------------------------
  // ACT III: the ice explodes → the bottle in the dark → the drop → callouts → end card
  actNight(t, P, info) {
    const B = this.scenes.bottle;
    let cam;
    let rotY = 0;
    if (t < CUE.drop) {
      // shot A — reveal: from a low macro of the shoulder, craning up and around to a medium shot
      const u = ease.inOutCubic(remap(t, CUE.bottleIn - 0.3, CUE.drop + 0.4));
      const ang = lerp(1.25, -0.4, u);
      const rad = lerp(0.95, 2.35, u);
      const h = lerp(0.42, 0.52, u) + 0.12 * Math.sin(Math.PI * u);
      cam = { pos: [Math.sin(ang) * rad, h, Math.cos(ang) * rad], target: [0, lerp(0.7, 0.52, u), 0], fov: lerp(24, 30, u) };
      rotY = lerp(0.25, 0.0, u);
    } else if (t < CUE.endcard) {
      // shot B — hero: a fast push on the drop, then a slow arc
      const u = remap(t, CUE.drop, CUE.endcard);
      const push = ease.outExpo(remap(t, CUE.drop, CUE.drop + 0.9));
      const ang = lerp(0.16, -0.12, ease.inOutSine(u));
      const rad = lerp(3.3, 2.75, push) - 0.15 * ease.inOutSine(u);
      cam = { pos: [Math.sin(ang) * rad, lerp(0.26, 0.36, push), Math.cos(ang) * rad], target: [0, 0.5, 0], fov: 30 };
      rotY = lerp(-0.1, 0.14, ease.inOutSine(u));
    } else {
      // shot C — end card: bottle on the right third
      const u = ease.outCubic(remap(t, CUE.endcard, CUE.fadeDone + 1));
      const off = -0.64 * (this.aspect / (16 / 9));
      cam = { pos: [off, 0.42, lerp(3.2, 2.95, u)], target: [off, lerp(0.5, 0.51, u), 0], fov: 30 };
      rotY = lerp(-0.32, -0.2, u);
    }
    const reveal = smooth(remap(t, CUE.bottleIn + 0.05, CUE.bottleIn + 1.2));
    // key strip light sweeps across during the reveal; then sits at a classic 3/4
    const keyAng = t < CUE.drop ? lerp(-2.2, 0.9, ease.inOutSine(remap(t, CUE.bottleIn, CUE.drop))) : 0.9;
    // light sweeps across the label on the drop and on the end card
    const sweep =
      t < CUE.drop ? -1 : t < CUE.endcard ? remap(t, CUE.drop + 0.05, CUE.drop + 1.3) : remap(t, CUE.endcard + 0.1, CUE.endcard + 1.6);
    const back = (t < CUE.drop ? 0.25 + 0.4 * smooth(remap(t, CUE.bottleIn + 0.5, CUE.drop)) : 1.0) * (t > CUE.endcard ? 0.8 : 1);
    const beat = t > CUE.drop && t < CUE.beatEnd ? Math.exp(-(((t - CUE.drop) % 0.5) / 0.12)) : 0;
    // botanicals orbit the bottle; the drop whips them into a vortex
    const swirl = 0.45 * (t - CUE.bottleIn) + (t > CUE.drop ? 3.2 * (1 - Math.exp(-(t - CUE.drop) / 0.8)) : 0);
    const orbit =
      0.5 * smooth(remap(t, CUE.bottleIn + 0.6, CUE.bottleIn + 3.0)) + 0.5 * smooth(remap(t, CUE.drop - 0.1, CUE.drop + 0.3)) - 0.45 * smooth(remap(t, CUE.endcard, CUE.endcard + 1.5));
    B.render(this.rt, { time: t, cam, rotY, reveal, keyAng, sweep, back, beat, smoke: 1.0, swirl, orbit: orbit * 0.75, rise: 0 });

    // the ice sheet explodes towards the camera, revealing the bottle
    const su = t - CUE.shatter;
    if (su < 2.0) {
      if (this.liquidAt !== CUE.shatter) {
        this.scenes.liquid.render(this.liquidRT, liquidParams(CUE.shatter));
        this.liquidAt = CUE.shatter;
      }
      this.scenes.shards.render(this.rt, { image: this.liquidRT.texture, u: su, crack: 1 });
    }

    if (t >= CUE.drop && t < CUE.beatEnd + 0.2) {
      const anchors = [
        { world: [0.0, 0.44, 0.172], side: -1, value: '56', label: 'BOTANICALS' },
        { world: [0.1, 0.13, 0.172], side: 1, value: '365', label: 'DAYS IN OAK' },
        { world: [-0.08, 0.7, 0.13], side: -1, value: '35%', label: 'VOL · FULL BODIED' },
        { world: [0.03, 0.86, 0.062], side: 1, value: '−18°C', label: 'SERVE ICE COLD' },
      ];
      info.callouts = anchors.map((a) => ({ ...a, anchor: B.project(a.world) }));
    }
    if (t >= CUE.endcard - 0.05) info.endX = 960 * (this.aspect / (16 / 9)) - 330;

    // ---- post
    const impactUV = this.toUV(IMPACT);
    if (su < 1.5) {
      P.shock = [impactUV[0], impactUV[1], 1.3 * su, 1.2 * after(t, CUE.shatter, 0.5)];
      P.shockLight = 0; // refraction only: a glowing ring reads as a stray circle over the bottle
      P.radial = [impactUV[0], impactUV[1], 0.07 * after(t, CUE.shatter, 0.2)];
    }
    P.rays = 0.9 * reveal * (t > CUE.endcard ? 0.7 : 1);
    P.raysPos = B.glowUV;
    P.raysDecay = 0.965;
    P.raysDensity = 0.9;
    P.raysThreshold = 0.03;
    P.raysTint = [1.0, 0.72, 0.42];
    P.letterbox = t < CUE.drop ? LETTERBOX : LETTERBOX * (1 - ease.outExpo(remap(t, CUE.drop, CUE.drop + 0.45)));
    P.flashAmt = 0.16 * pulse(t, CUE.shatter, 0.02, 0.1) + 0.45 * pulse(t, CUE.drop, 0.02, 0.16) + 0.25 * pulse(t, CUE.endcard, 0.02, 0.25);
    P.flash = t < CUE.drop ? [0.92, 0.97, 1.0] : [1.0, 0.86, 0.7];
    P.bloom = 0.09;
    P.bloomThreshold = 1.1;
    P.streak = 0.45 + 0.8 * after(t, CUE.shatter, 0.5);
    P.streakThreshold = 2.0;
    P.streakTint = t < CUE.shatter + 1.0 ? [0.7, 0.85, 1.0] : [1.0, 0.66, 0.36];
    P.ghosts = 0.1 + 0.15 * after(t, CUE.shatter, 0.6) + 0.12 * after(t, CUE.drop, 0.8);
    P.glowGain = 1.8;
    P.ca = 0.01 + 0.07 * after(t, CUE.shatter, 0.3) + 0.06 * after(t, CUE.drop, 0.25);
    addShake(P, shake(t, CUE.shatter, 0.012, 0.35));
    addShake(P, shake(t, CUE.drop, 0.008, 0.25));
    addShake(P, shake(t, CUE.endcard, 0.004, 0.3));
    if (t > CUE.drop && t < CUE.beatEnd) {
      const bt = (t - CUE.drop) % 0.5;
      addShake(P, [noise1(t * 40, 1) * 0.0012 * Math.exp(-bt / 0.08), noise1(t * 40, 2) * 0.0012 * Math.exp(-bt / 0.08)]);
      P.exposure = 1.0 + 0.1 * Math.exp(-bt / 0.1);
    }
    P.vignette = t > CUE.endcard ? 0.7 : 0.6;
    P.fade = smooth(remap(t, CUE.fadeOut, CUE.fadeDone));
  }
}
