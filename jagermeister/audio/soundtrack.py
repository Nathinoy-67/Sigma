#!/usr/bin/env python3
"""Score and sound design for the Jägermeister film.

Everything is synthesised from scratch (no samples) and cut to the same
cue sheet as the picture (audio/cues.json, exported from src/timeline.js).

    python3 audio/soundtrack.py   ->  audio/soundtrack.wav (48 kHz, 24-bit)
"""
import json
import os

import numpy as np
from scipy import signal
from scipy.io import wavfile

HERE = os.path.dirname(os.path.abspath(__file__))
C = json.load(open(os.path.join(HERE, "cues.json")))
SR = 48000
LEN = C["DURATION"] + 1.5
N = int(SR * LEN)
rng = np.random.default_rng(1934)

dry = np.zeros((2, N))
wet = np.zeros((2, N))  # reverb send


# ----------------------------------------------------------------------------- basics
def secs(n):
    return np.arange(n) / SR


def ns(d):
    return max(1, int(round(d * SR)))


def noise(n):
    return rng.standard_normal(n)


def place(sig, t0, db=0.0, pan=0.0, rev=0.0):
    """Mix a mono (equal-power panned) or stereo signal in at t0 seconds."""
    g = 10 ** (db / 20)
    if sig.ndim == 1:
        a = (np.clip(pan, -1, 1) + 1) * np.pi / 4
        st = np.vstack([sig * np.cos(a), sig * np.sin(a)]) * np.sqrt(2)
    else:
        st = sig
    # de-click: 0.5 ms fade-in, 20 ms fade-out on everything
    n = st.shape[1]
    fi, fo = min(n, ns(0.0005)), min(n, ns(0.02))
    st = st.copy()
    st[:, :fi] *= np.linspace(0, 1, fi)[None, :]
    st[:, n - fo :] *= np.linspace(1, 0, fo)[None, :]
    i0 = int(round(t0 * SR))
    if i0 < 0:
        st = st[:, -i0:]
        i0 = 0
    n = min(st.shape[1], N - i0)
    if n <= 0:
        return
    dry[:, i0 : i0 + n] += st[:, :n] * g
    if rev > 0:
        wet[:, i0 : i0 + n] += st[:, :n] * g * rev


def stereo(fn, *a, **k):
    """Render a generator twice (fresh randomness) for a wide stereo image."""
    return np.vstack([fn(*a, **k), fn(*a, **k)])


def env_exp(n, tau, attack=0.002):
    t = secs(n)
    e = np.exp(-t / tau)
    if attack > 0:
        e *= np.minimum(1.0, t / attack)
    return e


def env_fade(n, fin, fout, shape=1.0):
    t = secs(n)
    d = n / SR
    e = np.ones(n)
    if fin > 0:
        e *= np.clip(t / fin, 0, 1) ** shape
    if fout > 0:
        e *= np.clip((d - t) / fout, 0, 1) ** shape
    return e


# ----------------------------------------------------------------------------- oscillators
def _phase(f, n):
    f = np.broadcast_to(np.asarray(f, dtype=np.float64), (n,))
    return np.cumsum(f) / SR, f / SR


def sine(f, n, ph0=0.0):
    ph, _ = _phase(f, n)
    return np.sin(2 * np.pi * (ph + ph0))


def saw(f, n, ph0=0.0):
    ph, dt = _phase(f, n)
    t = (ph + ph0) % 1.0
    y = 2 * t - 1
    m = t < dt
    x = t[m] / dt[m]
    y[m] -= x + x - x * x - 1
    m = t > 1 - dt
    x = (t[m] - 1) / dt[m]
    y[m] -= x * x + x + x + 1
    return y


def note(name):
    names = {"C": -9, "C#": -8, "Db": -8, "D": -7, "D#": -6, "Eb": -6, "E": -5, "F": -4, "F#": -3, "Gb": -3,
             "G": -2, "G#": -1, "Ab": -1, "A": 0, "A#": 1, "Bb": 1, "B": 2}
    p, o = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((names[p] + 12 * (o - 4)) / 12)


# ----------------------------------------------------------------------------- filters
def biquad(kind, f, q=0.707, gain_db=0.0):
    w = 2 * np.pi * min(max(f, 10.0), SR * 0.45) / SR
    cw, sw = np.cos(w), np.sin(w)
    al = sw / (2 * q)
    A = 10 ** (gain_db / 40)
    if kind == "lp":
        b, a = [(1 - cw) / 2, 1 - cw, (1 - cw) / 2], [1 + al, -2 * cw, 1 - al]
    elif kind == "hp":
        b, a = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2], [1 + al, -2 * cw, 1 - al]
    elif kind == "bp":
        b, a = [al, 0, -al], [1 + al, -2 * cw, 1 - al]
    elif kind == "peak":
        b, a = [1 + al * A, -2 * cw, 1 - al * A], [1 + al / A, -2 * cw, 1 - al / A]
    elif kind == "lowshelf":
        s = 2 * np.sqrt(A) * al
        b = [A * ((A + 1) - (A - 1) * cw + s), 2 * A * ((A - 1) - (A + 1) * cw), A * ((A + 1) - (A - 1) * cw - s)]
        a = [(A + 1) + (A - 1) * cw + s, -2 * ((A - 1) + (A + 1) * cw), (A + 1) + (A - 1) * cw - s]
    elif kind == "highshelf":
        s = 2 * np.sqrt(A) * al
        b = [A * ((A + 1) + (A - 1) * cw + s), -2 * A * ((A - 1) + (A + 1) * cw), A * ((A + 1) + (A - 1) * cw - s)]
        a = [(A + 1) - (A - 1) * cw + s, 2 * ((A - 1) - (A + 1) * cw), (A + 1) - (A - 1) * cw - s]
    else:
        raise ValueError(kind)
    a = np.array(a)
    return np.array(b) / a[0], a / a[0]


