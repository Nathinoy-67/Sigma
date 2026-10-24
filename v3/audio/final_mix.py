#!/usr/bin/env python3
"""Final mix: the orchestral score (score/score_mix.wav, 48 kHz stereo, premixed) + the narration (vo/final/*.wav at
the times in vo/lines.json).

VO bus: resampled to 48 kHz, a touch of short plate-like reverb, centred.  The score is ducked under the voice by an
envelope follower on the VO (about -5 dB, 60 ms attack, 350 ms release).  Master: gentle glue compression, true-peak
limiter at -1 dBTP, normalised to -14 LUFS integrated.  Writes mix/final_mix.wav (48 kHz / 24-bit) and
mix/preview.m4a (AAC 256k).
    python3 v3/audio/final_mix.py
"""
import json, os, subprocess, sys
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "score"))
import mixer as X  # noqa: E402
from audio_tools import lufs, true_peak_db  # noqa: E402

SR = 48000


def follower(x, att, rel, sr=SR):
    a, r = np.exp(-1 / (att * sr)), np.exp(-1 / (rel * sr))
    out = np.empty_like(x)
    e = 0.0
    for i, v in enumerate(x):
        g = a if v > e else r
        e = g * e + (1 - g) * v
        out[i] = e
    return out


def main():
    score, sr = sf.read(os.path.join(HERE, "score", "score_mix.wav"), always_2d=True)
    assert sr == SR
    score = score.T                     # (2, n): the score tools' layout
    n = score.shape[1]
    meta = json.load(open(os.path.join(HERE, "vo", "lines.json")))
    vo = np.zeros(n)
    for line in meta["lines"]:
        y, s = sf.read(os.path.join(HERE, "vo", "final", f"{line['key']}.wav"))
        y = resample_poly(y, SR, s) if s != SR else y
        i0 = int(round(line["start"] * SR))
        i1 = min(n, i0 + len(y))
        vo[i0:i1] += y[: i1 - i0]
    # VO level: each line was peak-normalised; bring the bus to about -16 LUFS on its own (speech parts)
    act = np.abs(vo) > 1e-4
    g = 10 ** ((-16.0 - lufs(np.stack([vo[act], vo[act]]), SR)) / 20) if act.any() else 1.0
    vo *= g
    # a little air: short dense reverb, low level, high-passed
    ir = X.hall_ir(rt60=0.9, predelay=0.012, seed=11, hp_f=250.0, lp_f=7000.0)
    wet = X.convolve(np.stack([vo, vo]), ir) * 10 ** (-17 / 20)
    vo_st = np.stack([vo, vo]) * 0.7071 + wet
    # duck the score under the voice
    env = follower(np.abs(vo), 0.004, 0.08)
    lvl = 20 * np.log10(env + 1e-9)
    duck_db = np.clip((lvl + 40) / 25, 0, 1) * -5.0          # 0 dB in silence, -5 dB under full speech
    duck = 10 ** (follower(-duck_db, 0.06, 0.35) * -1 / 20)
    mix = score * duck[None, :] + vo_st
    # master: glue + true-peak limiting, -14 LUFS
    gr, _ = X.compressor_gain(mix, thresh_db=-16.0, ratio=1.6, attack=0.03, release=0.3)
    mix = mix * gr[None, :]
    mix *= 10 ** ((-14.0 - lufs(mix, SR)) / 20)
    lim = X.truepeak_limiter_gain(mix, ceiling_db=-1.0)
    mix = mix * lim[None, :]
    out_dir = os.path.join(HERE, "mix")
    os.makedirs(out_dir, exist_ok=True)
    wav = os.path.join(out_dir, "final_mix.wav")
    sf.write(wav, mix.T.astype(np.float32), SR, subtype="PCM_24")
    print(f"mix: {lufs(mix, SR):.2f} LUFS, true peak {true_peak_db(mix, SR):.2f} dBTP, {n / SR:.2f}s")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "aac", "-b:a", "256k",
                    os.path.join(out_dir, "preview.m4a")], check=True)


if __name__ == "__main__":
    main()
