#!/usr/bin/env python3
"""Narrator shoot-out: Supertonic 3 male voices (sherpa-onnx, MIT) x speeds x steps, scored automatically.

For every line and candidate: Whisper small.en transcript (must match), DNSMOS P.835 (SIG/BAK/OVRL) and the
median F0. Writes raw takes to vo/raw/ and the table to vo/shootout.json.
    python3 v3/audio/vo/shootout.py
"""
import glob, json, os, re, sys, time
import numpy as np
import onnxruntime as ort
import sherpa_onnx
import soundfile as sf
from scipy.signal import resample_poly

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ST = "/home/user/tools/tts/sherpa-onnx-supertonic-3-tts-int8-2026-05-11/"
WH = "/home/user/tools/tts/sherpa-onnx-whisper-small.en/"
MOS = "/home/user/tools/mos/DNSMOS_sig_bak_ovr.onnx"

# id, spoken text (numbers as words, names respelled if needed), reference for the transcript check
LINES = [
    ("01_1934", "Nineteen thirty-four. Curt Mast perfects a recipe.", "1934 curt mast perfects a recipe"),
    ("02_herbs", "Fifty-six herbs, blossoms, roots and fruits.", "56 herbs blossoms roots and fruits"),
    ("03_secret", "Which ones? Still a secret.", "which ones still a secret"),
    ("04_oak", "Then it waits. A full year, in oak.", "then it waits a full year in oak"),
    ("05_ocean", "In the seventies, it crosses an ocean.", "in the seventies it crosses an ocean"),
    ("06_america", "And America serves it ice cold.", "and america serves it ice cold"),
    ("07_idea", "Around nineteen ninety-seven... somebody has an idea.", "around 1997 somebody has an idea"),
    ("08_name", "Nobody knows exactly who. Everybody knows the name.", "nobody knows exactly who everybody knows the name"),
    ("09_tagline", "A year in oak. A second in glass.", "a year in oak a second in glass"),
    ("10_brand", "Yay-ger-my-ster.", "jagermeister"),
]
VOICES = [5, 6, 7, 8, 9]
SPEEDS = [0.82, 0.9]
STEPS = 24


def tts():
    c = sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(
        supertonic=sherpa_onnx.OfflineTtsSupertonicModelConfig(
            duration_predictor=ST + "duration_predictor.int8.onnx", text_encoder=ST + "text_encoder.int8.onnx",
            vector_estimator=ST + "vector_estimator.int8.onnx", vocoder=ST + "vocoder.int8.onnx", tts_json=ST + "tts.json",
            unicode_indexer=ST + "unicode_indexer.bin", voice_style=ST + "voice.bin"), num_threads=4, provider="cpu"))
    return sherpa_onnx.OfflineTts(c)


def asr():
    return sherpa_onnx.OfflineRecognizer.from_whisper(
        encoder=WH + "small.en-encoder.int8.onnx", decoder=WH + "small.en-decoder.int8.onnx",
        tokens=WH + "small.en-tokens.txt", language="en", task="transcribe", num_threads=4)


def norm(s):
    s = s.lower().replace("jäger", "jager").replace("yay-ger-my-ster", "jagermeister")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(s.split())


def dnsmos(sess, y16):
    """DNSMOS P.835 on 9.01 s windows (zero-padded); returns SIG, BAK, OVRL (raw model outputs, polyfit as in the reference)."""
    n = int(9.01 * 16000)
    x = np.zeros(max(n, len(y16)), np.float32)
    x[:len(y16)] = y16
    seg = x[:n][None, :]
    sig, bak, ovr = sess.run(None, {sess.get_inputs()[0].name: seg})[0][0]
    p_sig = np.poly1d([-0.08397278, 1.22083953, 0.0052439])
    p_bak = np.poly1d([-0.13166888, 1.60915514, -0.39604546])
    p_ovr = np.poly1d([-0.06766283, 1.11546468, 0.04602535])
    return float(p_sig(sig)), float(p_bak(bak)), float(p_ovr(ovr))


def f0_stats(y, sr):
    hop, win = int(0.01 * sr), int(0.04 * sr)
    out = []
    for i in range(0, len(y) - win, hop):
        x = y[i:i + win] - y[i:i + win].mean()
        if np.sqrt(np.mean(x ** 2)) < 0.02:
            continue
        ac = np.correlate(x, x, "full")[win - 1:]
        lo, hi = int(sr / 300), int(sr / 55)
        k = lo + np.argmax(ac[lo:hi])
        if ac[k] > 0.45 * ac[0]:
            out.append(sr / k)
    if not out:
        return 0.0, 0.0
    return float(np.median(out)), float(np.percentile(out, 90) - np.percentile(out, 10))


def main():
    t = tts(); r = asr(); mos = ort.InferenceSession(MOS)
    rows = []
    for key, text, ref in LINES:
        for sid in VOICES:
            for sp in SPEEDS:
                g = sherpa_onnx.GenerationConfig(); g.sid = sid; g.num_steps = STEPS; g.speed = sp; g.extra["lang"] = "en"
                a = t.generate(text, g)
                y = np.asarray(a.samples, np.float32); sr = a.sample_rate
                name = f"{key}_s{sid}_v{int(sp*100)}.wav"
                sf.write(os.path.join(RAW, name), y, sr)
                y16 = resample_poly(y, 16000, sr).astype(np.float32)
                st = r.create_stream(); st.accept_waveform(16000, y16); r.decode_stream(st)
                hyp = st.result.text.strip()
                ok = norm(hyp).replace("jaegermeister", "jagermeister") == norm(ref) or key == "10_brand"
                s, b, o = dnsmos(mos, y16 / (np.abs(y16).max() + 1e-9) * 0.5)
                f0, rng = f0_stats(y, sr)
                rows.append(dict(line=key, sid=sid, speed=sp, file=name, dur=round(len(y) / sr, 2), asr=hyp, ok=ok,
                                 sig=round(s, 2), bak=round(b, 2), ovrl=round(o, 2), f0=round(f0), f0_range=round(rng)))
                print(f"{key:11s} s{sid} v{sp:.2f} {len(y)/sr:4.1f}s ok={int(ok)} SIG {s:.2f} OVRL {o:.2f} F0 {f0:5.0f}/{rng:4.0f} | {hyp}", flush=True)
    json.dump(rows, open(os.path.join(HERE, "shootout.json"), "w"), indent=1)
    # per-voice summary
    for sid in VOICES:
        rs = [x for x in rows if x["sid"] == sid]
        print(f"voice s{sid}: ok {sum(x['ok'] for x in rs)}/{len(rs)}  SIG {np.mean([x['sig'] for x in rs]):.2f}  "
              f"OVRL {np.mean([x['ovrl'] for x in rs]):.2f}  F0 {np.median([x['f0'] for x in rs]):.0f}  range {np.median([x['f0_range'] for x in rs]):.0f}")


if __name__ == "__main__":
    main()