def filt(x, kind, f, q=0.707, gain_db=0.0):
    b, a = biquad(kind, f, q, gain_db)
    return signal.lfilter(b, a, x, axis=-1)


def sweep(x, kind, fc, q=0.707, block=96):
    """Time-varying biquad; fc is a per-sample cutoff curve."""
    fc = np.broadcast_to(np.asarray(fc, dtype=np.float64), (len(x),))
    y = np.empty_like(x)
    zi = np.zeros(2)
    for i in range(0, len(x), block):
        b, a = biquad(kind, float(fc[i]), q)
        y[i : i + block], zi = signal.lfilter(b, a, x[i : i + block], zi=zi)
    return y


def sample_times(t0, t1, count, dens):
    ts = np.linspace(t0, t1, 4000)
    c = np.cumsum(np.maximum(dens(ts), 1e-9))
    c /= c[-1]
    return np.sort(np.interp(rng.random(count), c, ts))


# ----------------------------------------------------------------------------- instruments
def kick(dur=0.5):
    n = ns(dur)
    t = secs(n)
    f = 50 + 150 * np.exp(-t / 0.03)
    body = sine(f, n) * env_exp(n, 0.32, 0.001)
    punch = sine(118, n) * env_exp(n, 0.045, 0.001) * 0.45  # audible on small speakers
    click = filt(noise(n), "hp", 2500) * env_exp(n, 0.004, 0.0004) * 0.3
    return np.tanh(2.0 * (body + punch + click)) / np.tanh(2.0)


def clap(dur=0.55):
    n = ns(dur)
    nz = noise(n)
    x = np.zeros(n)
    for k, d in enumerate([0.0, 0.010, 0.021, 0.031]):
        i = ns(d)
        x[i:] += nz[i:] * env_exp(n - i, 0.006 if k < 3 else 0.15, 0.0004) * (0.9 if k < 3 else 1.0)
    return filt(x, "bp", 1150, 0.9) + filt(x, "hp", 3200) * 0.22


def hat(dur=0.09, tau=0.022):
    n = ns(dur)
    x = filt(noise(n), "hp", 7800, 0.7) * env_exp(n, tau, 0.0004)
    t = secs(n)
    metal = sum(np.sign(np.sin(2 * np.pi * f * t)) for f in (5530, 7210, 8340, 9870)) * 0.05
    return x + filt(metal, "hp", 6000) * env_exp(n, tau * 0.8, 0.0004)


def boom(dur=4.0, f0=95, f1=29, tau_p=0.28, tau_a=1.7):
    n = ns(dur)
    t = secs(n)
    f = f1 + (f0 - f1) * np.exp(-t / tau_p)
    s = sine(f, n) * env_exp(n, tau_a, 0.004)
    body = filt(noise(n), "lp", 160, 0.7) * env_exp(n, 0.35, 0.002) * 1.4
    click = filt(noise(n), "hp", 1500) * env_exp(n, 0.012, 0.0005) * 0.35
    return np.tanh(1.4 * (s + body + click))


def braam(dur, notes, tau=2.6, bright=3200, drive=2.4):
    n = ns(dur)
    t = secs(n)
    x = np.zeros(n)
    for f in notes:
        for det in (-0.14, 0.0, 0.12):
            x += saw(f * 2 ** (det / 12), n, rng.random())
    fc = 80 + bright * (1 - np.exp(-t / 0.05)) * np.exp(-t / 0.8) + 260 * np.exp(-t / 3.0)
    x = sweep(x / (3 * len(notes)), "lp", fc, 1.1)
    return np.tanh(drive * x) * env_exp(n, tau, 0.015)


def fm_bell(f, dur=2.5, ratio=3.5, index=2.6, tau_i=0.4, tau_a=1.3, attack=0.002):
    n = ns(dur)
    t = secs(n)
    I = index * np.exp(-t / tau_i)
    return np.sin(2 * np.pi * f * t + I * np.sin(2 * np.pi * f * ratio * t)) * env_exp(n, tau_a, attack)


