# Issue #018 — Sound: Z80 driver + music/SFX map

**Epic 3**  
**Milestone:** M3  
**Status:** done 2026-11-10 (write-up: `docs/sound.md`)

## Goal
Find the Z80 sound driver, music, and sound effects.

## Acceptance
- [x] Z80 code location + driver entry identified
- [x] Music/SFX data regions located with addresses
- [x] How the 68000 triggers music/SFX (commands via Z80 RAM) documented
- [x] Written up in `docs/graphics.md` (audio section) or `docs/sound.md`

## Done 2026-11-10
`docs/sound.md` — driver blob ROM `0xEBB6E–0xED0E4`, entry Z80 `$0000`
(`SHayes1991` at `$00DA`); 19 songs + 2 no-ops (map in the doc, stream
lengths verified from the end pointers, parser simulation shows songs 8/16/20
terminate and the rest loop); SFX table `$FCAE2` (62 slots, only 0–38 called) + pointer SFX
90–96; full 68k→Z80 command path (`$EB772` tick, `$EB806` upload, `$EB88A`
start-song, `$EBA00` streamer, `$EBAC6` queue, `$EB9C4`/`$EB9EE` checks);
live-verified in BlastEm (original-ROM breakpoint run + snapshot harness).
Tooling gap CLOSED for disassembly: Ghidra 11.4.2 headless Z80
(`z80:LE:16:default`) disassembled the driver (1067 instructions).
Corrections made during the write-up re-check: `$EB9EE` has 4 callers (SFX-busy
gate in the `$3Dxxx` combat routines); `$EB986`/`$EB9A0`/`$EB9B4`/`$EB8E0` are
dead (no callers); `$17586`'s second argument is `$FFFF` at all 98 call sites.
**M3 is now complete.**

**Addendum 2026-11-10 (song-mapping, ROM-only):** the 17 fan-site track names
are mapped to song indices in `docs/sound.md` §7.4 — by code context
(location table §7.3, `$32D0E` picker, all `$173BC`/`$173EC` call sites),
parsed song streams, and one BlastEm audio capture per song (dispatch-table
patch, `SDL_AUDIODRIVER=disk`, `.scratch018/songs/songNN.wav`, NOT
committed). Certain: song 0 (silent), song 2 (Enchanters), 18/19 (no-ops).
Strong: song 1 (Main theme), song 8 (unnamed sting). The rest are guesses
by character/context, stated as such; a live playthrough could upgrade
them. The §7.3 location→song map is now the full verified 0–151 dump (loc 63
→ song 3, not 4, was corrected). §12 item 1 (mapping) is marked done; §12
item 9 is corrected — the PSG IS used (`$0967` writes `$7F11`, pointer-SFX
path). Top table SFX identified by context in `docs/sound.md` §8.4 (SFX 32
= ubiquitous action, 20 = arrival chime, 1 = transition, 15/19/21/33 =
combat/XP); no SFX audio was captured — that is the remaining follow-up.
Original ROM re-verified unchanged (MD5 `30c18fdbe2183f64702ae9f1a45d63f9`).

**Burst follow-up 2026-11-10 (debugger; docs/sound.md §7.5, §12 item 12):**
burst 1 is **SOLVED — SFX 94** (pointer SFX, data `$4504`, called from
`FUN_0123b0` at `$0129DC`). A BlastEm breakpoint on `$17586` in the
song-0 ROM logs exactly two calls in 99 s emulated — SFX 94 at 17.2 s,
SFX 1 at 60.4 s — with audio events at 17.3 s and 60.4 s in the same run
(ratio calibrated from that run's audio, 2.197); the SFX 94 harness
capture shares burst 1's spectral peaks (193/232/260–263/318/490 Hz) and
band ratio (0.96). The earlier "ruled out by correlation 0.03–0.07" for
SFX 94 was a window/alignment artefact, superseded. Burst 2 (~67.6–71.1 s)
is **SOLVED — SFX 1** [live, NOP test]: a test ROM with the SFX 1 call at
`$0150EC` NOP'd (`jsr $17586(pc)` → `NOP NOP`, checksums fixed) removes
burst 2 entirely while burst 1 is sample-identical (corr 1.000) — the
SFX 1 call is the necessary and sufficient cause. The earlier "burst 2 is
not SFX 1" (spectrum/correlation mismatch) is superseded: SFX 1 is
deterministic within a context (a fresh harness capture reproduces the old
peaks exactly), but renders with different pitches in the cinematic (song 1
playing) context than in the silent harness — context-dependent voicing.
Burst 2 and the harness SFX 1 share some low peaks and have nearly
identical band energies, but differ in mid/high peaks with ~0 waveform
correlation. **Mechanism follow-up 2026-11-10 (docs/sound.md §7.5, §12 item 12) —
root cause found [live], pitch translation [open]:** SFX 1's note `$09`
is allocated a different FM voice by song context. The `$FD`
voice-table row for channel E=`$0E` (`$0143–$0147`) holds `$09` at
index 0 when silent (`09 FF FF FF FF`) but at index 2 when song 1
plays (`FF FF 09 FF FF`); via the `$EB` voice→FM-channel map
(`0→ch0, 2→ch2`) SFX 1 sounds on **FM channel 0 (silent) vs FM
channel 2 (song 1)**. The SFX's frequency state is identical in both
contexts (slot freq `$0930` at 60 frames, `$0C2C` at 1 frame;
channel-struct freq `$043C`; `$00A6` `$120C`), so the
base-frequency hypothesis is ruled out — the install-time base is
`$0C3C` (note 9) in both, set by SFX 1's own note byte, not the song.
PSG is ruled out [static]: all `$7F11` writes are in `$0967–$09AA`
(song loop only); SFX 1 is FM-only. Still [open]: how ch 2 vs ch 0
moves the heard peaks (282–612 Hz → 112–254 Hz) — candidates are the
song's notes on ch 2 overwriting the SFX's frequency registers, or a
per-channel operator difference; a YM2612 write trace for SFX 1 in
both contexts would settle it. Also [open]: 88 data steps (~1.5 s)
vs ~3.6 s audible. Harness caveat: multi-byte `(a0)+` Z80 dumps
return an identical pattern for different addresses (unreliable);
the voice-row numbers above are from absolute-address reads (sanity
checked). Harnesses in `.scratch018/` (`harness_slotonly*.s`,
`run_bonly_sonly.py`, `run_s1f.py`, `run_cs.py`, `run_vt.py`,
`harness_sanity.s`). Original ROM re-verified unchanged (MD5
`30c18fdbe2183f64702ae9f1a45d63f9`).

## Notes
- 68000 touches the Z80 only via `$A11100` bus control so far.
  The driver itself lives in Z80 address space — Ghidra m68k will not
  cover it; note the tooling gap if it blocks the work.

