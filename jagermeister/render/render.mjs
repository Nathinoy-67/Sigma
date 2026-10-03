// Offline frame renderer: headless Chromium (SwiftShader WebGL2) → JPEG frames.
//   node render/render.mjs --w 1920 --h 1080 --out frames --workers 2 [--from 0 --to 1500] [--step 1]
import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import { startServer } from './server.mjs';
import fs from 'node:fs';
import path from 'node:path';

const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, v, i, a) => (v.startsWith('--') ? [...acc, [v.slice(2), a[i + 1]]] : acc), []),
);
const W = +(args.w || 1920), H = +(args.h || 1080);
const OUT = path.resolve(args.out || 'frames');
const WORKERS = +(args.workers || 2);
const FPS = 30, DURATION = 60;
const total = Math.round(FPS * DURATION);
const from = +(args.from || 0), to = Math.min(total, +(args.to || total)), step = +(args.step || 1);
const quality = +(args.quality || 96);
fs.mkdirSync(OUT, { recursive: true });

const todo = [];
for (let f = from; f < to; f += step) if (!fs.existsSync(path.join(OUT, `f${String(f).padStart(5, '0')}.jpg`))) todo.push(f);
console.log(`${todo.length} frames to render at ${W}x${H} with ${WORKERS} workers`);
const { url, close } = await startServer();
let next = 0, done = 0;
const t0 = Date.now();

async function worker(id) {
  const browser = await chromium.launch({
    args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--disable-gpu-vsync'],
  });
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  page.setDefaultTimeout(600000);
  page.on('pageerror', (e) => console.log(`[w${id}] pageerror:`, e.message));
  await page.goto(`${url}/index.html?mode=render&w=${W}&h=${H}`);
  await page.waitForFunction(() => window.FILM && window.FILM.ready, null, { timeout: 120000 });
  await page.evaluate(() => window.FILM.ready);
  while (next < todo.length) {
    const f = todo[next++];
    await page.evaluate((t) => window.FILM.renderFrame(t), f / FPS);
    const buf = await page.screenshot({ type: 'jpeg', quality, clip: { x: 0, y: 0, width: W, height: H } });
    fs.writeFileSync(path.join(OUT, `f${String(f).padStart(5, '0')}.jpg`), buf);
    done++;
    if (done % 10 === 0 || done === todo.length) {
      const el = (Date.now() - t0) / 1000;
      const eta = (el / done) * (todo.length - done);
      console.log(`${done}/${todo.length}  ${(el / done).toFixed(2)} s/frame  eta ${(eta / 60).toFixed(1)} min`);
    }
  }
  await browser.close();
}
await Promise.all(Array.from({ length: WORKERS }, (_, i) => worker(i)));
close();
console.log(`done in ${((Date.now() - t0) / 60000).toFixed(1)} min`);
