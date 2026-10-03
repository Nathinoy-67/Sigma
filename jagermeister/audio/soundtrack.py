#!/usr/bin/env python3
"""Soundtrack v2: orchestral score + synthesized sound design + English voice-over, mixed and mastered.

    python3 audio/soundtrack.py   ->  audio/soundtrack.wav (48 kHz, 24-bit)

Inputs: audio/cues.json (exported from src/timeline.js), audio/vo/*.wav (audio/voiceover.py),
the MuseScore General SoundFont (score.py) and FluidSynth.
"""
import json
import os
import sys

import numpy as np
import soundfile as sf
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import synth as S  # noqa: E402
from score import render_stems  # noqa: E402

C = json.load(open(os.path.join(HERE, "cues.json")))
SR = S.SR
LEN = C["DURATION"]
N = int(SR * LEN)
note, ns, secs = S.note, S.ns, S.secs


def tidy(x):
    return np.nan_to_num(x)


# ============================================================================= 1 · orchestra
print("rendering orchestral stems…")
stems = render_stems(C, LEN)
STEM_MIX = {  # gain dB, reverb send
    "strings": (0.0, 0.55),
    "brass": (-1.0, 0.45),
    "choir": (-3.0, 0.7),
    "keys": (-4.0, 0.6),
    "perc": (-0.5, 0.3),
}
ref = max(np.abs(s).max() for s in stems.values())
music = np.zeros((2, N))
music_wet = np.zeros((2, N))
for name, s in stems.items():
    g, rv = STEM_MIX[name]
    s = s / ref * 10 ** (g / 20)
    if name == "strings":
        s = S.filt(s, "lowshelf", 120, 0.7, 1.5)
    if name == "perc":
        s = S.filt(s, "lowshelf", 90, 0.7, 3.0)  # weight for timpani/taiko
    music += s
    music_wet += s * rv

# ============================================================================= 2 · sound design
fx = S.Mixer(LEN)
D1, A1, D2, F2, A2, D3, A3 = (note(x) for x in ["D1", "A1", "D2", "F2", "A2", "D3", "A3"])

# title: wind, a slow heartbeat, a breath of shimmer
wn = ns(13.0)
gust = 0.5 + 0.5 * np.sin(2 * np.pi * secs(wn) * 0.13) * np.sin(2 * np.pi * secs(wn) * 0.051 + 1)
wind = np.vstack([S.sweep(S.noise(wn), "bp", 360 + 300 * gust, 0.5) * gust * S.env_fade(wn, 2.0, 2.5) for _ in range(2)])
fx.place(wind, 0.0, -22)
for tb in (0.9, 2.15, 3.3):
    fx.place(S.heartbeat(), tb, -15, rev=0.15)
sub = S.stereo(S.pad, 4.6, [D1, D2], 120, 260, 0.1, 3)
fx.place(sub * S.env_fade(sub.shape[1], 1.5, 0.6), 0.0, -14)

# the flight: trees rushing past
for i, tb in enumerate([4.7, 5.5, 6.25, 6.9, 7.6, 8.25, 8.9, 9.5, 10.1, 10.7]):
    side = -1 if i % 2 == 0 else 1
    fx.place(S.whoosh(0.7, 500, 2600, q=0.8, peak=0.55, pan0=side * 0.2, pan1=side * 0.95), tb, -25 + 2 * (i % 3 == 0), rev=0.2)
air = np.vstack([S.sweep(S.noise(ns(7.4)), "bp", np.linspace(500, 1400, ns(7.4)), 0.7) for _ in range(2)])
fx.place(air * S.env_fade(air.shape[1], 1.0, 1.6), 4.4, -28)

# the stag: a riser and an inhale into the light
fx.place(S.stereo(S.riser, 2.6, 300, 6000, 0, 1), C["ignite"] - 2.6, -26, rev=0.3)
fx.place(S.stereo(S.reverse_swell, 1.0), C["ignite"] - 1.0, -19, rev=0.3)
fx.place(S.stereo(S.boom, 4.5), C["ignite"], -7, rev=0.3)
fx.place(S.stereo(S.braam, 3.5, [D1, D2, A2, D3]), C["ignite"], -16, rev=0.4)
fx.place(S.stereo(S.reverse_swell, 0.7, 1500), C["burst"] - 0.7, -20, rev=0.3)

