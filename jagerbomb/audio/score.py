#!/usr/bin/env python3
"""The orchestral score for "The Drop", written as MIDI and played through the MuseScore General SoundFont.

D minor throughout, resolving to D major on the end card. The hunting-horn call of The Hunter's Hour
(A–D–F–A | G–F–E–D) is the leitmotif: a solo horn under the title, the full brass when the beat drops,
and once more in D major at the very end. The second half moves onto a 120 BPM grid (the beat drops on
CUE.slam) so the synthesized club layer in soundtrack.py locks to it.

    from score import render_stems; stems = render_stems(cues, seconds)   # dict name -> (2, n) float array
"""
import os
import subprocess
import tempfile

import mido
import numpy as np
import soundfile as sf

SF2 = "/usr/share/sounds/sf2/MuseScore_General_Full.sf2"
TPS = 960  # MIDI ticks per second (480 ticks/beat at 120 BPM)
NOTE = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}


def m(name):
    """'D4' -> 62"""
    return 12 * (int(name[-1]) + 1) + NOTE[name[:-1]]


def ms(names):
    return [m(n) for n in names.split()]


class Part:
    def __init__(self, program, channel, volume=100, pan=64):
        self.program, self.channel, self.volume, self.pan = program, channel, volume, pan
        self.notes = []  # (t, dur, pitch, vel)
        self.cc = []  # (t, controller, value)

    def n(self, t, dur, pitch, vel):
        self.notes.append((t, dur, int(pitch), int(np.clip(vel, 1, 127))))

    def chord(self, t, dur, pitches, vel):
        for p in pitches:
            self.n(t, dur, p, vel)

    def seq(self, t0, step, pitches, dur, vel):
        for i, p in enumerate(pitches):
            v = vel(i) if callable(vel) else vel
            self.n(t0 + i * step, dur, p, v)

    def expr(self, t0, t1, v0, v1, steps=24):
        for i in range(steps + 1):
            u = i / steps
            self.cc.append((t0 + (t1 - t0) * u, 11, int(round(v0 + (v1 - v0) * u))))


def write_midi(parts, path):
    mf = mido.MidiFile(ticks_per_beat=480)
    meta = mido.MidiTrack()
    meta.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
    mf.tracks.append(meta)
    for p in parts:
        ev = [(0, 0, mido.Message("program_change", channel=p.channel, program=p.program))]
        for c, v in ((7, p.volume), (10, p.pan), (11, 100), (91, 0), (93, 0), (64, 0)):
            ev.append((0, 1, mido.Message("control_change", channel=p.channel, control=c, value=v)))
        for t, c, v in p.cc:
            ev.append((round(t * TPS), 2, mido.Message("control_change", channel=p.channel, control=c, value=int(np.clip(v, 0, 127)))))
        for t, d, pitch, vel in p.notes:
            ev.append((round(t * TPS), 4, mido.Message("note_on", channel=p.channel, note=pitch, velocity=vel)))
            ev.append((round((t + d) * TPS), 3, mido.Message("note_off", channel=p.channel, note=pitch, velocity=0)))
        ev.sort(key=lambda e: (e[0], e[1]))
        tr = mido.MidiTrack()
        last = 0
        for tick, _, msg in ev:
            msg.time = tick - last
            last = tick
            tr.append(msg)
        mf.tracks.append(tr)
    mf.save(path)


def render(parts, seconds, gain=0.5):
    with tempfile.TemporaryDirectory() as d:
        mid, wav = os.path.join(d, "s.mid"), os.path.join(d, "s.wav")
        write_midi(parts, mid)
        subprocess.run(["fluidsynth", "-ni", "-q", "-R", "0", "-C", "0", "-g", str(gain), "-r", "48000",
                        "-O", "float", "-T", "wav", "-F", wav, SF2, mid], check=True, stdout=subprocess.DEVNULL)
        y, sr = sf.read(wav, always_2d=True)
    assert sr == 48000
    out = np.zeros((2, int(seconds * 48000)))
    n = min(out.shape[1], y.shape[0])
    out[:, :n] = y[:n].T
    return out


