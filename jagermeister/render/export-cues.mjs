// Writes the master timeline to audio/cues.json so the soundtrack is cut to the same cues.
import fs from 'node:fs';
import { CUE, FPS, DURATION } from '../src/timeline.js';
fs.writeFileSync(new URL('../audio/cues.json', import.meta.url), JSON.stringify({ ...CUE, FPS, DURATION }, null, 2));
console.log('audio/cues.json written');
