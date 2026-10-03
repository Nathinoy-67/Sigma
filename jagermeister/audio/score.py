#!/usr/bin/env python3
"""The orchestral score (v2), written as MIDI and played through the MuseScore General SoundFont.

Key: D minor, resolving to D major on the end card. A hunting-horn call (A–D–F–A | G–F–E–D) is
the leitmotif: celesta over the title, horns on the drop, a solo horn in D major at the very end.
Each stem (strings, brass, choir, keys, percussion) is rendered separately with FluidSynth so the
mix can treat them differently.

    from score import render_stems; stems = render_stems(cues)   # dict name -> (2, n) float array
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
    # ------------------------------------------------------------------ the band
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

    # ------------------------------------------------------------------ S1 · title (0–4.4)
    basses.n(0.0, 4.7, m("D2"), 72)
    basses.expr(0.0, 4.4, 30, 90)
    celli.n(0.0, 4.7, m("D3"), 58)
    celli.n(1.5, 3.2, m("A2"), 52)
    oohs.chord(0.8, 4.2, ms("D4 A4"), 46)
    oohs.expr(0.8, 4.4, 40, 95)
    motif = [("A4", 1.20, 0.45), ("D5", 1.65, 0.15), ("F5", 1.80, 0.6), ("A5", 2.40, 1.2), ("G5", 3.60, 0.6), ("F5", 4.20, 0.3), ("E5", 4.50, 0.3), ("D5", 4.80, 1.4)]
    for nm, t, d in motif:
        celesta.n(t, d + 0.6, m(nm), 72)
        harp.n(t, d + 0.8, m(nm) - 12, 44)

    # ------------------------------------------------------------------ S2 · flight (4.4–11.6), 120 BPM
    bars = [(4.4, "Dm", ms("D3 D3 A3 D3 F3 D3 A3 D3"), "D2", ms("D4 F4 A4"), ms("A3 D4"), "D2"),
            (6.4, "Bb", ms("Bb2 Bb2 F3 Bb2 D3 Bb2 F3 Bb2"), "Bb1", ms("D4 F4 Bb4"), ms("F3 Bb3"), "F2"),
            (8.4, "Gm", ms("G2 G2 D3 G2 Bb2 G2 D3 G2"), "G1", ms("D4 G4 Bb4"), ms("G3 D4"), "G2"),
            (10.4, "A", ms("A2 A2 E3 A2 C#3"), "A1", ms("C#4 E4 A4"), ms("A3 C#4 E4"), "A2")]
    for bi, (t0, _, pat, root, choir, hrn, tim) in enumerate(bars):
        for i, p in enumerate(pat):
            t = t0 + i * 0.25
            prog = (t - 4.4) / 7.2
            acc = 14 if i in (0, 3, 6) else 0
            stac.n(t, 0.2, p, 56 + 40 * prog + acc)
            pizz.n(t, 0.15, p + 12, 58 + 30 * prog + acc)  # articulation on the ostinato
            if bi >= 1:
                stac.n(t, 0.2, p + 12, 40 + 34 * prog + acc)
        dur = 1.95 if bi < 3 else 1.4
        basses.n(t0, dur, m(root), 86)
        aahs.chord(t0, dur, choir, 52 + bi * 8)
        horns.chord(t0, dur, hrn, 50 + bi * 6)
        timp.n(t0, 0.9, m(tim), 80 + bi * 10)
        for off, v in ((0.0, 92), (1.0, 84), (1.5, 96)):
            if t0 + off < 11.6:
                taiko.n(t0 + off, 0.5, 60, v + bi * 7)
    aahs.expr(4.4, 11.6, 60, 110)
    stac.expr(4.4, 11.6, 80, 118)
    for i, nm in enumerate(["A3", "C#4", "E4", "A4"]):  # horn call into the clearing
        horns.n(10.40 + i * 0.25, 0.22 if i < 3 else 1.0, m(nm), 92)
    for i, p in enumerate([TOM_L, TOM_L, TOM_M, TOM_M, TOM_H, TOM_H, TOM_M, TOM_L]):
        kit.n(10.9 + i * 0.0625, 0.06, p, 70 + i * 5)
    timp.n(11.62, 1.2, m("D2"), 70)

    # ------------------------------------------------------------------ S3 · the stag (11.6–16.0)
    arps = [(11.65, 0.13, ms("D3 A3 D4 E4 F4 A4 D5 E5")), (12.85, 0.13, ms("Bb2 F3 A3 D4 F4 A4 Bb4 D5")),
            (14.05, 0.12, ms("G2 D3 G3 A3 Bb3 D4 G4 A4")), (15.05, 0.1, ms("A2 E3 A3 D4 E4 G4"))]
    for t0, step, ns_ in arps:
        harp.seq(t0, step, ns_, 1.6, lambda i: 58 + i * 3)
    harp.n(15.7, 1.0, m("C#5"), 80)
    for t in np.sort(R.uniform(11.7, 13.5, 14)):
        celesta.n(t, 0.8, int(R.choice(ms("D6 E6 F6 A6 C7 D7 E7 F7"))), int(R.integers(38, 66)))
    for t0, d, ch in [(11.6, 1.25, ms("D3 A3 E4 F4")), (12.8, 1.25, ms("Bb2 F3 A3 D4")), (14.0, 1.05, ms("G2 D3 Bb3 D4")), (15.0, 1.05, ms("A2 E3 A3 C#4 E4"))]:
        slow.chord(t0, d, ch, 72)
    slow.expr(11.6, 16.0, 40, 122)
    strings.n(14.0, 2.0, m("A5"), 60)
    strings.n(15.0, 1.0, m("D6"), 64)
    strings.expr(14.0, 16.0, 40, 120)
    aahs.chord(13.4, 2.6, ms("A4 D5"), 64)
    aahs.expr(13.4, 16.0, 40, 118)
    roll(timp, 15.0, 15.98, m("A2"), 30, 112)

    # ------------------------------------------------------------------ HIT · ignite (16.0)
    t = C["ignite"]
    brass.chord(t, 1.4, ms("D2 A2 D3 F3 A3"), 122)
    bones.chord(t, 1.2, ms("D2 A2 D3"), 118)
    tuba.n(t, 1.5, m("D1"), 120)
    horns.chord(t, 1.3, ms("D4 F4 A4"), 120)
    strings.chord(t, 1.3, ms("D2 A2 D3 F3 A3 D4 F4 A4"), 116)
    aahs.chord(t, 1.4, ms("D4 F4 A4 D5"), 104)
    timp.n(t, 1.5, m("D2"), 127)
    taiko.n(t, 1.0, 60, 127)
    for p in (CRASH, CHINA, KICK):
        kit.n(t, 1.5, p, 122)
    strings.expr(t, t + 0.01, 120, 120)
    trem.chord(t + 0.1, 1.2, ms("A5 D6"), 62)
    for tt in np.sort(R.uniform(t + 0.1, t + 1.2, 8)):
        celesta.n(tt, 0.6, int(R.choice(ms("D6 F6 A6 D7"))), 52)

    # ------------------------------------------------------------------ HIT · burst (17.3)
    t = C["burst"]
    timp.n(t, 1.2, m("D2"), 120)
    taiko.n(t, 0.8, 60, 112)
    kit.n(t, 1.5, CRASH2, 112)
    glock.seq(t, 0.045, ms("D7 A6 F6 D6 A5 F5 D5"), 0.9, 100)
    harp.seq(t, 0.025, ms("D6 C6 A5 G5 F5 E5 D5 C5 A4 G4 F4 E4 D4"), 1.2, 88)
    brass.chord(t, 0.6, ms("D3 F3 A3"), 104)

    # ------------------------------------------------------------------ S4 · 56 botanicals (17.3–25.0)
    b4 = [(17.3, ms("F2 C3 A3 C4"), "F2", ms("F3 A3 C4 F4 A4 C5 A4 F4"), ms("F4 A4"), "C4"),
          (19.3, ms("E2 C3 G3 C4"), "E2", ms("E3 G3 C4 E4 G4 C5 G4 E4"), ms("E4 G4"), "C4"),
          (21.3, ms("D2 A2 F3 A3 D4"), "D2", ms("D3 F3 A3 D4 F4 A4 F4 D4"), ms("F4 A4"), "A3"),
          (23.3, ms("Bb1 F2 D3 F3 Bb3"), "Bb1", ms("Bb2 D3 F3 Bb3 D4 F4 D4 Bb3"), ms("F4 Bb4"), "Bb3")]
    for t0, ch, root, arp, oo, hrn in b4:
        d = 2.0 if t0 < 23.3 else 1.7
        strings.chord(t0 + 0.02, d, ch, 76)
        oohs.chord(t0, d, oo, 50)
        horns.n(t0, d, m(hrn), 46)
        for k in range(4 if t0 < 23.3 else 3):
            stac.n(t0 + k * 0.5, 0.42, m(root), 70)
        for k in range(8 if t0 < 23.3 else 7):
            harp.n(t0 + k * 0.25, 1.0, arp[k % 8], 54)
    strings.expr(17.3, 23.0, 85, 95)
    for t0, d, nm, v in [(17.3, 1.0, "A4", 82), (18.3, 1.0, "C5", 84), (19.3, 2.0, "E5", 70), (21.3, 1.0, "D5", 70), (22.3, 1.0, "F5", 74), (23.3, 1.7, "D5", 80)]:
        strings.n(t0, d, m(nm), v)
        strings.n(t0, d, m(nm) + 12, v - 18)
    for i, nm in enumerate(["D5", "F5", "G5", "A5", "C6", "D6", "F6", "G6"]):  # one note per ingredient
        celesta.n(C["ingredients"] + i * 0.22, 1.0, m(nm), 86)
        harp.n(C["ingredients"] + i * 0.22, 1.2, m(nm) - 12, 70)
    glock.chord(C["ingredients"] + 1.95, 1.5, ms("D6 A6"), 68)
    strings.expr(23.3, 24.95, 95, 122)
    roll(kit, 24.2, 24.95, SNARE, 30, 100, 0.05)
    roll(timp, 24.4, 24.95, m("D2"), 40, 110)
    t = C["whip"]
    brass.chord(t, 0.8, ms("Bb1 F2 Bb2 D3"), 110)
    timp.n(t, 1.0, m("D2"), 115)
    taiko.n(t, 0.8, 60, 110)
    kit.n(t, 1.2, CRASH, 100)

    # ------------------------------------------------------------------ S5 · 365 days in oak (25.0–30.6)
    for t0, d, nm in [(25.4, 0.8, "F3"), (26.2, 0.4, "G3"), (26.6, 1.4, "A3"), (28.0, 0.5, "G3"), (28.5, 0.5, "F3"), (29.0, 0.6, "E3"), (29.6, 1.2, "D3")]:
        celli.n(t0, d, m(nm), 74)
    for t0, d, root, ch, hrn in [(25.0, 2.0, "Bb1", ms("D3 F3 Bb3"), ms("F3 Bb3")), (27.0, 2.0, "G1", ms("D3 G3 Bb3"), ms("G3 D4")), (29.0, 1.8, "D2", ms("D3 F3 A3"), ms("F3 A3"))]:
        basses.n(t0, d, m(root), 76)
        slow.chord(t0, d, ch, 56)
        horns.chord(t0, d, hrn, 44)
    for i in range(11):  # pizzicato clock
        pizz.n(C["countStart"] + i * 0.25, 0.2, m("A4") if i % 2 else m("D5"), 48 + (i % 2) * 6)
    t = C["countEnd"]
    kit.n(t, 0.8, TOM_L, 112)
    taiko.n(t, 0.8, 60, 100)
    timp.n(t, 1.0, m("D2"), 88)
    slow.chord(29.0, 1.6, ms("D3 A3 E4"), 50)

    # ------------------------------------------------------------------ S6 · ice cold (30.6–35.6)
    trem.chord(30.6, 4.9, ms("A5 D6 E6"), 44)
    trem.expr(30.6, 35.5, 30, 122)
    strings.chord(31.5, 4.0, ms("D4 E4 F4 A4"), 56)
    strings.expr(31.5, 35.5, 50, 122)
    oohs.chord(30.6, 4.9, ms("D3 A3"), 46)
    for tt in np.sort(R.uniform(30.8, 33.4, 13)):
        celesta.n(tt, 0.7, int(R.choice(ms("D6 E6 F6 A6 C7 D7 E7 F7"))), int(R.integers(38, 62)))
    glock.seq(C["frostText"] + 0.12, 0.14, ms("D6 F6 A6 D7 F7 A7"), 1.0, 80)
    basses.n(33.5, 2.1, m("D1"), 72)
    roll(timp, 34.9, 35.58, m("D2"), 40, 120)
    roll(kit, 35.0, 35.58, SNARE, 40, 110, 0.045)

    # ------------------------------------------------------------------ HIT · shatter (35.6)
    t = C["shatter"]
    timp.n(t, 1.6, m("D2"), 127)
    taiko.n(t, 1.0, 60, 127)
    for p in (KICK, CRASH, CRASH2, CHINA):
        kit.n(t, 1.6, p, 126)
    brass.chord(t, 1.0, ms("D2 A2 D3"), 127)
    tuba.n(t, 1.6, m("D1"), 127)
    strings.chord(t, 1.0, ms("D2 A2 D3 F3"), 120)

    # ------------------------------------------------------------------ S7 · the bottle in the dark (35.6–41.8)
    basses.chord(35.7, 5.9, ms("D1 D2"), 62)
    basses.expr(35.7, 41.6, 60, 115)
    slow.chord(35.8, 1.7, ms("D5 A5"), 40)
    k = 0
    t = 37.0
    while t < 41.55:  # 3+3+2 ostinato
        prog = (t - 37.0) / 4.55
        stac.n(t, 0.2, m("D3"), 50 + 50 * prog + (16 if k % 8 in (0, 3, 6) else 0))
        pizz.n(t, 0.15, m("D4"), 48 + 40 * prog + (18 if k % 8 in (0, 3, 6) else 0))
        if t >= 39.8:
            timp.n(t, 0.24, m("D2") if k % 2 == 0 else m("A2"), 60 + 50 * prog)
        k += 1
        t += 0.25
    for t0, d, ch in [(37.0, 1.8, ms("D3 F3 A3")), (38.8, 1.0, ms("D3 F3 Bb3")), (39.8, 1.0, ms("D3 G3 Bb3")), (40.8, 0.8, ms("C#3 E3 A3"))]:
        horns.chord(t0, d, ch, 58 if t0 < 40.8 else 86)
    horns.expr(37.0, 41.6, 60, 120)
    bones.n(40.8, 0.8, m("A1"), 96)
    aahs.chord(40.8, 0.8, ms("A3 C#4 E4 A4"), 92)
    roll(kit, 41.0, 41.6, SNARE, 40, 120, 0.045)

    # ------------------------------------------------------------------ S8 · the drop (41.8–47.8), 120 BPM
    theme = [("A3", 41.800, 0.375), ("D4", 42.175, 0.125), ("F4", 42.300, 0.5), ("A4", 42.800, 0.95), ("G4", 43.800, 0.5), ("F4", 44.300, 0.25),
             ("E4", 44.550, 0.25), ("D4", 44.800, 0.95), ("C4", 45.800, 0.375), ("F4", 46.175, 0.125), ("A4", 46.300, 0.5), ("C5", 46.800, 0.5), ("E5", 47.300, 0.45)]
    for nm, t0, d in theme:
        horns.n(t0, d, m(nm), 118)
        bones.n(t0, d, m(nm) - 12, 104)
        if t0 >= 45.8:
            trumpet.n(t0, d, m(nm) + 12, 96)
    horns.expr(41.8, 41.81, 120, 120)
    drop_bars = [(41.8, 2.0, ms("D4 F4 A4 F4"), ("D2", "D3"), ms("D4 F4 A4"), ms("D3 F3 A3")),
                 (43.8, 2.0, ms("D4 F4 Bb4 F4"), ("Bb1", "Bb2"), ms("D4 F4 Bb4"), ms("Bb2 D3 F3")),
                 (45.8, 1.0, ms("C4 F4 A4 F4"), ("F1", "F2"), ms("C4 F4 A4"), ms("F2 A2 C3 F3")),
                 (46.8, 1.0, ms("C4 E4 G4 E4"), ("C2", "C3"), ms("C4 E4 G4"), ms("C3 E3 G3"))]
    for t0, d, cyc, (lo, hi), choir, stab in drop_bars:
        for i in range(int(d / 0.125)):
            stac.n(t0 + i * 0.125, 0.11, cyc[i % 4], 84 + (16 if i % 4 == 0 else 0))
        for i in range(int(d / 0.25)):
            stac.n(t0 + i * 0.25, 0.22, m(lo) if i % 2 == 0 else m(hi), 96)
        basses.n(t0, d, m(lo), 104)
        aahs.chord(t0, d, choir, 98)
        brass.chord(t0, 0.4, stab, 112)
    stac.expr(41.8, 41.81, 120, 120)
    basses.expr(41.8, 41.81, 120, 120)
    for bt in np.arange(41.8, 47.8, 0.5):
        beat = int(round((bt - 41.8) / 0.5))
        if beat % 2 == 0:
            taiko.n(bt, 0.5, 60, 118)
        if beat % 4 == 0:
            timp.n(bt, 0.8, m("D2") if bt < 43.8 else (m("Bb1") + 12 if bt < 45.8 else m("F2")), 112)
        if beat % 2 == 1:
            kit.n(bt, 0.3, SNARE, 104)
        kit.n(bt, 0.3, KICK, 110)
    for t0 in (41.8, 43.8, 45.8):
        kit.n(t0, 1.5, CRASH, 112)
    for t0 in (43.55, 45.55):
        for i in range(4):
            taiko.n(t0 + i * 0.0625, 0.06, 60, 90 + i * 8)
    for i in range(8):
        kit.n(47.3 + i * 0.0625, 0.06, [SNARE, TOM_H, TOM_M, TOM_L][i % 4], 96 + i * 4)

    # ------------------------------------------------------------------ END · D major (47.8–60)
    t = C["endcard"]
    # a punchy hit that clears quickly for the voice ("Jägermeister" lands in its decay)
    brass.chord(t, 1.1, ms("D2 A2 D3 F#3 A3 D4"), 124)
    bones.chord(t, 1.0, ms("D2 A2 D3"), 118)
    tuba.n(t, 1.2, m("D1"), 120)
    trumpet.n(t, 1.0, m("F#5"), 116)
    horns.chord(t, 1.2, ms("D4 F#4 A4"), 116)
    strings.chord(t, 9.6, ms("D2 A2 D3 F#3 A3 D4 F#4 A4 D5"), 118)
    strings.expr(t, t + 0.9, 120, 58)
    strings.expr(52.0, 57.6, 58, 30)
    aahs.chord(t, 9.4, ms("D4 F#4 A4 D5"), 108)
    aahs.expr(t, t + 0.9, 118, 56)
    aahs.expr(52.0, 57.4, 56, 28)
    timp.n(t, 2.0, m("D2"), 127)
    taiko.n(t, 1.0, 60, 127)
    for p in (KICK, CRASH):
        kit.n(t, 2.0, p, 120)
    bells.n(t, 4.0, m("D5"), 100)
    harp.seq(t, 0.03, ms("D3 F#3 A3 D4 F#4 A4 D5 F#5 A5 D6"), 2.0, 92)
    for nm, t0, d in [("A3", 53.85, 0.45), ("D4", 54.30, 0.15), ("F#4", 54.45, 0.6), ("A4", 55.05, 2.0)]:  # the call, now in D major
        horns.n(t0, d, m(nm), 84)
        celesta.n(t0, d + 0.8, m(nm) + 12, 62)
    horns.expr(53.8, 53.81, 100, 100)
    timp.n(55.05, 2.0, m("D2"), 52)
    bells.n(55.05, 4.0, m("D4"), 60)

    return {
        "strings": [strings, stac, trem, pizz, celli, basses, slow],
        "brass": [horns, brass, bones, tuba, trumpet],
        "choir": [aahs, oohs],
        "keys": [celesta, harp, glock, bells],
        "perc": [timp, taiko, kit],
    }


def render_stems(C, seconds):
    return {name: render(parts, seconds) for name, parts in compose(C).items()}