# burst: glitter cascade + a swirling resonance as the botanicals gather
fx.place(S.stereo(S.boom, 3.0, 120, 34, 0.15, 1.0), C["burst"], -11, rev=0.3)
fx.place(S.whoosh(1.4, 7000, 260, q=0.9, peak=0.05, pan0=0.0, pan1=0.0), C["burst"], -15, rev=0.4)
for tb in S.sample_times(C["burst"], C["burst"] + 3.0, 360, lambda x: np.exp(-(x - C["burst"]) / 0.9) + 0.12):
    fx.place(S.ping(S.rng.uniform(2600, 9500), S.rng.uniform(0.015, 0.07)), tb, -36 + S.rng.uniform(-8, 0), S.rng.uniform(-0.95, 0.95), rev=0.5)
sn = ns(3.0)
st = secs(sn)
swirl = S.sweep(S.noise(sn), "bp", 500 * 2 ** (2.6 * np.sin(np.pi * st / 3.0)), 3.0) * np.sin(np.pi * st / 3.0) ** 1.5 * 1.8
ang = (np.sin(2 * np.pi * st * 0.9) + 1) * np.pi / 4
fx.place(np.vstack([swirl * np.cos(ang), swirl * np.sin(ang)]) * np.sqrt(2), C["burst"] + 0.3, -25, rev=0.5)

# the gust and the whip into the liqueur
fx.place(S.whoosh(1.4, 400, 2400, q=0.7, peak=0.75, pan0=-0.9, pan1=0.9), C["disperse"] - 0.1, -16, rev=0.3)
fx.place(S.whoosh(0.42, 1500, 6000, q=0.9, peak=0.7, pan0=-0.6, pan1=0.9), C["whip"] - 0.32, -14, rev=0.2)
fx.place(S.stereo(S.boom, 2.5, 70, 32, 0.2, 0.9), C["whip"], -15, rev=0.3)
for _ in range(14):
    fx.place(S.bloop(S.rng.uniform(140, 260), S.rng.uniform(400, 700), S.rng.uniform(0.06, 0.12)), C["whip"] + S.rng.uniform(0, 0.5), -27, S.rng.uniform(-0.7, 0.7), rev=0.3)

# 365: liquid ambience, bubbles, the counter's ticks and the oak knock
ld = C["shatter"] - C["whip"]
rumble = S.stereo(lambda: S.filt(S.noise(ns(ld)), "lp", 160, 0.7) * S.env_fade(ns(ld), 0.5, 1.0))
fx.place(rumble, C["whip"], -24)
for tb in S.sample_times(C["whip"] + 0.6, C["freeze"] + 0.4, 16, lambda x: np.ones_like(x)):
    fx.place(S.bloop(S.rng.uniform(120, 220), S.rng.uniform(380, 650), S.rng.uniform(0.07, 0.14)), tb, -30, S.rng.uniform(-0.8, 0.8), rev=0.4)
cs, ce = C["countStart"], C["countEnd"]
last = -1
for x in np.linspace(cs, ce, 4000):
    u = (x - cs) / (ce - cs)
    cnt = round((1 - (1 - u) ** 4) * 365)
    if cnt // 7 != last:
        last = cnt // 7
        fx.place(S.tick(), x, -28, S.rng.uniform(-0.2, 0.2), rev=0.15)
fx.place(S.knock(), ce, -13, 0.0, rev=0.5)

# ice: crackles growing, the freeze swell, cracks, the shatter
fx.place(S.stereo(S.reverse_swell, 1.6, 2500), C["freeze"] - 0.4, -25, rev=0.5)
for tb in S.sample_times(C["freeze"] + 0.2, C["crack"], 160, lambda x: 0.2 + ((x - C["freeze"]) / (C["crack"] - C["freeze"])) ** 1.5):
    n_ = ns(0.06)
    xx = S.filt(S.noise(n_) * S.env_exp(n_, S.rng.uniform(0.001, 0.004), 0.0002), "bp", S.rng.uniform(2200, 9000), S.rng.uniform(3, 12)) * 3
    fx.place(xx, tb, -25 + S.rng.uniform(-9, 0), S.rng.uniform(-1, 1), rev=0.3)
