// Master cue sheet (seconds) for "The Drop" — picture, score, voice-over and subtitles are all
// cut to it (exported to audio/cues.json by render/export-cues.mjs).
export const FPS = 30;
export const DURATION = 74.0;

export const CUE = {
  // ACT 0 — COLD OPEN: a single drop
  openIn: 0.3,
  dropHit: 3.62, // the drop lands on "…a single drop" — HIT
  titleIn: 4.5,
  titleOut: 7.6,

  // ACT I — 1934 (the forest, the stag and the 56 come from The Hunter's Hour, re-timed)
  forestIn: 6.9,
  locIn: 8.2,
  locOut: 12.6,
  stagStart: 15.1,
  stagDone: 19.5,
  ignite: 20.2, // right after "…the master hunter." — HIT
  burst: 21.4, // HIT
  formDone: 23.6,
  disperse: 25.5,
  whip: 26.2, // whip-pan into the liqueur
  freeze: 28.0,
  coldText: 28.7,
  crack: 30.9,
  shatter: 31.5, // HIT — the ice explodes, revealing the bottle
  bottleIn: 31.5,

  // ACT II — LAKE TAHOE, c. 1997
  tahoe: 35.4, // whip into the snowy pines
  tahoeLocIn: 36.2,
  tahoeLocOut: 39.4,
  fizz: 39.6, // inside the energy drink
  pour: 42.6, // the glass is filled
  hover: 45.4, // the shot glass descends over the glass
  release: 50.35, // it is let go…
  hit: 51.4, // …and hits the drink — HIT (slow motion)
  rampUp: 53.6, // slow motion ends, the mix billows
  slam: 56.6, // JÄGERBOMB — the beat drops

  // ACT III — THE BEAT (120 BPM)
  bpm: 120,
  cuts: [56.6, 58.6, 60.1, 61.6, 63.1],
  callouts: [58.75, 60.25, 61.75],
  endcard: 64.6, // HIT
  tagline: 67.2,
  legal: 68.6,
  fadeOut: 72.2,
  fadeDone: 73.6,

  // voice-over line starts (audio/vo/<id>.wav)
  vo: {
    drop: 0.6,
    germany: 7.6,
    mast: 10.6,
    named: 15.4,
    hunter: 18.1,
    botanicals: 22.0,
    ocean: 27.4,
    night: 32.0,
    tahoe: 35.9,
    energy: 39.75,
    nobody: 44.3,
    moment: 48.45,
    born: 54.2,
    one: 58.7,
    ice: 60.2,
    dropit: 61.7,
    brand: 65.3,
    tagline: 67.3,
  },
};
