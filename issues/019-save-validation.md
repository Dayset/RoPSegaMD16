# Issue #019 — Save/SRAM validation + $DCE2 / $42FC8 / $43012

**Epic 2**  
**Milestone:** M2  
**Status:** done 2026-11-09 (M2 complete)

## Goal
Understand `$4323C` fully: what storage the game uses and how it
validates a save.

## Acceptance
- [x] `$DCE2`, `$42FC8`, `$43012` traced and documented (what they read,
      what the `$E0`/`$B0` magic bytes mean) — `docs/save.md` §2–§3
- [x] Save medium decided: SRAM / EEPROM / passwords / none, with evidence
      — **128-byte serial EEPROM**, Microwire bit-bang via `$200000`,
      DI = D7, CLK = D6, DO = D7; header declares no SRAM; BlastEm
      `rom.db` (`T-50176`, I2C, size 128) corroborates. Chip identity
      open (93C46 family unproven). — `docs/save.md` Verdict + §2
- [x] The 128-byte `$FF016A` buffer format + its byte-sum check explained
      — magic `0x2A` + parity + 1001-bit packed `$FFA800`; a valid save
      **fails** `$4323C`'s byte-sum check 3/3 (harness-proven) — the
      check is vestigial. — `docs/save.md` §1.2/§4/§5
- [x] `$FF0168` flag values (0 / 1 / −1) mapped to game states
      — 0 = default/valid-or-ignored, 1 = `$E0` clear path, −1 =
      EEPROM error or invalid-checksum-with-`$B0`; never read by any
      code (re-verified by grep). — `docs/save.md` §1.4

## Notes
- Depends on #003. Header SRAM field is blank — do not assume SRAM exists.

