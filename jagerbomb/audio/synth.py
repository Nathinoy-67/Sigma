"""DSP primitives and synthesized sound-design instruments (no samples).

Shared by the score/mix scripts. Everything works on float64 arrays at SR.
"""
import numpy as np
from scipy import signal

SR = 48000
rng = np.random.default_rng(1934)


class Mixer:
    """A stereo dry bus plus a reverb send, both of fixed length."""

    def __init__(self, seconds):
        self.N = int(SR * seconds)
        self.dry = np.zeros((2, self.N))
        self.wet = np.zeros((2, self.N))

    def place(self, sig, t0, db=0.0, pan=0.0, rev=0.0):
        """Mix a mono (equal-power panned) or stereo signal in at t0 seconds."""
        g = 10 ** (db / 20)
        if sig.ndim == 1:
            a = (np.clip(pan, -1, 1) + 1) * np.pi / 4
            st = np.vstack([sig * np.cos(a), sig * np.sin(a)]) * np.sqrt(2)
        else:
            st = sig.copy()
        # de-click: 0.5 ms fade-in, 20 ms fade-out on everything
        n = st.shape[1]
        fi, fo = min(n, ns(0.0005)), min(n, ns(0.02))
        st[:, :fi] *= np.linspace(0, 1, fi)[None, :]
        st[:, n - fo :] *= np.linspace(1, 0, fo)[None, :]
        i0 = int(round(t0 * SR))
        if i0 < 0:
            st = st[:, -i0:]
            i0 = 0
        n = min(st.shape[1], self.N - i0)
        if n <= 0:
            return
        self.dry[:, i0 : i0 + n] += st[:, :n] * g
        if rev > 0:
            self.wet[:, i0 : i0 + n] += st[:, :n] * g * rev


# ----------------------------------------------------------------------------- basics
def secs(n):
    return np.arange(n) / SR


def ns(d):
    return max(1, int(round(d * SR)))


def noise(n):
    return rng.standard_normal(n)


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






def sidechain(n, times, depth=0.65, release=0.16):
    """Gain curve (length n) that ducks after each trigger time."""
    g = np.ones(n)
    for tk in times:
        i = ns(tk)
        m = min(n - i, ns(release * 6))
        if m > 0:
            g[i : i + m] = np.minimum(g[i : i + m], 1 - depth * np.exp(-secs(m) / release))
    return g


def make_ir(dur=3.6, seed=11, rt=(3.4, 2.7, 1.9, 0.9), predelay=0.018):
    """Synthetic stereo hall impulse response with frequency-dependent decay."""
    r = np.random.default_rng(seed)
    n = ns(dur)
    t = secs(n)
    ir = np.zeros((2, n))
    for ch in range(2):
        nz = r.standard_normal(n)
        acc = np.zeros(n)
        for (lo, hi), rt60 in zip([(None, 350), (350, 1800), (1800, 6000), (6000, None)], rt):
            x = nz
            if lo:
                x = filt(x, "hp", lo, 0.6)
            if hi:
                x = filt(x, "lp", hi, 0.6)
            acc += x * np.exp(-6.91 * t / rt60)
        for _ in range(14):  # early reflections
            i = int(r.uniform(0.004, 0.07) * SR)
            acc[i] += r.uniform(-1, 1) * 6
        acc *= np.minimum(1, t / 0.008)
        ir[ch] = acc
    pre = ns(predelay)
    ir = np.pad(ir, ((0, 0), (pre, 0)))[:, :n]
    return ir / np.sqrt((ir ** 2).sum(axis=1, keepdims=True))


def convolve(x, ir):
    return np.vstack([signal.fftconvolve(x[c], ir[c])[: x.shape[1]] for c in range(2)])


def compress(x, thr_db=-20.0, ratio=2.4, att=0.01, rel=0.25, key=None):
    """Feed-forward RMS compressor (optionally keyed by another signal)."""
    k = x if key is None else key
    p = np.mean(k ** 2, axis=0)
    a = 1 - np.exp(-1 / (0.02 * SR))
    env = np.sqrt(np.maximum(signal.lfilter([a], [1, -(1 - a)], p), 1e-12))
    over = np.maximum(20 * np.log10(env) - thr_db, 0)
    gr = -over * (1 - 1 / ratio)
    ka, kr = 1 - np.exp(-1 / (att * SR)), 1 - np.exp(-1 / (rel * SR))
    g = signal.lfilter([kr], [1, -(1 - kr)], gr)
    g = np.minimum(g, signal.lfilter([ka], [1, -(1 - ka)], gr[::-1])[::-1])
    return x * 10 ** (g / 20)


