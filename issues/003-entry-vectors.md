# Issue #003 — Entry point, vectors, VBlank/HBlank interrupts

**Milestone:** M2  
**Epic 2**  
**Status:** ✅ done 2026-11-09

## Goal
Label the reset path and the interrupt handlers.

## Acceptance
- [x] Reset vector (`0x200`) traced to first game init
- [x] VBlank / HBlank / level interrupt handlers identified by address
- [x] TMSS / SEGA init sequence annotated
- [x] Written up in `docs/architecture.md`

## Evidence (how verified)

- **Reset trace** — Capstone range disassembly (`tools/.venv/bin/python
  /tmp/rop_range_dis.py`, scratch dumps in `/tmp/dump*.txt`):
  `0x200` TMSS check → table-driven init from the 108-byte table at
  `0x28E` (24 VDP regs) → `"SEGA"` write to `$A14000` → RAM/VRAM/
  CRAM/VSRAM clears + 38-byte Z80 stub upload + PSG silence →
  `bra $2FA` → `jsr $FD07C` (checksum) → `jsr $4323C` (EEPROM/save
  check) → `$8134` (display blank) → `$3AA`/`$A14`/`$3AA` →
  `$8174` (display ON) → attract loop `0x35C–0x390` → `bra $119E` →
  `jsr $EB806` (sound upload) → `jmp $D25C` (dispatcher: `$11E06`,
  `$14FB6`, `$1B5D6`, `$32D0E`, `$173BC`, `$D28E`, `$179B6`).
- **Vectors** — all 64 vector longwords read from the ROM: only SSP
  (`0x00FFEC1E`), reset (`0x200`), HBlank (`0x1270`, single `rte`),
  VBlank (`0x1272`) are non-zero. Consequence: no fault handlers.
- **VBlank** — fully traced `0x1272–0x134E`: `$FF0016=0`,
  `$FF0010++`, port-1 joypad read (`$A10003`), `jsr $EB772` at
  `0x12F2`, 3-frame debounce (`$FF0019`), 16-entry ring
  `$FF001C`[head `$FF001A`, tail `$FF001B`], three `rte` exits
  (`0x1312`/`0x1340`/`0x134E`); `$1350` is the polled pop routine.
- **$EB772** — the per-frame **sound/music tick** (`0xEB772–0xEB7C6`):
  PAL/NTSC tempo tick to Z80 `$A000E6`, `jsr $EBAC6` (command queue),
  every 16 frames `jsr $EBA00` (music streamer). Single call site
  `0x12F2`. Corrects the `docs/overview.md` line that put a
  draw dispatch there (overview fix left for review).
- **HBlank** — `0x1270` is a single `rte` and never fires: boot
  R0=`$04` leaves H-int enable (bit 4) = 0.
- **$4323C helpers (call-graph level)** — `$42FC8` EEPROM enable,
  `$43012` EEPROM write, `$430F4` EEPROM read, all bit-banging a
  Microwire-style serial EEPROM through `$200000` (DI=D0, CLK=D6,
  DO=D7); `$DCE2` = joypad port 2 read (8 call sites); `$E0` =
  B+C+Start, `$B0` = A+C+Start on pad 2. Full save analysis is #019.
- **Ghidra** — headless call graph, 436 functions / 1,434 edges
  (`/tmp/ghidra_calls.txt`): entry calls `$FD07C`/`$119E`/`$4323C`/
  `$3AA`/`$A14`/`$4E6`; `$D25C` 7 callees; `$D28E` 25 callees;
  `$4323C` → `$42FC8`/`$DCE2`/`$43012`/`$430F4`. Ghidra did **not**
  auto-create functions at `0x1270`/`0x1272`/`$EB772` (no call
  sites) — noted in `docs/architecture.md`.
- **BlastEm** — 10 s headless run (`SDL_AUDIODRIVER=dummy timeout 10
  xvfb-run -a /usr/games/blastem -l /tmp/rop_blast.gen`), address log
  `/home/hatch/address.log`: 2,487 unique addresses, first-hit
  order. Confirms `200 → 2FA → 119E → D25C → D28E`, hits on `FD07C`,
  `4323C`, `3AA`, `A14`, `4E6`, `1272`, `EB772`, `EB806`, `EBAC6`,
  `EBA00`, `1350`, `D8BA`, and **0 hits on `1270`**. BlastEm also
  auto-detected a 128-byte EEPROM and saved an all-`$FF`
  `save.eeprom`, matching the 128-byte buffer at `$FF016A`.
- **Write-up** — `docs/architecture.md` (Entry / Vectors /
  Interrupts / $EB772 / $4323C sections, replacing the early-notes
  stub); `disasm/map.md` updated (entry trace, VBlank/HBlank,
  `$EB772`/`$EB806`/`$119E`/`$D25C`/`$D28E`, sound-cluster row,
  open questions 1–2 answered/partially answered).

## Left open (not #003's scope)

- #011: Ghidra recursive analysis + function map (code/data
  boundary still provisional; interrupt handlers need manual
  function creation).
- #019: save validation — EEPROM chip identity, `$FF016A` buffer
  layout, `$43012`/`$430F4` ACK semantics, `$4323C` return value,
  whether the pad-2 `$E0`/`$B0` combos are a deliberate "clear
  save" feature.
- #020: main loop / state machine — what `$D25C`'s seven callees do,
  the `$D28E` flag dispatch, the `$FF02B4`/`$FF02DB` 52-byte structs
  behind `$D8BA`, where the eternal loop sits (`rts` at `0xD28C`
  is not reached in normal flow).
