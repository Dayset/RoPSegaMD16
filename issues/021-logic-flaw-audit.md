# Issue #021 — Combat / XP / gold / spell tables + logic-flaw audit

**Epic 2**  
**Milestone:** M4  
**Status:** open

## Goal
Map the numbers behind the game and audit them for logic flaws.

## Acceptance
- [ ] XP table, level-up, gold/shop, combat damage, spell tables located
- [ ] Each `docs/overview.md` audit question answered with an address +
      a trace: proven, or killed with evidence
- [ ] Debug mode (`Diags On/Off`, format string `0x023934`) reachability decided
- [ ] Audit written to `docs/logic-audit.md` — no claim without evidence

## Notes
- Depends on #007, #008, #020. A suspected flaw is not a finding until
  it is reproduced.

