#!/usr/bin/env python3
"""qa_scan_samples.py -- measure the pitch of EVERY sample of the instruments the score uses.

For each sample: YIN f0 in a stable window, refined from the fundamental (h1) and from the first
six harmonics (h6).  Deviation from the catalog pitch in cents.  Flags octave errors and
detunings > 20 cents where the two estimators agree (aperiodicity < 0.25).
Writes qa_scan_samples.json:  {path: {inst, note, layer, rr, yin_c, h1_c, h6_c, ap}}.

    nice -n 10 python3 qa_scan_samples.py
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'sampler'))
sys.path.insert(0, HERE)
import audio_tools as A  # noqa: E402
from sampler import Sampler, midi_name  # noqa: E402

IDS = ['strings.violins.sus', 'strings.violins.spic', 'strings.violins.trem', 'strings.violins.pizz',
       'strings.violas.sus', 'strings.violas.spic', 'strings.violas.trem', 'strings.violas.pizz',
       'strings.celli.sus', 'strings.celli.spic', 'strings.celli.trem', 'strings.celli.pizz',
       'strings.basses.sus', 'strings.basses.spic', 'strings.basses.trem', 'strings.basses.pizz',
       'strings.violin_solo.sus', 'strings.harp', 'brass.horn.sus', 'brass.horn.stac', 'brass.trumpet.sus',
       'brass.trumpet.stac', 'brass.trombone.sus', 'brass.trombone.stac', 'brass.tuba.sus', 'brass.tuba.stac',
       'woods.bassoon.sus', 'woods.bassoon.stac', 'keys.piano', 'keys.organ', 'keys.organ.pedal']
SHORT = ('spic', 'stac', 'pizz')


def one(job):
    iid, path, pitch, onset, end, layer, rr = job
    try:
        x, sr = sf.read(path, always_2d=True, dtype='float32')
        x = x.T
        short = any(k in iid for k in SHORT) or iid == 'strings.harp' or iid == 'keys.piano'
        t0 = onset + (0.03 if short else 0.3)
        t1 = min(end, onset + (0.25 if short else 1.1))
        if t1 - t0 < 0.08:
            t0, t1 = onset + 0.02, max(onset + 0.12, end)
        f_exp = A.midi_to_hz(pitch)
        f0, ap = A.yin_f0(x, sr, fmin=max(20, f_exp / 2.3), fmax=f_exp * 2.3, t0=t0, t1=t1, hop=0.01)
        f1 = A.refine_f0(x, sr, f0, t0, t1, H=1)
        f6 = A.refine_f0(x, sr, f0, t0, t1, H=6)
        c = lambda f: round(100 * (A.hz_to_midi(f) - pitch), 1) if np.isfinite(f) and f > 0 else None
        return path, dict(inst=iid, note=midi_name(pitch), pitch=pitch, layer=layer, rr=rr, yin_c=c(f0), h1_c=c(f1),
                          h6_c=c(f6), ap=round(float(ap), 3))
    except Exception as e:  # pragma: no cover
        return path, dict(inst=iid, error=str(e))


def main():
    s = Sampler()
    jobs, seen = [], set()
    for iid in IDS:
        inst = s.instrument(iid)
        for smp in inst.samples:
            if smp.path in seen:
                continue
            seen.add(smp.path)
            jobs.append((iid, smp.path, smp.pitch, smp.onset, smp.end, smp.layer, smp.rr))
    out = {}
    with ProcessPoolExecutor(max_workers=2) as ex:
        for i, (p, r) in enumerate(ex.map(one, jobs, chunksize=8)):
            out[p] = r
            if i % 200 == 0:
                print(f'{i}/{len(jobs)}', flush=True)
    json.dump(out, open(os.path.join(HERE, 'qa_scan_samples.json'), 'w'), indent=0)
    # summary per instrument
    by = {}
    for p, r in out.items():
        by.setdefault(r['inst'], []).append(r)
    print(f'\n{"instrument":24s} {"n":>4s} {"median_c":>8s} {"p10":>6s} {"p90":>6s}  flagged')
    for iid in IDS:
        rs = [r for r in by.get(iid, []) if r.get('h6_c') is not None]
        ok = [r for r in rs if r['ap'] < 0.25 and abs(r['h6_c']) < 60]
        cs = np.array([r['h6_c'] for r in ok]) if ok else np.zeros(1)
        flags = []
        for r in rs:
            agree = r['yin_c'] is not None and abs(r['yin_c'] - r['h6_c']) < 15
            if agree and abs(r['h6_c']) > 1100:
                flags.append(f"{r['note']}/L{r['layer']}/rr{r['rr']} OCT {r['h6_c']:+.0f}c")
            elif agree and r['ap'] < 0.25 and 20 < abs(r['h6_c']) < 200:
                flags.append(f"{r['note']}/L{r['layer']}/rr{r['rr']} {r['h6_c']:+.0f}c")
        print(f'{iid:24s} {len(rs):4d} {np.median(cs):+8.1f} {np.percentile(cs, 10):+6.1f} {np.percentile(cs, 90):+6.1f}  '
              f'{"; ".join(flags)}')


if __name__ == '__main__':
    main()
