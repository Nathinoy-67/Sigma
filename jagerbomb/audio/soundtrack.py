#!/usr/bin/env python3
"""Soundtrack for "The Drop": orchestral score + synthesized sound design and club layer + English
voice-over, mixed and mastered.

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
BEAT = 60.0 / C["bpm"]

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
        s = S.filt(s, "lowshelf", 90, 0.7, 3.0)
    music += s
    music_wet += s * rv

# ============================================================================= 2 · sound design
fx = S.Mixer(LEN)
D1, A1, D2, F2, A2, D3, A3 = (note(x) for x in ["D1", "A1", "D2", "F2", "A2", "D3", "A3"])

# --- cold open: a room tone, a heartbeat, a single drop
sub = S.stereo(S.pad, 5.0, [D1, D2], 120, 240, 0.1, 3)
fx.place(sub * S.env_fade(sub.shape[1], 1.6, 1.2), 0.0, -16)
for tb in (0.5, 1.75, 2.9):
    fx.place(S.heartbeat(), tb, -17, rev=0.15)
fx.place(S.stereo(S.reverse_swell, 1.2, 900), C["dropHit"] - 1.2, -22, rev=0.4)
fx.place(S.droplet_hit(), C["dropHit"], -8, 0.0, rev=0.6)
fx.place(S.stereo(S.boom, 3.5, 80, 30, 0.2, 1.4), C["dropHit"], -11, rev=0.4)
for k in range(5):  # the ripples ring out
    fx.place(S.ping(S.rng.uniform(900, 1600), 0.12), C["dropHit"] + 0.25 + 0.3 * k, -32 - 2 * k, S.rng.uniform(-0.5, 0.5), rev=0.7)
fx.place(S.stereo(S.boom, 3.0, 70, 28, 0.25, 1.2), C["titleIn"], -16, rev=0.5)
fx.place(S.whoosh(1.6, 300, 1800, q=0.7, peak=0.6, pan0=-0.6, pan1=0.6), C["titleIn"] - 0.4, -27, rev=0.5)

# --- 1934: wind, the flight, the stag, the light
wn = ns(C["whip"] - C["forestIn"])
gust = 0.5 + 0.5 * np.sin(2 * np.pi * secs(wn) * 0.13) * np.sin(2 * np.pi * secs(wn) * 0.051 + 1)
wind = np.vstack([S.sweep(S.noise(wn), "bp", 360 + 300 * gust, 0.5) * gust * S.env_fade(wn, 2.0, 2.5) for _ in range(2)])
fx.place(wind, C["forestIn"], -25)
for i, tb in enumerate(np.arange(C["forestIn"] + 0.6, C["stagStart"] - 0.5, 0.78)):
    side = -1 if i % 2 == 0 else 1
    fx.place(S.whoosh(0.7, 500, 2600, q=0.8, peak=0.55, pan0=side * 0.2, pan1=side * 0.95), tb, -27 + 2 * (i % 3 == 0), rev=0.2)
fx.place(S.stereo(S.riser, 2.6, 300, 6000, 0, 1), C["ignite"] - 2.6, -26, rev=0.3)
fx.place(S.stereo(S.reverse_swell, 1.0), C["ignite"] - 1.0, -19, rev=0.3)
fx.place(S.stereo(S.boom, 4.5), C["ignite"], -7, rev=0.3)
fx.place(S.stereo(S.braam, 3.5, [D1, D2, A2, D3]), C["ignite"], -16, rev=0.4)
fx.place(S.stereo(S.reverse_swell, 0.7, 1500), C["burst"] - 0.7, -20, rev=0.3)
fx.place(S.stereo(S.boom, 3.0, 120, 34, 0.15, 1.0), C["burst"], -11, rev=0.3)
fx.place(S.whoosh(1.4, 7000, 260, q=0.9, peak=0.05, pan0=0.0, pan1=0.0), C["burst"], -15, rev=0.4)
for tb in S.sample_times(C["burst"], C["burst"] + 3.0, 300, lambda x: np.exp(-(x - C["burst"]) / 0.9) + 0.12):
    fx.place(S.ping(S.rng.uniform(2600, 9500), S.rng.uniform(0.015, 0.07)), tb, -36 + S.rng.uniform(-8, 0), S.rng.uniform(-0.95, 0.95), rev=0.5)
fx.place(S.whoosh(1.4, 400, 2400, q=0.7, peak=0.75, pan0=-0.9, pan1=0.9), C["disperse"] - 0.1, -17, rev=0.3)
fx.place(S.whoosh(0.42, 1500, 6000, q=0.9, peak=0.7, pan0=-0.6, pan1=0.9), C["whip"] - 0.32, -14, rev=0.2)
fx.place(S.stereo(S.boom, 2.5, 70, 32, 0.2, 0.9), C["whip"], -15, rev=0.3)

# --- oak, ice, the shatter
ld = C["shatter"] - C["whip"]
rumble = S.stereo(lambda: S.filt(S.noise(ns(ld)), "lp", 160, 0.7) * S.env_fade(ns(ld), 0.5, 1.0))
fx.place(rumble, C["whip"], -24)
for _ in range(14):
    fx.place(S.bloop(S.rng.uniform(140, 260), S.rng.uniform(400, 700), S.rng.uniform(0.06, 0.12)), C["whip"] + S.rng.uniform(0, 1.5), -28, S.rng.uniform(-0.7, 0.7), rev=0.3)
fx.place(S.stereo(S.reverse_swell, 1.6, 2500), C["freeze"] - 0.4, -25, rev=0.5)
for tb in S.sample_times(C["freeze"] + 0.2, C["crack"], 140, lambda x: 0.2 + ((x - C["freeze"]) / (C["crack"] - C["freeze"])) ** 1.5):
    n_ = ns(0.06)
    xx = S.filt(S.noise(n_) * S.env_exp(n_, S.rng.uniform(0.001, 0.004), 0.0002), "bp", S.rng.uniform(2200, 9000), S.rng.uniform(3, 12)) * 3
    fx.place(xx, tb, -25 + S.rng.uniform(-9, 0), S.rng.uniform(-1, 1), rev=0.3)
fx.place(S.stereo(S.riser, C["shatter"] - C["crack"] + 0.3, 600, 9000, 220, 1.5), C["crack"] - 0.3, -21, rev=0.3)
for tc, lv in [(C["crack"], -15), (C["crack"] + 0.2, -13), (C["crack"] + 0.38, -12), (C["crack"] + 0.52, -11)]:
    fx.place(S.ice_crack(), tc, lv, S.rng.uniform(-0.5, 0.5), rev=0.4)
fx.place(np.vstack([S.shatter_layer(), S.shatter_layer()]), C["shatter"], -8, rev=0.6)
fx.place(S.stereo(S.boom, 4.0, 110, 28, 0.25, 1.4), C["shatter"], -6, rev=0.4)
for tb in S.sample_times(C["shatter"] + 0.2, C["shatter"] + 1.6, 60, lambda x: np.exp(-(x - C["shatter"]) / 0.5)):
    fx.place(S.ping(S.rng.uniform(3000, 10000), S.rng.uniform(0.01, 0.05)), tb, -32, S.rng.uniform(-1, 1), rev=0.5)
fx.place(S.whoosh(2.0, 300, 2500, q=0.7, peak=0.5, pan0=-0.8, pan1=0.6), C["bottleIn"] + 1.0, -25, rev=0.5)

# --- the whip to America; snow and wind by the lake; a bar somewhere ahead
fx.place(S.whoosh(0.5, 1200, 6500, q=0.9, peak=0.7, pan0=-0.9, pan1=0.9), C["tahoe"] - 0.35, -13, rev=0.2)
fx.place(S.stereo(S.boom, 3.0, 60, 26, 0.3, 1.2), C["tahoe"], -13, rev=0.4)
tn_ = ns(C["fizz"] - C["tahoe"] + 0.6)
gust = 0.55 + 0.45 * np.sin(2 * np.pi * secs(tn_) * 0.21 + 0.5)
snowwind = np.vstack([S.sweep(S.noise(tn_), "bp", 700 + 500 * gust, 0.6) * gust * S.env_fade(tn_, 0.4, 0.8) for _ in range(2)])
fx.place(snowwind, C["tahoe"], -22)
fx.place(S.stereo(S.riser, C["fizz"] - C["tahoe"] - 1.0, 200, 3000, 0, 1), C["tahoe"] + 1.0, -30, rev=0.4)

# --- the club layer: on the 120 BPM grid that the slam sits on, muffled outside, open inside
club = S.Mixer(LEN)
grid0 = C["slam"] - BEAT * round((C["slam"] - C["tahoe"]) / BEAT)
beats = np.arange(grid0, C["hover"] - 0.01, BEAT)
for tb in beats:
    club.place(S.kick(), tb, -9)
    if tb >= C["fizz"]:
        i = int(round((tb - grid0) / BEAT))
        club.place(S.hat(), tb + BEAT / 2, -22, 0.3)
        if i % 2 == 1:
            club.place(S.clap(), tb, -18, 0.0, rev=0.3)
roots = {C["fizz"]: note("D2"), C["fizz"] + 2.0: note("A#1"), C["pour"]: note("F1"), C["pour"] + 1.4: note("C2")}
arp_notes = {C["fizz"]: ["D4", "F4", "A4", "D5"], C["fizz"] + 2.0: ["D4", "F4", "A#4", "D5"], C["pour"]: ["C4", "F4", "A4", "C5"], C["pour"] + 1.4: ["C4", "E4", "G4", "C5"]}
ks = sorted(roots)
for tb in np.arange(grid0, C["hover"] - 0.01, BEAT / 4):
    if tb < C["fizz"]:
        continue
    seg = max(k for k in ks if k <= tb + 1e-6) if any(k <= tb + 1e-6 for k in ks) else ks[0]
    j = int(round((tb - grid0) / (BEAT / 4)))
    club.place(S.pluck(note(arp_notes[seg][j % 4]), 0.22, 1800 + 2600 * min(1, (tb - C["fizz"]) / 3)), tb, -21, 0.35 * (1 if j % 2 else -1), rev=0.35)
    if j % 2 == 0:
        club.place(S.sub_bass(roots[seg], BEAT / 2 * 0.9), tb, -15)
# outside the bar the beat is a muffled thump through the snow; inside, it opens up
club_dry = club.dry.copy()
t_ = secs(N)
muffle = np.clip((t_ - (C["fizz"] - 0.6)) / 0.6, 0, 1)
low = S.filt(club_dry, "lp", 220, 0.7) * 0.9
club_mix = low * (1 - muffle) * np.clip((t_ - C["tahoe"] - 0.4) / 3.0, 0, 1) + club_dry * muffle
club_mix *= np.clip((C["hover"] - t_) / 0.05, 0, 1)
club_wet = club.wet * muffle

# --- energy: fizz, the pour
fx.place(S.stereo(S.fizz, C["pour"] - C["fizz"] + 0.3, 1400, 1.0), C["fizz"], -16, rev=0.3)
for tb in S.sample_times(C["fizz"], C["pour"], 40, lambda x: np.ones_like(x)):
    fx.place(S.bloop(S.rng.uniform(300, 600), S.rng.uniform(800, 1600), S.rng.uniform(0.03, 0.07)), tb, -30, S.rng.uniform(-0.8, 0.8), rev=0.4)
fx.place(S.whoosh(0.5, 3000, 600, q=0.8, peak=0.2, pan0=0.0, pan1=0.0), C["fizz"] - 0.05, -18, rev=0.3)
fx.place(S.filt(S.stereo(S.pour, C["hover"] - C["pour"] - 0.4), "lp", 7000, 0.7), C["pour"] - 0.05, -16, rev=0.25)
fx.place(S.stereo(S.fizz, C["release"] - C["pour"], 700, 0.8), C["pour"] + 0.5, -21, rev=0.3)

# --- the hover: a heartbeat, a clock, a held breath; the fall; the hit; slow motion
for i, tb in enumerate(np.arange(C["hover"] + 0.2, C["release"] - 0.3, 0.92)):
    fx.place(S.heartbeat(), tb, -16 + 0.6 * i, rev=0.15)
fx.place(S.stereo(S.riser, C["hit"] - C["hover"] - 1.5, 300, 7000, 110, 2.0), C["hover"] + 1.5, -24, rev=0.3)
fx.place(S.stereo(S.reverse_swell, 1.0, 600), C["hit"] - 1.0, -14, rev=0.3)
fx.place(S.whoosh(1.0, 400, 3000, q=0.9, peak=0.9, pan0=0.0, pan1=0.0), C["release"], -20, rev=0.3)
fx.place(np.vstack([S.plunge(2.6), S.plunge(2.6)]), C["hit"], -5, rev=0.5)
fx.place(S.stereo(S.boom, 5.0, 90, 24, 0.35, 2.0), C["hit"], -5, rev=0.4)
fx.place(S.stereo(S.braam, 3.5, [D1, D2, A2], 1.4, 2400), C["hit"], -15, rev=0.4)
sl = ns(C["rampUp"] - C["hit"] + 0.6)
under = np.vstack([S.filt(S.noise(sl), "lp", 300, 0.7) * S.env_fade(sl, 0.05, 0.6) * 1.4 for _ in range(2)])
fx.place(under, C["hit"] + 0.05, -20)
for tb in S.sample_times(C["hit"] + 0.1, C["rampUp"] + 1.0, 70, lambda x: np.exp(-(x - C["hit"]) / 1.4)):
    fx.place(S.bloop(S.rng.uniform(110, 260), S.rng.uniform(300, 700), S.rng.uniform(0.08, 0.2)), tb, -26, S.rng.uniform(-0.8, 0.8), rev=0.5)
fx.place(S.stereo(S.fizz, 3.4, 2600, 1.1), C["rampUp"] - 0.3, -15, rev=0.3)  # the foam surges
fx.place(S.stereo(S.riser, C["slam"] - C["rampUp"] - 0.25, 300, 9000, 110, 2.0), C["rampUp"], -18, rev=0.25)
fx.place(S.stereo(S.reverse_swell, 0.6, 1200), C["slam"] - 0.65, -15, rev=0.3)

# --- the slam and the beat
fx.place(S.stereo(S.boom, 3.0, 110, 30, 0.2, 1.1), C["slam"], -7, rev=0.3)
fx.place(S.stereo(S.braam, 2.0, [D1, D2, A2], 0.9, 2600), C["slam"], -17, rev=0.3)
bkicks = np.arange(C["slam"], C["endcard"] - 0.01, BEAT)
for i, tk in enumerate(bkicks):
    fx.place(S.kick(), tk, -8)
    if i % 2 == 1:
        fx.place(S.clap(), tk, -17, 0.0, rev=0.35)
    fx.place(S.hat(), tk + BEAT / 2, -23, 0.25)
for tb in np.arange(C["slam"], C["endcard"] - 0.01, BEAT / 2):
    j = int(round((tb - C["slam"]) / (BEAT / 2)))
    bar = min(3, int((tb - C["slam"]) // 2.0))
    root = [note("D2"), note("A#1"), note("F1"), note("A1")][bar]
    fx.place(S.sub_bass(root, BEAT / 2 * 0.85), tb, -14 + (2 if j % 2 == 0 else 0))
for i, c in enumerate(C["cuts"][1:]):
    fx.place(S.whoosh(0.35, 800, 5000, q=0.9, peak=0.85, pan0=-0.7 * (-1) ** i, pan1=0.7 * (-1) ** i), c - 0.3, -17, rev=0.2)
    fx.place(S.fm_bell(note(["A5", "D6", "F6", "A6"][i]), 1.0, ratio=2.0, index=0.8, tau_i=0.05, tau_a=0.25), c, -25, (-1) ** i * 0.5, rev=0.4)
# the replayed drop in "Drop it."
fx.place(np.vstack([S.plunge(1.6), S.plunge(1.6)]), C["cuts"][3] + 0.2, -11, rev=0.4)
fx.place(S.stereo(S.reverse_swell, 0.5, 1200), C["endcard"] - 0.5, -17, rev=0.3)

# --- end card
fx.place(S.stereo(S.boom, 3.0, 100, 27, 0.3, 0.9), C["endcard"], -7, rev=0.35)
fx.place(S.stereo(S.braam, 1.6, [D1, D2, A2, D3], 0.7, 2800), C["endcard"], -18, rev=0.4)
fx.place(S.stereo(S.fizz, 6.0, 300, 0.9), C["endcard"] + 0.5, -28, rev=0.3)
fx.place(S.glass_clink(), C["tagline"] + 3.6, -20, 0.15, rev=0.6)

fx_mix = fx.dry + club_mix
fx_wet = fx.wet + club_wet

# ============================================================================= 3 · voice-over
vo = np.zeros((2, N))
vo_meta = json.load(open(os.path.join(HERE, "vo", "lines.json")))
spans = {}
for key, t0 in C["vo"].items():
    y, sr = sf.read(os.path.join(HERE, "vo", f"{key}.wav"))
    y = signal.resample_poly(y, SR, sr)
    y = S.filt(y, "hp", 70, 0.7)
    y = S.filt(y, "lowshelf", 150, 0.7, 2.5)
    y = S.filt(y, "peak", 380, 1.2, -2.5)
    y = S.filt(y, "peak", 3200, 0.9, 3.5)
    y = S.filt(y, "highshelf", 7500, 0.7, 3.0)
    y = y / (np.abs(y).max() + 1e-9)
    i0 = int(round(t0 * SR))
    n = min(len(y), N - i0)
    vo[:, i0 : i0 + n] += y[:n]
    spans[key] = (i0, i0 + n)
vo = S.compress(vo, thr_db=-26.0, ratio=3.0, att=0.004, rel=0.12) * 10 ** (8 / 20)
vo = np.tanh(vo * 1.1) / 1.1
# duck each line just enough to sit ~10 dB above the music and effects under it
lvl = lambda x: 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)
bed_raw = music + fx_mix
vo_active = np.zeros(N)
for key, (a_, b_) in spans.items():
    vo_active[a_:b_] = np.clip(10.0 - (lvl(vo[:, a_:b_]) - lvl(bed_raw[:, a_:b_])), 4.0, 18.0)
vo_ir = S.make_ir(1.6, seed=5, rt=(1.3, 1.1, 0.8, 0.4), predelay=0.012)
vo_wet = S.convolve(vo, vo_ir)

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
bed = (music + fx_mix) * duck
bed_wet = (music_wet * 0.8 + fx_wet) * duck
mix = bed + S.convolve(bed_wet, ir) * 0.5 + vo + vo_wet * 0.12
mix = np.nan_to_num(mix)
mix = S.filt(mix, "hp", 24, 0.7)
mix = S.filt(mix, "peak", 300, 0.8, -1.0)
mix = S.compress(mix, thr_db=-22.0, ratio=1.8)
peak = np.max(np.abs(mix))
mix = mix / peak * 1.35
mix = np.tanh(mix) / np.tanh(1.35)
mix *= 10 ** (-1.6 / 20) / np.max(np.abs(mix))  # sample peak −1.6 dBFS keeps the true peak under −1 dBTP
t = secs(N)
mix *= np.clip((LEN - 0.05 - t) / 0.6, 0, 1)

if os.environ.get("DUMP"):  # components for analysis
    d = os.environ["DUMP"]
    os.makedirs(d, exist_ok=True)
    for nm, x in [("music", music * duck), ("fx", fx_mix), ("vo", vo)] + [(k, v) for k, v in stems.items()]:
        sf.write(os.path.join(d, nm + ".wav"), (x / (np.abs(x).max() + 1e-9) * 0.5).T.astype(np.float32), SR)
    # how far the voice sits above everything else, line by line
    lvl = lambda x: 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)
    for key, t0 in sorted(C["vo"].items(), key=lambda kv: kv[1]):
        a_, b_ = ns(t0), ns(t0 + vo_meta[key]["dur"])
        print(f"  {key:10s} voice over bed {lvl(vo[:, a_:b_]) - lvl(bed[:, a_:b_]):+5.1f} dB")

out = os.path.join(HERE, "soundtrack.wav")
sf.write(out, mix.T.astype(np.float32), SR, subtype="PCM_24")
print("wrote", out)
rms = lambda a_, b_: 20 * np.log10(np.sqrt(np.mean(mix[:, ns(a_) : ns(b_)] ** 2)) + 1e-12)
for a_, b_, name in [(0, C["forestIn"], "open"), (C["forestIn"], C["ignite"], "1934"), (C["ignite"], C["whip"], "56"), (C["whip"], C["shatter"], "ice"),
                     (C["shatter"], C["tahoe"], "bottle"), (C["tahoe"], C["fizz"], "tahoe"), (C["fizz"], C["hover"], "energy"),
                     (C["hover"], C["hit"], "hover"), (C["hit"], C["slam"], "drop"), (C["slam"], C["endcard"], "beat"), (C["endcard"], LEN, "end")]:
    print(f"  {name:7s} {rms(a_, b_):6.1f} dBFS rms")
