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

## Notes
- 68000 touches the Z80 only via `$A11100` bus control so far.
  The driver itself lives in Z80 address space — Ghidra m68k will not
  cover it; note the tooling gap if it blocks the work.

