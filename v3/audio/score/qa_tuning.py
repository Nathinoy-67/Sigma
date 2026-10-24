#!/usr/bin/env python3
"""qa_tuning.py -- spot-check the sampler's tuning with an independent pitch detector.

Each test note is rendered through the full Sampler chain (catalog note mapping + octave
convention + polyphase pitch shift + unison doubling), then its fundamental is measured with
YIN, refined from the first harmonics.  Timpani are checked on their principal (1,1) mode, bells
on their strike tone.  Reports the deviation in cents and any octave error.

    nice -n 10 python3 qa_tuning.py [--quick] [--out qa_tuning.json]
"""
import argparse
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'sampler'))
sys.path.insert(0, HERE)
from sampler import SR, Note, Sampler, note_to_midi, midi_name  # noqa: E402
import audio_tools as A  # noqa: E402

# (instrument, [pitches], [velocities], window (t0, t1) seconds after the note start, kind)
TESTS = [
    ('strings.violins.sus', ['G3', 'D4', 'A4', 'F#5', 'A5', 'D6'], [50, 110], (0.35, 1.2), 'h'),
    ('strings.violins.trem', ['D4', 'E5', 'F5', 'G5'], [60, 110], (0.35, 1.2), 'h'),
    ('strings.violins.spic', ['D4', 'A4', 'D5', 'F#5', 'A5'], [70, 115], (0.02, 0.16), 'h'),
    ('strings.violins.pizz', ['D4', 'A4', 'D5'], [80], (0.02, 0.25), 'h'),
    ('strings.violin_solo.sus', ['A5', 'D6', 'A6'], [40], (0.35, 1.2), 'h'),
    ('strings.violas.sus', ['C3', 'D3', 'A3', 'F4'], [60, 110], (0.35, 1.2), 'h'),
    ('strings.violas.spic', ['D3', 'F3', 'A3', 'D4'], [70, 115], (0.02, 0.16), 'h'),
    ('strings.violas.trem', ['D3', 'A3', 'D4'], [80], (0.35, 1.2), 'h'),
    ('strings.celli.sus', ['C2', 'D2', 'A2', 'D3', 'F3'], [60, 110], (0.35, 1.2), 'h'),
    ('strings.celli.spic', ['D2', 'D3', 'F3', 'A3'], [70, 115], (0.02, 0.18), 'h'),
    ('strings.celli.trem', ['D2', 'D3'], [80], (0.35, 1.2), 'h'),
    ('strings.celli.pizz', ['D2', 'D3', 'A3'], [80], (0.03, 0.3), 'h'),
    ('strings.basses.sus', ['D1', 'F#1', 'A1', 'D2'], [60, 110], (0.35, 1.2), 'h'),
    ('strings.basses.spic', ['D1', 'E1', 'F1', 'D2'], [80, 115], (0.02, 0.2), 'h'),
    ('strings.basses.pizz', ['D1', 'A1', 'D2'], [90], (0.03, 0.3), 'h'),
    ('strings.basses.trem', ['D1', 'D2'], [90], (0.35, 1.2), 'h'),
    ('strings.harp', ['D2', 'A2', 'D3', 'A4', 'D5', 'D6'], [70, 110], (0.03, 0.4), 'h'),
    ('brass.horns.sus', ['D3', 'F3', 'A3', 'Bb3', 'B3', 'D4', 'E4'], [60, 115], (0.3, 1.0), 'h'),
    ('brass.horn.sus', ['D4', 'A4', 'Bb4'], [70], (0.3, 1.0), 'h'),
    ('brass.horns.stac', ['D3', 'A3'], [110], (0.03, 0.15), 'h'),
    ('brass.trumpets.sus', ['A4', 'Bb4', 'B4', 'D5', 'E5', 'F5'], [70, 115], (0.3, 1.0), 'h'),
    ('brass.trombones.sus', ['D2', 'F2', 'A2', 'Bb2', 'D3', 'F3'], [60, 115], (0.3, 1.0), 'h'),
    ('brass.trombones.stac', ['D2', 'D3'], [115], (0.04, 0.2), 'h'),
    ('brass.tuba.sus', ['D1', 'D2', 'F2', 'A2'], [70, 115], (0.3, 1.0), 'h'),
    ('brass.tuba.stac', ['D2', 'E2', 'F2'], [110], (0.04, 0.2), 'h'),
    ('woods.bassoon.sus', ['D2', 'F2', 'A2', 'D3'], [70, 110], (0.3, 1.0), 'h'),
    ('woods.bassoon.stac', ['D2', 'F2'], [100], (0.03, 0.15), 'h'),
    ('keys.piano', ['D2', 'D3', 'F4', 'A4'], [50, 100], (0.05, 0.6), 'h'),
    ('keys.organ', ['D2', 'D3', 'D4'], [100], (0.4, 1.4), 'h'),
    ('keys.organ.pedal', ['D1', 'A1', 'D2', 'A2'], [100], (0.4, 1.4), 'h'),
    # timpani: perceived pitch = (1,1) mode after the attack glide (loud strokes start up to ~1 st sharp)
    ('perc.timpani.all', ['D2', 'F2', 'A2', 'D3'], [70, 120], (0.3, 1.2), 'timp'),
    ('perc.timpani.vsco', ['A2', 'D3'], [100], (0.3, 1.2), 'timp'),
    ('perc.timpani', ['D2', 'F2', 'G2', 'A2', 'Bb2', 'C3', 'D3'], [50, 85, 120], (0.3, 1.2), 'timp'),
    ('perc.timpani.roll', ['D2', 'A2', 'D3'], [90], (0.3, 1.4), 'timp'),
    # bells: strike tone = virtual pitch of modes 4-6 (~2:3:4); checked separately (README / report)
]
QUICK = {'strings.violins.sus', 'strings.celli.spic', 'strings.basses.sus', 'brass.horns.sus', 'brass.trumpets.sus',
         'brass.trombones.sus', 'brass.tuba.sus', 'keys.organ.pedal', 'perc.timpani', 'strings.harp', 'keys.piano',
         'perc.timpani.vsco', 'perc.timpani.roll', 'brass.tuba.stac', 'perc.timpani.all'}


