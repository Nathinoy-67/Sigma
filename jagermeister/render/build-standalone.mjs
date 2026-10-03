// Bundles the real-time film into one self-contained HTML file (code, fonts and soundtrack inlined).
//   node render/build-standalone.mjs  ->  out/jagermeister-realtime.html
import { build } from 'esbuild';
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const res = await build({ entryPoints: [path.join(ROOT, 'src/main.js')], bundle: true, minify: true, format: 'esm', write: false, legalComments: 'none' });
const js = res.outputFiles[0].text;

const fontDir = path.join(ROOT, 'assets/fonts');
const fonts = Object.fromEntries(
  fs.readdirSync(fontDir).filter((f) => f.endsWith('.woff2')).map((f) => [f, `url(data:font/woff2;base64,${fs.readFileSync(path.join(fontDir, f)).toString('base64')})`]),
);

// MP3 plays in every browser (open-source Chromium builds lack AAC)
const mp3 = path.join(ROOT, 'audio/soundtrack.mp3');
execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', path.join(ROOT, 'audio/soundtrack.wav'), '-c:a', 'libmp3lame', '-b:a', '256k', mp3]);
const audio = `data:audio/mpeg;base64,${fs.readFileSync(mp3).toString('base64')}`;

let html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
html = html.replace(/<script type="importmap">[\s\S]*?<\/script>\n/, '');
// (replacer functions: the minified code contains `$&`-style sequences that String.replace would expand)
html = html.replace('src="audio/soundtrack.mp3"', () => `src="${audio}"`);
html = html.replace(
  '<script type="module" src="./src/main.js"></script>',
  () => `<script>window.FONT_DATA = ${JSON.stringify(fonts)};</script>\n<script type="module">${js.replace(/<\/script/g, '<\\/script')}</script>`,
);
fs.mkdirSync(path.join(ROOT, 'out'), { recursive: true });
const out = path.join(ROOT, 'out/jagermeister-realtime.html');
fs.writeFileSync(out, html);
console.log(`wrote ${out} (${(fs.statSync(out).size / 1e6).toFixed(1)} MB)`);