def marimba(f, dur=1.4):
    return fm_bell(f, dur, ratio=4.0, index=1.8, tau_i=0.05, tau_a=0.42) + 0.3 * fm_bell(f * 2, dur, 1.0, 0.0, 1, 0.2)


def ping(f, tau):
    n = ns(tau * 7)
    return np.sin(2 * np.pi * f * secs(n) + rng.random() * 6.28) * env_exp(n, tau, 0.0004)


def whoosh(dur, f0, f1, q=1.1, peak=0.55, pan0=-0.7, pan1=0.7):
    n = ns(dur)
    u = secs(n) / dur
    fc = f0 * (f1 / f0) ** u
    x = sweep(noise(n), "bp", fc, q) * 2.5
    e = np.where(u < peak, (u / peak) ** 2.2, ((1 - u) / (1 - peak)) ** 1.6)
    x *= e
    a = (pan0 + (pan1 - pan0) * u + 1) * np.pi / 4
    return np.vstack([x * np.cos(a), x * np.sin(a)]) * np.sqrt(2)


def riser(dur, f0=280, f1=7500, tone=110.0, octaves=2.0):
    n = ns(dur)
    u = secs(n) / dur
    fc = f0 * (f1 / f0) ** (u ** 1.4)
    x = sweep(noise(n), "bp", fc, 1.6) * 2.2 * u ** 2.2
    if tone:
        f = tone * 2 ** (u * octaves)
        ts = saw(f, n) + 0.5 * saw(f * 1.5, n) + 0.35 * saw(f * 2.0, n)
        ts = sweep(ts, "lp", 250 + 5200 * u ** 2, 0.9) * u ** 2.4 * 0.35
        x = x + ts
    return x


def reverse_swell(dur=1.2, hp=700):
    n = ns(dur)
    x = filt(noise(n), "hp", hp) * env_exp(n, dur * 0.22, 0.001)
    x = filt(x, "lp", 9000)
    return x[::-1] * 0.8


def pad(dur, notes, fc0=600, fc1=900, detune=0.09, voices=3, pitch=None, saturate=True):
    n = ns(dur)
    t = secs(n)
    x = np.zeros(n)
    pm = 1.0 if pitch is None else pitch
    for f in notes:
        for v in range(voices):
            det = (v - (voices - 1) / 2) * detune * 2 / max(1, voices - 1)
            vib = 1 + 0.0018 * np.sin(2 * np.pi * (0.17 + 0.05 * v) * t + rng.random() * 6.28)
            x += saw(f * 2 ** (det / 12) * vib * pm, n, rng.random())
        x += 0.5 * sine(f * pm, n)
    fc = fc0 * (fc1 / fc0) ** (t / dur)
    x = sweep(x / (voices * len(notes)), "lp", fc, 0.6)
    return np.tanh(1.5 * x) if saturate else x


def glass_clink():
    n = ns(2.2)
    t = secs(n)
    x = np.zeros(n)
    for k, off in enumerate([0.0, 0.014]):
        i = ns(off)
        m = n - i
        tt = secs(m)
        g = 1.0 if k == 0 else 0.55
        for f, tau, a in [(2380, 0.55, 1.0), (4980, 0.32, 0.6), (6890, 0.22, 0.45), (9120, 0.14, 0.3), (3270, 0.4, 0.3)]:
            fk = f * (1.0 + 0.012 * k)
            x[i:] += np.sin(2 * np.pi * fk * tt + rng.random() * 6) * np.exp(-tt / tau) * a * g * np.minimum(1, tt / 0.0004)
        x[i:] += filt(noise(m), "hp", 5000) * env_exp(m, 0.003, 0.0002) * 0.6 * g
    return x * 0.5


def ice_crack(level=1.0):
    n = ns(1.4)
    t = secs(n)
    x = filt(noise(n) * env_exp(n, 0.005, 0.0002) * 1.6, "hp", 900)
    for f, tau in [(1850, 0.13), (3130, 0.09), (4720, 0.07), (6900, 0.045), (820, 0.2)]:
        x += np.sin(2 * np.pi * f * t + rng.random() * 6) * env_exp(n, tau, 0.0003) * 0.22
    x += sine(55 + 40 * np.exp(-t / 0.03), n) * env_exp(n, 0.09, 0.001) * 0.9
    return x * level


def shatter_layer(dur=2.6):
    n = ns(dur)
    x = filt(noise(n), "hp", 1800) * env_exp(n, 0.2, 0.0004) * 0.7
    for ti in np.sort(rng.exponential(0.24, 300)):
        f = rng.uniform(1800, 11500)
        tau = rng.uniform(0.008, 0.13)
        i = ns(ti)
        if i >= n:
            continue
        m = min(n - i, ns(tau * 7))
        x[i : i + m] += np.sin(2 * np.pi * f * secs(m) + rng.random() * 6) * np.exp(-secs(m) / tau) * rng.uniform(0.04, 0.3)
    return x


def tick():
    n = ns(0.03)
    t = secs(n)
    return np.sin(2 * np.pi * 2650 * t) * env_exp(n, 0.0025, 0.0002) + filt(noise(n), "hp", 4000) * env_exp(n, 0.0012, 0.0001) * 0.5


