// Scene lab: renders one scene with explicit parameters (for look development).
import * as THREE from 'three';
import { makeRT } from './gl.js';
import { Post, DEFAULT_POST } from './post.js';
import { DropScene } from './scenes/drop.js';
import { FizzScene } from './scenes/fizz.js';
import { ForestScene } from './scenes/forest.js';

const qs = new URLSearchParams(location.search);
const W = +(qs.get('w') || 1280), H = +(qs.get('h') || 720);
const canvas = document.getElementById('film');
canvas.width = W;
canvas.height = H;
const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: false, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(W, H, false);
renderer.autoClear = false;
renderer.outputColorSpace = THREE.LinearSRGBColorSpace;
const rt = makeRT(W, H, { depthBuffer: true });
const post = new Post(renderer, W, H);
const scenes = { drop: new DropScene(renderer, W, H), fizz: new FizzScene(renderer, W, H), forest: new ForestScene(renderer, W, H) };
window.LAB = {
  render(name, s, p = {}) {
    renderer.setRenderTarget(rt);
    renderer.setClearColor(0x000000, 0);
    renderer.clear();
    scenes[name].render(rt, s);
    const P = { ...DEFAULT_POST(), letterbox: 0, ...p };
    post.render(rt.texture, null, null, P, 0);
    renderer.getContext().finish();
    return true;
  },
};
