#!/usr/bin/env python3
"""Final narration: several takes per line, the best one kept, then a trailer-VO chain.

Supertonic 3 (MIT, via sherpa-onnx) is stochastic, so every call is a different read. For each line we generate
TAKES reads per voice and speed, trim them, reject any whose Whisper transcript doesn't match or that overruns the
line's slot, and score the rest on DNSMOS (SIG + OVRL) with a small bonus for pitch movement (a read that goes
somewhere instead of droning). The voice with the best average wins the whole film; per line its best take is used.

Chain (per take, after selection): high-pass, chest low shelf, mud cut, presence and air, a de-esser, 3:1 bus-style
compression, gentle tube-style saturation, a very short room. Output: vo/final/<line>.wav (44.1 kHz mono, peak -1 dBFS)
and vo/lines.json (start time on the film clock, duration, subtitle text).
    python3 v3/audio/vo/make_vo.py [--voices 6,9] [--takes 6]
"""
import argparse, json, os, re, sys
import numpy as np
import onnxruntime as ort
import sherpa_onnx
import soundfile as sf
from scipy.signal import butter, sosfilt, resample_poly

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "score"))
from shootout import tts, asr, dnsmos, f0_stats, MOS  # noqa: E402
from audio_tools import lufs  # noqa: E402

SR = 44100
# key, start (s, film clock), max speech length (s), speeds to try, pause scale, text to speak, subtitle, accepted transcripts
LINES = [
    ("01", 2.6, 3.55, (0.98, 1.03), 1.1, "Nineteen thirty-four. Curt Mast perfects a recipe.", "1934. Curt Mast perfects a recipe.",
     ["1934 kurt mast perfects a recipe", "1934 curt mast perfects a recipe", "1934 kurtmast perfects a recipe"]),
    ("02", 6.3, 3.4, (0.94, 1.0), 1.1, "Fifty-six herbs, blossoms, roots and fruits.", "Fifty-six herbs, blossoms, roots and fruits.",
     ["56 herbs blossoms roots and fruits"]),
    ("03", 9.75, 3.0, (0.8, 0.88), 1.6, "Which ones? Still a secret.", "Which ones? Still a secret.",
     ["which ones still a secret", "which one s still a secret"]),
    ("04", 13.25, 4.6, (0.78, 0.86), 1.5, "Then it waits. A full year, in oak.", "Then it waits. A full year, in oak.",
     ["then it waits a full year in oak"]),
    ("05", 20.65, 3.8, (0.82, 0.9), 1.2, "In the seventies, it crosses an ocean.", "In the seventies, it crosses an ocean.",
     ["in the 70s it crosses an ocean", "in the seventies it crosses an ocean"]),
    ("06", 24.6, 2.8, (0.82, 0.9), 1.2, "And America serves it ice cold.", "And America serves it ice cold.",
     ["and america serves it ice cold"]),
    ("07", 30.9, 3.75, (0.94, 1.0), 1.0, "Around nineteen ninety-seven... somebody has an idea.", "Around 1997… somebody has an idea.",
     ["around 1997 somebody has an idea"]),
    ("08a", 34.75, 1.5, (0.98, 1.04), 1.0, "Nobody knows exactly who.", "Nobody knows exactly who.",
     ["nobody knows exactly who"]),
    ("08b", 36.3, 2.2, (0.82, 0.9), 1.0, "Everybody knows the name.", "Everybody knows the name.",
     ["everybody knows the name"]),
    ("09", 50.6, 4.0, (0.72, 0.8), 1.5, "A year in oak. A second in glass.", "A year in oak. A second in glass.",
     ["a year in oak a second in glass"]),
    ("10", 57.55, 1.6, (0.82, 0.9), 1.0, "Yay-ger-my-ster.", "Jägermeister.",
     ["yeagermeister", "jagermeister", "jaegermeister", "yagermeister", "yeager meister", "jager meister", "yegermeister"]),
]


def norm(s):
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    return " ".join(s.split())


def trim(y, thr_db=-45.0, pad=0.03):
    """Cut leading/trailing silence (relative to peak), keep `pad` s, 15 ms fades."""
    env = np.convolve(np.abs(y), np.ones(441) / 441, "same")
    idx = np.where(env > np.abs(y).max() * 10 ** (thr_db / 20))[0]
    a = max(0, idx[0] - int(pad * SR)); b = min(len(y), idx[-1] + int(pad * SR))
    y = y[a:b].copy()
    f = int(0.015 * SR)
    y[:f] *= np.linspace(0, 1, f); y[-f:] *= np.linspace(1, 0, f)
    return y


