#!/usr/bin/env python3
"""fix_tuning.py -- tuning QA fixes applied to catalog.json (run after build_catalog.py).

The QA pass (v3/audio/score/qa_tuning.py + qa_scan_samples.py, an independent YIN + harmonic
pitch detector run on notes rendered through the sampler and on every raw sample) found:

 1. Timpani (VCSL Timpani 1 + 2, rolls, VSCO copies): the catalog's principal-mode detector took the FIRST maximum
    of a template score evaluated with +-25-cent windows on a 5-cent grid, so every drum was
    read ~15-30 cents flat and the sampler then shifted it SHARP by that much (QA: D3 +24..+38 c,
    A2 +20..+48 c).  Fix: centre of the score plateau, then the exact (1,1)-mode peak frequency
    (parabolic interpolation on a 2^19-point spectrum); per-drum consensus as before, plus a per-sample
    `tune_fix_cents` where a stroke settles 5-60 cents off its drum's consensus.  Several drums of
    Timpani 2 have split heads (two (1,1) peaks ~1 st apart): sampler id `perc.timpani.clean` keeps
    only the drums with a single clean principal mode.
 2. Pipe Organ "Loud Pedal": the octave was decided from sibling folders (+12) although its
    own detector votes said 0.  The registration includes a 16' stop, so Rode_Pedal_C1 sounds
    C1 (32.7 Hz).  The sampler works in SOUNDING pitch, so the offset must be 0 (QA: every
    pedal note sounded one octave below the requested pitch).
 3. Per-sample fine tuning: samples whose measured pitch deviates by 8-60 cents, where YIN, a
    fundamental-only and a six-harmonic estimate agree within 10 cents and the sound is periodic
    (aperiodicity < 0.25), get `tune_fix_cents` (= -deviation), which sampler.py adds to the
    pitch shift.  Mostly the concert harp (played ~7-13 cents flat), tuba F1 and soft tuba staccati.
 4. Excluded samples (`exclude: true`): Cello Section trem B2 v2 (contains a strong lower octave:
    0.5f / 1.5f / 2.5f partials at -2..-8 dB).

Idempotent: original values are kept in `midi_float_orig` / `midi_orig`.

    python3 fix_tuning.py [--scan ../score/qa_scan_samples.json]
"""
import argparse
import json
import math
import os
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
CAT = os.path.join(HERE, 'catalog.json')

TIMPANI_GROUPS = ['VCSL/Membranophones/Struck Membranophones/Timpani 2/Hit::Timpani_Hit',
                  'VCSL/Membranophones/Struck Membranophones/Timpani 1/Hit::Timpani_Hit',
                  'VCSL/Membranophones/Struck Membranophones/Timpani 1/Roll::Timpani_Roll',
                  'VSCO-2-CE/Percussion/Timpani::Timpani_Hit',
                  'VSCO-2-CE/Percussion/Timpani/Rolls::Timpani_Roll']
PEDAL_GROUP = 'VCSL/Aerophones/Edge-blown Aerophones/Pipe Organ/Loud Pedal'
EXCLUDE = ['VSCO-2-CE/Strings/Cello Section/trem/trem_B2_v2_1.wav']


def _spec(x, sr, t0, t1):
    seg = x[int(t0 * sr):int(t1 * sr)]
    seg = (seg - seg.mean()) * np.hanning(len(seg))
    n = 1 << 19
    S = np.abs(np.fft.rfft(seg, n))
    fr = np.fft.rfftfreq(n, 1 / sr)
    m = (fr > 25) & (fr < 8000)
    Sd = 20 * np.log10(S + 1e-9)
    fl = np.median(Sd[m])
    return fr, S, np.clip(Sd - fl, 0, None)


def _val(fr, S, f, cents):
    lo, hi = f * 2 ** (-cents / 1200), f * 2 ** (cents / 1200)
    i0, i1 = np.searchsorted(fr, [lo, hi])
    return float(S[i0:i1 + 1].max()) if i1 > i0 else 0.0


