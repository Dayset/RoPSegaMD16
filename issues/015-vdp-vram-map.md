# Issue #015 — VDP register + VRAM layout map

**Epic 3**  
**Milestone:** M3  
**Status:** open

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