def knock():
    n = ns(0.8)
    t = secs(n)
    x = filt(noise(n), "bp", 230, 6) * env_exp(n, 0.1, 0.0005) * 3.0
    x += filt(noise(n), "bp", 540, 8) * env_exp(n, 0.06, 0.0005) * 2.0
    x += sine(150, n) * env_exp(n, 0.14, 0.001) * 0.8
    return x


def bloop(f0=170, f1=520, dur=0.09):
    n = ns(dur)
    t = secs(n)
    return sine(f0 * (f1 / f0) ** (t / dur), n) * env_exp(n, dur * 0.35, 0.003)


def hoot(dur, f0, f1):
    n = ns(dur)
    t = secs(n)
    f = f0 + (f1 - f0) * (t / dur)
    s = sine(f, n) + 0.12 * sine(2 * f, n)
    s += filt(noise(n), "bp", f0, 3) * 0.3
    return s * np.sin(np.pi * t / dur) ** 1.6


def heartbeat():
    n = ns(1.0)
    t = secs(n)
    th = filt(noise(n), "lp", 260, 0.8) * env_exp(n, 0.05, 0.002) * 1.6
    a = sine(40 + 60 * np.exp(-t / 0.04), n) * env_exp(n, 0.16, 0.004) + th
    i = ns(0.2)
    b = np.zeros(n)
    b[i:] = (sine(38 + 45 * np.exp(-secs(n - i) / 0.04), n - i) * env_exp(n - i, 0.2, 0.004) + th[: n - i]) * 0.7
    return np.tanh(2.2 * (a + b)) / np.tanh(2.2)


def sidechain(times, depth=0.65, release=0.16):
    """Gain curve that ducks after each kick."""
    g = np.ones(N)
    for tk in times:
        i = ns(tk)
        m = min(N - i, ns(release * 6))
        g[i : i + m] = np.minimum(g[i : i + m], 1 - depth * np.exp(-secs(m) / release))
    return g


# ============================================================================= THE SCORE
D1, A1, D2, F2, A2, C3, D3, E3, F3, G3, A3, Bb2, Bb1 = (note(x) for x in ["D1", "A1", "D2", "F2", "A2", "C3", "D3", "E3", "F3", "G3", "A3", "Bb2", "Bb1"])

# ---- ACT I · the forest -------------------------------------------------------
# night wind
wind_n = ns(16.5)
wind = np.zeros((2, wind_n))
gust = 0.55 + 0.45 * np.sin(2 * np.pi * secs(wind_n) * 0.11) * np.sin(2 * np.pi * secs(wind_n) * 0.043 + 1)
for ch in range(2):
    w = sweep(noise(wind_n), "bp", 380 + 260 * gust, 0.5) * gust
    wind[ch] = w * env_fade(wind_n, 2.5, 3.5)
place(wind, 0.0, -21)

# sub drone in D, opening up as the forest appears
drone = stereo(pad, 14.2, [D1, D2, A2], 140, 520, 0.12, 3)
drone *= env_fade(drone.shape[1], 3.0, 1.6)
place(drone, 0.1, -12, rev=0.25)

# the epigraph: a few distant bells, a breath of shimmer
for t0, nn, pan in [(0.45, "D5", -0.3), (1.2, "A5", 0.25), (1.95, "F5", -0.1), (2.7, "E5", 0.3)]:
    place(fm_bell(note(nn), 4.0, ratio=3.5, index=1.6, tau_i=0.6, tau_a=1.6), t0, -27, pan, rev=0.9)
sh = stereo(lambda: filt(noise(ns(4.0)), "bp", 6500, 0.8) * env_fade(ns(4.0), 1.2, 2.2))
place(sh, 0.3, -40, rev=0.6)

# the forest opens: low string pad
p1 = stereo(pad, 11.0, [D2, A2, F3, C3 * 2], 260, 1100, 0.1, 3)
p1 *= env_fade(p1.shape[1], 3.0, 1.2)
place(p1, 2.6, -21, rev=0.5)

# location title
place(whoosh(1.4, 900, 3200, peak=0.6, pan0=-0.3, pan1=0.3), C["locIn"] - 0.5, -30, rev=0.4)
place(fm_bell(note("D4"), 4.0, ratio=2.0, index=1.0, tau_a=2.0), C["locIn"] + 0.1, -28, 0.0, rev=0.8)

# an owl, far to the right
place(hoot(0.42, 395, 360), 6.4, -33, 0.75, rev=1.0)
place(hoot(0.22, 400, 380), 7.25, -35, 0.75, rev=1.0)
place(hoot(0.42, 390, 355), 7.55, -34, 0.75, rev=1.0)

# heartbeat, quickening towards the light
for tb in [5.6, 7.0, 8.2, 9.25, 10.15, 10.9, 11.45]:
    place(heartbeat(), tb, -15, rev=0.15)

