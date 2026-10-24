#!/usr/bin/env python3
"""qa_onsets.py -- where does the audible attack of each hit instrument land relative to the note time?

Renders single notes (no humanisation) at t = 0.5 s through the sampler and reports, per layer,
the time of the first sample above -30 / -20 / -10 dB of the note's peak (ms, relative to t).
The sampler aligns each sample so that a point `align_db` below its peak lands on t; this shows
how much of the attack (stick noise, pluck, pre-ring) then sounds before the frame.

    nice -n 10 python3 qa_onsets.py
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'sampler'))
from sampler import Note, Sampler  # noqa: E402

TESTS = [('perc.timpani', 'D2'), ('perc.timpani', 'A2'), ('perc.bass_drum', 55), ('perc.bass_drum.b', 57),
         ('perc.bass_drum.vcsl', 57), ('perc.bass_drum.muted', 55), ('perc.toms.low', 57), ('perc.frame_drum', 57),
         ('perc.cymbal.crash', None), ('perc.cymbal.crash2', None), ('perc.cymbal.sus', None), ('perc.gong.c', None),
         ('perc.snare.rope', None), ('perc.claves', 65), ('perc.tubular_bells', 'D4'), ('strings.violins.pizz', 'A4'),
         ('strings.harp', 'A3'), ('strings.basses.pizz', 'D1'), ('keys.piano', 'D1'), ('keys.piano', 'D3'),
         ('brass.trombones.sus', 'D2'), ('brass.tuba.sus', 'D2'), ('brass.horns.sus', 'D3'), ('strings.violins.spic', 'D5')]


def first_above(m, i0, rel_db):
    w = np.abs(m[i0 - 24000:i0 + 24000])
    pk = w.max()
    k = np.nonzero(w >= pk * 10 ** (rel_db / 20))[0]
    return (k[0] - 24000) / 48.0 if len(k) else None


def main():
    s = Sampler()
    print(f"{'instrument':24s} {'pitch':5s} {'vel':>4s}   -30 dB   -20 dB   -10 dB  (ms vs note time)")
    for inst, p in TESTS:
        for v in (60, 100, 127):
            s.reset()
            buf = s.render([Note(inst, 0.5, 1.0, p, v)], seconds=2.0)
            m = buf.mean(axis=0)
            i0 = 24000
            r = [first_above(m, i0, d) for d in (-30, -20, -10)]
            print(f"{inst:24s} {str(p):5s} {v:4d}  " + '  '.join(f'{x:7.1f}' for x in r))


if __name__ == '__main__':
    main()
