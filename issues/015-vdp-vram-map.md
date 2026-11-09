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

