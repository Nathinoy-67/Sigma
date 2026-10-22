#!/usr/bin/env python3
"""Walk the VSCO-2-CE and VCSL sample libraries and write catalog.json + catalog_summary.md.

Usage:
    python3 build_catalog.py [--jobs 2] [--limit N] [--out DIR]

For every wav file we record: parsed note name / MIDI note, velocity layer, round robin,
file path, sample rate, channels, length, peak, RMS, a K-weighted momentary loudness
(used by the sampler for gain normalisation), the onset time (leading silence) and the
end of the audible tail.  Pitched samples are also run through a harmonic pitch detector
so that the octave convention of each folder is verified instead of assumed
(VSCO-2-CE orchestral folders name middle C "C3", i.e. one octave below scientific
pitch; VCSL mostly uses C4 = middle C).  Timpani have no note names at all, so their
pitch is detected from the spectrum (principal (1,1) mode).

Samples are grouped into "instrument+articulation" groups: one group per folder for
pitched folders, one group per stroke name ("stem") for flat percussion folders.
"""
import argparse
import json
import math
import os
import re
import sys
import time
from collections import Counter, defaultdict
from multiprocessing import Pool

import numpy as np
import soundfile as sf
from scipy.signal import lfilter

LIBS = {
    'VSCO-2-CE': '/home/user/tools/VSCO-2-CE',
    'VCSL': '/home/user/tools/VCSL',
}
HERE = os.path.dirname(os.path.abspath(__file__))

NOTE_RE = re.compile(r'^([A-Ga-g])([#b]?)(-?\d)$')
PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
DYN = {'pppp': 0, 'ppp': 1, 'pp': 2, 'p': 3, 'mp': 4, 'mp-mf': 4.5, 'mf': 5, 'f': 6, 'ff': 7, 'fff': 8,
       'quiet': 2.5, 'soft': 3, 'medium': 5, 'med': 5, 'loud': 7}
DYN_RE = re.compile(r'^(pppp|ppp|pp|p|mp-mf|mp|mf|fff|ff|f|quiet|soft|medium|med|loud)(\d*)$')
VEL_RE = re.compile(r'^(?:v|vl|dyn)(\d+)$', re.I)
RR_RE = re.compile(r'^(?:rr|r|var)(\d+)$', re.I)
MIC_TOKENS = {'sum', 'mid', 'main', 'close', 'far', 'mainspirit', 'player', 'room'}
TIMP_RE = re.compile(r'^(Timpani)(\d+)([A-Z]?)$')


def note_to_midi(letter, acc, octv):
    """Scientific-pitch MIDI number of a note name (C4 = 60)."""
    m = PC[letter.upper()] + (12 * (int(octv) + 1))
    if acc == '#':
        m += 1
    elif acc == 'b':
        m -= 1
    return m


NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def midi_name(m):
    m = int(round(m))
    return f"{NAMES[m % 12]}{m // 12 - 1}"


def family_of(rel):
    r = rel.lower()
    if r.startswith('strings') or 'chordophones' in r:
        return 'strings' if r.startswith('strings') else 'chordophones'
    if r.startswith('brass'):
        return 'brass'
    if r.startswith('woodwinds'):
        return 'woodwinds'
    if r.startswith('keys'):
        return 'keys'
    if 'percussion' in r or 'membranophones' in r or 'idiophones' in r:
        return 'percussion'
    if 'miscellania' in r:
        return 'fx'
    if 'aerophones' in r:
        return 'aerophones'
    if 'electrophones' in r:
        return 'electrophones'
    return 'other'


def parse_name(fname, reldir):
    """Split a filename into (stem, note, vel, vel_label, rr, mic)."""
    base = os.path.splitext(fname)[0]
    toks = [t for t in re.split(r'[_ ]+', base) if t != '']
    note = None
    vel = None
    vel_label = None
    rr = None
    mic = None
    stem = []
    # special case: VSCO "Keys/Upright Piano/Player_dyn1_rr1_000.wav" -> key = 21 + 2*N
    if reldir.endswith('Keys/Upright Piano') and re.match(r'^\d{3}$', toks[-1]):
        note = ('key', 21 + 2 * int(toks[-1]))
        toks = toks[:-1]
    n = len(toks)
    for i, t in enumerate(toks):
        tl = t.lower()
        m = NOTE_RE.match(t)
        if note is None and m and (t[0].isupper() or n <= 4):
            note = (m.group(1).upper(), m.group(2), m.group(3))
            continue
        m = VEL_RE.match(t)
        if m and vel is None:
            vel = int(m.group(1))
            vel_label = t
            continue
        m = RR_RE.match(t)
        if m and rr is None:
            rr = int(m.group(1))
            continue
        m = DYN_RE.match(t)
        if m and vel is None and (i > 0):
            vel = DYN[m.group(1)]
            vel_label = m.group(1)
            if m.group(2) and rr is None:
                rr = int(m.group(2))
            continue
        if tl in MIC_TOKENS:
            mic = t
            continue
        if re.match(r'^\d+$', t) and i == n - 1 and rr is None and i > 0:
            rr = int(t)
            continue
        if re.match(r'^\d+$', t) and i > 0 and rr is None and all(
                (tt.lower() in MIC_TOKENS) for tt in toks[i + 1:]):
            rr = int(t)
            continue
        stem.append(t)
    return '_'.join(stem), note, vel, vel_label, rr, mic


