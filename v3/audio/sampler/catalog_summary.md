# Sample catalog summary (VSCO-2-CE + VCSL)

Built 2026-10-22 10:20:04 by `build_catalog.py`: **7399 wav files** in **884 instrument+articulation groups**. Full per-sample data (MIDI note, velocity layer, round robin, path, length, peak, RMS, K-weighted loudness, onset/tail, detected pitch) is in `catalog.json`.

Conventions: `midi` is scientific (C4 = 60). VSCO-2-CE orchestral folders name middle C "C3", so +12 is applied (verified per folder by a harmonic pitch detector; see the octave column). Timpani carry no note names: their pitch is detected from the principal mode. Unpitched groups use notional key 60. Velocity layer 0 = softest. Most files are 44.1 kHz; the sampler converts to 48 kHz.

## Picks for an epic trailer score

| Role | Sampler id(s) | Source group | Why |
|---|---|---|---|
| Big drums (trailer low end) | `perc.bass_drum  (+ perc.bass_drum.vcsl, .b, .legacy)` | VSCO-2-CE/Percussion::BDrumNewhit | concert bass drum, 7 velocity layers x 2 RR, long natural room tail; pitch it down 3-7 st (pitch=53..57) for the "huge" trailer boom |
| Giant drum / taiko substitute | `perc.giant_drum (mallet), .hand, .sticks, .rim` | VSCO-2-CE/VSCO 1 Percussion/drums/other/ethnic/giant/* | large ethnic drum: deep, wide body, 4-7 dynamics; the closest thing to a taiko in both libraries |
| Toms (ensemble patterns) | `perc.toms.low / perc.toms.high (mallet), .stick variants; perc.tenor_drum.low/.high` | VCSL Tom 1/Tom 2 Mallet, VCSL Legacy Toms tenor_lower/higher | mallet toms (3 layers x 2 RR) for the pattern; tenor drums have 7 layers x 4-6 RR -> best for fast 16ths |
| Timpani | `perc.timpani (34 tunings, D#2-A3), perc.timpani.vsco, perc.timpani.roll` | VCSL/.../Timpani 2/Hit::Timpani_Hit | pitch detected per tuning (principal mode); nearly chromatic D#2..A3, so shifts stay < 1 st; 3 layers x 2 RR |
| Low brass | `brass.trombones.sus (a3), brass.tuba.sus, brass.trombone_old.sus (5 layers x 3 RR), *.stac` | VSCO-2-CE/Brass/Tenor Trombone/sus, Tuba/sus, OldTrombone/Sustain | tenor trombone A#1-F4 and tuba F1-D4 sustains, 3 layers; OldTrombone has the most layers/RR (F2-G4) for chord pads; trombone stac 4 layers x 2 RR for hits |
| String ostinato | `strings.celli.spic, strings.violas.spic, strings.violins.spic, strings.basses.spic` | VSCO-2-CE/Strings/*/spic | section spiccato, 2 layers x 2 RR, sampled every 2-3 semitones |
| Sustained strings | `strings.{violins,violas,celli,basses}.sus, *.trem` | VSCO-2-CE/Strings/*/susvib, trem | section sustains 2 layers (~10 s, loop-extended beyond); tremolo for builds |
| Horns | `brass.horns.sus (a4), brass.horns.stac` | VSCO-2-CE/Brass/F Horn/sus | solo horn doubled into a 4-horn section; dense up to C4 (sounding) - keep heroic lines F2-D4 and double higher octaves with trumpets |
| Cymbal swells | `perc.cymbal.swell (auto-picks a 1.5-7.5 s crescendo that PEAKS at t+dur), fx.reverse_cymbal` | VCSL Suspended Cymbal 1/2 cresc_*, VSCO susCymb1-cresc-* | real recorded rolls; reversed clash cymbals for the classic suck-back |
| Gongs / tam-tam | `perc.gong (10 dynamics), perc.gong.hard, perc.gong.roll, fx.reverse_gong` | VSCO-2-CE/VSCO 1 Percussion/varMetal/Gong::gong_hit | pppp..fff, very long tails |
| Hits / metals | `perc.cymbal.crash (4 layers x 2 RR), perc.anvil, perc.brake_drum, perc.snare.rimshot` | VCSL Clash Cymbals 1, VSCO Anvil/BrakeDrum | layer under the downbeat hits |

## Sampler instrument ids (sampler.py)

Range = sampled range +-3 semitones (notes outside it still play, with a warning). Unison = number of doubled players built from a solo recording.

| Id | Kind | Sampled | Layers | RR | Unison | Default pan | Source group(s) |
|---|---|---|---|---|---|---|---|
| `strings.violins.spic` | short | G3-D6 | 2 | 2 | 1 | -0.50 | Strings/Violin Section/Spic |
| `strings.violins.sus` | sustain | G3-D6 | 2 | 1 | 1 | -0.50 | Strings/Violin Section/susVib |
| `strings.violins.trem` | sustain | G3-D6 | 2 | 1 | 1 | -0.50 | Strings/Violin Section/Trem |
| `strings.violins.pizz` | short | G3-D6 | 2 | 2 | 1 | -0.50 | Strings/Violin Section/Pizz |
| `strings.violas.spic` | short | C3-D6 | 2 | 2 | 1 | +0.12 | Strings/Viola Section/spic |
| `strings.violas.sus` | sustain | C3-D6 | 2 | 1 | 1 | +0.12 | Strings/Viola Section/susvib |
| `strings.violas.trem` | sustain | C3-D6 | 2 | 1 | 1 | +0.12 | Strings/Viola Section/trem |
| `strings.violas.pizz` | short | C3-D6 | 2 | 2 | 1 | +0.12 | Strings/Viola Section/pizz |
| `strings.celli.spic` | short | C2-F5 | 2 | 2 | 1 | +0.28 | Strings/Cello Section/spic |
| `strings.celli.sus` | sustain | C2-F5 | 2 | 2 | 1 | +0.28 | Strings/Cello Section/susvib |
| `strings.celli.trem` | sustain | C2-F5 | 2 | 1 | 1 | +0.28 | Strings/Cello Section/trem |
| `strings.celli.pizz` | short | C2-F5 | 2 | 2 | 1 | +0.28 | Strings/Cello Section/pizzT |
| `strings.basses.spic` | short | E1-B3 | 2 | 2 | 3 | +0.40 | Strings/Solo Contrabass/Spic |
| `strings.basses.sus` | sustain | F#1-B3 | 2 | 1 | 3 | +0.40 | Strings/Solo Contrabass/SusVib |
| `strings.basses.susnv` | sustain | E1-B3 | 2 | 1 | 3 | +0.40 | Strings/Solo Contrabass/SusNV |
| `strings.basses.trem` | sustain | E1-B3 | 2 | 1 | 3 | +0.40 | Strings/Solo Contrabass/Trem |
| `strings.basses.pizz` | short | E1-B3 | 2 | 2 | 3 | +0.40 | Strings/Solo Contrabass/Pizz |
| `strings.bass_solo.spic` | short | E1-B3 | 2 | 2 | 1 | +0.40 | Strings/Solo Contrabass/Spic |
| `strings.bass_solo.sus` | sustain | F#1-B3 | 2 | 1 | 1 | +0.40 | Strings/Solo Contrabass/SusVib |
| `strings.bass_solo.pizz` | short | E1-B3 | 2 | 2 | 1 | +0.40 | Strings/Solo Contrabass/Pizz |
| `strings.violin_solo.sus` | sustain | G3-C7 | 2 | 1 | 1 | -0.20 | Strings/Solo Violin/Arco Vib |
| `strings.violin_solo.spic` | short | G3-C7 | 2 | 2 | 1 | -0.20 | Strings/Solo Violin/spic |
| `strings.violin_solo.trem` | sustain | G3-C7 | 2 | 1 | 1 | -0.20 | Strings/Solo Violin/Trem |
| `strings.violin_solo.pizz` | short | G3-C7 | 2 | 2 | 1 | -0.20 | Strings/Solo Violin/Pizz |
| `strings.harp` | short | E1-F7 | 4 | 1 | 1 | -0.30 | Chordophones/Composite Chordophones/Concert Harp |
| `brass.horns.sus` | sustain | A1-F5 | 4 | 1 | 4 | -0.30 | Brass/F Horn/sus |
| `brass.horns.stac` | short | A1-F5 | 3 | 2 | 4 | -0.30 | Brass/F Horn/stac |
| `brass.horns.mute` | sustain | A#2-F5 | 3 | 1 | 4 | -0.30 | Brass/F Horn/mute |
| `brass.horn.sus` | sustain | A1-F5 | 4 | 1 | 1 | -0.30 | Brass/F Horn/sus |
| `brass.horn.stac` | short | A1-F5 | 3 | 2 | 1 | -0.30 | Brass/F Horn/stac |
| `brass.horn.mute` | sustain | A#2-F5 | 3 | 1 | 1 | -0.30 | Brass/F Horn/mute |
| `brass.trombones.sus` | sustain | A#1-F4 | 3 | 1 | 3 | +0.25 | Brass/Tenor Trombone/sus |
| `brass.trombones.stac` | short | A#1-F4 | 4 | 2 | 3 | +0.25 | Brass/Tenor Trombone/stac |
| `brass.trombone.sus` | sustain | A#1-F4 | 3 | 1 | 1 | +0.25 | Brass/Tenor Trombone/sus |
| `brass.trombone.stac` | short | A#1-F4 | 4 | 2 | 1 | +0.25 | Brass/Tenor Trombone/stac |
| `brass.trombone.vib` | sustain | F2-D#4 | 1 | 2 | 1 | +0.25 | Brass/Tenor Trombone/vib |
| `brass.trombone_old.sus` | sustain | F2-G4 | 5 | 3 | 1 | +0.35 | Brass/OldTrombone/Sustain |
| `brass.trombone_old.short` | short | F2-F4 | 3 | 7 | 1 | +0.35 | Brass/OldTrombone/Short |
| `brass.trombone_old.buzz` | sustain | F2-D4 | 2 | 2 | 1 | +0.35 | Brass/OldTrombone/Buzz |
| `brass.trombone_old.fall` | short | G2-B3 | 1 | 3 | 1 | +0.35 | Brass/OldTrombone/Fall |
| `brass.trumpets.sus` | sustain | F3-C6 | 2 | 1 | 3 | +0.10 | Brass/Trumpet/sus |
| `brass.trumpets.stac` | short | F3-C6 | 3 | 2 | 3 | +0.10 | Brass/Trumpet/stac |
| `brass.trumpet.sus` | sustain | F3-C6 | 2 | 1 | 1 | +0.10 | Brass/Trumpet/sus |
| `brass.trumpet.susvib` | sustain | F3-C6 | 2 | 1 | 1 | +0.10 | Brass/Trumpet/susvib |
| `brass.trumpet.stac` | short | F3-C6 | 3 | 2 | 1 | +0.10 | Brass/Trumpet/stac |
| `brass.trumpet.mute` | sustain | A#3-A5 | 2 | 1 | 1 | +0.10 | Brass/Trumpet/straightM-sus |
| `brass.trumpet.harmon` | sustain | A#3-A5 | 2 | 1 | 1 | +0.10 | Brass/Trumpet/harmonM-sus |
| `brass.tuba.sus` | sustain | F1-D4 | 3 | 1 | 1 | +0.35 | Brass/Tuba/sus |
| `brass.tuba.stac` | short | A#1-D4 | 2 | 4 | 1 | +0.35 | Brass/Tuba/stac |
| `woods.flute.sus` | sustain | C4-C7 | 3 | 1 | 1 | -0.10 | Woodwinds/Flute/susNV |
| `woods.flute.vib` | sustain | C4-C7 | 1 | 2 | 1 | -0.10 | Woodwinds/Flute/susvib |
| `woods.flute.stac` | short | A4-C7 | 4 | 2 | 1 | -0.10 | Woodwinds/Flute/stac |
| `woods.piccolo.sus` | sustain | G5-G7 | 1 | 1 | 1 | -0.15 | Woodwinds/Piccolo/Sus |
| `woods.piccolo.stac` | short | A#5-A#7 | 1 | 1 | 1 | -0.15 | Woodwinds/Piccolo/Stac |
| `woods.oboe.sus` | sustain | A#3-F6 | 2 | 1 | 1 | +0.08 | Woodwinds/Oboe/Sus |
| `woods.oboe.vib` | sustain | A#3-F6 | 2 | 1 | 1 | +0.08 | Woodwinds/Oboe/Vib |
| `woods.oboe.stac` | short | A#3-F6 | 3 | 2 | 1 | +0.08 | Woodwinds/Oboe/Stacc |
| `woods.clarinet.sus` | sustain | D3-F#6 | 3 | 1 | 1 | -0.05 | Woodwinds/Clarinet/susLong |
| `woods.clarinet.stac` | short | D3-F6 | 3 | 2 | 1 | -0.05 | Woodwinds/Clarinet/stac |
| `woods.bassoon.sus` | sustain | A#1-D#5 | 2 | 1 | 1 | +0.15 | Woodwinds/Bassoon/sus |
| `woods.bassoon.vib` | sustain | G2-C5 | 2 | 2 | 1 | +0.15 | Woodwinds/Bassoon/vib |
| `woods.bassoon.stac` | short | A#1-C5 | 2 | 2 | 1 | +0.15 | Woodwinds/Bassoon/stac |
| `keys.piano` | short | A#0-G#7 | 3 | 1 | 1 | +0.00 | Chordophones/Zithers/Grand Piano, Steinway B/Sus |
| `keys.piano.kawai` | short | A#0-C8 | 4 | 1 | 1 | +0.00 | Chordophones/Zithers/Grand Piano, Kawai/Sustains |
| `keys.piano.upright` | short | C1-G7 | 3 | 2 | 1 | +0.00 | Keys/Upright Nr1 |
| `keys.organ` | sustain | C1-C6 | 1 | 1 | 1 | +0.00 | Aerophones/Edge-blown Aerophones/Pipe Organ/Loud |
| `keys.organ.pedal` | sustain | C2-F#4 | 1 | 1 | 1 | +0.00 | Aerophones/Edge-blown Aerophones/Pipe Organ/Loud Pedal |
| `perc.timpani` | perc | D#2-A3 | 3 | 3 | 1 | +0.00 | Membranophones/Struck Membranophones/Timpani 2/Hit::Timpani_Hit |
| `perc.timpani.vsco` | perc | F#2-F#3 | 3 | 2 | 1 | +0.00 | Membranophones/Struck Membranophones/Timpani 1/Hit::Timpani_Hit |
| `perc.timpani.roll` | sustain | F#2-G3 | 4 | 1 | 1 | +0.00 | Membranophones/Struck Membranophones/Timpani 1/Roll::Timpani_Roll |
| `perc.tubular_bells` | perc | C4-F5 | 2 | 1 | 1 | +0.25 | Idiophones/Struck Idiophones/Tubular Bells 2 |
| `perc.chimes` | perc | C4-E5 | 5 | 1 | 1 | +0.25 | Idiophones/Struck Idiophones/Tubular Bells 1 |
| `perc.glock` | perc | G5-C8 | 3 | 1 | 1 | -0.20 | Idiophones/Struck Idiophones/Glockenspiel |
| `perc.xylo` | perc | G4-C8 | 2 | 1 | 1 | -0.15 | Idiophones/Struck Idiophones/Xylophone/Hard Mallets |
| `perc.marimba` | perc | F2-C7 | 3 | 1 | 1 | +0.10 | Idiophones/Struck Idiophones/Marimba |
| `perc.vibes` | perc | F3-E6 | 2 | 1 | 1 | +0.10 | Idiophones/Struck Idiophones/Vibraphone/Hard Mallets |
| `perc.vibes.bowed` | perc | A3-E6 | 1 | 1 | 1 | +0.10 | Idiophones/Struck Idiophones/Vibraphone/Bowed |
| `perc.bass_drum` | perc | unpitched (key 60) | 7 | 2 | 1 | +0.00 | Percussion::BDrumNewhit |
| `perc.bass_drum.vcsl` | perc | unpitched (key 60) | 4 | 2 | 1 | +0.00 | Membranophones/Struck Membranophones/Bass Drum 1::BDrumNew_hit |
| `perc.bass_drum.b` | perc | unpitched (key 60) | 5 | 2 | 1 | +0.00 | Membranophones/Struck Membranophones/Bass Drum 2::bassdrum_hit |
| `perc.bass_drum.legacy` | perc | unpitched (key 60) | 7 | 3 | 1 | +0.00 | Membranophones/Struck Membranophones/Bass Drum 3 - Legacy::bdrum |
| `perc.bass_drum.muted` | perc | unpitched (key 60) | 6 | 3 | 1 | +0.00 | Membranophones/Struck Membranophones/Bass Drum 3 - Legacy::bdrum_muted |
| `perc.bass_drum.roll` | sustain | unpitched (key 60) | 4 | 1 | 1 | +0.00 | Membranophones/Struck Membranophones/Bass Drum 2::bassdrum_roll |
| `perc.giant_drum` | perc | unpitched (key 60) | 4 | 2 | 1 | +0.00 | VSCO 1 Percussion/drums/other/ethnic/giant/mallet::EthnicLargeMallet_hit |
| `perc.giant_drum.hand` | perc | unpitched (key 60) | 6 | 4 | 1 | +0.00 | VSCO 1 Percussion/drums/other/ethnic/giant/hand::EthnicLargeHand_hit |
| `perc.giant_drum.sticks` | perc | unpitched (key 60) | 7 | 2 | 1 | +0.00 | VSCO 1 Percussion/drums/other/ethnic/giant/sticks::EthnicLargeSticks_hit |
| `perc.giant_drum.rim` | perc | unpitched (key 60) | 1 | 3 | 1 | +0.00 | VSCO 1 Percussion/drums/other/ethnic/giant::EthnicLargeStick_rimshot |
| `perc.toms.low` | perc | unpitched (key 60) | 3 | 2 | 1 | +0.20 | Membranophones/Struck Membranophones/Tom 2/Mallet::TomL_HitM |
| `perc.toms.high` | perc | unpitched (key 60) | 3 | 2 | 1 | -0.20 | Membranophones/Struck Membranophones/Tom 1/Mallet::TomH_HitM |
| `perc.toms.low.stick` | perc | unpitched (key 60) | 3 | 2 | 1 | +0.20 | Membranophones/Struck Membranophones/Tom 2/Stick::TomL_HitS |
| `perc.toms.high.stick` | perc | unpitched (key 60) | 3 | 2 | 1 | -0.20 | Membranophones/Struck Membranophones/Tom 1/Stick::TomH_HitS |
| `perc.toms.low.roll` | sustain | unpitched (key 60) | 2 | 1 | 1 | +0.20 | Membranophones/Struck Membranophones/Tom 2/Mallet::TomL_RollM |
| `perc.tenor_drum.low` | perc | unpitched (key 60) | 7 | 4 | 1 | +0.25 | Membranophones/Struck Membranophones/Legacy Toms/tenor_lower::tenor |
| `perc.tenor_drum.high` | perc | unpitched (key 60) | 7 | 6 | 1 | -0.25 | Membranophones/Struck Membranophones/Legacy Toms/tenor_higher::tenorH |
| `perc.frame_drum` | perc | unpitched (key 60) | 2 | 2 | 1 | -0.30 | Membranophones/Struck Membranophones/Frame Drum::HDrumL_Hit |
| `perc.frame_drum.small` | perc | unpitched (key 60) | 2 | 2 | 1 | +0.30 | Membranophones/Struck Membranophones/Frame Drum::HDrumS_Hit |
| `perc.ethnic_drum.low` | perc | unpitched (key 60) | 3 | 4 | 1 | +0.30 | VSCO 1 Percussion/drums/other/ethnic/congo/open::ethnicLowOpen_hit |
| `perc.snare` | perc | unpitched (key 60) | 5 | 2 | 1 | -0.10 | Membranophones/Struck Membranophones/Snare Drum, Modern 1::Snare2_HitSN |
| `perc.snare.nosnare` | perc | unpitched (key 60) | 4 | 2 | 1 | -0.10 | Membranophones/Struck Membranophones/Snare Drum, Modern 1::Snare2_HitNS |
| `perc.snare.rimshot` | perc | unpitched (key 60) | 2 | 2 | 1 | -0.10 | Membranophones/Struck Membranophones/Snare Drum, Modern 3::Snare4_rimshot |
| `perc.snare.roll` | sustain | unpitched (key 60) | 3 | 1 | 1 | -0.10 | Membranophones/Struck Membranophones/Snare Drum, Modern 1::Snare2_rollSN |
| `perc.taiko_rim` | perc | unpitched (key 60) | 1 | 3 | 1 | +0.00 | VSCO 1 Percussion/drums/other/ethnic/giant::EthnicLargeStick_rimshot |
| `perc.cymbal.crash` | perc | unpitched (key 60) | 4 | 2 | 1 | +0.20 | Idiophones/Struck Idiophones/Clash Cymbals 1::cymbal_crash1 |
| `perc.cymbal.crash2` | perc | unpitched (key 60) | 3 | 2 | 1 | +0.20 | Idiophones/Struck Idiophones/Clash Cymbals 2::cymbal_crash2 |
| `perc.cymbal.crash3` | perc | unpitched (key 60) | 4 | 2 | 1 | +0.20 | Percussion::cymbal-crash1 |
| `perc.cymbal.sus` | perc | unpitched (key 60) | 4 | 1 | 1 | +0.20 | Idiophones/Struck Idiophones/Suspended Cymbal 1::susCymb1_hit |
| `perc.cymbal.sus2` | perc | unpitched (key 60) | 5 | 1 | 1 | +0.20 | Idiophones/Struck Idiophones/Suspended Cymbal 2::susCymb2_hit |
| `perc.cymbal.roll` | sustain | unpitched (key 60) | 3 | 1 | 1 | +0.20 | Idiophones/Struck Idiophones/Suspended Cymbal 1::susCymb1_roll_nloop |
| `perc.cymbal.swell` | swell | unpitched (key 60) | 1 | 1 | 1 | +0.20 | Idiophones/Struck Idiophones/Suspended Cymbal 1::susCymb1_cresc_1.5s<br>Idiophones/Struck Idiophones/Suspended Cymbal 1::susCymb1_cresc_2s<br>Idiophones/Struck Idiophones/Suspended Cymbal 1::susCymb1_cresc_4s<br>(+7 more) |
| `perc.bass_drum.swell` | swell | unpitched (key 60) | 1 | 1 | 1 | +0.00 | Membranophones/Struck Membranophones/Bass Drum 2::bassdrum_cresc<br>Membranophones/Struck Membranophones/Bass Drum 2::bassdrum_cresc_short |
| `perc.gong` | perc | unpitched (key 60) | 10 | 3 | 1 | -0.30 | VSCO 1 Percussion/varMetal/Gong::gong_hit |
| `perc.gong.hard` | perc | unpitched (key 60) | 3 | 1 | 1 | -0.30 | VSCO 1 Percussion/varMetal/Gong::gong_hit_hard |
| `perc.gong.b` | perc | unpitched (key 60) | 4 | 1 | 1 | -0.30 | Percussion::gongHit |
| `perc.gong.c` | perc | unpitched (key 60) | 4 | 1 | 1 | -0.30 | Idiophones/Struck Idiophones/Gong 1::gong |
| `perc.gong.roll` | sustain | unpitched (key 60) | 2 | 1 | 1 | -0.30 | VSCO 1 Percussion/varMetal/Gong::gong_roll_long |
| `perc.gong.scrape` | perc | unpitched (key 60) | 1 | 3 | 1 | -0.30 | VSCO 1 Percussion/varMetal/Gong::gong_scrape |
| `perc.anvil` | perc | unpitched (key 60) | 3 | 1 | 1 | +0.25 | Percussion::Anvil_Hit1 |
| `perc.brake_drum` | perc | unpitched (key 60) | 3 | 1 | 1 | +0.25 | Percussion::BrakeDrum1_Hammer |
| `perc.triangle` | perc | unpitched (key 60) | 2 | 2 | 1 | +0.30 | Percussion::Triangle6-Hit |
| `fx.reverse_cymbal` | reverse | unpitched (key 60) | 4 | 2 | 1 | +0.00 | Idiophones/Struck Idiophones/Clash Cymbals 1::cymbal_crash1 |
| `fx.reverse_gong` | reverse | unpitched (key 60) | 10 | 3 | 1 | +0.00 | VSCO 1 Percussion/varMetal/Gong::gong_hit |
| `fx.reverse_sus_cymbal` | reverse | unpitched (key 60) | 4 | 1 | 1 | +0.00 | Idiophones/Struck Idiophones/Suspended Cymbal 1::susCymb1_hit |

## Pitched groups

Columns: range (sounding), distinct sampled notes, velocity layers (labels), max round robins, median length, octave offset applied to the file names and how it was decided.

### VCSL / Aerophones

| Group | Range | Notes | Layers | RR | Len (s) | Octave |
|---|---|---|---|---|---|---|
| Aerophones/Edge-blown Aerophones/Baroque Alto Recorder/Staccato | F#4-E6 | 12 | 1 (single) | 1 | 0.43 | +12 (pitch detector, 12/12 detected samples agree) |
| Aerophones/Edge-blown Aerophones/Baroque Alto Recorder/SusVib | F4-E6 | 12 | 1 (single) | 1 | 11.13 | +12 (pitch detector, 12/12 detected samples agree) |
| Aerophones/Edge-blown Aerophones/Baroque Alto Recorder/Sustain | F4-E6 | 12 | 1 (single) | 1 | 12.49 | +12 (pitch detector, 12/12 detected samples agree) |
| Aerophones/Edge-blown Aerophones/Baroque Bass Recorder/Staccato | F3-F5 | 15 | 1 (single) | 1 | 0.45 | +12 (pitch detector, 13/15 detected samples agree) |
| Aerophones/Edge-blown Aerophones/Baroque Bass Recorder/SusVib | F3-E5 | 14 | 1 (single) | 1 | 4.42 | +12 (pitch detector, 14/14 detected samples agree) |
| Aerophones/Edge-blown Aerophones/Baroque Bass Recorder/Sustain | F#3-E5 | 12 | 1 (single) | 1 | 5.98 | +12 (pitch detector, 12/12 detected samples agree) |
| Aerophones/Edge-blown Aerophones/Baroque Soprano Recorder/Staccato | C5-A#6 | 12 | 1 (single) | 1 | 0.47 | +12 (pitch detector, 12/12 detected samples agree) |
| Aerophones/Edge-blown Aerophones/Baroque Soprano Recorder/Sustain | C5-C7 | 13 | 1 (single) | 1 | 11.74 | +12 (pitch detector, 13/13 detected samples agree) |
| Aerophones/Edge-blown Aerophones/Baroque Tenor Recorder/Staccato | C4-B5 | 12 | 1 (single) | 1 | 0.51 | +12 (pitch detector, 12/12 detected samples agree) |
| Aerophones/Edge-blown Aerophones/Baroque Tenor Recorder/SusVib | C4-B5 | 14 | 1 (single) | 1 | 5.5 | +12 (pitch detector, 14/14 detected samples agree) |
| Aerophones/Edge-blown Aerophones/Baroque Tenor Recorder/Sustain | C4-C6 | 13 | 1 (single) | 1 | 8.1 | +12 (pitch detector, 13/13 detected samples agree) |
| Aerophones/Edge-blown Aerophones/Ocarina, Small/Staccato | A5-C7 | 13 | 1 (single) | 1 | 0.28 | +12 (pitch detector, 13/13 detected samples agree) |
| Aerophones/Edge-blown Aerophones/Ocarina, Small/Sustain | A#5-B6 | 10 | 1 (single) | 1 | 17.65 | +12 (pitch detector, 10/10 detected samples agree) |
| Aerophones/Edge-blown Aerophones/Ocarina, Typical/Releases/Sus | A2-C#4 | 11 | 1 (single) | 1 | 0.86 | -12 (pitch detector, 3/3 detected samples agree) |
| Aerophones/Edge-blown Aerophones/Ocarina, Typical/Releases/SusVib | A2-C4 | 10 | 1 (single) | 1 | 0.7 | -12 (pitch detector, 3/3 detected samples agree) |
| Aerophones/Edge-blown Aerophones/Ocarina, Typical/Sustains/Sus | A3-C#5 | 11 | 1 (single) | 1 | 6.54 | +0 (pitch detector, 8/11 detected samples agree) |
| Aerophones/Edge-blown Aerophones/Ocarina, Typical/Sustains/SusVib | A3-C5 | 10 | 1 (single) | 1 | 8.1 | +0 (pitch detector, 7/10 detected samples agree) |
| Aerophones/Edge-blown Aerophones/Pipe Organ/Loud | C1-C6 | 21 | 1 (single) | 1 | 12.29 | +0 (pitch detector, 21/21 detected samples agree) |
| Aerophones/Edge-blown Aerophones/Pipe Organ/Loud Pedal | C2-F#4 | 11 | 1 (single) | 1 | 12.71 | +12 (sibling folders (detector unsure), 0/11 detected samples agree) |
| Aerophones/Edge-blown Aerophones/Pipe Organ/Quiet | C2-C7 | 21 | 1 (single) | 1 | 12.14 | +12 (pitch detector, 21/21 detected samples agree) |
| Aerophones/Edge-blown Aerophones/Pipe Organ/Quiet Pedal | C2-F#4 | 11 | 1 (single) | 1 | 11.99 | +12 (pitch detector, 11/11 detected samples agree) |
| Aerophones/Edge-blown Aerophones/Renaissance Organ/4' | C0-E4 | 27 | 1 (single) | 1 | 6.51 | -12 (pitch detector, 3/5 detected samples agree) |
| Aerophones/Edge-blown Aerophones/Renaissance Organ/8' | C2-E6 | 27 | 1 (single) | 1 | 8.35 | +12 (pitch detector, 15/24 detected samples agree) |
| Aerophones/Edge-blown Aerophones/Renaissance Organ/Full | C2-E6 | 27 | 1 (single) | 1 | 5.83 | +12 (pitch detector, 24/24 detected samples agree) |
| Aerophones/Free Aerophones/Harmonica-Hohner-Special20-C/Releases/Normal | C4-C7 | 9 | 1 (single) | 1 | 0.38 | +12 (pitch detector, 7/7 detected samples agree) |
| Aerophones/Free Aerophones/Harmonica-Hohner-Special20-C/Releases/Soft | C4-C7 | 10 | 1 (single) | 1 | 0.35 | +12 (pitch detector, 8/9 detected samples agree) |
| Aerophones/Free Aerophones/Harmonica-Hohner-Special20-C/Releases/Vib | C4-C7 | 10 | 1 (single) | 1 | 0.38 | +12 (pitch detector, 10/10 detected samples agree) |
| Aerophones/Free Aerophones/Harmonica-Hohner-Special20-C/Sustains/Normal | C4-C7 | 9 | 1 (single) | 1 | 4.7 | +12 (pitch detector, 9/9 detected samples agree) |
| Aerophones/Free Aerophones/Harmonica-Hohner-Special20-C/Sustains/Soft | C4-C7 | 10 | 1 (single) | 1 | 5.58 | +12 (pitch detector, 10/10 detected samples agree) |
| Aerophones/Free Aerophones/Harmonica-Hohner-Special20-C/Sustains/Vib | C4-C7 | 10 | 1 (single) | 1 | 6.11 | +12 (pitch detector, 10/10 detected samples agree) |
| Aerophones/Free Aerophones/Harmonica-Hohner-Special20-F/Releases/Accented | F4-F7 | 10 | 1 (single) | 1 | 0.48 | +12 (pitch detector, 10/10 detected samples agree) |
| Aerophones/Free Aerophones/Harmonica-Hohner-Special20-F/Releases/HandVib | F4-F7 | 10 | 1 (single) | 1 | 0.38 | +12 (pitch detector, 7/8 detected samples agree) |
| Aerophones/Free Aerophones/Harmonica-Hohner-Special20-F/Releases/Normal | F4-C7 | 8 | 1 (single) | 1 | 0.6 | +12 (pitch detector, 8/8 detected samples agree) |
| Aerophones/Free Aerophones/Harmonica-Hohner-Special20-F/Releases/Vib | F4-F7 | 9 | 1 (single) | 1 | 0.46 | +12 (pitch detector, 9/9 detected samples agree) |
| Aerophones/Free Aerophones/Harmonica-Hohner-Special20-F/Sustains/Accented | F4-F7 | 10 | 1 (single) | 1 | 5.69 | +12 (pitch detector, 10/10 detected samples agree) |
| Aerophones/Free Aerophones/Harmonica-Hohner-Special20-F/Sustains/HandVib | F4-F7 | 10 | 1 (single) | 1 | 5.6 | +12 (pitch detector, 10/10 detected samples agree) |
| Aerophones/Free Aerophones/Harmonica-Hohner-Special20-F/Sustains/Normal | F4-C7 | 8 | 1 (single) | 1 | 6.27 | +12 (pitch detector, 8/8 detected samples agree) |
| Aerophones/Free Aerophones/Harmonica-Hohner-Special20-F/Sustains/Stac | F4-F7 | 10 | 1 (single) | 2 | 0.65 | +12 (pitch detector, 20/20 detected samples agree) |
| Aerophones/Free Aerophones/Harmonica-Hohner-Special20-F/Sustains/Vib | F4-F7 | 9 | 1 (single) | 1 | 6.44 | +12 (pitch detector, 9/9 detected samples agree) |
| Aerophones/Free Aerophones/Harmonica-Hohner-Super64/Releases/Accented | C3-C7 | 13 | 1 (single) | 1 | 0.41 | +12 (pitch detector, 13/13 detected samples agree) |
| Aerophones/Free Aerophones/Harmonica-Hohner-Super64/Releases/Normal | C3-C7 | 13 | 1 (single) | 1 | 0.5 | +12 (pitch detector, 13/13 detected samples agree) |
| Aerophones/Free Aerophones/Harmonica-Hohner-Super64/Releases/Vib | C3-C7 | 13 | 1 (single) | 1 | 0.41 | +12 (pitch detector, 10/11 detected samples agree) |
| Aerophones/Free Aerophones/Harmonica-Hohner-Super64/Sustains/Accented | C3-C7 | 13 | 1 (single) | 1 | 4.83 | +12 (pitch detector, 13/13 detected samples agree) |
| Aerophones/Free Aerophones/Harmonica-Hohner-Super64/Sustains/Normal | C3-C7 | 13 | 1 (single) | 1 | 4.87 | +12 (pitch detector, 13/13 detected samples agree) |
| Aerophones/Free Aerophones/Harmonica-Hohner-Super64/Sustains/Vib | C3-C7 | 13 | 1 (single) | 1 | 5.97 | +12 (pitch detector, 13/13 detected samples agree) |
| Aerophones/Reed Aerophones/Saxello/Non-Vibrato | A#3-E6 | 8 | 2 (vl2,vl3) | 1 | 4.98 | +12 (pitch detector, 16/16 detected samples agree) |
| Aerophones/Reed Aerophones/Saxello/Staccato | A#3-D6 | 8 | 2 (vl1,vl2) | 1 | 0.51 | +12 (pitch detector, 15/15 detected samples agree) |
| Aerophones/Reed Aerophones/Saxello/Vibrato | A#3-D#6 | 8 | 1 (vl2) | 1 | 6.27 | +12 (pitch detector, 8/8 detected samples agree) |
| Aerophones/Reed Aerophones/Tenor Saxophone/Non-Vibrato | G#2-E6 | 23 | 2 (vl2,vl3) | 1 | 7.43 | +12 (pitch detector, 46/46 detected samples agree) |
| Aerophones/Reed Aerophones/Tenor Saxophone/Staccato | G#2-E6 | 23 | 2 (vl1,vl2) | 1 | 0.55 | +12 (pitch detector, 40/40 detected samples agree) |
| Aerophones/Reed Aerophones/Tenor Saxophone/Vibrato | A#2-D6 | 19 | 1 (single) | 1 | 6.16 | +12 (pitch detector, 19/19 detected samples agree) |

### VCSL / Chordophones

| Group | Range | Notes | Layers | RR | Len (s) | Octave |
|---|---|---|---|---|---|---|
| Chordophones/Composite Chordophones/Concert Harp | E1-F7 | 23 | 4 (p,mp,mf,f) | 1 | 10.62 | +0 (pitch detector, 38/43 detected samples agree) |
| Chordophones/Composite Chordophones/Folk Harp | C2-G#6 | 29 | 2 (v2,v3) | 1 | 6.87 | +12 (pitch detector, 57/57 detected samples agree) |
| Chordophones/Composite Chordophones/Strumstick/Finger | D3-A5 | 19 | 3 (vl1,vl2,vl3) | 1 | 6.02 | +12 (pitch detector, 56/56 detected samples agree) |
| Chordophones/Zithers/Dan Tranh/Normal | B2-B5 | 16 | 3 (mf,f,ff) | 1 | 5.99 | +12 (pitch detector, 46/48 detected samples agree) |
| Chordophones/Zithers/Dan Tranh/Tremolo | B2-B5 | 16 | 1 (single) | 1 | 12.49 | +12 (pitch detector, 16/16 detected samples agree) |
| Chordophones/Zithers/Dan Tranh/Vibrato | B2-B5 | 16 | 2 (mf,ff) | 1 | 4.41 | +12 (pitch detector, 29/31 detected samples agree) |
| Chordophones/Zithers/Grand Piano, Kawai - Legacy/Releases | C1-C6 | 15 | 4 (v1,v2,v3,v4) | 1 | 0.83 | +12 (pitch detector, 22/34 detected samples agree) |
| Chordophones/Zithers/Grand Piano, Kawai - Legacy/Sustains | C1-C8 | 19 | 4 (v1,v2,v3,v4) | 1 | 13.15 | +12 (pitch detector, 69/71 detected samples agree) |
| Chordophones/Zithers/Grand Piano, Kawai/Releases | A#0-D#6 | 34 | 3 (v2,v3,v4) | 1 | 1.0 | +12 (sibling folders (detector unsure), 20/44 detected samples agree) |
| Chordophones/Zithers/Grand Piano, Kawai/Sustains | A#0-C8 | 38 | 4 (v1,v2,v3,v4) | 1 | 17.53 | +12 (pitch detector, 110/123 detected samples agree) |
| Chordophones/Zithers/Grand Piano, Steinway B/NoSus | A#0-G#7 | 42 | 3 (vl2,vl3,vl4) | 1 | 16.0 | +0 (pitch detector, 105/119 detected samples agree) |
| Chordophones/Zithers/Grand Piano, Steinway B/Rel | A#0-D6 | 33 | 3 (vl2,vl3,vl4) | 1 | 1.17 | +0 (sibling folders (detector unsure), 15/35 detected samples agree) |
| Chordophones/Zithers/Grand Piano, Steinway B/Sus | A#0-G#7 | 42 | 3 (vl2,vl3,vl4) | 1 | 25.77 | +0 (pitch detector, 76/84 detected samples agree) |
| Chordophones/Zithers/Harpsichord, English/Releases/Lute | A#0-E5 | 26 | 1 (single) | 1 | 0.68 | +0 (pitch detector (low agreement) + range sanity, 3/11 detected samples agree) |
| Chordophones/Zithers/Harpsichord, English/Releases/Normal | A#1-E6 | 28 | 1 (single) | 1 | 0.98 | +12 (pitch detector (low agreement), 7/16 detected samples agree) |
| Chordophones/Zithers/Harpsichord, English/Sustains/Lute | A#1-E6 | 27 | 1 (single) | 2 | 3.68 | +12 (pitch detector, 26/26 detected samples agree) |
| Chordophones/Zithers/Harpsichord, English/Sustains/Normal | A#1-E6 | 28 | 1 (single) | 1 | 6.43 | +12 (pitch detector, 28/28 detected samples agree) |
| Chordophones/Zithers/Harpsichord, Flemish/Releases/High | F#2-C7 | 26 | 1 (single) | 1 | 0.88 | +12 (pitch detector (low agreement), 5/9 detected samples agree) |
| Chordophones/Zithers/Harpsichord, Flemish/Releases/Low | F#1-C6 | 28 | 1 (single) | 1 | 1.0 | +12 (pitch detector (low agreement), 10/19 detected samples agree) |
| Chordophones/Zithers/Harpsichord, Flemish/Sustains/High | F#2-C7 | 26 | 1 (single) | 1 | 5.84 | +12 (pitch detector, 26/26 detected samples agree) |
| Chordophones/Zithers/Harpsichord, Flemish/Sustains/Low | F#1-C6 | 28 | 1 (single) | 1 | 8.4 | +12 (pitch detector, 28/28 detected samples agree) |
| Chordophones/Zithers/Harpsichord, French/Releases | D1-C6 | 28 | 1 (single) | 1 | 0.91 | +12 (sibling folders (detector unsure), 7/15 detected samples agree) |
| Chordophones/Zithers/Harpsichord, French/Sustains | D1-C6 | 28 | 1 (single) | 2 | 10.39 | +12 (pitch detector, 30/30 detected samples agree) |
| Chordophones/Zithers/Harpsichord, Italian/Releases/stop1 | F#1-B5 | 31 | 1 (single) | 1 | 2.19 | +12 (pitch detector, 27/29 detected samples agree) |
| Chordophones/Zithers/Harpsichord, Italian/Sustains/stop1 | F#1-B5 | 32 | 1 (single) | 1 | 11.42 | +12 (pitch detector, 32/32 detected samples agree) |
| Chordophones/Zithers/Harpsichord, Unk/Releases | F1-F6 | 61 | 1 (single) | 1 | 0.83 | +12 (sibling folders (detector unsure), 4/28 detected samples agree) |
| Chordophones/Zithers/Harpsichord, Unk/Sustains | F1-F6 | 61 | 1 (single) | 1 | 8.26 | +12 (pitch detector, 61/61 detected samples agree) |
| Chordophones/Zithers/Psaltery, Bowed and Plucked/LongBow | A#4-F#6 | 11 | 1 (single) | 1 | 6.53 | +12 (pitch detector, 11/11 detected samples agree) |
| Chordophones/Zithers/Psaltery, Bowed and Plucked/Pluck | A#4-F#6 | 11 | 1 (single) | 1 | 4.61 | +12 (pitch detector, 11/11 detected samples agree) |
| Chordophones/Zithers/Psaltery, Bowed and Plucked/Spiccato | A#4-F#6 | 11 | 1 (single) | 1 | 3.74 | +12 (pitch detector, 11/11 detected samples agree) |
| Chordophones/Zithers/Upright Piano, Knight/Releases | A0-C8 | 45 | 1 (single) | 1 | 3.71 | +12 (sibling folders (detector unsure), 4/16 detected samples agree) |
| Chordophones/Zithers/Upright Piano, Knight/Sustains | A0-C8 | 45 | 2 (vl1,vl2) | 1 | 16.99 | +12 (pitch detector, 61/65 detected samples agree) |
| Chordophones/Zithers/Upright Piano, Yamaha/Releases | C1-C7 | 13 | 3 (vl1,vl2,vl3) | 3 | 0.35 | +12 (sibling folders (detector unsure), 5/24 detected samples agree) |
| Chordophones/Zithers/Upright Piano, Yamaha/Sustains | C1-C7 | 13 | 3 (vl1,vl2,vl3) | 3 | 13.07 | +12 (pitch detector, 53/62 detected samples agree) |

### VCSL / Electrophones

| Group | Range | Notes | Layers | RR | Len (s) | Octave |
|---|---|---|---|---|---|---|
| Electrophones/TX81Z/Clavisynth | C1-C7 | 19 | 3 (vl1,vl2,vl3) | 1 | 2.98 | +12 (pitch detector, 24/24 detected samples agree) |
| Electrophones/TX81Z/FM Piano | C1-C8 | 22 | 3 (vl1,vl2,vl3) | 1 | 7.49 | +12 (pitch detector + range sanity, 3/66 detected samples agree) |
| Electrophones/TX81Z/Piano 1 | C1-C8 | 22 | 3 (vl1,vl2,vl3) | 1 | 4.07 | +12 (pitch detector, 65/65 detected samples agree) |

### VCSL / Idiophones

| Group | Range | Notes | Layers | RR | Len (s) | Octave |
|---|---|---|---|---|---|---|
| Idiophones/Friction Idiophones/Wine Glasses/Releases/Fast | D#5-D6 | 4 | 1 (single) | 1 | 2.13 | +12 (pitch detector, 2/2 detected samples agree) |
| Idiophones/Friction Idiophones/Wine Glasses/Releases/Slow | D#4-D5 | 4 | 1 (single) | 1 | 1.4 | +0 (pitch detector, 2/2 detected samples agree) |
| Idiophones/Friction Idiophones/Wine Glasses/Sustains/Fast | D#5-D6 | 4 | 1 (single) | 1 | 20.38 | +12 (pitch detector, 2/3 detected samples agree) |
| Idiophones/Friction Idiophones/Wine Glasses/Sustains/Slow | D#5-D6 | 4 | 1 (single) | 1 | 16.6 | +12 (pitch detector, 2/2 detected samples agree) |
| Idiophones/Plucked Idiophones/Kalimba, Kenya | B1-B3 | 11 | 1 (vl3) | 2 | 4.81 | -12 (pitch detector, 5/8 detected samples agree) |
| Idiophones/Plucked Idiophones/Kalimba, Tanzania | G1-C#6 | 25 | 1 (single) | 2 | 2.34 | +0 (pitch detector + range sanity, 0/6 detected samples agree) |
| Idiophones/Plucked Idiophones/Mbira Mavembe (Gandanga), Zimbabwe, Low G | A#2-A5 | 22 | 1 (vl2) | 2 | 5.43 | +12 (pitch detector, 10/16 detected samples agree) |
| Idiophones/Plucked Idiophones/Mbira dzaVadzimu Nyamaropa, Zimbabwe, Low B | A#2-C#6 | 22 | 1 (single) | 2 | 3.55 | +12 (pitch detector, 20/22 detected samples agree) |
| Idiophones/Plucked Idiophones/Nyunga Nyunga, Mozambique, Low F | F1-F3 | 14 | 1 (vl3) | 2 | 3.57 | -12 (sibling folders (detector unsure), 4/13 detected samples agree) |
| Idiophones/Struck Idiophones/Balafon/Hard Mallet | C#3-F5 | 6 | 3 (vl1,vl2,vl3) | 1 | 1.01 | +0 (pitch detector (low agreement), 6/13 detected samples agree) |
| Idiophones/Struck Idiophones/Balafon/Soft Mallet | C#3-F5 | 6 | 3 (vl1,vl2,vl3) | 1 | 0.85 | +0 (pitch detector (low agreement), 5/9 detected samples agree) |
| Idiophones/Struck Idiophones/Balafon/Traditional Mallet | C#3-F5 | 6 | 3 (vl1,vl2,vl3) | 1 | 0.98 | +0 (pitch detector (low agreement), 5/11 detected samples agree) |
| Idiophones/Struck Idiophones/Bell Tree/Individual | C6-A#6 | 6 | 1 (single) | 1 | 4.34 | +12 (pitch detector, 4/5 detected samples agree) |
| Idiophones/Struck Idiophones/Glockenspiel | G5-C8 | 7 | 3 (soft,medium,loud) | 1 | 5.03 | +12 (pitch detector, 18/18 detected samples agree) |
| Idiophones/Struck Idiophones/Hand Chimes | C4-C7 | 19 | 1 (single) | 1 | 8.35 | +12 (pitch detector, 9/14 detected samples agree) |
| Idiophones/Struck Idiophones/Marimba | F2-C7 | 10 | 3 (soft,med,loud) | 1 | 3.57 | +12 (manual override (instrument range), 6/13 detected samples agree) |
| Idiophones/Struck Idiophones/Tubular Bells 1 | C4-E5 | 9 | 5 (pp,p,f,ff,fff) | 1 | 12.71 | +12 (manual override (instrument range), 6/6 detected samples agree) |
| Idiophones/Struck Idiophones/Tubular Bells 2 | C4-F5 | 11 | 2 (v2,v4) | 1 | 18.36 | +0 (pitch detector, 18/18 detected samples agree) |
| Idiophones/Struck Idiophones/Tubular Glockenspiel | G1-A2 | 9 | 3 (quiet,medium,loud) | 1 | 2.58 | +12 (sibling folders (detector unsure), 0/27 detected samples agree) |
| Idiophones/Struck Idiophones/Vibraphone/Bowed | A3-E6 | 6 | 1 (single) | 1 | 15.84 | +12 (pitch detector, 5/6 detected samples agree) |
| Idiophones/Struck Idiophones/Vibraphone/Hard Mallets | F3-E6 | 11 | 2 (v2,v3) | 1 | 11.0 | +12 (pitch detector, 13/21 detected samples agree) |
| Idiophones/Struck Idiophones/Vibraphone/Soft Mallets | F3-E6 | 11 | 1 (soft) | 2 | 10.84 | +12 (manual override (instrument range), 9/13 detected samples agree) |
| Idiophones/Struck Idiophones/Xylophone/Hard Mallets | G4-C8 | 8 | 2 (pp,ff) | 1 | 1.75 | +12 (pitch detector, 15/15 detected samples agree) |
| Idiophones/Struck Idiophones/Xylophone/Medium Mallets | G4-C8 | 8 | 2 (pp,ff) | 1 | 1.74 | +12 (pitch detector, 14/16 detected samples agree) |
| Idiophones/Struck Idiophones/Xylophone/Soft Mallets | G4-C8 | 8 | 2 (pp,ff) | 1 | 2.15 | +12 (sibling folders (detector unsure), 7/13 detected samples agree) |

### VCSL / Membranophones

| Group | Range | Notes | Layers | RR | Len (s) | Octave |
|---|---|---|---|---|---|---|
| Membranophones/Struck Membranophones/Timpani 1/Hit::Timpani_Hit | F#2-F#3 | 5 | 3 (v2,v3,v4) | 2 | 8.58 | detected (timpani principal mode) |
| Membranophones/Struck Membranophones/Timpani 1/Roll::Timpani_Roll | F#2-G3 | 5 | 4 (v2,v3,v4,v5) | 1 | 22.47 | detected (timpani principal mode) |
| Membranophones/Struck Membranophones/Timpani 2/Hit::Timpani_Hit | D#2-A3 | 19 | 3 (v2,v3,v5) | 3 | 4.66 | detected (timpani principal mode) |

### VSCO-2-CE / Brass

| Group | Range | Notes | Layers | RR | Len (s) | Octave |
|---|---|---|---|---|---|---|
| Brass/F Horn/mute | A#2-F5 | 9 | 3 (v1,v2,v3) | 1 | 5.47 | +12 (pitch detector, 14/17 detected samples agree) |
| Brass/F Horn/stac | A1-F5 | 11 | 3 (v1,v2,v3) | 2 | 1.42 | +12 (pitch detector, 49/54 detected samples agree) |
| Brass/F Horn/sus | A1-F5 | 11 | 4 (v1,v2,v3,v4) | 1 | 9.9 | +12 (pitch detector, 29/29 detected samples agree) |
| Brass/OldTrombone/Buzz | F2-D4 | 13 | 2 (v1,v2) | 2 | 2.88 | +12 (pitch detector, 22/25 detected samples agree) |
| Brass/OldTrombone/Fall | G2-B3 | 15 | 1 (single) | 3 | 0.89 | +12 (pitch detector, 14/14 detected samples agree) |
| Brass/OldTrombone/Short | F2-F4 | 15 | 3 (v1,v2,v3) | 7 | 0.84 | +12 (pitch detector, 186/191 detected samples agree) |
| Brass/OldTrombone/Sustain | F2-G4 | 16 | 5 (v1,v2,v3,v4,v5) | 3 | 5.92 | +12 (pitch detector, 127/127 detected samples agree) |
| Brass/OldTrombone/Vibrato | A#2-F4 | 12 | 1 (v1) | 3 | 2.05 | +12 (pitch detector, 23/23 detected samples agree) |
| Brass/Tenor Trombone/stac | A#1-F4 | 7 | 4 (v1,v2,v3,v4) | 2 | 1.24 | +12 (pitch detector, 54/56 detected samples agree) |
| Brass/Tenor Trombone/sus | A#1-F4 | 11 | 3 (v1,v2,v3) | 1 | 9.14 | +12 (pitch detector, 31/31 detected samples agree) |
| Brass/Tenor Trombone/vib | F2-D#4 | 11 | 1 (v1) | 2 | 5.53 | +12 (pitch detector, 12/12 detected samples agree) |
| Brass/Trumpet/harmonM-sus | A#3-A5 | 8 | 2 (v1,v3) | 1 | 6.21 | +12 (pitch detector, 16/16 detected samples agree) |
| Brass/Trumpet/stac | F3-C6 | 11 | 3 (v1,v2,v3) | 2 | 1.27 | +12 (pitch detector, 56/57 detected samples agree) |
| Brass/Trumpet/straightM-sus | A#3-A5 | 8 | 2 (v1,v3) | 1 | 9.11 | +12 (pitch detector, 16/16 detected samples agree) |
| Brass/Trumpet/sus | F3-C6 | 10 | 2 (v1,v3) | 1 | 10.86 | +12 (pitch detector, 19/20 detected samples agree) |
| Brass/Trumpet/susvib | F3-C6 | 11 | 2 (v1,v2) | 1 | 5.5 | +12 (pitch detector, 22/22 detected samples agree) |
| Brass/Tuba/stac | A#1-D4 | 8 | 2 (v1,v2) | 4 | 0.79 | +12 (manual override (instrument range), 12/45 detected samples agree) |
| Brass/Tuba/sus | F1-D4 | 9 | 3 (v1,v2,v3) | 1 | 7.45 | +12 (pitch detector, 20/22 detected samples agree) |

### VSCO-2-CE / Keys

| Group | Range | Notes | Layers | RR | Len (s) | Octave |
|---|---|---|---|---|---|---|
| Keys/Upright Nr1 | C1-G7 | 14 | 3 (pp,mf,f) | 2 | 10.48 | +0 (pitch detector, 68/75 detected samples agree) |
| Keys/Upright Piano | A0-C#8 | 23 | 3 (dyn1,dyn2,dyn3) | 1 | 14.13 | +0 (pitch detector, 48/52 detected samples agree) |

### VSCO-2-CE / Percussion

| Group | Range | Notes | Layers | RR | Len (s) | Octave |
|---|---|---|---|---|---|---|
| Percussion/Glock | G5-C8 | 6 | 1 (medium) | 1 | 7.08 | +12 (pitch detector, 6/6 detected samples agree) |
| Percussion/Marimba | F2-C7 | 10 | 1 (loud) | 1 | 3.76 | +12 (pitch detector, 6/9 detected samples agree) |
| Percussion/Timpani/Rolls::Timpani_Roll | F#2-G3 | 5 | 3 (v3,v4,v5) | 1 | 22.47 | detected (timpani principal mode) |
| Percussion/Timpani::Timpani_Hit | F#2-E3 | 5 | 3 (v1,v3,v4) | 2 | 7.38 | detected (timpani principal mode) |
| Percussion/Xylo | G4-C8 | 8 | 1 (ff) | 1 | 1.75 | +12 (pitch detector, 8/8 detected samples agree) |
| Percussion::TB_hit | C4-F5 | 4 | 2 (v3,v4) | 1 | 17.72 | +0 (pitch detector, 4/4 detected samples agree) |

### VSCO-2-CE / Strings

| Group | Range | Notes | Layers | RR | Len (s) | Octave |
|---|---|---|---|---|---|---|
| Strings/Cello Section/pizzT | C2-F5 | 13 | 2 (v1,v2) | 2 | 2.71 | +12 (pitch detector, 25/29 detected samples agree) |
| Strings/Cello Section/spic | C2-F5 | 13 | 2 (v1,v2) | 2 | 1.67 | +12 (pitch detector, 52/52 detected samples agree) |
| Strings/Cello Section/susvib | C2-F5 | 13 | 2 (v1,v3) | 2 | 9.64 | +12 (pitch detector, 27/27 detected samples agree) |
| Strings/Cello Section/trem | C2-F5 | 14 | 2 (v1,v2) | 1 | 7.59 | +12 (pitch detector, 24/25 detected samples agree) |
| Strings/Harp | E1-F7 | 23 | 3 (mp,mf,f) | 1 | 8.96 | +0 (pitch detector, 19/22 detected samples agree) |
| Strings/Solo Contrabass/Pizz | E1-B3 | 14 | 2 (v1,v3) | 2 | 2.5 | +12 (manual override (instrument range), 2/34 detected samples agree) |
| Strings/Solo Contrabass/Spic | E1-B3 | 14 | 2 (v1,v3) | 2 | 1.59 | +12 (manual override (instrument range), 15/40 detected samples agree) |
| Strings/Solo Contrabass/SusNV | E1-B3 | 14 | 2 (v1,v3) | 1 | 10.03 | +12 (pitch detector, 23/28 detected samples agree) |
| Strings/Solo Contrabass/SusVib | F#1-B3 | 13 | 2 (v1,v3) | 1 | 10.48 | +12 (pitch detector, 23/26 detected samples agree) |
| Strings/Solo Contrabass/Trem | E1-B3 | 8 | 2 (v1,v2) | 1 | 7.26 | +12 (sibling folders (detector unsure), 8/15 detected samples agree) |
| Strings/Solo Violin/Arco Vib | G3-C7 | 15 | 2 (p,f) | 1 | 14.13 | +0 (pitch detector, 30/30 detected samples agree) |
| Strings/Solo Violin/Pizz | G3-C7 | 13 | 2 (p,f) | 2 | 1.39 | +0 (pitch detector, 26/28 detected samples agree) |
| Strings/Solo Violin/Trem | G3-C7 | 14 | 2 (v1,v2) | 1 | 7.04 | +12 (pitch detector, 27/27 detected samples agree) |
| Strings/Solo Violin/spic | G3-C7 | 15 | 2 (v1,v2) | 2 | 1.2 | +12 (pitch detector, 60/60 detected samples agree) |
| Strings/Viola Section/pizz | C3-D6 | 12 | 2 (v1,v2) | 2 | 0.94 | +12 (manual override (instrument range), 15/18 detected samples agree) |
| Strings/Viola Section/spic | C3-D6 | 12 | 2 (v1,v2) | 2 | 1.05 | +12 (pitch detector, 48/48 detected samples agree) |
| Strings/Viola Section/susvib | C3-D6 | 13 | 2 (v1,v2) | 1 | 10.26 | +12 (pitch detector, 26/26 detected samples agree) |
| Strings/Viola Section/trem | C3-D6 | 12 | 2 (v1,v2) | 1 | 10.74 | +12 (pitch detector, 24/24 detected samples agree) |
| Strings/Violin Section/Pizz | G3-D6 | 11 | 2 (v1,v2) | 2 | 0.98 | +12 (pitch detector, 23/34 detected samples agree) |
| Strings/Violin Section/Spic | G3-D6 | 11 | 2 (v1,v2) | 2 | 0.95 | +12 (pitch detector, 44/44 detected samples agree) |
| Strings/Violin Section/Trem | G3-D6 | 11 | 2 (v1,v2) | 1 | 9.42 | +12 (pitch detector, 21/21 detected samples agree) |
| Strings/Violin Section/susVib | G3-D6 | 11 | 2 (v1,v2) | 1 | 11.69 | +12 (pitch detector, 22/22 detected samples agree) |

### VSCO-2-CE / Woodwinds

| Group | Range | Notes | Layers | RR | Len (s) | Octave |
|---|---|---|---|---|---|---|
| Woodwinds/Bassoon/stac | A#1-C5 | 13 | 2 (v1,v2) | 2 | 0.71 | +12 (pitch detector, 46/46 detected samples agree) |
| Woodwinds/Bassoon/sus | A#1-D#5 | 13 | 2 (v1,v2) | 1 | 7.9 | +12 (pitch detector, 25/25 detected samples agree) |
| Woodwinds/Bassoon/vib | G2-C5 | 10 | 2 (v1,v2) | 2 | 7.95 | +12 (pitch detector, 21/21 detected samples agree) |
| Woodwinds/Clarinet/stac | D3-F6 | 11 | 3 (v1,v2,v3) | 2 | 0.59 | +12 (pitch detector, 46/47 detected samples agree) |
| Woodwinds/Clarinet/susLong | D3-F#6 | 11 | 3 (v1,v2,v3) | 1 | 10.35 | +12 (pitch detector, 30/30 detected samples agree) |
| Woodwinds/Flute/expvib | C4-C7 | 10 | 1 (v1) | 2 | 10.48 | +12 (pitch detector, 13/14 detected samples agree) |
| Woodwinds/Flute/stac | A4-C7 | 8 | 4 (v1,v2,v3,v4) | 2 | 0.78 | +12 (pitch detector, 29/48 detected samples agree) |
| Woodwinds/Flute/susNV | C4-C7 | 10 | 3 (v1,v2,v3) | 1 | 9.98 | +12 (pitch detector, 18/19 detected samples agree) |
| Woodwinds/Flute/susvib | C4-C7 | 10 | 1 (v1) | 2 | 7.34 | +12 (pitch detector, 12/13 detected samples agree) |
| Woodwinds/Oboe/Stacc | A#3-F6 | 9 | 3 (v1,v2,v3) | 2 | 0.74 | +12 (pitch detector, 49/51 detected samples agree) |
| Woodwinds/Oboe/Sus | A#3-F6 | 9 | 2 (v1,v3) | 1 | 9.75 | +12 (pitch detector, 18/18 detected samples agree) |
| Woodwinds/Oboe/Vib | A#3-F6 | 9 | 2 (v1,v3) | 1 | 7.13 | +12 (pitch detector, 18/18 detected samples agree) |
| Woodwinds/Piccolo/Stac | A#5-A#7 | 5 | 1 (single) | 1 | 0.44 | +12 (pitch detector, 4/5 detected samples agree) |
| Woodwinds/Piccolo/Sus | G5-G7 | 5 | 1 (single) | 1 | 8.39 | +12 (pitch detector, 4/5 detected samples agree) |

## Unpitched groups (percussion, effects)

### VCSL / Aerophones

| Group (stroke) | Samples | Layers | RR | Len (s) |
|---|---|---|---|---|
| Aerophones/Edge-blown Aerophones/Ball Whistle::BallWhistle_Long-001 | 1 | 1 (single) | 1 | 2.05 |
| Aerophones/Edge-blown Aerophones/Ball Whistle::BallWhistle_Short-001 | 1 | 1 (single) | 1 | 1.09 |
| Aerophones/Edge-blown Aerophones/Pipe Organ::Rode_Blower | 1 | 1 (single) | 1 | 37.17 |
| Aerophones/Edge-blown Aerophones/Train Whistle, Toy::TrainLow_Double-001 | 1 | 1 (single) | 1 | 2.45 |
| Aerophones/Edge-blown Aerophones/Train Whistle, Toy::TrainLow_Fall-001 | 1 | 1 (single) | 1 | 2.1 |
| Aerophones/Edge-blown Aerophones/Train Whistle, Toy::TrainLow_Med-001 | 1 | 1 (single) | 1 | 1.49 |
| Aerophones/Edge-blown Aerophones/Train Whistle, Toy::TrainLow_Short-001 | 1 | 1 (single) | 1 | 1.12 |
| Aerophones/Edge-blown Aerophones/Train Whistle, Toy::TrainLow_Sus-001 | 1 | 1 (single) | 1 | 2.66 |
| Aerophones/Edge-blown Aerophones/Train Whistle, Toy::TrainMed_Short-001 | 1 | 1 (single) | 1 | 1.32 |
| Aerophones/Free Aerophones/Siren::SirenWhistle-002 | 1 | 1 (single) | 1 | 3.86 |
| Aerophones/Free Aerophones/Siren::SirenWhistle-005 | 1 | 1 (single) | 1 | 2.09 |
| Aerophones/Free Aerophones/Siren::SirenWhistle-008 | 1 | 1 (single) | 1 | 9.19 |
| Aerophones/Free Aerophones/Siren::SirenWhistle-009 | 1 | 1 (single) | 1 | 10.74 |
| Aerophones/Free Aerophones/Siren::SirenWhistle-010 | 1 | 1 (single) | 1 | 7.7 |
| Aerophones/Lip Aerophones/Didgeridoo::Didgeridoo1_Bark1 | 1 | 1 (single) | 1 | 0.46 |
| Aerophones/Lip Aerophones/Didgeridoo::Didgeridoo1_BarkDown2 | 1 | 1 (single) | 1 | 2.13 |
| Aerophones/Lip Aerophones/Didgeridoo::Didgeridoo1_Phrase1 | 1 | 1 (single) | 1 | 11.68 |
| Aerophones/Lip Aerophones/Didgeridoo::Didgeridoo1_Phrase3 | 1 | 1 (single) | 1 | 15.27 |
| Aerophones/Lip Aerophones/Didgeridoo::Didgeridoo1_Phrase5 | 1 | 1 (single) | 1 | 10.6 |
| Aerophones/Lip Aerophones/Didgeridoo::Didgeridoo1_Phrase6 | 1 | 1 (single) | 1 | 13.06 |
| Aerophones/Lip Aerophones/Didgeridoo::Didgeridoo1_Phrase8 | 1 | 1 (single) | 1 | 12.71 |
| Aerophones/Lip Aerophones/Didgeridoo::Didgeridoo1_Short1 | 1 | 1 (single) | 1 | 0.37 |
| Aerophones/Lip Aerophones/Didgeridoo::Didgeridoo1_Sus2 | 1 | 1 (single) | 1 | 12.38 |
| Aerophones/Lip Aerophones/Didgeridoo::Didgeridoo1_Sus3 | 1 | 1 (single) | 1 | 9.89 |
| Aerophones/Lip Aerophones/Didgeridoo::Didgeridoo1_Sus8 | 1 | 1 (single) | 1 | 14.5 |
| Aerophones/Lip Aerophones/Didgeridoo::Didgeridoo1_Tap1 | 1 | 1 (single) | 1 | 0.26 |

### VCSL / Chordophones

| Group (stroke) | Samples | Layers | RR | Len (s) |
|---|---|---|---|---|
| Chordophones/Zithers/Dan Tranh/FX::FX | 5 | 1 (single) | 5 | 9.8 |
| Chordophones/Zithers/Dan Tranh/FX::FX_05c | 1 | 1 (single) | 1 | 2.75 |
| Chordophones/Zithers/Dan Tranh/FX::FX_07c | 1 | 1 (single) | 1 | 3.91 |
| Chordophones/Zithers/Dan Tranh/Gliss::Gliss_Dwn_Med | 2 | 2 (mf,ff) | 1 | 8.86 |
| Chordophones/Zithers/Dan Tranh/Gliss::Gliss_Dwn_Slw | 2 | 2 (mf,ff) | 1 | 9.68 |
| Chordophones/Zithers/Dan Tranh/Gliss::Gliss_Dwn_Swl | 2 | 2 (mf,ff) | 1 | 9.8 |
| Chordophones/Zithers/Dan Tranh/Gliss::Gliss_Up_Med | 2 | 2 (mf,ff) | 1 | 8.28 |
| Chordophones/Zithers/Dan Tranh/Gliss::Gliss_Up_Slw | 2 | 2 (mf,ff) | 1 | 8.38 |
| Chordophones/Zithers/Dan Tranh/Gliss::Gliss_Up_Swl | 2 | 2 (mf,ff) | 1 | 8.71 |
| Chordophones/Zithers/Upright Piano, Knight/Pedal/Off::PedOff | 4 | 1 (single) | 4 | 3.31 |
| Chordophones/Zithers/Upright Piano, Knight/Pedal/On::PedOn | 4 | 1 (single) | 4 | 4.39 |

### VCSL / Idiophones

| Group (stroke) | Samples | Layers | RR | Len (s) |
|---|---|---|---|---|
| Idiophones/Struck Idiophones/Agogo Bells/Legacy::agogoBell | 2 | 2 (mf,f) | 1 | 1.63 |
| Idiophones/Struck Idiophones/Agogo Bells/Legacy::agogoBell2 | 3 | 2 (mp,mf) | 2 | 1.29 |
| Idiophones/Struck Idiophones/Agogo Bells/Legacy::agogoBell3 | 5 | 2 (f,ff) | 3 | 1.2 |
| Idiophones/Struck Idiophones/Agogo Bells::Agogo_High | 3 | 3 (v1,v2,v3) | 1 | 1.12 |
| Idiophones/Struck Idiophones/Agogo Bells::Agogo_Low | 2 | 2 (v1,v2) | 1 | 2.21 |
| Idiophones/Struck Idiophones/Anvil::Anvil_Hit1 | 3 | 3 (v1,v2,v3) | 1 | 1.69 |
| Idiophones/Struck Idiophones/Anvil::Anvil_Hit2 | 3 | 3 (v1,v2,v3) | 1 | 1.98 |
| Idiophones/Struck Idiophones/Anvil::Anvil_Hit3 | 3 | 3 (v1,v2,v3) | 1 | 1.44 |
| Idiophones/Struck Idiophones/Bell Tree - Legacy::bell_tree_metalscrape1 | 1 | 1 (single) | 1 | 3.52 |
| Idiophones/Struck Idiophones/Bell Tree - Legacy::bell_tree_scrape1 | 1 | 1 (single) | 1 | 2.33 |
| Idiophones/Struck Idiophones/Bell Tree - Legacy::bell_tree_scrape2 | 1 | 1 (single) | 1 | 4.4 |
| Idiophones/Struck Idiophones/Bell Tree - Legacy::bell_tree_scrape3 | 1 | 1 (single) | 1 | 4.44 |
| Idiophones/Struck Idiophones/Bell Tree - Legacy::bell_tree_woodscrape1 | 1 | 1 (single) | 1 | 3.7 |
| Idiophones/Struck Idiophones/Bell Tree/Stroke::BellTree_Stroke | 5 | 1 (single) | 5 | 5.65 |
| Idiophones/Struck Idiophones/Brake Drum::BrakeDrum1_Bowed | 1 | 1 (single) | 1 | 6.67 |
| Idiophones/Struck Idiophones/Brake Drum::BrakeDrum1_Hammer | 3 | 3 (v1,v2,v3) | 1 | 1.7 |
| Idiophones/Struck Idiophones/Brake Drum::BrakeDrum1_Susp | 2 | 2 (v1,v3) | 1 | 3.46 |
| Idiophones/Struck Idiophones/Brake Drum::BrakeDrum1_YarnM | 3 | 3 (v1,v2,v3) | 1 | 1.66 |
| Idiophones/Struck Idiophones/Brake Drum::BrakeDrum2_Bowed | 1 | 1 (single) | 1 | 5.89 |
| Idiophones/Struck Idiophones/Brake Drum::BrakeDrum2_Hammer1 | 2 | 2 (v1,v2) | 1 | 1.63 |
| Idiophones/Struck Idiophones/Brake Drum::BrakeDrum2_Hammer3 | 3 | 3 (v1,v2,v3) | 1 | 1.34 |
| Idiophones/Struck Idiophones/Brake Drum::BrakeDrum2_Susp | 2 | 2 (v1,v2) | 1 | 2.36 |
| Idiophones/Struck Idiophones/Cabasa::Cabasa1_Hit | 2 | 1 (single) | 2 | 0.85 |
| Idiophones/Struck Idiophones/Cabasa::Cabasa1_Rub | 4 | 2 (v1,v2) | 2 | 1.0 |
| Idiophones/Struck Idiophones/Cajon::Cajon_hit1 | 6 | 3 (mp,f,fff) | 2 | 1.29 |
| Idiophones/Struck Idiophones/Cajon::Cajon_hit2 | 6 | 3 (pp,mp,f) | 2 | 1.29 |
| Idiophones/Struck Idiophones/Cajon::Cajon_hit3 | 6 | 3 (p,mp,f) | 2 | 1.39 |
| Idiophones/Struck Idiophones/Claps::Clap | 6 | 1 (single) | 6 | 0.7 |
| Idiophones/Struck Idiophones/Claps::SoloClap | 4 | 4 (vl1,vl2,vl3,vl4) | 1 | 0.41 |
| Idiophones/Struck Idiophones/Clash Cymbals 1::cymbal_crash1 | 8 | 4 (pp,mp,mf,ff) | 2 | 8.94 |
| Idiophones/Struck Idiophones/Clash Cymbals 1::cymbal_crash1_short1 | 1 | 1 (single) | 1 | 2.39 |
| Idiophones/Struck Idiophones/Clash Cymbals 1::cymbal_crash1_short2 | 1 | 1 (single) | 1 | 1.9 |
| Idiophones/Struck Idiophones/Clash Cymbals 2::cymbal_crash2 | 5 | 3 (mp,f,fff) | 2 | 12.9 |
| Idiophones/Struck Idiophones/Claves/Legacy::claves | 6 | 4 (pp,mp,mf,ff) | 3 | 0.45 |
| Idiophones/Struck Idiophones/Claves::Claves1_Hit | 3 | 3 (v1,v2,v3) | 1 | 1.13 |
| Idiophones/Struck Idiophones/Claves::Claves2_Hit | 3 | 3 (v1,v2,v3) | 1 | 1.03 |
| Idiophones/Struck Idiophones/Cowbells::Cowbell1_Hit | 3 | 3 (v2,v3,v4) | 1 | 1.13 |
| Idiophones/Struck Idiophones/Cowbells::Cowbell1_Muted | 2 | 2 (v2,v3) | 1 | 1.08 |
| Idiophones/Struck Idiophones/Cowbells::Cowbell1_Normal | 2 | 2 (v2,v3) | 1 | 0.97 |
| Idiophones/Struck Idiophones/Cowbells::Cowbell2_Double | 2 | 2 (v2,v3) | 1 | 1.14 |
| Idiophones/Struck Idiophones/Cowbells::Cowbell2_Muted | 2 | 2 (v2,v3) | 1 | 1.13 |
| Idiophones/Struck Idiophones/Cowbells::Cowbell2_Normal | 2 | 2 (v2,v3) | 1 | 1.74 |
| Idiophones/Struck Idiophones/Finger Cymbals::Fing_Cymb | 1 | 1 (single) | 1 | 6.34 |
| Idiophones/Struck Idiophones/Flexatone::flexatone1 | 1 | 1 (single) | 1 | 3.8 |
| Idiophones/Struck Idiophones/Flexatone::flexatone2 | 1 | 1 (single) | 1 | 3.56 |
| Idiophones/Struck Idiophones/Flexatone::flexatone_extralong | 1 | 1 (single) | 1 | 12.49 |
| Idiophones/Struck Idiophones/Flexatone::flexatone_fast | 1 | 1 (single) | 1 | 4.32 |
| Idiophones/Struck Idiophones/Flexatone::flexatone_long | 1 | 1 (single) | 1 | 7.82 |
| Idiophones/Struck Idiophones/Flexatone::flexatone_long2 | 1 | 1 (single) | 1 | 8.96 |
| Idiophones/Struck Idiophones/Flexatone::flexatone_slap1 | 1 | 1 (single) | 1 | 1.01 |
| Idiophones/Struck Idiophones/Flexatone::flexatone_slap2 | 1 | 1 (single) | 1 | 1.31 |
| Idiophones/Struck Idiophones/Gong 1::gong | 4 | 4 (p,mf,f,fff) | 1 | 30.11 |
| Idiophones/Struck Idiophones/Gong 1::gong_2 | 2 | 2 (mp,f) | 1 | 21.46 |
| Idiophones/Struck Idiophones/Gong 1::gong_scrape | 1 | 1 (mf) | 1 | 9.57 |
| Idiophones/Struck Idiophones/Guiro/Legacy::guiro_long | 1 | 1 (single) | 1 | 0.58 |
| Idiophones/Struck Idiophones/Guiro/Legacy::guiro_long2 | 1 | 1 (single) | 1 | 0.96 |
| Idiophones/Struck Idiophones/Guiro/Legacy::guiro_short | 1 | 1 (single) | 1 | 0.35 |
| Idiophones/Struck Idiophones/Guiro/Legacy::guiro_short2 | 1 | 1 (single) | 1 | 0.52 |
| Idiophones/Struck Idiophones/Guiro/Legacy::guiro_short3 | 1 | 1 (single) | 1 | 0.43 |
| Idiophones/Struck Idiophones/Guiro/Legacy::guiro_short4 | 1 | 1 (single) | 1 | 0.43 |
| Idiophones/Struck Idiophones/Guiro/Legacy::guiro_short5 | 1 | 1 (single) | 1 | 0.4 |
| Idiophones/Struck Idiophones/Guiro/Legacy::guiro_superlong | 1 | 1 (single) | 1 | 0.98 |
| Idiophones/Struck Idiophones/Guiro/Legacy::gurio_long4 | 1 | 1 (single) | 1 | 0.66 |
| Idiophones/Struck Idiophones/Guiro::Guiro_Fast | 1 | 1 (single) | 1 | 1.51 |
| Idiophones/Struck Idiophones/Guiro::Guiro_Hit | 2 | 1 (single) | 2 | 1.32 |
| Idiophones/Struck Idiophones/Guiro::Guiro_Med | 1 | 1 (single) | 1 | 1.88 |
| Idiophones/Struck Idiophones/Guiro::Guiro_Slow | 1 | 1 (single) | 1 | 2.44 |
| Idiophones/Struck Idiophones/Hand Bells, Nepalese::HB | 3 | 1 (single) | 3 | 2.24 |
| Idiophones/Struck Idiophones/Hi-Hat Cymbal::HiHat | 2 | 1 (single) | 2 | 1.39 |
| Idiophones/Struck Idiophones/Hi-Hat Cymbal::HiHat_HitC | 8 | 4 (v1,v2,v3,v4) | 2 | 1.37 |
| Idiophones/Struck Idiophones/Hi-Hat Cymbal::HiHat_HitLoose | 2 | 1 (single) | 2 | 2.63 |
| Idiophones/Struck Idiophones/Hi-Hat Cymbal::HiHat_HitO | 2 | 1 (single) | 2 | 5.99 |
| Idiophones/Struck Idiophones/Hi-Hat Cymbal::HiHat_HitOC | 1 | 1 (single) | 1 | 1.94 |
| Idiophones/Struck Idiophones/Mark Trees/Legacy::windchimes_asc1 | 1 | 1 (single) | 1 | 7.76 |
| Idiophones/Struck Idiophones/Mark Trees/Legacy::windchimes_desc1 | 1 | 1 (single) | 1 | 9.87 |
| Idiophones/Struck Idiophones/Mark Trees/Legacy::windchimes_fastAsc1 | 1 | 1 (single) | 1 | 13.32 |
| Idiophones/Struck Idiophones/Mark Trees/Legacy::windchimes_random | 1 | 1 (single) | 1 | 21.64 |
| Idiophones/Struck Idiophones/Mark Trees/Legacy::windchimes_slowAsc1 | 1 | 1 (single) | 1 | 11.22 |
| Idiophones/Struck Idiophones/Mark Trees/Legacy::windchimes_slowDesc1 | 1 | 1 (single) | 1 | 10.73 |
| Idiophones/Struck Idiophones/Ratchet::Ratchet1_Crank | 2 | 1 (single) | 2 | 1.45 |
| Idiophones/Struck Idiophones/Ratchet::Ratchet1_Fast | 1 | 1 (single) | 1 | 7.07 |
| Idiophones/Struck Idiophones/Ratchet::Ratchet1_Slow | 1 | 1 (single) | 1 | 8.95 |
| Idiophones/Struck Idiophones/Ratchet::Ratchet2_Crank | 2 | 1 (v1) | 2 | 1.48 |
| Idiophones/Struck Idiophones/Ratchet::Ratchet2_Fast | 1 | 1 (single) | 1 | 8.76 |
| Idiophones/Struck Idiophones/Ratchet::Ratchet2_Slow | 1 | 1 (single) | 1 | 10.23 |
| Idiophones/Struck Idiophones/Shaker - Legacy::shake1 | 1 | 1 (single) | 1 | 0.18 |
| Idiophones/Struck Idiophones/Shaker - Legacy::shake2 | 1 | 1 (single) | 1 | 0.19 |
| Idiophones/Struck Idiophones/Shaker, Large::LShaker_Hit | 2 | 1 (single) | 2 | 1.31 |
| Idiophones/Struck Idiophones/Shaker, Large::LShaker_Shake1D | 2 | 1 (single) | 2 | 1.36 |
| Idiophones/Struck Idiophones/Shaker, Large::LShaker_Shake1U | 2 | 1 (single) | 2 | 1.4 |
| Idiophones/Struck Idiophones/Shaker, Small::ShakerDouble_Down | 2 | 1 (single) | 2 | 0.26 |
| Idiophones/Struck Idiophones/Shaker, Small::ShakerDouble_Up | 2 | 1 (single) | 2 | 0.15 |
| Idiophones/Struck Idiophones/Shaker, Small::ShakerHighFaster_Down | 2 | 1 (single) | 2 | 0.16 |
| Idiophones/Struck Idiophones/Shaker, Small::ShakerHighFaster_Up | 2 | 1 (single) | 2 | 0.16 |
| Idiophones/Struck Idiophones/Shaker, Small::ShakerLowFaster_Down | 2 | 1 (single) | 2 | 0.14 |
| Idiophones/Struck Idiophones/Shaker, Small::ShakerLowFaster_Up | 2 | 1 (single) | 2 | 0.1 |
| Idiophones/Struck Idiophones/Shaker, Small::Shaker_Roll_Fast | 2 | 1 (single) | 2 | 3.48 |
| Idiophones/Struck Idiophones/Shaker, Small::Shaker_Slap | 2 | 1 (single) | 2 | 0.69 |
| Idiophones/Struck Idiophones/Slapstick::slapstick | 5 | 1 (single) | 5 | 0.67 |
| Idiophones/Struck Idiophones/Sleigh Bells::Sleighbells_Hit | 2 | 1 (single) | 2 | 2.48 |
| Idiophones/Struck Idiophones/Sleigh Bells::sleighbell1_shake1 | 1 | 1 (single) | 1 | 5.25 |
| Idiophones/Struck Idiophones/Sleigh Bells::sleighbell2_hit | 2 | 1 (loud) | 2 | 1.42 |
| Idiophones/Struck Idiophones/Sleigh Bells::sleighbell2_shake1 | 1 | 1 (single) | 1 | 6.3 |
| Idiophones/Struck Idiophones/Slit Drum::LogDrumHi_MedM | 3 | 3 (v1,v2,v3) | 1 | 1.52 |
| Idiophones/Struck Idiophones/Slit Drum::LogDrumLo_MedM | 3 | 3 (v1,v2,v3) | 1 | 1.25 |
| Idiophones/Struck Idiophones/Suspended Cymbal 1::susCymb1_bow | 4 | 1 (single) | 4 | 10.82 |
| Idiophones/Struck Idiophones/Suspended Cymbal 1::susCymb1_cresc_1.5s | 1 | 1 (single) | 1 | 11.44 |
| Idiophones/Struck Idiophones/Suspended Cymbal 1::susCymb1_cresc_2s | 1 | 1 (single) | 1 | 10.42 |
| Idiophones/Struck Idiophones/Suspended Cymbal 1::susCymb1_cresc_4s | 1 | 1 (single) | 1 | 12.99 |
| Idiophones/Struck Idiophones/Suspended Cymbal 1::susCymb1_cresc_7.5s | 1 | 1 (single) | 1 | 16.96 |
| Idiophones/Struck Idiophones/Suspended Cymbal 1::susCymb1_hit | 4 | 4 (pp,mp,f,fff) | 1 | 11.42 |
| Idiophones/Struck Idiophones/Suspended Cymbal 1::susCymb1_hit_bell | 3 | 3 (pp,mf,fff) | 1 | 7.25 |
| Idiophones/Struck Idiophones/Suspended Cymbal 1::susCymb1_hit_stick | 3 | 3 (pp,mp,f) | 1 | 6.88 |
| Idiophones/Struck Idiophones/Suspended Cymbal 1::susCymb1_roll_nloop | 3 | 3 (mp,f,ff) | 1 | 29.66 |
| Idiophones/Struck Idiophones/Suspended Cymbal 1::susCymb1_roll_rel | 3 | 3 (mp,f,ff) | 1 | 6.17 |
| Idiophones/Struck Idiophones/Suspended Cymbal 1::susCymb1_scrape | 1 | 1 (single) | 1 | 7.55 |
| Idiophones/Struck Idiophones/Suspended Cymbal 2::susCymb2_bowed | 3 | 1 (single) | 3 | 14.51 |
| Idiophones/Struck Idiophones/Suspended Cymbal 2::susCymb2_cresc_2.5s2 | 1 | 1 (single) | 1 | 14.02 |
| Idiophones/Struck Idiophones/Suspended Cymbal 2::susCymb2_cresc_4s | 1 | 1 (single) | 1 | 14.54 |
| Idiophones/Struck Idiophones/Suspended Cymbal 2::susCymb2_cresc_7s | 1 | 1 (single) | 1 | 17.39 |
| Idiophones/Struck Idiophones/Suspended Cymbal 2::susCymb2_hit | 5 | 5 (pp,mp,mf,f,fff) | 1 | 10.71 |
| Idiophones/Struck Idiophones/Suspended Cymbal 2::susCymb2_hit_bell | 2 | 2 (p,f) | 1 | 8.15 |
| Idiophones/Struck Idiophones/Suspended Cymbal 2::susCymb2_hit_stick | 3 | 3 (pp,mp,mf) | 1 | 7.62 |
| Idiophones/Struck Idiophones/Suspended Cymbal 2::susCymb2_roll_nloop | 3 | 3 (pp,f,fff) | 1 | 18.99 |
| Idiophones/Struck Idiophones/Suspended Cymbal 2::susCymb2_roll_rel | 3 | 3 (pp,f,fff) | 1 | 7.31 |
| Idiophones/Struck Idiophones/Suspended Cymbal 2::susCymb2_scrape | 1 | 1 (single) | 1 | 10.55 |
| Idiophones/Struck Idiophones/Tambourine 1::Tamb1_Hit | 2 | 2 (v1,v2) | 1 | 1.79 |
| Idiophones/Struck Idiophones/Tambourine 1::Tamb1_Roll | 3 | 3 (v1,v2,v3) | 1 | 10.49 |
| Idiophones/Struck Idiophones/Tambourine 1::Tamb1_Shake | 2 | 1 (single) | 2 | 1.41 |
| Idiophones/Struck Idiophones/Tambourine 2::Tamb2_Hit | 2 | 2 (v1,v2) | 1 | 1.32 |
| Idiophones/Struck Idiophones/Tambourine 2::Tamb2_Roll | 3 | 3 (v1,v2,v3) | 1 | 10.11 |
| Idiophones/Struck Idiophones/Tambourine 2::Tamb2_Shake | 2 | 1 (single) | 2 | 1.05 |
| Idiophones/Struck Idiophones/Tambourine 3 - Legacy::tambourine_down | 2 | 1 (single) | 2 | 0.59 |
| Idiophones/Struck Idiophones/Tambourine 3 - Legacy::tambourine_up | 2 | 1 (single) | 2 | 0.3 |
| Idiophones/Struck Idiophones/Tambourine 4 - Legacy::tamb2 | 4 | 1 (single) | 4 | 0.3 |
| Idiophones/Struck Idiophones/Tambourine 4 - Legacy::tamb2_rollFast | 1 | 1 (single) | 1 | 4.67 |
| Idiophones/Struck Idiophones/Tambourine 4 - Legacy::tamb2_rollSlow | 1 | 1 (single) | 1 | 2.89 |
| Idiophones/Struck Idiophones/Tambourine 5 - Legacy::tamb3 | 8 | 1 (single) | 8 | 0.33 |
| Idiophones/Struck Idiophones/Tambourine 5 - Legacy::tamb3_roll | 1 | 1 (single) | 1 | 11.5 |
| Idiophones/Struck Idiophones/Triangles/Legacy/1::triangle1_hit | 2 | 2 (pp,mp) | 1 | 6.64 |
| Idiophones/Struck Idiophones/Triangles/Legacy/1::triangle1_hit_muted | 1 | 1 (pp) | 1 | 2.37 |
| Idiophones/Struck Idiophones/Triangles/Legacy/1::triangle1_hit_muted1 | 1 | 1 (mp) | 1 | 2.46 |
| Idiophones/Struck Idiophones/Triangles/Legacy/1::triangle1_hit_muted2 | 1 | 1 (mp) | 1 | 2.37 |
| Idiophones/Struck Idiophones/Triangles/Legacy/1::triangle1_hit_muted3 | 1 | 1 (mp) | 1 | 2.56 |
| Idiophones/Struck Idiophones/Triangles/Legacy/1::triangle1_hit_pt2 | 1 | 1 (mf) | 1 | 9.35 |
| Idiophones/Struck Idiophones/Triangles/Legacy/1::triangle1_hit_pt3 | 1 | 1 (mp) | 1 | 9.99 |
| Idiophones/Struck Idiophones/Triangles/Legacy/1::triangle1_roll | 1 | 1 (single) | 1 | 13.05 |
| Idiophones/Struck Idiophones/Triangles/Legacy/2::triangle2_hit | 4 | 2 (p,mp) | 2 | 5.8 |
| Idiophones/Struck Idiophones/Triangles/Legacy/2::triangle2_roll | 1 | 1 (single) | 1 | 11.61 |
| Idiophones/Struck Idiophones/Triangles/Legacy/3::triangle3_hit | 5 | 4 (pp,p,mp,mf) | 2 | 3.11 |
| Idiophones/Struck Idiophones/Triangles/Legacy/3::triangle3_hit_pt2 | 1 | 1 (mp) | 1 | 5.06 |
| Idiophones/Struck Idiophones/Triangles/Legacy/3::triangle3_hit_pt3 | 1 | 1 (mp) | 1 | 4.39 |
| Idiophones/Struck Idiophones/Triangles/Legacy/3::triangle3_roll | 1 | 1 (single) | 1 | 10.69 |
| Idiophones/Struck Idiophones/Triangles/Legacy/4::triangle4_hit | 3 | 2 (mp,mf) | 2 | 6.37 |
| Idiophones/Struck Idiophones/Triangles/Legacy/4::triangle4_roll1 | 1 | 1 (single) | 1 | 8.77 |
| Idiophones/Struck Idiophones/Triangles::Triangle1_Hit | 4 | 2 (v1,v2) | 2 | 5.02 |
| Idiophones/Struck Idiophones/Triangles::Triangle1_HitFM | 2 | 1 (v1) | 2 | 1.13 |
| Idiophones/Struck Idiophones/Triangles::Triangle1_HitM | 2 | 1 (v1) | 2 | 1.14 |
| Idiophones/Struck Idiophones/Triangles::Triangle1_Roll | 1 | 1 (single) | 1 | 27.93 |
| Idiophones/Struck Idiophones/Triangles::Triangle1_hitFM | 2 | 1 (v2) | 2 | 2.22 |
| Idiophones/Struck Idiophones/Triangles::Triangle3_Hit | 4 | 2 (v1,v2) | 2 | 9.47 |
| Idiophones/Struck Idiophones/Triangles::Triangle3_HitFM | 4 | 2 (v1,v2) | 2 | 0.85 |
| Idiophones/Struck Idiophones/Triangles::Triangle3_HitM | 4 | 2 (v1,v2) | 2 | 1.36 |
| Idiophones/Struck Idiophones/Triangles::Triangle3_Roll | 1 | 1 (v2) | 1 | 39.38 |
| Idiophones/Struck Idiophones/Triangles::Triangle6_Hit | 4 | 2 (v1,v2) | 2 | 2.26 |
| Idiophones/Struck Idiophones/Triangles::Triangle6_HitFM | 4 | 2 (v1,v2) | 2 | 1.02 |
| Idiophones/Struck Idiophones/Triangles::Triangle6_HitM | 4 | 2 (v1,v2) | 2 | 1.05 |
| Idiophones/Struck Idiophones/Triangles::Triangle6_Roll | 1 | 1 (v2) | 1 | 22.97 |
| Idiophones/Struck Idiophones/Vibraslap/Legacy::vibraslap | 4 | 1 (single) | 4 | 2.87 |
| Idiophones/Struck Idiophones/Woodblock::wood_click | 7 | 4 (pp,mp,f,ff) | 3 | 0.51 |
| Idiophones/Struck Idiophones/Woodblock::wood_click2 | 1 | 1 (mp) | 1 | 1.4 |
| Idiophones/Struck Idiophones/Woodblock::wood_click3 | 2 | 2 (vl1,vl2) | 1 | 0.82 |

### VCSL / Membranophones

| Group (stroke) | Samples | Layers | RR | Len (s) |
|---|---|---|---|---|
| Membranophones/Other Membranophones/Ocean Drum::OceanDrum_Sus | 3 | 1 (single) | 3 | 25.4 |
| Membranophones/Struck Membranophones/Bass Drum 1::BDrumNew_hit | 8 | 4 (v2,v3,v5,v7) | 2 | 2.71 |
| Membranophones/Struck Membranophones/Bass Drum 2::bassdrum_cresc | 1 | 1 (med) | 1 | 26.51 |
| Membranophones/Struck Membranophones/Bass Drum 2::bassdrum_cresc_short | 1 | 1 (single) | 1 | 16.25 |
| Membranophones/Struck Membranophones/Bass Drum 2::bassdrum_hit | 8 | 5 (pp,mp,mf,f,ff) | 2 | 9.91 |
| Membranophones/Struck Membranophones/Bass Drum 2::bassdrum_roll | 4 | 4 (pp,mp,mf,ff) | 1 | 12.99 |
| Membranophones/Struck Membranophones/Bass Drum 2::bassdrum_roll_fast | 4 | 4 (pp,mp,mf,f) | 1 | 10.87 |
| Membranophones/Struck Membranophones/Bass Drum 2::bassdrum_roll_fast_rel | 4 | 4 (pp,mp,mf,f) | 1 | 7.41 |
| Membranophones/Struck Membranophones/Bass Drum 2::bassdrum_roll_rel | 4 | 4 (pp,mp,mf,ff) | 1 | 8.56 |
| Membranophones/Struck Membranophones/Bass Drum 2::bassdrum_rub10 | 1 | 1 (single) | 1 | 8.7 |
| Membranophones/Struck Membranophones/Bass Drum 2::bassdrum_rub12 | 1 | 1 (single) | 1 | 11.19 |
| Membranophones/Struck Membranophones/Bass Drum 2::bassdrum_rub2 | 1 | 1 (single) | 1 | 7.72 |
| Membranophones/Struck Membranophones/Bass Drum 2::bassdrum_rub7 | 1 | 1 (single) | 1 | 4.88 |
| Membranophones/Struck Membranophones/Bass Drum 3 - Legacy::bdrum | 13 | 7 (ppp,pp,p,mp,f,ff,fff) | 3 | 5.58 |
| Membranophones/Struck Membranophones/Bass Drum 3 - Legacy::bdrum2 | 4 | 2 (ppp,pp) | 2 | 3.37 |
| Membranophones/Struck Membranophones/Bass Drum 3 - Legacy::bdrum3 | 4 | 4 (ppp,p,mp,fff) | 1 | 7.08 |
| Membranophones/Struck Membranophones/Bass Drum 3 - Legacy::bdrum_muted | 11 | 6 (ppp,pp,mp,mf,ff,fff) | 3 | 2.24 |
| Membranophones/Struck Membranophones/Bass Drum 3 - Legacy::bdrum_roll-quietest | 1 | 1 (single) | 1 | 13.89 |
| Membranophones/Struck Membranophones/Bass Drum 3 - Legacy::bdrum_roll1 | 1 | 1 (single) | 1 | 10.16 |
| Membranophones/Struck Membranophones/Bass Drum 3 - Legacy::bdrum_roll_long1 | 1 | 1 (single) | 1 | 22.84 |
| Membranophones/Struck Membranophones/Bass Drum 3 - Legacy::bdrum_roll_quieter | 1 | 1 (single) | 1 | 27.29 |
| Membranophones/Struck Membranophones/Bass Drum 3 - Legacy::bdrum_roll_short | 2 | 1 (single) | 2 | 7.05 |
| Membranophones/Struck Membranophones/Bass Drum 3 - Legacy::bdrum_special_sidehit | 1 | 1 (single) | 1 | 0.86 |
| Membranophones/Struck Membranophones/Bongos::BongoH_Hit1 | 6 | 3 (v1,v2,v3) | 2 | 1.09 |
| Membranophones/Struck Membranophones/Bongos::BongoH_HitMuted1 | 6 | 3 (v1,v2,v3) | 2 | 1.02 |
| Membranophones/Struck Membranophones/Bongos::BongoH_Roll | 2 | 2 (v2,v3) | 1 | 3.43 |
| Membranophones/Struck Membranophones/Bongos::BongoL_Hit1 | 6 | 3 (v1,v2,v3) | 2 | 1.11 |
| Membranophones/Struck Membranophones/Bongos::BongoL_HitMuted2 | 6 | 3 (v1,v2,v3) | 2 | 1.12 |
| Membranophones/Struck Membranophones/Bongos::BongoL_Roll | 2 | 2 (v2,v3) | 1 | 3.1 |
| Membranophones/Struck Membranophones/Conga::Conga_HitFM | 4 | 2 (v1,v2) | 2 | 0.82 |
| Membranophones/Struck Membranophones/Conga::Conga_HitN | 6 | 3 (v1,v2,v3) | 2 | 0.9 |
| Membranophones/Struck Membranophones/Conga::Quinto_HitFM1 | 4 | 2 (v1,v2) | 2 | 0.79 |
| Membranophones/Struck Membranophones/Conga::Quinto_HitN | 6 | 3 (v1,v2,v3) | 2 | 0.89 |
| Membranophones/Struck Membranophones/Conga::Tumba_HitFM | 6 | 3 (v2,v3,v4) | 2 | 0.54 |
| Membranophones/Struck Membranophones/Conga::Tumba_HitN | 8 | 4 (v1,v2,v3,v4) | 2 | 0.72 |
| Membranophones/Struck Membranophones/Darbuka::Darbuka_1_hit | 4 | 2 (vl1,vl2) | 2 | 1.21 |
| Membranophones/Struck Membranophones/Darbuka::Darbuka_2_hit | 4 | 2 (vl1,vl2) | 2 | 0.63 |
| Membranophones/Struck Membranophones/Darbuka::Darbuka_3_hit | 4 | 2 (vl1,vl2) | 2 | 0.51 |
| Membranophones/Struck Membranophones/Darbuka::Darbuka_4_hit | 4 | 2 (vl1,vl2) | 2 | 0.63 |
| Membranophones/Struck Membranophones/Darbuka::Darbuka_5_hit | 4 | 2 (vl1,vl2) | 2 | 0.58 |
| Membranophones/Struck Membranophones/Frame Drum::HDrumL_Hand | 1 | 1 (single) | 1 | 1.16 |
| Membranophones/Struck Membranophones/Frame Drum::HDrumL_Hit | 4 | 2 (v2,v3) | 2 | 3.53 |
| Membranophones/Struck Membranophones/Frame Drum::HDrumL_HitMuted | 4 | 2 (v2,v3) | 2 | 1.72 |
| Membranophones/Struck Membranophones/Frame Drum::HDrumS_Hand | 1 | 1 (v1) | 1 | 0.84 |
| Membranophones/Struck Membranophones/Frame Drum::HDrumS_Hit | 4 | 2 (v2,v3) | 2 | 2.36 |
| Membranophones/Struck Membranophones/Frame Drum::HDrumS_HitMuted | 4 | 2 (v2,v3) | 2 | 0.99 |
| Membranophones/Struck Membranophones/Legacy Snares/OldSnare::snare | 14 | 5 (pp,p,mf,f,ff) | 4 | 0.25 |
| Membranophones/Struck Membranophones/Legacy Snares/OldSnare::snare_rim | 1 | 1 (single) | 1 | 0.25 |
| Membranophones/Struck Membranophones/Legacy Snares/drum1::snare1 | 16 | 8 (pppp,ppp,pp,p,mp,f,ff,fff) | 3 | 0.54 |
| Membranophones/Struck Membranophones/Legacy Snares/drum1::snare1_click | 1 | 1 (single) | 1 | 0.28 |
| Membranophones/Struck Membranophones/Legacy Snares/drum1::snare1_click2 | 1 | 1 (single) | 1 | 0.28 |
| Membranophones/Struck Membranophones/Legacy Snares/drum1::snare1_click3 | 1 | 1 (single) | 1 | 0.29 |
| Membranophones/Struck Membranophones/Legacy Snares/drum1::snare1_click4 | 1 | 1 (single) | 1 | 0.22 |
| Membranophones/Struck Membranophones/Legacy Snares/drum1::snare1_nosnare | 14 | 7 (ppp,pp,mp,mf,f,ff,fff) | 3 | 0.51 |
| Membranophones/Struck Membranophones/Legacy Snares/drum1::snare1_rim | 1 | 1 (fff) | 1 | 1.11 |
| Membranophones/Struck Membranophones/Legacy Snares/drum1::snare1_rimshot | 3 | 3 (mf,f,fff) | 1 | 0.52 |
| Membranophones/Struck Membranophones/Legacy Snares/drum1::snare1_snare | 1 | 1 (mp) | 1 | 0.49 |
| Membranophones/Struck Membranophones/Legacy Snares/drum1::snare1_snare2 | 1 | 1 (mp) | 1 | 0.49 |
| Membranophones/Struck Membranophones/Legacy Snares/drum2::sfx_click | 1 | 1 (single) | 1 | 0.2 |
| Membranophones/Struck Membranophones/Legacy Snares/drum2::snare2 | 17 | 9 (pppp,ppp,pp,p,mp,mf,f,ff,fff) | 3 | 0.41 |
| Membranophones/Struck Membranophones/Legacy Snares/drum2::snare2_click | 1 | 1 (single) | 1 | 0.38 |
| Membranophones/Struck Membranophones/Legacy Snares/drum2::snare2_nosnare | 12 | 8 (pppp,ppp,pp,p,mf,f,ff,fff) | 3 | 0.47 |
| Membranophones/Struck Membranophones/Legacy Snares/drum2::snare2_nosnare_roll | 1 | 1 (ff) | 1 | 3.28 |
| Membranophones/Struck Membranophones/Legacy Snares/drum2::snare2_rimshot | 4 | 3 (mf,f,ff) | 2 | 0.61 |
| Membranophones/Struck Membranophones/Legacy Snares/drum3_marching::snare3 | 13 | 6 (ppp,pp,p,mp,f,fff) | 4 | 0.4 |
| Membranophones/Struck Membranophones/Legacy Snares/drum3_marching::snare3_click | 2 | 1 (single) | 2 | 0.31 |
| Membranophones/Struck Membranophones/Legacy Snares/drum3_marching::snare3_rimshot | 2 | 2 (f,ff) | 1 | 0.46 |
| Membranophones/Struck Membranophones/Legacy Toms/tenor_higher::tenorH | 22 | 7 (pp,p,mp,mf,f,ff,fff) | 6 | 1.89 |
| Membranophones/Struck Membranophones/Legacy Toms/tenor_lower::tenor | 19 | 7 (ppp,pp,mp,mf,f,ff,fff) | 4 | 1.66 |
| Membranophones/Struck Membranophones/Snare Drum, Modern 1::Snare2_HitNS | 8 | 4 (v2,v4,v5,v6) | 2 | 0.94 |
| Membranophones/Struck Membranophones/Snare Drum, Modern 1::Snare2_HitSN | 10 | 5 (v3,v5,v6,v7,v9) | 2 | 1.46 |
| Membranophones/Struck Membranophones/Snare Drum, Modern 1::Snare2_rollNS | 4 | 4 (v2,v3,v4,v5) | 1 | 6.95 |
| Membranophones/Struck Membranophones/Snare Drum, Modern 1::Snare2_rollSN | 3 | 3 (v2,v4,v5) | 1 | 9.17 |
| Membranophones/Struck Membranophones/Snare Drum, Modern 1::Snare2_stick | 2 | 1 (v1) | 2 | 0.8 |
| Membranophones/Struck Membranophones/Snare Drum, Modern 1::Snare2_taps | 2 | 1 (v4) | 2 | 1.23 |
| Membranophones/Struck Membranophones/Snare Drum, Modern 2::Snare3M_HitNS | 6 | 3 (v2,v4,v5) | 2 | 0.94 |
| Membranophones/Struck Membranophones/Snare Drum, Modern 2::Snare3M_HitSN | 8 | 4 (v2,v3,v4,v5) | 2 | 0.94 |
| Membranophones/Struck Membranophones/Snare Drum, Modern 2::Snare3M_Xstick | 2 | 1 (v2) | 2 | 1.15 |
| Membranophones/Struck Membranophones/Snare Drum, Modern 2::Snare3M_rollNS | 2 | 2 (v3,v4) | 1 | 6.76 |
| Membranophones/Struck Membranophones/Snare Drum, Modern 2::Snare3M_rollSN | 2 | 2 (v3,v4) | 1 | 7.17 |
| Membranophones/Struck Membranophones/Snare Drum, Modern 2::Snare3M_stick | 2 | 1 (v3) | 2 | 0.85 |
| Membranophones/Struck Membranophones/Snare Drum, Modern 2::Snare3M_taps | 2 | 1 (v4) | 2 | 0.91 |
| Membranophones/Struck Membranophones/Snare Drum, Modern 3::Snare4_HitSN | 6 | 3 (v2,v4,v5) | 2 | 0.99 |
| Membranophones/Struck Membranophones/Snare Drum, Modern 3::Snare4_Xstick | 2 | 1 (v2) | 2 | 0.9 |
| Membranophones/Struck Membranophones/Snare Drum, Modern 3::Snare4_rimshot | 4 | 2 (v2,v4) | 2 | 2.16 |
| Membranophones/Struck Membranophones/Snare Drum, Modern 3::Snare4_rollSN | 3 | 3 (v3,v4,v5) | 1 | 8.25 |
| Membranophones/Struck Membranophones/Snare Drum, Modern 3::Snare4_stick | 2 | 1 (v3) | 2 | 0.97 |
| Membranophones/Struck Membranophones/Snare Drum, Modern 3::Snare4_taps | 2 | 1 (v4) | 2 | 0.76 |
| Membranophones/Struck Membranophones/Snare Drum, Rope Tension/Hi::RopeSnare_hi_sn | 8 | 4 (vl1,vl2,vl3,vl4) | 2 | 2.13 |
| Membranophones/Struck Membranophones/Snare Drum, Rope Tension/Low::RopeSnare_low_ns | 6 | 3 (vl1,vl2,vl3) | 2 | 1.97 |
| Membranophones/Struck Membranophones/Snare Drum, Rope Tension/Low::RopeSnare_low_sn | 6 | 3 (vl1,vl2,vl3) | 2 | 2.53 |
| Membranophones/Struck Membranophones/Snare Drum, Rope Tension/Low::RopeSnare_low_tsn | 8 | 4 (vl1,vl2,vl3,vl4) | 2 | 1.85 |
| Membranophones/Struck Membranophones/Snare Drum, Rope Tension::RopeSnare_sidestick | 2 | 1 (vl2) | 2 | 1.3 |
| Membranophones/Struck Membranophones/Snare Drum, Rope Tension::RopeSnare_stick | 2 | 1 (vl1) | 2 | 1.05 |
| Membranophones/Struck Membranophones/Tom 1/Mallet::TomH_HitM | 6 | 3 (v2,v3,v4) | 2 | 2.62 |
| Membranophones/Struck Membranophones/Tom 1/Mallet::TomH_RollM | 2 | 2 (v1,v2) | 1 | 9.78 |
| Membranophones/Struck Membranophones/Tom 1/Stick::TomH_HitS | 6 | 3 (v2,v3,v4) | 2 | 2.52 |
| Membranophones/Struck Membranophones/Tom 1/Stick::TomH_RollS | 2 | 2 (v1,v2) | 1 | 10.32 |
| Membranophones/Struck Membranophones/Tom 1::TomH_rimFLS | 2 | 1 (single) | 2 | 1.39 |
| Membranophones/Struck Membranophones/Tom 1::TomH_rimS | 4 | 2 (v2,v4) | 2 | 1.45 |
| Membranophones/Struck Membranophones/Tom 2/Mallet::TomL_HitM | 6 | 3 (v2,v3,v4) | 2 | 2.38 |
| Membranophones/Struck Membranophones/Tom 2/Mallet::TomL_RollM | 2 | 2 (v1,v2) | 1 | 9.7 |
| Membranophones/Struck Membranophones/Tom 2/Stick::TomL_HitS | 6 | 3 (v2,v3,v4) | 2 | 3.02 |
| Membranophones/Struck Membranophones/Tom 2/Stick::TomL_RollS | 2 | 2 (v1,v2) | 1 | 9.32 |
| Membranophones/Struck Membranophones/Tom 2::TomL_rimFLS | 2 | 1 (single) | 2 | 1.43 |
| Membranophones/Struck Membranophones/Tom 2::TomL_rimS | 4 | 2 (v2,v4) | 2 | 1.44 |

### VSCO-2-CE / Keys

| Group (stroke) | Samples | Layers | RR | Len (s) |
|---|---|---|---|---|
| Keys/Organ/Loud::Rode_Man3Open | 21 | 1 (single) | 21 | 12.29 |
| Keys/Organ/Loud::Rode_Pedal | 11 | 1 (single) | 11 | 12.71 |
| Keys/Organ/Quiet::NT5_Man3Quiet_122 | 1 | 1 (single) | 1 | 11.55 |
| Keys/Organ/Quiet::NT5_Man3Quiet_125 | 1 | 1 (single) | 1 | 11.63 |
| Keys/Organ/Quiet::NT5_Man3Quiet_128 | 1 | 1 (single) | 1 | 12.16 |
| Keys/Organ/Quiet::NT5_Man3Quiet_131 | 1 | 1 (single) | 1 | 11.57 |
| Keys/Organ/Quiet::NT5_Man3Quiet_134 | 1 | 1 (single) | 1 | 12.49 |
| Keys/Organ/Quiet::NT5_Man3Quiet_137 | 1 | 1 (single) | 1 | 12.98 |
| Keys/Organ/Quiet::NT5_Man3Quiet_140 | 1 | 1 (single) | 1 | 12.13 |
| Keys/Organ/Quiet::NT5_Man3Quiet_143 | 1 | 1 (single) | 1 | 12.37 |
| Keys/Organ/Quiet::NT5_Man3Quiet_146 | 1 | 1 (single) | 1 | 12.14 |
| Keys/Organ/Quiet::NT5_Man3Quiet_149 | 1 | 1 (single) | 1 | 12.8 |
| Keys/Organ/Quiet::NT5_Man3Quiet_152 | 1 | 1 (single) | 1 | 12.26 |
| Keys/Organ/Quiet::NT5_Man3Quiet_155 | 1 | 1 (single) | 1 | 12.14 |
| Keys/Organ/Quiet::NT5_Man3Quiet_158 | 1 | 1 (single) | 1 | 12.15 |
| Keys/Organ/Quiet::NT5_Man3Quiet_161 | 1 | 1 (single) | 1 | 12.19 |
| Keys/Organ/Quiet::NT5_Man3Quiet_164 | 1 | 1 (single) | 1 | 12.06 |
| Keys/Organ/Quiet::NT5_Man3Quiet_167 | 1 | 1 (single) | 1 | 12.29 |
| Keys/Organ/Quiet::NT5_Man3Quiet_170 | 1 | 1 (single) | 1 | 12.27 |
| Keys/Organ/Quiet::NT5_Man3Quiet_173 | 1 | 1 (single) | 1 | 12.02 |
| Keys/Organ/Quiet::NT5_Man3Quiet_176 | 1 | 1 (single) | 1 | 11.73 |
| Keys/Organ/Quiet::NT5_Man3Quiet_179 | 1 | 1 (single) | 1 | 11.43 |
| Keys/Organ/Quiet::NT5_Man3Quiet_182 | 1 | 1 (single) | 1 | 11.99 |
| Keys/Organ/Quiet::NT5_PedalQuiet_064 | 1 | 1 (single) | 1 | 12.26 |
| Keys/Organ/Quiet::NT5_PedalQuiet_067 | 1 | 1 (single) | 1 | 11.99 |
| Keys/Organ/Quiet::NT5_PedalQuiet_070 | 1 | 1 (single) | 1 | 11.84 |
| Keys/Organ/Quiet::NT5_PedalQuiet_073 | 1 | 1 (single) | 1 | 11.68 |
| Keys/Organ/Quiet::NT5_PedalQuiet_076 | 1 | 1 (single) | 1 | 12.13 |
| Keys/Organ/Quiet::NT5_PedalQuiet_079 | 1 | 1 (single) | 1 | 12.09 |
| Keys/Organ/Quiet::NT5_PedalQuiet_082 | 1 | 1 (single) | 1 | 11.89 |
| Keys/Organ/Quiet::NT5_PedalQuiet_085 | 1 | 1 (single) | 1 | 12.04 |
| Keys/Organ/Quiet::NT5_PedalQuiet_088 | 1 | 1 (single) | 1 | 12.24 |
| Keys/Organ/Quiet::NT5_PedalQuiet_091 | 1 | 1 (single) | 1 | 11.9 |
| Keys/Organ/Quiet::NT5_PedalQuiet_094 | 1 | 1 (single) | 1 | 11.97 |
| Keys/Organ::Rode_Blower | 1 | 1 (single) | 1 | 37.17 |

### VSCO-2-CE / Miscellania Raw

| Group (stroke) | Samples | Layers | RR | Len (s) |
|---|---|---|---|---|
| Miscellania Raw/Misc 1::alien1 | 2 | 1 (ff) | 2 | 3.34 |
| Miscellania Raw/Misc 1::alien2 | 1 | 1 (pp) | 1 | 4.46 |
| Miscellania Raw/Misc 1::alien3 | 1 | 1 (single) | 1 | 5.3 |
| Miscellania Raw/Misc 1::alien4 | 1 | 1 (single) | 1 | 3.12 |
| Miscellania Raw/Misc 1::alien5 | 1 | 1 (single) | 1 | 3.52 |
| Miscellania Raw/Misc 1::alien6 | 1 | 1 (single) | 1 | 3.42 |
| Miscellania Raw/Misc 1::ambience1 | 1 | 1 (single) | 1 | 18.91 |
| Miscellania Raw/Misc 1::brick_scrape | 1 | 1 (single) | 1 | 1.14 |
| Miscellania Raw/Misc 1::brick_scrape2 | 1 | 1 (single) | 1 | 1.19 |
| Miscellania Raw/Misc 1::bubbles | 1 | 1 (single) | 1 | 2.86 |
| Miscellania Raw/Misc 1::bubbles2 | 1 | 1 (single) | 1 | 3.46 |
| Miscellania Raw/Misc 1::bubbles4 | 1 | 1 (single) | 1 | 2.11 |
| Miscellania Raw/Misc 1::chain_grind | 1 | 1 (single) | 1 | 1.01 |
| Miscellania Raw/Misc 1::chain_loop | 1 | 1 (single) | 1 | 2.26 |
| Miscellania Raw/Misc 1::chaingrindLoop | 1 | 1 (single) | 1 | 8.97 |
| Miscellania Raw/Misc 1::cymb_gong | 1 | 1 (single) | 1 | 7.19 |
| Miscellania Raw/Misc 1::cymb_gong2 | 1 | 1 (single) | 1 | 8.57 |
| Miscellania Raw/Misc 1::cymb_timp | 1 | 1 (single) | 1 | 0.79 |
| Miscellania Raw/Misc 1::cymb_timp2 | 1 | 1 (single) | 1 | 1.11 |
| Miscellania Raw/Misc 1::cymbgong | 1 | 1 (pp) | 1 | 2.92 |
| Miscellania Raw/Misc 1::cymbgong_weird | 1 | 1 (single) | 1 | 4.39 |
| Miscellania Raw/Misc 1::glass_break | 1 | 1 (single) | 1 | 0.68 |
| Miscellania Raw/Misc 1::glass_break2 | 1 | 1 (single) | 1 | 0.65 |
| Miscellania Raw/Misc 1::glass_break3 | 1 | 1 (single) | 1 | 0.77 |
| Miscellania Raw/Misc 1::glass_break4 | 1 | 1 (single) | 1 | 0.88 |
| Miscellania Raw/Misc 1::glass_break5 | 1 | 1 (single) | 1 | 0.92 |
| Miscellania Raw/Misc 1::glass_break6 | 1 | 1 (single) | 1 | 0.77 |
| Miscellania Raw/Misc 1::glass_break7 | 1 | 1 (single) | 1 | 1.28 |
| Miscellania Raw/Misc 1::glass_break8 | 1 | 1 (single) | 1 | 1.09 |
| Miscellania Raw/Misc 1::metal_hit1 | 1 | 1 (single) | 1 | 2.02 |
| Miscellania Raw/Misc 1::metal_hit10 | 1 | 1 (single) | 1 | 2.56 |
| Miscellania Raw/Misc 1::metal_hit11 | 1 | 1 (single) | 1 | 2.4 |
| Miscellania Raw/Misc 1::metal_hit13 | 1 | 1 (single) | 1 | 2.27 |
| Miscellania Raw/Misc 1::metal_hit14 | 1 | 1 (single) | 1 | 2.04 |
| Miscellania Raw/Misc 1::metal_hit2 | 1 | 1 (single) | 1 | 1.65 |
| Miscellania Raw/Misc 1::metal_hit3 | 1 | 1 (single) | 1 | 1.57 |
| Miscellania Raw/Misc 1::metal_hit4 | 1 | 1 (single) | 1 | 1.47 |
| Miscellania Raw/Misc 1::metal_hit5 | 1 | 1 (single) | 1 | 1.74 |
| Miscellania Raw/Misc 1::metal_hit6 | 1 | 1 (single) | 1 | 2.71 |
| Miscellania Raw/Misc 1::metal_hit7 | 1 | 1 (single) | 1 | 2.24 |
| Miscellania Raw/Misc 1::metal_hit8 | 1 | 1 (single) | 1 | 2.84 |
| Miscellania Raw/Misc 1::metal_hit9 | 1 | 1 (single) | 1 | 2.01 |
| Miscellania Raw/Misc 1::siren1 | 1 | 1 (single) | 1 | 3.86 |
| Miscellania Raw/Misc 1::siren2 | 1 | 1 (single) | 1 | 5.33 |
| Miscellania Raw/Misc 1::siren3 | 1 | 1 (single) | 1 | 8.24 |
| Miscellania Raw/Misc 1::siren4 | 1 | 1 (single) | 1 | 8.8 |
| Miscellania Raw/Misc 1::siren5 | 1 | 1 (single) | 1 | 7.96 |
| Miscellania Raw/Misc 1::timp_snare | 4 | 3 (ppp,pp,f) | 2 | 1.63 |
| Miscellania Raw/Misc 1::timpsnare | 5 | 4 (ppp,pp,mf,fff) | 2 | 1.33 |
| Miscellania Raw/Misc 1::timpsnare_tenor | 3 | 2 (ff,fff) | 2 | 1.17 |
| Miscellania Raw/Misc 1::timpsnare_tenor1 | 1 | 1 (single) | 1 | 1.14 |
| Miscellania Raw/Misc 1::timpsnare_tenor2 | 1 | 1 (single) | 1 | 0.44 |
| Miscellania Raw/Misc 1::vibraring1 | 1 | 1 (single) | 1 | 1.99 |
| Miscellania Raw/Misc 1::vibraring2 | 1 | 1 (single) | 1 | 1.68 |
| Miscellania Raw/Misc 1::vibraring3 | 1 | 1 (single) | 1 | 2.21 |
| Miscellania Raw/Misc 1::vibraring4 | 1 | 1 (single) | 1 | 2.4 |
| Miscellania Raw/Misc 1::zap1 | 1 | 1 (single) | 1 | 2.44 |
| Miscellania Raw/Misc 1::zap10 | 1 | 1 (single) | 1 | 1.83 |
| Miscellania Raw/Misc 1::zap11 | 1 | 1 (single) | 1 | 3.07 |
| Miscellania Raw/Misc 1::zap12 | 1 | 1 (single) | 1 | 3.13 |
| Miscellania Raw/Misc 1::zap13 | 1 | 1 (single) | 1 | 2.45 |
| Miscellania Raw/Misc 1::zap14 | 1 | 1 (single) | 1 | 2.51 |
| Miscellania Raw/Misc 1::zap2 | 1 | 1 (single) | 1 | 2.05 |
| Miscellania Raw/Misc 1::zap3 | 1 | 1 (single) | 1 | 2.55 |
| Miscellania Raw/Misc 1::zap4 | 1 | 1 (single) | 1 | 3.09 |
| Miscellania Raw/Misc 1::zap5 | 1 | 1 (single) | 1 | 2.01 |
| Miscellania Raw/Misc 1::zap6 | 1 | 1 (single) | 1 | 2.41 |
| Miscellania Raw/Misc 1::zap7 | 1 | 1 (single) | 1 | 2.14 |
| Miscellania Raw/Misc 1::zap8 | 1 | 1 (single) | 1 | 2.3 |
| Miscellania Raw/Misc 1::zap9 | 1 | 1 (single) | 1 | 1.97 |
| Miscellania Raw/Misc 2/NepaleseBells::fx | 1 | 1 (med) | 1 | 7.3 |
| Miscellania Raw/Misc 2/NepaleseBells::fx1_short | 11 | 1 (single) | 11 | 2.18 |
| Miscellania Raw/Misc 2/NepaleseBells::fx2_short | 7 | 1 (single) | 7 | 3.0 |
| Miscellania Raw/Misc 2/NepaleseBells::fx3_short | 4 | 1 (single) | 4 | 3.7 |
| Miscellania Raw/Misc 2/NepaleseBells::fx_long | 1 | 1 (single) | 1 | 16.47 |
| Miscellania Raw/Misc 2/NepaleseBells::fx_long2 | 1 | 1 (single) | 1 | 24.94 |
| Miscellania Raw/Misc 2/glock_glisses::glock_fx_down_chromatic_fast | 4 | 1 (single) | 4 | 6.97 |
| Miscellania Raw/Misc 2/glock_glisses::glock_fx_down_chromatic_slow | 3 | 1 (single) | 3 | 7.01 |
| Miscellania Raw/Misc 2/glock_glisses::glock_fx_down_pentatonic | 3 | 1 (med) | 3 | 6.52 |
| Miscellania Raw/Misc 2/glock_glisses::glock_fx_up_chromatic | 3 | 1 (med) | 3 | 7.01 |
| Miscellania Raw/Misc 2/glock_glisses::glock_fx_up_chromatic_fast | 2 | 1 (single) | 2 | 7.05 |
| Miscellania Raw/Misc 2/glock_glisses::glock_fx_up_chromatic_slow | 3 | 1 (single) | 3 | 7.01 |
| Miscellania Raw/Misc 2/glock_glisses::glock_fx_up_pentatonic | 2 | 1 (med) | 2 | 5.58 |
| Miscellania Raw/Misc 2::rtomtom_frame | 1 | 1 (single) | 1 | 8.13 |
| Miscellania Raw/Misc 2::rtomtom_frame2 | 1 | 1 (single) | 1 | 1.97 |
| Miscellania Raw/Misc 2::rtomtomframe_roll | 1 | 1 (single) | 1 | 13.21 |
| Miscellania Raw/Misc 2::sleighbell1_hit | 6 | 2 (quiet,loud) | 4 | 1.24 |
| Miscellania Raw/Misc 2::sleighbell1_shake1 | 1 | 1 (single) | 1 | 5.25 |
| Miscellania Raw/Misc 2::sleighbell2_hit | 3 | 1 (loud) | 3 | 1.56 |
| Miscellania Raw/Misc 2::sleighbell2_shake1 | 1 | 1 (single) | 1 | 6.3 |
| Miscellania Raw/Misc 2::spoons_fun | 1 | 1 (single) | 1 | 8.72 |
| Miscellania Raw/Misc 2::tamb2 | 4 | 1 (single) | 4 | 0.3 |
| Miscellania Raw/Misc 2::tamb2_rollFast | 1 | 1 (single) | 1 | 4.67 |
| Miscellania Raw/Misc 2::tamb2_rollSlow | 1 | 1 (single) | 1 | 2.89 |
| Miscellania Raw/Misc 2::tamb3 | 8 | 1 (single) | 8 | 0.33 |
| Miscellania Raw/Misc 2::tamb3_roll | 1 | 1 (single) | 1 | 11.5 |
| Miscellania Raw/Misc 2::tubaMP | 1 | 1 (single) | 1 | 0.56 |
| Miscellania Raw/Misc 2::tubaMP2 | 1 | 1 (single) | 1 | 0.58 |
| Miscellania Raw/Misc 2::tubaMP3 | 1 | 1 (single) | 1 | 0.55 |

### VSCO-2-CE / Percussion

| Group (stroke) | Samples | Layers | RR | Len (s) |
|---|---|---|---|---|
| Percussion/temp::Triangle3-Hit | 4 | 2 (v1,v2) | 2 | 9.47 |
| Percussion/temp::Triangle3-HitFM | 4 | 2 (v1,v2) | 2 | 0.85 |
| Percussion/temp::Triangle3-HitM | 4 | 2 (v1,v2) | 2 | 1.36 |
| Percussion/temp::Triangle3-Roll | 1 | 1 (v2) | 1 | 39.38 |
| Percussion/temp::Triangle6-Hit | 4 | 2 (v1,v2) | 2 | 2.26 |
| Percussion/temp::Triangle6-HitFM | 4 | 2 (v1,v2) | 2 | 1.02 |
| Percussion/temp::Triangle6-HitM | 4 | 2 (v1,v2) | 2 | 1.05 |
| Percussion/temp::Triangle6-Roll | 1 | 1 (v2) | 1 | 22.97 |
| Percussion/temp::Tumba-HitN | 6 | 3 (v1,v2,v3) | 2 | 0.71 |
| Percussion/temp::Tumba-Tap1 | 2 | 1 (v1) | 2 | 0.5 |
| Percussion/temp::timp-snare | 1 | 1 (f) | 1 | 2.31 |
| Percussion/temp::timpsnare | 3 | 3 (ppp,pp,mf) | 1 | 0.79 |
| Percussion/temp::timpsnaretenor | 3 | 3 (f,ff,fff) | 1 | 1.14 |
| Percussion/temp::vibraring | 2 | 1 (v1) | 2 | 2.04 |
| Percussion/temp::zap1 | 1 | 1 (v1) | 1 | 1.83 |
| Percussion/temp::zap2 | 1 | 1 (v1) | 1 | 2.05 |
| Percussion/temp::zap3 | 1 | 1 (v1) | 1 | 2.45 |
| Percussion/temp::zap4 | 1 | 1 (v1) | 1 | 2.41 |
| Percussion::Anvil_Hit1 | 3 | 3 (v1,v2,v3) | 1 | 1.69 |
| Percussion::BDrumNewhit | 14 | 7 (v1,v2,v3,v4,v5,v6,v7) | 2 | 2.99 |
| Percussion::BellTree_Stroke1 | 1 | 1 (v1) | 1 | 4.56 |
| Percussion::BellTree_Stroke2 | 1 | 1 (v1) | 1 | 5.13 |
| Percussion::BellTree_Stroke3 | 1 | 1 (v1) | 1 | 5.9 |
| Percussion::BellTree_Stroke4 | 1 | 1 (v1) | 1 | 5.95 |
| Percussion::BrakeDrum1_Hammer | 3 | 3 (v1,v2,v3) | 1 | 1.7 |
| Percussion::Claves1_Hit | 6 | 3 (v1,v2,v3) | 2 | 1.11 |
| Percussion::Conga-HitN | 6 | 3 (v1,v2,v3) | 2 | 0.9 |
| Percussion::Conga-Tap1 | 2 | 1 (v1) | 2 | 0.42 |
| Percussion::Cowbell1_Hit | 8 | 4 (v1,v2,v3,v4) | 2 | 1.09 |
| Percussion::Guiro-Fast | 1 | 1 (v1) | 1 | 1.51 |
| Percussion::Guiro-Hit | 2 | 1 (v1) | 2 | 1.34 |
| Percussion::Guiro-M | 1 | 1 (v1) | 1 | 1.88 |
| Percussion::Guiro-Slow | 1 | 1 (v1) | 1 | 2.64 |
| Percussion::LogDrumHi_MedM | 6 | 3 (v1,v2,v3) | 2 | 1.53 |
| Percussion::LogDrumLo_MedM | 6 | 3 (v1,v2,v3) | 2 | 1.29 |
| Percussion::Quinto-HitN | 6 | 3 (v1,v2,v3) | 2 | 0.89 |
| Percussion::Quinto-Tap1 | 2 | 1 (v1) | 2 | 0.67 |
| Percussion::Ratchet1-Crank | 2 | 1 (v1) | 2 | 1.63 |
| Percussion::Ratchet1-Fast | 1 | 1 (v1) | 1 | 7.07 |
| Percussion::Ratchet1-Slow | 1 | 1 (v1) | 1 | 8.95 |
| Percussion::Sleighbells_Hit | 2 | 1 (v1) | 2 | 2.48 |
| Percussion::Snare2-HitNS | 8 | 4 (v1,v3,v5,v6) | 2 | 0.93 |
| Percussion::Snare2-HitSN | 10 | 5 (v1,v3,v5,v7,v9) | 2 | 1.46 |
| Percussion::Snare2-rollNS | 3 | 3 (v1,v3,v5) | 1 | 6.86 |
| Percussion::Snare2-rollSN | 3 | 3 (v1,v3,v5) | 1 | 11.14 |
| Percussion::Snare2-taps | 8 | 4 (v1,v2,v3,v4) | 2 | 1.06 |
| Percussion::Tamb1-Hit | 4 | 2 (v1,v2) | 2 | 1.69 |
| Percussion::Tamb1-Roll | 3 | 3 (v1,v2,v3) | 1 | 10.49 |
| Percussion::Tamb1-Shake | 2 | 1 (v1) | 2 | 1.41 |
| Percussion::Triangle3-Hit | 4 | 2 (v1,v2) | 2 | 9.47 |
| Percussion::Triangle3-HitFM | 4 | 2 (v1,v2) | 2 | 0.85 |
| Percussion::Triangle3-HitM | 4 | 2 (v1,v2) | 2 | 1.36 |
| Percussion::Triangle3-Roll | 1 | 1 (v2) | 1 | 39.38 |
| Percussion::Triangle6-Hit | 4 | 2 (v1,v2) | 2 | 2.26 |
| Percussion::Triangle6-HitFM | 4 | 2 (v1,v2) | 2 | 1.02 |
| Percussion::Triangle6-HitM | 4 | 2 (v1,v2) | 2 | 1.05 |
| Percussion::Triangle6-Roll | 1 | 1 (v2) | 1 | 22.97 |
| Percussion::Tumba-HitN | 6 | 3 (v1,v2,v3) | 2 | 0.71 |
| Percussion::Tumba-Tap1 | 2 | 1 (v1) | 2 | 0.5 |
| Percussion::alien1 | 2 | 2 (pp,ff) | 1 | 3.34 |
| Percussion::alien2 | 1 | 1 (f) | 1 | 3.12 |
| Percussion::alien3 | 1 | 1 (f) | 1 | 3.42 |
| Percussion::bassdrum_rub1 | 1 | 1 (v1) | 1 | 4.61 |
| Percussion::bassdrum_rub2 | 1 | 1 (v1) | 1 | 11.19 |
| Percussion::bassdrum_rub3 | 1 | 1 (v1) | 1 | 9.68 |
| Percussion::bassdrum_rub4 | 1 | 1 (v1) | 1 | 7.34 |
| Percussion::cymbal-crash1 | 8 | 4 (pp,mp,mf,ff) | 2 | 8.94 |
| Percussion::cymbal-crashshort | 1 | 1 (v1) | 1 | 1.9 |
| Percussion::gongHit | 4 | 4 (p,mf,f,fff) | 1 | 30.11 |
| Percussion::gongscrape | 2 | 2 (pp,mf) | 1 | 7.44 |
| Percussion::susCymb1-bow-1 | 1 | 1 (single) | 1 | 16.29 |
| Percussion::susCymb1-bow-2 | 1 | 1 (single) | 1 | 2.64 |
| Percussion::susCymb1-bow-3 | 1 | 1 (single) | 1 | 11.46 |
| Percussion::susCymb1-bow-4 | 1 | 1 (single) | 1 | 7.78 |
| Percussion::susCymb1-cresc-Long | 1 | 1 (v1) | 1 | 16.96 |
| Percussion::susCymb1-cresc-Median | 1 | 1 (v1) | 1 | 12.99 |
| Percussion::susCymb1-cresc-Short | 1 | 1 (v1) | 1 | 12.03 |
| Percussion::susCymb1-hit | 8 | 4 (pp,mp,f,fff) | 2 | 12.13 |
| Percussion::susCymb1-hit-bell | 3 | 3 (pp,mf,fff) | 1 | 7.25 |
| Percussion::susCymb1-hitstick | 8 | 4 (pp,mp,f,fff) | 2 | 8.36 |
| Percussion::susCymb1-scrape1 | 1 | 1 (v1) | 1 | 7.55 |
| Percussion::susCymb1-scrape2 | 1 | 1 (v1) | 1 | 9.12 |
| Percussion::timp-snare | 1 | 1 (f) | 1 | 2.31 |
| Percussion::timpsnare | 3 | 3 (ppp,pp,mf) | 1 | 0.79 |
| Percussion::timpsnaretenor | 3 | 3 (f,ff,fff) | 1 | 1.14 |
| Percussion::vibraring | 2 | 1 (v1) | 2 | 2.04 |
| Percussion::zap1 | 1 | 1 (v1) | 1 | 1.83 |
| Percussion::zap2 | 1 | 1 (v1) | 1 | 2.05 |
| Percussion::zap3 | 1 | 1 (v1) | 1 | 2.45 |
| Percussion::zap4 | 1 | 1 (v1) | 1 | 2.41 |

### VSCO-2-CE / VSCO 1 Percussion

| Group (stroke) | Samples | Layers | RR | Len (s) |
|---|---|---|---|---|
| VSCO 1 Percussion/drums/bass::bdrum | 13 | 7 (ppp,pp,p,mp,f,ff,fff) | 3 | 5.58 |
| VSCO 1 Percussion/drums/bass::bdrum2 | 4 | 2 (ppp,pp) | 2 | 3.37 |
| VSCO 1 Percussion/drums/bass::bdrum3 | 4 | 4 (ppp,p,mp,fff) | 1 | 7.08 |
| VSCO 1 Percussion/drums/bass::bdrum_muted | 11 | 6 (ppp,pp,mp,mf,ff,fff) | 3 | 2.24 |
| VSCO 1 Percussion/drums/bass::bdrum_roll-quietest | 1 | 1 (single) | 1 | 13.89 |
| VSCO 1 Percussion/drums/bass::bdrum_roll1 | 1 | 1 (single) | 1 | 10.16 |
| VSCO 1 Percussion/drums/bass::bdrum_roll_long1 | 1 | 1 (single) | 1 | 22.84 |
| VSCO 1 Percussion/drums/bass::bdrum_roll_quieter | 1 | 1 (single) | 1 | 27.29 |
| VSCO 1 Percussion/drums/bass::bdrum_roll_short | 2 | 1 (single) | 2 | 7.05 |
| VSCO 1 Percussion/drums/bass::bdrum_special_sidehit | 1 | 1 (single) | 1 | 0.86 |
| VSCO 1 Percussion/drums/other/Bongos::HighBongo1 | 1 | 1 (single) | 1 | 1.22 |
| VSCO 1 Percussion/drums/other/Bongos::HighBongo2 | 1 | 1 (single) | 1 | 1.14 |
| VSCO 1 Percussion/drums/other/Bongos::LowBongo1 | 1 | 1 (single) | 1 | 1.14 |
| VSCO 1 Percussion/drums/other/Bongos::LowBongo2 | 1 | 1 (single) | 1 | 1.08 |
| VSCO 1 Percussion/drums/other/ethnic/congo/muted::ethnicHigh_hit | 3 | 3 (pp,mp,f) | 1 | 0.95 |
| VSCO 1 Percussion/drums/other/ethnic/congo/muted::ethnicLow_hit | 3 | 3 (pp,mp,f) | 1 | 0.66 |
| VSCO 1 Percussion/drums/other/ethnic/congo/open::ethnicHighOpen_hit | 2 | 1 (f) | 2 | 0.91 |
| VSCO 1 Percussion/drums/other/ethnic/congo/open::ethnicLowOpen_hit | 10 | 3 (pp,mp,f) | 4 | 0.73 |
| VSCO 1 Percussion/drums/other/ethnic/giant/hand::EthnicLargeHand_brush | 1 | 1 (single) | 1 | 0.72 |
| VSCO 1 Percussion/drums/other/ethnic/giant/hand::EthnicLargeHand_hit | 16 | 6 (ppp,pp,p,mp,f,ff) | 4 | 0.9 |
| VSCO 1 Percussion/drums/other/ethnic/giant/mallet::EthnicLargeMallet_hit | 5 | 4 (pp,mf,f,ff) | 2 | 1.5 |
| VSCO 1 Percussion/drums/other/ethnic/giant/sticks::EthnicLargeSticks_hit | 10 | 7 (ppp,pp,p,mp,mf,f,fff) | 2 | 1.2 |
| VSCO 1 Percussion/drums/other/ethnic/giant::EthnicLargeStick_rimshot | 3 | 1 (single) | 3 | 0.66 |
| VSCO 1 Percussion/drums/snare/OldSnare::snare | 14 | 5 (pp,p,mf,f,ff) | 4 | 0.25 |
| VSCO 1 Percussion/drums/snare/OldSnare::snare_rim | 1 | 1 (single) | 1 | 0.25 |
| VSCO 1 Percussion/drums/snare/drum1::snare1 | 16 | 8 (pppp,ppp,pp,p,mp,f,ff,fff) | 3 | 0.54 |
| VSCO 1 Percussion/drums/snare/drum1::snare1_click | 1 | 1 (single) | 1 | 0.28 |
| VSCO 1 Percussion/drums/snare/drum1::snare1_click2 | 1 | 1 (single) | 1 | 0.28 |
| VSCO 1 Percussion/drums/snare/drum1::snare1_click3 | 1 | 1 (single) | 1 | 0.29 |
| VSCO 1 Percussion/drums/snare/drum1::snare1_click4 | 1 | 1 (single) | 1 | 0.22 |
| VSCO 1 Percussion/drums/snare/drum1::snare1_nosnare | 14 | 7 (ppp,pp,mp,mf,f,ff,fff) | 3 | 0.51 |
| VSCO 1 Percussion/drums/snare/drum1::snare1_rim | 1 | 1 (fff) | 1 | 1.11 |
| VSCO 1 Percussion/drums/snare/drum1::snare1_rimshot | 3 | 3 (mf,f,fff) | 1 | 0.52 |
| VSCO 1 Percussion/drums/snare/drum1::snare1_snare | 1 | 1 (mp) | 1 | 0.49 |
| VSCO 1 Percussion/drums/snare/drum1::snare1_snare2 | 1 | 1 (mp) | 1 | 0.49 |
| VSCO 1 Percussion/drums/snare/drum2::sfx_click | 1 | 1 (single) | 1 | 0.2 |
| VSCO 1 Percussion/drums/snare/drum2::snare2 | 17 | 9 (pppp,ppp,pp,p,mp,mf,f,ff,fff) | 3 | 0.41 |
| VSCO 1 Percussion/drums/snare/drum2::snare2_click | 1 | 1 (single) | 1 | 0.38 |
| VSCO 1 Percussion/drums/snare/drum2::snare2_nosnare | 12 | 8 (pppp,ppp,pp,p,mf,f,ff,fff) | 3 | 0.47 |
| VSCO 1 Percussion/drums/snare/drum2::snare2_nosnare_roll | 1 | 1 (ff) | 1 | 3.28 |
| VSCO 1 Percussion/drums/snare/drum2::snare2_rimshot | 4 | 3 (mf,f,ff) | 2 | 0.61 |
| VSCO 1 Percussion/drums/snare/drum3_marching::snare3 | 13 | 6 (ppp,pp,p,mp,f,fff) | 4 | 0.4 |
| VSCO 1 Percussion/drums/snare/drum3_marching::snare3_click | 2 | 1 (single) | 2 | 0.31 |
| VSCO 1 Percussion/drums/snare/drum3_marching::snare3_rimshot | 2 | 2 (f,ff) | 1 | 0.46 |
| VSCO 1 Percussion/drums/tenor/tenor_higher::tenorH | 22 | 7 (pp,p,mp,mf,f,ff,fff) | 6 | 1.89 |
| VSCO 1 Percussion/drums/tenor/tenor_lower::tenor | 19 | 7 (ppp,pp,mp,mf,f,ff,fff) | 4 | 1.66 |
| VSCO 1 Percussion/varMetal/Cymbals/clash::crash_hit_loose | 5 | 4 (pp,mp,ff,fff) | 2 | 7.67 |
| VSCO 1 Percussion/varMetal/Cymbals/clash::crash_hit_tight | 1 | 1 (ff) | 1 | 2.97 |
| VSCO 1 Percussion/varMetal/Cymbals/clash::crash_hit_verytight | 1 | 1 (ff) | 1 | 4.5 |
| VSCO 1 Percussion/varMetal/Cymbals/susp::susp_FX_scrape | 3 | 1 (single) | 3 | 3.43 |
| VSCO 1 Percussion/varMetal/Cymbals/susp::susp_FX_scrape_continuous | 1 | 1 (single) | 1 | 25.04 |
| VSCO 1 Percussion/varMetal/Cymbals/susp::susp_FX_scrape_rapid | 1 | 1 (single) | 1 | 4.92 |
| VSCO 1 Percussion/varMetal/Cymbals/susp::susp_hit_hardmall | 3 | 3 (mf,f,fff) | 1 | 13.52 |
| VSCO 1 Percussion/varMetal/Cymbals/susp::susp_hit_metal | 1 | 1 (single) | 1 | 3.18 |
| VSCO 1 Percussion/varMetal/Cymbals/susp::susp_hit_metal_2 | 5 | 4 (mf,f,ff,fff) | 2 | 5.68 |
| VSCO 1 Percussion/varMetal/Cymbals/susp::susp_hit_softmall | 4 | 4 (p,mp,f,ff) | 1 | 11.65 |
| VSCO 1 Percussion/varMetal/Cymbals/susp::susp_hit_softmall_roll1 | 1 | 1 (single) | 1 | 8.04 |
| VSCO 1 Percussion/varMetal/Cymbals/susp::susp_hit_softmall_roll2_cresc | 1 | 1 (single) | 1 | 9.63 |
| VSCO 1 Percussion/varMetal/Cymbals/susp::susp_hit_softmall_roll3 | 1 | 1 (ff) | 1 | 16.59 |
| VSCO 1 Percussion/varMetal/Cymbals/susp::susp_hit_softmall_roll4_long | 1 | 1 (fff) | 1 | 15.93 |
| VSCO 1 Percussion/varMetal/Cymbals/susp::susp_hit_softmall_roll5_long | 1 | 1 (p) | 1 | 22.07 |
| VSCO 1 Percussion/varMetal/Cymbals/susp::susp_hit_woodmall | 4 | 4 (p,mp,mf,f) | 1 | 7.32 |
| VSCO 1 Percussion/varMetal/Cymbals/susp::susp_hit_woodmall_roll_cresc | 1 | 1 (single) | 1 | 7.99 |
| VSCO 1 Percussion/varMetal/Cymbals/susp::susp_hit_woodmall_roll_fx | 1 | 1 (single) | 1 | 6.91 |
| VSCO 1 Percussion/varMetal/Gong::gong_hit | 13 | 10 (pppp,ppp,pp,p,mp,mp-mf,mf,f,ff,fff) | 3 | 20.44 |
| VSCO 1 Percussion/varMetal/Gong::gong_hit_hard | 3 | 3 (p,mp,ff) | 1 | 19.21 |
| VSCO 1 Percussion/varMetal/Gong::gong_hit_hard2 | 1 | 1 (p) | 1 | 20.26 |
| VSCO 1 Percussion/varMetal/Gong::gong_roll_f | 1 | 1 (medium) | 1 | 27.69 |
| VSCO 1 Percussion/varMetal/Gong::gong_roll_ff | 1 | 1 (medium) | 1 | 22.36 |
| VSCO 1 Percussion/varMetal/Gong::gong_roll_long | 2 | 2 (f,ff) | 1 | 28.54 |
| VSCO 1 Percussion/varMetal/Gong::gong_scrape | 3 | 1 (single) | 3 | 6.34 |
| VSCO 1 Percussion/varMetal/Gong::gong_smack | 3 | 1 (single) | 3 | 10.17 |
| VSCO 1 Percussion/varMetal/Gong::gong_smack_light1 | 1 | 1 (single) | 1 | 2.65 |
| VSCO 1 Percussion/varMetal/Gong::gong_smack_low | 1 | 1 (single) | 1 | 8.76 |
| VSCO 1 Percussion/varMetal/triangle/1::triangle1_hit | 2 | 2 (pp,mp) | 1 | 6.64 |
| VSCO 1 Percussion/varMetal/triangle/1::triangle1_hit_muted | 1 | 1 (pp) | 1 | 2.37 |
| VSCO 1 Percussion/varMetal/triangle/1::triangle1_hit_muted1 | 1 | 1 (mp) | 1 | 2.46 |
| VSCO 1 Percussion/varMetal/triangle/1::triangle1_hit_muted2 | 1 | 1 (mp) | 1 | 2.37 |
| VSCO 1 Percussion/varMetal/triangle/1::triangle1_hit_muted3 | 1 | 1 (mp) | 1 | 2.56 |
| VSCO 1 Percussion/varMetal/triangle/1::triangle1_hit_pt2 | 1 | 1 (mf) | 1 | 9.35 |
| VSCO 1 Percussion/varMetal/triangle/1::triangle1_hit_pt3 | 1 | 1 (mp) | 1 | 9.99 |
| VSCO 1 Percussion/varMetal/triangle/1::triangle1_roll | 1 | 1 (single) | 1 | 13.05 |
| VSCO 1 Percussion/varMetal/triangle/2::triangle2_hit | 4 | 2 (p,mp) | 2 | 5.8 |
| VSCO 1 Percussion/varMetal/triangle/2::triangle2_roll | 1 | 1 (single) | 1 | 11.61 |
| VSCO 1 Percussion/varMetal/triangle/3::triangle3_hit | 5 | 4 (pp,p,mp,mf) | 2 | 3.11 |
| VSCO 1 Percussion/varMetal/triangle/3::triangle3_hit_pt2 | 1 | 1 (mp) | 1 | 5.06 |
| VSCO 1 Percussion/varMetal/triangle/3::triangle3_hit_pt3 | 1 | 1 (mp) | 1 | 4.39 |
| VSCO 1 Percussion/varMetal/triangle/3::triangle3_roll | 1 | 1 (single) | 1 | 10.69 |
| VSCO 1 Percussion/varMetal/triangle/4::triangle4_hit | 3 | 2 (mp,mf) | 2 | 6.37 |
| VSCO 1 Percussion/varMetal/triangle/4::triangle4_roll1 | 1 | 1 (single) | 1 | 8.77 |
| VSCO 1 Percussion/varMetal/various::Fing_Cymb | 1 | 1 (single) | 1 | 6.34 |
| VSCO 1 Percussion/varMetal/various::agogoBell | 2 | 2 (mf,f) | 1 | 1.63 |
| VSCO 1 Percussion/varMetal/various::agogoBell2 | 3 | 2 (mp,mf) | 2 | 1.29 |
| VSCO 1 Percussion/varMetal/various::agogoBell3 | 5 | 2 (f,ff) | 3 | 1.2 |
| VSCO 1 Percussion/varMetal/various::bell_tree_metalscrape1 | 1 | 1 (single) | 1 | 3.52 |
| VSCO 1 Percussion/varMetal/various::bell_tree_scrape1 | 1 | 1 (single) | 1 | 2.33 |
| VSCO 1 Percussion/varMetal/various::bell_tree_scrape2 | 1 | 1 (single) | 1 | 4.4 |
| VSCO 1 Percussion/varMetal/various::bell_tree_scrape3 | 1 | 1 (single) | 1 | 4.44 |
| VSCO 1 Percussion/varMetal/various::bell_tree_woodscrape1 | 1 | 1 (single) | 1 | 3.7 |
| VSCO 1 Percussion/varMetal/various::brake | 4 | 3 (mp,mf,fff) | 2 | 1.79 |
| VSCO 1 Percussion/varMetal/various::cabasa | 6 | 1 (single) | 6 | 0.8 |
| VSCO 1 Percussion/varMetal/various::cabasa_roll1 | 1 | 1 (single) | 1 | 2.05 |
| VSCO 1 Percussion/varMetal/various::cabasa_roll2 | 1 | 1 (single) | 1 | 3.52 |
| VSCO 1 Percussion/varMetal/various::cowbell | 6 | 3 (mf,ff,fff) | 2 | 1.95 |
| VSCO 1 Percussion/varMetal/various::flexatone1 | 1 | 1 (single) | 1 | 3.8 |
| VSCO 1 Percussion/varMetal/various::flexatone2 | 1 | 1 (single) | 1 | 3.56 |
| VSCO 1 Percussion/varMetal/various::flexatone_extralong | 1 | 1 (single) | 1 | 12.49 |
| VSCO 1 Percussion/varMetal/various::flexatone_fast | 1 | 1 (single) | 1 | 4.32 |
| VSCO 1 Percussion/varMetal/various::flexatone_long | 1 | 1 (single) | 1 | 7.82 |
| VSCO 1 Percussion/varMetal/various::flexatone_long2 | 1 | 1 (single) | 1 | 8.96 |
| VSCO 1 Percussion/varMetal/various::flexatone_slap1 | 1 | 1 (single) | 1 | 1.01 |
| VSCO 1 Percussion/varMetal/various::flexatone_slap2 | 1 | 1 (single) | 1 | 1.31 |
| VSCO 1 Percussion/varMetal/various::sleighbell1_hit | 6 | 2 (quiet,loud) | 4 | 1.24 |
| VSCO 1 Percussion/varMetal/various::sleighbell1_shake1 | 1 | 1 (single) | 1 | 5.25 |
| VSCO 1 Percussion/varMetal/various::sleighbell2_hit | 3 | 1 (loud) | 3 | 1.56 |
| VSCO 1 Percussion/varMetal/various::sleighbell2_shake1 | 1 | 1 (single) | 1 | 6.3 |
| VSCO 1 Percussion/varMetal/various::windchimes_asc1 | 1 | 1 (single) | 1 | 7.76 |
| VSCO 1 Percussion/varMetal/various::windchimes_desc1 | 1 | 1 (single) | 1 | 9.87 |
| VSCO 1 Percussion/varMetal/various::windchimes_fastAsc1 | 1 | 1 (single) | 1 | 13.32 |
| VSCO 1 Percussion/varMetal/various::windchimes_random | 1 | 1 (single) | 1 | 21.64 |
| VSCO 1 Percussion/varMetal/various::windchimes_slowAsc1 | 1 | 1 (single) | 1 | 11.22 |
| VSCO 1 Percussion/varMetal/various::windchimes_slowDesc1 | 1 | 1 (single) | 1 | 10.73 |
| VSCO 1 Percussion/varWood/Camo's Shaker::shake1 | 1 | 1 (single) | 1 | 0.18 |
| VSCO 1 Percussion/varWood/Camo's Shaker::shake2 | 1 | 1 (single) | 1 | 0.19 |
| VSCO 1 Percussion/varWood/Camo's Shaker::shake3 | 1 | 1 (single) | 1 | 0.25 |
| VSCO 1 Percussion/varWood/Camo's Shaker::shake4 | 1 | 1 (single) | 1 | 0.16 |
| VSCO 1 Percussion/varWood/Camo's Shaker::shake5 | 1 | 1 (single) | 1 | 0.16 |
| VSCO 1 Percussion/varWood/Camo's Shaker::shake6 | 1 | 1 (single) | 1 | 0.27 |
| VSCO 1 Percussion/varWood/Camo's Shaker::shake7 | 1 | 1 (single) | 1 | 0.23 |
| VSCO 1 Percussion/varWood/Camo's Shaker::shake8 | 1 | 1 (single) | 1 | 0.16 |
| VSCO 1 Percussion/varWood/log_drum::slitdrum0 | 11 | 3 (ppp,mp,ff) | 4 | 0.33 |
| VSCO 1 Percussion/varWood/log_drum::slitdrum1 | 12 | 3 (ppp,mp,ff) | 4 | 0.36 |
| VSCO 1 Percussion/varWood/log_drum::slitdrum2 | 12 | 3 (ppp,mp,ff) | 4 | 0.33 |
| VSCO 1 Percussion/varWood/log_drum::slitdrum3 | 12 | 3 (p,mp,ff) | 4 | 0.37 |
| VSCO 1 Percussion/varWood::claves | 6 | 4 (pp,mp,mf,ff) | 3 | 0.45 |
| VSCO 1 Percussion/varWood::guiro_long | 1 | 1 (single) | 1 | 0.58 |
| VSCO 1 Percussion/varWood::guiro_long2 | 1 | 1 (single) | 1 | 0.96 |
| VSCO 1 Percussion/varWood::guiro_short | 1 | 1 (single) | 1 | 0.35 |
| VSCO 1 Percussion/varWood::guiro_short2 | 1 | 1 (single) | 1 | 0.52 |
| VSCO 1 Percussion/varWood::guiro_short3 | 1 | 1 (single) | 1 | 0.43 |
| VSCO 1 Percussion/varWood::guiro_short4 | 1 | 1 (single) | 1 | 0.43 |
| VSCO 1 Percussion/varWood::guiro_short5 | 1 | 1 (single) | 1 | 0.4 |
| VSCO 1 Percussion/varWood::guiro_superlong | 1 | 1 (single) | 1 | 0.98 |
| VSCO 1 Percussion/varWood::gurio_long4 | 1 | 1 (single) | 1 | 0.66 |
| VSCO 1 Percussion/varWood::maraca1 | 1 | 1 (single) | 1 | 0.53 |
| VSCO 1 Percussion/varWood::maraca2 | 1 | 1 (single) | 1 | 0.37 |
| VSCO 1 Percussion/varWood::maraca3 | 1 | 1 (single) | 1 | 0.32 |
| VSCO 1 Percussion/varWood::maraca4 | 1 | 1 (single) | 1 | 0.29 |
| VSCO 1 Percussion/varWood::maraca5 | 1 | 1 (single) | 1 | 0.28 |
| VSCO 1 Percussion/varWood::maraca_shake | 1 | 1 (single) | 1 | 6.93 |
| VSCO 1 Percussion/varWood::ratchet1 | 1 | 1 (single) | 1 | 3.77 |
| VSCO 1 Percussion/varWood::ratchet2 | 1 | 1 (single) | 1 | 13.5 |
| VSCO 1 Percussion/varWood::slapstick | 2 | 1 (quiet) | 2 | 0.27 |
| VSCO 1 Percussion/varWood::slapstick1 | 1 | 1 (single) | 1 | 1.31 |
| VSCO 1 Percussion/varWood::slapstick2 | 1 | 1 (single) | 1 | 0.7 |
| VSCO 1 Percussion/varWood::slapstick3 | 1 | 1 (single) | 1 | 0.67 |
| VSCO 1 Percussion/varWood::tambourine_Down | 1 | 1 (single) | 1 | 0.6 |
| VSCO 1 Percussion/varWood::tambourine_down | 6 | 1 (single) | 6 | 0.58 |
| VSCO 1 Percussion/varWood::tambourine_shake | 1 | 1 (single) | 1 | 7.34 |
| VSCO 1 Percussion/varWood::tambourine_up | 7 | 1 (single) | 7 | 0.29 |
| VSCO 1 Percussion/varWood::vibraslap1 | 1 | 1 (single) | 1 | 2.88 |
| VSCO 1 Percussion/varWood::vibraslap2 | 1 | 1 (single) | 1 | 3.51 |
| VSCO 1 Percussion/varWood::vibraslap3 | 1 | 1 (single) | 1 | 2.87 |
| VSCO 1 Percussion/varWood::vibraslap4 | 1 | 1 (single) | 1 | 2.36 |
| VSCO 1 Percussion/varWood::wood_click | 7 | 4 (pp,mp,f,ff) | 3 | 0.51 |
| VSCO 1 Percussion/varWood::wood_click2 | 1 | 1 (mp) | 1 | 1.4 |
| VSCO 1 Percussion/varWood::wood_click3 | 2 | 1 (loud) | 2 | 0.82 |

