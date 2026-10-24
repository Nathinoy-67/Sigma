"""synth.py -- synthesized layers (sub hits, risers, reverse swells, heartbeat sine) and the
foley of the sound-design notes (typebar strikes, room tones, neon buzz, fizz, glass plunge, ...).

Everything is deterministic (fixed seeds), 48 kHz, returned as float64 (2, n) timeline buffers.
A few foley layers use VCSL percussion recordings (claves escapement tick, bowed brake drum and
guiro creaks, gong for the reverse tail), as the sound-design notes allow.
"""
from __future__ import annotations

import math
import os

import numpy as np
import soundfile as sf
from scipy.signal import butter, resample_poly, sosfilt
from fractions import Fraction

import mixer as X

SR = 48000
VCSL = '/home/user/tools/VCSL'


def T(frame):
    return frame / 24.0


# --------------------------------------------------------------------------- primitives
def place(buf, sig, t, gain=1.0):
    """Add sig ((2, m) or (m,)) into buf at time t (seconds); clipped to the buffer."""
    sig = np.asarray(sig, np.float64)
    if sig.ndim == 1:
        sig = np.stack([sig, sig])
    i0 = int(round(t * SR))
    s0 = 0
    if i0 < 0:
        s0, i0 = -i0, 0
    i1 = min(buf.shape[1], i0 + sig.shape[1] - s0)
    if i1 > i0:
        buf[:, i0:i1] += gain * sig[:, s0:s0 + (i1 - i0)]


def white(n, rng):
    return rng.standard_normal(n)


def pink(n, rng):
    """Pink noise via spectral 1/sqrt(f) shaping."""
    w = rng.standard_normal(n)
    F = np.fft.rfft(w)
    f = np.fft.rfftfreq(n, 1 / SR)
    F[1:] /= np.sqrt(f[1:])
    F[0] = 0
    y = np.fft.irfft(F, n)
    return y / (np.std(y) + 1e-12)


def brown(n, rng):
    y = np.cumsum(rng.standard_normal(n))
    y = X.hp(y, 15.0)
    return y / (np.std(y) + 1e-12)


def env_ar(n, attack, tau, sr=SR):
    t = np.arange(n) / sr
    a = np.minimum(1.0, t / max(attack, 1e-4))
    return a * np.exp(-np.maximum(0, t - attack) / tau)


def sine_glide(f0, f1, dur, glide, phase=0.0):
    """Sine with exponential frequency glide f0 -> f1 over `glide` seconds, then f1."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    k = np.minimum(t / max(glide, 1e-4), 1.0)
    f = f0 * (f1 / f0) ** k
    ph = phase + 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph)


def fade(sig, fin=0.0, fout=0.0):
    sig = np.array(sig, np.float64)
    n = sig.shape[-1]
    if fin > 0:
        k = min(n, int(fin * SR))
        sig[..., :k] *= np.sin(np.linspace(0, np.pi / 2, k)) ** 2
    if fout > 0:
        k = min(n, int(fout * SR))
        sig[..., n - k:] *= np.cos(np.linspace(0, np.pi / 2, k)) ** 2
    return sig


def load(path, semitones=0.0, mono=False):
    """Read a library sample, convert to 48 kHz with a pitch shift (resampling)."""
    x, sr = sf.read(path, always_2d=True, dtype='float64')
    x = x.T
    if x.shape[0] == 1:
        x = np.repeat(x, 2, axis=0)
    ratio = SR / (sr * 2 ** (semitones / 12))
    fr = Fraction(ratio).limit_denominator(1000)
    if fr.numerator != fr.denominator:
        x = resample_poly(x, fr.numerator, fr.denominator, axis=1)
    if mono:
        return x.mean(axis=0)
    return x


def damped(f, tau, dur, sr=SR):
    t = np.arange(int(dur * sr)) / sr
    return np.sin(2 * np.pi * f * t) * np.exp(-t / tau)


def modal(freqs, taus, amps, dur):
    out = 0
    for f, ta, a in zip(freqs, taus, amps):
        out = out + a * damped(f, ta, dur)
    return out


def peak_norm(x, peak_db):
    m = np.abs(x).max()
    return x * (X.db(peak_db) / m) if m > 0 else x


def rms_norm(x, rms_db):
    r = np.sqrt(np.mean(np.asarray(x) ** 2))
    return x * (X.db(rms_db) / r) if r > 0 else x


# --------------------------------------------------------------------------- synth layers
def sub_hit(f0, f1, drop, tail, level_db, attack=0.004, tau=None):
    """Sine sub hit: pitch drop f0 -> f1 over `drop` s, exponential tail of length `tail`."""
    tau = tau or tail / 4.5
    s = sine_glide(f0, f1, tail, drop)
    e = env_ar(len(s), attack, tau)
    e[-int(0.05 * SR):] *= np.linspace(1, 0, int(0.05 * SR))
    sig = s * e
    # a touch of 2nd harmonic so it reads on small speakers (soft saturation)
    sig = np.tanh(1.6 * sig) / np.tanh(1.6)
    return peak_norm(sig, level_db)


def riser(dur, level_db, seed, f_lo=250.0, f_hi=7000.0, saw_from=50.0, saw_to=62.0, curve=2.6):
    """Filtered-noise + rising-saw riser that ENDS (hard) at its last sample."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    u = t / dur
    amp = u ** curve
    # noise through a band-pass sweeping up (block-wise to keep it cheap)
    nz = white(n, rng)
    out_n = np.zeros(n)
    blk = 2400
    for i in range(0, n, blk):
        uc = (i + blk / 2) / n
        fc = f_lo * (f_hi / f_lo) ** (uc ** 1.4)
        lo, hi = fc / 1.6, min(fc * 1.6, 20000)
        seg = nz[max(0, i - 2048):i + blk]
        y = sosfilt(butter(2, [lo, hi], 'bandpass', fs=SR, output='sos'), seg)
        out_n[i:i + blk] = y[-len(nz[i:i + blk]):]
    # rising saw (3 detuned voices), pitch saw_from -> saw_to (MIDI), low-pass opening
    saw = np.zeros(n)
    for det in (-9, 0, 8):
        m = saw_from + (saw_to - saw_from) * u ** 1.6 + det / 100
        f = 440 * 2 ** ((m - 69) / 12)
        ph = np.cumsum(f) / SR
        saw += 2 * (ph % 1.0) - 1
    saw /= 3
    saw_f = np.zeros(n)
    for i in range(0, n, blk):
        uc = (i + blk / 2) / n
        fc = 300 * (12000 / 300) ** (uc ** 1.5)
        seg = saw[max(0, i - 2048):i + blk]
        y = sosfilt(butter(2, min(fc, 20000), 'lowpass', fs=SR, output='sos'), seg)
        saw_f[i:i + blk] = y[-len(saw[i:i + blk]):]
    sig = (0.8 * out_n / (np.std(out_n) + 1e-9) + 0.45 * saw_f / (np.std(saw_f) + 1e-9)) * amp
    st = np.stack([sig, np.roll(sig, int(0.007 * SR))])  # a little width
    st[:, -int(0.004 * SR):] *= np.linspace(1, 0, int(0.004 * SR))
    return peak_norm(st, level_db)