# the constellation: celesta glints as the stars appear
for tb in sample_times(C["stagStart"], C["stagStart"] + 1.8, 22, lambda x: np.exp(-((x - (C["stagStart"] + 0.6)) / 0.7) ** 2)):
    nn = rng.choice(["D6", "F6", "A6", "C7", "D7", "E6", "A5"])
    place(fm_bell(note(nn), 2.5, ratio=3.5, index=1.2, tau_i=0.2, tau_a=0.7), tb, -31 + rng.uniform(-4, 2), rng.uniform(-0.8, 0.8), rev=0.9)
# antlers grow: a swelling string cluster + tension riser
sw = stereo(pad, 4.2, [D3, A3, D3 * 2, E3 * 2], 300, 2600, 0.15, 3)
sw *= env_fade(sw.shape[1], 3.4, 0.25) ** 1.5
place(sw, C["stagStart"] + 0.0, -22, rev=0.6)
place(stereo(riser, 3.6, 260, 5000, 0, 1), C["ignite"] - 3.6, -24, rev=0.3)
place(stereo(reverse_swell, 1.0), C["ignite"] - 1.0, -20, rev=0.4)

# IGNITE — the Hubertus light
place(stereo(boom, 4.5), C["ignite"], -6, rev=0.35)
place(stereo(braam, 4.0, [D1, D2, A2, D3]), C["ignite"], -11, rev=0.45)
for nn, pan in [("D6", -0.4), ("A6", 0.4), ("D7", 0.0), ("F6", -0.2), ("A7", 0.2)]:
    place(fm_bell(note(nn), 5.0, ratio=3.5, index=2.0, tau_i=0.8, tau_a=2.2), C["ignite"] + rng.uniform(0, 0.05), -26, pan, rev=1.0)
glow = stereo(pad, 1.4, [D3 * 2, A3 * 2, D3 * 4], 2000, 5000, 0.2, 3)
glow *= env_fade(glow.shape[1], 0.3, 0.6)
place(glow, C["ignite"] + 0.05, -28, rev=0.8)
place(stereo(reverse_swell, 0.75, 1500), C["burst"] - 0.75, -19, rev=0.3)

# ---- ACT II · 56 botanicals ------------------------------------------------------
place(stereo(boom, 3.0, 120, 34, 0.15, 1.0), C["burst"], -10, rev=0.3)
place(whoosh(1.5, 7000, 260, q=0.9, peak=0.05, pan0=0.0, pan1=0.0), C["burst"], -12, rev=0.4)
for tb in sample_times(C["burst"], C["burst"] + 3.2, 420, lambda x: np.exp(-(x - C["burst"]) / 0.9) + 0.15):
    place(ping(rng.uniform(2600, 9500), rng.uniform(0.015, 0.07)), tb, -34 + rng.uniform(-8, 0), rng.uniform(-0.95, 0.95), rev=0.5)
# swirl: a resonant sweep circling the stereo field as the particles spiral in
sn = ns(3.0)
st = secs(sn)
fcs = 500 * 2 ** (2.6 * np.sin(np.pi * st / 3.0))
swirl = sweep(noise(sn), "bp", fcs, 3.0) * np.sin(np.pi * st / 3.0) ** 1.5 * 1.8
ang = (np.sin(2 * np.pi * st * 0.9) + 1) * np.pi / 4
place(np.vstack([swirl * np.cos(ang), swirl * np.sin(ang)]) * np.sqrt(2), C["burst"] + 0.4, -22, rev=0.5)
for tb in sample_times(C["burst"] + 1.4, C["burst"] + 3.1, 40, lambda x: (x - C["burst"] - 1.3) ** 2):
    nn = rng.choice(["D6", "F6", "G6", "A6", "C7", "D7"])
    place(fm_bell(note(nn), 1.8, ratio=3.5, index=1.0, tau_i=0.1, tau_a=0.45), tb, -33, rng.uniform(-0.9, 0.9), rev=0.7)
# "56" lands: warm chord
place(stereo(boom, 2.5, 80, 38, 0.2, 0.9), C["formDone"] - 0.05, -18, rev=0.3)
p56 = stereo(pad, 4.6, [D2, A2, E3, F3, A3], 400, 1500, 0.1, 3)
p56 *= env_fade(p56.shape[1], 0.9, 1.5)
place(p56, C["formDone"] - 0.4, -17, rev=0.55)
# one note per ingredient
for i, nn in enumerate(["D5", "F5", "G5", "A5", "C6", "D6", "F6", "G6"]):
    place(marimba(note(nn)), C["ingredients"] + i * 0.22, -21, -0.6 + i * 0.17, rev=0.55)
place(fm_bell(note("D4"), 4.0, ratio=1.4, index=1.5, tau_a=1.8), C["ingredients"] + 1.95, -24, 0.0, rev=0.8)
# the gust that carries them away + whip into the liquid
place(whoosh(1.4, 400, 2400, q=0.7, peak=0.75, pan0=-0.9, pan1=0.9), C["disperse"] - 0.1, -15, rev=0.3)
place(whoosh(0.42, 1500, 6000, q=0.9, peak=0.7, pan0=-0.6, pan1=0.9), C["whip"] - 0.32, -13, rev=0.2)

