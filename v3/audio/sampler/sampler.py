"""sampler.py -- a small orchestral sample engine over VSCO-2-CE + VCSL (CC0 recordings).

Pure numpy / scipy / soundfile.  Output: float32 stereo arrays shaped (2, n) at 48 kHz.

Quick start
-----------
    from sampler import Sampler, Note, Humanize
    s = Sampler()            # catalog.json next to this file; Sampler(path, cache_dir=None,
                             #   cache_bytes=4<<30, threads=2)
    print(s.list('strings'))                        # instrument ids
    inst = s.instrument('strings.violins.spic')     # -> Instrument (range, layers, rr, kind...)
    ev = [Note('strings.celli.spic', t=0.0, dur=0.2, pitch='D3', vel=100),
          Note('brass.horns.sus', t=0.0, dur=4.0, pitch='A3', vel=70, dyn=[(0, 50), (3.5, 115)]),
          Note('perc.timpani', t=0.0, pitch='D2', vel=120),
          Note('perc.cymbal.swell', t=2.0, dur=2.0, vel=100)]    # swell PEAKS at t+dur
    buf = s.render(ev, seconds=8.0, humanize=Humanize(seed=7))  # (2, 384000) float32
    stems = s.render(ev, 8.0, stems=True)                        # {bus: (2, n)} e.g. strings/brass/perc
    s.write('out.wav', buf)

Notes / events  (`Note` fields)
-------------------------------
  inst      instrument id (see `Sampler.list()` / catalog_summary.md)
  t, dur    start time and length in seconds.  For sustained instruments the note is held for
            `dur` then released; one-shots (spiccato, pizz, staccato, drums, ...) ring out
            naturally and ignore `dur` unless `choke=True`.  For kind 'swell' / 'reverse' the
            sound starts at t and *peaks/lands* at t+dur.
  pitch     MIDI number (int or float, C4 = 60) or a name like 'D2', 'Bb3', 'F#4'.  Unpitched
            instruments use notional key 60: pitch=None (or 60) plays the recording untouched,
            pitch=55 plays it 5 semitones lower (a classic "bigger drum" trick).
  vel       1..127.  Picks the velocity layer(s) and sets the level (see Levels).
  dyn       optional dynamics automation for held notes: [(t_rel, vel), ...] (crescendo /
            diminuendo; velocity layers are cross-faded over time).
  pan       -1..1 (None = instrument default seat), width: stereo width 0..1 (None = default)
  gain_db   extra trim.  attack: fade-in seconds (soft entries).  release: override release.
  offset    seconds to skip into the sample.  tune: cents.  choke: stop one-shots at t+dur.
  legato    None = automatic for legato-capable instruments, False = always re-articulate.
  voice     optional legato voice id (otherwise voices are matched by nearest pitch).
  bus       stem name override (default: instrument family: strings/brass/woods/perc/keys/fx).

Engine behaviour
----------------
* Nearest sampled note is chosen per velocity layer (shifting up costs 15% more) and
  pitch-shifted + converted to 48 kHz in ONE polyphase resampling step
  (scipy.signal.resample_poly, Kaiser windowed sinc; the ratio is approximated by a fraction
  with denominator <= 1000, i.e. < 0.01 cent error).  If a layer has no sample within 3
  semitones but a neighbouring layer has, the neighbouring layer is used.
* Velocity layers: layer coordinate p = vel/127*n - 0.5.  Instruments with `xfade` > 0
  equal-power cross-fade the two adjacent layers in a zone of that width; others switch.
* Round robins cycle per (instrument, layer, sampled note) -- deterministic.
* Levels: every layer is normalised with the catalog's K-weighted momentary loudness so that
  a note at vel 127 reaches ~TARGET_LUFS (-20 LUFS max momentary; + instrument gain_db +
  note gain_db), and
  level(vel) = vel_k * log10(vel/127) dB below that (vel_k ~ 30..36).  So instruments are
  directly comparable; per-note loudness differences inside a layer are half-corrected.
* Timing: the sample is anticipated so that its attack (first point within `align_db` of
  its peak, capped at `align_max` seconds) lands on `t`.
* Sustains: fade at note-off with the instrument's release time (strings 0.38 s, brass
  0.25 s, ...).  Notes longer than the recording are extended with an equal-power
  cross-faded loop taken from the stable part of the sustain.
* Legato: for legato instruments, a note starting within 60 ms of the end of a previous
  note of the same instrument (and same `voice` if given, else nearest pitch) becomes a
  legato transition: the old note fades out and the new one fades in over `legato_xf`
  (equal power) with its attack skipped (`legato_skip`), so lines connect instead of
  re-bowing.
* Unison / sections: some ids are built from solo recordings doubled N times with small
  detune, delay, pan spread and different sampled notes / round robins
  (brass.horns.* = 4 horns, brass.trombones.* = 3, brass.trumpets.* = 3, strings.basses.* = 3).
* Humanize(time_ms, vel, cents, seed): Gaussian jitter, deterministic for a given seed and
  event order.
* Caching: decoded+resampled buffers are kept in an LRU (default 4 GB) keyed by
  (file, cents shift); optionally persisted as .npy in `cache_dir` (instant re-renders across
  runs).  While rendering, each upcoming ~8 s window of events is resolved first (same
  deterministic choices) and its missing buffers are decoded + resampled in `threads` worker
  threads.  Humanised detune is quantised to 3-cent steps so that notes keep sharing buffers.
* Swells: kind 'swell' (perc.cymbal.swell, perc.bass_drum.swell) picks the recorded crescendo
  whose natural length best fits `dur` and places it so its peak lands exactly on t+dur;
  kind 'reverse' (fx.reverse_*) plays a one-shot backwards so its attack lands on t+dur.
* Ranges: `Sampler.instrument(id).info()` gives sampled range, layers, round robins; notes
  beyond the sampled range +-3 st, or needing more than `max_shift` semitones, still play but
  are reported in `Sampler.warnings`.
* Known limitations: resampling shifts formants with pitch (keep shifts small: the engine always
  takes the nearest sample); VSCO horn sustains are dense only up to C4 (D5/F5 exist at pp
  only) so high horn lines get shifted up to 7 st -- double them with trumpets instead; most
  VSCO sustains have 1 round robin; the solo-contrabass/horn/trombone/trumpet "sections" are
  doublings of one player; no true legato transition samples (crossfade emulation).

Helpers: `fx_hall` (synthetic stereo hall convolution reverb), `fx_limit` (look-ahead peak
limiter), `Sampler.write(path, buf)`.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
import time
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field, replace
from fractions import Fraction

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly, fftconvolve, butter, sosfilt
from scipy.ndimage import maximum_filter1d, uniform_filter1d

SR = 48000
TARGET_LUFS = -20.0
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CATALOG = os.path.join(HERE, 'catalog.json')

_PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def note_to_midi(x):
    """'D2' -> 38, 'Bb3' -> 58, 'F#4' -> 66, numbers pass through."""
    if x is None or isinstance(x, (int, float, np.integer, np.floating)):
        return None if x is None else float(x)
    m = re.match(r'^\s*([A-Ga-g])([#b]?)(-?\d)\s*$', str(x))
    if not m:
        raise ValueError(f'bad note name {x!r}')
    v = _PC[m.group(1).upper()] + 12 * (int(m.group(3)) + 1)
    v += {'#': 1, 'b': -1, '': 0}[m.group(2)]
    return float(v)


def midi_name(m):
    m = int(round(m))
    return f'{_NAMES[m % 12]}{m // 12 - 1}'


# ============================================================================ instruments
V2, VC = 'VSCO-2-CE/', 'VCSL/'
_STR, _BR, _WW = V2 + 'Strings/', V2 + 'Brass/', V2 + 'Woodwinds/'
_MEM = VC + 'Membranophones/Struck Membranophones/'
_IDI = VC + 'Idiophones/Struck Idiophones/'
_V1P = V2 + 'VSCO 1 Percussion/'

# unison recipes: (detune cents, delay ms, pan offset, gain dB, alternative sample index)
_A4 = [(0, 0, 0.0, 0, 0), (6, 17, -0.16, -0.5, 1), (-5, 29, 0.14, -0.5, 2), (3, 9, 0.05, -1.0, 3)]
_A3 = [(0, 0, 0.0, 0, 0), (5, 15, -0.13, -0.5, 1), (-6, 26, 0.13, -0.5, 2)]

_SUS_STR = dict(kind='sustain', release=0.38, legato=True, legato_xf=0.11, legato_skip=0.12, xfade=0.6,
                vel_k=30, align_db=-18, align_max=0.07, bus='strings')
_SUS_BR = dict(kind='sustain', release=0.25, legato=True, legato_xf=0.08, legato_skip=0.07, xfade=0.6,
               vel_k=32, align_db=-18, align_max=0.06, bus='brass')
_SUS_WW = dict(kind='sustain', release=0.2, legato=True, legato_xf=0.07, legato_skip=0.06, xfade=0.6,
               vel_k=30, align_db=-18, align_max=0.05, bus='woods')
_SHORT = dict(kind='short', vel_k=32, align_db=-12, align_max=0.08)
# plucked strings: the pluck transient often sits ~-13 dB below a body swell that peaks 50-150 ms later,
# so align on the pluck (-22 dB) instead (QA: violins pizz A4 sounded 30 ms early with -12 dB);
# clash cymbals: the first plate contact is ~8 ms before the -10 dB point.
_PERC = dict(kind='perc', vel_k=36, align_db=-10, align_max=0.03, bus='perc', norm_note=1.0, max_shift=12)

INSTRUMENTS = {
    # ---------------------------------------------------------------- strings (VSCO 2 CE sections)
    'strings.violins.spic': dict(_SHORT, groups=[_STR + 'Violin Section/Spic'], pan=-0.5, width=0.8, bus='strings'),
    'strings.violins.sus': dict(_SUS_STR, groups=[_STR + 'Violin Section/susVib'], pan=-0.5, width=0.9),
    'strings.violins.trem': dict(_SUS_STR, groups=[_STR + 'Violin Section/Trem'], pan=-0.5, legato=False, width=0.9),
    'strings.violins.pizz': dict(_SHORT, align_db=-22, align_max=0.03, groups=[_STR + 'Violin Section/Pizz'], pan=-0.5, width=0.8, bus='strings'),
    'strings.violas.spic': dict(_SHORT, groups=[_STR + 'Viola Section/spic'], pan=0.12, width=0.7, bus='strings'),
    'strings.violas.sus': dict(_SUS_STR, groups=[_STR + 'Viola Section/susvib'], pan=0.12, width=0.8),
    'strings.violas.trem': dict(_SUS_STR, groups=[_STR + 'Viola Section/trem'], pan=0.12, legato=False, width=0.8),
    'strings.violas.pizz': dict(_SHORT, align_db=-22, align_max=0.03, groups=[_STR + 'Viola Section/pizz'], pan=0.12, width=0.7, bus='strings'),
    'strings.celli.spic': dict(_SHORT, groups=[_STR + 'Cello Section/spic'], pan=0.28, width=0.7, bus='strings'),
    'strings.celli.sus': dict(_SUS_STR, groups=[_STR + 'Cello Section/susvib'], pan=0.28, width=0.8),
    'strings.celli.trem': dict(_SUS_STR, groups=[_STR + 'Cello Section/trem'], pan=0.28, legato=False, width=0.8),
    'strings.celli.pizz': dict(_SHORT, align_db=-22, align_max=0.03, groups=[_STR + 'Cello Section/pizzT'], pan=0.28, width=0.7, bus='strings'),
    # basses: solo contrabass doubled x3 into a section
    'strings.basses.spic': dict(_SHORT, groups=[_STR + 'Solo Contrabass/Spic'], pan=0.4, width=0.6, bus='strings', unison=_A3),
    'strings.basses.sus': dict(_SUS_STR, groups=[_STR + 'Solo Contrabass/SusVib'], pan=0.4, width=0.6, unison=_A3),
    'strings.basses.susnv': dict(_SUS_STR, groups=[_STR + 'Solo Contrabass/SusNV'], pan=0.4, width=0.6, unison=_A3),
    'strings.basses.trem': dict(_SUS_STR, groups=[_STR + 'Solo Contrabass/Trem'], pan=0.4, width=0.6, legato=False, unison=_A3),
    'strings.basses.pizz': dict(_SHORT, align_db=-22, align_max=0.03, groups=[_STR + 'Solo Contrabass/Pizz'], pan=0.4, width=0.6, bus='strings', unison=_A3),
    'strings.bass_solo.spic': dict(_SHORT, groups=[_STR + 'Solo Contrabass/Spic'], pan=0.4, width=0.5, bus='strings'),
    'strings.bass_solo.sus': dict(_SUS_STR, groups=[_STR + 'Solo Contrabass/SusVib'], pan=0.4, width=0.5),
    'strings.bass_solo.pizz': dict(_SHORT, align_db=-22, align_max=0.03, groups=[_STR + 'Solo Contrabass/Pizz'], pan=0.4, width=0.5, bus='strings'),
    'strings.violin_solo.sus': dict(_SUS_STR, groups=[_STR + 'Solo Violin/Arco Vib'], pan=-0.2, width=0.5, xfade=0.0),
    'strings.violin_solo.spic': dict(_SHORT, groups=[_STR + 'Solo Violin/spic'], pan=-0.2, width=0.5, bus='strings'),
    'strings.violin_solo.trem': dict(_SUS_STR, groups=[_STR + 'Solo Violin/Trem'], pan=-0.2, width=0.5, legato=False),
    'strings.violin_solo.pizz': dict(_SHORT, align_db=-22, align_max=0.03, groups=[_STR + 'Solo Violin/Pizz'], pan=-0.2, width=0.5, bus='strings'),
    'strings.harp': dict(_SHORT, groups=[VC + 'Chordophones/Composite Chordophones/Concert Harp'], pan=-0.3, width=0.6,
                         bus='strings'),
    # ---------------------------------------------------------------- brass
    'brass.horns.sus': dict(_SUS_BR, groups=[_BR + 'F Horn/sus'], pan=-0.3, width=0.7, unison=_A4),
    'brass.horns.stac': dict(_SHORT, groups=[_BR + 'F Horn/stac'], pan=-0.3, width=0.7, bus='brass', unison=_A4),
    'brass.horns.mute': dict(_SUS_BR, groups=[_BR + 'F Horn/mute'], pan=-0.3, width=0.7, unison=_A4),
    'brass.horn.sus': dict(_SUS_BR, groups=[_BR + 'F Horn/sus'], pan=-0.3, width=0.6),
    'brass.horn.stac': dict(_SHORT, groups=[_BR + 'F Horn/stac'], pan=-0.3, width=0.6, bus='brass'),
    'brass.horn.mute': dict(_SUS_BR, groups=[_BR + 'F Horn/mute'], pan=-0.3, width=0.6),
    'brass.trombones.sus': dict(_SUS_BR, groups=[_BR + 'Tenor Trombone/sus'], pan=0.25, width=0.6, unison=_A3),
    'brass.trombones.stac': dict(_SHORT, groups=[_BR + 'Tenor Trombone/stac'], pan=0.25, width=0.6, bus='brass', unison=_A3),
    'brass.trombone.sus': dict(_SUS_BR, groups=[_BR + 'Tenor Trombone/sus'], pan=0.25, width=0.5),
    'brass.trombone.stac': dict(_SHORT, groups=[_BR + 'Tenor Trombone/stac'], pan=0.25, width=0.5, bus='brass'),
    'brass.trombone.vib': dict(_SUS_BR, groups=[_BR + 'Tenor Trombone/vib'], pan=0.25, width=0.5),
    'brass.trombone_old.sus': dict(_SUS_BR, groups=[_BR + 'OldTrombone/Sustain'], pan=0.35, width=0.5),
    'brass.trombone_old.short': dict(_SHORT, groups=[_BR + 'OldTrombone/Short'], pan=0.35, width=0.5, bus='brass'),
    'brass.trombone_old.buzz': dict(_SUS_BR, groups=[_BR + 'OldTrombone/Buzz'], pan=0.35, width=0.5, legato=False),
    'brass.trombone_old.fall': dict(_SHORT, groups=[_BR + 'OldTrombone/Fall'], pan=0.35, width=0.5, bus='brass'),
    'brass.trumpets.sus': dict(_SUS_BR, groups=[_BR + 'Trumpet/sus'], pan=0.1, width=0.6, unison=_A3),
    'brass.trumpets.stac': dict(_SHORT, groups=[_BR + 'Trumpet/stac'], pan=0.1, width=0.6, bus='brass', unison=_A3),
    'brass.trumpet.sus': dict(_SUS_BR, groups=[_BR + 'Trumpet/sus'], pan=0.1, width=0.5),
    'brass.trumpet.susvib': dict(_SUS_BR, groups=[_BR + 'Trumpet/susvib'], pan=0.1, width=0.5),
    'brass.trumpet.stac': dict(_SHORT, groups=[_BR + 'Trumpet/stac'], pan=0.1, width=0.5, bus='brass'),
    'brass.trumpet.mute': dict(_SUS_BR, groups=[_BR + 'Trumpet/straightM-sus'], pan=0.1, width=0.5),
    'brass.trumpet.harmon': dict(_SUS_BR, groups=[_BR + 'Trumpet/harmonM-sus'], pan=0.1, width=0.5),
    'brass.tuba.sus': dict(_SUS_BR, groups=[_BR + 'Tuba/sus'], pan=0.35, width=0.5, release=0.3),
    'brass.tuba.stac': dict(_SHORT, groups=[_BR + 'Tuba/stac'], pan=0.35, width=0.5, bus='brass'),
    # ---------------------------------------------------------------- woodwinds
    'woods.flute.sus': dict(_SUS_WW, groups=[_WW + 'Flute/susNV'], pan=-0.1, width=0.5),
    'woods.flute.vib': dict(_SUS_WW, groups=[_WW + 'Flute/susvib'], pan=-0.1, width=0.5),
    'woods.flute.stac': dict(_SHORT, groups=[_WW + 'Flute/stac'], pan=-0.1, width=0.5, bus='woods'),
    'woods.piccolo.sus': dict(_SUS_WW, groups=[_WW + 'Piccolo/Sus'], pan=-0.15, width=0.5),
    'woods.piccolo.stac': dict(_SHORT, groups=[_WW + 'Piccolo/Stac'], pan=-0.15, width=0.5, bus='woods'),
    'woods.oboe.sus': dict(_SUS_WW, groups=[_WW + 'Oboe/Sus'], pan=0.08, width=0.5),
    'woods.oboe.vib': dict(_SUS_WW, groups=[_WW + 'Oboe/Vib'], pan=0.08, width=0.5),
    'woods.oboe.stac': dict(_SHORT, groups=[_WW + 'Oboe/Stacc'], pan=0.08, width=0.5, bus='woods'),
    'woods.clarinet.sus': dict(_SUS_WW, groups=[_WW + 'Clarinet/susLong'], pan=-0.05, width=0.5),
    'woods.clarinet.stac': dict(_SHORT, groups=[_WW + 'Clarinet/stac'], pan=-0.05, width=0.5, bus='woods'),
    'woods.bassoon.sus': dict(_SUS_WW, groups=[_WW + 'Bassoon/sus'], pan=0.15, width=0.5),
    'woods.bassoon.vib': dict(_SUS_WW, groups=[_WW + 'Bassoon/vib'], pan=0.15, width=0.5),
    'woods.bassoon.stac': dict(_SHORT, groups=[_WW + 'Bassoon/stac'], pan=0.15, width=0.5, bus='woods'),
    # ---------------------------------------------------------------- keys
    'keys.piano': dict(_SHORT, groups=[VC + 'Chordophones/Zithers/Grand Piano, Steinway B/Sus'], pan=0.0, width=0.9,
                       bus='keys', vel_k=40, norm_note=0.3),
    'keys.piano.kawai': dict(_SHORT, groups=[VC + 'Chordophones/Zithers/Grand Piano, Kawai/Sustains'], pan=0.0,
                             width=0.9, bus='keys', vel_k=40, norm_note=0.3),
    'keys.piano.upright': dict(_SHORT, groups=[V2 + 'Keys/Upright Nr1'], pan=0.0, width=0.8, bus='keys', vel_k=40),
    'keys.organ': dict(_SUS_WW, groups=[VC + 'Aerophones/Edge-blown Aerophones/Pipe Organ/Loud'], pan=0.0, width=1.0,
                       bus='keys', legato=False, release=0.6, xfade=0.0),
    'keys.organ.pedal': dict(_SUS_WW, groups=[VC + 'Aerophones/Edge-blown Aerophones/Pipe Organ/Loud Pedal'], pan=0.0,
                             width=1.0, bus='keys', legato=False, release=0.8, xfade=0.0),
    # ---------------------------------------------------------------- pitched percussion
    # every Timpani 2 drum (several have split heads -> ambiguous / out-of-tune pitch at some layers)
    'perc.timpani.all': dict(_PERC, groups=[_MEM + 'Timpani 2/Hit::Timpani_Hit'], pan=0.0, width=0.8, min_conf=0.6,
                             norm_note=0.5, max_shift=4),
    # QA (fix_tuning.py / score/qa_tuning.py): only the drums whose (1,1) mode is one clean peak (no
    # split-head doublet within 1.8 st stronger than -11 dB on any layer; 2A, 6A, 8C have equal-level
    # doublets 40-45 cents apart); D2 comes from drum 1C (E2) shifted -2 st, A2 from 2B, D3 from 3C.
    'perc.timpani': dict(_PERC, groups=[_MEM + 'Timpani 2/Hit::Timpani_Hit', _MEM + 'Timpani 1/Hit::Timpani_Hit'],
                               drums=['1C', '2B', '3A', '3B', '3C', '4A', '1', '2', '3'],
                               pan=0.0, width=0.8, norm_note=0.5, max_shift=4),
    'perc.timpani.vsco': dict(_PERC, groups=[_MEM + 'Timpani 1/Hit::Timpani_Hit'], pan=0.0, width=0.8, norm_note=0.5, max_shift=5),
    'perc.timpani.roll': dict(_SUS_BR, groups=[_MEM + 'Timpani 1/Roll::Timpani_Roll'], pan=0.0, width=0.8, legato=False,
                              release=0.6, bus='perc', xfade=0.0, vel_k=36),
    'perc.tubular_bells': dict(_PERC, groups=[_IDI + 'Tubular Bells 2'], pan=0.25, width=0.6, norm_note=0.5, max_shift=5),
    'perc.chimes': dict(_PERC, groups=[_IDI + 'Tubular Bells 1'], pan=0.25, width=0.6, norm_note=0.5, max_shift=5),
    'perc.glock': dict(_PERC, groups=[_IDI + 'Glockenspiel'], pan=-0.2, width=0.5, norm_note=0.5, max_shift=5),
    'perc.xylo': dict(_PERC, groups=[_IDI + 'Xylophone/Hard Mallets'], pan=-0.15, width=0.5, norm_note=0.5, max_shift=5),
    'perc.marimba': dict(_PERC, groups=[_IDI + 'Marimba'], pan=0.1, width=0.6, norm_note=0.5, max_shift=5),
    'perc.vibes': dict(_PERC, groups=[_IDI + 'Vibraphone/Hard Mallets'], pan=0.1, width=0.6, norm_note=0.5, max_shift=5),
    'perc.vibes.bowed': dict(_PERC, groups=[_IDI + 'Vibraphone/Bowed'], pan=0.1, width=0.6, norm_note=0.5, max_shift=5),
    # ---------------------------------------------------------------- trailer drums (unpitched)
    'perc.bass_drum': dict(_PERC, groups=[V2 + 'Percussion::BDrumNewhit'], pan=0.0, width=0.9),
    'perc.bass_drum.vcsl': dict(_PERC, groups=[_MEM + 'Bass Drum 1::BDrumNew_hit'], pan=0.0, width=0.9),
    'perc.bass_drum.b': dict(_PERC, groups=[_MEM + 'Bass Drum 2::bassdrum_hit'], pan=0.0, width=0.9),
    'perc.bass_drum.legacy': dict(_PERC, groups=[_MEM + 'Bass Drum 3 - Legacy::bdrum'], pan=0.0, width=0.9),
    'perc.bass_drum.muted': dict(_PERC, groups=[_MEM + 'Bass Drum 3 - Legacy::bdrum_muted'], pan=0.0, width=0.9),
    'perc.bass_drum.roll': dict(_SUS_BR, groups=[_MEM + 'Bass Drum 2::bassdrum_roll'], pan=0.0, width=0.9,
                                legato=False, release=0.8, bus='perc', xfade=0.0, vel_k=36),
    'perc.giant_drum': dict(_PERC, groups=[_V1P + 'drums/other/ethnic/giant/mallet::EthnicLargeMallet_hit'], pan=0.0,
                            width=0.9),
    'perc.giant_drum.hand': dict(_PERC, groups=[_V1P + 'drums/other/ethnic/giant/hand::EthnicLargeHand_hit'], pan=0.0,
                                 width=0.9),
    'perc.giant_drum.sticks': dict(_PERC, groups=[_V1P + 'drums/other/ethnic/giant/sticks::EthnicLargeSticks_hit'],
                                   pan=0.0, width=0.9),
    'perc.giant_drum.rim': dict(_PERC, groups=[_V1P + 'drums/other/ethnic/giant::EthnicLargeStick_rimshot'], pan=0.0,
                                width=0.9),
    'perc.toms.low': dict(_PERC, groups=[_MEM + 'Tom 2/Mallet::TomL_HitM'], pan=0.2, width=0.8),
    'perc.toms.high': dict(_PERC, groups=[_MEM + 'Tom 1/Mallet::TomH_HitM'], pan=-0.2, width=0.8),
    'perc.toms.low.stick': dict(_PERC, groups=[_MEM + 'Tom 2/Stick::TomL_HitS'], pan=0.2, width=0.8),
    'perc.toms.high.stick': dict(_PERC, groups=[_MEM + 'Tom 1/Stick::TomH_HitS'], pan=-0.2, width=0.8),
    'perc.toms.low.roll': dict(_SUS_BR, groups=[_MEM + 'Tom 2/Mallet::TomL_RollM'], pan=0.2, width=0.8, legato=False,
                               release=0.4, bus='perc', xfade=0.0, vel_k=36),
    'perc.tenor_drum.low': dict(_PERC, groups=[_MEM + 'Legacy Toms/tenor_lower::tenor'], pan=0.25, width=0.8),
    'perc.tenor_drum.high': dict(_PERC, groups=[_MEM + 'Legacy Toms/tenor_higher::tenorH'], pan=-0.25, width=0.8),
    'perc.frame_drum': dict(_PERC, groups=[_MEM + 'Frame Drum::HDrumL_Hit'], pan=-0.3, width=0.7),
    'perc.frame_drum.small': dict(_PERC, groups=[_MEM + 'Frame Drum::HDrumS_Hit'], pan=0.3, width=0.7),
    'perc.ethnic_drum.low': dict(_PERC, groups=[_V1P + 'drums/other/ethnic/congo/open::ethnicLowOpen_hit'], pan=0.3,
                                 width=0.7),
    'perc.snare': dict(_PERC, groups=[_MEM + 'Snare Drum, Modern 1::Snare2_HitSN'], pan=-0.1, width=0.6),
    'perc.snare.nosnare': dict(_PERC, groups=[_MEM + 'Snare Drum, Modern 1::Snare2_HitNS'], pan=-0.1, width=0.6),
    'perc.snare.rimshot': dict(_PERC, groups=[_MEM + 'Snare Drum, Modern 3::Snare4_rimshot'], pan=-0.1, width=0.6),
    'perc.snare.roll': dict(_SUS_BR, groups=[_MEM + 'Snare Drum, Modern 1::Snare2_rollSN'], pan=-0.1, width=0.6,
                            legato=False, release=0.3, bus='perc', xfade=0.0, vel_k=36),
    'perc.snare.rope': dict(_PERC, groups=[_MEM + 'Snare Drum, Rope Tension/Hi::RopeSnare_hi_sn'], pan=-0.15, width=0.6),
    'perc.snare.rope.low': dict(_PERC, groups=[_MEM + 'Snare Drum, Rope Tension/Low::RopeSnare_low_sn'], pan=-0.15,
                                width=0.6),
    'perc.claves': dict(_PERC, groups=[_IDI + 'Claves/Legacy::claves'], pan=0.0, width=0.0, align_db=-6, align_max=0.01),
    'perc.woodblock': dict(_PERC, groups=[_IDI + 'Woodblock::wood_click'], pan=0.0, width=0.0, align_db=-6,
                           align_max=0.01),
    'perc.taiko_rim': dict(_PERC, groups=[_V1P + 'drums/other/ethnic/giant::EthnicLargeStick_rimshot'], pan=0.0,
                           width=0.8),
    # ---------------------------------------------------------------- metals
    'perc.cymbal.crash': dict(_PERC, align_db=-20, groups=[_IDI + 'Clash Cymbals 1::cymbal_crash1'], pan=0.2, width=1.0),
    'perc.cymbal.crash2': dict(_PERC, align_db=-20, groups=[_IDI + 'Clash Cymbals 2::cymbal_crash2'], pan=0.2, width=1.0),
    'perc.cymbal.crash3': dict(_PERC, align_db=-20, groups=[V2 + 'Percussion::cymbal-crash1'], pan=0.2, width=1.0),
    'perc.cymbal.sus': dict(_PERC, groups=[_IDI + 'Suspended Cymbal 1::susCymb1_hit'], pan=0.2, width=1.0),
    'perc.cymbal.sus2': dict(_PERC, groups=[_IDI + 'Suspended Cymbal 2::susCymb2_hit'], pan=0.2, width=1.0),
    'perc.cymbal.roll': dict(_SUS_BR, groups=[_IDI + 'Suspended Cymbal 1::susCymb1_roll_nloop'], pan=0.2, width=1.0,
                             legato=False, release=1.2, bus='perc', xfade=0.0, vel_k=36),
    'perc.cymbal.swell': dict(_PERC, kind='swell', pan=0.2, width=1.0, groups=[
        _IDI + 'Suspended Cymbal 1::susCymb1_cresc_1.5s', _IDI + 'Suspended Cymbal 1::susCymb1_cresc_2s',
        _IDI + 'Suspended Cymbal 1::susCymb1_cresc_4s', _IDI + 'Suspended Cymbal 1::susCymb1_cresc_7.5s',
        _IDI + 'Suspended Cymbal 2::susCymb2_cresc_2.5s2', _IDI + 'Suspended Cymbal 2::susCymb2_cresc_4s',
        _IDI + 'Suspended Cymbal 2::susCymb2_cresc_7s',
        V2 + 'Percussion::susCymb1-cresc-Short', V2 + 'Percussion::susCymb1-cresc-Median',
        V2 + 'Percussion::susCymb1-cresc-Long']),
    'perc.bass_drum.swell': dict(_PERC, kind='swell', pan=0.0, width=0.9, groups=[
        _MEM + 'Bass Drum 2::bassdrum_cresc', _MEM + 'Bass Drum 2::bassdrum_cresc_short']),
    'perc.gong': dict(_PERC, groups=[_V1P + 'varMetal/Gong::gong_hit'], pan=-0.3, width=1.0),
    'perc.gong.hard': dict(_PERC, groups=[_V1P + 'varMetal/Gong::gong_hit_hard'], pan=-0.3, width=1.0),
    'perc.gong.b': dict(_PERC, groups=[V2 + 'Percussion::gongHit'], pan=-0.3, width=1.0),
    'perc.gong.c': dict(_PERC, groups=[_IDI + 'Gong 1::gong'], pan=-0.3, width=1.0),
    'perc.gong.roll': dict(_SUS_BR, groups=[_V1P + 'varMetal/Gong::gong_roll_long'], pan=-0.3, width=1.0, legato=False,
                           release=2.0, bus='perc', xfade=0.0, vel_k=36),
    'perc.gong.scrape': dict(_PERC, groups=[_V1P + 'varMetal/Gong::gong_scrape'], pan=-0.3, width=1.0),
    'perc.anvil': dict(_PERC, groups=[V2 + 'Percussion::Anvil_Hit1'], pan=0.25, width=0.5),
    'perc.brake_drum': dict(_PERC, groups=[V2 + 'Percussion::BrakeDrum1_Hammer'], pan=0.25, width=0.5),
    'perc.triangle': dict(_PERC, groups=[V2 + 'Percussion::Triangle6-Hit'], pan=0.3, width=0.5),
    # ---------------------------------------------------------------- reversed one-shots (risers that land on t+dur)
    'fx.reverse_cymbal': dict(_PERC, kind='reverse', groups=[_IDI + 'Clash Cymbals 1::cymbal_crash1'], pan=0.0,
                              width=1.0, bus='fx'),
    'fx.reverse_gong': dict(_PERC, kind='reverse', groups=[_V1P + 'varMetal/Gong::gong_hit'], pan=0.0, width=1.0,
                            bus='fx'),
    'fx.reverse_sus_cymbal': dict(_PERC, kind='reverse', groups=[_IDI + 'Suspended Cymbal 1::susCymb1_hit'], pan=0.0,
                                  width=1.0, bus='fx'),
}

_DEFAULTS = dict(kind='short', pan=0.0, width=1.0, release=0.25, legato=False, legato_xf=0.1, legato_skip=0.1,
                 xfade=0.0, vel_k=32, gain_db=0.0, align_db=-12, align_max=0.05, max_shift=7, norm_note=0.5,
                 unison=None, bus=None, min_conf=0.0, range_ext=3, drums=None)


# ============================================================================ data classes
@dataclass
class Note:
    inst: str
    t: float
    dur: float = 0.5
    pitch: object = None
    vel: float = 100
    pan: float = None
    gain_db: float = 0.0
    dyn: list = None
    attack: float = None
    release: float = None
    offset: float = 0.0
    legato: bool = None
    voice: object = None
    bus: str = None
    tune: float = 0.0
    width: float = None
    choke: bool = False


@dataclass
class Humanize:
    time_ms: float = 6.0      # timing std-dev
    vel: float = 4.0          # velocity std-dev
    cents: float = 2.0        # tuning std-dev (sustained instruments only)
    seed: int = 1


@dataclass
class _Smp:
    path: str
    pitch: float      # actual sounding pitch (MIDI float)
    key: str          # sampled-note key (round robins share it)
    layer: int
    rr: int
    loud: float
    onset: float
    end: float
    sr: int
    fix: float = 0.0  # per-sample tuning correction in cents (catalog `tune_fix_cents`, see fix_tuning.py)


class Instrument:
    """A playable instrument built from one or more catalog groups."""

    def __init__(self, iid, spec, catalog):
        self.id = iid
        p = dict(_DEFAULTS)
        p.update(spec)
        self.p = p
        self.kind = p['kind']
        self.groups = list(p['groups'])
        fam = iid.split('.')[0]
        self.bus = p['bus'] or {'woods': 'woods', 'fx': 'fx'}.get(fam, fam)
        missing = [g for g in self.groups if g not in catalog['groups']]
        if missing:
            raise KeyError(f'{iid}: catalog groups missing: {missing}')
        smps = []
        self.pitched = False
        for gi, g in enumerate(self.groups):
            grp = catalog['groups'][g]
            self.pitched |= bool(grp.get('pitched'))
            for s in grp['samples']:
                if 'error' in s or s.get('len_s', 0) <= 0.02 or s.get('exclude'):
                    continue
                if p['min_conf'] and s.get('pitch_confidence', 1.0) < p['min_conf']:
                    continue
                if p['drums'] and s.get('drum') not in p['drums']:
                    continue
                pitch = s.get('midi_float', s.get('midi', 60))
                pitch = 60.0 if pitch is None else float(pitch)
                key = f"{gi}:{s.get('drum', '')}:{pitch:.2f}"
                smps.append(_Smp(s['path'], pitch, key, s.get('vel_layer', 0), s.get('rr', 1),
                                 s.get('loud_db', -30.0), s.get('onset_s', 0.0), s.get('end_s', s['len_s']),
                                 s.get('sr', 44100), float(s.get('tune_fix_cents', 0.0))))
        if not smps:
            raise ValueError(f'{iid}: no usable samples')
        if self.kind == 'swell' or (len(self.groups) > 1 and not self.pitched):
            # each group is a variant (e.g. swells of different lengths): one layer of alternatives
            for s in smps:
                s.layer = 0
        # re-index layers densely
        layers = sorted(set(s.layer for s in smps))
        for s in smps:
            s.layer = layers.index(s.layer)
        self.n_layers = len(layers)
        self.samples = smps
        # layer -> sorted list of (pitch, key, [samples in rr order])
        self.table = []
        for k in range(self.n_layers):
            d = defaultdict(list)
            for s in smps:
                if s.layer == k:
                    d[s.key].append(s)
            rows = [(v[0].pitch, key, sorted(v, key=lambda s: s.rr)) for key, v in d.items()]
            rows.sort(key=lambda r: r[0])
            self.table.append(rows)
        self.layer_level = [float(np.median([s.loud for s in smps if s.layer == k])) for k in range(self.n_layers)]
        self.max_rr = max(len(r[2]) for rows in self.table for r in rows)
        ps = [s.pitch for s in smps]
        self.sampled = (min(ps), max(ps))
        if self.pitched:
            self.range = (math.floor(min(ps)) - p['range_ext'], math.ceil(max(ps)) + p['range_ext'])
        else:
            self.range = None

    def info(self):
        d = dict(id=self.id, kind=self.kind, pitched=self.pitched, layers=self.n_layers, max_rr=self.max_rr,
                 n_samples=len(self.samples), pan=self.p['pan'], bus=self.bus,
                 unison=len(self.p['unison']) if self.p['unison'] else 1)
        if self.pitched:
            d['sampled'] = (midi_name(self.sampled[0]), midi_name(self.sampled[1]))
            d['range'] = (midi_name(self.range[0]), midi_name(self.range[1]))
            d['notes'] = sorted(set(round(s.pitch, 2) for s in self.samples))
        return d

    def __repr__(self):
        i = self.info()
        r = f" {i['sampled'][0]}-{i['sampled'][1]}" if self.pitched else ''
        return f"<Instrument {self.id} {self.kind}{r} layers={self.n_layers} rr={self.max_rr}>"


@dataclass
class _Ev:
    n: Note
    idx: int
    inst: Instrument
    t: float
    dur: float
    pitch: float
    vel: float
    tune: float
    prev: object = None
    next: object = None


class _Buf:
    __slots__ = ('a', 'env', 'nbytes', 'align', 'peak_i')

    def __init__(self, a):
        self.a = a
        self.nbytes = a.nbytes
        self.env = None
        self.align = {}
        self.peak_i = None


# ============================================================================ engine
class Sampler:
    def __init__(self, catalog_path=DEFAULT_CATALOG, cache_dir=None, cache_bytes=4 << 30, threads=2, verbose=False):
        with open(catalog_path) as f:
            self.catalog = json.load(f)
        self.cache_dir = cache_dir
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
        self.cache_bytes = cache_bytes
        self._cache = OrderedDict()
        self._cache_used = 0
        self._insts = {}
        self._rr = defaultdict(int)
        self.verbose = verbose
        self.threads = max(1, int(threads))
        self._lock = threading.Lock()
        self.warnings = []
        self.stats = defaultdict(float)

    # ------------------------------------------------------------------ instruments
    def list(self, prefix=''):
        return [k for k in INSTRUMENTS if k.startswith(prefix)]

    def instrument(self, iid):
        if iid not in self._insts:
            if iid not in INSTRUMENTS:
                raise KeyError(f'unknown instrument {iid!r}; see Sampler.list()')
            self._insts[iid] = Instrument(iid, INSTRUMENTS[iid], self.catalog)
        return self._insts[iid]

    def available(self):
        """{id: info or error string} for every registered id."""
        out = {}
        for k in INSTRUMENTS:
            try:
                out[k] = self.instrument(k).info()
            except Exception as e:  # pragma: no cover
                out[k] = f'ERROR {e}'
        return out

    def reset(self):
        """Reset round-robin counters and warnings (cache is kept)."""
        self._rr.clear()
        self.warnings = []

    # ------------------------------------------------------------------ buffers
    def _load(self, smp: _Smp, shift):
        """Decoded sample starting at its onset, pitch-shifted by `shift` semitones, at SR, (2, n)."""
        cents = int(round(shift * 100))
        key = (smp.path, cents)
        with self._lock:
            b = self._cache.get(key)
            if b is not None:
                self._cache.move_to_end(key)
                self.stats['cache_hits'] += 1
                return b
        t0 = time.time()
        a = None
        cp = None
        if self.cache_dir:
            h = hashlib.sha1(f'{smp.path}|{cents}|{SR}'.encode()).hexdigest()[:20]
            cp = os.path.join(self.cache_dir, h + '.npy')
            if os.path.exists(cp):
                a = np.load(cp)
        if a is None:
            x, sr = sf.read(smp.path, dtype='float32', always_2d=True)
            i0 = int(smp.onset * sr)
            i1 = min(len(x), int((smp.end + 0.4) * sr))
            x = x[i0:i1]
            if x.shape[1] == 1:
                x = np.repeat(x, 2, axis=1)
            elif x.shape[1] > 2:
                x = x[:, :2]
            x = np.ascontiguousarray(x.T)
            ratio = SR / (sr * 2.0 ** (cents / 1200.0))  # output samples per input sample
            fr = Fraction(ratio).limit_denominator(1000)
            if fr.numerator != fr.denominator:
                x = resample_poly(x, fr.numerator, fr.denominator, axis=1)
            a = np.ascontiguousarray(x, dtype=np.float32)
            nf = min(a.shape[1], int(0.002 * SR))  # 2 ms fade-in against clicks at the cut point
            if nf > 0:
                a[:, :nf] *= np.linspace(0, 1, nf, dtype=np.float32)
            if cp:
                np.save(cp, a)
            with self._lock:
                self.stats['resamples'] += 1
        b = _Buf(a)
        with self._lock:
            if key in self._cache:
                return self._cache[key]
            self._cache[key] = b
            self._cache_used += b.nbytes
            while self._cache_used > self.cache_bytes and len(self._cache) > 1:
                _, old = self._cache.popitem(last=False)
                self._cache_used -= old.nbytes
            self.stats['load_s'] += time.time() - t0
        return b

    @staticmethod
    def _env(b: _Buf):
        """1 ms-resolution peak envelope (5 ms smoothed); sets b.peak_i (sample index of the maximum)."""
        if b.env is None:
            blk = 48
            nb = max(1, b.a.shape[1] // blk)
            a = b.a[:, :nb * blk] if b.a.shape[1] >= blk else np.pad(b.a, ((0, 0), (0, blk - b.a.shape[1])))
            m = np.abs(a.reshape(2, nb, blk)).max(axis=(0, 2))
            e = np.sqrt(np.maximum(uniform_filter1d(m * m, 5), 0))
            b.env = e
            b.peak_i = int(np.argmax(e)) * blk + blk // 2
        return b.env

    def _align(self, b: _Buf, db, cap):
        k = (db, cap)
        if k not in b.align:
            e = self._env(b)
            thr = e.max() * 10 ** (db / 20)
            i = int(np.argmax(e >= thr)) * 48
            b.align[k] = min(i, int(cap * SR))
        return b.align[k]

    @staticmethod
    def _extend(a, need):
        """Loop-extend a sustained buffer to `need` samples with equal-power crossfades."""
        n = a.shape[1]
        if n >= need:
            return a
        m = np.abs(a).max(axis=0)
        w = int(0.05 * SR)
        env = np.sqrt(np.maximum(uniform_filter1d(m ** 2, w), 0))
        start = max(int(np.argmax(env)), int(0.35 * SR))
        if start >= n - int(0.5 * SR):
            start = n // 3
        lev = np.median(env[start:]) if n > start else env.max()
        above = np.nonzero(env[start:] >= lev * 10 ** (-4 / 20))[0]
        b = start + int(above[-1]) if len(above) else n
        b = min(b, n)
        la = start + int(0.35 * (b - start))
        if b - la < int(0.4 * SR):
            la = max(0, b - int(0.4 * SR))
        seg = a[:, la:b]
        L = seg.shape[1]
        if L < int(0.1 * SR):
            out = np.zeros((2, need), np.float32)
            out[:, :n] = a
            return out
        xf = min(int(0.3 * SR), L // 3)
        th = np.linspace(0, np.pi / 2, xf, dtype=np.float32)
        fo, fi = np.cos(th), np.sin(th)
        res = [a[:, :b - xf]]
        tail = a[:, b - xf:b]
        total = b - xf
        while total < need:
            res.append(tail * fo + seg[:, :xf] * fi)
            res.append(seg[:, xf:L - xf])
            tail = seg[:, L - xf:]
            total += L - xf
        res.append(tail)
        return np.concatenate(res, axis=1)[:, :need]

    # ------------------------------------------------------------------ selection
    def _choose(self, inst: Instrument, layer, pitch, alt=0):
        """Return (row, layer) where row = (pitch, key, [samples]).

        Nearest sampled note in the requested layer (shifting up costs 15% more than shifting
        down).  If that layer has nothing within 3 semitones and another layer is at least 2
        semitones closer, the closest such layer is used instead.  `alt` > 0 picks the alt-th
        nearest note within 4 semitones (used to decorrelate unison voices)."""

        def cost(r):
            d = r[0] - pitch
            return d if d >= 0 else -d * 1.15

        ranked = sorted(inst.table[layer], key=cost)
        best_d = abs(ranked[0][0] - pitch)
        if best_d > 3 and inst.n_layers > 1:
            cands = []
            for k in range(inst.n_layers):
                if k != layer:
                    r2 = min(inst.table[k], key=cost)
                    d2 = abs(r2[0] - pitch)
                    if d2 <= best_d - 2:
                        cands.append((abs(k - layer), d2, k))
            if cands:
                layer = min(cands)[2]
                ranked = sorted(inst.table[layer], key=cost)
        if alt:
            close = [r for r in ranked if abs(r[0] - pitch) <= 4.0]
            if len(close) > 1:
                return close[alt % len(close)], layer
        return ranked[0], layer

    def _layer_weights(self, inst: Instrument, vel):
        n = inst.n_layers
        if n == 1:
            return [(0, 1.0)]
        p = min(max(vel / 127.0 * n - 0.5, 0.0), n - 1.0)
        k0 = int(math.floor(p))
        if k0 >= n - 1:
            return [(n - 1, 1.0)]
        f = p - k0
        z = inst.p['xfade']
        if z <= 0:
            return [(k0 + (1 if f >= 0.5 else 0), 1.0)]
        f2 = min(max((f - 0.5) / z + 0.5, 0.0), 1.0)
        out = []
        if f2 < 1:
            out.append((k0, math.cos(f2 * math.pi / 2)))
        if f2 > 0:
            out.append((k0 + 1, math.sin(f2 * math.pi / 2)))
        return out

    def _layer_weights_vec(self, inst: Instrument, v):
        """Vectorised _layer_weights: (n_layers, len(v)) weight matrix."""
        n = inst.n_layers
        W = np.zeros((n, len(v)))
        if n == 1:
            W[0] = 1.0
            return W
        p = np.clip(v / 127.0 * n - 0.5, 0.0, n - 1.0)
        k0 = np.minimum(np.floor(p).astype(int), n - 2)
        f = p - k0
        z = inst.p['xfade']
        f2 = np.clip((f - 0.5) / z + 0.5, 0.0, 1.0) if z > 0 else (f >= 0.5).astype(float)
        idx = np.arange(len(v))
        np.add.at(W, (k0, idx), np.cos(f2 * np.pi / 2))
        np.add.at(W, (k0 + 1, idx), np.sin(f2 * np.pi / 2))
        return W

    def _level_db(self, inst: Instrument, vel):
        v = min(max(float(vel), 1.0), 127.0)
        return TARGET_LUFS + inst.p['gain_db'] + inst.p['vel_k'] * math.log10(v / 127.0)

    # ------------------------------------------------------------------ preparation
    def _prepare(self, events, humanize):
        evs = []
        if humanize is True:
            humanize = Humanize()
        for i, n in enumerate(events):
            inst = self.instrument(n.inst)
            pitch = note_to_midi(n.pitch)
            if pitch is None:
                if inst.pitched and inst.kind not in ('swell', 'reverse'):
                    raise ValueError(f'{n.inst}: pitch required')
                pitch = 60.0 if not inst.pitched else None
            t, vel, tune = float(n.t), float(n.vel), float(n.tune)
            if humanize:
                rng = np.random.default_rng([int(humanize.seed) & 0xffffffff, i])
                z = np.clip(rng.standard_normal(3), -2.2, 2.2)
                t += z[0] * humanize.time_ms / 1000.0
                vel = min(127.0, max(1.0, vel + z[1] * humanize.vel))
                if inst.kind == 'sustain' and humanize.cents:
                    # quantised to 3-cent steps so humanised notes still share cached buffers
                    tune += 3.0 * round(z[2] * humanize.cents / 3.0)
            if inst.range and pitch is not None and not (inst.range[0] <= pitch <= inst.range[1]):
                self.warnings.append(f'{n.inst}: pitch {midi_name(pitch)} outside {midi_name(inst.range[0])}-'
                                     f'{midi_name(inst.range[1])}')
            evs.append(_Ev(n, i, inst, t, float(n.dur), pitch, vel, tune))
        self._link_legato(evs)
        evs.sort(key=lambda e: (e.t, e.idx))
        return evs

    @staticmethod
    def _link_legato(evs, gap=0.06):
        groups = defaultdict(list)
        for e in evs:
            if e.inst.kind == 'sustain' and e.inst.p['legato'] and e.n.legato is not False:
                groups[e.inst.id].append(e)
        for iid, es in groups.items():
            es.sort(key=lambda e: (e.n.t, e.idx))
            for e in es:
                best = None
                for p in es:
                    if p is e or p.next is not None or p.n.t >= e.n.t:
                        continue
                    if e.n.voice is not None or p.n.voice is not None:
                        if e.n.voice != p.n.voice:
                            continue
                    if abs(p.n.t + p.dur - e.n.t) > gap:
                        continue
                    if p.pitch is None or e.pitch is None or abs(p.pitch - e.pitch) < 0.5:
                        continue
                    c = abs(p.pitch - e.pitch)
                    if best is None or c < best[0]:
                        best = (c, p)
                if best:
                    best[1].next = e
                    e.prev = best[1]

    # ------------------------------------------------------------------ render
    def render(self, events, seconds=None, humanize=None, stems=False):
        """Render events -> float32 (2, n) at 48 kHz (or {bus: array} when stems=True)."""
        t0 = time.time()
        evs = self._prepare(events, humanize)
        if seconds is None:
            seconds = max([e.t + e.dur for e in evs] + [0]) + 4.0
        N = int(round(seconds * SR))
        buses = {}
        win_end = -1e9
        for i, e in enumerate(evs):
            if self.threads > 1 and e.t >= win_end:
                # decode/resample the next ~8 s of events in parallel (bounded working set)
                win_end = e.t + 8.0
                self._prefetch([x for x in evs[i:] if x.t < win_end])
            name = (e.n.bus or e.inst.bus) if stems else 'mix'
            out = buses.get(name)
            if out is None:
                out = buses[name] = np.zeros((2, N), np.float32)
            self._render_event(e, out)
        self.stats['notes'] += len(evs)
        self.stats['render_s'] += time.time() - t0
        if stems:
            return buses
        return buses.get('mix', np.zeros((2, N), np.float32))

    def _render_event(self, e: _Ev, out):
        inst = e.inst
        voices = inst.p['unison'] or [(0, 0, 0.0, 0, 0)]
        vgain = -10 * math.log10(len(voices))
        for vi, (det, dly, pdo, gdb, alt) in enumerate(voices):
            self._render_voice(e, out, det, dly / 1000.0, pdo, gdb + vgain, alt, vi)

    def _select(self, e: _Ev, detune, alt, vi):
        """Choose (layer, used layer, sample, shift, level correction) for one voice of an event.
        Advances the round-robin counters (only for the main unison voice)."""
        inst, n = e.inst, e.n
        P = inst.p
        kind = inst.kind
        pitch = e.pitch
        if n.dyn:
            dvs = np.array([float(b) for _, b in n.dyn])
            vs = np.linspace(float(dvs.min()), float(dvs.max()), 24)
            layers = sorted(set(k for v in vs for k, _ in self._layer_weights(inst, v)))
        else:
            layers = [k for k, _ in self._layer_weights(inst, e.vel)]
        picks = []
        for k in layers:
            if kind == 'swell':
                row, kk = self._pick_variant(inst, n), 0
            else:
                row, kk = self._choose(inst, k, pitch if pitch is not None else 60.0, alt)
            rrkey = (inst.id, kk, row[1])
            cnt = self._rr[rrkey]
            if vi == 0:
                self._rr[rrkey] = cnt + 1
            smp = row[2][(cnt + alt) % len(row[2])]
            shift = 0.0
            if pitch is not None and inst.pitched and kind != 'swell':
                shift = pitch - smp.pitch
            elif not inst.pitched and pitch is not None:
                shift = pitch - 60.0
            if inst.pitched and kind != 'swell':
                shift += smp.fix / 100.0  # measured per-sample detuning (fix_tuning.py)
            shift += (e.tune + detune) / 100.0
            if abs(shift) > P['max_shift'] + 0.01:
                w = f'{inst.id}: shifting {shift:+.1f} st for {midi_name(pitch) if pitch else "-"}'
                if w not in self.warnings:
                    self.warnings.append(w)
            corr = float(np.clip(P['norm_note'] * (inst.layer_level[kk] - smp.loud), -6, 6))
            picks.append((k, kk, smp, shift, corr))
        return picks

    def _prefetch(self, evs):
        """Decode + resample every buffer the render will need, in parallel threads."""
        snap = dict(self._rr)
        need = {}
        for e in evs:
            voices = e.inst.p['unison'] or [(0, 0, 0.0, 0, 0)]
            for vi, (det, dly, pdo, gdb, alt) in enumerate(voices):
                for (_, _, smp, shift, _) in self._select(e, det, alt, vi):
                    key = (smp.path, int(round(shift * 100)))
                    if key not in self._cache:
                        need[key] = (smp, shift)
        self._rr.clear()
        self._rr.update(snap)
        if need:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=self.threads) as ex:
                list(ex.map(lambda a: self._load(*a), need.values()))

    def _render_voice(self, e: _Ev, out, detune, delay, pan_off, gain_db, alt, vi):
        inst, n = e.inst, e.n
        P = inst.p
        kind = inst.kind
        if n.dyn:
            dts = np.array([float(a) for a, _ in n.dyn])
            dvs = np.array([float(b) for _, b in n.dyn])
        picks = [(k, kk, smp, self._load(smp, shift), corr) for (k, kk, smp, shift, corr) in
                 self._select(e, detune, alt, vi)]
        main = picks[0][3]
        # ---- timeline
        t_mus = e.t + delay
        fade_in = float(n.attack or 0.0)
        src0 = int(round(max(0.0, n.offset) * SR))
        rel_curve = 'cos'
        if kind == 'sustain':
            if e.prev is not None:
                X = P['legato_xf']
                start = t_mus - X / 2
                src0 += int(P['legato_skip'] * SR)
                fade_in = max(fade_in, X)
                fi_curve = 'ep'
            else:
                start = t_mus - self._align(main, P['align_db'], P['align_max']) / SR
                fi_curve = 'lin'
            if e.next is not None:
                X = P['legato_xf']
                off = e.next.t + delay - X / 2
                rel = X
                rel_curve = 'ep'
            else:
                off = t_mus + e.dur
                rel = n.release if n.release is not None else P['release']
            length = int((off - start + rel) * SR)
            off_i = int((off - start) * SR)
        elif kind == 'swell':
            self._env(main)
            pk = main.peak_i
            climax = t_mus + e.dur
            start = climax - pk / SR
            if start < t_mus:
                src0 += int((t_mus - start) * SR)
                start = t_mus
                fade_in = max(fade_in, min(0.4, 0.3 * e.dur))
            fi_curve = 'lin'
            length = main.a.shape[1] - src0
            off_i, rel = None, 0.0
            if n.choke:
                off_i = int((climax - start) * SR) + int(0.05 * SR)
                rel = n.release if n.release is not None else 0.5
                length = off_i + int(rel * SR)
        elif kind == 'reverse':
            climax = t_mus + e.dur
            Lr = min(main.a.shape[1], int(e.dur * SR))
            start = climax - Lr / SR
            fade_in = max(fade_in, min(0.3, 0.25 * e.dur))
            fi_curve = 'lin'
            length = Lr
            off_i, rel = None, 0.0
        else:  # short / perc one-shots
            start = t_mus - self._align(main, P['align_db'], P['align_max']) / SR
            fi_curve = 'lin'
            length = main.a.shape[1] - src0
            off_i, rel = None, 0.0
            if n.choke:
                off_i = int((t_mus + e.dur - start) * SR)
                rel = n.release if n.release is not None else 0.08
                length = min(length, off_i + int(rel * SR))
        if length <= 0:
            return
        # ---- per-layer gain (possibly time-varying)
        seg = np.zeros((2, length), np.float32)
        if n.dyn:
            ctl = 64
            nc = length // ctl + 2
            tc = (np.arange(nc) * ctl) / SR + (start - e.t)  # time relative to note start
            vc = np.clip(np.interp(tc, dts, dvs), 1.0, 127.0)
            lvl_db = TARGET_LUFS + P['gain_db'] + P['vel_k'] * np.log10(vc / 127.0)
            wmat = self._layer_weights_vec(inst, vc)
        for (k, kk, smp, b, corr) in picks:
            if kind == 'reverse':
                src = b.a[:, :length][:, ::-1]
                take = src.shape[1]
                src = np.ascontiguousarray(src)
                if take < length:
                    pad = np.zeros((2, length), np.float32)
                    pad[:, length - take:] = src
                    src = pad
            else:
                a = b.a
                if kind == 'sustain' and src0 + length > a.shape[1]:
                    a = self._extend(a, src0 + length)
                src = a[:, src0:src0 + length]
            if src.shape[1] == 0:
                continue
            m = src.shape[1]
            if n.dyn:
                g_db = lvl_db - inst.layer_level[kk] + corr + gain_db + n.gain_db
                g = (10 ** (g_db / 20)) * wmat[k]
                gc = np.interp(np.arange(m), np.arange(nc) * ctl, g).astype(np.float32)
                seg[:, :m] += src * gc
            else:
                w = dict(self._layer_weights(inst, e.vel)).get(k, 0.0)
                if w <= 0:
                    continue
                g_db = self._level_db(inst, e.vel) - inst.layer_level[kk] + corr + gain_db + n.gain_db
                seg[:, :m] += src * np.float32(w * 10 ** (g_db / 20))
        # ---- envelope: fade-in, release, end fade
        if fade_in > 0:
            nf = min(length, int(fade_in * SR))
            r = np.linspace(0, 1, nf, dtype=np.float32)
            seg[:, :nf] *= (np.sin(r * np.pi / 2) if fi_curve == 'ep' else r * r * (3 - 2 * r))
        if off_i is not None and kind != 'reverse':
            nr = max(1, int(rel * SR))
            a0 = max(0, min(off_i, length))
            a1 = min(length, a0 + nr)
            if a1 > a0:
                r = np.linspace(0, 1, nr, dtype=np.float32)[:a1 - a0]
                if rel_curve == 'ep':
                    seg[:, a0:a1] *= np.cos(r * np.pi / 2)
                else:
                    seg[:, a0:a1] *= 0.5 * (1 + np.cos(r * np.pi))
            seg[:, a1:] = 0
        else:
            nr = min(length, int(0.01 * SR))
            seg[:, length - nr:] *= np.linspace(1, 0, nr, dtype=np.float32)
        # ---- stereo placement: width (M/S) + constant-power balance
        pan = (n.pan if n.pan is not None else P['pan']) + pan_off
        pan = min(max(pan, -1.0), 1.0)
        width = n.width if n.width is not None else P['width']
        if width != 1.0:
            mid = 0.5 * (seg[0] + seg[1])
            side = 0.5 * (seg[0] - seg[1]) * np.float32(width)
            seg = np.stack([mid + side, mid - side])
        th = (pan + 1) * math.pi / 4
        seg[0] *= np.float32(math.cos(th) * math.sqrt(2))
        seg[1] *= np.float32(math.sin(th) * math.sqrt(2))
        # ---- mix
        i0 = int(round(start * SR))
        N = out.shape[1]
        s0, d0 = 0, i0
        if d0 < 0:
            s0, d0 = -d0, 0
        d1 = min(N, i0 + length)
        if d1 > d0:
            out[:, d0:d1] += seg[:, s0:s0 + (d1 - d0)]

    def _pick_variant(self, inst: Instrument, n: Note):
        """Swell instruments: pick the variant whose crescendo length best fits n.dur (round-robin among
        equally good ones); the sample is then placed so that its peak lands on t + dur."""
        rows = inst.table[0]
        if inst.kind == 'swell':
            def fit(r):
                s = r[2][0]
                L = self._swell_len(s)
                return (0 if L >= n.dur else 1, abs(L - n.dur))
            ranked = sorted(rows, key=fit)
            best = fit(ranked[0])
            ties = [r for r in ranked if abs(fit(r)[1] - best[1]) < 0.35 and fit(r)[0] == best[0]]
            cnt = self._rr[(inst.id, 'var')]
            self._rr[(inst.id, 'var')] = cnt + 1
            return ties[cnt % len(ties)]
        return rows[0]

    def _swell_len(self, s: _Smp):
        b = self._load(s, 0.0)
        self._env(b)
        return b.peak_i / SR

    # ------------------------------------------------------------------ io
    @staticmethod
    def write(path, buf, subtype='PCM_24'):
        sf.write(path, np.asarray(buf, np.float32).T, SR, subtype=subtype)


# ============================================================================ fx helpers
def fx_hall(buf, rt60=2.6, predelay=0.022, wet=0.25, dry=1.0, seed=3, hp=120.0, lp=9000.0):
    """Synthetic stereo hall: decorrelated noise IR with frequency-dependent decay + early reflections."""
    rng = np.random.default_rng(seed)
    L = int(SR * min(rt60 * 1.3, 6.0))
    t = np.arange(L) / SR
    ir = np.zeros((2, L), np.float32)
    bands = [(None, 400, 1.15), (400, 2500, 1.0), (2500, None, 0.55)]
    for lo, hi, k in bands:
        for c in range(2):
            nz = rng.standard_normal(L)
            if lo and hi:
                sos = butter(2, [lo, hi], 'bandpass', fs=SR, output='sos')
            elif lo:
                sos = butter(2, lo, 'highpass', fs=SR, output='sos')
            else:
                sos = butter(2, hi, 'lowpass', fs=SR, output='sos')
            ir[c] += (sosfilt(sos, nz) * np.exp(-6.9078 * t / (rt60 * k))).astype(np.float32)
    # soft onset of the diffuse tail
    ir *= np.minimum(1.0, t / 0.03).astype(np.float32)
    for _ in range(14):  # early reflections
        d = int(rng.uniform(0.004, 0.075) * SR)
        g = rng.uniform(0.15, 0.5) * math.exp(-d / SR / 0.08)
        ir[rng.integers(0, 2), d] += g
    pd = int(predelay * SR)
    ir = np.concatenate([np.zeros((2, pd), np.float32), ir], axis=1)
    sos = butter(2, [hp, lp], 'bandpass', fs=SR, output='sos')
    ir = sosfilt(sos, ir, axis=1).astype(np.float32)
    ir /= np.sqrt(np.sum(ir ** 2) / 2)
    x = np.asarray(buf, np.float32)
    y = np.stack([fftconvolve(x[0], ir[0])[:x.shape[1]] + 0.15 * fftconvolve(x[1], ir[0])[:x.shape[1]],
                  fftconvolve(x[1], ir[1])[:x.shape[1]] + 0.15 * fftconvolve(x[0], ir[1])[:x.shape[1]]])
    return (dry * x + wet * y).astype(np.float32)


def fx_limit(buf, ceiling_db=-1.0, lookahead=0.005, release=0.12):
    """Look-ahead peak limiter (no overshoot): returns float32 (2, n)."""
    x = np.asarray(buf, np.float32)
    c = 10 ** (ceiling_db / 20)
    la = max(1, int(lookahead * SR))
    pk = maximum_filter1d(np.abs(x).max(axis=0), size=2 * la + 1)
    g = np.minimum(1.0, c / np.maximum(pk, 1e-9))
    # release smoothing (one-pole on the gain, only when gain rises)
    a = math.exp(-1.0 / (release * SR))
    from scipy.signal import lfilter
    gr = 1.0 - g
    # peak-hold style: fast attack (already looked ahead), slow release
    sm = lfilter([1 - a], [1, -a], gr)
    gr = np.maximum(gr, sm)
    g = 1.0 - gr
    g = uniform_filter1d(g, la)
    g = np.minimum(g, c / np.maximum(pk, 1e-9))
    return (x * g.astype(np.float32)).astype(np.float32)


if __name__ == '__main__':
    import sys
    s = Sampler()
    pref = sys.argv[1] if len(sys.argv) > 1 else ''
    for k, v in s.available().items():
        if k.startswith(pref):
            print(k, v if isinstance(v, str) else
                  {kk: v[kk] for kk in ('kind', 'layers', 'max_rr', 'sampled', 'range', 'unison') if kk in v})
