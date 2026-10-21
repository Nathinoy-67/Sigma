import * as THREE from 'three';
import { FPS, DURATION } from './timeline.js';
import { makeRT } from './gl.js';
import { Post } from './post.js';
import { Overlay } from './overlay.js';
import { loadFonts } from './fonts.js';
import { ForestScene } from './scenes/forest.js';
import { ParticleScene } from './scenes/particles.js';
import { LiquidScene } from './scenes/liquid.js';
import { BottleScene } from './scenes/bottle.js';
import { ShardScene } from './scenes/shards.js';
import { DropScene } from './scenes/drop.js';
import { FizzScene } from './scenes/fizz.js';
import { Director } from './director.js';

const qs = new URLSearchParams(location.search);
const MODE = qs.get('mode') || 'play';
// offline renders default to 1080p; live playback to 720p unless ?hd is set
const HD = MODE === 'render' || qs.has('hd');
const W = +(qs.get('w') || (HD ? 1920 : 1280));
const H = +(qs.get('h') || (HD ? 1080 : 720));

const canvas = document.getElementById('film');
canvas.width = W;
canvas.height = H;
if (MODE === 'render') {
  // offline rendering: canvas at 1:1 pixels in the top-left corner, no UI
  document.getElementById('ui').remove();
  document.body.style.display = 'block';
  Object.assign(canvas.style, { width: W + 'px', height: H + 'px', maxWidth: 'none', maxHeight: 'none' });
}

const renderer = new THREE.WebGLRenderer({
  canvas,
  antialias: false,
  alpha: false,
  depth: true,
  stencil: false,
  preserveDrawingBuffer: MODE === 'render',
  powerPreference: 'high-performance',
});
renderer.setPixelRatio(1);
renderer.setSize(W, H, false);
renderer.autoClear = false;
renderer.outputColorSpace = THREE.LinearSRGBColorSpace;
renderer.toneMapping = THREE.NoToneMapping;

const film = {
  W, H, FPS, DURATION,
  ready: null,
  renderFrame: null,
};
window.FILM = film;

film.ready = (async () => {
  await loadFonts();
  const sceneRT = makeRT(W, H, { depthBuffer: true });
  const msaaRT = makeRT(W, H, { depthBuffer: true, samples: 4 });
  const post = new Post(renderer, W, H);
  const overlay = new Overlay(W, H);
  const scenes = {
    forest: new ForestScene(renderer, W, H),
    particles: new ParticleScene(renderer, W, H),
    liquid: new LiquidScene(renderer, W, H),
    bottle: new BottleScene(renderer, W, H),
    shards: new ShardScene(renderer, W, H),
    drop: new DropScene(renderer, W, H),
    fizz: new FizzScene(renderer, W, H),
  };
  const director = new Director({ renderer, W, H, scenes, overlay, sceneRT, msaaRT });
  film.debug = { scenes, director, overlay, post, renderer };

  film.renderFrame = (t) => {
    const frame = Math.round(t * FPS);
    const P = director.frame(t);
    overlay.upload();
    post.render(director.rt.texture, overlay.usedText ? overlay.textTex : null, overlay.usedGlow ? overlay.glowTex : null, P, frame, overlay.usedSub ? overlay.subTex : null);
    return true;
  };
  // per-stage timings (debug): scene, typography, post — each forced to completion
  film.profile = (t) => {
    const gl = renderer.getContext();
    const px = new Float32Array(4);
    const sync = () => gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.FLOAT, px);
    const T = [performance.now()];
    const P = director.frame(t);
    renderer.setRenderTarget(director.rt);
    sync();
    T.push(performance.now());
    overlay.upload();
    T.push(performance.now());
    post.render(director.rt.texture, overlay.usedText ? overlay.textTex : null, overlay.usedGlow ? overlay.glowTex : null, P, Math.round(t * FPS), overlay.usedSub ? overlay.subTex : null);
    renderer.setRenderTarget(null);
    gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array(4));
    T.push(performance.now());
    return { sceneAndOverlayDraw: T[1] - T[0], upload: T[2] - T[1], post: T[3] - T[2] };
  };
  // warm-up: compile every program once
  for (const t of [2, 10, 22, 28, 31, 33, 37, 41, 46, 66]) film.renderFrame(t);
  renderer.getContext().finish();
  return true;
})();

// --- interactive playback -------------------------------------------------
if (MODE === 'play') {
  const ui = document.getElementById('ui');
  const status = document.getElementById('status');
  const btn = document.getElementById('play');
  const audio = document.getElementById('score');
  film.ready.then(() => (status.textContent = `${Math.round(DURATION)} seconds · sound on`));
  let start = 0;
  let running = false;
  const tick = () => {
    if (!running) return;
    let t = audio && !audio.paused && audio.currentTime > 0 ? audio.currentTime : (performance.now() - start) / 1000;
    if (t >= DURATION) {
      running = false;
      ui.classList.remove('hidden');
      btn.textContent = 'Play again';
      return;
    }
    film.renderFrame(t);
    requestAnimationFrame(tick);
  };
  btn.addEventListener('click', async () => {
    await film.ready;
    ui.classList.add('hidden');
    start = performance.now();
    try {
      audio.currentTime = 0;
      await audio.play();
    } catch (e) {
      /* no audio available — run on the wall clock */
    }
    running = true;
    requestAnimationFrame(tick);
  });
  const seek = qs.get('t');
  if (seek) film.ready.then(() => film.renderFrame(+seek));
}