# ----------------------------------------------------------------------------- analysis

def kweight(x, sr):
    """BS.1770 K-weighting (pre-filter shelf + RLB high-pass), any sample rate."""
    G, fc, Q = 4.0, 1500.0, 1 / math.sqrt(2)
    A = 10 ** (G / 40)
    w0 = 2 * math.pi * fc / sr
    al = math.sin(w0) / (2 * Q)
    c = math.cos(w0)
    b = [A * ((A + 1) + (A - 1) * c + 2 * math.sqrt(A) * al), -2 * A * ((A - 1) + (A + 1) * c),
         A * ((A + 1) + (A - 1) * c - 2 * math.sqrt(A) * al)]
    a = [(A + 1) - (A - 1) * c + 2 * math.sqrt(A) * al, 2 * ((A - 1) - (A + 1) * c),
         (A + 1) - (A - 1) * c - 2 * math.sqrt(A) * al]
    y = lfilter(b, a, x, axis=0)
    fc, Q = 38.0, 0.5
    w0 = 2 * math.pi * fc / sr
    al = math.sin(w0) / (2 * Q)
    c = math.cos(w0)
    b = [(1 + c) / 2, -(1 + c), (1 + c) / 2]
    a = [1 + al, -2 * c, 1 - al]
    return lfilter(b, a, y, axis=0)


def momentary_max(x, sr):
    """Max 400 ms K-weighted loudness (LUFS-like, channels summed)."""
    y = kweight(x, sr)
    p = np.sum(y.astype(np.float64) ** 2, axis=1)
    w = int(0.4 * sr)
    if len(p) <= w:
        ms = p.mean() * len(p) / w  # short sounds: energy over a 400 ms window
        return -0.691 + 10 * math.log10(ms + 1e-20)
    cs = np.concatenate([[0.0], np.cumsum(p)])
    hop = int(0.025 * sr)
    idx = np.arange(0, len(p) - w + 1, hop)
    ms = (cs[idx + w] - cs[idx]) / w
    return -0.691 + 10 * math.log10(ms.max() + 1e-20)


def spectrum_db(x, sr, t0, t1):
    a, b = int(t0 * sr), int(t1 * sr)
    seg = x[a:b]
    if len(seg) < int(0.05 * sr):
        return None, None
    seg = (seg - seg.mean()) * np.hanning(len(seg))
    n = 1 << int(math.ceil(math.log2(max(len(seg) * 4, 32768))))
    S = 20 * np.log10(np.abs(np.fft.rfft(seg, n)) + 1e-9)
    fr = np.fft.rfftfreq(n, 1 / sr)
    m = (fr > 25) & (fr < 8000)
    fl = np.median(S[m])
    return fr, np.clip(S - fl, 0, None)


def _val(fr, S, f, cents=35):
    lo, hi = f * 2 ** (-cents / 1200), f * 2 ** (cents / 1200)
    if hi >= fr[-1]:
        return 0.0
    i0, i1 = np.searchsorted(fr, [lo, hi])
    return float(S[i0:i1 + 1].max()) if i1 > i0 else 0.0


def harmonic_score(fr, S, f, H=8):
    vals = [_val(fr, S, h * f) for h in range(1, H + 1) if h * f < 8000]
    return (sum(vals) / len(vals)) if vals else 0.0, vals


