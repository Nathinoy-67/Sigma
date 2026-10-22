#!/usr/bin/env python3
"""Render demo.wav: ~20 s D-minor trailer passage that exercises the sampler.

  bars 1-2  low strings + spiccato ostinato (celli/violas), soft timpani and bass drum
  bars 3-4  violins join the ostinato, 4 horns state the theme (legato), drums on 1 and 3
  bars 5-6  i-VI-iv-V with low brass, full trailer drum ensemble
  bars 7-8  build: tremolo strings crescendo, timpani + snare rolls, cymbal swell & reversed
            cymbal landing on the downbeat of bar 9
  bar 9     tutti D minor hit (bass drums pitched down, giant drum, gong, crash), ring-out

Prints timing figures.  Usage: python3 demo.py [out.wav]
"""
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sampler import SR, Humanize, Note, Sampler, fx_hall, fx_limit, note_to_midi  # noqa: E402

BPM = 120
BEAT = 60 / BPM
BAR = 4 * BEAT
S16 = BEAT / 4
HIT = 8 * BAR  # 16.0 s


def m(x):
    return note_to_midi(x)


# chord per bar: (root name for low strings, triad pitch classes for the ostinato)
CHORDS = ['Dm', 'Dm', 'Dm', 'Bb', 'Gm', 'A', 'Bb', 'A']
ROOT = {'Dm': 'D', 'Bb': 'Bb', 'Gm': 'G', 'A': 'A'}
TRIAD = {'Dm': (0, 3, 7), 'Bb': (0, 4, 7), 'Gm': (0, 3, 7), 'A': (0, 4, 7)}


def root(ch, octave):
    return m(f'{ROOT[ch]}{octave}')


