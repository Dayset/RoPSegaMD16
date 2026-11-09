# Issue #018 — Sound: Z80 driver + music/SFX map

**Epic 3**  
**Milestone:** M3  
**Status:** done (2026-11-09)

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



## Work done 2026-11-09 (agent session, no ROM in VM)

- **Deliverable:** docs/sound.md — Z80 driver map from 68000-side evidence: upload $EB806 (1,576 bytes from ROM $EBB6E -> Z80 RAM), per-frame tick $EB772, streamer $EBA00, command queue $EBAC6, song path $173BC/$173EC + 19-entry song list at 0xCD208, SFX trigger $17586, 17-track fan list cross-check, and the tooling gap stated.
- **Acceptance:** MET: driver location/entry (upload-based), music/SFX trigger mechanism, write-up in docs/sound.md. PARTIAL/BLOCKED: the Z80 code itself has never been disassembled (Ghidra m68k does not cover Z80 space) and the $EBB04/$EBBFE handlers are untraced — needs the ROM extracted as Z80 on the owner's machine.

**Status after this session:** in progress — partial (see below). Not marked done.

## Update 2026-11-09 (continuation) — Z80 BLOB DISASSEMBLED

Extracted ROM $EBB6E, 0x1576 bytes (the map's hex length), and
disassembled with z80dis via the new tools/disasm_z80.py.
First-pass map written into docs/sound.md: reset/vector layout,
the 0x000A/0x000B command mailbox + poll loop at 0x0188, main
entry 0x017D, YM write helpers (0x01B4/0x01BA part 1,
0x04B9/0x04BF part 2), bank-switch writes at 0x04A8/0x04B0,
PSG writer at 0x0972+, and the two data regions (52 zero bytes
at 0x00A6, 92 0xFF bytes at 0x00F1) identified so they are not
mistaken for code.
**Status: done** (first-pass map as scoped; deep routine-by-
routine annotation remains future work, not this issue's bar).
