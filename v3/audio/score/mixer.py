"""mixer.py -- DSP for the PATIENCE score: filters, convolution hall/room, gates, linked bus
compressor, true-peak limiter, loudness normalisation.  Arrays are float32/float64 (2, n) at 48 kHz.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.ndimage import maximum_filter1d, minimum_filter1d
from scipy.signal import butter, fftconvolve, lfilter, resample_poly, sosfilt, sosfiltfilt

SR = 48000


# --------------------------------------------------------------------------- filters
def hp(x, f, order=2, sr=SR):
    return sosfilt(butter(order, f, 'highpass', fs=sr, output='sos'), x, axis=-1)


def lp(x, f, order=2, sr=SR):
    return sosfilt(butter(order, f, 'lowpass', fs=sr, output='sos'), x, axis=-1)


def bp(x, lo, hi, order=2, sr=SR):
    return sosfilt(butter(order, [lo, hi], 'bandpass', fs=sr, output='sos'), x, axis=-1)


def _biquad(kind, f0, gain_db, q, sr=SR):
    """RBJ cookbook biquads: 'peak', 'lowshelf', 'highshelf'."""
    A = 10 ** (gain_db / 40)
    w0 = 2 * math.pi * f0 / sr
    cw, sw = math.cos(w0), math.sin(w0)
    alpha = sw / (2 * q)
    if kind == 'peak':
        b = [1 + alpha * A, -2 * cw, 1 - alpha * A]
        a = [1 + alpha / A, -2 * cw, 1 - alpha / A]
    elif kind == 'lowshelf':
        s = 2 * math.sqrt(A) * alpha
        b = [A * ((A + 1) - (A - 1) * cw + s), 2 * A * ((A - 1) - (A + 1) * cw), A * ((A + 1) - (A - 1) * cw - s)]
        a = [(A + 1) + (A - 1) * cw + s, -2 * ((A - 1) + (A + 1) * cw), (A + 1) + (A - 1) * cw - s]
    elif kind == 'highshelf':
        s = 2 * math.sqrt(A) * alpha
        b = [A * ((A + 1) + (A - 1) * cw + s), -2 * A * ((A - 1) + (A + 1) * cw), A * ((A + 1) + (A - 1) * cw - s)]
        a = [(A + 1) - (A - 1) * cw + s, 2 * ((A - 1) - (A + 1) * cw), (A + 1) - (A - 1) * cw - s]
    else:
        raise ValueError(kind)
    b, a = np.array(b) / a[0], np.array(a) / a[0]
    return b, a


def eq(x, bands):
    """bands: [(kind, f0, gain_db, q)]; kind in peak/lowshelf/highshelf."""
    y = np.asarray(x, np.float64)
    for kind, f0, g, q in bands:
        b, a = _biquad(kind, f0, g, q)
        y = lfilter(b, a, y, axis=-1)
    return y


def db(x):
    return 10 ** (x / 20.0)


def to_stereo(m):
    m = np.asarray(m, np.float64)
    return np.stack([m, m]) if m.ndim == 1 else m


def pan_mono(m, pan=0.0, width_delay_ms=0.0):
    """Constant-power pan of a mono signal (-1..1), optional Haas-style micro delay for width."""
    th = (pan + 1) * math.pi / 4
    L, R = m * math.cos(th) * math.sqrt(2), m * math.sin(th) * math.sqrt(2)
    if width_delay_ms:
        d = int(abs(width_delay_ms) * SR / 1000)
        if width_delay_ms > 0:
            R = np.concatenate([np.zeros(d), R[:-d]]) if d else R
        else:
            L = np.concatenate([np.zeros(d), L[:-d]]) if d else L
    return np.stack([L, R])


# --------------------------------------------------------------------------- reverbs
def hall_ir(rt60=2.6, predelay=0.025, seed=7, length=None, hp_f=90.0, lp_f=9500.0, er=True):
    """Synthetic stereo concert-hall IR: early reflections (image-source-like taps, both
    channels, 5-80 ms), then a decorrelated diffuse tail with frequency-dependent decay
    (lows 1.2x, mids 1x, highs 0.5x of RT60), soft 40 ms build-up; pre-delay in front."""
    rng = np.random.default_rng(seed)
    L = int(SR * (length or min(rt60 * 1.4, 6.0)))
    t = np.arange(L) / SR
    ir = np.zeros((2, L))
    for lo, hi, k in [(None, 250, 1.2), (250, 1200, 1.05), (1200, 4500, 0.8), (4500, None, 0.5)]:
        for c in range(2):
            nz = rng.standard_normal(L)
            if lo and hi:
                sos = butter(2, [lo, hi], 'bandpass', fs=SR, output='sos')
            elif lo:
                sos = butter(2, lo, 'highpass', fs=SR, output='sos')
            else:
                sos = butter(2, hi, 'lowpass', fs=SR, output='sos')
            ir[c] += sosfilt(sos, nz) * np.exp(-6.9078 * t / (rt60 * k))
    ir *= np.minimum(1.0, (t / 0.04) ** 1.5)
    if er:
        for _ in range(26):
            d = rng.uniform(0.005, 0.08)
            g = rng.uniform(0.25, 0.7) * math.exp(-d / 0.06)
            c = rng.integers(0, 2)
            i = int(d * SR)
            ir[c, i] += g * rng.choice([-1, 1])
            ir[1 - c, min(L - 1, i + int(rng.uniform(0.0003, 0.002) * SR))] += 0.6 * g * rng.choice([-1, 1])
    pd = int(predelay * SR)
    ir = np.concatenate([np.zeros((2, pd)), ir], axis=1)
    ir = sosfilt(butter(2, [hp_f, lp_f], 'bandpass', fs=SR, output='sos'), ir, axis=1)
    ir /= np.sqrt(np.sum(ir ** 2) / 2)
    return ir


def room_ir(rt60=0.35, predelay=0.004, seed=3):
    """Short small-room IR for the foley (wood/plaster room, ~0.35 s)."""
    return hall_ir(rt60=rt60, predelay=predelay, seed=seed, length=rt60 * 1.5, hp_f=150.0, lp_f=8000.0)


def convolve(x, ir, cross=0.12):
    """Stereo convolution (L->L, R->R plus a little cross-feed), output length = len(x)."""
    x = np.asarray(x, np.float64)
    n = x.shape[1]
    yl = fftconvolve(x[0], ir[0])[:n] + cross * fftconvolve(x[1], ir[0])[:n]
    yr = fftconvolve(x[1], ir[1])[:n] + cross * fftconvolve(x[0], ir[1])[:n]
    return np.stack([yl, yr])


# --------------------------------------------------------------------------- gates / envelopes
def gate_curve(n, segments):
    """Gain curve from [(t0, t1, g0, g1)] linear ramps (seconds); default 1."""
    g = np.ones(n)
    for t0, t1, g0, g1 in segments:
        i0, i1 = int(round(t0 * SR)), int(round(t1 * SR))
        i0, i1 = max(0, i0), min(n, i1)
        if i1 > i0:
            g[i0:i1] = np.linspace(g0, g1, i1 - i0, endpoint=False)
    return g


def zero_after(x, t, fade=0.003):
    """Hard cut: x * 0 from t (a `fade`-long cosine ramp ending exactly at t)."""
    y = np.array(x, np.float64)
    i = int(round(t * SR))
    nf = max(1, int(fade * SR))
    i0 = max(0, i - nf)
    r = 0.5 * (1 + np.cos(np.linspace(0, np.pi, i - i0)))
    y[:, i0:i] *= r
    y[:, i:] = 0.0
    return y


def zero_before(x, t, fade=0.0):
    y = np.array(x, np.float64)
    i = int(round(t * SR))
    y[:, :i] = 0.0
    if fade > 0:
        nf = int(fade * SR)
        y[:, i:i + nf] *= np.linspace(0, 1, nf)
    return y


# --------------------------------------------------------------------------- dynamics
def _smooth_gain_db(gr_db, attack, release, rate):
    """One-pole attack/release smoothing of a gain-reduction curve (dB, >= 0) at control rate."""
    aa = math.exp(-1.0 / (attack * rate))
    ar = math.exp(-1.0 / (release * rate))
    out = np.empty_like(gr_db)
    s = 0.0
    for i, v in enumerate(gr_db):
        c = aa if v > s else ar
        s = c * s + (1 - c) * v
        out[i] = s
    return out


def compressor_gain(mix, thresh_db=-18.0, ratio=2.0, knee_db=6.0, attack=0.03, release=0.25, rms_win=0.012,
                    ctl=48):
    """Linked feed-forward RMS compressor: returns the per-sample linear gain for `mix` (2, n)."""
    x = np.asarray(mix, np.float64)
    n = x.shape[1]
    p = (x ** 2).mean(axis=0)
    w = max(1, int(rms_win * SR))
    cs = np.concatenate([[0.0], np.cumsum(p)])
    idx = np.arange(0, n, ctl)
    lo = np.maximum(0, idx - w)
    lvl = 10 * np.log10(np.maximum((cs[np.minimum(n, idx + 1)] - cs[lo]) / np.maximum(1, idx + 1 - lo), 1e-12))
    over = lvl - thresh_db
    gr = np.where(over <= -knee_db / 2, 0.0,
                  np.where(over >= knee_db / 2, over * (1 - 1 / ratio),
                           (1 - 1 / ratio) * (over + knee_db / 2) ** 2 / (2 * knee_db)))
    gr = _smooth_gain_db(gr, attack, release, SR / ctl)
    g = 10 ** (-gr / 20)
    return np.interp(np.arange(n), idx, g), float(gr.max())


def truepeak_limiter_gain(mix, ceiling_db=-1.0, lookahead=0.004, release=0.08, os=4):
    """Look-ahead limiter gain (per sample) computed on the 4x-oversampled peak envelope.

    need = ceiling / true-peak per sample; g1 = min of need over +-lookahead; slow release of g1
    at a 1 ms control rate; finally a moving average over `lookahead` so the gain ramps into each
    peak (the +-lookahead minimum guarantees the averaged gain is still <= need at the peak)."""
    from scipy.ndimage import uniform_filter1d
    x = np.asarray(mix, np.float64)
    n = x.shape[1]
    up = resample_poly(x, os, 1, axis=1)
    pk = np.abs(up).max(axis=0)
    pk = np.pad(pk, (0, max(0, n * os - len(pk))))[:n * os].reshape(n, os).max(axis=1)
    c = 10 ** (ceiling_db / 20)
    la = max(2, int(lookahead * SR))
    need = np.minimum(1.0, c / np.maximum(pk, 1e-12))
    g1 = minimum_filter1d(need, 2 * la + 1)
    ctl = 48
    m = -(-n // ctl)
    gpad = np.pad(g1, (0, m * ctl - n), constant_values=1.0).reshape(m, ctl).min(axis=1)
    ar = math.exp(-1.0 / (release * SR / ctl))
    g = np.empty(m)
    s = 1.0
    for i, v in enumerate(gpad):
        s = v if v < s else ar * s + (1 - ar) * v
        g[i] = s
    gr = np.repeat(g, ctl)[:n]
    gr = np.minimum(gr, g1)
    return np.minimum(uniform_filter1d(gr, la), 1.0)


def soft_clip(x, drive_db=0.0):
    k = db(drive_db)
    return np.tanh(x * k) / k
