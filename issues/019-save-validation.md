# Issue #019 — Save/SRAM validation + $DCE2 / $42FC8 / $43012

**Epic 2**  
**Milestone:** M2  
**Status:** open

## Goal
Understand `$4323C` fully: what storage the game uses and how it
validates a save.

## Acceptance
- [ ] `$DCE2`, `$42FC8`, `$43012` traced and documented (what they read,
      what the `$E0`/`$B0` magic bytes mean)
- [ ] Save medium decided: SRAM / EEPROM / passwords / none, with evidence
- [ ] The 128-byte `$FF016A` buffer format + its byte-sum check explained
- [ ] `$FF0168` flag values (0 / 1 / −1) mapped to game states

## Notes
- Depends on #003. Header SRAM field is blank — do not assume SRAM exists.