# ----------------------------------------------------------------------------- the Jägerbomb
def fizz(dur, density=900, bright=1.0):
    """Carbonation: a soft hiss carrying thousands of tiny bubble pops."""
    n = ns(dur)
    x = filt(filt(noise(n), "hp", 3500), "lp", 11000) * 0.05 * bright
    m_ = int(density * dur)
    for ti in rng.uniform(0, dur, m_):
        i = ns(ti)
        k = min(n - i, ns(0.006))
        if k <= 4:
            continue
        f = rng.uniform(2500, 9000) * bright
        x[i:i + k] += np.sin(2 * np.pi * f * secs(k)) * np.exp(-secs(k) / rng.uniform(0.0008, 0.0025)) * rng.uniform(0.05, 0.4)
    return x


def pour(dur, flow=1.0):
    """A stream of liquid into a glass: a gurgling band of noise, bubbles and a rising fill pitch."""
    n = ns(dur)
    t = secs(n)
    u = t / dur
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * (9 + 4 * np.sin(2 * np.pi * 0.7 * t)) * t)
    body = sweep(noise(n), "bp", 500 + 900 * u + 200 * np.sin(2 * np.pi * 3.1 * t), 1.4) * lfo * 1.6
    splash = filt(noise(n), "hp", 2500) * (0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 13 * t))) * 0.35
    x = (body + splash) * flow
    for ti in rng.uniform(0, dur, int(55 * dur)):  # bubbles, rising in pitch as the glass fills
        b = bloop(rng.uniform(200, 380) * (1 + 1.2 * ti / dur), rng.uniform(600, 1100) * (1 + ti / dur), rng.uniform(0.03, 0.08))
        i = ns(ti)
        k = min(n - i, len(b))
        x[i:i + k] += b[:k] * rng.uniform(0.1, 0.4)
    return x * env_fade(n, 0.05, 0.25)


def plunge(slow=1.0):
    """The shot glass hitting the drink: a heavy plop, a splash, a burst of bubbles.
    slow > 1 renders it in slow motion (lower, longer)."""
    d = 1.6
    n = ns(d)
    t = secs(n)
    thump = sine(110 * np.exp(-t / 0.05) + 45, n) * env_exp(n, 0.12, 0.002) * 1.2
    plop = sine(260 * np.exp(-t / 0.035) + 140, n) * env_exp(n, 0.06, 0.001) * 0.7
    spl = filt(noise(n), "bp", 2600, 0.6) * env_exp(n, 0.22, 0.003) * 1.1
    spl += filt(noise(n), "hp", 5000) * env_exp(n, 0.08, 0.001) * 0.5
    x = thump + plop + spl
    for ti in np.sort(rng.exponential(0.15, 60)):
        b = bloop(rng.uniform(250, 600), rng.uniform(700, 1500), rng.uniform(0.02, 0.06))
        i = ns(0.03 + ti)
        if i >= n:
            continue
        k = min(n - i, len(b))
        x[i:i + k] += b[:k] * rng.uniform(0.08, 0.35)
    if slow != 1.0:
        x = signal.resample_poly(x, int(round(100 * slow)), 100)
    return x


def droplet_hit(level=1.0):
    """A single drop falling into liqueur: a bright 'plink' with a dark body."""
    n = ns(1.2)
    t = secs(n)
    x = sine(1150 * np.exp(-t / 0.02) + 520, n) * env_exp(n, 0.07, 0.0008) * 0.9
    x += sine(90 + 60 * np.exp(-t / 0.03), n) * env_exp(n, 0.18, 0.002) * 0.8
    x += filt(noise(n), "bp", 3200, 1.2) * env_exp(n, 0.03, 0.0005) * 0.5
    return x * level


def pluck(f, dur=0.25, bright=2600):
    """A synth pluck for the energy arpeggio: detuned saws through a decaying low-pass."""
    n = ns(dur)
    t = secs(n)
    x = saw(f, n, rng.random()) + saw(f * 1.006, n, rng.random()) * 0.8 + saw(f * 0.5, n) * 0.4
    fc = 300 + bright * np.exp(-t / 0.06)
    return sweep(x * 0.35, "lp", fc, 1.4) * env_exp(n, 0.12, 0.002)


def sub_bass(f, dur):
    n = ns(dur)
    t = secs(n)
    x = sine(f, n) + 0.3 * np.tanh(3 * sine(f, n))
    return x * np.minimum(1, t / 0.005) * np.clip((dur - t) / 0.03, 0, 1)
