// Master cue sheet (seconds) for v2 — picture, score and voice-over are all cut to it
// (exported to audio/cues.json by render/export-cues.mjs).
export const FPS = 30;
export const DURATION = 60.0;

export const CUE = {
  // ACT 0 — TITLE
  titleIn: 1.2,
  titleOut: 4.6,
  forestIn: 4.4,

  // ACT I — THE FOREST
  flightStart: 4.4, // camera flies along the trail
  locIn: 7.0,
  locOut: 10.4,
  arrive: 12.0, // reaches the clearing
  stagStart: 11.6,
  stagDone: 15.4,
  ignite: 16.0, // Hubertus light — HIT (end of "…a light shone")
  burst: 17.3, // light bursts into botanicals — HIT

  // ACT II — CRAFT
  formDone: 20.3,
  botText: 20.0,
  ingredients: 20.9,
  disperse: 24.3,
  whip: 25.0, // whip-pan into the liqueur
  countStart: 25.8,
  countEnd: 28.4,
  daysText: 27.9,
  freeze: 30.6,
  frostText: 31.8,
  coldText: 32.9,
  crack: 34.9,
  shatter: 35.6, // HIT — the ice explodes towards camera

  // ACT III — THE NIGHT
  bottleIn: 35.6,
  drop: 41.8, // beat drop — HIT
  bpm: 120,
  callouts: [42.3, 43.3, 44.3, 45.3],
  beatEnd: 47.8,
  endcard: 47.8, // wordmark — HIT
  tagline: 50.6,
  legal: 52.6,
  fadeOut: 57.0,
  fadeDone: 58.6,

  // voice-over line starts (audio/vo/<id>.wav)
  vo: {
    secrets: 0.7,
    woods: 6.0,
    antlers: 11.92, // ends on "shone" at the ignition
    botanicals: 19.9,
    oak: 26.3,
    cold: 32.4,
    master: 38.6,
    brand: 48.75,
    tagline: 50.75,
  },
};