def reverse_swell(dur, level_db, seed, ir, src='chord', pitch=50.0):
    """Reverse-reverb swell: a burst (noise or a D-minor 'chord' of saws) run through the hall,
    reversed, so it sucks up into the downbeat at the end of the returned buffer."""
    rng = np.random.default_rng(seed)
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    if src == 'chord':
        b = 0
        for m in (pitch - 12, pitch, pitch + 3, pitch + 7, pitch + 12):
            f = 440 * 2 ** ((m - 69) / 12)
            b = b + np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)
        b = b * np.exp(-t / 0.08) + 0.3 * white(n, rng) * np.exp(-t / 0.03)
    else:
        b = white(n, rng) * np.exp(-t / 0.05)
    L = int(dur * SR)
    src2 = np.zeros((2, L))
    src2[:, :n] = b
    wet = X.convolve(src2, ir)
    wet = wet[:, ::-1]
    wet = fade(wet, fin=min(0.3, dur / 3))
    wet[:, -int(0.003 * SR):] *= np.linspace(1, 0, int(0.003 * SR))
    return peak_norm(wet, level_db)


def heartbeat_sine(level_db):
    """40 Hz sine thump (doubled in the score by a soft-mallet bass drum and pizz basses)."""
    s = sine_glide(46.0, 40.0, 0.7, 0.06)
    e = env_ar(len(s), 0.008, 0.16)
    return peak_norm(s * e, level_db)


# --------------------------------------------------------------------------- foley helpers
def burst(n, rng, lo=None, hi=None, order=2):
    x = white(n, rng)
    if lo and hi:
        return X.bp(x, lo, hi, order)
    if lo:
        return X.hp(x, lo, order)
    if hi:
        return X.lp(x, hi, order)
    return x


def chirp(f0, f1, dur, tau, phase=0.0):
    n = max(8, int(dur * SR))
    t = np.arange(n) / SR
    f = f0 * (f1 / f0) ** (t / dur)
    return np.sin(phase + 2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / tau)


def bubbles(buf, t0, t1, rate, rng, f_lo, f_hi, rise=(1.3, 2.0), dur=(0.002, 0.008), tau=(0.0015, 0.004),
            level_db=-40.0, pan_w=0.8, rate_fn=None, pitch_fn=None, rev=False):
    """Poisson field of exponential-chirp bubble pops (fizz / liquid). rate_fn(t)/pitch_fn(t) scale
    density / pitch over time (fizz-rush speed ramp)."""
    t = t0
    amp0 = X.db(level_db)
    while True:
        r = rate * (rate_fn(t) if rate_fn else 1.0)
        t += rng.exponential(1.0 / max(r, 1e-3))
        if t >= t1:
            break
        ps = pitch_fn(t) if pitch_fn else 1.0
        f0 = math.exp(rng.uniform(math.log(f_lo), math.log(f_hi))) * ps
        k = rng.uniform(*rise)
        d = rng.uniform(*dur) / ps
        ta = rng.uniform(*tau) / ps
        c = chirp(f0, min(f0 * k, 20000), d, ta, rng.uniform(0, 6.28))
        if rev:
            c = c[::-1]
        a = amp0 * math.exp(rng.normal(0, 0.6))
        p = rng.uniform(-pan_w, pan_w)
        th = (p + 1) * math.pi / 4
        place(buf, np.stack([c * math.cos(th), c * math.sin(th)]) * a * 1.41, t)