def detect_harmonic(x, sr, named_midi, onset, end):
    """Return (best_midi_float, octave_offset, confidence) for a sample named `named_midi`."""
    dur = end - onset
    if dur < 0.08:
        return None
    t0 = onset + min(0.06, 0.2 * dur)
    t1 = min(end, t0 + 1.0)
    fr, S = spectrum_db(x, sr, t0, t1)
    if fr is None:
        return None
    best = None
    for off in (-24, -12, 0, 12, 24):
        m = named_midi + off
        f = 440 * 2 ** ((m - 69) / 12)
        if f < 20 or f > 5000:
            continue
        sc, vals = harmonic_score(fr, S, f)
        if best is None or sc > best[0]:
            best = (sc, off, f)
    if best is None or best[0] < 3:
        return None
    sc, off, f = best
    # octave-down check: are the odd harmonics of f/2 present?
    while off - 12 >= -24:
        fl = f / 2
        if fl < 20:
            break
        odd = [_val(fr, S, h * fl) for h in (1, 3, 5, 7) if h * fl < 8000]
        even = [_val(fr, S, h * fl) for h in (2, 4, 6, 8) if h * fl < 8000]
        if odd and even and np.mean(odd) >= 0.6 * np.mean(even) and np.mean(odd) > 6:
            off -= 12
            f = fl
        else:
            break
    # fine tuning +-60 cents
    cents = np.arange(-60, 61, 2)
    scores = []
    for c in cents:
        ff = f * 2 ** (c / 1200)
        vals = [_val(fr, S, h * ff, cents=4) / math.sqrt(h) for h in range(1, 7) if h * ff < 8000]
        scores.append(sum(vals))
    c = float(cents[int(np.argmax(scores))])
    return named_midi + off + c / 100.0, off, sc


def detect_timpani(x, sr, onset, end):
    """Principal-mode pitch of a timpano (template on the (1,1),(2,1),(3,1),(4,1) modes)."""
    t0 = onset + 0.35
    t1 = min(end, onset + 1.6)
    if t1 - t0 < 0.3:
        t0, t1 = onset + 0.08, min(end, onset + 0.9)
    fr, S = spectrum_db(x, sr, t0, t1)
    if fr is None:
        return None
    cands = 55 * 2 ** (np.arange(0, 2900, 5) / 1200)
    sc = [_val(fr, S, f, 25) + 0.7 * _val(fr, S, 1.5 * f, 25) + 0.5 * _val(fr, S, 2 * f, 25)
          + 0.3 * _val(fr, S, 2.5 * f, 25) for f in cands]
    i = int(np.argmax(sc))
    return 69 + 12 * math.log2(cands[i] / 440), float(sc[i])


def analyze(job):
    path, info = job
    out = dict(info)
    try:
        x, sr = sf.read(path, always_2d=True, dtype='float32')
    except Exception as e:  # unreadable file
        out['error'] = str(e)
        return out
    n, ch = x.shape
    out.update(sr=sr, ch=ch, frames=n, len_s=round(n / sr, 4))
    a = np.abs(x).max(axis=1)
    pk = float(a.max()) if n else 0.0
    out['peak_db'] = round(20 * math.log10(pk + 1e-12), 2)
    out['rms_db'] = round(10 * math.log10(float(np.mean(x.astype(np.float64) ** 2)) + 1e-20), 2)
    if n == 0 or pk <= 0:
        out['error'] = 'silent'
        return out
    # 5 ms RMS envelope
    w = max(1, int(0.005 * sr))
    e = np.sqrt(np.convolve(a.astype(np.float64) ** 2, np.ones(w) / w, mode='same'))
    emax = e.max()
    on = int(np.argmax(e > emax * 10 ** (-35 / 20)))
    on = max(0, on - int(0.003 * sr))
    above = np.nonzero(e > emax * 10 ** (-60 / 20))[0]
    end = int(above[-1]) if len(above) else n
    out['onset_s'] = round(on / sr, 4)
    out['peak_t_s'] = round(int(np.argmax(e)) / sr, 4)
    out['end_s'] = round(end / sr, 4)
    act = e > emax * 10 ** (-30 / 20)
    out['rms_active_db'] = round(10 * math.log10(float(np.mean(e[act] ** 2)) + 1e-20), 2)
    out['loud_db'] = round(momentary_max(x, sr), 2)
    mono = x.mean(axis=1).astype(np.float64)
    if info.get('_detect') == 'harmonic' and info.get('midi_named') is not None:
        r = detect_harmonic(mono, sr, info['midi_named'], on / sr, end / sr)
        if r:
            out['f0_midi'] = round(r[0], 2)
            out['f0_oct_off'] = r[1]
            out['f0_score'] = round(r[2], 1)
    elif info.get('_detect') == 'timpani':
        r = detect_timpani(mono, sr, on / sr, end / sr)
        if r:
            out['f0_midi'] = round(r[0], 2)
            out['f0_score'] = round(r[1], 1)
    return out


