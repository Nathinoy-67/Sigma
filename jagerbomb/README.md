# Jägermeister — *The Drop*

A 74-second cinematic motion piece (unofficial spec film) about Jägermeister and the birth of the
Jägerbomb, generated entirely in code: WebGL2 shaders for the picture (including a ray-traced glass,
drink and splash), an orchestral score written as MIDI, a synthesized club layer and sound design, an
English voice-over from an open text-to-speech model, and burned-in English subtitles. There's no stock
footage, no 3D models, no samples and no recordings.

| Deliverable | |
|---|---|
| `out/jagermeister-the-drop.mp4` | master · 1920×1080 · 30 fps · H.264 ~7 Mbps + AAC 256k (67 MB) |
| `out/jagermeister-the-drop-hevc.mp4` | **best quality per MB**: 1080p HEVC (29 MB). Plays on iPhone and most recent Android phones |
| `out/jagermeister-the-drop-share.mp4` | lighter 1080p H.264 copy that plays everywhere (29 MB) |
| `out/jagermeister-the-drop.en.srt` | the English subtitles as a sidecar file (they're also burned into the picture) |
| `out/poster.jpg` | end-card still |

## The film

| Time | Act | Picture | Voice-over |
|---|---|---|---|
| 0:00 | Cold open | Macro: a single drop of dark liqueur falls into a black pool in slow motion; a crown splash, ripples. **THE DROP**, *the legend of the Jägerbomb* | "Every legend begins with a single drop." |
| 0:07 | 1934 | The night forest of Lower Saxony (from *The Hunter's Hour*). WOLFENBÜTTEL · GERMANY, *1934* | "Germany, 1934. In Wolfenbüttel, Curt Mast perfected a secret recipe." |
| 0:15 | The stag | The stag constellation forms; the light ignites between its antlers | "He called it Jägermeister. The master hunter." |
| 0:21 | 56 | The light bursts into 56 botanicals | "Fifty-six botanicals. A full year in oak." |
| 0:26 | Ice cold | A whip-pan into the swirling liqueur, which freezes into −18°C; the ice shatters and reveals the bottle | "Served ice cold, it crossed an ocean… and conquered the night." |
| 0:35 | Lake Tahoe | A flight through snowy pines towards the warm lights of a bar. LAKE TAHOE · CALIFORNIA, *circa 1997*. A club beat thumps through the snow | "Decades later, in the snowy pines of Lake Tahoe…" |
| 0:40 | Energy | Inside the golden energy drink: streams of bubbles rising to the surface | "…a new kind of energy was hitting the bars." |
| 0:43 | The pour | The drink is poured into an ice-cold highball | |
| 0:45 | The hover | A frosted shot of Jägermeister hangs over the glass. Heartbeat, a clock, a held breath | "Nobody knows for sure who dropped the first one. But the moment that shot hit the glass…" |
| 0:51 | **The drop** | Slow motion: the shot plunges in, a crown splash and droplets, the camera orbits; the liqueur billows through the gold and the foam surges | "…a legend was born." |
| 0:57 | **Jägerbomb** | The beat drops (120 BPM) on the title; a cut on every third beat | "One shot. Ice cold. Drop it." |
| 1:05 | End card | The bottle and the finished Jägerbomb; stag emblem, the *Jägermeister* wordmark. BORN IN THE FOREST · DROPPED INTO LEGEND | "Jägermeister. Born in the forest. Dropped into legend." |

The history is told as it's generally reported: Curt Mast created Jägermeister in Wolfenbüttel in 1934
(it went on sale in 1935); Sidney Frank brought it to the United States in the 1970s; and the Jägerbomb
is usually said to have appeared around 1997, with Lake Tahoe the most often cited birthplace. Nobody
knows for sure, and the film says so. The energy drink is unbranded.

## How it's built

- `src/timeline.js`: the cue sheet. Picture, score, voice-over and subtitles are all cut to it
  (`npm run cues` exports it to `audio/cues.json`, `src/vo-lines.js` and the `.srt`).
- `src/director.js`: decides, as a pure function of time, what's on screen. The 1934 acts reuse the
  scenes of *The Hunter's Hour* on that film's clock (`src/legacy.js`), re-timed to this one.
- `src/scenes/drop.js`: the Jägerbomb, ray-traced analytically in one full-screen pass. A heavy highball
  on a lacquered bar top; refraction through the glass walls, base and liquid surface with Fresnel,
  total internal reflection and Beer–Lambert absorption; the drink integrated as a volume, with bubbles
  on nested cylindrical shells (so they have real parallax); a frosted shot glass; the crown splash and
  droplets; the liqueur billowing through the drink as domain-warped ridged noise; foam; the pour;
  condensation on the ice-cold glass; a golden caustic on the bar. The studio lighting is baked into an
  environment map once per frame. In "pool" mode it renders the opening macro of a single drop.
- `src/scenes/fizz.js`: the macro inside the drink, bubbles on depth layers with bokeh.
- `src/scenes/forest.js` gained a snowy-night palette (snow on the branches, falling snowflakes) for Lake Tahoe.
- `src/overlay.js`: typography and line art (titles, supers, the stag, recipe callouts, the end card)
  and the burned-in subtitles, which `src/post.js` composites on top of the letterbox.
- `audio/score.py`: the orchestral score (D minor → D major), composed as MIDI and rendered in five stems
  with FluidSynth and the MuseScore General soundfont. The second half sits on a 120 BPM grid.
- `audio/synth.py`: synthesized sound design: the drop, pour, carbonation, the plunge (slowed down for
  the slow motion), risers, booms, and the club layer (kick, clap, hats, sub bass, plucked arpeggio),
  which is low-passed while we're still outside in the snow.
- `audio/voiceover.py`: the voice-over, made with Kokoro-82M v1.0 (a blend of two of its male voices,
  slowed down), with pronunciation fixes for *Jägermeister* and *Wolfenbüttel*.
- `audio/soundtrack.py`: the mix: convolution reverb, voice ducking, bus compression and a limiter
  (about −14.5 LUFS integrated).
- `lab.html`, `src/lab.js`, `render/lab.mjs`: a look-development harness that renders one scene with
  explicit parameters.

## Rebuild

```bash
npm install
sudo apt install fluidsynth musescore-general-soundfont-lossless
pip install numpy scipy soundfile mido
npm run audio                                    # audio/soundtrack.wav
node render/render.mjs --w 1920 --h 1080         # frames/ (headless Chromium, about 3.5 h on 4 CPU cores)
bash render/encode.sh frames                     # out/*.mp4
```

To regenerate the voice-over: `pip install kokoro-onnx`, download `kokoro-v1.0.onnx` and
`voices-v1.0.bin` from the kokoro-onnx GitHub release `model-files-v1.0`, then
`python3 audio/voiceover.py kokoro-v1.0.onnx voices-v1.0.bin`.

Live preview: serve the folder (`npx serve .`) and open `index.html` (`?hd` for 1080p, `?t=51.5` for a still).

Fonts: UnifrakturMaguntia, Cinzel, Cormorant Garamond, Montserrat, Grenze Gotisch (SIL OFL, via Fontsource).
Kokoro-82M is Apache-2.0; the MuseScore General soundfont is MIT.
Jägermeister and its marks belong to Mast-Jägermeister SE. This is an unofficial spec piece.
Please enjoy responsibly.
