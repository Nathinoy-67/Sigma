// Look-development stills: node render/lab.mjs shots.json out_dir [w h]
// shots.json: [{ "name": "a", "scene": "drop", "s": {...scene params}, "p": {...post overrides} }]
import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import { startServer } from './server.mjs';
import fs from 'node:fs';
const [, , file, outDir, w = 1280, h = 720] = process.argv;
const shots = JSON.parse(fs.readFileSync(file, 'utf8'));
fs.mkdirSync(outDir, { recursive: true });
const { url, close } = await startServer();
const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: +w, height: +h } });
page.setDefaultTimeout(600000);
page.on('console', (m) => console.log('console:', m.text()));
page.on('pageerror', (e) => console.log('pageerror:', e.message));
await page.goto(`${url}/lab.html?w=${w}&h=${h}`);
await page.waitForFunction(() => window.LAB, null, { timeout: 60000 });
for (const sh of shots) {
  const t0 = Date.now();
  await page.evaluate(({ scene, s, p }) => window.LAB.render(scene, s, p), sh);
  const buf = await page.screenshot({ type: 'png', clip: { x: 0, y: 0, width: +w, height: +h } });
  fs.writeFileSync(`${outDir}/${sh.name}.png`, buf);
  console.log(sh.name, Date.now() - t0, 'ms');
}
await browser.close();
close();
