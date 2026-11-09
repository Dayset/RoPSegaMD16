# Issue #026 — Game logic reimplementation (stats/XP/gold/shops)

**Milestone:** M7
**Epic 5** (Tribute remake)
**Status:** open

## Goal
Implement the game's core logic in C++ in the tribute, from the RE
spec — not from memory of playing it: stats, XP/level, gold, shop
buy/sell, food/water consumption, transport costs. Every behaviour
is either verified (traced to a ROM address in `docs/logic.md`) or
labelled tribute.

## Acceptance
- [ ] XP/level curve implemented from the #007 XP table/routine
- [ ] Gold + shop arithmetic implemented; the trading table in
  `docs/research/ringsofpower-co-uk-guides.md` (21 goods, buy/sell
  cities and prices) reproduces from the implemented tables
- [ ] Food/water consumption implemented; the transport table
  (per-terrain and per-craft food/water costs) reproduces
- [ ] A test scene (or unit tests) showing each table reproducing
  from the implementation, not hard-coded

## Notes
- The trading/transport tables are player-observed (fan site) — they
  are verification targets, not the source of truth. The source of
  truth is #007's traced routines; where fan data and code disagree,
  the code wins and the disagreement is noted in the issue.
- Known open questions from #021 (overflows, edge cases) apply here:
  a reimplementation must decide per case whether to reproduce the
  original bug (classic) or fix it (new) — and record the decision.
- Owns: `tribute/logic/` (stats, economy, survival). Do not touch
  combat (#027) or the UI (#029) — expose function hooks for them.

## Depends on
#007 (in progress — do not start implementation until `docs/logic.md`
lands; reading the fan-site tables to prepare is fine). #008 for
spell-related costs if they overlap.

## Status
open


## Work done 2026-11-09 (agent session, no ROM in VM)

- **Deliverable:** docs/tribute/026-logic-reimplementation.md — full spec from docs/logic.md (dependency now met): verbatim formulas with addresses (XP/level/HP/Power/prices/buy/sell/RNG/attitude drift), the trading-table verification rule (20/21 reproduce; Gems 428 must NOT), food/water implemented as a labelled HYPOTHESIS table (routine unlocated), and per-flaw classic/fixed decisions (F5/F6/F7).
- **Acceptance:** PARTIAL: spec complete; C++ implementation + test scene wait on #023. Food/water + Bribe remain hypotheses until the ROM routines are traced (see logic-audit §5).

**Status after this session:** in progress — partial (see below). Not marked done.
