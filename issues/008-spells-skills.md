# Issue #008 — Spells / skills system

**Milestone:** M4  
**Epic 2**  
**Status:** ✅ done 2026-11-09

## Goal
Map the six-arts spell system: spell tables, costs, effects.

## Acceptance
- [x] Spell list + IDs extracted with addresses
- [x] Spell cost / power tables located
- [x] At least one spell effect routine traced end to end

## Done 2026-11-09
`docs/spells.md` (remake-spec standard, same as `docs/logic.md`),
`disasm/spells/` tables (`spell_list.txt` 120 spells,
`rank_tables.txt` 6 tables × 21 records, `names_cd431.txt` 893
names), `tools/test_spells_harness.s` + `tools/ghidra_decomp_spells*.py`.

- Spell list: price records 1–120, 6 blocks × 20, names from
  `$CD431`; discipline↔block mapping NOT proven (hypothesis only).
- Rank tables: new-game init `0x1B5F4` installs 10 pointers at
  `$FFA7CC` (ranks 1–6 distinct, 7–10 reuse rank 2); 6-byte
  records (`w0` damage base/effect class/bit 11, `w1` param +
  `$FF012C` code, `w4` = Power cost base).
- Cost: `$3C2C0` = `w4 × (modifier+1) × 3`; deduction `$37D0E`
  (clamp + out-of-power HP −5 drain) — **harness 44/44 PASS**
  (S1 dispatch ×4, S2 costs, S3 deduction ×3, S4a link chain,
  S4b farthest-pick, S4c full `$3B51E` path; `/tmp/ropre/run008.json`).
- #007 Q1 answered at the dispatch level: both damage paths run,
  `+0x24` selects spell vs melee; `$FFC418`/`$FFC41A` =
  target/caster indices (S1 live). `$FF012C` codes mapped (§5).
- Unblocking story (§8.3): harness stalled inside `$37D0E` —
  S1 leaves `slot0.+0x00 = 0xA0`, `$25456` takes its
  `$12FA0` → `$12072` sound branch when `+0x00 & 0xF == 0` and
  `$12072` never returns in the cold attract context; fixed by
  resetting the slot in `setup_spell` (+ `slot5.+0x29 = 5` for
  the S4 group link). Open: giant-function block selection,
  `$12072` spin loop, live-combat half of Q1 → #020/#021.

