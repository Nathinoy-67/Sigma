#!/usr/bin/env python3
"""measure.py -- measurements of the rendered PATIENCE score (premix + stems).

  * integrated loudness (BS.1770-4), LRA, true peak (4x), sample peak, clipping
  * momentary-loudness maxima and the loudness at the reserved peak frames
  * per-section loudness of every stem and octave-band spectrum of the premix
  * frame-accuracy of the hits (onset detection around each expected frame)
  * the dead cut at f660, total digital silence f1005-f1019, the end fade

    python3 measure.py [--dir v3/audio/score]  -> measurements.json + printed report
"""
import argparse
import json
import os
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import audio_tools as A  # noqa: E402

SR = 48000
STEMS = ['orchestra', 'percussion', 'synth_fx', 'foley']
SECTIONS = [  # (name, t0, t1)
    ('Act I  workroom    b1-5   f0-300', 0.0, 12.5),
    ('Act II cellar      b6-8   f300-480', 12.5, 20.0),
    ('Act III crossing   b9-11  f480-660', 20.0, 27.5),
    ('Tahoe  dead cut    b12-14 f660-840', 27.5, 35.0),
    ('Tahoe  the climb   b15-17 f840-1005', 35.0, 41.875),
    ('SILENCE                   f1005-1020', 41.875, 42.5),
    ('Impact + bloom     b18-19 f1020-1140', 42.5, 47.5),
    ('Title + hero       b20-22 f1140-1320', 47.5, 55.0),
    ('Coda + button      b23-24 f1320-1440', 55.0, 60.0),
]
RESERVED = [0, 480, 1020, 1080, 1200, 1380]
HITS = [  # (frame, stem, label, threshold dB over the pre-level)
    (0, 'percussion', 'overture hit', 12), (0, 'synth_fx', 'sub 41 Hz', 12),
    (15, 'foley', 'typebar 1', 12), (30, 'foley', 'typebar 2', 12), (45, 'foley', 'typebar 3', 12),
    (60, 'foley', 'typebar 4', 12), (135, 'orchestra', 'pizz + harp pluck', 6),
    (225, 'orchestra', 'low piano octave D', 6),
    (300, 'percussion', 'HIT 1', 9), (420, 'percussion', "'1935' timp + choke", 6),
    (480, 'percussion', 'HIT 2', 9), (480, 'synth_fx', 'sub boom 45->30 Hz', 6),
    (585, 'percussion', 'choke + timp f585', 6),
    (690, 'foley', 'neon ignition', 12), (780, 'percussion', 'heartbeat 1', 9),
    (1020, 'percussion', 'IMPACT', 12), (1020, 'foley', 'glass plunge', 12), (1020, 'synth_fx', 'sub impact', 12),
    (1080, 'percussion', 'BLOOM', 6), (1140, 'percussion', 'TITLE HIT', 6), (1200, 'percussion', 'HERO HIT', 6),
    (1335, 'foley', 'neon death click', 9), (1350, 'percussion', 'low chime D', 6),
    (1380, 'percussion', 'BUTTON', 9), (1425, 'percussion', 'fuse tick f1425', 9),
    (60, 'percussion', 'fuse tick f60', 9), (90, 'percussion', 'fuse tick f90', 9),
]


def env_db(x, win=0.001):
    m = np.asarray(x, np.float64).mean(axis=0) if x.ndim == 2 else x
    w = max(1, int(win * SR))
    p = np.convolve(m ** 2, np.ones(w) / w, mode='same')
    return 10 * np.log10(np.maximum(p, 1e-20))


def onset(x, frame, thr_db):
    """Onset near `frame`: the steepest rise (3 ms difference of the 1-ms RMS envelope, dB) within
    [-40, +60] ms of the frame, provided it rises at least thr_db; returns (error ms, rise dB)."""
    t = frame / 24.0
    e = env_db(x)
    i0, i1 = max(3 * 48, int((t - 0.04) * SR)), int((t + 0.06) * SR)
    d = e[i0:i1] - e[i0 - 3 * 48:i1 - 3 * 48]
    k = int(np.argmax(d))
    if d[k] < thr_db:
        return None, float(d[k])
    return ((i0 + k - 1.5 * 48) / SR - t) * 1000.0, float(d[k])


