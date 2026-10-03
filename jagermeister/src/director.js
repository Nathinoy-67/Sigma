import * as THREE from 'three';
import { CUE } from './timeline.js';
import { DEFAULT_POST } from './post.js';
import { clamp, lerp, remap, ease, noise1, smooth, FSPass } from './gl.js';

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
  // ACT I: forest → stag → Hubertus light → burst into 56 botanicals
  actMyth(t, P, info) {
    const F = this.scenes.forest;
    const reveal = ease.inOutSine(remap(t, CUE.forestIn, CUE.forestIn + 2.8));
    const camZ = 7.2 * ease.inOutSine(remap(t, 1.0, CUE.burst + 4.0));
    const cam = [0.22 * noise1(t * 0.12, 5), 0.06 * noise1(t * 0.16, 8), camZ];
    const tilt = 0.075 - 0.02 * remap(t, 2, 13);
    // the stag lives in the clearing, ~14 units deep
    const stagW = [0, -0.82, 16.5];
    const sp = F.project(stagW, { cam, tilt });
    const designX = 960 * (this.aspect / (16 / 9)) + sp[0] * 1080;
    const designY = 540 - sp[1] * 1080;
    const scale = 9.0 / (stagW[2] - camZ);
    info.stag = { x: designX, y: designY, scale, alpha: 1 };
    // star (p-space, untilted) lives between the antlers
    const starDesign = [designX, designY + this.overlay.stag.star[1] * scale];
    const starP = [(starDesign[0] - 960 * (this.aspect / (16 / 9))) / 1080, (540 - starDesign[1]) / 1080];
    info.starP = starP;

    // Hubertus light envelope
    let star = 0.0;
    star += 0.06 * smooth(remap(t, CUE.stagDone - 0.6, CUE.ignite));
    star += 1.15 * (t >= CUE.ignite ? Math.exp(-(t - CUE.ignite) / 0.5) * 0.55 + 0.45 : 0) * (t < CUE.burst ? 1 : 0);
    star *= t < CUE.burst ? 1 - 0.55 * Math.exp(-Math.pow((t - (CUE.burst - 0.05)) / 0.18, 2)) : 1; // inhale before the burst
    if (t >= CUE.burst) star = 3.2 * Math.exp(-(t - CUE.burst) / 0.22);
    star *= clamp(remap(t, CUE.ignite - 0.05, CUE.ignite)) * 0.95 + 0.05;
    const starSize = 1.0 + 0.25 * after(t, CUE.ignite, 0.6) + (t >= CUE.burst ? 1.3 * (1 - Math.exp(-(t - CUE.burst) / 0.15)) : 0);
    const moonI = (1.0 - 0.45 * smooth(remap(t, CUE.stagStart, CUE.stagDone))) * (1 - 0.6 * smooth(remap(t, CUE.ignite - 0.2, CUE.ignite + 0.4)));
    // the light sits high in the clearing, so the stag's head reads against dark fog
    const glowScreen = [0.0, 0.085];

    const dim = 1 - ease.inOutCubic(remap(t, CUE.burst + 0.05, CUE.burst + 2.2));
    const fogMore = 1 + 0.5 * smooth(remap(t, CUE.stagStart, CUE.ignite)) + 0.8 * smooth(remap(t, CUE.burst, CUE.burst + 2));
    const forestOn = t > CUE.forestIn - 0.05 && dim > 0.001;
    if (forestOn) {
      F.render(this.rt, {
        time: t,
        cam,
        tilt,
        fog: fogMore,
        reveal: reveal * dim,
        clear: 0.2,
        moon: [glowScreen[0], glowScreen[1] + tilt, 1.0 * moonI, 0.02],
        star: [starP[0], starP[1] + tilt, star, starSize],
        embers: 2.4 * reveal * (1 - 0.6 * remap(t, CUE.burst, CUE.burst + 2)),
        focus: 8.0,
      });
    }

    // botanicals: particle burst from the light, forming "56"
    if (t >= CUE.burst - 0.02) {
      const bu = this.bgDust.uniforms;
      bu.uAmt.value = smooth(remap(t, CUE.burst + 0.6, CUE.burst + 2.4));
      bu.uTime.value = t;
      if (bu.uAmt.value > 0) this.bgDust.render(this.r, this.rt);
      this.scenes.particles.render(this.rt, {
        time: t - CUE.burst,
        origin: starP,
        whipOut: remap(t, CUE.whip - 0.35, CUE.whip),
      });
    }

    // ---- post
    const toUV = (p) => [0.5 + (p[0] * this.H) / this.W, 0.5 + p[1]];
    const rayFromStar = t >= CUE.ignite;
    if (!rayFromStar) {
      P.rays = forestOn ? 1.5 * reveal : 0;
      P.raysPos = toUV(glowScreen);
      P.raysDecay = 0.968;
      P.raysDensity = 0.95;
      P.raysThreshold = 0.04;
      P.raysTint = [0.8, 1.0, 0.9];
    } else {
      P.rays = 0.3 * after(t, CUE.ignite, 1.0) * (t < CUE.burst + 0.8 ? 1 : 0) + 0.25 * reveal * dim;
      P.raysPos = toUV(starP);
      P.raysDecay = 0.97;
      P.raysDensity = 1.0;
      P.raysThreshold = 1.4;
      P.raysTint = [1.0, 0.75, 0.45];
    }
    P.glowGain = 2.4;
    P.bloom = 0.11 + 0.02 * after(t, CUE.ignite, 0.8);
    P.streak = 0.55 * smooth(remap(t, CUE.ignite - 0.05, CUE.ignite + 0.05)) + (t > CUE.burst ? 0.35 : 0);
    P.streakThreshold = 1.4;
    P.streakTint = [1.0, 0.6, 0.28];
    P.flashAmt = 0.05 * pulse(t, CUE.ignite, 0.04, 0.15) + 0.16 * pulse(t, CUE.burst, 0.04, 0.16);
    P.flash = [1.0, 0.9, 0.75];
    P.ca = 0.012 + 0.04 * after(t, CUE.ignite, 0.35) + 0.07 * after(t, CUE.burst, 0.3);
    addShake(P, shake(t, CUE.ignite, 0.005, 0.35));
    addShake(P, shake(t, CUE.burst, 0.01, 0.4));
    P.letterbox = LETTERBOX;
    P.slope = [0.98, 1.02, 1.0];
    P.exposure = 1.0;
    // whip-pan out of the 56
    P.whip = 0.32 * ease.inCubic(remap(t, CUE.whip - 0.32, CUE.whip));
    P.fade = 0;
  }

  // ------------------------------------------------------------------------
  // ACT II: 365 days in oak (liquid) → ice cold (frost) → crack
  actCraft(t, P, info) {
    const L = this.scenes.liquid;
    const lt = t - CUE.whip;
    // the liquid slows down and stops as it freezes
    const fz = CUE.freeze - CUE.whip;
    const flow = lt < fz ? lt : fz + 1.1 * (1 - Math.exp(-(lt - fz) / 1.1));
    const freeze = ease.inOutSine(remap(t, CUE.freeze, CUE.freeze + 2.6));
    L.render(this.rt, {
      time: lt,
      flow,
      freeze,
      frost: ease.inOutSine(remap(t, CUE.freeze + 0.2, CUE.freeze + 3.4)),
      frostText: remap(t, CUE.frostText, CUE.frostText + 1.9),
      crack: remap(t, CUE.crack, CUE.shatter),
      exposure: 1.0,
      push: lt,
    });
    P.whip = -0.32 * (1 - ease.outCubic(remap(t, CUE.whip, CUE.whip + 0.4)));
    P.letterbox = LETTERBOX;
    P.bloom = 0.1 + 0.05 * freeze;
    P.bloomThreshold = 0.9;
    P.streak = 0.32 + 0.4 * freeze + 1.5 * smooth(remap(t, CUE.crack, CUE.shatter));
    P.streakThreshold = 1.4;
    P.streakTint = [lerp(1.0, 0.55, freeze), lerp(0.62, 0.85, freeze), lerp(0.3, 1.0, freeze)];
    P.glowGain = 2.0;
    P.slope = [lerp(1.0, 0.94, freeze), lerp(1.0, 1.0, freeze), lerp(1.0, 1.08, freeze)];
    P.highTint = [lerp(0.014, -0.01, freeze), 0.004, lerp(-0.012, 0.016, freeze)];
    P.sat = lerp(1.04, 0.92, freeze);
    P.ca = 0.012 + 0.04 * smooth(remap(t, CUE.crack, CUE.shatter));
    addShake(P, shake(t, CUE.crack + 0.05, 0.0035, 0.5, 30));
    P.flashAmt = 0.95 * smooth(remap(t, CUE.shatter - 0.12, CUE.shatter));
    P.flash = [0.92, 0.97, 1.0];
  }

  // ------------------------------------------------------------------------
  // ACT III: the bottle in the dark → the drop → callouts → end card
  actNight(t, P, info) {
    const B = this.scenes.bottle;
    let cam;
    let rotY = 0;
    // shot A — reveal: one long move from a macro of the shoulder to a medium shot
    if (t < CUE.drop) {
      const u = ease.inOutCubic(remap(t, CUE.bottleIn, CUE.drop + 0.4));
      const ang = lerp(0.95, -0.42, u);
      const rad = lerp(1.05, 2.4, u);
      const h = lerp(0.74, 0.5, u);
      cam = { pos: [Math.sin(ang) * rad, h, Math.cos(ang) * rad], target: [0, lerp(0.7, 0.52, u), 0], fov: lerp(26, 30, u) };
      rotY = lerp(0.2, 0.0, u);
    } else if (t < CUE.endcard) {
      // shot B — hero, front, slow arc
      const u = remap(t, CUE.drop, CUE.endcard);
      const ang = lerp(0.12, -0.1, ease.inOutSine(u));
      const rad = lerp(2.85, 2.6, ease.outCubic(u));
      cam = { pos: [Math.sin(ang) * rad, 0.36, Math.cos(ang) * rad], target: [0, 0.5, 0], fov: 30 };
      rotY = lerp(-0.1, 0.12, ease.inOutSine(u));
    } else {
      // shot C — end card: bottle on the right third
      const u = ease.outCubic(remap(t, CUE.endcard, CUE.fadeDone + 1));
      const off = -0.64 * (this.aspect / (16 / 9));
      cam = { pos: [off, 0.42, lerp(3.2, 2.95, u)], target: [off, lerp(0.5, 0.51, u), 0], fov: 30 };
      rotY = lerp(-0.32, -0.2, u);
    }
    const reveal = smooth(remap(t, CUE.bottleIn + 0.1, CUE.bottleIn + 1.4));
    // key strip light sweeps across during the reveal; then sits at a classic 3/4
    const keyAng = t < CUE.drop ? lerp(-2.2, 0.9, ease.inOutSine(remap(t, CUE.bottleIn, CUE.drop))) : 0.9;
    // light sweeps across the label on the drop and on the end card
    const sweep =
      t < CUE.drop ? -1 : t < CUE.endcard ? remap(t, CUE.drop + 0.05, CUE.drop + 1.3) : remap(t, CUE.endcard + 0.1, CUE.endcard + 1.6);
    const back = (t < CUE.drop ? 0.35 * smooth(remap(t, CUE.bottleIn + 1.5, CUE.drop)) : 1.0) * (t > CUE.endcard ? 0.8 : 1);
    B.render(this.rt, {
      time: t,
      cam,
      rotY,
      reveal,
      keyAng,
      sweep,
      back,
      beat: t > CUE.drop && t < CUE.beatEnd ? Math.exp(-(((t - CUE.drop) % 0.5) / 0.12)) : 0,
      smoke: 1.0,
    });

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
    P.letterbox = t < CUE.drop ? LETTERBOX : LETTERBOX * (1 - ease.outExpo(remap(t, CUE.drop, CUE.drop + 0.45)));
    P.flashAmt = 0.95 * after(t, CUE.shatter, 0.13) + 0.45 * pulse(t, CUE.drop, 0.02, 0.16) + 0.25 * pulse(t, CUE.endcard, 0.02, 0.25);
    P.flash = t < CUE.drop ? [0.92, 0.97, 1.0] : [1.0, 0.86, 0.7];
    P.bloom = 0.09;
    P.bloomThreshold = 1.1;
    P.streak = 0.45;
    P.streakThreshold = 2.0;
    P.streakTint = [1.0, 0.66, 0.36];
    P.glowGain = 1.8;
    P.ca = 0.01 + 0.06 * after(t, CUE.drop, 0.25);
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