def peq(y, f0, gain_db, q=0.9, kind="peak"):
    """RBJ biquad (peak / lowshelf / highshelf)."""
    A = 10 ** (gain_db / 40); w = 2 * np.pi * f0 / SR; cw, sw = np.cos(w), np.sin(w); al = sw / (2 * q)
    if kind == "peak":
        b = [1 + al * A, -2 * cw, 1 - al * A]; a = [1 + al / A, -2 * cw, 1 - al / A]
    else:
        sA = 2 * np.sqrt(A) * al; s = 1 if kind == "lowshelf" else -1
        b = [A * ((A + 1) - s * (A - 1) * cw + sA), s * 2 * A * ((A - 1) - s * (A + 1) * cw), A * ((A + 1) - s * (A - 1) * cw - sA)]
        a = [(A + 1) + s * (A - 1) * cw + sA, -s * 2 * ((A - 1) + s * (A + 1) * cw), (A + 1) + s * (A - 1) * cw - sA]
    b = np.array(b) / a[0]; a = np.array(a) / a[0]
    from scipy.signal import lfilter
    return lfilter(b, a, y)


def follower(x, att, rel):
    """Peak envelope follower (attack/release in seconds)."""
    ga, gr = np.exp(-1 / (att * SR)), np.exp(-1 / (rel * SR))
    out = np.empty_like(x); e = 0.0
    for i, v in enumerate(np.abs(x)):
        g = ga if v > e else gr
        e = g * e + (1 - g) * v
        out[i] = e
    return out