def compose(C):
    R = np.random.default_rng(56)
    strings = Part(48, 0, 108)  # string ensemble, sustained
    stac = Part(48, 1, 100)  # string ensemble, short notes (ostinati)
    trem = Part(44, 2, 92)  # tremolo strings
    pizz = Part(45, 3, 90)
    celli = Part(42, 4, 104, 54)
    basses = Part(43, 5, 108, 60)
    slow = Part(49, 6, 100)  # slow strings (pads)
    horns = Part(60, 0, 112, 58)
    brass = Part(61, 1, 104)
    bones = Part(57, 2, 100, 72)
    tuba = Part(58, 3, 100)
    trumpet = Part(56, 4, 96, 70)
    aahs = Part(52, 0, 100)
    oohs = Part(53, 1, 96)
    celesta = Part(8, 0, 96, 74)
    harp = Part(46, 1, 100, 52)
    glock = Part(9, 2, 88, 80)
    bells = Part(14, 3, 84, 60)
    timp = Part(47, 0, 112)
    taiko = Part(116, 1, 110)
    kit = Part(0, 9, 104)  # GM drum kit
    CRASH, CRASH2, CHINA, SNARE, KICK, TOM_L, TOM_M, TOM_H = 49, 57, 52, 38, 36, 41, 45, 48

    def roll(part, t0, t1, pitch, v0, v1, step=0.055):
        k = int((t1 - t0) / step)
        for i in range(k):
            part.n(t0 + i * step, step * 0.9, pitch, v0 + (v1 - v0) * i / max(1, k - 1))

    def hit(t, chord_lo="D2 A2 D3 F3 A3", big=True, major=False):
        third = "F#" if major else "F"
        brass.chord(t, 1.4, ms(chord_lo.replace("F", third) if major else chord_lo), 124)
        bones.chord(t, 1.2, ms("D2 A2 D3"), 118)
        tuba.n(t, 1.5, m("D1"), 122)
        horns.chord(t, 1.3, ms(f"D4 {third}4 A4"), 118)
        strings.chord(t, 1.3, ms(f"D2 A2 D3 {third}3 A3 D4 {third}4 A4"), 116)
        aahs.chord(t, 1.4, ms(f"D4 {third}4 A4 D5"), 104)
        timp.n(t, 1.5, m("D2"), 127)
        taiko.n(t, 1.0, 60, 127)
        for p in (CRASH, CHINA, KICK) if big else (CRASH, KICK):
            kit.n(t, 1.5, p, 122)

    motif = [("A", 0.0, 0.45), ("D", 0.45, 0.15), ("F", 0.6, 0.6), ("A", 1.2, 1.1), ("G", 2.4, 0.5), ("F", 2.9, 0.3), ("E", 3.2, 0.3), ("D", 3.5, 1.2)]

    # ------------------------------------------------------------------ S0 · cold open: a single drop (0–4.5)
    basses.n(0.2, 6.6, m("D2"), 66)
    basses.expr(0.2, 4.4, 24, 84)
    celli.n(0.4, 6.4, m("D3"), 52)
    oohs.chord(0.9, 3.4, ms("D4 A4"), 40)
    oohs.expr(0.9, 3.6, 30, 80)
    for t, nm in [(1.05, "A5"), (1.95, "D6"), (2.75, "F6")]:  # drips, the call in fragments
        celesta.n(t, 1.4, m(nm), 54)
    t = C["dropHit"]
    timp.n(t, 1.6, m("D2"), 84)
    bells.n(t, 3.0, m("D5"), 84)
    harp.seq(t + 0.02, 0.035, ms("A6 F6 D6 A5 F5 D5 A4 F4 D4"), 1.6, 70)
    slow.chord(t, 3.2, ms("D3 A3 F4"), 52)
    slow.expr(t, t + 3.0, 70, 40)

    # ------------------------------------------------------------------ S1 · title: the horn call (4.5–7.6)
    t0 = C["titleIn"] + 0.15
    for nm, dt, d in motif:
        horns.n(t0 + dt * 0.75, d * 0.75 + 0.15, m(nm + ("4" if nm != "A" or dt > 0.5 else "3")), 84)
    strings.chord(C["titleIn"], 3.0, ms("D3 A3 D4 F4"), 64)
    strings.expr(C["titleIn"], C["titleIn"] + 3.0, 50, 90)
    aahs.chord(C["titleIn"] + 0.8, 2.3, ms("A4 D5"), 52)

    # ------------------------------------------------------------------ S2 · 1934: the flight (6.9–15.1), 120 BPM
    t0 = C["forestIn"]
    prog = [("Dm", ms("D3 D3 A3 D3 F3 D3 A3 D3"), "D2", ms("D4 F4 A4"), ms("A3 D4"), "D2"),
            ("Bb", ms("Bb2 Bb2 F3 Bb2 D3 Bb2 F3 Bb2"), "Bb1", ms("D4 F4 Bb4"), ms("F3 Bb3"), "F2"),
            ("Gm", ms("G2 G2 D3 G2 Bb2 G2 D3 G2"), "G1", ms("D4 G4 Bb4"), ms("G3 D4"), "G2"),
            ("A", ms("A2 A2 E3 A2 C#3 A2 E3 A2"), "A1", ms("C#4 E4 A4"), ms("A3 C#4"), "A2")]
    span = C["stagStart"] - t0
    nbars = 4
    bar = span / nbars  # ~2.05 s
    for bi in range(nbars):
        _, pat, root, choir, hrn, tim = prog[bi]
        tb = t0 + bi * bar
        for i, p in enumerate(pat):
            t = tb + i * bar / 8
            pr = (t - t0) / span
            acc = 12 if i in (0, 3, 6) else 0
            stac.n(t, bar / 9, p, 50 + 34 * pr + acc)
            pizz.n(t, 0.15, p + 12, 50 + 26 * pr + acc)
        basses.n(tb, bar * 0.97, m(root), 82)
        aahs.chord(tb, bar * 0.97, choir, 46 + bi * 7)
        horns.chord(tb, bar * 0.97, hrn, 44 + bi * 6)
        timp.n(tb, 0.9, m(tim), 74 + bi * 8)
        for off, v in ((0.0, 84), (bar / 2, 76), (bar * 0.75, 88)):
            taiko.n(tb + off, 0.5, 60, v + bi * 6)
    aahs.expr(t0, C["stagStart"], 50, 100)
    stac.expr(t0, C["stagStart"], 70, 112)

    # ------------------------------------------------------------------ S3 · the stag (15.1–20.2)
    ts = C["stagStart"]
    arps = [(ts + 0.05, 0.14, ms("D3 A3 D4 E4 F4 A4 D5 E5")), (ts + 1.3, 0.14, ms("Bb2 F3 A3 D4 F4 A4 Bb4 D5")),
            (ts + 2.55, 0.13, ms("G2 D3 G3 A3 Bb3 D4 G4 A4")), (ts + 3.75, 0.11, ms("A2 E3 A3 D4 E4 G4 A4 C#5"))]
    for t, step, ns_ in arps:
        harp.seq(t, step, ns_, 1.6, lambda i: 54 + i * 3)
    for tt in np.sort(R.uniform(ts + 0.2, ts + 2.4, 12)):
        celesta.n(tt, 0.8, int(R.choice(ms("D6 E6 F6 A6 C7 D7"))), int(R.integers(36, 60)))
    for t, d, ch in [(ts, 1.25, ms("D3 A3 E4 F4")), (ts + 1.25, 1.25, ms("Bb2 F3 A3 D4")), (ts + 2.5, 1.2, ms("G2 D3 Bb3 D4")), (ts + 3.7, 1.4, ms("A2 E3 A3 C#4 E4"))]:
        slow.chord(t, d, ch, 70)
    slow.expr(ts, C["ignite"], 40, 122)
    strings.n(ts + 2.5, 2.6, m("A5"), 58)
    strings.n(ts + 3.7, 1.4, m("D6"), 62)
    strings.expr(ts + 2.5, C["ignite"], 40, 118)
    aahs.chord(ts + 2.0, C["ignite"] - ts - 2.0, ms("A4 D5"), 60)
    aahs.expr(ts + 2.0, C["ignite"], 40, 116)
    roll(timp, C["ignite"] - 1.0, C["ignite"] - 0.02, m("A2"), 30, 112)

    # ------------------------------------------------------------------ HITS · ignite + burst
    t = C["ignite"]
    hit(t)
    trem.chord(t + 0.1, 1.1, ms("A5 D6"), 60)
    t = C["burst"]
    timp.n(t, 1.2, m("D2"), 120)
    taiko.n(t, 0.8, 60, 112)
    kit.n(t, 1.5, CRASH2, 112)
    glock.seq(t, 0.045, ms("D7 A6 F6 D6 A5 F5 D5"), 0.9, 100)
    harp.seq(t, 0.025, ms("D6 C6 A5 G5 F5 E5 D5 C5 A4 G4 F4 E4 D4"), 1.2, 88)
    brass.chord(t, 0.6, ms("D3 F3 A3"), 104)

    # ------------------------------------------------------------------ S4 · 56 botanicals (21.4–26.2)
    tb = C["burst"]
    b4 = [(tb, ms("F2 C3 A3 C4"), "F2", ms("F3 A3 C4 F4 A4 C5 A4 F4"), ms("F4 A4"), "C4", 1.2),
          (tb + 1.2, ms("E2 C3 G3 C4"), "E2", ms("E3 G3 C4 E4 G4 C5 G4 E4"), ms("E4 G4"), "C4", 1.2),
          (tb + 2.4, ms("D2 A2 F3 A3 D4"), "D2", ms("D3 F3 A3 D4 F4 A4 F4 D4"), ms("F4 A4"), "A3", 1.2),
          (tb + 3.6, ms("Bb1 F2 D3 F3 Bb3"), "Bb1", ms("Bb2 D3 F3 Bb3 D4 F4 D4 Bb3"), ms("F4 Bb4"), "Bb3", C["whip"] - tb - 3.6)]
    for t0, ch, root, arp, oo, hrn, d in b4:
        strings.chord(t0 + 0.02, d, ch, 74)
        oohs.chord(t0, d, oo, 48)
        horns.n(t0, d, m(hrn), 44)
        for k in range(int(d / 0.3)):
            harp.n(t0 + k * 0.15, 1.0, arp[k % 8], 52)
    strings.expr(tb, C["whip"] - 1.2, 85, 95)
    for t0, d, nm, v in [(tb + 0.6, 0.6, "A4", 76), (tb + 1.2, 1.2, "C5", 78), (tb + 2.4, 1.2, "D5", 74), (tb + 3.6, 1.2, "F5", 78)]:
        strings.n(t0, d, m(nm), v)
        strings.n(t0, d, m(nm) + 12, v - 18)
    strings.expr(C["whip"] - 1.2, C["whip"] - 0.05, 95, 122)
    roll(kit, C["whip"] - 0.75, C["whip"] - 0.05, SNARE, 30, 100, 0.05)
    roll(timp, C["whip"] - 0.55, C["whip"] - 0.05, m("D2"), 40, 110)
    t = C["whip"]
    brass.chord(t, 0.8, ms("Bb1 F2 Bb2 D3"), 110)
    timp.n(t, 1.0, m("D2"), 115)
    taiko.n(t, 0.8, 60, 110)
    kit.n(t, 1.2, CRASH, 100)

    # ------------------------------------------------------------------ S5 · oak (26.2–28.0) → S6 · ice cold (28.0–31.5)
    for t0, d, nm in [(26.5, 0.5, "F3"), (27.0, 0.3, "G3"), (27.3, 0.9, "A3")]:
        celli.n(t0, d, m(nm), 72)
    basses.n(26.2, 1.8, m("Bb1"), 74)
    slow.chord(26.2, 1.8, ms("D3 F3 Bb3"), 54)
    for i in range(7):  # pizzicato clock
        pizz.n(26.4 + i * 0.25, 0.2, m("A4") if i % 2 else m("D5"), 46 + (i % 2) * 6)
    tf = C["freeze"]
    trem.chord(tf, C["shatter"] - tf, ms("A5 D6 E6"), 44)
    trem.expr(tf, C["shatter"] - 0.05, 30, 122)
    strings.chord(tf + 0.6, C["shatter"] - tf - 0.6, ms("D4 E4 F4 A4"), 54)
    strings.expr(tf + 0.6, C["shatter"] - 0.05, 46, 122)
    oohs.chord(tf, C["shatter"] - tf, ms("D3 A3"), 44)
    for tt in np.sort(R.uniform(tf + 0.2, tf + 2.4, 11)):
        celesta.n(tt, 0.7, int(R.choice(ms("D6 E6 F6 A6 C7 D7 E7 F7"))), int(R.integers(36, 60)))
    glock.seq(C["coldText"] + 0.1, 0.14, ms("D6 F6 A6 D7 F7 A7"), 1.0, 76)
    basses.n(tf + 1.4, C["shatter"] - tf - 1.4, m("D1"), 70)
    roll(timp, C["crack"], C["shatter"] - 0.02, m("D2"), 40, 120)
    roll(kit, C["crack"] + 0.1, C["shatter"] - 0.02, SNARE, 40, 110, 0.045)

    # ------------------------------------------------------------------ HIT · shatter → S7 · the bottle (31.5–35.4)
    t = C["shatter"]
    timp.n(t, 1.6, m("D2"), 127)
    taiko.n(t, 1.0, 60, 127)
    for p in (KICK, CRASH, CRASH2, CHINA):
        kit.n(t, 1.6, p, 124)
    brass.chord(t, 1.0, ms("D2 A2 D3"), 126)
    tuba.n(t, 1.6, m("D1"), 126)
    strings.chord(t, 1.0, ms("D2 A2 D3 F3"), 118)
    basses.chord(t + 0.1, C["tahoe"] - t - 0.1, ms("D1 D2"), 60)
    basses.expr(t + 0.1, C["tahoe"] - 0.1, 60, 110)
    k = 0
    t = t + 1.0
    while t < C["tahoe"] - 0.3:  # 3+3+2 ostinato
        pr = (t - C["shatter"]) / (C["tahoe"] - C["shatter"])
        stac.n(t, 0.2, m("D3"), 50 + 46 * pr + (16 if k % 8 in (0, 3, 6) else 0))
        pizz.n(t, 0.15, m("D4"), 48 + 36 * pr + (18 if k % 8 in (0, 3, 6) else 0))
        k += 1
        t += 0.25
    for t0, d, ch in [(32.5, 1.3, ms("D3 F3 A3")), (33.8, 0.8, ms("D3 F3 Bb3")), (34.6, 0.8, ms("C#3 E3 A3"))]:
        horns.chord(t0, d, ch, 60 if t0 < 34.6 else 84)
    horns.expr(32.5, C["tahoe"] - 0.05, 60, 118)
    aahs.chord(34.6, 0.8, ms("A3 C#4 E4 A4"), 84)
    roll(kit, 34.9, C["tahoe"] - 0.03, SNARE, 40, 112, 0.045)
    t = C["tahoe"]
    timp.n(t, 1.4, m("D2"), 104)
    kit.n(t, 2.0, CRASH, 96)

    # ------------------------------------------------------------------ S8 · Lake Tahoe, c. 1997 (35.4–39.6): winter
    tt0 = C["tahoe"]
    slow.chord(tt0, C["fizz"] - tt0, ms("D4 F4 A4 C5"), 46)  # Dm9 colour
    slow.expr(tt0, C["fizz"], 40, 92)
    strings.chord(tt0 + 0.1, C["fizz"] - tt0 - 0.1, ms("D2 A2"), 56)
    for i, nm in enumerate(["A5", "D6", "F6", "A6", "G6", "F6", "E6", "D6"]):  # the call on celesta, glittering like snow
        celesta.n(tt0 + 0.5 + i * 0.42, 1.2, m(nm), 60)
        bells.n(tt0 + 0.5 + i * 0.42, 1.0, m(nm) - 12, 30)
    for tt in np.sort(R.uniform(tt0 + 0.3, C["fizz"] - 0.2, 10)):
        glock.n(tt, 0.6, int(R.choice(ms("D7 F7 A7 C8"))), int(R.integers(26, 44)))

    # ------------------------------------------------------------------ S9–S10 · energy (39.6–45.4)
    tf0 = C["fizz"]
    beat = 60.0 / C["bpm"]
    grid0 = C["slam"] - beat * round((C["slam"] - tf0) / beat)  # beats locked to the slam
    t = grid0
    k = 0
    while t < C["hover"] - 0.01:
        pr = (t - tf0) / (C["hover"] - tf0)
        for j in range(2):  # eighths
            stac.n(t + j * beat / 2, beat / 2.4, m("D3") if (k + j) % 4 else m("A2"), 54 + 40 * pr)
        if k % 2 == 0:
            taiko.n(t, 0.5, 60, 70 + 30 * pr)
        k += 1
        t += beat
    prog2 = [(tf0, ms("D3 F3 A3"), "D2"), (tf0 + 2.0, ms("D3 F3 Bb3"), "Bb1"), (C["pour"], ms("C3 F3 A3"), "F1"), (C["pour"] + 1.4, ms("C3 E3 G3"), "C2")]
    for t0, ch, root in prog2:
        d = 2.0 if t0 < C["pour"] else 1.4
        strings.chord(t0, d, ch, 70)
        basses.n(t0, d, m(root), 80)
    strings.expr(tf0, C["hover"], 60, 104)
    aahs.chord(C["pour"], C["hover"] - C["pour"], ms("A4 D5"), 56)
    aahs.expr(C["pour"], C["hover"], 50, 100)

    # ------------------------------------------------------------------ S11 · the hover: suspense (45.4–51.4)
    th0 = C["hover"]
    trem.chord(th0, C["hit"] - th0, ms("D6 E6"), 34)
    trem.expr(th0, C["hit"] - 0.1, 26, 100)
    basses.n(th0, C["hit"] - th0 - 0.2, m("D1"), 58)
    oohs.chord(th0 + 1.0, C["hit"] - th0 - 1.2, ms("D3 A3"), 40)
    oohs.expr(th0 + 1.0, C["hit"] - 0.2, 30, 96)
    celli.seq(th0 + 0.5, 0.6, ms("D3 Eb3 D3 Eb3 D3 Eb3"), 0.55, 54)  # a semitone, ticking like a clock
    strings.chord(C["release"] - 1.6, 1.4, ms("D4 Eb4 A4"), 60)
    strings.expr(C["release"] - 1.6, C["release"] - 0.2, 40, 116)
    roll(timp, C["release"] - 1.4, C["release"] - 0.15, m("D2"), 30, 104)

    # ------------------------------------------------------------------ HIT · the shot hits the glass (51.4) → slow motion
    t = C["hit"]
    hit(t)
    trumpet.n(t, 1.2, m("A5"), 112)
    slow.chord(t + 0.3, C["rampUp"] - t, ms("D3 A3 D4 F4"), 66)
    slow.expr(t + 0.3, C["rampUp"], 90, 60)
    aahs.chord(t + 0.2, C["rampUp"] - t, ms("D4 A4 D5"), 70)
    aahs.expr(t + 0.2, C["rampUp"], 100, 64)
    basses.chord(t, C["rampUp"] - t + 0.4, ms("D1 D2"), 76)

    # ------------------------------------------------------------------ S12 · the build into the slam (53.6–56.6)
    tr0 = C["rampUp"]
    scale = ms("D4 E4 F4 G4 A4 Bb4 C5 C#5 D5 E5 F5 G5 A5")
    step = (C["slam"] - 0.3 - tr0) / len(scale)
    for i, p in enumerate(scale):
        strings.n(tr0 + i * step, step * 1.05, p, 70 + i * 4)
        strings.n(tr0 + i * step, step * 1.05, p - 12, 64 + i * 4)
    strings.expr(tr0, C["slam"] - 0.3, 80, 124)
    aahs.chord(tr0, C["slam"] - 0.3 - tr0, ms("A3 D4 F4 A4"), 70)
    aahs.expr(tr0, C["slam"] - 0.3, 60, 124)
    horns.chord(tr0 + 1.5, C["slam"] - 0.3 - tr0 - 1.5, ms("A3 C#4 E4"), 70)
    horns.expr(tr0 + 1.5, C["slam"] - 0.3, 60, 124)
    roll(timp, tr0 + 1.0, C["slam"] - 0.3, m("A2"), 40, 124)
    roll(kit, tr0 + 1.6, C["slam"] - 0.3, SNARE, 36, 124, 0.04)
    for i in range(4):
        taiko.n(C["slam"] - 0.5 - 0.125 * (3 - i) - 0.05, 0.1, 60, 96 + i * 8)

    # ------------------------------------------------------------------ S13 · the beat: JÄGERBOMB (56.6–64.6), 120 BPM
    ts0 = C["slam"]
    theme = [("A3", 0.000, 0.375), ("D4", 0.375, 0.125), ("F4", 0.500, 0.5), ("A4", 1.000, 0.95), ("G4", 2.000, 0.5), ("F4", 2.500, 0.25),
             ("E4", 2.750, 0.25), ("D4", 3.000, 0.95), ("C4", 4.000, 0.375), ("F4", 4.375, 0.125), ("A4", 4.500, 0.5), ("C5", 5.000, 0.95),
             ("Bb4", 6.000, 0.5), ("A4", 6.500, 0.25), ("G4", 6.750, 0.25), ("E4", 7.000, 0.9)]
    for nm, dt, d in theme:
        horns.n(ts0 + dt, d, m(nm), 120)
        bones.n(ts0 + dt, d, m(nm) - 12, 104)
        if dt >= 4.0:
            trumpet.n(ts0 + dt, d, m(nm) + 12, 98)
    horns.expr(ts0, ts0 + 0.01, 122, 122)
    bars = [(ts0, ms("D4 F4 A4 F4"), ("D2", "D3"), ms("D4 F4 A4"), ms("D3 F3 A3")),
            (ts0 + 2.0, ms("D4 F4 Bb4 F4"), ("Bb1", "Bb2"), ms("D4 F4 Bb4"), ms("Bb2 D3 F3")),
            (ts0 + 4.0, ms("C4 F4 A4 F4"), ("F1", "F2"), ms("C4 F4 A4"), ms("F2 A2 C3 F3")),
            (ts0 + 6.0, ms("C#4 E4 A4 E4"), ("A1", "A2"), ms("C#4 E4 A4"), ms("A2 C#3 E3"))]
    for t0, cyc, (lo, hi), choir, stab in bars:
        for i in range(16):
            stac.n(t0 + i * 0.125, 0.11, cyc[i % 4], 84 + (16 if i % 4 == 0 else 0))
        for i in range(8):
            stac.n(t0 + i * 0.25, 0.22, m(lo) if i % 2 == 0 else m(hi), 96)
        basses.n(t0, 2.0, m(lo), 104)
        aahs.chord(t0, 2.0, choir, 98)
        brass.chord(t0, 0.4, stab, 112)
    stac.expr(ts0, ts0 + 0.01, 120, 120)
    basses.expr(ts0, ts0 + 0.01, 120, 120)
    for bt in np.arange(ts0, C["endcard"] - 0.01, 0.5):
        b = int(round((bt - ts0) / 0.5))
        if b % 2 == 0:
            taiko.n(bt, 0.5, 60, 118)
        if b % 4 == 0:
            timp.n(bt, 0.8, m(["D2", "Bb1", "F2", "A1"][min(3, b // 4)]) + (12 if b // 4 == 1 else 0), 112)
    for t0 in (ts0, ts0 + 2.0, ts0 + 4.0, ts0 + 6.0):
        kit.n(t0, 1.5, CRASH, 110)
    for c in C["cuts"][1:]:  # stingers on the cuts
        bells.n(c, 1.2, m("D6"), 70)
        brass.chord(c, 0.25, ms("D3 A3 D4"), 104)
    for i in range(8):
        kit.n(C["endcard"] - 0.5 + i * 0.0625, 0.06, [SNARE, TOM_H, TOM_M, TOM_L][i % 4], 96 + i * 4)

    # ------------------------------------------------------------------ END · D major (64.6–74)
    t = C["endcard"]
    brass.chord(t, 1.1, ms("D2 A2 D3 F#3 A3 D4"), 124)
    bones.chord(t, 1.0, ms("D2 A2 D3"), 118)
    tuba.n(t, 1.2, m("D1"), 120)
    trumpet.n(t, 1.0, m("F#5"), 116)
    horns.chord(t, 1.2, ms("D4 F#4 A4"), 116)
    strings.chord(t, 8.4, ms("D2 A2 D3 F#3 A3 D4 F#4 A4 D5"), 118)
    strings.expr(t, t + 0.9, 120, 56)
    strings.expr(69.0, 73.3, 56, 26)
    aahs.chord(t, 8.2, ms("D4 F#4 A4 D5"), 108)
    aahs.expr(t, t + 0.9, 118, 54)
    aahs.expr(69.0, 73.2, 54, 26)
    timp.n(t, 2.0, m("D2"), 127)
    taiko.n(t, 1.0, 60, 127)
    for p in (KICK, CRASH):
        kit.n(t, 2.0, p, 120)
    bells.n(t, 4.0, m("D5"), 100)
    harp.seq(t, 0.03, ms("D3 F#3 A3 D4 F#4 A4 D5 F#5 A5 D6"), 2.0, 92)
    tc = C["tagline"] + 2.2  # the call, now in D major, after the tagline
    for nm, dt, d in [("A3", 0.0, 0.45), ("D4", 0.45, 0.15), ("F#4", 0.6, 0.6), ("A4", 1.2, 2.0)]:
        horns.n(tc + dt, d, m(nm), 82)
        celesta.n(tc + dt, d + 0.8, m(nm) + 12, 60)
    horns.expr(tc, tc + 0.01, 100, 100)
    timp.n(tc + 1.2, 2.0, m("D2"), 50)
    bells.n(tc + 1.2, 4.0, m("D4"), 58)

    return {
        "strings": [strings, stac, trem, pizz, celli, basses, slow],
        "brass": [horns, brass, bones, tuba, trumpet],
        "choir": [aahs, oohs],
        "keys": [celesta, harp, glock, bells],
        "perc": [timp, taiko, kit],
    }


def render_stems(C, seconds):
    return {name: render(parts, seconds) for name, parts in compose(C).items()}