# ---- ACT II · 365 days in oak ----------------------------------------------------
place(stereo(boom, 2.5, 70, 32, 0.2, 0.9), C["whip"], -14, rev=0.3)
for k in range(14):
    place(bloop(rng.uniform(140, 260), rng.uniform(400, 700), rng.uniform(0.06, 0.12)), C["whip"] + rng.uniform(0, 0.5), -26, rng.uniform(-0.7, 0.7), rev=0.3)
# warm low pad (Bb major 7) that slows and sinks as the liquid freezes
liq_dur = C["shatter"] - C["whip"] + 0.2
ln = ns(liq_dur)
lt = secs(ln) + C["whip"]
slow = np.where(lt < C["freeze"], 1.0, 0.5 + 0.5 * np.exp(-(lt - C["freeze"]) / 1.2))
lp = stereo(pad, liq_dur, [Bb1, F2, D3, A3], 420, 260, 0.1, 3, slow)
lp *= env_fade(ln, 0.6, 1.2) * np.where(lt < C["freeze"], 1.0, np.exp(-(lt - C["freeze"]) / 2.2))[None, :]
place(lp, C["whip"], -12, rev=0.5)
rumble = stereo(lambda: filt(noise(ln), "lp", 160, 0.7) * env_fade(ln, 0.5, 1.0))
place(rumble, C["whip"], -21)
for tb in sample_times(C["whip"] + 0.6, C["freeze"] + 0.4, 18, lambda x: np.ones_like(x)):
    place(bloop(rng.uniform(120, 220), rng.uniform(380, 650), rng.uniform(0.07, 0.14)), tb, -29, rng.uniform(-0.8, 0.8), rev=0.4)
# the counter: ticks follow its speed, then an oak cask knock
cs, ce = C["countStart"], C["countEnd"]
last = -1
for x in np.linspace(cs, ce, 4000):
    u = (x - cs) / (ce - cs)
    cnt = round((1 - (1 - u) ** 4) * 365)
    if cnt // 7 != last:
        last = cnt // 7
        place(tick(), x, -27, rng.uniform(-0.2, 0.2), rev=0.15)
place(knock(), ce, -12, 0.0, rev=0.5)
place(stereo(boom, 2.0, 70, 40, 0.15, 0.6), ce, -20, rev=0.3)
place(fm_bell(note("D5"), 4.0, ratio=1.0, index=1.2, tau_a=2.0), C["daysText"] + 0.3, -26, 0.2, rev=0.8)

# ---- ACT II · ice cold ------------------------------------------------------------
fz_dur = C["shatter"] - C["freeze"]
fz = stereo(pad, fz_dur, [note("G6"), note("C7"), note("D7"), note("A6")], 3000, 6000, 0.25, 3, saturate=False)
fzn = fz.shape[1]
trem = 0.75 + 0.25 * np.sin(2 * np.pi * 5.5 * secs(fzn))
fz *= env_fade(fzn, 2.2, 0.1) * trem
place(fz, C["freeze"], -31, rev=0.8)
place(stereo(reverse_swell, 1.6, 2500), C["freeze"] - 0.4, -24, rev=0.5)
drone2 = stereo(pad, fz_dur, [D1, A1, D2], 180, 420, 0.12, 3)
drone2 *= env_fade(drone2.shape[1], 1.5, 0.05)
place(drone2, C["freeze"], -15, rev=0.3)
for tb in sample_times(C["freeze"] + 0.2, C["crack"], 170, lambda x: 0.2 + ((x - C["freeze"]) / (C["crack"] - C["freeze"])) ** 1.5):
    n = ns(0.06)
    xx = filt(noise(n) * env_exp(n, rng.uniform(0.001, 0.004), 0.0002), "bp", rng.uniform(2200, 9000), rng.uniform(3, 12)) * 3
    place(xx, tb, -24 + rng.uniform(-9, 0), rng.uniform(-1, 1), rev=0.3)
for i, nn in enumerate(["D6", "F6", "A6", "D7", "F7", "A7"]):
    place(fm_bell(note(nn), 3.0, ratio=3.5, index=1.4, tau_i=0.3, tau_a=1.0), C["frostText"] + 0.12 + i * 0.14, -25, -0.5 + i * 0.2, rev=0.9)
place(whoosh(1.2, 2500, 9000, q=0.8, peak=0.8, pan0=0.0, pan1=0.0), C["coldText"] - 0.6, -30, rev=0.5)
# the ice gives way
place(stereo(riser, C["shatter"] - C["crack"] + 0.25, 600, 9000, 220, 1.5), C["crack"] - 0.25, -20, rev=0.3)
for tc, lv in [(C["crack"], -15), (C["crack"] + 0.26, -13), (C["crack"] + 0.45, -12), (C["crack"] + 0.6, -11)]:
    place(ice_crack(), tc, lv, rng.uniform(-0.5, 0.5), rev=0.4)