fx.place(S.stereo(S.riser, C["shatter"] - C["crack"] + 0.3, 600, 9000, 220, 1.5), C["crack"] - 0.3, -21, rev=0.3)
for tc, lv in [(C["crack"], -15), (C["crack"] + 0.22, -13), (C["crack"] + 0.42, -12), (C["crack"] + 0.58, -11)]:
    fx.place(S.ice_crack(), tc, lv, S.rng.uniform(-0.5, 0.5), rev=0.4)
fx.place(np.vstack([S.shatter_layer(), S.shatter_layer()]), C["shatter"], -8, rev=0.6)
fx.place(S.stereo(S.boom, 4.0, 110, 28, 0.25, 1.4), C["shatter"], -6, rev=0.4)
for tb in S.sample_times(C["shatter"] + 0.2, C["shatter"] + 1.6, 70, lambda x: np.exp(-(x - C["shatter"]) / 0.5)):
    fx.place(S.ping(S.rng.uniform(3000, 10000), S.rng.uniform(0.01, 0.05)), tb, -32, S.rng.uniform(-1, 1), rev=0.5)

# the bottle: a light sweep, a dark rise, a breath before the drop
fx.place(S.whoosh(2.0, 300, 2500, q=0.7, peak=0.5, pan0=-0.8, pan1=0.6), C["bottleIn"] + 1.6, -25, rev=0.5)
fx.place(S.stereo(S.riser, 2.2, 300, 9000, 110, 2.0), C["drop"] - 0.2 - 2.2, -19, rev=0.25)
fx.place(S.stereo(S.reverse_swell, 0.9), C["drop"] - 0.2 - 0.9, -19)

# the drop: hybrid percussion layer on the orchestra
beat = 60.0 / C["bpm"]
kicks = list(np.arange(C["drop"], C["beatEnd"] - 0.01, beat))
for tk in kicks:
    fx.place(S.kick(), tk, -9)
for i, tb in enumerate(kicks):
    if i % 2 == 1:
        fx.place(S.clap(), tb, -19, 0.0, rev=0.35)
    fx.place(S.hat(), tb + beat / 2, -25, 0.25)
fx.place(S.stereo(S.boom, 3.0, 110, 30, 0.2, 1.1), C["drop"], -9, rev=0.3)
fx.place(S.stereo(S.braam, 2.0, [D1, D2, A2], 0.9, 2600), C["drop"], -19, rev=0.3)
for i, tc in enumerate(C["callouts"]):
    side = [-1, 1, -1, 1][i]
    fx.place(S.fm_bell(note(["A5", "D6", "F6", "A6"][i]), 1.0, ratio=2.0, index=0.8, tau_i=0.05, tau_a=0.25), tc, -25, side * 0.6, rev=0.4)
fx.place(S.stereo(S.reverse_swell, 0.5, 1200), C["endcard"] - 0.5, -18, rev=0.3)

# end card
fx.place(S.stereo(S.boom, 3.0, 100, 27, 0.3, 0.9), C["endcard"], -7, rev=0.35)
fx.place(S.stereo(S.braam, 1.6, [D1, D2, A2, D3], 0.7, 2800), C["endcard"], -18, rev=0.4)
fx.place(S.glass_clink(), 57.2, -20, 0.15, rev=0.6)

fx_mix = fx.dry
fx_wet = fx.wet