def timpani_pitch(path, onset, end):
    x, sr = sf.read(path, always_2d=True, dtype='float64')
    mono = x.mean(axis=1)
    t0, t1 = onset + 0.35, min(end, onset + 1.6)
    if t1 - t0 < 0.3:
        t0, t1 = onset + 0.08, min(end, onset + 0.9)
    fr, S, Sd = _spec(mono, sr, t0, t1)
    cands = 55 * 2 ** (np.arange(0, 2900, 5) / 1200)
    sc = np.array([_val(fr, Sd, f, 25) + 0.7 * _val(fr, Sd, 1.5 * f, 25) + 0.5 * _val(fr, Sd, 2 * f, 25)
                   + 0.3 * _val(fr, Sd, 2.5 * f, 25) for f in cands])
    top = np.nonzero(sc >= sc.max() - 1e-9)[0]
    # plateau of equal scores around the first maximum -> its centre
    run = [top[0]]
    for i in top[1:]:
        if i == run[-1] + 1:
            run.append(i)
        else:
            break
    fc = cands[run[len(run) // 2]]
    # exact (1,1)-mode peak within +-40 cents
    lo, hi = np.searchsorted(fr, [fc * 2 ** (-40 / 1200), fc * 2 ** (40 / 1200)])
    k = lo + int(np.argmax(S[lo:hi]))
    a, b, c = np.log(S[k - 1] + 1e-12), np.log(S[k] + 1e-12), np.log(S[k + 1] + 1e-12)
    p = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else 0.0
    f = (k + p) * (fr[1] - fr[0])
    return 69 + 12 * math.log2(f / 440.0)


def peak_near(path, onset, end, midi, cents=50):
    """Dominant spectral peak within +-cents of `midi` (the drum consensus), window onset+0.35..1.6 s."""
    x, sr = sf.read(path, always_2d=True, dtype='float64')
    mono = x.mean(axis=1)
    t0, t1 = onset + 0.35, min(end, onset + 1.6)
    if t1 - t0 < 0.3:
        t0, t1 = onset + 0.08, min(end, onset + 0.9)
    fr, S, _ = _spec(mono, sr, t0, t1)
    f0 = 440 * 2 ** ((midi - 69) / 12)
    lo, hi = np.searchsorted(fr, [f0 * 2 ** (-cents / 1200), f0 * 2 ** (cents / 1200)])
    k = lo + int(np.argmax(S[lo:hi]))
    a, b, c = np.log(S[k - 1] + 1e-12), np.log(S[k] + 1e-12), np.log(S[k + 1] + 1e-12)
    p = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else 0.0
    return 69 + 12 * math.log2((k + p) * (fr[1] - fr[0]) / 440.0)


def _job(args):
    path, onset, end = args
    try:
        return path, timpani_pitch(path, onset, end)
    except Exception:
        return path, None


def fix_timpani(cat, log):
    for gk in TIMPANI_GROUPS:
        g = cat['groups'][gk]
        jobs = [(s['path'], s.get('onset_s', 0.0), s.get('end_s', s['len_s'])) for s in g['samples']]
        with ProcessPoolExecutor(max_workers=2) as ex:
            res = dict(ex.map(_job, jobs, chunksize=6))
        by_drum = defaultdict(list)
        for s in g['samples']:
            s['f0_midi_refined'] = None if res[s['path']] is None else round(res[s['path']], 3)
            by_drum[s.get('drum', '?')].append(s)
        for d, ss in sorted(by_drum.items()):
            vals = [s['f0_midi_refined'] for s in ss if s['f0_midi_refined'] is not None]
            if not vals:
                continue
            soft = [s['f0_midi_refined'] for s in ss if s['f0_midi_refined'] is not None and s['vel_layer'] <= 1] or vals
            med = float(np.median(soft))
            agree = sum(abs(v - med) < 0.6 for v in vals) / len(vals)
            old = ss[0].get('midi_float_orig', ss[0].get('midi_float'))
            for s in ss:
                s.setdefault('midi_float_orig', s.get('midi_float'))
                s['midi_float'] = round(med, 2)
                s['midi'] = int(round(med))
                s['pitch_confidence'] = round(agree, 2)
                # loud strokes of some drums settle a little off the drum's consensus: per-sample fix
                # from the dominant (1,1) peak within +-50 cents of the consensus
                v = peak_near(s['path'], s.get('onset_s', 0.0), s.get('end_s', s['len_s']), med)
                s['f0_midi_stroke'] = round(v, 3)
                if 0.03 <= abs(v - med) <= 0.5:
                    s['tune_fix_cents'] = round(100 * (med - v), 1)
                else:
                    s.pop('tune_fix_cents', None)
            log.append(dict(fix='timpani', group=gk.split('/', 1)[1], drum=d, old=old, new=round(med, 2),
                            cents=round(100 * (med - old), 1) if old is not None else None, agreement=round(agree, 2)))


def fix_pedal(cat, log):
    g = cat['groups'][PEDAL_GROUP]
    if g.get('octave_offset') == 0:
        return
    for s in g['samples']:
        s.setdefault('midi_orig', s['midi'])
        s['midi'] = s['midi_named']
        n = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        s['note'] = f"{n[s['midi'] % 12]}{s['midi'] // 12 - 1}"
    old = g['octave_offset']
    g['octave_offset'] = 0
    g['octave_method'] = 'QA fix: sounding pitch (16\' fundamental measured), detector votes'
    mids = [s['midi'] for s in g['samples']]
    g['range'] = [g['samples'][int(np.argmin(mids))]['note'], g['samples'][int(np.argmax(mids))]['note']]
    g['range_midi'] = [min(mids), max(mids)]
    log.append(dict(fix='pedal_octave', group=PEDAL_GROUP, old_offset=old, new_offset=0))


def fix_fine(cat, scan, log):
    by_path = {}
    for gk, g in cat['groups'].items():
        for s in g['samples']:
            by_path[s['path']] = s
    for p, r in scan.items():
        s = by_path.get(p)
        if s is None or r.get('h6_c') is None or r.get('h1_c') is None or r.get('yin_c') is None:
            continue
        if 'Pipe Organ' in p or 'Piano' in p:
            continue  # organ: octave/mixture ambiguity; piano: stretch tuning by design
        d = r['h6_c']
        agree = abs(r['yin_c'] - d) < 10 and abs(r['h1_c'] - d) < 10
        if agree and r['ap'] < 0.25 and 8 <= abs(d) <= 60:
            fix = round(-float(np.mean([r['yin_c'], r['h1_c'], r['h6_c']])), 1)
            s['tune_fix_cents'] = fix
            log.append(dict(fix='fine', inst=r['inst'], note=r['note'], layer=r['layer'], rr=r['rr'],
                            measured_c=d, tune_fix_cents=fix, file=os.path.basename(p)))
        elif 'tune_fix_cents' in s:
            del s['tune_fix_cents']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scan', default=os.path.join(HERE, '..', 'score', 'qa_scan_samples.json'))
    a = ap.parse_args()
    cat = json.load(open(CAT))
    log = []
    fix_timpani(cat, log)
    fix_pedal(cat, log)
    if os.path.exists(a.scan):
        fix_fine(cat, json.load(open(a.scan)), log)
    for gk, g in cat['groups'].items():
        for s in g['samples']:
            if any(s['path'].endswith(e) for e in EXCLUDE):
                s['exclude'] = True
                log.append(dict(fix='exclude', file=s['file']))
    cat['tuning_fixes'] = dict(script='fix_tuning.py', n=len(log))
    with open(CAT, 'w') as f:
        json.dump(cat, f, indent=1)
    import build_catalog
    build_catalog.write_summary(cat, os.path.join(HERE, 'catalog_summary.md'))
    with open(os.path.join(HERE, 'fix_tuning.log.json'), 'w') as f:
        json.dump(log, f, indent=1)
    for r in log:
        if r['fix'] != 'fine':
            print(r)
    fine = [r for r in log if r['fix'] == 'fine']
    print(f'{len(fine)} per-sample fine-tuning corrections:')
    by = defaultdict(list)
    for r in fine:
        by[r['inst']].append(r['tune_fix_cents'])
    for k, v in by.items():
        print(f'  {k:24s} n={len(v):3d}  median fix {np.median(v):+.1f} c  range {min(v):+.1f}..{max(v):+.1f}')


if __name__ == '__main__':
    main()