# ----------------------------------------------------------------------------- grouping

def walk():
    files = []
    for lib, root in LIBS.items():
        for d, ds, fs in os.walk(root):
            ds.sort()
            for f in sorted(fs):
                if f.lower().endswith('.wav'):
                    files.append((lib, root, os.path.relpath(d, root), f))
    return files


def build_jobs(files):
    # first pass: parse
    parsed = []
    by_dir = defaultdict(list)
    for lib, root, reldir, f in files:
        stem, note, vel, vel_label, rr, mic = parse_name(f, reldir)
        rec = dict(lib=lib, reldir=reldir, file=f, path=os.path.join(root, reldir, f), stem=stem,
                   note=note, vel=vel, vel_label=vel_label, rr=rr, mic=mic)
        parsed.append(rec)
        by_dir[(lib, reldir)].append(rec)
    jobs = []
    for (lib, reldir), recs in by_dir.items():
        noted = [r for r in recs if r['note'] is not None]
        merge_noted = len(noted) >= 0.8 * len(recs) and len(noted) >= 2
        common = Counter(r['stem'] for r in noted).most_common(1)[0][0] if noted else ''
        for r in recs:
            stem = r['stem']
            drum = None
            m = TIMP_RE.match(stem.split('_')[0]) if stem else None
            timp = m is not None
            if timp:
                rest = stem.split('_')[1:]
                drum = m.group(2) + m.group(3)
                stem = '_'.join(['Timpani'] + [t.capitalize() for t in rest])
            if r['note'] is not None and merge_noted:
                stem = common
            gkey = f"{lib}/{reldir}" + (f"::{stem}" if not (r['note'] is not None and merge_noted) else '')
            gkey = gkey.replace('/.', '')
            info = dict(lib=lib, group=gkey, stem=stem or os.path.basename(reldir), file=r['file'],
                        vel_raw=r['vel'], vel_label=r['vel_label'], rr=r['rr'], mic=r['mic'])
            if drum:
                info['drum'] = drum
            note = r['note']
            if note is not None:
                if note[0] == 'key':
                    info['note_named'] = midi_name(note[1])
                    info['midi_named'] = note[1]
                else:
                    info['note_named'] = note[0] + note[1] + note[2]
                    info['midi_named'] = note_to_midi(*note)
                info['_detect'] = 'harmonic'
            elif timp and 'roll' not in stem.lower():
                info['_detect'] = 'timpani'
            elif timp:
                info['_detect'] = 'timpani'
            jobs.append((r['path'], info))
    return jobs