def chain(y):
    y = sosfilt(butter(2, 65, "hp", fs=SR, output="sos"), y)
    y = peq(y, 120, 3.0, 0.8, "lowshelf")       # chest / proximity
    y = peq(y, 320, -2.5, 1.0)                    # mud
    y = peq(y, 3800, 2.0, 0.8)                    # presence
    y = peq(y, 11000, -1.5, 0.7, "highshelf")    # tame the vocoder sheen
    # de-esser: duck the 5-9 kHz band when it gets hot
    band = sosfilt(butter(2, [5000, 9000], "bp", fs=SR, output="sos"), y)
    be = follower(band, 0.001, 0.04); fe = follower(y, 0.002, 0.08) + 1e-6
    ratio = be / fe
    g = np.clip(1 - 1.6 * np.maximum(ratio - 0.18, 0), 0.45, 1)
    y = y - band * (1 - g)
    # compressor 3:1, soft knee, ~5 dB of gain reduction on peaks
    y = y / (np.abs(y).max() + 1e-9) * 0.5
    env = follower(y, 0.004, 0.12)
    lv = 20 * np.log10(env + 1e-9); thr = -16.0
    over = np.maximum(lv - thr, 0)
    gr = over * (1 - 1 / 3.0)
    y = y * 10 ** (-gr / 20)
    # gentle tube-style saturation (asymmetric, mostly 2nd harmonic), blended
    d = 1.8
    sat = np.tanh(d * (y + 0.06)) - np.tanh(d * 0.06)
    y = 0.8 * y + 0.2 * sat / d * 1.2
    # very short room: a few early reflections, low level
    room = np.zeros_like(y)
    for ms, gdb in ((11, -22), (17, -24), (23, -26), (31, -28), (43, -31)):
        k = int(ms * SR / 1000); room[k:] += y[:-k] * 10 ** (gdb / 20)
    room = sosfilt(butter(1, [300, 6000], "bp", fs=SR, output="sos"), room)
    y = y + room
    return y / (np.abs(y).max() + 1e-9) * 10 ** (-1 / 20)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voices", default="6,9")
    ap.add_argument("--takes", type=int, default=5)
    ap.add_argument("--resume", action="store_true", help="reuse the takes already scored in make_vo.log")
    args = ap.parse_args()
    voices = [int(v) for v in args.voices.split(",")]
    t = tts(); r = asr(); mos = ort.InferenceSession(MOS)
    takes_dir = os.path.join(HERE, "takes"); os.makedirs(takes_dir, exist_ok=True)
    cands = {}
    done = set()
    if args.resume and os.path.exists(os.path.join(HERE, "make_vo.log")):
        pat = re.compile(r"^(\S+)\s+s(\d+) v([\d.]+) #(\d+) ([\d.]+)s/([\d.]+) ok=(\d) SIG ([\d.]+) OVRL ([\d.]+) "
                         r"F0\s+(\d+)/\s*(\d+) score ([\d.]+) \| (.*)$")
        maxlens = {l[0]: l[2] for l in LINES}
        accepts = {l[0]: [norm(a) for a in l[7]] for l in LINES}
        for line in open(os.path.join(HERE, "make_vo.log")):
            m = pat.match(line.strip())
            if not m:
                continue
            key, sid, sp, k = m.group(1), int(m.group(2)), float(m.group(3)), int(m.group(4))
            name = f"{key}_s{sid}_v{int(round(sp * 100))}_{k}.wav"
            if not os.path.exists(os.path.join(HERE, "takes", name)):
                continue
            dur = float(m.group(5))
            cands.setdefault(key, []).append(dict(file=name, sid=sid, speed=sp, dur=dur, ok=norm(m.group(13)) in accepts[key],
                                                  fits=dur <= maxlens[key], asr=m.group(13), sig=float(m.group(8)),
                                                  ovrl=float(m.group(9)), f0=int(m.group(10)), rng=int(m.group(11)),
                                                  score=float(m.group(12))))
            done.add((key, sid, round(sp, 2), k))
    for key, start, maxlen, speeds, pause, text, sub, accept in LINES:
        for sid in voices:
            for sp in speeds:
                for k in range(args.takes):
                    if (key, sid, round(sp, 2), k) in done:
                        continue
                    g = sherpa_onnx.GenerationConfig(); g.sid = sid; g.num_steps = 32; g.speed = sp; g.silence_scale = pause; g.extra["lang"] = "en"
                    y = trim(np.asarray(t.generate(text, g).samples, np.float64))
                    dur = len(y) / SR
                    y16 = resample_poly(y, 16000, SR).astype(np.float32)
                    st = r.create_stream(); st.accept_waveform(16000, y16); r.decode_stream(st)
                    hyp = st.result.text.strip()
                    ok = norm(hyp) in [norm(a) for a in accept]
                    s, _, o = dnsmos(mos, (y16 / (np.abs(y16).max() + 1e-9) * 0.5).astype(np.float32))
                    f0, rng = f0_stats(y.astype(np.float32), SR)
                    score = s + o + 0.004 * min(rng, 60)
                    name = f"{key}_s{sid}_v{int(sp*100)}_{k}.wav"
                    sf.write(os.path.join(takes_dir, name), y.astype(np.float32), SR)
                    c = dict(file=name, sid=sid, speed=sp, dur=round(dur, 2), ok=ok, fits=dur <= maxlen, asr=hyp,
                             sig=round(s, 3), ovrl=round(o, 3), f0=round(f0), rng=round(rng), score=round(score, 3))
                    cands.setdefault(key, []).append(c)
                    print(f"{key:4s} s{sid} v{sp:.2f} #{k} {dur:4.2f}s/{maxlen} ok={int(ok)} SIG {s:.2f} OVRL {o:.2f} "
                          f"F0 {f0:4.0f}/{rng:3.0f} score {score:.2f} | {hyp}", flush=True)
    json.dump(cands, open(os.path.join(HERE, "takes.json"), "w"), indent=1)

    def best(key, sid):
        good = [c for c in cands[key] if c["sid"] == sid and c["ok"] and c["fits"]]
        if not good:  # relax: accept a near-fit transcript or a slight overrun rather than nothing
            good = [c for c in cands[key] if c["sid"] == sid and c["ok"]] or [c for c in cands[key] if c["sid"] == sid]
            good = sorted(good, key=lambda c: c["dur"])[:3]
        return max(good, key=lambda c: c["score"])

    totals = {sid: np.mean([best(k[0], sid)["score"] for k in LINES]) for sid in voices}
    print("voice totals:", {f"s{k}": round(v, 3) for k, v in totals.items()})
    sid = max(totals, key=totals.get)
    out_dir = os.path.join(HERE, "final"); os.makedirs(out_dir, exist_ok=True)
    meta = []
    for key, start, maxlen, speeds, pause, text, sub, accept in LINES:
        c = best(key, sid)
        y, _ = sf.read(os.path.join(takes_dir, c["file"]))
        y = chain(y)
        sf.write(os.path.join(out_dir, f"{key}.wav"), y.astype(np.float32), SR, subtype="PCM_24")
        meta.append(dict(key=key, start=start, dur=round(len(y) / SR, 3), text=sub, take=c["file"], score=c["score"],
                         asr=c["asr"], fits=c["fits"], lufs=round(lufs(y, SR), 2)))
        print(f"{key}: {c['file']} {c['dur']}s (max {maxlen}) score {c['score']}  {c['asr']}")
    json.dump(dict(voice=f"supertonic3-sid{sid}", lines=meta), open(os.path.join(HERE, "lines.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