place(np.vstack([shatter_layer(), shatter_layer()]), C["shatter"], -9, rev=0.6)
place(stereo(boom, 4.0, 110, 28, 0.25, 1.4), C["shatter"], -6, rev=0.4)

# ---- ACT III · the bottle ----------------------------------------------------------
# in the dark: a low pulse at the coming tempo
beat = 60.0 / C["bpm"]
for k in range(int((C["drop"] - (C["bottleIn"] + 0.7)) / beat)):
    tb = C["drop"] - (k + 1) * beat
    if tb < C["bottleIn"] + 0.5:
        break
    lvl = -18 - 10 * (k / 8)
    place(heartbeat()[: ns(0.4)] * env_fade(ns(0.4), 0.0, 0.15), tb, lvl, rev=0.2)
dark = stereo(pad, C["drop"] - C["bottleIn"], [D1, D2, A2], 150, 900, 0.12, 3)
dark *= env_fade(dark.shape[1], 1.5, 0.12)
place(dark, C["bottleIn"], -16, rev=0.4)
place(whoosh(2.0, 300, 2500, q=0.7, peak=0.5, pan0=-0.8, pan1=0.6), C["bottleIn"] + 1.4, -24, rev=0.5)
place(stereo(riser, 2.4, 300, 9000, 110, 2.0), C["drop"] - 0.15 - 2.4, -17, rev=0.25)
place(stereo(reverse_swell, 1.0), C["drop"] - 0.15 - 1.0, -18)

# THE DROP: 120 BPM
kicks = [C["drop"] + k * beat for k in range(int(round((C["beatEnd"] - C["drop"]) / beat)) + 0)]
duck = sidechain(kicks)
for tk in kicks:
    place(kick(), tk, -6)
for k in range(len(kicks)):
    tb = C["drop"] + k * beat
    if k % 2 == 1:
        place(clap(), tb, -14, 0.0, rev=0.35)
    place(hat(), tb + beat / 2, -22, 0.25)
    place(hat(0.05, 0.012), tb + beat / 4, -31, -0.3)
    place(hat(0.05, 0.012), tb + 3 * beat / 4, -31, 0.3)
bass_notes = [D1, D1, D1, D1, D1, D1, F2 / 2, F2 / 2, C3 / 4, C3 / 4, D1]  # sub + two octaves of harmonics
for k, f in enumerate(bass_notes[: len(kicks)]):
    tb = C["drop"] + k * beat + beat / 2
    n = ns(0.24)
    t = secs(n)
    b = sine(f, n) * 0.6 + sine(2 * f, n) * 0.5 + sweep(saw(4 * f, n), "lp", 220 + 1800 * np.exp(-t / 0.05), 1.4) * 0.45
    place(np.tanh(1.6 * b) * env_fade(n, 0.003, 0.06), tb, -11)
for tb in [C["drop"], C["drop"] + 4 * beat, C["drop"] + 8 * beat]:
    stab = stereo(pad, 0.5, [D3, F3, A3, D3 * 2], 2600, 500, 0.2, 3)
    stab *= env_exp(stab.shape[1], 0.16, 0.003)
    place(stab, tb, -16, rev=0.55)
place(stereo(boom, 3.0, 110, 30, 0.2, 1.1), C["drop"], -8, rev=0.3)
place(stereo(braam, 2.0, [D1, D2, A2], 0.9, 2600), C["drop"], -16, rev=0.3)
# the beat bed under the callouts (ducked by the kick)
bed_dur = C["beatEnd"] - C["drop"]
bed = stereo(pad, bed_dur, [D2, A2, D3, F3], 900, 2200, 0.12, 3)
bed *= env_fade(bed.shape[1], 0.05, 0.4)
i0 = ns(C["drop"])
bed *= duck[i0 : i0 + bed.shape[1]][None, :]
place(bed, C["drop"], -19, rev=0.4)
# callouts: UI blips
for i, tc in enumerate(C["callouts"]):
    side = [-1, 1, -1, 1][i]
    place(fm_bell(note(["A5", "D6", "F6", "A6"][i]), 1.0, ratio=2.0, index=0.8, tau_i=0.05, tau_a=0.25), tc, -22, side * 0.6, rev=0.4)
    place(tick(), tc, -26, side * 0.6)
# turnaround into the end card
place(stereo(reverse_swell, 0.5, 1200), C["endcard"] - 0.5, -16, rev=0.3)
place(whoosh(0.6, 600, 5000, q=0.8, peak=0.85, pan0=0.0, pan1=0.0), C["endcard"] - 0.55, -20)

# ---- END CARD ------------------------------------------------------------------------
place(stereo(boom, 5.0, 100, 27, 0.3, 2.0), C["endcard"], -5, rev=0.45)
place(stereo(braam, 5.0, [D1, D2, A2, D3], 3.2, 3000), C["endcard"], -11, rev=0.5)
for nn, pan in [("D6", -0.4), ("A6", 0.4), ("D7", 0.0), ("F#6", 0.2)]:
    place(fm_bell(note(nn), 6.0, ratio=3.5, index=1.8, tau_i=0.9, tau_a=2.6), C["endcard"] + 0.02, -27, pan, rev=1.0)
