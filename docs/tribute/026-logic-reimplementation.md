# #026 — Game-logic reimplementation spec

Status 2026-11-09: **spec complete** — `docs/logic.md` (#007) has
landed, so this issue's dependency is met; C++ implementation waits
on #023. Every formula below is verified (ROM address given);
anything else is labelled TRIBUTE or HYPOTHESIS.

## Implement exactly (verified — code wins over fan data)

| System | Rule | Source |
|---|---|---|
| Level | smallest L with XP < 100·2^L; **max level 8**; XP cap 13000 | `$2F030`, logic.md §2 |
| Max HP / Power | min(20+15·L, 140) / (L+1)·1000 | `$31958`/`$31946` |
| XP grant | on level change recompute maxes; party loop full-heals (F5 — classic keeps, see decisions) | `0x2C4E2`, logic.md §2.3 |
| Battle-end | XP/person = total/alive-party clamped [1,50]; gold to leader | `0x35600` area |
| RNG | glibc LCG, seed `$FF0072`, `rand()%n` semantics | `$12B82`, logic.md §2.5 |
| Gold | struct field, cap 15000, floor 0 | `0x2C474` |
| Prices | `$2EA92` algorithm verbatim incl. attitude ×0.64–×1.36, ×2 at (merchant-type 32, location 367), goods /2 special, clamp [2,9000], merchant-none = **0x00FF** | logic.md §3.4 |
| Buy/sell | buy `0x1FDC4`, sell `0x1FB88` (sell = price(14, slot)/2) | logic.md §3.6 |
| Attitude drift | per world tick: +5 / −4 clamped vs merchant struct fields (the `$2155E` loop) | architecture.md #020 |

## Verification targets (acceptance)

- The 21-good trading table must **reproduce from the implemented
  tables**: 20/21 fit the formula; **Gems sell 428 must NOT
  reproduce** — it is impossible under `$2EA92` (max 2.72× base).
  The test asserts the 20 fits and documents Gems as the known
  guide error / unknown alternate path (`disasm/logic/trading_check.txt`).
- Transport/food-water: **cannot be implemented as verified** —
  the consumption routine is unlocated (logic.md §3.7). Implement
  the guide's per-terrain table (foot path 1/1, grass 4/2, desert
  7/5, swamp 8/4, ice 4/3; boat shallow 1/1, deep 5/20; ship 1/1;
  dino road 1/1, other 3/1; dragon 40/40) labelled **HYPOTHESIS**
  in code, with a single table to swap when the routine is traced.

## Classic-vs-fixed decisions (recorded per #021 flaw)

F5 full-heal on XP grant: classic = reproduce; new = heal only the
levelling member (TRIBUTE choice, note in code). F6 `+0x2A`
gold/status overlap: **split fields in both modes** (data-model
bug, invisible to players). F7 `0x00FF` sentinel: implement the
correct sentinel; the −1-index path is a latent bug, not a feature.
Bribe: attitude exists, the Bribe action's effect is unlocated —
implement the walkthrough's "10 gold repairs attitude" as
HYPOTHESIS behind the same flag as food/water.