def amb(n, rng, kind, level_db, lo=None, hi=None, lfo=None):
    """Ambience bed: pink/brown noise, filtered, optional slow LFO, stereo decorrelated."""
    out = []
    for c in range(2):
        x = pink(n, rng) if kind == 'pink' else brown(n, rng) if kind == 'brown' else white(n, rng)
        if lo and hi:
            x = X.bp(x, lo, hi)
        elif hi:
            x = X.lp(x, hi)
        elif lo:
            x = X.hp(x, lo)
        out.append(x)
    y = np.stack(out)
    if lfo:
        f, depth = lfo
        t = np.arange(n) / SR
        y *= 1 + depth * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28))
    return rms_norm(y, level_db)


def buzz(dur, f=120.0, level_db=-40.0, seed=0, bright=1.0):
    """Mains transformer / neon buzz: 120 Hz with rich harmonics (soft-clipped sine) + a little
    60 Hz, band-limited, with slow flutter."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    fl = 1 + 0.004 * np.sin(2 * np.pi * 0.7 * t) + 0.002 * rng.standard_normal(n).cumsum() / np.sqrt(n)
    ph = 2 * np.pi * np.cumsum(f * fl) / SR
    s = np.tanh(3.0 * bright * np.sin(ph)) + 0.25 * np.sin(ph / 2)
    s = X.bp(s, 90, 4000)
    s += 0.05 * X.bp(rng.standard_normal(n), 2000, 7000)  # gas hiss
    return rms_norm(np.stack([s, s * 0.96]), level_db)


# --------------------------------------------------------------------------- foley
def typebar(rng, claves):
    """One typebar strike (onset at sample 0): key thunk + slap + platen thock + steel ring, with
    the escapement tick (VCSL claves pitched up) ~75 ms later."""
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    thunk = np.sin(2 * np.pi * (200 * np.exp(-t / 0.02) + 165) * t) * np.exp(-t / 0.007) * (t < 0.02)
    slap = burst(int(0.008 * SR), rng, lo=2000) * np.exp(-np.arange(int(0.008 * SR)) / SR / 0.0018)
    thock = X.bp(white(n, rng), 300, 520) * np.exp(-t / 0.013)
    ring = (0.25 * damped(2630, 0.018, 0.25) + 0.18 * damped(3710, 0.012, 0.25) + 0.1 * damped(5240, 0.008, 0.25))
    s = 0.9 * thunk + 0.0
    s[:len(slap)] += 1.1 * slap / (np.abs(slap).max() + 1e-9)
    s += 0.8 * thock / (np.abs(thock).max() + 1e-9) + ring
    st = X.pan_mono(s, 0.12)
    tick = claves[:, :int(0.04 * SR)] * np.linspace(1, 0, int(0.04 * SR))
    place(st, X.hp(tick, 1500) * 0.35 / (np.abs(tick).max() + 1e-9), 0.075)
    return st


def key_tick(rng):
    n = int(0.012 * SR)
    s = burst(n, rng, lo=2500) * np.exp(-np.arange(n) / SR / 0.0015) + 0.3 * damped(3100, 0.003, 0.012)
    return X.pan_mono(s, -0.35)


def build_foley(N, ir_room, seed=2026):
    """Return the (2, N) foley stem (with its short-room reflections) and a cue list."""
    rng = np.random.default_rng(seed)
    F = np.zeros((2, N))
    cues = []

    def cue(name, t):
        cues.append(dict(name=name, t=round(t, 4), frame=round(t * 24, 2)))

    claves = load(f'{VCSL}/Idiophones/Struck Idiophones/Claves/Claves1_Hit_v2_rr1_Mid.wav', 7.0)
    claves = claves[:, np.argmax(np.abs(claves).max(axis=0) > 0.05 * np.abs(claves).max()):]

    # ---------------- ACT I  workroom (0 - 12.5 s)
    a = amb(int(12.5 * SR), rng, 'pink', -60, hi=450)
    place(F, fade(a, 0.4, 0.3), 0.0)
    gust = X.bp(white(int(3.2 * SR), rng), 220, 900)
    tt = np.linspace(0, 1, gust.shape[0])
    gust *= np.sin(np.pi * tt) ** 2 * (1 + 0.3 * np.sin(2 * np.pi * 1.3 * tt * 3.2))
    place(F, X.pan_mono(rms_norm(gust, -55), -0.55), 5.2)
    cue('wind gust', 5.2)
    for fr in (15, 30, 45, 60):
        place(F, peak_norm(typebar(rng, claves), -13.0), T(fr))
        cue(f'typebar strike f{fr}', T(fr))
    # super type-on key ticks (2 frames per character) + odometer rolls landing on beats
    supers = [(3.00, 'WOLFENBÜTTEL · GERMANY', 5.0), (16.40, 'OAK CASK', T(420)), (20.40, 'NORTH ATLANTIC', 21.875),
              (24.45, 'UNITED STATES', 25.625), (28.10, 'LAKE TAHOE (ALLEGEDLY)', 30.0)]
    for t0, txt, land in supers:
        for i, ch in enumerate(txt):
            if ch.strip() and ch not in '·()':
                place(F, peak_norm(key_tick(rng), -32 + rng.normal(0, 1.5)), t0 + i * 2 / 24)
        # odometer: ~10 frames of soft detent clicks accelerating into the landing beat
        for k in range(7):
            tk = land - (10 / 24) * (1 - k / 7) ** 1.3
            place(F, peak_norm(key_tick(rng), -38), tk)
        place(F, peak_norm(key_tick(rng), -31), land)
        cue(f'super "{txt}" type-on', t0)
    # S02 botanical rustle (f75-135): granular high-passed crackle riding the slider
    bub = np.zeros((2, int(2.6 * SR)))
    tt = 0.0
    while tt < 2.5:
        tt += rng.exponential(1 / 70.0)
        g = burst(int(rng.uniform(0.0008, 0.004) * SR), rng, lo=2200) * rng.uniform(0.2, 1.0)
        place(bub, X.pan_mono(g, -0.6 + 1.2 * tt / 2.5), tt)
    bub *= np.sin(np.pi * np.linspace(0, 1, bub.shape[1])) ** 0.7
    place(F, rms_norm(bub, -50), T(75))
    cue('botanical rustle', T(75))
    # S03 chain tinkle (f135-170) + pivot tick when the pointer settles (f180)
    for k in range(9):
        tk = T(135) + 0.25 * k ** 1.2 + rng.uniform(0, 0.08)
        f0 = rng.uniform(2300, 3600)
        s = modal([f0, f0 * 2.31, f0 * 3.89], [0.06, 0.035, 0.02], [1, 0.5, 0.3], 0.25)
        place(F, X.pan_mono(peak_norm(s, -44 - 2.5 * k), 0.3), tk)
    tick = burst(int(0.004 * SR), rng, lo=1800) + 0.4 * damped(1850, 0.01, 0.004)
    place(F, X.pan_mono(peak_norm(np.concatenate([tick, damped(1850, 0.02, 0.1) * 0.3]), -34), 0.1), T(180) - 0.004)
    cue('balance chain tinkle', T(135))
    cue('pivot tick', T(180))
    # S04 'day' swells (filtered noise per light flicker) + faint glass ring
    for fr in (195, 210, 225):
        L = int(0.55 * SR)
        s = X.bp(white(L, rng), 350, 2400) * np.sin(np.pi * np.linspace(0, 1, L)) ** 2
        place(F, X.pan_mono(rms_norm(s, -52), 0.2), T(fr) - 0.4)
    place(F, X.pan_mono(peak_norm(modal([1318, 3093, 5480], [1.6, 0.9, 0.5], [1, 0.4, 0.15], 2.5), -54), 0.25),
          T(186))
    cue('day swells', T(195))
    # S05 card flex (around f246)
    L = int(0.45 * SR)
    s = X.bp(white(L, rng), 900, 5000) * (0.4 + 0.6 * np.abs(np.sin(np.linspace(0, 9, L)))) * \
        np.sin(np.pi * np.linspace(0, 1, L))
    place(F, X.pan_mono(rms_norm(s, -50), -0.1), T(246))
    cue('card flex', T(246))

    # ---------------- ACT II  cellar (12.5 - 20.0 s)
    a = amb(int(7.6 * SR), rng, 'brown', -56, hi=260, lfo=(0.11, 0.25))
    place(F, fade(a, 0.05, 0.05), T(300))
    a = amb(int(7.6 * SR), rng, 'pink', -66, lo=300, hi=2500)
    place(F, fade(a, 0.05, 0.05), T(300))
    for k, fr in enumerate(range(300, 390, 15)):  # one 'day' whoomp per sun sweep (6)
        L = int(0.6 * SR)
        s = X.lp(white(L, rng), 160, 4) * np.sin(np.pi * np.linspace(0, 1, L) ** 0.6) ** 2
        place(F, X.pan_mono(rms_norm(s, -43), -0.3 + 0.12 * k), T(fr) - 0.12)
    cue('sun-sweep whoomps x6', T(300))
    L = int(0.36 * SR)
    am = (np.sin(2 * np.pi * 47 * np.arange(L) / SR) > 0.2).astype(float)
    s = X.hp(white(L, rng), 2600) * (0.3 + am) * np.sin(np.pi * np.linspace(0, 1, L)) ** 0.5
    place(F, X.pan_mono(rms_norm(s, -34), 0.15), T(420) - 0.05)
    cue('chalk scratch', T(420) - 0.05)

    # ---------------- ACT III  freighter hold (20.0 - 24.375 s) and 1980s back bar (-27.5 s)
    d = T(585) - T(480)
    n = int(d * SR)
    tt = np.arange(n) / SR
    ph = np.cumsum(36 + 2.5 * np.sin(2 * np.pi * 0.21 * tt)) / SR
    saw = 2 * (ph % 1) - 1
    groan = np.zeros(n)
    for i in range(0, n, 2400):
        fc = 90 + 220 * (0.5 + 0.5 * math.sin(2 * math.pi * 0.23 * i / SR - 1.2))
        seg = saw[max(0, i - 2048):i + 2400]
        y = sosfilt(butter(2, [max(30, fc * 0.6), fc * 1.4], 'bandpass', fs=SR, output='sos'), seg)
        groan[i:i + 2400] = y[-len(saw[i:i + 2400]):]
    place(F, X.pan_mono(rms_norm(fade(groan, 0.4, 0.2), -46), 0.1), T(480))
    sea = amb(n, rng, 'pink', -47, lo=150, hi=1800)
    sea *= (0.35 + 0.65 * (0.5 + 0.5 * np.sin(2 * np.pi * tt / 3.6 - 1.0)) ** 2)
    place(F, fade(sea, 0.3, 0.2) * np.array([[1.0], [0.6]]), T(480))
    bd = load(f'{VCSL}/Idiophones/Struck Idiophones/Brake Drum/BrakeDrum1_Bowed_rr2_Mid.wav', -14.0)
    place(F, X.lp(fade(peak_norm(bd[:, :int(1.8 * SR)], -40), 0.25, 0.6), 1800), 21.1)
    gu = load(f'{VCSL}/Idiophones/Struck Idiophones/Guiro/Guiro_Slow_rr2_Mid.wav', -11.0)
    place(F, X.lp(fade(peak_norm(gu, -41), 0.05, 0.3), 2500) * np.array([[0.7], [1.0]]), 22.75)
    for k, ts in enumerate([20.55, 21.65, 22.75, 23.85]):   # lamp-chain squeak at each swing extreme
        s = chirp(1750 + 120 * (k % 2), 2050, 0.16, 0.08) * (1 + 0.5 * white(int(0.16 * SR), rng) * 0.1)
        place(F, X.pan_mono(peak_norm(X.bp(s, 1200, 4000), -47), 0.45 if k % 2 else -0.15), ts)
    cue('hold: hull groan, sea wash, creaks, chain squeaks', T(480))
    # tap machine (f585-630): compressor hum, liquid stream + bubbles, rising fill resonance
    d = T(630) - T(585)
    n = int(d * SR)
    tt = np.arange(n) / SR
    hum = sum(a * np.sin(2 * np.pi * 60 * h * tt) for h, a in ((1, 1), (2, 0.6), (3, 0.35), (4, 0.2)))
    place(F, rms_norm(np.stack([hum, hum]), -50), T(585))
    stream = X.bp(white(n, rng), 600, 2600) * (0.6 + 0.4 * np.abs(X.lp(white(n, rng), 18)) * 3)
    place(F, X.pan_mono(rms_norm(fade(stream, 0.05, 0.1), -42), -0.05), T(585))
    bb = np.zeros((2, n))
    bubbles(bb, 0.0, d, 26, rng, 380, 1300, rise=(1.4, 2.2), dur=(0.015, 0.04), tau=(0.006, 0.015),
            level_db=-44, pan_w=0.2)
    place(F, bb, T(585))
    res = np.zeros(n)
    for i in range(0, n, 2400):
        fc = 420 * (2.3 ** (i / n))
        seg = white(2400 + 2048, rng)
        y = sosfilt(butter(2, [fc * 0.93, fc * 1.07], 'bandpass', fs=SR, output='sos'), seg)[-2400:]
        res[i:i + 2400] = y[:len(res[i:i + 2400])]
    place(F, X.pan_mono(rms_norm(fade(res, 0.3, 0.1), -50), 0.0), T(585))
    cue('tap machine: compressor hum, liquid stream, fill resonance', T(585))
    # fluorescent tube hum (S11 faint, S12 close)
    fl = buzz(T(660) - T(585), 120.0, -58, seed=5, bright=0.5)
    fl[:, int((T(630) - T(585)) * SR):] *= X.db(6)
    place(F, fl, T(585))
    cue('fluorescent hum', T(630))
    # ---- the f660 dead cut: everything above (incl. its room reflections) ends on the cut frame
    F = X.zero_after(F + 0.32 * X.convolve(F, ir_room), T(660), fade=0.002)
    F_pre, F = F, np.zeros((2, N))

    # ---------------- ACT IV  Tahoe (27.5 - 41.875 s)
    t0, t1 = T(660), T(1005)
    n = int((t1 - t0) * SR)
    room = amb(n, rng, 'pink', -58, lo=60, hi=900)
    place(F, fade(room, 0.25, 0.0), t0)
    lake = np.zeros((2, n + SR))
    tt = 0.15
    while tt < (t1 - t0):
        L = int(rng.uniform(0.5, 0.9) * SR)
        s = X.lp(white(L, rng), rng.uniform(450, 800)) * env_ar(L, rng.uniform(0.03, 0.08), rng.uniform(0.12, 0.25))
        g = np.zeros((2, L))
        place(g, X.pan_mono(s, rng.uniform(-0.7, 0.7)), 0)
        bubbles(g, 0.02, 0.4, 25, rng, 180, 520, rise=(1.3, 1.8), dur=(0.02, 0.05), tau=(0.01, 0.03),
                level_db=-30, pan_w=0.5)
        place(lake, g * X.db(rng.normal(0, 2.5)), tt)
        tt += rng.uniform(1.1, 2.6)
    place(F, rms_norm(lake[:, :n], -51), t0)
    crk = np.zeros((2, n))
    for fc, pan, rate, ph in ((4480, -0.6, 0.83, 0.1), (4720, 0.55, 0.71, 0.4)):
        tt = ph
        while tt < (t1 - t0):
            for p in range(4):
                s = np.sin(2 * np.pi * fc * np.arange(int(0.014 * SR)) / SR) * np.hanning(int(0.014 * SR))
                place(crk, X.pan_mono(s, pan), tt + p * 0.038)
            tt += rate * rng.uniform(0.92, 1.08)
    place(F, X.lp(rms_norm(crk, -60), 7000), t0)
    cue('Tahoe: room tone, lake lap, crickets', t0)
    # neon ignition at f690: tick-tick, crackle, buzz, two stutters, then it catches -> pedal tone
    tn = T(690)
    nb = buzz(T(1005) - tn, 120.0, -42, seed=11)
    gate = X.gate_curve(nb.shape[1], [(0.12, 0.20, 0, 0), (0.20, 0.205, 0, 1), (0.30, 0.36, 0, 0),
                                      (0.36, 0.365, 0, 1)])
    nb *= gate
    for tk in (0.0, 0.04, 0.12, 0.20, 0.30, 0.36):
        place(nb, X.pan_mono(peak_norm(burst(int(0.006 * SR), rng, lo=1500), -34), 0.4), tk)
    cr = np.zeros((2, int(0.5 * SR)))
    for _ in range(40):
        place(cr, X.pan_mono(burst(int(rng.uniform(0.0005, 0.002) * SR), rng, lo=3000) * rng.uniform(0.2, 1), 0.4),
              rng.uniform(0, 0.45))
    place(nb, peak_norm(cr, -38), 0.0)
    place(F, nb * np.array([[1.0], [0.85]]), tn)
    cue('neon ignition (tick-tick, stutters, catches)', tn)
    fr_hum = buzz(T(1005) - T(735), 60.0, -63, seed=13, bright=0.3)
    place(F, X.lp(fr_hum, 400), T(735))
    cue('refrigerator hum', T(735))
    fz = np.zeros((2, int((T(1005) - T(735)) * SR)))

    def fizz_level(t):  # relative to f735
        a = t + T(735)
        if a < T(795):
            return 0.35       # S14 slider passes the highball
        if a < T(870):
            return 0.12       # S15 stool (far)
        if a < T(930):
            return 0.6        # S16 ring / highball soft behind
        return 1.0            # S17 close into the highball
    bubbles(fz, 0.0, fz.shape[1] / SR, 260, rng, 2800, 9000, level_db=-41, rate_fn=fizz_level)
    place(F, fz, T(735))
    cue('close fizz', T(735))
    for k, ts in enumerate([T(797), T(797) + 0.62, T(797) + 1.36, T(797) + 2.3]):   # swivel bearing squeaks
        s = chirp(1250 - 60 * k, 1500 - 80 * k, 0.32 + 0.08 * k, 0.15) * \
            (1 + 0.6 * np.sin(2 * np.pi * 31 * np.arange(int((0.32 + 0.08 * k) * SR)) / SR))
        place(F, X.pan_mono(peak_norm(X.bp(s, 900, 3500), -42 - 3 * k), 0.15), ts)
    cue('stool swivel squeaks (decelerating)', T(797))
    # ---- f1005-1019 total silence for the foley too (2-frame fade out, room tail included)
    F = F + 0.32 * X.convolve(F, ir_room)
    F *= X.gate_curve(N, [(T(1003), T(1005), 1, 0), (T(1005), N / SR + 1, 0, 0)])[None, :]
    F = X.zero_before(F, T(660))
    F_mid, F = F, np.zeros((2, N))

    # ---------------- ACT V  the second (42.5 s -)
    ti = T(1020)
    L = int(1.6 * SR)
    tt = np.arange(L) / SR
    boom = sine_glide(56, 42, 1.6, 0.35) * env_ar(L, 0.003, 0.32) + \
        0.6 * X.lp(white(L, rng), 300, 4) * env_ar(L, 0.002, 0.18)
    place(F, peak_norm(np.stack([boom, boom]), -11), ti)
    spl = np.zeros((2, int(1.0 * SR)))
    tg = 0.0
    while tg < 0.75:   # 'time-stretched 4x, pitched down' splash: sparse low grains thinning out
        tg += rng.exponential(1 / (900 * math.exp(-tg / 0.25) + 40))
        Lg = int(rng.uniform(0.003, 0.012) * SR)
        gr = X.bp(white(Lg, rng), 250, 2200) * np.hanning(Lg) * math.exp(-tg / 0.3)
        place(spl, X.pan_mono(gr, rng.uniform(-0.5, 0.5)), tg)
    place(F, peak_norm(spl, -10), ti + 0.005)
    L = int(0.9 * SR)
    crown = X.hp(white(L, rng), 6000) * env_ar(L, 0.02, 0.22) * (0.6 + 0.4 * np.abs(X.lp(white(L, rng), 40)) * 4)
    place(F, X.pan_mono(rms_norm(crown, -27), 0.1, 0.4), ti + 0.03)
    rb = np.zeros((2, int(1.1 * SR)))
    bubbles(rb, 0.0, 1.0, 22, rng, 900, 2600, rise=(1.4, 2.0), dur=(0.03, 0.08), tau=(0.02, 0.04),
            level_db=-36, pan_w=0.4, rev=True)
    place(F, rb, ti + 0.25)
    gong = load(f'{VCSL}/Idiophones/Struck Idiophones/Gong 1/' +
                sorted(os.listdir(f'{VCSL}/Idiophones/Struck Idiophones/Gong 1'))[0], -3.0)
    gr = gong[:, :int(1.15 * SR)][:, ::-1]
    place(F, fade(peak_norm(X.lp(gr, 3000), -30), 0.4, 0.0), T(1050) - gr.shape[1] / SR)
    cue('glass plunge: boom, slow-motion splash, crown shimmer, reversed bubbles, reverse-gong tail', ti)
    L = int(0.45 * SR)
    tonk = modal([780, 1810, 3320, 5170], [0.11, 0.07, 0.045, 0.03], [1, 0.55, 0.3, 0.15], 0.45)
    tonk = X.lp(tonk + 0.5 * X.lp(white(L, rng), 220) * env_ar(L, 0.001, 0.02), 2400)
    place(F, X.pan_mono(peak_norm(tonk, -13), 0.0), 44.4)
    cue('muted glass tonk (shot glass touches bottom)', 44.4)
    L = int(2.6 * SR)
    tt = np.arange(L) / SR
    ink = 0
    for m, a in ((38, 1.0), (45, 0.5), (50, 0.35)):
        for det in (-4, 0, 5):
            f = 440 * 2 ** ((m + det / 100 - 69) / 12) * (1 + 0.003 * np.sin(2 * np.pi * 0.31 * tt + det))
            ink = ink + a * np.sin(2 * np.pi * np.cumsum(f) / SR)
    sw = np.zeros(L)
    nz = white(L, rng)
    for i in range(0, L, 2400):
        fc = 220 + 160 * math.sin(2 * math.pi * 0.45 * i / SR)
        y = sosfilt(butter(2, [fc * 0.7, fc * 1.4], 'bandpass', fs=SR, output='sos'), nz[max(0, i - 2048):i + 2400])
        sw[i:i + 2400] = y[-len(nz[i:i + 2400]):]
    ink = ink / np.abs(ink).max() + 0.6 * sw / (np.abs(sw).max() + 1e-9)
    ink *= np.sin(np.pi * np.minimum(tt / 2.4, 1.0)) ** 1.5
    place(F, np.stack([ink, np.roll(ink, 300)]) * X.db(-30) / np.abs(ink).max(), T(1080))
    cue('ink tone', T(1080))
    # fizz rush on the speed ramp (playback 1/6 -> 1 between f1110 and f1130), then real-time fizz
    t_a, t_b, t_end = T(1110), T(1130), T(1320)
    fr_buf = np.zeros((2, int((t_end - t_a) * SR)))

    def ramp(t):
        a = t + t_a
        u = min(1.0, max(0.0, (a - t_a) / (t_b - t_a)))
        return (1 / 6) * (6 ** u)

    def rush_rate(t):
        a = t + t_a
        if a < t_b:
            return ramp(t) * 2.0
        if a < T(1140):
            return 2.0
        return 0.75     # hero still: settled fizz, wider shot
    bubbles(fr_buf, 0.0, fr_buf.shape[1] / SR, 300, rng, 2600, 8500, level_db=-38, rate_fn=rush_rate,
            pitch_fn=ramp)
    fr_buf *= np.minimum(1.0, np.arange(fr_buf.shape[1]) / (0.25 * SR))[None, :]
    place(F, fr_buf, t_a)
    cue('fizz rush (slowed -> real time)', t_a)
    # packshot: bar room tone, neon hum, condensation slide on the bead at the 50.0 hero hit
    t0, t1 = T(1140), T(1335)
    n = int((t1 - t0) * SR)
    place(F, fade(amb(n + int(0.4 * SR), rng, 'pink', -61, lo=60, hi=900), 0.4, 0.4), t0)
    nh = buzz(t1 - t0, 120.0, -47, seed=17)
    # stutters at 55.2 and 55.4 s, death click on f1335 (55.625 s)
    rel = lambda a: a - t0
    g = X.gate_curve(nh.shape[1], [(rel(55.2), rel(55.29), 0, 0), (rel(55.4), rel(55.52), 0, 0)])
    nh *= g
    for ts in (55.2, 55.29, 55.4, 55.52):
        place(nh, X.pan_mono(peak_norm(burst(int(0.005 * SR), rng, lo=1500), -36), 0.4), rel(ts))
    place(F, fade(nh, 0.6, 0.0) * np.array([[1.0], [0.85]]), t0)
    L = int(0.8 * SR)
    sl = X.bp(white(L, rng), 2500, 6500) * np.sin(np.pi * np.linspace(0, 1, L)) ** 2 + \
        0.3 * chirp(2600, 1900, 0.8, 0.5)
    place(F, X.pan_mono(rms_norm(sl, -56), -0.25), T(1200) + 0.05)
    cue('condensation slide on the bottle bead', T(1200) + 0.05)
    td = T(1335)
    click = burst(int(0.003 * SR), rng, lo=800) + 0.5 * damped(2100, 0.012, 0.003)
    click = np.concatenate([click, 0.4 * damped(2100, 0.015, 0.06)])
    place(F, X.pan_mono(peak_norm(click, -27), 0.4), td)
    L = int(0.9 * SR)
    rd = sine_glide(120, 96, 0.9, 0.6) * np.exp(-np.arange(L) / SR / 0.22)
    rd = np.tanh(2 * rd)
    place(F, X.pan_mono(peak_norm(X.bp(rd, 80, 1500), -44), 0.4), td)
    cue('neon stutters 55.2/55.4, death click + transformer ring-down', td)
    # lake lap only, to the end (fades out with the picture)
    t0 = T(1140)
    n = int((60.0 - t0) * SR)
    lake = np.zeros((2, n))
    tt = 0.3
    while tt < n / SR:
        L = int(rng.uniform(0.5, 0.9) * SR)
        s = X.lp(white(L, rng), rng.uniform(450, 800)) * env_ar(L, rng.uniform(0.03, 0.08), rng.uniform(0.12, 0.25))
        place(lake, X.pan_mono(s, rng.uniform(-0.7, 0.7)) * X.db(rng.normal(0, 2.5)), tt)
        tt += rng.uniform(1.1, 2.6)
    lake = rms_norm(lake, -57)
    lake[:, int((T(1335) - t0) * SR):] *= X.db(4)     # once the neon dies, the lake is all there is
    place(F, lake, t0)
    F = X.zero_before(F + 0.32 * X.convolve(F, ir_room), T(1020))
    F = F_pre + F_mid + F
    # ---- fade with the picture's last 8 frames
    F *= X.gate_curve(N, [(T(1432), 60.0, 1, 0), (60.0, N / SR + 1, 0, 0)])[None, :]
    return F, cues


def build_synth(N, ir_hall, seed=77):
    """Synth/fx layers: sub hits, risers, reverse swells, heartbeat sines.  Returns (dry, cues)."""
    rng = np.random.default_rng(seed)
    S = np.zeros((2, N))
    cues = []

    def add(name, sig, t, gain_db=0.0):
        place(S, sig, t, X.db(gain_db))
        cues.append(dict(name=name, t=round(t, 4), frame=round(t * 24, 2)))

    add('sub 41 Hz, 3 s tail (overture hit)', sub_hit(41.2, 41.2, 0.01, 3.0, -12.0), T(0))
    add('sub 41 Hz soft (hit 1)', sub_hit(44, 39, 0.25, 2.2, -16.0), T(300))
    r1 = riser(T(480) - T(420), -18.0, seed + 1, saw_from=50, saw_to=62)
    add('riser 1 (filtered noise + rising saw) into f480', r1, T(420))
    rs = reverse_swell(T(480) - T(450), -17.0, seed + 2, ir_hall, pitch=50)
    add('reverse-reverb swell into f480', rs, T(450))
    add('sub boom 45->30 Hz (hit 2)', sub_hit(45, 30, 0.6, 3.2, -10.0), T(480))
    rs2 = reverse_swell(T(660) - T(612), -16.0, seed + 3, ir_hall, pitch=57)
    add('reverse swell rising toward f660 (cut dead)', rs2, T(612))
    for fr in (780, 810, 840, 870, 900, 930, 960, 990):
        k = (fr - 780) / 210
        add(f'heartbeat 40 Hz sine f{fr}', heartbeat_sine(-15.0 + 4 * k), T(fr))
    r2 = riser(4.4, -14.0, seed + 4, f_lo=180, f_hi=9000, saw_from=45, saw_to=62, curve=2.2)
    add('riser 2 (4.4 s) into f1005', r2, T(1005) - 4.4)
    add('sub impact 45->28 Hz', sub_hit(45, 28, 0.9, 4.0, -9.0), T(1020))
    add('sub D1 bloom', sub_hit(40, 36.7, 0.3, 2.5, -12.0), T(1080))
    add('sub D1 title hit', sub_hit(40, 36.7, 0.3, 2.0, -15.0), T(1140))
    add('sub D1 hero hit', sub_hit(42, 36.7, 0.4, 2.8, -10.0), T(1200))
    add('sub D1 button', sub_hit(40, 36.7, 0.3, 2.0, -12.0), T(1380))
    return S, cues
