"""audio_tools.py -- measurement helpers for the PATIENCE score (numpy/scipy only).

  yin_f0(x, sr, fmin, fmax, t0, t1)          median YIN fundamental (Hz) over a window
  refine_f0(x, sr, f0, t0, t1)               spectral refinement from the first harmonics
  lufs(x, sr) / loudness_curve(x, sr, win)   ITU-R BS.1770-4 integrated / momentary / short-term
  true_peak_db(x, sr)                        4x oversampled true peak (dBTP)
  band_levels(x, sr, t0, t1)                 energy per octave band (dB)
  onset_time(x, sr, t_guess, search, hp)     first sample above threshold near a guess
"""
from __future__ import annotations

import math

import numpy as np
from scipy.signal import butter, lfilter, resample_poly, sosfilt


# --------------------------------------------------------------------------- pitch
def _mono(x):
    x = np.asarray(x, np.float64)
    return x.mean(axis=0) if x.ndim == 2 else x


def yin_f0(x, sr, fmin=25.0, fmax=2000.0, t0=0.1, t1=0.6, thr=0.12, hop=0.02):
    """Median YIN f0 (de Cheveigne & Kawahara 2002) over frames in [t0, t1]. Returns (f0, aperiodicity)."""
    m = _mono(x)
    tmax = int(sr / fmin)
    tmin = max(2, int(sr / fmax))
    W = max(2048, 2 * tmax)
    f0s, aps = [], []
    i = int(t0 * sr)
    while i + W + tmax < min(len(m), int(t1 * sr) + W + tmax):
        fr = m[i:i + W + tmax]
        # difference function via FFT autocorrelation
        a = fr[:W]
        n = 1 << int(math.ceil(math.log2(len(fr) + W)))
        Fa = np.fft.rfft(a, n)
        Ff = np.fft.rfft(fr, n)
        corr = np.fft.irfft(np.conj(Fa) * Ff, n)[:tmax + 1]
        e = np.cumsum(np.concatenate([[0.0], fr ** 2]))
        energy_t = e[np.arange(tmax + 1) + W] - e[np.arange(tmax + 1)]
        d = e[W] + energy_t - 2 * corr
        d[0] = 0
        cm = np.ones_like(d)
        cs = np.cumsum(d[1:])
        cm[1:] = d[1:] * np.arange(1, tmax + 1) / np.maximum(cs, 1e-12)
        tau = None
        for t in range(tmin, tmax - 1):
            if cm[t] < thr:
                while t + 1 < tmax and cm[t + 1] < cm[t]:
                    t += 1
                tau = t
                break
        if tau is None:
            tau = tmin + int(np.argmin(cm[tmin:tmax]))
        if 1 <= tau < tmax:
            y0, y1, y2 = cm[tau - 1], cm[tau], cm[tau + 1]
            den = (y0 - 2 * y1 + y2)
            dt = 0.5 * (y0 - y2) / den if abs(den) > 1e-12 else 0.0
        else:
            dt = 0.0
        f0s.append(sr / (tau + dt))
        aps.append(cm[tau])
        i += int(hop * sr)
    if not f0s:
        return float('nan'), 1.0
    f0s, aps = np.array(f0s), np.array(aps)
    good = aps < max(0.3, np.percentile(aps, 50))
    return float(np.median(f0s[good] if good.any() else f0s)), float(np.median(aps))


def refine_f0(x, sr, f0, t0=0.1, t1=0.6, H=6):
    """Least-squares f0 from spectral peaks near h*f0 (h=1..H), weighted by magnitude."""
    m = _mono(x)[int(t0 * sr):int(t1 * sr)]
    if len(m) < 256 or not np.isfinite(f0):
        return f0
    w = np.hanning(len(m))
    n = 1 << 19
    S = np.abs(np.fft.rfft(m * w, n))
    df = sr / n
    num = den = 0.0
    for h in range(1, H + 1):
        fc = h * f0
        if fc > sr / 2 - 100:
            break
        lo, hi = int(fc * 2 ** (-0.4 / 12) / df), int(fc * 2 ** (0.4 / 12) / df)
        if hi <= lo + 2:
            continue
        k = lo + int(np.argmax(S[lo:hi]))
        if 1 <= k < len(S) - 1:
            a, b, c = np.log(S[k - 1] + 1e-12), np.log(S[k] + 1e-12), np.log(S[k + 1] + 1e-12)
            p = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else 0.0
        else:
            p = 0.0
        fk = (k + p) * df
        # weighted least squares of fk = h*f0 (weights = peak magnitude)
        num += S[k] * h * fk
        den += S[k] * h * h
    return num / den if den > 0 else f0


def hz_to_midi(f):
    return 69 + 12 * math.log2(f / 440.0)


def midi_to_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def spectral_peak(x, sr, flo, fhi, t0=0.05, t1=0.5):
    """Frequency of the strongest spectral peak between flo and fhi (for timpani / inharmonic)."""
    m = _mono(x)[int(t0 * sr):int(t1 * sr)]
    n = 1 << 19
    S = np.abs(np.fft.rfft(m * np.hanning(len(m)), n))
    df = sr / n
    lo, hi = int(flo / df), int(fhi / df)
    k = lo + int(np.argmax(S[lo:hi]))
    a, b, c = np.log(S[k - 1] + 1e-12), np.log(S[k] + 1e-12), np.log(S[k + 1] + 1e-12)
    p = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else 0.0
    return (k + p) * df


