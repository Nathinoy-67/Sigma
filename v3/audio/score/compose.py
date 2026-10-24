#!/usr/bin/env python3
"""compose.py -- 'PATIENCE', the 60 s orchestral/hybrid score of ONE YEAR. ONE SECOND.

96 BPM 4/4, 24 bars (1 beat = 15 frames @ 24 fps, 1 bar = 60 frames), D minor -> D major at
bar 19.  Leitmotif PATIENCE D-A-Bb-A (-> D-A-B-A).  Follows the bar map and sound-design
notes of v3/TREATMENT.md (## music, ## sound_design).

Every orchestral / percussion part is played from real recordings (VSCO-2-CE, VCSL) by
v3/audio/sampler; only sub hits, risers, reverse swells, the heartbeat sine and the foley are
synthesized (synth.py).  Every structural hit time is computed from its frame number / 24
and rendered without humanisation; everything else is humanised (+-8 ms, velocity, cents).

Outputs (v3/audio/score/):
  stem_orchestra.wav, stem_percussion.wav, stem_synth_fx.wav, stem_foley.wav  (48 kHz / 24-bit)
  score_mix.wav   premix without voice (= sum of the stems; ~-16 LUFS integrated, <= -1 dBTP)
  patience.mid    the score as MIDI (mido, PPQ 480, 96 BPM; synth/foley cues as markers)
  render_log.json render + mix facts (gains, compressor, limiter, cues)

    nice -n 10 python3 compose.py [--fast]      (--fast: no second string/horn pass)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import replace

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'sampler'))
sys.path.insert(0, HERE)
from sampler import INSTRUMENTS, SR, Humanize, Note, Sampler, note_to_midi  # noqa: E402
import audio_tools as A  # noqa: E402
import mixer as X  # noqa: E402
import synth as SY  # noqa: E402

FPS, BPM = 24, 96
BEAT = 60.0 / BPM            # 0.625 s = 15 frames
BAR = 4 * BEAT               # 2.5 s = 60 frames
DUR = 60.0
N = int(DUR * SR)
CUT_DEAD = 660               # orchestra + fuse stop dead
SIL_A, SIL_B = 1005, 1020    # total digital silence [f1005, f1020)


def T(frame):
    return frame / FPS


def M(p):
    return note_to_midi(p) if isinstance(p, str) else p


# --------------------------------------------------------------------------- instruments
VN, VNS, VNT, VNP = 'strings.violins.spic', 'strings.violins.sus', 'strings.violins.trem', 'strings.violins.pizz'
VA, VAS, VAT, VAP = 'strings.violas.spic', 'strings.violas.sus', 'strings.violas.trem', 'strings.violas.pizz'
VC, VCS, VCT, VCP = 'strings.celli.spic', 'strings.celli.sus', 'strings.celli.trem', 'strings.celli.pizz'
CB, CBS, CBN, CBP = 'strings.basses.spic', 'strings.basses.sus', 'strings.basses.susnv', 'strings.basses.pizz'
VSOLO, HARP = 'strings.violin_solo.sus', 'strings.harp'
HN, HN1 = 'brass.horns.sus', 'brass.horn.sus'
TPT = 'brass.trumpet.sus'
TBS, TB1 = 'brass.trombones.sus', 'brass.trombone.sus'
TU, TUS = 'brass.tuba.sus', 'brass.tuba.stac'
TBX, HNX, TPX = 'brass.trombones.stac', 'brass.horns.stac', 'brass.trumpet.stac'
BN, BNS = 'woods.bassoon.sus', 'woods.bassoon.stac'
PNO, ORG, PED = 'keys.piano', 'keys.organ', 'keys.organ.pedal'
TIMP = 'perc.timpani'
BD, BDB, BDV, TOM = 'perc.bass_drum', 'perc.bass_drum.b', 'perc.bass_drum.vcsl', 'perc.toms.low'
FD = 'perc.frame_drum'
SN, SNR = 'perc.snare.rope', 'perc.snare.roll'
CR, CR2, SUS, SWELL = 'perc.cymbal.crash', 'perc.cymbal.crash2', 'perc.cymbal.sus', 'perc.cymbal.swell'
GONG, BELL, CLV = 'perc.gong.c', 'perc.tubular_bells', 'perc.claves'
RCYM, RGONG = 'fx.reverse_cymbal', 'fx.reverse_gong'

# per-instrument trims (dB) on top of the sampler's loudness normalisation (balance of a real
# orchestra: sections > solos, brass above strings at f, percussion weight for the hits)
GAIN = {
    VN: 0.0, VNS: -1.0, VNT: -1.0, VNP: -2.0, VA: -1.0, VAS: -1.5, VAT: -2.0, VAP: -2.0, VC: 0.0, VCS: -0.5, VCT: -1.0, VCP: -1.0,
    CB: 1.0, CBS: 0.0, CBN: 0.5, CBP: 0.0, VSOLO: -3.0, HARP: -1.0,
    HN: 2.0, HN1: 0.0, TPT: 0.0, TBS: 1.0, TB1: -1.0, TU: 1.0, TUS: 0.0, BN: -3.0, BNS: -3.0,
    TBX: 1.0, HNX: 1.0, TPX: -1.0,
    PNO: -1.0, ORG: -4.0, PED: -1.0,
    TIMP: 4.0, BD: 8.0, BDB: 6.0, BDV: 7.0, TOM: 3.0, FD: 2.0, SN: -3.0, SNR: -5.0,
    CR: 0.0, CR2: 0.0, SUS: -3.0, SWELL: -3.0, GONG: 1.0, BELL: -3.0, CLV: -9.0, RCYM: -2.0, RGONG: -2.0,
}

# sub-bus routing -> delivery stem
STEM_OF = {'strings': 'orchestra', 'brass': 'orchestra', 'woods': 'orchestra', 'keys': 'orchestra',
           'piano': 'orchestra', 'harm': 'orchestra', 'perc': 'percussion', 'bells': 'percussion',
           'fuse': 'percussion', 'fx': 'synth_fx'}


class Score:
    def __init__(self):
        self.ev = []      # dict(note, locked, double)
        self.marks = []   # (t, text) MIDI markers

    def n(self, inst, t, dur, pitch, vel, locked=False, double=None, **kw):
        kw['gain_db'] = kw.get('gain_db', 0.0) + GAIN.get(inst, 0.0)
        note = Note(inst, float(t), float(dur), M(pitch), float(max(1, min(127, vel))), **kw)
        self.ev.append(dict(note=note, locked=locked, double=double))
        return note

    def mark(self, t, text):
        self.marks.append((t, text))


def is_section_string(inst):
    return inst.startswith('strings.') and not (inst.startswith('strings.violin_solo') or inst == HARP or
                                                inst.startswith('strings.bass_solo'))


# --------------------------------------------------------------------------- helpers
def ostinato(S, inst, t0, step, pitches, vel, acc, cresc=(0.0, 0.0), n=None, gain_db=0.0, double='strings', **kw):
    n = n or len(pitches)
    for i in range(n):
        v = vel + acc[i % len(acc)] + cresc[0] + (cresc[1] - cresc[0]) * i / max(1, n - 1)
        S.n(inst, t0 + i * step, step * 0.95, pitches[i % len(pitches)], v, double=double, gain_db=gain_db, **kw)


def pat(root, third, fifth):
    """D D A D F D A D  ->  R R 5 R 3 R 5 R."""
    r, t3, f5 = M(root), M(third), M(fifth)
    return [r, r, f5, r, t3, r, f5, r]


def timp_roll(S, t0, t1, pitch, v0, v1, rate=13.5, gain_db=0.0):
    """Timpani roll from single strokes of the clean-head drums (alternating hands)."""
    n = max(2, int((t1 - t0) * rate))
    for i in range(n):
        u = i / (n - 1)
        v = v0 + (v1 - v0) * u ** 1.6 - (3 if i % 2 else 0)
        S.n(TIMP, t0 + i * (t1 - t0) / n, 0.4, pitch, v, gain_db=gain_db)


def harp_gliss(S, t0, dur, lo, hi, scale, v0, v1, gain_db=0.0):
    ps = [p for p in range(int(M(lo)), int(M(hi)) + 1) if p % 12 in scale]
    for i, p in enumerate(ps):
        u = i / max(1, len(ps) - 1)
        S.n(HARP, t0 + dur * u ** 0.9, 1.5, p, v0 + (v1 - v0) * u, gain_db=gain_db)


def stabs(S, t, layers, vel):
    """Staccato brass layered on the attack of a sustained brass hit (the recorded stac attack is
    the 'bite' a sustain sample, which swells in over ~300 ms, does not have)."""
    for inst, ps in layers:
        for p in ps:
            S.n(inst, t, 0.4, p, vel, True, double='horns' if inst == HNX else None)


def sfz(v, hold=0.55, end=0.3, dur=4.0):
    return [(0.0, v), (0.16, v * 0.82), (0.9, v * hold), (dur, v * end)]


DMIN = {2, 4, 5, 7, 9, 10, 0}          # D natural minor pitch classes
DMAJ = {2, 4, 6, 7, 9, 11, 1}


# --------------------------------------------------------------------------- the score
def compose():
    S = Score()
    L = True  # locked (frame-accurate, not humanised)

    # ===================================================== BAR 1  f0  OVERTURE HIT
    t = T(0)
    S.mark(t, 'BAR 1 OVERTURE HIT f0')
    hold = lambda v: [(0.0, v), (0.45, v * 0.94), (1.3, v * 0.6), (4.0, v * 0.3)]
    S.n(TU, t, 4.0, 'D2', 127, L, dyn=hold(127), release=0.9)
    S.n(TBS, t, 4.0, 'D2', 127, L, dyn=hold(127), release=0.9)
    S.n(TBS, t, 4.0, 'D3', 120, L, dyn=hold(120), release=0.9)
    S.n(BN, t, 4.0, 'D2', 112, L, dyn=hold(112), release=0.8)
    S.n(HN, t, 3.0, 'D3', 108, L, double='horns', dyn=hold(108), release=0.7)
    S.n(BDB, t, 1, 57, 112, L)
    stabs(S, t, [(TUS, ('D2',)), (TBX, ('D2', 'D3')), (HNX, ('D3',)), (BNS, ('D2',))], 127)
    S.n(CBN, t, 4.0, 'D1', 110, L, dyn=sfz(110), release=1.0, double='strings')
    S.n(TIMP, t, 1, 'D2', 122, L)
    S.n(BDV, t, 1, 57, 120, L)
    S.n(BD, t, 1, 55, 118, L)
    S.n(BELL, t, 1, 'D4', 96, L, bus='bells')
    # cello + bass D pedal pp under the decay (to the end of bar 3)
    S.n(VCS, T(30), T(180) - T(30), 'D2', 30, attack=1.4, dyn=[(0, 26), (3.0, 34), (6.0, 40)], double='strings')
    S.n(CBN, T(36), T(180) - T(36), 'D1', 28, attack=1.6, dyn=[(0, 24), (3.0, 32), (5.5, 36)], double='strings')

    # ===================================================== BAR 2  f60
    S.mark(T(60), 'BAR 2 solo horn PATIENCE')
    S.n(PNO, T(60), 3.5, 'D3', 40, L, bus='piano')
    for fr, p, v, d in ((60, 'D3', 60, 1.25), (90, 'A3', 64, 1.25), (120, 'Bb3', 68, 1.25), (150, 'A3', 60, 1.75)):
        S.n(HN1, T(fr), d, p, v, dyn=[(0, v - 9), (0.35, v), (d, v - 6)])

    # ===================================================== BAR 3  f120  ostinato starts
    S.mark(T(120), 'BAR 3 spiccato ostinato, harp harmonics')
    S.n(HARP, T(121), 2.5, 'A5', 44, bus='harm')
    S.n(HARP, T(128.5), 2.5, 'D6', 40, bus='harm')
    S.n(HARP, T(135), 2.0, 'A3', 66, L)                    # f135 cut (balance): harp + pizz pluck
    S.n(VNP, T(135), 1.0, 'A4', 70, L, double='strings')
    acc8 = [12, 0, 4, 0, 8, 0, 4, 0]
    ostinato(S, VC, T(120), BEAT / 2, pat('D3', 'F3', 'A3'), 34, acc8, cresc=(0, 10))
    ostinato(S, VA, T(120), BEAT / 2, pat('D4', 'F4', 'A4'), 30, acc8, cresc=(0, 10))
    S.n(CBP, T(120), 1, 'D2', 60, double='strings')
    S.n(CBP, T(150), 1, 'Bb1', 58, double='strings')

    # ===================================================== BAR 4  f180  jar time-lapse
    S.mark(T(180), 'BAR 4 ostinato in 16ths, harp gliss, day swells')
    S.n(TIMP, T(180), 1, 'D3', 46, L)                       # the balance settles
    acc16 = [12, 0, 4, 0, 8, 0, 4, 0]
    ostinato(S, VC, T(180), BEAT / 4, pat('G2', 'Bb2', 'D3'), 46, acc16, cresc=(0, 6))
    ostinato(S, VA, T(180), BEAT / 4, pat('G3', 'Bb3', 'D4'), 40, acc16, cresc=(0, 6))
    ostinato(S, VC, T(210), BEAT / 4, pat('A2', 'C#3', 'E3'), 52, acc16, cresc=(0, 8))
    ostinato(S, VA, T(210), BEAT / 4, pat('A3', 'C#4', 'E4'), 46, acc16, cresc=(0, 8))
    S.n(CBP, T(180), 1, 'G1', 62, double='strings')
    S.n(CBP, T(210), 1, 'A1', 64, double='strings')
    harp_gliss(S, T(180) + 0.02, 0.62, 'D3', 'A5', DMIN, 46, 68)
    for fr in (195, 210, 225):                             # brushed sus-cymbal swell per 'day'
        S.n(SWELL, T(fr) - 0.6, 0.6, None, 52, L, gain_db=-5.0)
    S.n(PNO, T(225), 3.5, 'D1', 64, L, bus='piano')        # f225 cut (card): low piano octave D
    S.n(PNO, T(225), 3.5, 'D2', 58, L, bus='piano')

    # ===================================================== BAR 5  f240  GEHEIM
    S.mark(T(240), 'BAR 5 GEHEIM trombones pp, timp roll, reverse cymbal')
    # Gm -> A sus4 -> A: outer voices hold, the middle voice resolves D -> C#
    for v_id, notes in (('a', (('G2', 240, 1.25), ('A2', 270, 1.4))), ('b', (('Bb2', 240, 1.25), ('D3', 270, 0.625),
                                                                          ('C#3', 285, 0.775))),
                        ('c', (('D3', 240, 1.25), ('E3', 270, 1.4)))):
        for p, fr, d in notes:
            S.n(TB1, T(fr), d, p, 40, voice=v_id, dyn=[(0, 34), (d * 0.6, 44), (d, 40)])
    ostinato(S, VC, T(240), BEAT / 2, pat('G2', 'Bb2', 'D3'), 50, acc8, n=4)
    ostinato(S, VC, T(255), BEAT / 2, [M('G2'), M('D3'), M('Bb2'), M('G2')], 52, acc8, n=4)
    ostinato(S, VC, T(270), BEAT / 2, pat('A2', 'C#3', 'E3'), 54, acc8, cresc=(0, 12))
    S.n(CBP, T(240), 1, 'G1', 62, double='strings')
    S.n(CBP, T(270), 1, 'A1', 66, double='strings')
    S.n(CBN, T(270), 1.25, 'A1', 40, dyn=[(0, 36), (1.25, 70)], double='strings')
    timp_roll(S, T(270), T(300), 'A2', 34, 96)
    S.n(RCYM, T(300) - 1.4, 1.4, None, 92, L)

    # ===================================================== BAR 6  f300  HIT 1
    S.mark(T(300), 'BAR 6 HIT 1 stamp -> cask; horns + celli PATIENCE')
    t = T(300)
    S.n(TIMP, t, 1, 'D2', 104, L)
    S.n(BD, t, 1, 57, 96, L)
    S.n(TBS, t, 2.2, 'D2', 96, L, dyn=sfz(96, 0.6, 0.45, 2.2), release=0.6)
    S.n(TU, t, 2.2, 'D2', 96, L, dyn=sfz(96, 0.6, 0.45, 2.2), release=0.6)
    stabs(S, t, [(TUS, ('D2',)), (TBX, ('D2', 'D3'))], 100)
    S.n(CR, t, 1, None, 72, L)
    motif = (('D3', 300), ('A3', 330), ('Bb3', 360), ('A3', 390))
    for i, (p, fr) in enumerate(motif):
        d = 1.25
        dyn = [(0, 82), (0.3, 88), (d, 86)] if i < 2 else [(0, 88), (0.9 * d, 102), (d, 98)]
        S.n(HN, T(fr), d, p, 86, double='horns', dyn=dyn)
        S.n(VCS, T(fr), d, p, 80, double='strings', dyn=[(0, 74), (0.3, 82), (d, 84 + 6 * i)])
        S.n(VAS, T(fr), d, M(p) + 12, 70, double='strings', dyn=[(0, 64), (0.3, 72), (d, 74 + 5 * i)])
    for p, fr in (('D2', 300), ('Bb1', 330), ('F1', 360), ('C2', 390)):
        S.n(CBN, T(fr), 1.25, p, 74, double='strings', dyn=[(0, 70), (1.25, 80)])
    # violin tremolo on the seasons harmony (Dm, Bb), then spiccato 16ths from bar 7
    for fr, ps in ((300, ('A4', 'D5')), (330, ('Bb4', 'D5'))):
        for p in ps:
            S.n(VNT, T(fr), 1.25, p, 58, double='strings', dyn=[(0, 52), (1.25, 64)])
    # one pizz accent per sun sweep (every beat, f300-f405)
    pz = ['D5', 'A4', 'F5', 'D5', 'D5', 'Bb4', 'F5', 'D5', 'C5', 'A4', 'F5', 'C5', 'G4', 'C5', 'E5', 'G5']
    for k, fr in enumerate(range(300, 420, 15)):
        S.n(VNP, T(fr), 0.6, pz[2 * k % len(pz)], 74 if k < 6 else 66, double='strings')
        S.n(VAP, T(fr), 0.6, M(pz[(2 * k + 1) % len(pz)]) - 12, 66, double='strings')

    # ===================================================== BAR 7  f360
    S.mark(T(360), 'BAR 7 violins spiccato 16ths, snare roll from f390')
    acc4 = [12, 0, 5, 0]
    ostinato(S, VN, T(360), BEAT / 4, [M('A4'), M('C5'), M('F5'), M('C5')], 58, acc4, cresc=(0, 8), n=8)
    ostinato(S, VN, T(390), BEAT / 4, [M('G4'), M('C5'), M('E5'), M('C5')], 64, acc4, cresc=(0, 10), n=8)
    S.n(SNR, T(390), T(480) - T(390) - 0.11, None, 24, dyn=[(0, 22), (1.6, 40), (T(480) - T(390), 92)],
        release=0.06)

    # ===================================================== BAR 8  f420  '1935'
    S.mark(T(420), "BAR 8 '1935' timp + choke, riser, horns crescendo")
    S.n(TIMP, T(420), 1, 'Bb2', 96, L)
    S.n(SUS, T(420), 0.16, None, 92, L, choke=True, release=0.06)
    ostinato(S, VN, T(420), BEAT / 4, [M('F4'), M('Bb4'), M('D5'), M('Bb4')], 64, acc4, cresc=(0, 6), n=8)
    ostinato(S, VN, T(450), BEAT / 4, [M('G4'), M('C5'), M('E5'), M('C5')], 70, acc4, cresc=(0, 16), n=7)
    gap = 0.11      # the orchestra lets go ~110 ms before HIT 2 (the suck-in before the downbeat)
    for fr, ps, v0, v1 in ((420, ('F3', 'Bb3'), 70, 86), (450, ('G3', 'C4'), 86, 106)):
        for p in ps:
            d = 1.25 - (gap if fr == 450 else 0)
            S.n(HN, T(fr), d, p, v0, double='horns', dyn=[(0, v0), (d, v1)], release=0.08 if fr == 450 else None)
    for fr, ps, v0, v1 in ((420, ('Bb2', 'D3', 'F3'), 50, 64), (450, ('C3', 'E3', 'G3'), 66, 94)):
        for i, p in enumerate(ps):
            d = 1.25 - (gap if fr == 450 else 0)
            S.n(TB1, T(fr), d, p, v0, voice=f'tb{i}', dyn=[(0, v0), (d, v1)], release=0.08 if fr == 450 else None)
    for fr, p in ((420, 'D4'), (450, 'E4')):
        S.n(VAT, T(fr), 1.25 - (gap if fr == 450 else 0), p, 56, double='strings',
            dyn=[(0, 52), (1.25, 84 if fr == 450 else 66)], release=0.08 if fr == 450 else None)
    for fr, p in ((420, 'Bb2'), (450, 'C3')):
        S.n(VCS, T(fr), 1.25 - (gap if fr == 450 else 0), p, 66, double='strings',
            dyn=[(0, 62), (1.25, 92 if fr == 450 else 74)], release=0.08 if fr == 450 else None)
    for fr, p in ((420, 'Bb1'), (450, 'C2')):
        S.n(CBN, T(fr), 1.25 - (gap if fr == 450 else 0), p, 70, double='strings',
            dyn=[(0, 66), (1.25, 96 if fr == 450 else 78)], release=0.08 if fr == 450 else None)
    S.n(SWELL, T(420) + 0.1, T(480) - T(420) - 0.1, None, 92, L)
    timp_roll(S, T(450), T(480) - 0.04, 'C3', 46, 100)
    S.n(RCYM, T(480) - 1.25, 1.25, None, 100, L)

    # ===================================================== BAR 9  f480  HIT 2 + the MARCH
    S.mark(T(480), 'BAR 9 HIT 2 oculus -> porthole; ship-horn fifth; MARCH')
    t = T(480)
    S.n(BD, t, 1, 55, 127, L)
    S.n(BDB, t, 1, 57, 124, L)
    S.n(FD, t, 1, 57, 120, L)
    S.n(TOM, t, 1, 56, 122, L)
    S.n(TOM, t + 0.035, 1, 60, 104, L)                      # taiko-style flam
    S.n(TIMP, t, 1, 'D2', 127, L)
    S.n(CR2, t, 1, None, 118, L)
    for p in ('D2', 'A2'):
        S.n(TBS, t, 1.25, p, 120, L, dyn=[(0, 122), (0.2, 104), (1.25, 100)], release=0.35)
    S.n(TU, t, 1.25, 'D2', 122, L, dyn=[(0, 122), (0.2, 104), (1.25, 100)], release=0.35)
    S.n(BN, t, 1.25, 'D2', 108, L, dyn=[(0, 110), (1.25, 92)], release=0.3)
    for p in ('D3', 'A3'):
        S.n(HN, t, 1.25, p, 116, L, double='horns', dyn=[(0, 118), (0.2, 102), (1.25, 100)], release=0.3)
    S.n(CBN, t, 1.25, 'D1', 112, L, double='strings', dyn=[(0, 112), (1.25, 96)], release=0.35)
    stabs(S, t, [(TUS, ('D2',)), (TBX, ('D2', 'A2')), (HNX, ('D3', 'A3'))], 127)
    # march bass ostinato D-D-F-E (quarters) on tuba + bassoon + basses
    line = [('D2', 510), ('D2', 525), ('D2', 540), ('D2', 555), ('F2', 570), ('E2', 585),
            ('C2', 600), ('C2', 615), ('A1', 630), ('A1', 645)]
    for k, (p, fr) in enumerate(line):
        v = 92 + (10 if fr % 60 == 0 else 0)
        S.n(TUS, T(fr), 0.5, p, v)
        S.n(BNS, T(fr), 0.5, p, v - 6)
        S.n(CB, T(fr), 0.5, M(p) - (12 if p[0] in 'DEF' else 0), v, double='strings')
    # rope-tension snare ostinato (f510 -> f660): accent - . tap tap per beat, fill at f555
    for fr in range(510, 660, 15):
        b = T(fr)
        accent = 104 if fr % 30 == 0 else 92
        S.n(SN, b, 0.3, None, accent)
        if fr == 555:
            for k in range(1, 4):
                S.n(SN, b + k * BEAT / 4, 0.3, None, 70 + 10 * k)
        else:
            S.n(SN, b + 2 * BEAT / 4, 0.3, None, 58)
            S.n(SN, b + 3 * BEAT / 4, 0.3, None, 66)
    # upper strings over the march (light under VO 5)
    acc8b = [10, 0, 4, 0]
    ostinato(S, VN, T(510), BEAT / 2, [M('D5'), M('A4'), M('F4'), M('A4')], 60, acc8b, n=4)
    ostinato(S, VC, T(510), BEAT / 2, pat('D3', 'F3', 'A3'), 64, acc8, n=4)

    # ===================================================== BAR 10  f540  horns PATIENCE f
    S.mark(T(540), 'BAR 10 four horns PATIENCE f; snare fill f555; choke + timp f585')
    for p, fr, d in (('D3', 540, 1.25), ('A3', 570, 1.25), ('Bb3', 600, 1.25), ('A3', 630, 1.25)):
        v = 98 if fr < 600 else 104
        S.n(HN, T(fr), d, p, v, double='horns', dyn=[(0, v - 4), (0.3, v), (d, v + 2)])
    ostinato(S, VN, T(540), BEAT / 4, [M('D5'), M('F5'), M('Bb5'), M('F5')], 70, acc4, n=8)
    ostinato(S, VN, T(570), BEAT / 4, [M('C5'), M('F5'), M('A5'), M('F5')], 72, acc4, n=8)
    ostinato(S, VA, T(540), BEAT / 2, pat('Bb3', 'D4', 'F4'), 66, acc8, n=4)
    ostinato(S, VA, T(570), BEAT / 2, pat('F3', 'A3', 'C4'), 68, acc8, n=4)
    ostinato(S, VC, T(540), BEAT / 2, pat('Bb2', 'D3', 'F3'), 70, acc8, n=4)
    ostinato(S, VC, T(570), BEAT / 2, pat('F2', 'A2', 'C3'), 72, acc8, n=4)
    S.n(SUS, T(585), 0.14, None, 96, L, choke=True, release=0.05)
    S.n(TIMP, T(585), 1, 'F2', 100, L)

    # ===================================================== BAR 11  f600  AMERICA
    S.mark(T(600), 'BAR 11 AMERICA two trumpets A-E-F-E; full spiccato; dead cut at f660')
    for p, fr, d in (('A4', 600, 0.625), ('E5', 615, 0.625), ('F5', 630, 0.625), ('E5', 645, 0.8)):
        v = 94 if fr < 645 else 88
        S.n(TPT, T(fr), d, p, v, double='trumpets', dyn=[(0, v - 4), (0.15, v + 2), (d, v + 4)])
    S.n(TIMP, T(600), 1, 'C3', 100, L)
    S.n(TIMP, T(630), 1, 'A2', 104, L)
    ostinato(S, VN, T(600), BEAT / 4, [M('E5'), M('G5'), M('C6'), M('G5')], 76, acc4, cresc=(0, 6), n=8)
    ostinato(S, VN, T(630), BEAT / 4, [M('E5'), M('A5'), M('E6'), M('A5')], 76, acc4, cresc=(0, 4), n=8)
    ostinato(S, VA, T(600), BEAT / 4, [M('C4'), M('E4'), M('G4'), M('E4')], 70, acc4, n=8)
    ostinato(S, VA, T(630), BEAT / 4, [M('A3'), M('E4'), M('A4'), M('E4')], 72, acc4, cresc=(0, 6), n=8)
    ostinato(S, VC, T(600), BEAT / 2, pat('C3', 'E3', 'G3'), 74, acc8, n=4)
    ostinato(S, VC, T(630), BEAT / 2, [M('A2'), M('A2'), M('E3'), M('A2')], 76, acc8, cresc=(0, 6), n=4)
    for p in ('C3', 'E3', 'G3'):
        S.n(TB1, T(600), 0.625 * 2, p, 70, voice=p, dyn=[(0, 66), (1.25, 80)])
    for p, vo in (('A2', 'C3'), ('E3', 'E3'), ('A3', 'G3')):
        S.n(TB1, T(630), 1.25, p, 72, voice=vo, dyn=[(0, 70), (1.25, 84)])

    # ===================================================== BAR 12  f660  DEAD CUT -> Tahoe
    S.mark(T(660), 'BAR 12 DEAD CUT; violin harmonic A5 ppp, harp harmonic D')
    S.n(VSOLO, T(660) + 0.02, 4.6, 'A5', 30, attack=0.9, bus='harm', dyn=[(0, 26), (2.0, 34), (4.6, 28)])
    S.n(HARP, T(675), 3.0, 'D5', 48, bus='harm')

    # ===================================================== BAR 13  f720
    S.mark(T(720), 'BAR 13 piano callback, cello tremolo D pp, fuse in 16ths')
    S.n(PNO, T(720), 2.0, 'A4', 46, bus='piano')
    S.n(PNO, T(750), 2.5, 'F4', 42, bus='piano')
    S.n(VCT, T(722), T(SIL_A) - T(722), 'D3', 32, attack=1.2, double='strings',
        dyn=[(0, 28), (5.0, 36), (8.0, 48), (10.5, 70), (T(SIL_A) - T(722), 92)])

    # ===================================================== BAR 14  f780  heartbeat
    S.mark(T(780), 'BAR 14 sub heartbeat (bass drum + 40 Hz sine + pizz basses)')
    for k, fr in enumerate(range(780, 1000, 30)):
        v = 50 + 4 * k
        S.n('perc.bass_drum.muted', T(fr), 1, 55, v, L, gain_db=2.0)
        S.n(CBP, T(fr), 1, 'D1', 56 + 3 * k, L, double='strings')
    S.n(PNO, T(795), 3.0, 'D2', 44, bus='piano')

    # ===================================================== BARS 15-17  the climb
    S.mark(T(840), 'BARS 15-17 violin tremolo climbs E-F-G over the D pedal')
    for fr, p, v0, v1 in ((840, 'E5', 28, 40), (900, 'F5', 40, 58), (960, 'G5', 58, 96)):
        d = 2.5 if fr < 960 else T(SIL_A) - T(960)
        S.n(VNT, T(fr), d, p, v0, double='strings', dyn=[(0, v0), (d, v1)], attack=0.25 if fr == 840 else None)
        S.n(VAT, T(fr), d, M(p) - 12, v0 - 4, double='strings', dyn=[(0, v0 - 4), (d, v1 - 2)])
    S.n(CBN, T(900), T(SIL_A) - T(900), 'D1', 30, attack=0.8, double='strings', dyn=[(0, 28), (4.375, 80)])
    timp_roll(S, T(930), T(SIL_A), 'D2', 30, 104)
    S.mark(T(960), 'BAR 17 low brass PATIENCE in quarters; snare roll; reversed crash -> f1005')
    for p, fr, d, v in (('D3', 960, 0.625, 82), ('A3', 975, 0.625, 94), ('Bb3', 990, T(SIL_A) - T(990), 108)):
        S.n(TBS, T(fr), d, p, v, dyn=[(0, v), (d, v + 8)])
        S.n(TU, T(fr), d, M(p) - 12, v, dyn=[(0, v), (d, v + 8)])
        S.n(BN, T(fr), d, M(p) - 12, v - 10)
    S.n(SNR, T(975), T(SIL_A) - T(975), None, 40, dyn=[(0, 40), (T(SIL_A) - T(975), 110)])
    S.n(RCYM, T(SIL_A) - 2.0, 2.0, None, 112, L)

    # ===================================================== BAR 18  f1020  IMPACT
    S.mark(T(1020), 'BAR 18 IMPACT fff; Bb/D stab swelling; reverse gong + cymbal swell into f1080')
    t = T(1020)
    S.n(BD, t, 1, 55, 127, L)
    S.n(BD, t + 0.004, 1, 58, 120, L)
    S.n(BDV, t, 1, 57, 127, L)
    S.n(BDB, t, 1, 56, 120, L)
    S.n(TIMP, t, 1, 'D2', 127, L)
    S.n(TIMP, t, 1, 'A2', 118, L)
    S.n(CR2, t, 1, None, 124, L)
    S.n(CR, t + 0.01, 1, None, 110, L)
    S.n(GONG, t, 1, None, 116, L)
    stab = [(0, 127), (0.45, 114), (0.95, 80), (1.6, 76), (2.5, 96)]
    stabs(S, t, [(TUS, ('D2',)), (TBX, ('Bb2', 'D3', 'F3')), (HNX, ('F3', 'Bb3', 'D4')), (BNS, ('D2',))], 127)
    S.n(TU, t, 2.5, 'D2', 127, L, dyn=stab)
    S.n(BN, t, 2.5, 'D2', 116, L, dyn=stab)
    S.n(CBN, t, 2.5, 'D1', 120, L, dyn=stab, double='strings')
    for p in ('Bb2', 'D3', 'F3'):
        S.n(TBS, t, 2.5, p, 124, L, dyn=stab)
    for p in ('F3', 'Bb3', 'D4'):
        S.n(HN, t, 2.5, p, 122, L, double='horns', dyn=stab)
    for p in ('D5', 'F5'):
        S.n(VNT, t + 0.05, 2.45, p, 46, double='strings', dyn=[(0, 40), (2.45, 92)])
    S.n(VAT, t + 0.05, 2.45, 'Bb4', 44, double='strings', dyn=[(0, 40), (2.45, 88)])
    S.n(VCT, t + 0.05, 2.45, 'D3', 50, double='strings', dyn=[(0, 46), (2.45, 92)])
    timp_roll(S, T(1035), T(1080) - 0.04, 'D2', 40, 96)
    S.n(SWELL, T(1050), T(1080) - T(1050), None, 96, L)
    S.n(RGONG, T(1050), T(1080) - T(1050), None, 96, L)

    # ===================================================== BAR 19  f1080  THE BLOOM, D MAJOR
    S.mark(T(1080), 'BAR 19 THE BLOOM: D major, horns + trumpets D-A-B-A ff, organ 16/32')
    t = T(1080)
    S.n(TIMP, t, 1, 'D2', 122, L)
    S.n(BD, t, 1, 57, 116, L)
    S.n(TOM, t, 1, 57, 112, L)
    S.n(CR, t, 1, None, 108, L)
    stabs(S, t, [(HNX, ('D3',)), (TPX, ('D4',)), (TBX, ('D3', 'A3'))], 118)
    S.n(BD, T(1110), 1, 57, 100)
    S.n(TOM, T(1110), 1, 57, 100)
    for p, fr, d in (('D3', 1080, 0.625), ('A3', 1095, 0.625), ('B3', 1110, 1.25), ('A3', 1140, 1.25)):
        last = fr == 1140
        S.n(HN, T(fr), d, p, 118, double='horns',
            dyn=([(0, 116), (0.15, 120), (d, 118)] if fr < 1110 else [(0, 114), (d, 108)]) if not last
            else [(0, 110), (0.4, 92), (d, 80)])
        S.n(TPT, T(fr), d, M(p) + 12, 112, double='trumpets',
            dyn=[(0, 110), (0.15, 116), (d, 114)] if not last else [(0, 104), (0.4, 84), (d, 70)])
    for fr, ps in ((1080, ('D3', 'F#3', 'A3')), (1110, ('D3', 'G3', 'B3')), (1140, ('D3', 'F#3', 'A3'))):
        for i, p in enumerate(ps):
            S.n(TB1, T(fr), 1.25 if fr < 1140 else 1.6, p, 98 if fr < 1140 else 92, voice=f'b{i}',
                dyn=[(0, 98), (1.25, 100)] if fr < 1140 else [(0, 94), (0.5, 80), (1.6, 60)])
    S.n(TU, t, 2.5, 'D2', 104, dyn=[(0, 108), (2.5, 96)])
    S.n(CBN, t, 2.5, 'D1', 100, double='strings')
    S.n(PED, t, 4.8, 'D1', 104, dyn=[(0, 100), (2.5, 104), (4.8, 70)], release=1.0)          # 16'
    S.n(PED, t, 4.8, 'A1', 70, gain_db=-6, dyn=[(0, 66), (4.8, 50)], release=1.0)           # 10 2/3' -> resultant 32'
    S.n(ORG, t, 4.8, 'D2', 84, dyn=[(0, 84), (4.8, 60)], release=1.0)
    ostinato(S, VN, t, BEAT / 4, [M('D5'), M('F#5'), M('A5'), M('F#5')], 98, acc4, n=8)
    ostinato(S, VN, T(1110), BEAT / 4, [M('D5'), M('G5'), M('B5'), M('G5')], 94, acc4, n=8)
    ostinato(S, VA, t, BEAT / 4, [M('A3'), M('D4'), M('F#4'), M('D4')], 88, acc4, n=8)
    ostinato(S, VA, T(1110), BEAT / 4, [M('B3'), M('D4'), M('G4'), M('D4')], 90, acc4, n=8)
    ostinato(S, VC, t, BEAT / 2, pat('D3', 'F#3', 'A3'), 92, acc8, n=4)
    ostinato(S, VC, T(1110), BEAT / 2, [M('D3'), M('D3'), M('B2'), M('D3')], 92, acc8, n=4)
    S.n(VNS, t, 2.5, 'F#5', 84, double='strings', dyn=[(0, 80), (2.5, 92)])
    harp_gliss(S, t + 0.01, 0.6, 'D3', 'D6', DMAJ, 60, 84)

    # ===================================================== BAR 20  f1140  TITLE HIT
    S.mark(T(1140), 'BAR 20 TITLE HIT; brass holds D, pulls back to strings + horns')
    t = T(1140)
    S.n(TIMP, t, 1, 'D2', 112, L)
    S.n(BD, t, 1, 57, 108, L)
    S.n(CR, t, 1, None, 100, L)
    for fr, chord in ((1140, (('D5', 'F#5'), ('A4',), ('D3',), ('D2',))), (1170, (('C#5', 'E5'), ('A4',), ('A2',), ('A1',)))):
        vn, va, vc, cb = chord
        for p in vn:
            S.n(VNS, T(fr), 1.25, p, 76, double='strings', dyn=[(0, 80), (1.25, 70)])
        for p in va:
            S.n(VAS, T(fr), 1.25, p, 70, double='strings')
        for p in vc:
            S.n(VCS, T(fr), 1.25, p, 72, double='strings')
        for p in cb:
            S.n(CBN, T(fr), 1.25, p, 70, double='strings')
    for p in ('D3', 'F#3'):
        S.n(HN, T(1140), 1.25, p, 84, double='horns', dyn=[(0, 96), (0.6, 78), (1.25, 70)])
    for p in ('E3', 'C#4'):
        S.n(HN, T(1170), 1.25, p, 72, double='horns', dyn=[(0, 70), (1.25, 82)])

    # ===================================================== BAR 21  f1200  HERO HIT
    S.mark(T(1200), 'BAR 21 HERO HIT: full tutti D major + organ; motif in augmentation')
    t = T(1200)
    S.n(BD, t, 1, 55, 127, L)
    S.n(BDB, t, 1, 57, 120, L)
    S.n(TIMP, t, 1, 'D2', 125, L)
    S.n(CR2, t, 1, None, 116, L)
    S.n(TOM, t, 1, 57, 110, L)
    stabs(S, t, [(TUS, ('D2',)), (TBX, ('D3', 'F#3', 'A3')), (HNX, ('D3',)), (TPX, ('D4',))], 120)
    S.n(PED, t, 5.2, 'D1', 110, L, dyn=[(0, 112), (1.0, 96), (5.2, 84)], release=1.0)
    S.n(PED, t, 5.2, 'A1', 72, L, gain_db=-6, release=1.0)
    for p in ('D3', 'F#3', 'A3', 'D4'):
        S.n(ORG, t, 5.2, p, 110, L, dyn=[(0, 114), (1.0, 88), (5.2, 74)], release=1.0)
    S.n(TU, t, 2.5, 'D2', 116, L, dyn=[(0, 118), (0.4, 90), (2.5, 86)])
    S.n(CBN, t, 5.0, 'D1', 104, L, double='strings', dyn=[(0, 108), (5.0, 84)])
    S.n(CBN, t, 5.0, 'D2', 90, double='strings', dyn=[(0, 94), (5.0, 80)])
    for p, fr, d in (('D3', 1200, 1.25), ('A3', 1230, 1.25), ('B3', 1260, 1.25), ('A3', 1290, 1.6)):
        v = 114 if fr == 1200 else 86
        dh = [(0, v), (0.6, 92), (d, 88)] if fr == 1200 else [(0, v), (d, v - 4)]
        S.n(HN, T(fr), d, p, v, double='horns', dyn=dh)
        S.n(TPT, T(fr), d, M(p) + 12, v - 6, double='trumpets', dyn=[(a, b - 6) for a, b in dh])
    for fr, ps in ((1200, ('D3', 'F#3', 'A3')), (1230, ('C#3', 'F#3', 'A3')), (1260, ('D3', 'G3', 'B3')),
                   (1290, ('D3', 'F#3', 'A3'))):
        for i, p in enumerate(ps):
            v = 110 if fr == 1200 else 76
            S.n(TB1, T(fr), 1.25 if fr < 1290 else 1.8, p, v, voice=f'h{i}',
                dyn=[(0, v), (0.4, min(v, 84)), (1.25, 78)] if fr == 1200 else [(0, v), (1.25, v - 6)])
    # strings soar (bars 21-22): violins line F#5 E5 | B5 A5 over D F#m | G/D D
    for p, fr, d in (('F#5', 1200, 1.25), ('E5', 1230, 1.25), ('B5', 1260, 1.25), ('A5', 1290, 1.9)):
        S.n(VNS, T(fr), d, p, 92, double='strings', dyn=[(0, 88), (d * 0.5, 96), (d, 90 if fr < 1290 else 70)])
        S.n(VNS, T(fr), d, M(p) - 12, 80, double='strings', dyn=[(0, 78), (d, 82 if fr < 1290 else 62)])
    for p, fr in (('A4', 1200), ('A4', 1230), ('G4', 1260), ('F#4', 1290)):
        S.n(VAS, T(fr), 1.25 if fr < 1290 else 1.9, p, 80, double='strings')
    for p, fr in (('D3', 1200), ('F#2', 1230), ('G2', 1260), ('D3', 1290)):
        S.n(VCS, T(fr), 1.25 if fr < 1290 else 1.9, p, 82, double='strings')

    # ===================================================== BAR 22  f1260  plagal turn, harp shimmer
    S.mark(T(1260), 'BAR 22 plagal G/D -> D, harp shimmer, decrescendo')
    shimmer = [('D6', 'G6', 'B6', 'G6'), ('D6', 'F#6', 'A6', 'F#6')]
    for h, fr in enumerate((1260, 1290)):
        for k in range(8):
            S.n(HARP, T(fr) + k * BEAT / 4, 1.2, shimmer[h][k % 4], 52 - 2 * k - 6 * h)

    # ===================================================== BAR 23  f1320  thins to strings + organ
    S.mark(T(1320), 'BAR 23 strings + organ D; near silence after f1335; low chime + harmonics f1350')
    for p in ('D3', 'A3'):
        S.n(ORG, T(1320), T(1335) - T(1320) + 0.1, p, 60, dyn=[(0, 60), (0.7, 46)], release=0.5)
    for inst, p, v in ((VNS, 'D5', 56), (VNS, 'A4', 52), (VAS, 'F#4', 50), (VCS, 'D3', 52), (CBN, 'D2', 50)):
        S.n(inst, T(1320), T(1335) - T(1320), p, v, double='strings', dyn=[(0, v), (0.62, v - 18)], release=0.45)
    S.n(BELL, T(1350), 1, 'D4', 70, L, bus='bells')
    S.n(VSOLO, T(1350) + 0.02, DUR - T(1350) - 0.1, 'A5', 24, attack=0.6, bus='harm',
        dyn=[(0, 20), (1.5, 26), (3.5, 18)])
    S.n(VNS, T(1350) + 0.05, DUR - T(1350) - 0.15, 'D6', 22, attack=0.8, bus='harm', double='strings',
        dyn=[(0, 18), (1.8, 26), (3.6, 16)])

    # ===================================================== BAR 24  f1380  BUTTON
    S.mark(T(1380), 'BAR 24 BUTTON: timp, bass drum, low-brass D major, organ D, chime bookend')
    t = T(1380)
    S.n(TIMP, t, 1, 'D2', 124, L)
    S.n(BD, t, 1, 57, 124, L)
    S.n(BDB, t, 1, 57, 112, L)
    S.n(BELL, t, 1, 'D4', 90, L, bus='bells')
    for p in ('D3', 'F#3', 'A3'):
        S.n(TBS, t, 0.9, p, 120, L, dyn=[(0, 122), (0.5, 112), (0.9, 92)], release=0.7)
        S.n(HN, t, 0.9, p, 114, L, double='horns', dyn=[(0, 116), (0.5, 106), (0.9, 88)], release=0.7)
    S.n(TU, t, 0.9, 'D2', 120, L, dyn=[(0, 122), (0.5, 112), (0.9, 92)], release=0.7)
    stabs(S, t, [(TUS, ('D2',)), (TBX, ('D3', 'F#3', 'A3')), (HNX, ('D3', 'A3'))], 124)
    S.n(CBN, t, 1.0, 'D1', 104, L, double='strings', release=0.8)
    for p in ('D3', 'A3', 'D4'):
        S.n(ORG, t, 1.6, p, 110, L, dyn=[(0, 112), (1.6, 72)], release=1.3)
    S.n(PED, t, 1.6, 'D1', 104, L, dyn=[(0, 104), (1.6, 76)], release=1.3)

    # ===================================================== FUSE TICK (dry, mono, high-passed claves)
    def tick(fr, vel, gdb):
        S.n(CLV, T(fr), 0.05, 65, vel, L, bus='fuse', gain_db=gdb)
    for fr in range(60, 300, 30):            # Act I: half notes
        tick(fr, 60, -2.0)
    for fr in range(300, 480, 15):           # Act II: quarter notes
        tick(fr, 62, -1.0)
    for i, fr in enumerate(np.arange(480, 660, 7.5)):   # Act III: eighths (stops dead at f660)
        tick(fr, 64 if i % 2 == 0 else 56, -3.0)
    for i, fr in enumerate(np.arange(720, 1005, 3.75)):  # Tahoe: sixteenths, ~-30 dB, +2 dB per bar
        bar = int((fr - 720) // 60)
        tick(fr, 58 if i % 4 == 0 else 50, -6.0 + 2.0 * bar + (fr - 720 - 60 * bar) / 60 * 2.0)
    tick(1425, 62, -3.0)                     # once more, alone
    return S


# --------------------------------------------------------------------------- passes / segments
def build_passes(S, fast=False):
    """Return {(segment, kind): [Note]}: kind 'free' (humanised), 'locked', 'B' (second string /
    horn / trumpet pass, humanised with another seed)."""
    out = {}
    tune_sign = 1
    for e in S.ev:
        n = e['note']
        seg = 'A' if n.t < T(CUT_DEAD) else ('B' if n.t < T(SIL_A) else 'C')
        dbl = e['double']
        p0 = INSTRUMENTS[n.inst].get('pan', 0.0)
        if dbl == 'strings' and not fast:
            a = replace(n, pan=max(-1, p0 - 0.17), width=0.55)
            b = replace(n, pan=min(1, p0 + 0.19), width=0.55, tune=n.tune + 3.0, gain_db=n.gain_db - 1.0)
        elif dbl == 'horns' and not fast:
            tune_sign = -tune_sign
            a = replace(n, pan=p0 - 0.12, tune=n.tune - 2.0)
            b = replace(n, t=n.t + 0.010, pan=p0 + 0.14, tune=n.tune + 4.0 * tune_sign, gain_db=n.gain_db - 0.5)
        elif dbl == 'trumpets' and not fast:
            a = replace(n, pan=p0 - 0.15)
            b = replace(n, t=n.t + 0.012, pan=p0 + 0.2, tune=n.tune + 5.0)
        else:
            a, b = n, None
        kind = 'locked' if e['locked'] else 'free'
        out.setdefault((seg, kind), []).append(a)
        if b is not None:
            out.setdefault((seg, 'B'), []).append(b)
    return out


# --------------------------------------------------------------------------- MIDI
def write_midi(S, cues, path):
    import mido
    PPQ = 480
    mid = mido.MidiFile(type=1, ticks_per_beat=PPQ)
    tick = lambda t: int(round(t / BEAT * PPQ))
    meta = mido.MidiTrack()
    meta.append(mido.MetaMessage('track_name', name='PATIENCE (96 BPM, 24 fps: 1 frame = 32 ticks)', time=0))
    meta.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(BPM), time=0))
    meta.append(mido.MetaMessage('time_signature', numerator=4, denominator=4, time=0))
    meta.append(mido.MetaMessage('key_signature', key='Dm', time=0))
    marks = sorted([(t, txt) for t, txt in S.marks] + [(c['t'], c['name']) for c in cues] +
                   [(T(1080), 'KEY D MAJOR')])
    evs = [(tick(t), mido.MetaMessage('marker', text=txt[:120], time=0)) for t, txt in marks]
    last = 0
    for tk, m in sorted(evs, key=lambda x: x[0]):
        m.time = tk - last
        last = tk
        meta.append(m)
    mid.tracks.append(meta)
    by_inst = {}
    for e in S.ev:
        by_inst.setdefault(e['note'].inst, []).append(e['note'])
    for ch_i, (inst, notes) in enumerate(sorted(by_inst.items())):
        ch = ch_i % 16
        if ch == 9:
            ch = 15
        tr = mido.MidiTrack()
        tr.append(mido.MetaMessage('track_name', name=inst, time=0))
        msgs = []
        for n in notes:
            p = int(round(n.pitch)) if n.pitch is not None else 60
            msgs.append((tick(n.t), 1, mido.Message('note_on', channel=ch, note=p, velocity=int(round(n.vel)))))
            msgs.append((tick(n.t + max(n.dur, 0.05)), 0, mido.Message('note_off', channel=ch, note=p, velocity=0)))
        msgs.sort(key=lambda x: (x[0], x[1]))
        last = 0
        for tk, _, m in msgs:
            m.time = tk - last
            last = tk
            tr.append(m)
        mid.tracks.append(tr)
    mid.save(path)
    return len(by_inst)


# --------------------------------------------------------------------------- mix
SENDS = {   # sub-bus: (hall send, filters)
    'strings': 0.26, 'brass': 0.30, 'woods': 0.28, 'keys': 0.38, 'piano': 0.30, 'harm': 0.50,
    'perc': 0.22, 'bells': 0.0, 'fuse': 0.0, 'fx': 0.18,
}


def process_bus(name, x, ir_hall, ir_long):
    """EQ + hall return for one sub-bus (x: (2, n) float64 slice)."""
    if name == 'piano':     # felt piano: soft hammers -> dark, warm
        x = X.lp(x, 2400, 2)
        x = X.eq(x, [('lowshelf', 160, 2.0, 0.7), ('peak', 900, -1.5, 1.0)])
    elif name == 'harm':    # harmonics: airy, no bow noise, glassy top
        x = X.lp(X.hp(x, 300), 5200, 2)
    elif name == 'fuse':    # dry, mono, high-passed tick
        m = X.hp(x.mean(axis=0), 900, 2)
        m = X.eq(m[None, :], [('peak', 3200, 3.0, 1.2)])[0]
        return np.stack([m, m])
    elif name == 'strings':
        x = X.eq(X.hp(x, 28), [('peak', 300, -1.0, 1.0), ('peak', 3000, 1.0, 0.9), ('highshelf', 8000, 2.5, 0.7)])
    elif name == 'brass':
        x = X.eq(X.hp(x, 30), [('peak', 2200, 1.5, 1.0), ('highshelf', 8000, 2.0, 0.7)])
    elif name == 'perc':
        x = X.hp(x, 22, 2)
    wet = SENDS.get(name, 0.2)
    y = x.copy()
    if wet > 0:
        y += wet * X.convolve(x, ir_hall)
    if name == 'bells':     # the distant church bell in the long hall
        y = 0.55 * x + 0.85 * X.convolve(X.hp(x, 120), ir_long)
    return y


def render_all(S, fast=False, cache_dir=None, log=None):
    smp = Sampler(cache_dir=cache_dir, threads=2)
    passes = build_passes(S, fast)
    ir_hall = X.hall_ir(rt60=2.6, predelay=0.025, seed=7, lp_f=12000.0)
    ir_long = X.hall_ir(rt60=4.2, predelay=0.07, seed=9, length=6.0)
    seg_win = {'A': (0.0, T(CUT_DEAD)), 'B': (T(CUT_DEAD), T(SIL_A)), 'C': (T(SIL_B), DUR)}
    stems = {k: np.zeros((2, N)) for k in ('orchestra', 'percussion', 'synth_fx')}
    stats = {}
    for seg in ('A', 'B', 'C'):
        buses = {}
        for kind, hum in (('free', Humanize(time_ms=3.6, vel=3.0, cents=2.0, seed=11)), ('locked', None),
                          ('B', Humanize(time_ms=3.6, vel=3.0, cents=2.0, seed=23))):
            evs = passes.get((seg, kind), [])
            if not evs:
                continue
            t0 = time.time()
            out = smp.render(evs, seconds=DUR + 1.0, humanize=hum, stems=True)
            stats[f'{seg}/{kind}'] = dict(notes=len(evs), seconds=round(time.time() - t0, 1))
            print(f'  segment {seg} {kind:6s}: {len(evs):5d} notes  {time.time() - t0:6.1f} s', flush=True)
            for b, a in out.items():
                buses[b] = buses.get(b, 0) + a[:, :N].astype(np.float64)
        s0, s1 = seg_win[seg]
        i0 = max(0, int(s0 * SR) - int(0.15 * SR))       # pre-attack anticipation before the segment start
        i1 = N if seg == 'C' else min(N, int(s1 * SR) + int(0.05 * SR))
        for b, a in buses.items():
            y = np.zeros((2, N))
            y[:, i0:i1] = process_bus(b, a[:, i0:i1], ir_hall, ir_long)
            if seg == 'A':
                y = X.zero_after(y, T(CUT_DEAD), fade=0.003)       # DEAD CUT (exact frame)
            elif seg == 'B':
                y *= X.gate_curve(N, [(T(SIL_A - 2), T(SIL_A), 1, 0), (T(SIL_A), DUR + 1, 0, 0)])[None, :]
                y = X.zero_before(y, T(CUT_DEAD))
            else:
                y = X.zero_before(y, T(SIL_B))
            stems[STEM_OF.get(b, 'orchestra')] += y
    # percussion glue: shave the biggest drum transients by up to ~6 dB (look-ahead, 2 ms) so the
    # hits are dense rather than peaky, then make up 3 dB
    p = stems['percussion']
    ceil = A.true_peak_db(p, SR) - 6.0
    g = X.truepeak_limiter_gain(p, ceiling_db=ceil, lookahead=0.002, release=0.06)
    stems['percussion'] = p * g[None, :] * X.db(3.0)
    stats['perc_glue'] = dict(ceiling_dbfs=round(ceil, 2), gr_max_db=round(float(-20 * np.log10(g.min())), 2))
    diag = [n for (sg, kind), evs in passes.items() if kind == 'locked' for n in evs
            if smp.instrument(n.inst).kind == 'perc' and smp.instrument(n.inst).bus == 'perc']
    smp.reset()
    stats['diag_locked_perc_notes'] = len(diag)
    render_all.diag = smp.render(diag, seconds=DUR + 1.0, humanize=None)[:, :N]
    if log is not None:
        log['render'] = stats
        log['sampler_warnings'] = sorted(set(smp.warnings))[:60]
        log['sampler_stats'] = {k: round(v, 2) for k, v in smp.stats.items()}
    return stems, ir_hall


def master(stems, target_lufs=-16.0, log=None):
    """Linked bus compression (2:1) + true-peak limiter on the sum; the same gain curves are
    applied to every stem so that the stems sum exactly to the premix."""
    names = list(stems)
    pre = 0.0
    for it in range(6):
        g_pre = X.db(pre)
        mix = sum(stems[k] for k in names) * g_pre
        gc, grmax = X.compressor_gain(mix, thresh_db=-14.0, ratio=2.0, knee_db=6.0, attack=0.03, release=0.28)
        mix_c = mix * gc[None, :]
        gl = X.truepeak_limiter_gain(mix_c, ceiling_db=-1.2, lookahead=0.004, release=0.09)
        for k in names:
            gl = np.minimum(gl, X.truepeak_limiter_gain(stems[k] * g_pre * gc[None, :], ceiling_db=-0.5,
                                                        lookahead=0.004, release=0.09))
        out = mix_c * gl[None, :]
        L = A.lufs(out, SR)
        err = target_lufs - L
        print(f'  master pass {it}: pre {pre:+.2f} dB -> {L:.2f} LUFS, comp GR max {grmax:.1f} dB, '
              f'limiter GR max {-20 * np.log10(gl.min()):.1f} dB', flush=True)
        if abs(err) < 0.05:
            break
        pre += err * (1.0 if it == 0 else 0.9)
    gain = g_pre * gc * gl
    res = {k: stems[k] * gain[None, :] for k in names}
    if log is not None:
        lgr = -20 * np.log10(gl)
        ev, i = [], 0
        idx = np.argsort(lgr)[::-1]
        for j in idx[:200000:500]:
            if lgr[j] < 1.0:
                break
            if all(abs(j - k) > SR for k, _ in ev):
                ev.append((int(j), float(lgr[j])))
        log['limiter_events'] = [dict(t=round(j / SR, 3), frame=round(j / SR * 24, 1), gr_db=round(v, 1))
                                 for j, v in sorted(ev)[:20]]
        log['master'] = dict(pre_gain_db=round(pre, 2), comp_threshold_db=-14.0, comp_ratio=2.0,
                             comp_gr_max_db=round(grmax, 2), limiter_ceiling_dbtp=-1.2,
                             limiter_gr_max_db=round(float(-20 * np.log10(gl.min())), 2),
                             comp_gr_p95_db=round(float(np.percentile(-20 * np.log10(gc), 95)), 2))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fast', action='store_true')
    ap.add_argument('--out', default=HERE)
    ap.add_argument('--cache', default=os.environ.get('SAMPLER_CACHE', ''))
    a = ap.parse_args()
    t_start = time.time()
    log = {}
    S = compose()
    print(f'score: {len(S.ev)} notes', flush=True)
    stems, ir_hall = render_all(S, fast=a.fast, cache_dir=a.cache or None, log=log)
    print('synth/fx + foley ...', flush=True)
    syn, syn_cues = SY.build_synth(N, ir_hall)
    wet = lambda x: 0.85 * x + 0.12 * X.convolve(X.hp(x, 200), ir_hall)
    pre = X.zero_after(wet(X.zero_after(syn, T(CUT_DEAD), 0.003)), T(CUT_DEAD), 0.003)   # dead cut incl. tails
    post = wet(X.zero_before(syn, T(CUT_DEAD)))
    post *= X.gate_curve(N, [(T(SIL_A - 2), T(SIL_A), 1, 0), (T(SIL_A), T(SIL_B), 0, 0)])[None, :]
    stems['synth_fx'] += pre + X.zero_before(post, T(CUT_DEAD))
    fol, fol_cues = SY.build_foley(N, X.room_ir())
    stems['foley'] = fol * X.db(-1.0)
    # the dead cut also stops the synth layers; the end of the film fades with the picture
    end = X.gate_curve(N, [(T(1432), DUR, 1, 0)])[None, :]
    for k in stems:
        stems[k] = stems[k] * end
        stems[k][:, int(T(SIL_A) * SR):int(T(SIL_B) * SR)] = 0.0
    print('master ...', flush=True)
    stems = master(stems, -16.0, log)
    mix = sum(stems.values())
    os.makedirs(a.out, exist_ok=True)
    for k, v in stems.items():
        Sampler.write(os.path.join(a.out, f'stem_{k}.wav'), v.astype(np.float32))
    Sampler.write(os.path.join(a.out, 'score_mix.wav'), mix.astype(np.float32))
    os.makedirs(os.path.join(a.out, 'qa'), exist_ok=True)
    Sampler.write(os.path.join(a.out, 'qa', 'locked_perc_dry.wav'), render_all.diag.astype(np.float32) * 0.25)
    n_tracks = write_midi(S, syn_cues + fol_cues, os.path.join(a.out, 'patience.mid'))
    log.update(dict(notes=len(S.ev), midi_tracks=n_tracks, synth_cues=syn_cues, foley_cues=fol_cues,
                    lufs=round(A.lufs(mix, SR), 2), true_peak_dbtp=round(A.true_peak_db(mix, SR), 2),
                    seconds=round(time.time() - t_start, 1)))
    with open(os.path.join(a.out, 'render_log.json'), 'w') as f:
        json.dump(log, f, indent=1)
    print(f"done: {log['lufs']} LUFS, {log['true_peak_dbtp']} dBTP, {log['seconds']} s", flush=True)


if __name__ == '__main__':
    main()