# ============================================================================= 3 · voice-over
vo = np.zeros((2, N))
vo_meta = json.load(open(os.path.join(HERE, "vo", "lines.json")))
vo_active = np.zeros(N)
DUCK_DB = {"brand": 11.0, "tagline": 8.0}  # deeper under the brand name and the tagline
for key, t0 in C["vo"].items():
    y, sr = sf.read(os.path.join(HERE, "vo", f"{key}.wav"))
    y = signal.resample_poly(y, SR, sr)
    # broadcast-style chain: tidy lows, chest, less box, presence, air
    y = S.filt(y, "hp", 70, 0.7)
    y = S.filt(y, "lowshelf", 150, 0.7, 2.5)
    y = S.filt(y, "peak", 380, 1.2, -2.5)
    y = S.filt(y, "peak", 3200, 0.9, 3.5)
    y = S.filt(y, "highshelf", 7500, 0.7, 3.0)
    y = y / (np.abs(y).max() + 1e-9)
    i0 = int(round(t0 * SR))
    n = min(len(y), N - i0)
    vo[:, i0 : i0 + n] += y[:n]
    vo_active[i0 : i0 + n] = DUCK_DB.get(key, 5.0)
vo = S.compress(vo, thr_db=-26.0, ratio=3.0, att=0.004, rel=0.12) * 10 ** (8 / 20)
vo = np.tanh(vo * 1.1) / 1.1
vo_ir = S.make_ir(1.6, seed=5, rt=(1.3, 1.1, 0.8, 0.4), predelay=0.012)
vo_wet = S.convolve(vo, vo_ir)

# duck music + sound design under the voice: attack 120 ms (with 150 ms look-ahead), release 450 ms,
# computed at a 1 kHz control rate
CR = 1000
act = vo_active[:: SR // CR]
act = np.concatenate([act[int(0.15 * CR) :], np.zeros(int(0.15 * CR))])
env = np.zeros_like(act)
ka, kr, e = 1 - np.exp(-1 / (0.12 * CR)), 1 - np.exp(-1 / (0.45 * CR)), 0.0
for i, v in enumerate(act):
    e += (v - e) * (ka if v > e else kr)
    env[i] = e
env = np.interp(np.arange(N) / SR, np.arange(len(env)) / CR, env)
duck = 10 ** (-env / 20)

# ============================================================================= 4 · mix + master
ir = S.make_ir(3.4)
bed = music * duck + fx_mix * (0.6 + 0.4 * duck)
bed_wet = (music_wet * 0.8 + fx_wet) * duck
mix = bed + S.convolve(bed_wet, ir) * 0.5 + vo + vo_wet * 0.12
mix = tidy(mix)
mix = S.filt(mix, "hp", 24, 0.7)
mix = S.filt(mix, "peak", 300, 0.8, -1.0)
mix = S.compress(mix, thr_db=-24.0, ratio=2.2)
peak = np.max(np.abs(mix))
mix = mix / peak * 1.7
mix = np.tanh(mix) / np.tanh(1.7)
mix *= 10 ** (-1.0 / 20) / np.max(np.abs(mix))
t = secs(N)
mix *= np.clip((LEN - 0.05 - t) / 0.6, 0, 1)

if os.environ.get("DUMP"):  # components for analysis
    d = os.environ["DUMP"]
    os.makedirs(d, exist_ok=True)
    for nm, x in [("music", music * duck), ("fx", fx_mix), ("vo", vo)] + [(k, v) for k, v in stems.items()]:
        sf.write(os.path.join(d, nm + ".wav"), (x / (np.abs(x).max() + 1e-9) * 0.5).T.astype(np.float32), SR)
    np.save(os.path.join(d, "levels.npy"), np.array([np.abs(music * duck).max(), np.abs(fx_mix).max(), np.abs(vo).max()]))

out = os.path.join(HERE, "soundtrack.wav")
sf.write(out, mix.T.astype(np.float32), SR, subtype="PCM_24")
print("wrote", out)
rms = lambda a_, b_: 20 * np.log10(np.sqrt(np.mean(mix[:, ns(a_) : ns(b_)] ** 2)) + 1e-12)
for a_, b_, name in [(0, 4.4, "title"), (4.4, 11.6, "flight"), (11.6, 16, "stag"), (16, 17.3, "ignite"), (17.3, 25, "56"), (25, 30.6, "365"),
                     (30.6, 35.6, "ice"), (35.6, 41.8, "bottle"), (41.8, 47.8, "drop"), (47.8, 57, "end")]:
    print(f"  {name:7s} {rms(a_, b_):6.1f} dBFS rms")
