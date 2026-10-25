# ONE YEAR. ONE SECOND.

A 60-second photoreal spec film about Jägermeister and the birth of the Jägerbomb, built from scratch:
every set, prop, liquid and light is modelled in code and path-traced in Blender Cycles, the score is played
from real orchestral samples, the narrator is a deep male neural voice, and the type is set in post.

**The idea.** Two time signatures. Time-lapse compresses six decades (three days of maceration, a year in an
oak cask); extreme slow motion stretches the one legendary second (the shot glass dropping into the energy drink)
to about seven. *A year in oak. A second in glass.*

| Time | Picture | Narration |
|---|---|---|
| 0:00 | Extreme macro: a 1930s typewriter strikes '1934' into a recipe card at dawn | "1934. Curt Mast perfects a recipe." |
| 0:03 | Apothecary mise en place: star anise, cinnamon, juniper, saffron, chamomile, orange peel… | "Fifty-six herbs, blossoms, roots and fruits." |
| 0:06 | A brass balance settles; a linen sachet macerates as three days flicker past | |
| 0:09 | The typed recipe, every ingredient overtyped XXXX, a red GEHEIM stamp | "Which ones? Still a secret." |
| 0:12 | Match cut: the stamp becomes a chalked cask head; a year of sunlight sweeps a brick vault | "Then it waits. A full year, in oak." |
| 0:19 | The cellar's oculus becomes a freighter's porthole on the North Atlantic, 1970s | "In the seventies, it crosses an ocean." |
| 0:24 | An ice-cold tap pours a ruby-edged rope into a frosted shot; its mirrored lamp becomes… | "And America serves it ice cold." |
| 0:27 | …the full moon over Lake Tahoe; a pink neon OPEN stutters on; an empty stool still turning | "Around 1997… somebody has an idea." |
| 0:35 | A ring of melting frost where the shot stood | "Nobody knows exactly who. Everybody knows the name." |
| 0:39 | Held breath, then total silence: the shot drops; the crown, the spray, the bloom of ink in gold | |
| 0:47 | The Jägerbomb and the frosted bottle by the moonlit window | "A year in oak. A second in glass." |
| 0:56 | The neon dies. End card. | "Jägermeister." |

The history is told as it is usually reported (Curt Mast, Wolfenbüttel, 1934; Sidney Frank's import business in
the 1970s; the Jägerbomb most often credited to bars around Lake Tahoe c. 1997, origin disputed, and the film says so).

## How it is made

- `blender/lib/` the framework: scene/Cycles/AgX setup, camera rig with lens breathing and rack focus, a material
  library (glass with fingerprints and condensation fog, liquids with Beer-Lambert absorption, frost shells with a
  keyed melt track, woods, metals, paper, plaster, brick…), props (shot glass, highball with closed-form carbonation
  and condensation, square-shouldered bottle with our own label art), botanicals (rigid-body-settled heaps), and
  `fluid.py` which surfaces the simulation's particles with Geometry Nodes.
- `blender/sets/` seven sets: the 1934 workroom, the cask cellar, the freighter hold, the 1980s back bar, the
  Lake Tahoe lodge bar (with a painted exterior plate), the glass stage and the end slate.
- `blender/shots/sNN.py` one file per shot (23 shots), each deterministic; `render_shot.py` renders any frame range;
  `render_queue.sh` / `resume_render.sh` run resumable render queues.
- `blender/sims/mpm_plunge.py` the hero splash: a 3D MLS-MPM liquid simulation (Taichi, ~800 000 particles, 1 mm
  grid) of a full shot glass plunging into a highball, written to `frames/sim2/`.
- `blender/art/` artwork drawn with PIL: the typed recipe card (Courier 10 Pitch, ribbon weave, slug impressions,
  rubber stamp), hand-authored chalk numerals, spray-stencilled crate markings, the Tahoe plate.
- `audio/sampler/` + `audio/score/` the score "PATIENCE", composed as MIDI and played from the VSCO-2 CE and VCSL
  orchestral sample libraries (CC0), hit points locked to the cuts, a full stop of silence before the plunge.
- `audio/vo/` the narration: Supertonic 3 (MIT) male voice 9 (F0 ≈ 88 Hz), 20 takes per line, each checked by Whisper
  and scored with DNSMOS, the best take kept, then a trailer-VO chain (EQ, de-esser, compression, saturation, room).
- `audio/final_mix.py` score + narration with ducking, -14 LUFS, -1 dBTP.
- `post/finish.py` the edit and the finish: 2D moves on the high-resolution stills with the three circle match cuts
  measured on the renders, upscale to 1920x804, halation, grade, vignette, grain, letterbox, era supers, title,
  tagline, subtitles in the bottom bar, end card; `--encode` muxes the final mix into H.264 and HEVC.

## The film

- `out/one-year-one-second.mp4` master, 1920x1080, H.264, 24 fps, 60 s, stereo AAC (-14 LUFS)
- `out/one-year-one-second-hevc.mp4` the same in HEVC (smaller, best for Apple devices)
- `out/one-year-one-second-share.mp4` a lighter copy for phones and messaging
- `out/one-year-one-second.en.srt` the English subtitles as a sidecar file (they are also burned in)
- `out/poster.jpg` a poster frame

Jägermeister and its marks belong to Mast-Jägermeister SE. This is an unofficial spec piece; the label artwork is our
own and no logo is shown. Please enjoy responsibly.
