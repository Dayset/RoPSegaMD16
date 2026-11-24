# Void `error_show` code table (#276)

The "Void" death message ("By a cruel twist of fate, Void has found
your party and exterminated you in a mere N seconds…") is **not** a
timer and **not** a death. It is the game's generic fatal-error
display.

## Mechanism (verified)

- Text at ROM `0x1215E` (not `0x1215A` as previously recorded).
  Referenced by `pea.l L01215E` at `$120F2` inside `text_blit`
  (`$12072`), whose only caller is `error_show` (`$12FA0`, call at
  `$12FA8`). The earlier search missed the reference because it
  looked for a longword pointer or `lea` — the reference is a
  `pea.l` (push effective address).
- `error_show` just pushes the code to `text_blit` and returns.
  "N seconds" is the error code printed as a decimal, not elapsed
  time.
- There are exactly 36 `jsr error_show.l` sites in the ROM, each
  pushing an immediate error-code constant.

## Code table

Guard = the condition at the call site. Verdict = whether the code
can fire in normal play (static trace; live probes noted where done).

| Code | Sites | Guard | Can fire in normal play? |
|---|---|---|---|
| `$15` (21) | `$021032` | grid cell already occupied (grid byte != `$FF` where empty expected) | No — inconsistent grid state only |
| `$16` (22) | `$020F76` | free-record scan exhausted (56 `$FFB0CC` records, none `$270F`) | No — table exhaustion only |
| `$18` (24) | `$02111A`, `$0211FA`, `$02133E`, `$025176` | `map_grid_clear` returned 0 — record index in neither 32×32 grid | No — record with no grid cell (double-remove / stale index) |
| `$19` (25) | `$023764`, `$0238AC` | grid cell not `$FF` in grid-write routines (`$FFB76C` / `$FFB36C`) | No — writing onto an occupied cell |
| `$1A` (26) | `$023BBC` | merchant-slot scan found no free slot (d4 == `$FFFF` after 56 slots) | No — merchant table full |
| `$1B` (27) | `$023BE0`, `$023BFC` | merchant record value out of range (type 1 ≥ `$1CE`, type 4 ≥ `$CA`) | No — corrupt merchant record |
| `$1C` (28) | `$02547E`, `$02572E` | merchant record low nibble == 0 (empty/uninitialised slot) | No — uninitialised slot |
| `$1D` (29) | `$025986` | merchant nibble != 1 (`sys_struct52_scan`) | No — wrong nibble |
| `$1E` (30) | `$025B72` | merchant nibble != 1 (`sys_struct52_nibble_read`) | No — wrong nibble |
| `$32` (50) | `$02BCF6`, `$02CA1A`, `$02CA4E` | merchant nibble != 1 (`shop_merchant_scan` / `item_category_of` paths) | No — wrong nibble |
| `$3C` (60) | `$021490` | combat-effect record field `+0x0E` ≥ `$24` (36) | No — out-of-range effect record |
| `$46` (70) | `$032E88` | `text_event_resolve` dispatch default: event-kind byte `$9(a6)` ≥ 6 (6 valid kinds, 0–5) | No path found — kinds are table-driven; closing needs an enumeration of kind bytes in the `$D3102` event table (open, see below) |
| `$6D` (109) | `$033960` | `combat_move_unit` returned > 0 | Open — see below |
| `$6E` (110) | `$034B1A` | `combat_move_unit` returned > `$C8` (200) | Open — see below |
| `$6F` (111) | `$034A7E` | `combat_move_unit` returned > `$C8` (200) | Open — see below |
| `$70` (112) | `$034BC4` | `combat_move_unit` returned > `$C8` (200) | Open — see below |
| `$71` (113) | `$03384A`, `$0338EC`, `$034976` | `combat_move_unit` returned > `$C8` (200) | Open — see below |
| `$C8` (200) | `$02F87C` | save bit-offset `-$2(a6)` > `$3F0` (1008) at end of `save_serialise` | **No — provably unreachable** (see proof) |
| `$E6` (230) | `$0258A4` | map-draw record already free (`$270F`) in `world_find_char_by_grid` | No — stale record |
| `$E7` (231) | `$0210F6` | map-draw record already free (`$270F`) in `map_record_remove` | No — double-remove |
| `$E8` (232) | `$0211CC` | map-draw record already free (`$270F`) in `map_place_record_step` | No — stale record |
| `$E9` (233) | `$021428` | map-draw record already free (`$270F`) in `combat_effect_apply` | No — stale record |
| `$EA` (234) | `$02131E` | map-draw record already free (`$270F`) in `map_place_record` | No — stale record |
| `$190` (400) | `$025D24` | `world_vessel_grid_value` jump-table index ≥ 4 (arg>>8 ≥ 4) | No path found — needs vessel-word high byte ≥ 4; bound on the vessel word not yet proven (open, see below) |
| `$191` (401) | `$025D84` | `world_vessel_class` jump-table index ≥ 4 (arg>>8 ≥ 4) | Same as `$190` |
| `$192` (402) | `$025DDA` | `world_vessel_mode` jump-table index ≥ 4 (arg>>8 ≥ 4) | Same as `$190` |

## `combat_move_unit` return values (for `$6D`–`$71`)

`combat_move_unit` (`$024984`) returns:

- `0` — move ok.
- `1` — placed/init paths (`$024A6A` / `$024A6E`).
- `$DC` (220) — `combat_target_check` failure (`$024AB2`).
- `$E6` (230) — attack dispatched (`$024C5E`; requires mode 7,
  i.e. vessel word high byte 3, **and** action arg `$E6`).

So `$6D` fires on any of `1` / `$DC` / `$E6`, and `$6E`/`$6F`/`$70`/`$71`
fire only on `$DC` / `$E6`. The guard call sites pass their own
`$a(a6)` action arg straight through (e.g. `$033944`, `$03382C`),
and one `$71` site (`$03381A`) skips the call entirely when the
action is 4. **Open:** which caller actions + unit states produce a
nonzero return in normal play. What would close it: a BlastEm probe
with breakpoints on the seven `$6D`–`$71` `error_show` sites during
normal play (battles, movement, vessel use) — a hit names the live
path; a long clean run bounds it. No such probe has been run.

## `$C8` — provably unreachable (static + live)

`save_serialise` (`$02F11A`) serialises the save into a 128-byte
buffer as bit fields; `-$2(a6)` accumulates the bit offset. The
check at `$02F870` fires `error_show $C8` iff the final offset
exceeds `$3F0` (1008 bits). The total is **data-independent**: every
section is fixed (each variable loop is followed by a pad to a
constant), confirmed by re-running the numbers against the ROM
constants (`$D6707` = 11, `$D671B` = 15, `$D6725` = 33, `$D674D` =
33, `$D672F` = 25; `$D66A3` table all 20):

| Section | Bits |
|---|---:|
| Header fields | 61 |
| 6 party members × 16 (14 field/sentinel + 2 ratio, either path) | 96 |
| Merchant nibble==2 members, padded to 5 × 19 | 95 |
| 6 members × 20 (item-category counts + pad) | 120 |
| `$D6707` item section (11 × 1) | 11 |
| `$D671B` item section (padded to 15) | 15 |
| `$D6725` item section (padded to 40) | 40 |
| `$D674D` item section (padded to 40) | 40 |
| `$D672F` item section (23 × 7 + pad 14; loop starts at index 2) | 175 |
| 184-bit flag bitmap + 16 pad | 200 |
| Final loop 36 × 4 | 144 |
| **Total** | **997** |

997 ≤ 1008 with 11 bits of headroom, on **every** overworld save.
Live confirmation (#276, BlastEm probe): a probe ROM called
`save_serialise` once with `$FF00AE` forced to 1 and broke at each
section boundary — offsets read 61, 157, 252, 372, 383, 398, 438,
478, 653, 853, 997, matching this table exactly; the `$02F87C`
error path was not taken and the `$02F884` pass path was.

Note for the record: an earlier hand sum of this table gave 1011
(fires on every save). That was an arithmetic slip — it counted the
`$D672F` loop as 25 iterations × 7 + pad 14, but the loop counter
starts at 2 (`move.w #$2,-$6(a6)` at `$02F776`), so it runs 23 times;
23 × 7 + 14 = 175, not 189. The live bisection caught it. The
corrected static total (997) and the live measurement (997) agree.

## Open items (what would close them)

- **`$6D`–`$71`:** live probe as above (breakpoints on the seven
  sites during normal play).
- **`$190`–`$192`:** prove the bound on the vessel word
  (`+$02BA`): enumerate all writers and show the high byte is
  always 0–3, or live-probe the three dispatchers.
- **`$46`:** enumerate the kind byte of every record in the
  `$D3102` event table and show all are 0–5.
