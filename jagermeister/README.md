# Jägermeister — *The Hunter's Hour*

A 60-second cinematic motion piece (unofficial spec film), generated entirely in code:
WebGL2 shaders for the picture, an orchestral score written as MIDI, synthesized sound design
and a deep English voice-over from an open text-to-speech model. There's no stock footage, no 3D
models, no samples and no recordings.

| Deliverable | |
|---|---|
| `out/jagermeister-the-hunters-hour.mp4` | master · 1920×1080 · 30 fps · H.264 ~7 Mbps + AAC 256k |
| `out/jagermeister-the-hunters-hour-hevc.mp4` | **best quality per MB**: 1080p HEVC under 30 MB, closest to the source. Plays on iPhone and most recent Android phones |
| `out/jagermeister-the-hunters-hour-share.mp4` | lighter 1080p H.264 copy under 30 MB that plays everywhere |
| `out/jagermeister-realtime.html` | the same film running live in a browser (one self-contained file) |
| `out/poster.jpg` | end-card still |

## The film

| Time | Act | What happens |
|---|---|---|
| 0:00 | Title | Embers drift in the dark. **THE HUNTER'S HOUR**, *a legend from the forest*. VO: "They say the forest keeps its secrets." |
| 0:04 | The flight | The camera flies down a winding trail through a night spruce forest: fog, god rays, embers streaming past. LOWER SAXONY · GERMANY, *Winter, 1934*. VO: "In the dark woods of Lower Saxony, a hunter once followed a light." |
| 0:11 | The stag | Sparks stream in from the forest and become a golden constellation. The stag turns its head towards us as its antlers grow. VO: "And there, between the antlers of a stag… a light shone." |
| 0:16 | Hubertus light | A star ignites between the antlers (shockwave, lens ghosts), then bursts. |
| 0:17 | 56 | 40,000 streaks of light spiral into a 3D "56" while the camera orbits it, followed by the ingredient roll-call. VO: "Fifty-six botanicals." |
| 0:25 | 365 | A whip-pan into the swirling liqueur, with a counter running to 365 *days in oak*. VO: "A full year, in oak." |
| 0:30 | −18 °C | The liquid freezes, frost crystals creep in and "−18°C" crystallises. VO: "Served ice cold." |
| 0:35 | The shatter | The ice cracks from an impact point and explodes towards the camera in 3D shards, revealing the bottle. |
| 0:36 | The bottle | A low macro cranes up and around the bottle while botanicals orbit it in the backlight. VO: "Every night has its master." |
| 0:42 | The drop | The beat drops at 120 BPM, the letterbox opens and spec callouts land on the beat. |
| 0:48 | End card | Stag emblem and the *Jägermeister* wordmark. VO: "Jägermeister. Born in the forest. Made for the night." |

## How it's built

- `src/timeline.js`: the cue sheet. Picture, score and voice-over are all cut to it (`npm run cues` exports it to `audio/cues.json`).
- `src/director.js`: decides, as a pure function of time, what's on screen: the camera flight, lights, transitions, grade.
- `src/scenes/`:
  - `forest`: planes of procedural spruce silhouettes, recycled as the camera flies down a winding trail and composited front to back, with fog, glowing mist and embers.
  - `particles`: the 56, drawn as velocity-stretched streaks.
  - `liquid`: domain-warped liqueur, frost and the crystallising text.
  - `shards`: a Voronoi fracture with jagged shared edges, textured with the frozen frame and lit like ice as it flies apart.
  - `bottle`: superellipse-swept bottle, analytic studio lighting, foil label, condensation, mirror floor and orbiting botanicals.
- `src/overlay.js`: typography and line art: the title, the stag constellation (posed in 3D), callouts and the end card.
- `src/post.js`: HDR post: god rays, shockwaves, zoom blur, bloom, anamorphic streaks, lens ghosts, ACES tone-mapping, grade, grain, letterbox.
- `audio/score.py`: the orchestral score (strings, horns, choir, celesta, harp, taiko…), composed as MIDI and rendered in five stems with FluidSynth and the MuseScore General soundfont.
- `audio/synth.py`: synthesized sound design (wind, risers, impacts, ice, glass).
- `audio/voiceover.py`: the voice-over, made with the open Kokoro-82M model (a blend of two of its male voices, slowed down). The rendered lines are kept in `audio/vo/`.
- `audio/soundtrack.py`: the mix: convolution reverb, voice ducking, bus compression and a limiter, to about −13 LUFS.

## Rebuild

```bash
npm install
sudo apt install fluidsynth musescore-general-soundfont-lossless
pip install numpy scipy soundfile mido
npm run audio                                    # audio/soundtrack.wav
node render/render.mjs --w 1920 --h 1080         # frames/ (headless Chromium, ~2 h on 4 CPU cores)
bash render/encode.sh frames                     # out/*.mp4
node render/build-standalone.mjs                 # out/jagermeister-realtime.html
```

To regenerate the voice-over: `pip install kokoro-onnx`, then `python3 audio/voiceover.py <kokoro.onnx> <voices.npz>`.

Live preview: serve the folder (`npx serve .`) and open `index.html` (`?hd` for 1080p, `?t=12` for a still).

Fonts: UnifrakturMaguntia, Cinzel, Cormorant Garamond, Montserrat, Grenze Gotisch (SIL OFL, via Fontsource).
Kokoro-82M is Apache-2.0; the MuseScore General soundfont is MIT.
Jägermeister and its marks belong to Mast-Jägermeister SE. This is an unofficial spec piece.
