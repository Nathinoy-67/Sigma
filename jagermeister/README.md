# Jägermeister — *The Hunter's Hour*

A 50-second cinematic motion piece (unofficial spec film), generated entirely in code:
WebGL2 shaders for the picture and NumPy synthesis for the score. There's no stock footage, no
3D models and no audio samples.

| Deliverable | |
|---|---|
| `out/jagermeister-the-hunters-hour.mp4` | master · 1920×1080 · 30 fps · H.264 ~7 Mbps + AAC 256k (44 MB) |
| `out/jagermeister-the-hunters-hour-hevc.mp4` | **best quality per MB**: 1080p HEVC, 27 MB, closest to the source (SSIM 0.983). Plays on iPhone and most recent Android phones |
| `out/jagermeister-the-hunters-hour-share.mp4` | lighter 1080p H.264 copy that plays everywhere (26 MB) |
| `out/jagermeister-realtime.html` | the same film running live in a browser (one self-contained file) |
| `out/poster.jpg` | end-card still |

## The film

| Time | Act | What happens |
|---|---|---|
| 0:00 | Epigraph | Black. The hunter's verse from the label, *„Das ist des Jägers Ehrenschild…“*, appears in fraktur. |
| 0:03 | The forest | A dolly through a night spruce forest (fog, god rays, drifting embers). WOLFENBÜTTEL · 1934. |
| 0:08 | The stag | A golden constellation draws a stag. Its antlers grow like branches. |
| 0:12 | Hubertus light | A four-pointed star ignites between the antlers and bursts into light. |
| 0:13 | 56 | 28,000 botanicals spiral into a giant "56", followed by the ingredient roll-call. |
| 0:20 | 365 | A whip-pan into the swirling liqueur, with a counter running to 365 *days in oak*. |
| 0:26 | −18 °C | The liquid freezes, frost crystals creep in, "−18°C" crystallises, then the ice cracks. |
| 0:31 | The bottle | A 3D bottle in a dark studio: light sweeps, condensation, mirror floor. |
| 0:36 | The drop | A 120 BPM beat. The letterbox opens and spec callouts land on the beat. |
| 0:42 | End card | Stag emblem, the *Jägermeister* wordmark with a light sweep, BORN IN THE FOREST · MADE FOR THE NIGHT. |

## How it's built

- `src/timeline.js`: the cue sheet. Both picture and sound are cut to it.
- `src/director.js`: decides, as a pure function of time, what's on screen: cameras, lights, transitions, grade.
- `src/scenes/`: `forest` (layered procedural spruce silhouettes, fog, embers), `particles` (the 56),
  `liquid` (domain-warped liqueur, frost, cracks), `bottle` (superellipse-swept bottle, analytic studio
  lighting, foil label, droplets, mirror floor).
- `src/overlay.js`: typography and line art (the stag constellation, titles, callouts, end card).
- `src/post.js`: HDR post: god rays, bloom, anamorphic streaks, ACES tone-mapping, grade, grain, letterbox.
- `audio/soundtrack.py`: the whole score and sound design (drones, impacts, ice, the drop, the glass clink).

## Rebuild

```bash
npm install
npm run audio                                    # audio/soundtrack.wav
node render/render.mjs --w 1920 --h 1080         # frames/ (headless Chromium, ~1.5 h on 4 CPU cores)
bash render/encode.sh frames                     # out/*.mp4 (master + share copy)
node render/build-standalone.mjs                 # out/jagermeister-realtime.html
```

Live preview: serve the folder (`npx serve .`) and open `index.html` (`?hd` for 1080p, `?t=12` for a still).

Fonts: UnifrakturMaguntia, Cinzel, Cormorant Garamond, Montserrat, Grenze Gotisch (SIL OFL, via Fontsource).
Jägermeister and its marks belong to Mast-Jägermeister SE. This is an unofficial spec piece.