def measure(buf, kind, midi, t_note, win, piano=False):
    t0, t1 = t_note + win[0], t_note + win[1]
    f_exp = A.midi_to_hz(midi)
    if kind == 'timp':
        f = A.spectral_peak(buf, SR, f_exp * 0.8, f_exp * 1.25, t0, t1)
        return f, 0.0
    fmin = max(20.0, f_exp / 2.3)
    fmax = min(4000.0, f_exp * 2.3)
    f0, ap = A.yin_f0(buf, SR, fmin=fmin, fmax=fmax, t0=t0, t1=t1, hop=0.01)
    f = A.refine_f0(buf, SR, f0, t0, t1, H=1 if piano else 6)
    return f, ap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--only', default='')
    ap.add_argument('--out', default=os.path.join(HERE, 'qa_tuning.json'))
    a = ap.parse_args()
    s = Sampler(threads=2)
    rows = []
    for inst, pitches, vels, win, kind in TESTS:
        if a.quick and inst not in QUICK:
            continue
        if a.only and not inst.startswith(a.only):
            continue
        for p in pitches:
            for v in vels:
                s.reset()
                midi = note_to_midi(p)
                t_note = 0.2
                buf = s.render([Note(inst, t_note, 1.6, midi, v)], seconds=2.4)
                f, apv = measure(buf, kind, midi, t_note, win, piano=inst.startswith('keys.piano'))
                if not np.isfinite(f) or f <= 0:
                    rows.append(dict(inst=inst, note=p, vel=v, f=None))
                    print(f'{inst:26s} {p:4s} v{v:<3d}  no pitch')
                    continue
                dm = A.hz_to_midi(f) - midi
                octv = int(round(dm / 12.0))
                cents = 100 * (dm - 12 * octv)
                flag = ''
                if octv != 0:
                    flag += f' OCTAVE {octv:+d}'
                if abs(cents) > 25:
                    flag += ' DETUNED'
                rows.append(dict(inst=inst, note=p, vel=v, hz=round(f, 3), expected_hz=round(A.midi_to_hz(midi), 3),
                                 cents=round(cents, 1), octave=octv, aperiodicity=round(apv, 3), flag=flag.strip()))
                print(f'{inst:26s} {p:4s} v{v:<3d} {f:9.2f} Hz  exp {A.midi_to_hz(midi):8.2f}  '
                      f'{cents:+6.1f} c  ap={apv:.2f}{flag}', flush=True)
    with open(a.out, 'w') as fh:
        json.dump(dict(rows=rows, warnings=s.warnings), fh, indent=1)
    bad = [r for r in rows if r.get('flag')]
    print(f'\n{len(rows)} notes checked, {len(bad)} flagged')
    for r in bad:
        print('  ', r)


if __name__ == '__main__':
    main()
