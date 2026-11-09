# Hardware-limits checklist (issue #014)

Every build and every mod ticks this list before it lands. Source of
the budgets: `docs/overview.md` (hardware facts) + `docs/architecture.md`
(verified game behaviour). Written 2026-11-09 (agent session); the
harness half is scaffolded in `tools/test_harness.sh` and is blocked
on #013 + BlastEm on the owner's machine.

## Budgets — tick each one

- [ ] **ROM size:** output is exactly 1,048,576 bytes (1 MB flat,
      `0x000000–0x0FFFFF`, no bank switching in the header). Any growth
      needs a new header end address + both checksums — a new issue,
      not a silent change.
- [ ] **Free ROM space:** only the `0xFF` padding `0x0FD0CC–0x0FFFFF`
      (12,084 bytes) is free inside the 1 MB image. Hooks/trampolines
      must fit there (music-off uses 104 bytes of it) or free space
      elsewhere with evidence.
- [ ] **Checksums:** `tools/checksum.py fix-all` run — header word at
      `0x18E` AND runtime immediate at `0xFD098` (expected original
      sum `0x8F33608C`, routine at `0xFD07C` hangs at `0xFD0CA` on
      mismatch). Header-only fixing = blank screen at boot.
- [ ] **Work RAM:** 64 KB `0xFF0000–0xFFFFFF`; stack starts at
      `0x00FFEC1E`. No new persistent state outside a proven-free RAM
      gap (harnesses used `$FFD000+` after a gap analysis — copy that
      method, don't guess).
- [ ] **VDP:** 64 KB VRAM, 128 B CRAM (64 colours, 4×16), 4 bpp tiles,
      planes A/B + window, **80 sprites max, 20 per scanline**,
      320×224. All access via `$C00000`/`$C00004`.
- [ ] **DMA/blanking:** VRAM writes fit in blanking or are DMA'd via
      the control port; no mid-frame VRAM flooding (tearing).
- [ ] **CPU:** 68000 @ 7.67 MHz. Per-frame additions must fit the
      VBlank + frame budget; the `$D28E` loop already runs a
      10,000-iteration pacing delay — measure, don't assume.
- [ ] **Z80 bus discipline:** request/release `$A11100` around any
      Z80 RAM touch (the VBlank handler and `$EB92A` show the pattern).
- [ ] **No fault handlers exist:** every exception vector except
      reset/HBlank/VBlank is `0x00000000`. Any new divide, bad pointer
      or illegal instruction = jump to 0 = hang. New code must be
      divide-by-zero-safe by construction (see the `$FF0E18[2]`
      hazard, `docs/logic.md` §2.7).
- [ ] **TMSS:** the `"SEGA"` write to `$A14000` and the boot order
      (TMSS → VDP table `0x28E` → clears → checksum → save check)
      stay byte-compatible.

## Emulator-vs-hardware gaps (what BlastEm forgives)

- BlastEm auto-detects the serial EEPROM from the `$200000` access
  pattern and creates a 128-byte `save.eeprom`; real carts vary —
  a mod must not depend on emulator EEPROM timing/size.
- BlastEm headless (Xvfb + dummy audio) proves boot + address-log
  reachability, **not** audible output, raster timing, or DMA
  contention behaviour. The music-off patch's SFX audibility is
  explicitly "not proven" for this reason (`patches/music-off/README.md`).
- Emulators tolerate some illegal/edge instruction timings and
  open-bus reads that hardware does not; the zero exception vectors
  mean hardware will hang where an emulator log might warn.
- The vsync modal dialog in headless BlastEm can make a healthy ROM
  look hung (see `docs/spells.md` §8.3) — a harness failure is not a
  ROM failure until the dialog is ruled out.

## Harness (acceptance item 2) — status

`tools/test_harness.sh` implements the intended flow
(build → verify gate → fix-all → BlastEm headless → grep the address
log for `0x4323C` + main-loop addresses) but **cannot run in this VM**:
no ROM, no assembler, no BlastEm. First run belongs on the owner's
machine after #013.
