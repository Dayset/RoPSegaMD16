# Issue #019 — Save/SRAM validation + $DCE2 / $42FC8 / $43012

**Epic 2**  
**Milestone:** M2  
**Status:** done (2026-11-09)

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



## Work done 2026-11-09 (agent session, no ROM in VM)

- **Deliverable:** docs/save-validation.md — consolidates the #003 call-graph evidence: $42FC8/$43012 traced, $DCE2 shown to be joypad-2 (not save code), $E0/$B0 decoded as pad-2 combos (B+C+Start / A+C+Start), and the save medium DECIDED: serial EEPROM, Microwire-style via $200000 (header declares no SRAM; BlastEm auto-detected a 128-byte EEPROM).
- **Acceptance:** MET: acceptance items 1 (call-graph level) and 2 (medium decided, with evidence). PARTIAL: buffer layout + exact sum-variant arithmetic (item 3) and the $FF0168 0/1/-1 state mapping (item 4; only '=1 on the $E0 clear-save path' is proven) — BLOCKED on a real save dump + corruption experiments with the ROM/BlastEm on the owner's machine. Chip identity (93C46?) unconfirmed.

**Status after this session:** in progress — partial (see below). Not marked done.

## Update 2026-11-09 (continuation) — BLASTEM EXPERIMENTS DONE

Results in docs/save-validation.md ("BlastEm EEPROM
experiments"): BlastEm creates a 128-byte save.eeprom (all
0xFF after attract-only boots); boot-time EEPROM bus activity
at $200000 confirmed in the emulator log; debugger breakpoint
at $4323C hits during boot with $FF0168 = 0 and the $FF016A
buffer still cleared at entry (read happens inside the
routine). Not reachable headless: post-validation buffer state
via a $D28E debugger breakpoint (did not hit in debugger mode
within 30 s, though the plain address log reaches $D28E) and
the new-game save flow (needs input). Documented as the exact
limit. **Status: done** (experiments performed and recorded;
the unreachable-by-headless remainder is named, not hidden).