def sec_lufs(x, t0, t1):
    seg = x[:, int(t0 * SR):int(t1 * SR)]
    if seg.shape[1] < int(0.4 * SR):
        return float('-inf') if not np.any(seg) else round(A.lufs(np.pad(seg, ((0, 0), (0, int(0.4 * SR)))), SR), 1)
    z, _ = A._block_power(seg, SR, 0.4, 0.1)
    v = -0.691 + 10 * np.log10(max(z.mean(), 1e-20))
    return round(float(v), 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=HERE)
    a = ap.parse_args()
    rd = lambda n: sf.read(os.path.join(a.dir, n), always_2d=True)[0].T
    mix = rd('score_mix.wav')
    st = {k: rd(f'stem_{k}.wav') for k in STEMS}
    out = {}
    # ---------------- global
    g = {}
    for name, x in [('premix', mix)] + list(st.items()):
        tm, mom = A.loudness_curve(x, SR, 0.4, 0.1)
        ts, sht = A.loudness_curve(x, SR, 3.0, 0.1)
        g[name] = dict(lufs_i=round(A.lufs(x, SR), 2), lra=round(A.lra(x, SR), 1), true_peak_dbtp=round(A.true_peak_db(x, SR), 2),
                       sample_peak_dbfs=round(A.sample_peak_db(x), 2), clipped_samples=int(np.sum(np.abs(x) >= 0.9999)),
                       max_momentary=round(float(mom.max()), 1), max_short_term=round(float(sht.max()), 1))
    out['global'] = g
    stem_sum = sum(st.values())
    out['stems_sum_vs_premix_max_abs_diff'] = float(np.abs(stem_sum - mix).max())
    # ---------------- loudness peaks
    tm, mom = A.loudness_curve(mix, SR, 0.4, 0.05)
    peaks = []
    order = np.argsort(mom)[::-1]
    for i in order:
        if all(abs(tm[i] - tm[j]) > 1.6 for j in peaks):
            peaks.append(i)
        if len(peaks) >= 8:
            break
    out['top_momentary_peaks'] = [dict(t_end=round(float(tm[i]), 2), frame_end=round(float(tm[i]) * 24), lufs_m=round(float(mom[i]), 1))
                                  for i in sorted(peaks, key=lambda i: -mom[i])]
    res = []
    for fr in RESERVED:
        t = fr / 24
        w = (tm >= t + 0.15) & (tm <= t + 0.9)
        res.append(dict(frame=fr, max_momentary=round(float(mom[w].max()), 1)))
    # loudest momentary value NOT near a reserved frame
    far = np.ones_like(tm, bool)
    for fr in RESERVED:
        t = fr / 24
        far &= ~((tm >= t) & (tm <= t + 2.2))
    out['reserved_peaks'] = res
    out['max_momentary_elsewhere'] = dict(lufs_m=round(float(mom[far].max()), 1), t_end=round(float(tm[far][np.argmax(mom[far])]), 2))
    # ---------------- sections
    secs = []
    for name, t0, t1 in SECTIONS:
        row = dict(section=name, premix=sec_lufs(mix, t0, t1))
        for k in STEMS:
            row[k] = sec_lufs(st[k], t0, t1)
        bl = A.band_levels(mix, SR, t0, t1) if t1 - t0 > 1 else [None] * len(A.BANDS)
        row['bands_db_rel'] = [None if v is None or not np.isfinite(v) else round(v, 1) for v in bl]
        seg = mix[:, int(t0 * SR):int(t1 * SR)]
        row['peak_dbfs'] = round(A.sample_peak_db(seg), 1) if np.any(seg) else None
        secs.append(row)
    out['sections'] = secs
    out['bands_hz'] = A.BANDS
    # ---------------- hits
    hits = []
    for fr, stem, label, thr in HITS:
        d, rise = onset(st[stem], fr, thr)
        hits.append(dict(frame=fr, stem=stem, label=label, onset_error_ms=None if d is None else round(d, 1),
                         rise_db=None if rise is None else round(float(rise), 1)))
    out['hits'] = hits
    # frame-lock check on the dry render of the locked one-shot percussion (no beds, no rolls)
    dpath = os.path.join(a.dir, 'qa', 'locked_perc_dry.wav')
    if os.path.exists(dpath):
        dg = rd(os.path.join('qa', 'locked_perc_dry.wav')).mean(axis=0)
        frames = [0, 180, 300, 420, 480, 585, 600, 630, 780, 810, 1020, 1080, 1140, 1200, 1350, 1380, 1425]
        lock = []
        for fr in sorted(set(frames)):
            t = fr / 24
            i0, i1 = max(0, int((t - 0.05) * SR)), int((t + 0.05) * SR)
            w = np.abs(dg[i0:i1])
            if w.max() <= 0:
                continue
            pre = w[:int(0.02 * SR)].max()          # ringing tails of earlier hits, -50..-30 ms
            thr = max(w.max() * 10 ** (-30 / 20), pre * 10 ** (10 / 20))
            k = int(np.argmax(w >= thr))
            lock.append(dict(frame=fr, onset_error_ms=round((i0 + k) / SR * 1000 - t * 1000, 2)))
        out['frame_lock_dry_locked_perc'] = lock
    # ---------------- silences / cuts
    i0, i1 = int(round(1005 / 24 * SR)), int(round(1020 / 24 * SR))
    out['silence_f1005_f1020'] = {k: float(np.abs(x[:, i0:i1]).max()) for k, x in [('premix', mix)] + list(st.items())}
    c = int(round(660 / 24 * SR))
    dead = {}
    for k in ('orchestra', 'percussion', 'synth_fx'):
        x = st[k]
        before = 10 * np.log10(np.mean(x[:, c - int(0.1 * SR):c] ** 2) + 1e-20)
        after = 10 * np.log10(np.mean(x[:, c:c + int(0.1 * SR)] ** 2) + 1e-20)
        dead[k] = dict(rms_100ms_before_db=round(before, 1), rms_100ms_after_db=round(after, 1), drop_db=round(before - after, 1))
    out['dead_cut_f660'] = dead
    out['end'] = dict(rms_last_8_frames_db=round(10 * np.log10(np.mean(mix[:, -int(8 / 24 * SR):] ** 2) + 1e-20), 1),
                      last_sample_abs=float(np.abs(mix[:, -1]).max()))
    with open(os.path.join(a.dir, 'measurements.json'), 'w') as f:
        json.dump(out, f, indent=1)
    # ---------------- print
    print('GLOBAL')
    for k, v in g.items():
        print(f'  {k:11s} {v}')
    print(f"  stems sum == premix: max |diff| = {out['stems_sum_vs_premix_max_abs_diff']:.2e}")
    print('LOUDNESS PEAKS (momentary, 400 ms):', [(p['frame_end'], p['lufs_m']) for p in out['top_momentary_peaks']])
    print('  reserved frames:', [(r['frame'], r['max_momentary']) for r in res], ' elsewhere max:', out['max_momentary_elsewhere'])
    print('SECTIONS (mean K-weighted level, LUFS-like)')
    print(f"  {'section':40s} {'premix':>7s} " + ' '.join(f'{k:>10s}' for k in STEMS) + '   peak   bands 20-40..10k-20k (dB rel. total)')
    for r in secs:
        print(f"  {r['section']:40s} {r['premix']:7} " + ' '.join(f'{r[k]:10}' for k in STEMS) +
              f"  {r['peak_dbfs']}  {r['bands_db_rel']}")
    print('HITS (onset error ms)')
    for h in hits:
        print(f"  f{h['frame']:<5d} {h['stem']:10s} {h['label']:28s} {h['onset_error_ms']} ms  (rise {h['rise_db']} dB)")
    print('FRAME LOCK (dry locked percussion, first sample > max(peak-30 dB, tails+10 dB)):',
          [(d['frame'], d['onset_error_ms']) for d in out.get('frame_lock_dry_locked_perc', [])])
    print('SILENCE f1005-f1020 max |x|:', out['silence_f1005_f1020'])
    print('DEAD CUT f660:', dead)
    print('END:', out['end'])


if __name__ == '__main__':
    main()