# --------------------------------------------------------------------------- loudness
def _kweight(x, sr):
    """BS.1770 K-weighting (pre-filter shelf + RLB high-pass), coefficients for any sr."""
    # stage 1: high shelf (+4 dB at high frequencies)
    f0, G, Q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    K = math.tan(math.pi * f0 / sr)
    Vh = 10 ** (G / 20)
    Vb = Vh ** 0.4996667741545416
    a0 = 1 + K / Q + K * K
    b1 = [(Vh + Vb * K / Q + K * K) / a0, 2 * (K * K - Vh) / a0, (Vh - Vb * K / Q + K * K) / a0]
    a1 = [1, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0]
    # stage 2: high-pass
    f0, Q = 38.13547087602444, 0.5003270373238773
    K = math.tan(math.pi * f0 / sr)
    a0 = 1 + K / Q + K * K
    b2 = [1, -2, 1]
    a2 = [1, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0]
    y = lfilter(b1, a1, x, axis=-1)
    return lfilter(b2, a2, y, axis=-1)


def _block_power(x, sr, win=0.4, hop=0.1):
    y = _kweight(np.atleast_2d(np.asarray(x, np.float64)), sr)
    p = y ** 2
    W, Hp = int(win * sr), int(hop * sr)
    cs = np.concatenate([np.zeros((p.shape[0], 1)), np.cumsum(p, axis=1)], axis=1)
    starts = np.arange(0, p.shape[1] - W + 1, Hp)
    z = (cs[:, starts + W] - cs[:, starts]) / W   # mean square per channel per block
    return z.sum(axis=0), starts / sr                # L+R weights 1.0


def lufs(x, sr):
    """Integrated loudness (LUFS), BS.1770-4 gating."""
    z, _ = _block_power(x, sr, 0.4, 0.1)
    lk = -0.691 + 10 * np.log10(np.maximum(z, 1e-20))
    g1 = z[lk > -70]
    if len(g1) == 0:
        return -float('inf')
    lr = -0.691 + 10 * np.log10(g1.mean()) - 10
    g2 = z[(lk > -70) & (lk > lr)]
    return float(-0.691 + 10 * np.log10(g2.mean()))


def loudness_curve(x, sr, win=0.4, hop=0.1):
    """Momentary (win=0.4) or short-term (win=3.0) loudness: (times of block ends, LUFS)."""
    z, t = _block_power(x, sr, win, hop)
    return t + win, -0.691 + 10 * np.log10(np.maximum(z, 1e-20))


def lra(x, sr):
    """Loudness range (EBU 3342): 10th-95th percentile of gated short-term loudness."""
    t, st = loudness_curve(x, sr, 3.0, 0.1)
    st = st[st > -70]
    if len(st) == 0:
        return 0.0
    z = 10 ** ((st + 0.691) / 10)
    rel = -0.691 + 10 * np.log10(z.mean()) - 20
    st = st[st > rel]
    return float(np.percentile(st, 95) - np.percentile(st, 10))


def true_peak_db(x, sr):
    y = resample_poly(np.atleast_2d(np.asarray(x, np.float64)), 4, 1, axis=1)
    return float(20 * np.log10(max(np.abs(y).max(), 1e-12)))


def sample_peak_db(x):
    return float(20 * np.log10(max(np.abs(np.asarray(x)).max(), 1e-12)))


# --------------------------------------------------------------------------- spectrum
BANDS = [(20, 40), (40, 80), (80, 160), (160, 315), (315, 630), (630, 1250), (1250, 2500), (2500, 5000),
         (5000, 10000), (10000, 20000)]


def band_levels(x, sr, t0, t1):
    """Mean power per octave band (dBFS-ish, relative), from an FFT of the window."""
    m = _mono(x)[int(t0 * sr):int(t1 * sr)]
    if len(m) < 1024:
        return [float('-inf')] * len(BANDS)
    S = np.abs(np.fft.rfft(m * np.hanning(len(m)))) ** 2
    f = np.fft.rfftfreq(len(m), 1 / sr)
    tot = S.sum()
    out = []
    for lo, hi in BANDS:
        e = S[(f >= lo) & (f < hi)].sum()
        out.append(10 * np.log10(max(e / max(tot, 1e-30), 1e-12)))
    return out


def onset_time(x, sr, t_guess, search=0.05, hp=None, rel_db=-20.0):
    """First sample within [t_guess-search, t_guess+search] where |x| exceeds rel_db below that window's peak."""
    m = _mono(x)
    if hp:
        m = sosfilt(butter(4, hp, 'highpass', fs=sr, output='sos'), m)
    i0, i1 = max(0, int((t_guess - search) * sr)), int((t_guess + search) * sr)
    w = np.abs(m[i0:i1])
    if w.max() <= 0:
        return None
    k = int(np.argmax(w >= w.max() * 10 ** (rel_db / 20)))
    return (i0 + k) / sr
