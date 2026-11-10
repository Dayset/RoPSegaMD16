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
  2026-11-10) and live-verified (2026-11-10, 44/44 harness cases)**:
  deduction in `FUN_024984` `$024F38`–`$024FB2` (gate `$FF00AE==1`,
  food `$FFC364`, water `$FFC366`, clamp [1, 30000]); cost computed by
  `FUN_01c892` `$01C892` = base(mode) + terrain addition + height/2
  (food only); mode from char `+0x06` via `$25D8E`; terrain dispatch
  table `$01D73E` (35 types). **Live correction: mode-0 base is (3,1),
  not (2,2)** — the (2,2) write at `$01C8C6` falls through into the
  mode-1 (3,1) block. Verified vs manual: Road 1/1 (type 9, mode 0),
  **Desert 7/5 (type 17, mode 0: (3,1)+(4,4))**, Dino 3/1 (mode 1
  base), Boat deep 5/20 (type 0, mode 7), **Dragon 38/38 (mode 4 base,
  confirmed live — manual's 40/40 is off by 2)**; height term
  confirmed live incl. negative (delta −4 → food −1). **Open:**
  terrain-type → terrain-name mapping for Grass/Swamp/Ice (manual
  water 2/4/3 not attainable as flat mode-0 water — live mode-0 water
  is only 1 or 5), Dragon 40/40 vs live 38/38. **CAMP — located and
  live-verified (2026-11-10, 3/3 harness cases):** handler
  `FUN_03019a` `$03019a`, called as C=28 from the verb executor
  (Camp verb-table byte 11 = `$1C`); deduction is a direct register
  subtract + store (`$030346`–`$0303B4`: food `$FFC364 −= 100`, water
  `$FFC366 −= 100`, clamp [1, 30000]) — **not** via `$2BBD2`
  (the `$02C188` candidate was wrong); **regain is 25% of the
  HP/Power deficit** (`divs.w #$4`, measured HP 10→32, Power 20→35),
  **not** the manual's 50% — the 50% regain (`divs.w #$2`) is the
  inn service **Sleep** (goods 704, item 11 "services", price rec 136,
  75 gold), live-verified 2026-11-10 (3/3 harness cases,
  `.scratch007/harness_sleep.s`): `$2BBD2(1,704,1,1)` → HP 10→55,
  Power 20→50, no food/water/gold deduction; paired service **Meal**
  (goods 705, 50 gold) gives +25 HP only. Sleep is a service bought
  at an inn, not a carried item; the 75-gold payment is a separate
  transaction. **Temple counterparts — located and live-verified
  (2026-11-10, 4/4 harness cases, `.scratch007/harness_temple.s`):**
  **Heal** (goods 1026, 150 gold) = full HP restore (max HP recomputed
  from level, measured HP 10→95, HP max 100→95); **Pow Up** (goods
  1027, 150 gold) = full Power restore (measured Power 20→80, no
  recompute); **Life** (goods 1028, 700 gold) = revive a dead member
  (cur HP/Power = 5, maxes recomputed, dead flag `+0x2C` bit 13
  cleared, measured HP 0→5, Power 0→5, HP max 100→95, Power max
  80→6000; no-op on a live member; plays song 8 on a revive
  [static]). None deducts gold/food/water or flips the clock.
  **clock flips day↔night by setting `$FF0E16` to 540 (if ≤540) or 0**
  (measured 100→540, 1000→0) — not a +1200 advance. Open: which
  `$FF0E16` range is day vs night.
  Harness: `.scratch007/harness_camp.s` + `.scratch007/harness_sleep.s`
  + `.scratch007/harness_temple.s`
  (see docs/logic.md §3.7). → #020.
- Bribe/attitude action; Gems sell 428; `$FF012C` meanings; +0x02/+0x27;
  other `$2BBD2` handlers; who initialises `$FF0E18[2]`; item-record
  +4..+9 bytes; Doggonia 1,000-gold fee; post-harness PC=0 fault. → #021.
