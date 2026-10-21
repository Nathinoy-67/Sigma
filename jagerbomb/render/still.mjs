// Render individual frames to PNG for review:  node render/still.mjs out_dir w h t1 t2 ...
import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import { startServer } from './server.mjs';
import fs from 'node:fs';
const [, , outDir, w, h, ...times] = process.argv;
fs.mkdirSync(outDir, { recursive: true });
const { url, close } = await startServer();
const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: +w, height: +h } });
page.setDefaultTimeout(600000);
page.on('console', (m) => console.log('console:', m.text()));
page.on('pageerror', (e) => console.log('pageerror:', e.message));
await page.goto(`${url}/index.html?mode=render&w=${w}&h=${h}`);
await page.waitForFunction(() => window.FILM && window.FILM.ready, null, { timeout: 60000 });
const t0 = Date.now();
await page.evaluate(() => window.FILM.ready);
console.log('ready in', Date.now() - t0, 'ms');
for (const t of times) {
  const s = Date.now();
  await page.evaluate((tt) => { window.FILM.renderFrame(tt); }, +t);
  const buf = await page.screenshot({ type: 'png', clip: { x: 0, y: 0, width: +w, height: +h } });
  fs.writeFileSync(`${outDir}/t${(+t).toFixed(2).padStart(6, '0')}.png`, buf);
  console.log('t=', t, Date.now() - s, 'ms');
}
await browser.close();
close();
