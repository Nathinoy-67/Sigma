// Master timeline (seconds). Shared by the visuals and by audio/soundtrack.py
// (exported to audio/cues.json by render/export-cues.mjs).
export const FPS = 30;
export const DURATION = 50.0;

export const CUE = {
  // ACT I — MYTH
  poemIn: 0.4,
  poemOut: 3.3,
  forestIn: 2.7,
  locIn: 5.0,
  locOut: 8.3,
  stagStart: 8.0,
  stagDone: 11.6,
  ignite: 12.0, // Hubertus light — HIT
  burst: 13.0, // light bursts into botanicals — HIT

  // ACT II — CRAFT
  formDone: 15.9,
  botText: 15.5,
  ingredients: 16.2,
  disperse: 19.2,
  whip: 20.0, // whip-pan into the liquid
  countStart: 20.8,
  countEnd: 23.4,
  daysText: 23.0,
  freeze: 26.0,
  frostText: 27.3,
  coldText: 28.6,
  crack: 30.6,
  shatter: 31.3, // HIT

  // ACT III — NIGHT
  bottleIn: 31.3,
  drop: 36.0, // beat drop — HIT
  bpm: 120,
  callouts: [36.5, 37.5, 38.5, 39.5],
  beatEnd: 41.5,
  endcard: 42.0, // wordmark — HIT
  tagline: 43.2,
  legal: 44.4,
  fadeOut: 47.6,
  fadeDone: 49.0,
};
