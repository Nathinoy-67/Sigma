# Production plan — "ONE YEAR. ONE SECOND." (v3, photoreal)

The creative source of truth is `TREATMENT.md` / `treatment.json` (shots, timings, narration, music map, titles).
This file records the production rules and where we deliberately deviate from the treatment to stay within
the machine's budget. Everything below wins over the treatment when they disagree.

## Machine and tools
- 4 CPU cores, no GPU, ~15 GB free disk. Other jobs share the CPU: keep look-dev renders small and `nice -n 10` them.
- Blender 5.2 as a Python module: `/home/user/tools/blender-venv/bin/python script.py` (`import bpy`). Cycles CPU + OpenImageDenoise.
  Run scripts with `python script.py` (not `blender -b`). EEVEE is not usable (software GL is as slow as Cycles).
- System `python3` (3.13) has numpy, scipy, soundfile, pillow, sherpa_onnx.
- Fonts (fc-list): Courier 10 Pitch, Inter, Inter Display (Thin…Black), JetBrains Mono, Liberation Sans, DejaVu.
- No external assets: no HDRIs, photo textures, downloaded models or footage. Everything procedural / modelled in code;
  artwork (labels, stencils, card) drawn with PIL into images in `v3/blender/textures/`.
- No people, faces or hands. People are implied (a turning stool, a frost ring, a shadow).

## Format
- 24 fps, 60.0 s, 1,440 frames, 96 BPM (1 beat = 15 frames, 1 bar = 60 frames).
- Render 1920×804 (2.39:1); the 1920×1080 master adds 138 px bars that carry subtitles/legal text only.
- Look-dev: 640×268 at 16 spp. Finals: adaptive sampling, noise threshold 0.02–0.03, max 64–128 spp, OIDN (albedo+normal).
- Colour: AgX view transform ("AgX - Base" look Medium/High Contrast as fits), exposure per shot.
- Real-world metric scale in every set (a shot glass is 6 cm tall). 36 mm sensor, real focal lengths/f-stops.
  Anamorphic feel: `cam.data.dof.aperture_ratio = 1.5` (oval bokeh), 0 blades.
- Lens finish, grain, halation, vignette, letterbox, type and subtitles are done in post (`v3/post/`), not in Blender.

## Code layout
- `v3/blender/lib/` shared framework: `scene.py` (fresh scene, Cycles settings, colour management, output),
  `camera.py` (camera rig, focus empty, lens breathing, motion-control easing), `materials.py` (glass 1.52, energy drink 1.34,
  Jägermeister 1.355 with mahogany/ruby absorption, frost, condensation, metals, woods, paper, chalk, brick, plaster…),
  `props.py` (shot glass, highball, square-shouldered green bottle with our own label art, coaster, etc.), `botanicals.py`.
- `v3/blender/sets/<set>.py`: builds one set; `v3/blender/shots/<shot>.py`: camera + animation for one shot on a set.
- `v3/blender/render_shot.py --shot S18 --start 0 --end 44 --res final|look --out frames/S18`: builds the set, applies the
  shot, renders the frame range to PNG. Frame numbers are local to the shot; the edit decides the timeline position.
- Every shot must be deterministic (fixed seeds) so frame ranges can be rendered on different machines and spliced.
- Frames go to `v3/frames/<shot>/` (git-ignored); look-dev stills to `v3/lookdev/` (small JPEGs, committed sparingly).

## Scope decisions (deviations from the treatment)
- S01: no typewriter mechanism. Extreme macro of the card being typed: characters appear strike by strike (ink impression,
  ribbon texture), the rubber platen roller soft at the top of frame. Strikes on f15, f30, f45, f60.
- SIM 1 (tap pour) is faked: an animated, noise-displaced liquid rope and a rising fill level. No Mantaflow.
- SIM 3 (plume) is a procedural, animated absorption volume shaped around the sunken shot glass and the SIM 2 surface,
  not a guided gas sim.
- SIM 2 (hero plunge) stays a Mantaflow FLIP bake (resolution chosen by test; it may be baked on another machine).
- Static or near-static shots (S05 drift, S08 push, S12 push, S13 moonrise, S22, S23) are rendered as one high-resolution
  still (or a few states) and animated in 2D in post. Time-lapses render on twos/threes. Rack focus shots may render
  a reduced set of focus states.
- Render budget target: average ≤ 40 s per unique frame at final settings on 4 cores.

## Quality bar
Every shot must read as a real photograph from a high-end spirits commercial: real materials (bevelled edges, imperfection,
dust, fingerprints, wear), motivated practical lighting, shallow depth of field, nothing floating, no CG-clean surfaces,
no plastic-looking liquids. When in doubt: darker, closer, tighter focus.
