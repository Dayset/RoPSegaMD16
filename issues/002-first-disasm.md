# Issue #002 — First linear disassembly + code/data map

**Milestone:** M1
**Epic 1**  
**Status:** done (2026-11-09)

## Goal
A first-pass disassembly of the whole 1 MB ROM and a map of what is code,
text, graphics, and unknown data.

## Acceptance
- [x] `disasm/rop.s` generated from the entry point + vectors —
      273,209 instructions, 196,448 undecodable bytes, 20 MB
- [x] `disasm/map.md` lists address ranges: code / text / graphics /
      unknown, with evidence (strings, entropy, disassembly sanity)
- [x] Entry at `0x200` disassembled and annotated (in `disasm/map.md`)
- [x] Known text blob located with start/end addresses —
      dialogue blob `0x0D6EBA–0x0DC0C0` (20,998 bytes)

## Notes
- Linear disassembly will mis-decode data as code — the map is what makes
  the next pass (recursive / Ghidra) trustworthy.
- Depends on #001.
- Reproducibility proven: regenerating `disasm/rop.s` from the script +
  ROM gives a byte-identical file.
- Capstone gotcha: `disasm()` stops at the first undecodable word
  without skipdata — `tools/disassemble.py` enables it.
- Linear-sweep "instruction density" is 0.70–1.00 everywhere, including
  certain graphics/text regions — it does NOT discriminate code from
  data. The map marks only vector-reached code as verified.

## Key findings (details in `disasm/map.md`)
- Only 3 non-zero vectors: SSP `0xFFEC1E`, reset `0x200`, HBlank
  `0x1270` (`rte` only), VBlank `0x1272` (frame counter `$FF0010`,
  joypad read).
- Entry is textbook Sega startup (TMSS "SEGA" write, VDP init table
  at `0x28E`, RAM/VRAM clear), then `jsr $FD07C` + `jsr $4323C`.
- **Runtime checksum self-test at `0xFD07C`** (verified by simulation):
  sums 32-bit words `0x000000–0xFD07B` (skipping `0x18C`) and compares
  to `0x8F33608C`; mismatch → VDP setup + infinite loop at `0xFD0CA`.
  Any mod must patch the `cmpi.l` immediate at `0xFD098` too.
- Real code confirmed at `0x200–0x1300`, `0x4323C`, `0xFD07C–0xFD0CB`.
  High-entropy blocks `0x044000–0x05FFFF` and `0x094000–0x0CBFFF`
  (7.0–7.6) are probably compressed graphics/data. Last 12,084 bytes
  (`0xFD0CC–`) are `0xFF` padding.
- Dialogue blob is packed/tokenised (words concatenated), not plain
  sentences. UI strings are normal spaced ASCII at `0x01215A`,
  `0x02937D–0x029767`, etc. Story/credits text at `0x0A66F4`,
  `0x0B3D4E`, `0x0B6226` is strided/interleaved. Credits block at
  `0x1B324`. The exact string `Rings of Power` occurs nowhere as
  contiguous ASCII.
- BlastEm address log (8 s run) confirms the game boots through the
  checksum into `0x4323C` and main-loop code (`0xEB000` region),
  VBlank handler firing.

## Result
Done. Next: #003 (entry/vectors/interrupts, incl. `$4323C` +
`$42FC8`/`$DCE2` save-validation) and #004 (text extraction).