def score():
    ev = []
    # ------------------------------------------------------------ spiccato ostinati
    cell = [0, 0, 2, 0, 1, 0, 2, 0]  # triad degrees: R R 5 R 3 R 5 R
    for b, ch in enumerate(CHORDS):
        r3 = root(ch, 3)
        if r3 > m('F3'):
            r3 -= 12
        tri = TRIAD[ch]
        for i in range(16):
            t = b * BAR + i * S16
            acc = 112 if i % 4 == 0 else (92 if i % 2 == 0 else 78)
            deg = cell[i % 8]
            p = r3 + tri[deg]
            ev.append(Note('strings.celli.spic', t, S16, p, acc - (30 if b < 2 else 0)))
            ev.append(Note('strings.violas.spic', t, S16, p + 12, acc - (38 if b < 2 else 6)))
            if b >= 2:  # violins join in bar 3, pattern inverted upwards
                vp = r3 + 24 + tri[[2, 0, 1, 0, 2, 1, 2, 0][i % 8]]
                ev.append(Note('strings.violins.spic', t, S16, vp, acc - (10 if b < 4 else 0)))
            if b >= 4 and i % 2 == 0:  # basses double the roots in 8ths from bar 5
                ev.append(Note('strings.basses.spic', t, S16, root(ch, 2), acc - 8))
    # ------------------------------------------------------------ sustained low strings
    for b, ch in enumerate(CHORDS[:6]):
        t = b * BAR
        v0, v1 = (45, 70) if b < 2 else (70, 95)
        ev.append(Note('strings.basses.sus', t, BAR, root(ch, 2), v0, dyn=[(0, v0), (BAR, v1)]))
        if b < 4:
            ev.append(Note('strings.celli.sus', t, BAR, root(ch, 3) if b < 2 else root(ch, 2) + 12, v0 - 5,
                           dyn=[(0, v0 - 5), (BAR, v1 - 5)], attack=0.25 if b == 0 else None))
    # bars 7-8: tremolo strings crescendo into the hit
    for p in ('D3', 'A3'):
        ev.append(Note('strings.celli.trem', 6 * BAR, 2 * BAR, p, 50, dyn=[(0, 45), (2 * BAR, 125)]))
    for p in ('F4', 'A4'):
        ev.append(Note('strings.violas.trem', 6 * BAR, 2 * BAR, p, 50, dyn=[(0, 40), (2 * BAR, 120)]))
    ev.append(Note('strings.basses.trem', 6 * BAR, 2 * BAR, 'A1', 50, dyn=[(0, 50), (2 * BAR, 125)]))
    # ------------------------------------------------------------ horn theme (legato, a4)
    # 4 horns in their strong register (the VSCO horn sustains are dense up to C4 sounding),
    # doubled an octave higher by 3 trumpets from bar 5 -- classic trailer brass voicing.
    theme = [('D3', 2), ('A3', 2),                 # bar 3  Dm
             ('Bb3', 2), ('A3', 1), ('G3', 1),     # bar 4  Bb
             ('G3', 3), ('F3', 0.5), ('G3', 0.5),  # bar 5  Gm
             ('A3', 4),                            # bar 6  A
             ('D4', 2), ('C4', 1), ('Bb3', 1),     # bar 7  Bb
             ('A3', 2), ('C#4', 1), ('E4', 1)]     # bar 8  A  -> D4 on the hit
    t = 2 * BAR
    for p, beats in theme:
        d = beats * BEAT
        v = 92 if t < 4 * BAR else (108 if t < 6 * BAR else 118)
        ev.append(Note('brass.horns.sus', t, d, p, v))
        if t >= 4 * BAR:
            ev.append(Note('brass.trumpets.sus', t, d, m(p) + 12, v - 22, gain_db=-3))
        t += d
    # ------------------------------------------------------------ low brass from bar 5
    lowb = {'Gm': ('G2', 'D3'), 'A': ('A2', 'E3'), 'Bb': ('Bb2', 'F3')}
    for b in range(4, 8):
        ch = CHORDS[b]
        for p in lowb[ch]:
            ev.append(Note('brass.trombones.sus', b * BAR, BAR - 0.05, p, 80, dyn=[(0, 70), (BAR, 105)],
                           legato=False))
        ev.append(Note('brass.tuba.sus', b * BAR, BAR - 0.05, root(ch, 1) if root(ch, 1) >= m('F1') else root(ch, 2),
                       85, dyn=[(0, 75), (BAR, 110)], legato=False))
    # ------------------------------------------------------------ drums
    for b in range(8):
        t0 = b * BAR
        ch = CHORDS[b]
        tp = {'Dm': 'D2', 'Bb': 'F2', 'Gm': 'G2', 'A': 'A2'}[ch]
        if b < 2:
            ev.append(Note('perc.timpani', t0, 1, 'D2', 72))
            ev.append(Note('perc.bass_drum', t0, 1, 57, 68))
        elif b < 4:
            ev += [Note('perc.timpani', t0, 1, tp, 105), Note('perc.timpani', t0 + 2 * BEAT, 1, 'A2', 92),
                   Note('perc.bass_drum', t0, 1, 56, 105), Note('perc.bass_drum', t0 + 2 * BEAT, 1, 56, 92),
                   Note('perc.toms.low', t0 + 1.5 * BEAT, 1, None, 90), Note('perc.toms.low', t0 + 3.5 * BEAT, 1, None, 96)]
            for i in range(8):
                ev.append(Note('perc.frame_drum', t0 + i * BEAT / 2, 1, None, 70 if i % 2 else 85))
        elif b < 6:
            for i in (0, 4, 10, 12):
                ev.append(Note('perc.giant_drum', t0 + i * S16, 1, 55, 120 if i in (0, 12) else 100))
            for i in (0, 8):
                ev.append(Note('perc.bass_drum', t0 + i * S16, 1, 55, 122))
            for i in (2, 6, 10, 14, 15):
                ev.append(Note('perc.toms.low', t0 + i * S16, 1, None, 108 if i != 15 else 92))
            for i in (4, 12):
                ev.append(Note('perc.toms.high', t0 + i * S16, 1, None, 104))
            for i in range(16):
                ev.append(Note('perc.tenor_drum.low', t0 + i * S16, 1, None, 92 if i % 4 == 0 else 52))
            ev += [Note('perc.timpani', t0, 1, tp, 118), Note('perc.timpani', t0 + 2 * BEAT, 1, tp, 105)]
        else:  # bars 7-8: accelerating build
            step = 2 if b == 6 else 1
            for i in range(0, 16, step):
                frac = (b - 6 + i / 16) / 2
                v = int(70 + 55 * frac)
                ev.append(Note('perc.toms.low' if i % 2 == 0 else 'perc.toms.high', t0 + i * S16, 1, None, v))
                if i % 4 == 0:
                    ev.append(Note('perc.giant_drum', t0 + i * S16, 1, 55, v + 5))
            ev.append(Note('perc.bass_drum', t0, 1, 55, 120))
    ev.append(Note('perc.timpani.roll', 6 * BAR, 2 * BAR, 'A2', 40, dyn=[(0, 30), (2 * BAR, 127)]))
    ev.append(Note('perc.snare.roll', 7 * BAR, BAR, None, 40, dyn=[(0, 30), (BAR, 120)], gain_db=-4))
    # ------------------------------------------------------------ risers into the hit
    ev.append(Note('perc.cymbal.swell', HIT - 4.0, 4.0, None, 112))
    ev.append(Note('fx.reverse_cymbal', HIT - 2.0, 2.0, None, 105, gain_db=-3))
    # ------------------------------------------------------------ the hit (bar 9)
    ev += [Note('perc.bass_drum', HIT, 1, 53, 127), Note('perc.bass_drum.vcsl', HIT, 1, 50, 127, gain_db=-2),
           Note('perc.giant_drum', HIT, 1, 52, 127), Note('perc.timpani', HIT, 1, 'D2', 127),
           Note('perc.timpani', HIT + 0.01, 1, 'A2', 118),
           Note('perc.gong', HIT, 1, None, 120), Note('perc.cymbal.crash', HIT, 1, None, 122),
           Note('perc.toms.low', HIT, 1, 55, 120)]
    hold = 3.2
    for inst, ps, v in [('strings.basses.sus', ('D2',), 120), ('strings.celli.sus', ('D2', 'A2', 'D3'), 118),
                        ('strings.violas.sus', ('F4', 'A4'), 112), ('strings.violins.sus', ('D5', 'F5', 'A5'), 112),
                        ('brass.horns.sus', ('D3', 'F3', 'A3', 'D4'), 122), ('brass.trombones.sus', ('D3', 'A3'), 120),
                        ('brass.tuba.sus', ('D2',), 122), ('brass.trumpets.sus', ('D4', 'A4', 'D5'), 100)]:
        for p in ps:
            ev.append(Note(inst, HIT, hold, p, v, dyn=[(0, v), (0.5, v), (hold, max(40, v - 60))], legato=False,
                           release=1.2))
    return ev


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'demo.wav')
    t0 = time.time()
    s = Sampler()
    t_load = time.time() - t0
    ev = score()
    dur = HIT + 4.8
    t1 = time.time()
    stems = s.render(ev, dur, humanize=Humanize(time_ms=5, vel=4, cents=2, seed=11), stems=True)
    t_render = time.time() - t1
    t2 = time.time()
    gains = {'strings': 0.0, 'brass': -1.0, 'perc': -2.0, 'fx': -4.0, 'woods': 0.0, 'keys': 0.0}
    sends = {'strings': 0.32, 'brass': 0.28, 'perc': 0.16, 'fx': 0.3}
    dry = np.zeros((2, int(round(dur * SR))), np.float32)
    wet_in = np.zeros_like(dry)
    for k, v in stems.items():
        g = 10 ** (gains.get(k, 0.0) / 20)
        dry += v * g
        wet_in += v * g * sends.get(k, 0.2)
    mix = dry + fx_hall(wet_in, rt60=2.8, predelay=0.025, wet=1.0, dry=0.0)
    mix *= 10 ** (-1.0 / 20) / max(1e-9, np.percentile(np.abs(mix), 99.95))  # loud but leaves the limiter work
    mix = fx_limit(mix, ceiling_db=-1.0)
    t_mix = time.time() - t2
    Sampler.write(out, mix)
    n_notes = len(ev)
    print(f'events: {n_notes}  instruments: {len(set(e.inst for e in ev))}  duration: {dur:.1f}s')
    print(f'catalog load {t_load:.2f}s | render {t_render:.2f}s ({s.stats["resamples"]:.0f} resampled buffers, '
          f'{s.stats["cache_hits"]:.0f} cache hits, {s.stats["load_s"]:.2f}s decoding+resampling) | mix/reverb/limit '
          f'{t_mix:.2f}s')
    print('peak dBFS %.2f' % (20 * np.log10(np.abs(mix).max())))
    if s.warnings:
        print('warnings:', *sorted(set(s.warnings)), sep='\n  ')
    print('wrote', out)


if __name__ == '__main__':
    main()
