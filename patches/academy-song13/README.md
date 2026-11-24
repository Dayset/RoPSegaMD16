# academy-song13 — soften the Academy music (song 13)

The Academy classroom (destination 156, Buc's classroom) plays **song 13**
(ROM `$0F6844`, 241.45 s loop). It was harsh by design: only two channels
carry notes — ch2, the melody at a median 881 Hz, and ch5, a piercing voice
at a median 4,191 Hz — with no bass voice and no drums at all. Song 11 is
the Knights Guild theme, not the Academy; an earlier fix built on song 11
by mistake and was discarded.

## What the fix does (v4, approved 2026-11-24)

Built in four rounds, all in `fix_song13_v4.py`, which reads
`rop-original.gen` and writes `rop-academy-fix13-v4.gen`
(MD5 `97e12dccbbec650a0067190a5aa7cf0c`):

- **v1.** Bass on ch4: ch2's line two octaves down (140 notes, vel 110).
- **v2.** ch5 down one octave (416 events) + ch5 velocity 124 → 80.
  Dayset: still harsh — the octave moved the notes, not the harmonics.
- **v3.** Soften the instruments (FM timbre): feedback FB 7 → 2 on both
  lead voices, modulator total levels +8 (~6 dB quieter), ch2 attack
  31 → 24. Dayset: getting better, one more softening on top?
- **v4.** Modulator multiples to 1 on both voices (ch2 op1 12 → 1,
  op2 15 → 1; ch5 op1 5 → 1, op3 2 → 1). Detune left alone; carriers
  untouched. **Dayset: APPROVED 2026-11-24.**

## Why private copies

Song 13's instruments are **shared**: voice 14 (ch2) is used by songs 5,
12, 13, 14, 15; voice 16 (ch5) by songs 5, 11, 12, 13, 14, 15. In-place
edits would change five other songs. The fix instead writes softened
copies into unused voice slots 15 (ch2) and 17 (ch5) and repoints song
13's `$CX` at them (2 bytes, size-neutral). The shared voices are
provably untouched. Only the operator params (`$0C–$23`) are copied —
each block's `$00–$0B` header belongs to the previous voice.

## Metrics (full loop, 48 kHz native decode, 1 s windows, mean power spectrum)

| metric | original | v1 | v2 | v3 | v4 |
|---|---|---|---|---|---|
| p90 | 2,355 Hz | 2,355 Hz | 2,354 Hz | 2,096 Hz | **1,048 Hz** |
| median | 989 Hz | 659 Hz | 525 Hz | 525 Hz | 495 Hz |
| <300 Hz | 15.6% | 28.4% | 28.1% | 26.2% | 31.1% |
| 1–4 kHz | — | — | 24.2% | 17.5% | 11.3% |

Loop length exactly unchanged (14,487 ticks); seek +10120; the v4-vs-v3
ROM difference is exactly 9 bytes. The tune is intact (median moved
only ~30 Hz from v3 — a spectral-shape effect; the carriers, and
therefore the pitch, are untouched).

Caveat: MULT 1 is the floor of this lever — the song is now much darker.
If it ever sounds too plain rather than soft, the remaining levers are
ch2 velocity scaling or thinning the melody, not more MULT.

## Build

```sh
cp "Rings of Power (USA, Europe).gen" patches/academy-song13/rop-original.gen
python3 patches/academy-song13/fix_song13_v4.py
# -> patches/academy-song13/rop-academy-fix13-v4.gen (+ fix_song13_v4_patch.json)
```

The ROM is git-ignored (`*.gen`); only the builder, the patch JSON and
this README are committed. `fix_song13_v4_patch.json` records the exact
byte changes the builder makes. `song_check_rs.py` (the RS-aware song
parser the builder verifies with) and `tools/checksum.py` are vendored
in this dir so the builder is self-contained — `checksum.py` is
identical to the repo's `tools/checksum.py`.

## Feature build

The fix is also a `FEATURES=` feature, so it composes with the other
builds instead of needing a manual combine step:

```sh
make rom FEATURES=academy-song13            # v4 ROM, MD5 97e12dcc…
make rom FEATURES=topdown,academy-song13    # smooth ROM + v4, MD5 beb98c05…
```

`data.csv` is the feature's data: one row per changed byte run from
the v4 ROM vs the original (428 rows, 9,488 bytes), applied by
`tools/build_rom.py` after the hooks and before the checksums. The
two checksum fields (header `0x18E` and the runtime immediate
`0xFD098`) are left out on purpose — the build recomputes both. The
committed `rings-of-power-academy-song13.ips` is the feature build's
IPS; `tools/tests/test_build_rom.py` checks the build against it and
against both MD5s above, and that the combined build is the same in
either feature order.

To regenerate `data.csv` after any future fix version: rebuild the
fixed ROM with `fix_song13_v4.py`, diff it against the original ROM,
and keep every changed run except the two checksum fields. The
change sets are disjoint from the topdown feature (Academy: song
`0xF6844–0xF9044` + voices `~0xECE82`; topdown: hooks `0x127A–0x246C0`
+ blob `0xFD0CC–0xFFB73`), so the two compose in either order.
