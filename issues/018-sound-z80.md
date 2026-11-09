# Issue #018 — Sound: Z80 driver + music/SFX map

**Epic 3**  
**Milestone:** M3  
**Status:** open

## Goal
Find the Z80 sound driver, music, and sound effects.

## Acceptance
- [ ] Z80 code location + driver entry identified
- [ ] Music/SFX data regions located with addresses
- [ ] How the 68000 triggers music/SFX (commands via Z80 RAM) documented
- [ ] Written up in `docs/graphics.md` (audio section) or `docs/sound.md`

## Notes
- 68000 touches the Z80 only via `$A11100` bus control so far.
  The driver itself lives in Z80 address space — Ghidra m68k will not
  cover it; note the tooling gap if it blocks the work.

