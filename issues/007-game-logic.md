# Issue #007 — Game logic: stats, XP, gold, combat

**Milestone:** M4  
**Epic 2**  
**Status:** done (2026-11-09)

## Goal
Find the routines and tables behind character stats, XP/levelling, gold,
and combat damage.

## Acceptance
- [x] XP table / level-up routine located — **there is no XP table, it is a
  formula**: `$2F030` level = smallest L with XP < 100·2^L; max HP
  `$31958` = min(20+15·level, 140); max Power `$31946` = (level+1)·1000.
  Max level is **8** (XP 12800+), not 7. XP handler `$2C4E2` (cap 13000),
  battle-end XP `$35600` area, RNG `$12B82` (glibc LCG).
- [x] Gold / shop price handling located — gold at struct +0x2A (cap
  15000); item categories `$D66A6` (20 records); price table `$D6768`
  (257 records); price function `$2EA92` (attitude ×0.64–×1.36, ×2 at
  location 367, /2 for goods); buy `0x1FDC4`, sell `0x1FB88`
  (`$2EA92(14, slot)/2`). Trading guide checked: 20/21 goods fit,
  Gems sell 428 is impossible (see docs/logic.md §3.5).
- [x] Combat damage formula located — `$3B1EE`: atk/def stats from
  +0x28, modifier bits from +0x2C, order switch on rank (low nibble),
  special `$FF012C` values (0x8E–0x92 → 70, 0x97 → 5), immunity at
  +0x02 == 0x4D. **Distance term is dead** (always 0 — inverted
  division). Sibling vestigial path at `0x40880` — which runs is open
  (#008/#021).
- [x] Each finding has address + bytes + a test (emulator / trace) —
  harness `tools/test_logic_harness.s`: 90 result words, all PASS
  (see docs/logic.md §7.2). Tables in `disasm/logic/`.

## Evidence
- `docs/logic.md` — full write-up (remake spec; player-observed vs
  code-verified labelled throughout; rec 1004 quoted with record
  address; Gavin as code/design authority; Rubin negative finding).
- `disasm/logic/` — `xp_levels.txt`, `items.txt`, `price_table.txt`,
  `trading_check.txt`, `damage_tests.txt`, `README.md`.
- `tools/test_logic_harness.s` — emulator harness (1,338 bytes), hook at
  `0x35C`, results in `$FFD000+`, read back via BlastEm debugger
  breakpoint at 0.

## Open questions (for #008 / #020 / #021)
- Which damage path runs in live combat (`$3B1EE` vs `0x40880` spell path);
  `$FFC418`/`$FFC41A` contents; `$3B1EE` arg puzzle. → #008.
- Transport / food-water consumption routine — **located (static,
  2026-11-10)**: deduction in `FUN_024984` `$024F38`–`$024FB2` (gate
  `$FF00AE==1`, food `$FFC364`, water `$FFC366`, clamp [1, 30000]);
  cost computed by `FUN_01c892` `$01C892` = base(mode) + terrain
  addition + height/2 (food only); mode from char `+0x06` via `$25D8E`;
  terrain dispatch table `$01D73E` (35 types). Verified vs manual:
  Road 1/1 (type 9), Dino 3/1 (mode 1 base), Boat deep 5/20 (type 0,
  mode 7). **Open:** terrain-type → terrain-name mapping for
  Grass/Desert/Swamp/Ice (manual water 2/5/4/3 not attainable as
  mode-0 water), Dragon 40/40 vs code 38/38, CAMP 100/100 deduction —
  needs a live `$1C892` harness (see docs/logic.md §3.7). → #020.
- Bribe/attitude action; Gems sell 428; `$FF012C` meanings; +0x02/+0x27;
  other `$2BBD2` handlers; who initialises `$FF0E18[2]`; item-record
  +4..+9 bytes; Doggonia 1,000-gold fee; post-harness PC=0 fault. → #021.
