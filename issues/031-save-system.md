# Issue #031 — Save system (modern saves for the tribute)

**Milestone:** M7
**Epic 5** (Tribute remake)
**Status:** open

## Goal
Modern save/load for the tribute, informed by the original's save
format — including an import path from an original save if that
proves feasible.

## Acceptance
- [ ] Save/load works for party state, position, gold, inventory,
  quest flags (list the exact fields in the issue)
- [ ] Save format documented in `tribute/` (human-readable or
  versioned binary — decide in the issue)
- [ ] Original-save import attempted: yes/no with the reason, and
  if yes, at least one real original save imported and verified
  in-game

## Notes
- Original save: serial EEPROM, Microwire-style, bit-banged via
  `$200000`; 128-byte buffer at `$FF016A`; weak byte-sum validation
  (#003, #019). The original's save problems are part of why the
  Russian fan translation's commenters asked for an EEPROM→SRAM
  rework — read #019 before designing.
- Do not reproduce the original's weak validation in the new format.
- Owns: `tribute/save/`. Do not touch #019 (the RE issue) — read it.

## Depends on
#019 (save/EEPROM deep-dive), #020 (state machine — what state
there is to save). Design can start now; implementation waits for
#019.

## Status
open


## Work done 2026-11-09 (agent session, no ROM in VM)

- **Deliverable:** docs/tribute/031-save-system.md — design: full save field list from #020 state + #007 structs; format decision = versioned JSON + SHA-256 (the original's weak byte-sum explicitly NOT reproduced); original-save import attempted on paper and answered NO for v1 with the reason.
- **Acceptance:** PARTIAL: field list + format decided (acceptance items 1-2 as design). BLOCKED: implementation waits on #023; the import sub-item ('one real save imported') is blocked on #019's buffer layout, which is unknown — importing now would mean fabricating offsets.

**Status after this session:** in progress — partial (see below). Not marked done.
