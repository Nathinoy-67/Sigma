#!/usr/bin/env python3
"""English voice-over: Kokoro-82M (Apache-2.0), a deep male blend (80% am_onyx + 20% am_michael),
run with the kokoro-onnx runtime.

Model + voices come from npm (kokoro-q8-shards, kokoro-local-runtime) because Hugging Face is not
reachable from the render machine. Writes one raw WAV per line to audio/vo/ plus vo/lines.json.
    python3 audio/voiceover.py <kokoro-q8.onnx> <voices.npz>
"""
import json, os, sys
import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "vo")
# am_onyx: deepest voice with regular phonation (~88 Hz, 78% voiced); am_michael adds articulation
BLEND, SPEED, LANG = {"am_onyx": 0.8, "am_michael": 0.2}, 0.88, "en-us"

# id, text (or phonemes when ph=True)
LINES = [
    ("secrets", "They say the forest keeps its secrets.", False),
    ("woods", "In the dark woods of Lower Saxony, a hunter once followed a light.", False),
    ("antlers", "And there, between the antlers of a stag... a light shone.", False),
    ("botanicals", "Fifty-six botanicals.", False),
    ("oak", "A full year, in oak.", False),
    ("cold", "Served ice cold.", False),
    ("master", "Every night has its master.", False),
    ("brand", "jˈeɪɡɚmˌaɪstɚ.", True),  # "Jägermeister" as YAY-ger-my-ster (espeak misreads the umlaut)
    ("tagline", "Born in the forest. Made for the night.", False),
]


def trim(y, sr, thresh_db=-45, pad=0.04):
    env = np.abs(y)
    win = int(0.01 * sr)
    env = np.convolve(env, np.ones(win) / win, mode="same")
    on = np.where(env > env.max() * 10 ** (thresh_db / 20))[0]
    a, b = max(0, on[0] - int(pad * sr)), min(len(y), on[-1] + int(pad * sr))
    return y[a:b]


def main(model, voices):
    os.makedirs(OUT, exist_ok=True)
    k = Kokoro(model, voices)
    style = sum(w * k.get_voice_style(v) for v, w in BLEND.items())
    meta = {}
    for key, text, ph in LINES:
        y, sr = k.create(text, voice=style, speed=SPEED, lang=LANG, is_phonemes=ph)
        y = trim(np.asarray(y, dtype=np.float32), sr)
        sf.write(os.path.join(OUT, f"{key}.wav"), y, sr)
        meta[key] = {"text": text, "dur": round(len(y) / sr, 3), "sr": sr}
        print(f"{key:11s} {len(y)/sr:5.2f}s  {text}")
    json.dump(meta, open(os.path.join(OUT, "lines.json"), "w"), indent=2)


if __name__ == "__main__":
    main(*sys.argv[1:3])
