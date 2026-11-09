# Issue #015 — VDP register + VRAM layout map

**Epic 3**  
**Milestone:** M3  
**Status:** done (2026-11-09)

## Goal
Map how the game programs the VDP: registers, VRAM layout, draw dispatch.

## Acceptance
- [ ] VDP register sets documented (boot table `0x28E`, `$A14` set,
      `$4323C` tail writes) with what each register value means
- [ ] VRAM layout found: name tables, pattern base, sprite table,
      scroll values (addresses in VRAM, not ROM)
- [ ] Per-frame draw dispatch traced from VBlank `jsr $EB772`
- [ ] Written up in `docs/graphics.md`

## Notes
- Depends on #011. 103 `$C00004` references in the sweep are leads,
  not answers — most are in data regions.



## Work done 2026-11-09 (agent session, no ROM in VM)

- **Deliverable:** docs/graphics.md — VDP register sets documented (boot table 0x28E value-by-value, $A14 set, display-on sequence, $11E06 game set), VRAM layout table per configuration, and the per-frame section CORRECTED: $EB772 is sound-only (#003), drawing lives in the main loop ($1B918, $1194A, $170DA).
- **Acceptance:** MET: register sets + VRAM layout (verified pieces) + write-up in docs/graphics.md. NOT MET / NOT EVIDENCED: the issue's '$4323C tail writes' — $4323C is the save routine; no VDP writes are attributed to it in any repo doc (recorded in graphics.md §1d as a stale premise, not filled in). PARTIAL: full per-screen register sets + per-frame draw list remain open (need live trace).

**Status after this session:** in progress — partial (see below). Not marked done.

## Update 2026-11-09 (session #3, ROM + BlastEm debugger) — DONE

The remaining live-trace work is done; write-up in
docs/graphics.md §5 (per-screen register table §5a, draw
trace §5b, paradox note §5c). ROM used: the ORIGINAL
(scratch copy; byte-identical to the M5 rebuild).

- **Per-screen register sets — captured live** (`vr` at
  breakpoints 0x242 / 0x334 / 0x388 / $11E06 / $14FB6,
  VBlank-stepped intro samples, $D28E samples): boot table
  and $A14 set **confirmed value-for-value** against §1a/§1c;
  $A14's R11=$03 (per-line H-scroll) made explicit; $119E's
  R10 restore ($FF) caught between the animation and $11E06;
  $11E06's set confirmed exactly at $14FB6 entry.
- **New:** the intro driver runs **its own register sets**
  (planes $2000/$F000/$0000, SAT $4400, H-scroll $4000;
  R11 full on screen A, line on screen B), and by main-loop
  entry R16 is $01 (64×32), not $11E06's $03 — a later setup
  pass shrinks the planes (write not isolated).
- **Draw trace (the $11E06 → intro transition):** $11E06
  issues no DMA (CPU VRAM clear via $DC60/$D9EE); tile
  uploads are $11A7C → $DA04 DMA (13/13 sampled hits return
  to 0x11A98); nametables via the $1194A blitter from the
  intro draw cluster $15ECE–$15FA0; window rows via
  $DC60($F000 + n×$80); SAT written entry-by-entry by CPU
  (see #016). Per-frame main-loop redraw stays the $1B918
  flag dispatcher; its tile re-upload is one $DA04 DMA
  ($33C0 words from $FF1EC0 to $FF8674<<5).
- **Acceptance:** register sets ✓ (the '$4323C tail writes'
  sub-item stays recorded as a disproven premise in §1d —
  $4323C is the save routine and writes no VDP registers);
  VRAM layout ✓ (now per-configuration, runtime-verified);
  per-frame draw dispatch ✓ (the 'from VBlank $EB772'
  wording rests on the premise #003 disproved — $EB772 is
  sound-only; the actual dispatch is traced instead);
  write-up ✓ (docs/graphics.md §5).
- **Not covered:** register sets for post-intro gameplay
  screens (combat, towns) — unreachable without gameplay
  input in this headless setup; every screen reachable
  without input is captured.

**Status: done.**
