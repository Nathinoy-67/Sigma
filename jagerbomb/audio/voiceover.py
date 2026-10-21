#!/usr/bin/env python3
"""English voice-over: Kokoro-82M v1.0 (Apache-2.0), the same deep male blend as The Hunter's Hour
(80% am_onyx + 20% am_michael, slowed down), run with the kokoro-onnx runtime.

Model + voices: the kokoro-onnx GitHub release (model-files-v1.0). Writes one trimmed WAV per line to
audio/vo/ plus vo/lines.json, which also carries the subtitle text for each line.
    python3 audio/voiceover.py <kokoro-v1.0.onnx> <voices-v1.0.bin>
"""
import json, os, sys
import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "vo")
BLEND, LANG = {"am_onyx": 0.8, "am_michael": 0.2}, "en-us"

# espeak's reading → the pronunciation we want
FIX = {
    "jˈɛdʒɚmˌaɪstɚ": "jˈeɪɡɚmˌaɪstɚ",  # Jägermeister: YAY-ger-my-ster
    "wˈʊlfənbˌuːɾəl": "vˈɑlfənbˌuːtəl",  # Wolfenbüttel: VOL-fen-boo-tel
}

# id, spoken text, subtitle, speed
LINES = [
    ("drop", "Every legend begins with a single drop.", "Every legend begins with a single drop.", 0.86),
    ("germany", "Germany, nineteen thirty-four.", "Germany, 1934.", 0.86),
    ("mast", "In Wolfenbüttel, Curt Mast perfected a secret recipe.", "In Wolfenbüttel, Curt Mast perfected a secret recipe.", 0.88),
    ("named", "He called it Jägermeister.", "He called it Jägermeister.", 0.86),
    ("hunter", "The master hunter.", "The master hunter.", 0.84),
    ("botanicals", "Fifty-six botanicals. A full year in oak.", "Fifty-six botanicals. A full year in oak.", 0.88),
    ("ocean", "Served ice cold, it crossed an ocean,", "Served ice cold, it crossed an ocean…", 0.88),
    ("night", "and conquered the night.", "…and conquered the night.", 0.86),
    ("tahoe", "Decades later, in the snowy pines of Lake Tahoe,", "Decades later, in the snowy pines of Lake Tahoe…", 0.9),
    ("energy", "a new kind of energy was hitting the bars.", "…a new kind of energy was hitting the bars.", 0.9),
    ("nobody", "Nobody knows for sure who dropped the first one.", "Nobody knows for sure who dropped the first one.", 0.88),
    ("moment", "But the moment that shot hit the glass,", "But the moment that shot hit the glass…", 0.86),
    ("born", "a legend was born.", "…a legend was born.", 0.82),
    ("one", "One shot.", "One shot.", 0.86),
    ("ice", "Ice cold.", "Ice cold.", 0.86),
    ("dropit", "Drop it.", "Drop it.", 0.84),
    ("brand", "Jägermeister.", "Jägermeister.", 0.84),
    ("tagline", "Born in the forest. Dropped into legend.", "Born in the forest. Dropped into legend.", 0.86),
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
    for key, text, sub, speed in LINES:
        ph = k.tokenizer.phonemize(text, LANG)
        for a, b in FIX.items():
            ph = ph.replace(a, b)
        y, sr = k.create(ph, voice=style, speed=speed, lang=LANG, is_phonemes=True)
        y = trim(np.asarray(y, dtype=np.float32), sr)
        sf.write(os.path.join(OUT, f"{key}.wav"), y, sr)
        meta[key] = {"text": text, "sub": sub, "phonemes": ph, "dur": round(len(y) / sr, 3), "sr": sr}
        print(f"{key:11s} {len(y)/sr:5.2f}s  {ph}")
    json.dump(meta, open(os.path.join(OUT, "lines.json"), "w"), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main(*sys.argv[1:3])