place(glass_clink(), C["endcard"] + 0.75, -15, 0.15, rev=0.6)
end_dur = LEN - C["endcard"] - 0.3
ep = stereo(pad, end_dur, [D2, A2, D3, note("F#3"), A3, D3 * 2], 500, 1400, 0.1, 3)
en = ep.shape[1]
et = secs(en) + C["endcard"]
ep *= env_fade(en, 1.4, 0.0) * np.clip(1 - (et - C["fadeOut"]) / (C["fadeDone"] + 0.6 - C["fadeOut"]), 0, 1)[None, :] ** 1.5
place(ep, C["endcard"], -15, rev=0.6)
place(fm_bell(note("D5"), 5.0, ratio=1.0, index=1.0, tau_a=2.5), C["tagline"] + 0.05, -24, -0.2, rev=0.9)
place(fm_bell(note("A5"), 5.0, ratio=1.0, index=1.0, tau_a=2.5), C["tagline"] + 0.4, -26, 0.2, rev=0.9)

# ============================================================================= reverb + master
def make_ir(dur=3.6, seed=11):
    r = np.random.default_rng(seed)
    n = ns(dur)
    t = secs(n)
    ir = np.zeros((2, n))
    for ch in range(2):
        nz = r.standard_normal(n)
        acc = np.zeros(n)
        for lo, hi, rt in [(None, 350, 3.4), (350, 1800, 2.7), (1800, 6000, 1.9), (6000, None, 0.9)]:
            x = nz
            if lo:
                x = filt(x, "hp", lo, 0.6)
            if hi:
                x = filt(x, "lp", hi, 0.6)
            acc += x * np.exp(-6.91 * t / rt)
        for _ in range(14):  # early reflections
            i = int(r.uniform(0.004, 0.07) * SR)
            acc[i] += r.uniform(-1, 1) * 6
        acc *= np.minimum(1, t / 0.008)
        ir[ch] = acc
    pre = ns(0.018)
    ir = np.pad(ir, ((0, 0), (pre, 0)))[:, :n]
    return ir / np.sqrt((ir ** 2).sum(axis=1, keepdims=True))


ir = make_ir()
rev = np.vstack([signal.fftconvolve(wet[c], ir[c])[:N] for c in range(2)])
mix = dry + rev * 0.55

# master: tidy lows, a touch of air, glue compression, then a soft limiter
def compress(x, thr_db=-20.0, ratio=2.4, att=0.01, rel=0.25):
    p = np.mean(x ** 2, axis=0)
    a = 1 - np.exp(-1 / (0.02 * SR))
    env = np.sqrt(np.maximum(signal.lfilter([a], [1, -(1 - a)], p), 1e-12))
    over = np.maximum(20 * np.log10(env) - thr_db, 0)
    gr = -over * (1 - 1 / ratio)
    # attack/release smoothing of the gain (dB), forward then a light backward pass
    ka, kr = 1 - np.exp(-1 / (att * SR)), 1 - np.exp(-1 / (rel * SR))
    g = signal.lfilter([kr], [1, -(1 - kr)], gr)
    g = np.minimum(g, signal.lfilter([ka], [1, -(1 - ka)], gr[::-1])[::-1])
    return x * 10 ** (g / 20)


mix = filt(mix, "hp", 24, 0.7)
mix = compress(mix, thr_db=-26.0, ratio=2.6)
mix = filt(mix, "highshelf", 9000, 0.7, 1.5)
mix = filt(mix, "peak", 300, 0.8, -1.5)
peak = np.max(np.abs(mix))
mix = mix / peak * 1.6
mix = np.tanh(mix) / np.tanh(1.6)
mix *= 10 ** (-1.0 / 20) / np.max(np.abs(mix))
# global fade (picture fades by 49 s)
t = secs(N)
mix *= np.clip((LEN - 0.05 - t) / 0.4, 0, 1)

out = os.path.join(HERE, "soundtrack.wav")
pcm = np.clip(mix.T, -1, 1)
wavfile.write(out, SR, (pcm * (2 ** 31 - 1)).astype(np.int32))
rms = lambda a, b: 20 * np.log10(np.sqrt(np.mean(mix[:, ns(a) : ns(b)] ** 2)) + 1e-12)
print(f"wrote {out}  {LEN:.1f}s")
for a, b, name in [(0, 2.7, "epigraph"), (2.7, 8, "forest"), (8, 12, "stag"), (12, 13, "ignite"), (13, 20, "56"), (20, 26, "365"),
                   (26, 31.3, "frost"), (31.3, 36, "bottle"), (36, 41.5, "drop"), (42, 47, "end")]:
    print(f"  {name:9s} {rms(a, b):6.1f} dBFS rms")
