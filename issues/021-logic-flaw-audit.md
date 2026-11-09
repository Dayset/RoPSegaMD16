# Issue #021 — Combat / XP / gold / spell tables + logic-flaw audit

**Epic 2**  
**Milestone:** M4  
**Status:** done (2026-11-09)

## Goal
Map the numbers behind the game and audit them for logic flaws.

## Acceptance
- [x] XP table, level-up, gold/shop, combat damage, spell tables located
- [x] Each `docs/overview.md` audit question answered with an address +
      a trace: proven, or killed with evidence
- [x] Debug mode (`Diags On/Off`, format string `0x023934`) reachability decided
- [x] Audit written to `docs/logic-audit.md` — no claim without evidence

## Notes
- Depends on #007, #008, #020. A suspected flaw is not a finding until
  it is reproduced.


## Result (2026-11-09)
- `docs/logic-audit.md` written. Verdicts: gold overflow PROVEN +
  reproduced (15000+17768 -> 0, boundary at 32768); negative damage
  heals PROVEN + reproduced (HP 100 -> 106); save checksum WEAK and
  its result never read; debug mode IS reachable, format string dead;
  Void trigger NOT located; `$12072` spin loop solved (harness
  artifact); giant-function dispatch mapped; `$2B240` solves the
  +0x1E/+0x22 puzzle; `$1E0A4` = opposite-direction map; `$1F296` +
  `$12FE8` command maps done (command 23 writer not found); terrain
  decoder source ~0x60400+ (0x044000-0x05FFFF killed); food/water
  routine NOT located (leads killed); DoT drains stack (-10/round +
  1 HP 1/3 chance); `$1350` pop semantics reproduced.
- Q13 SOLVED: post-harness PC=0 fault is a stack leak in the hook
  design (`jsr` + `jmp`, never `rts`) — the hook sits on the attract
  loop's VBlank spin, so the stack plummets into RAM in ~3 s. Fixed
  with `rts` in all three harness sources; fixed #007 harness still
  90/90 and runs 12 s clean. The #008 harness faults identically if
  left running (observation-window artifact, not immunity).
- Audit harness `tools/test_audit_harness.s`: 25/25 PASS.
- Corrections applied: EEPROM `$43012`/`$430F4` labels swapped
  (READ/WRITE), `$12FE8` "only 0 or 37" corrected, `docs/overview.md`
  audit list answered, `docs/logic.md` §7.3 resolved.
- ROM MD5 unchanged (`30c18fdbe2183f64702ae9f1a45d63f9`).