def finalize(results):
    groups = {}
    by_group = defaultdict(list)
    for r in results:
        by_group[r['group']].append(r)
    for gkey, recs in sorted(by_group.items()):
        recs.sort(key=lambda r: r['file'])
        lib = recs[0]['lib']
        rel = gkey.split('/', 1)[1].split('::')[0]
        g = dict(library=lib, dir=rel, stem=recs[0]['stem'], family=family_of(rel))
        named = [r for r in recs if r.get('midi_named') is not None]
        detected_only = [r for r in recs if r.get('_detect') == 'timpani']
        if named:
            offs = Counter(r['f0_oct_off'] for r in named if 'f0_oct_off' in r and r.get('f0_score', 0) >= 6)
            off = offs.most_common(1)[0][0] if offs else 0
            agree = (offs[off] / max(1, sum(offs.values()))) if offs else 0.0
            g.update(pitched=True, pitch_source='filename', octave_offset=off,
                     octave_check=f"{offs[off] if offs else 0}/{sum(offs.values())} detected samples agree")
            devs = []
            for r in named:
                r['midi'] = r['midi_named'] + off
                r['note'] = midi_name(r['midi'])
                if 'f0_midi' in r and r.get('f0_oct_off') == off:
                    devs.append(r['f0_midi'] - r['midi'])
            if devs:
                g['tuning_cents_median'] = round(100 * float(np.median(devs)), 1)
            g['octave_agreement'] = round(agree, 2)
        elif detected_only:
            # timpani: consensus pitch per (drum tuning), soft layers first
            by_drum = defaultdict(list)
            for r in recs:
                by_drum[r.get('drum', '?')].append(r)
            for d, rs in by_drum.items():
                vals = [r['f0_midi'] for r in rs if 'f0_midi' in r]
                if not vals:
                    continue
                vels = sorted(set(r['vel_raw'] or 0 for r in rs))
                soft = [r['f0_midi'] for r in rs if 'f0_midi' in r and (r['vel_raw'] or 0) in vels[:2]] or vals
                med = float(np.median(soft))
                spread = float(np.median(np.abs(np.array(vals) - med)))
                agree = sum(abs(v - med) < 0.6 for v in vals) / len(vals)
                for r in rs:
                    r['midi_float'] = round(med, 2)
                    r['midi'] = int(round(med))
                    r['note'] = midi_name(med)
                    r['pitch_confidence'] = round(agree, 2)
            g.update(pitched=True, pitch_source='detected (timpani principal mode)')
        else:
            g.update(pitched=False, pitch_source='none', notional_key=60)
            for r in recs:
                r['midi'] = 60
                r['note'] = None
        # velocity layer index (0 = softest)
        vals = sorted(set(r['vel_raw'] for r in recs if r['vel_raw'] is not None))
        for r in recs:
            r['vel_layer'] = vals.index(r['vel_raw']) if r['vel_raw'] is not None else 0
        labels = {}
        for r in recs:
            labels[r['vel_layer']] = r['vel_label'] or 'single'
        g['n_vel_layers'] = max(1, len(vals))
        g['vel_labels'] = [labels[k] for k in sorted(labels)]
        # round robin index: 1..n within (midi/drum, layer)
        slots = defaultdict(list)
        for r in recs:
            slots[(r.get('midi'), r.get('drum'), r['vel_layer'])].append(r)
        for s, rs in slots.items():
            rs.sort(key=lambda r: ((r['rr'] if r['rr'] is not None else 0), r['file']))
            for i, r in enumerate(rs):
                r['rr_index'] = i + 1
        g['max_rr'] = max(len(v) for v in slots.values())
        mids = [r['midi'] for r in recs if r.get('midi') is not None]
        if g['pitched'] and mids:
            g['range'] = [midi_name(min(mids)), midi_name(max(mids))]
            g['range_midi'] = [int(min(mids)), int(max(mids))]
            g['n_notes'] = len(set(mids))
        g['n_samples'] = len(recs)
        g['len_s_median'] = round(float(np.median([r.get('len_s', 0) for r in recs])), 2)
        g['loud_db_median'] = round(float(np.median([r.get('loud_db', -99) for r in recs])), 1)
        samples = []
        for r in recs:
            s = {k: r[k] for k in ('note', 'midi', 'vel_layer', 'vel_label', 'rr_index', 'path', 'sr', 'ch', 'len_s',
                                   'peak_db', 'rms_db', 'rms_active_db', 'loud_db', 'onset_s', 'peak_t_s', 'end_s')
                 if k in r}
            s['rr'] = s.pop('rr_index')
            for k in ('note_named', 'midi_named', 'f0_midi', 'midi_float', 'pitch_confidence', 'drum', 'mic', 'error'):
                if k in r:
                    s[k] = r[k]
            samples.append(s)
        g['samples'] = samples
        groups[gkey] = g
    return groups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--filter', default='')
    ap.add_argument('--out', default=HERE)
    a = ap.parse_args()
    t = time.time()
    files = walk()
    jobs = build_jobs(files)
    if a.filter:
        jobs = [j for j in jobs if re.search(a.filter, j[0])]
    if a.limit:
        jobs = jobs[:a.limit]
    print(f"{len(jobs)} wav files", flush=True)
    results = []
    with Pool(a.jobs) as p:
        for i, r in enumerate(p.imap_unordered(analyze, jobs, chunksize=8)):
            results.append(r)
            if i % 500 == 0:
                print(f"  {i}/{len(jobs)}  {time.time() - t:.0f}s", flush=True)
    groups = finalize(results)
    cat = dict(version=1, built=time.strftime('%Y-%m-%d %H:%M:%S'), libraries=LIBS,
               notes=('midi = scientific MIDI (C4=60) after the per-folder octave check; note_named/midi_named are '
                      'the raw filename values. Unpitched groups use notional key 60. vel_layer 0 = softest. '
                      'loud_db = max 400 ms K-weighted loudness (LUFS-like). onset_s/end_s bound the audible part.'),
               n_groups=len(groups), n_samples=len(results), groups=groups)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'catalog.json'), 'w') as f:
        json.dump(cat, f, indent=1)
    print(f"wrote {len(groups)} groups / {len(results)} samples in {time.time() - t:.0f}s")


if __name__ == '__main__':
    main()
