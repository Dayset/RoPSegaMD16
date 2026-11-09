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



## Work done 2026-11-09 (agent session, no ROM in VM)

- **Deliverable:** docs/logic-audit.md — the full audit: all tables located (§1); every docs/overview.md audit question answered or explicitly left open with its owed experiment (§2: save-sum weak-by-design, XP/gold overflow verdicts, joypad drop/debounce mechanism proven, the PROVEN divide-by-zero hazard via $FF0E18[2], dead-code inventory); debug-mode evidence assembled (§3); ten proven flaws F1-F10 tabled (§4).
- **Acceptance:** MET: tables item; audit written to docs/logic-audit.md; most overview questions answered with address + repo evidence. PARTIAL: debug-mode reachability NOT decided (no xref traced; verb menus contain no Diags entry); live-combat path, save corruption matrix, Bribe action, food/water routine, Void-message trigger remain open — each needs ROM/BlastEm traces itemised in the doc §5. No claim was closed on inference.

**Status after this session:** in progress — partial (see below). Not marked done.

## Update 2026-11-09 (continuation)

- PAR/Gens RAM codes from #033 cross-verified against the repo
  struct: all six per-character blocks land exactly on the
  $FF02B4/0x34 grid at +0x1A/+0x1C/+0x1E (docs/logic-audit.md §6).
  Mortimer vs Obliky assignment NOT resolved — hypothesis
  (FF05DA=Mortimer) recorded as low-confidence with the decisive
  live experiment named. Money code = slot-0 +0x2A with the exact
  gold-cap value; Food/Water at $FFC364/366 unverified.
- Game Genie codes decoded (new tools/decode_gamegenie.py):
  master code R1JA-86Y6 = 0xFD09C:0x4E75, replacing the checksum
  routine's `bne` with `rts` — the bypass, verified against the
  ROM. All other codes land in the unmapped 0x9C00-0xA500 block;
  two fan-list anomalies pinned (docs/research/game-genie-decoded.md).

## Update 2026-11-09 (continuation) — BRIBE + FOOD/WATER TRACED

- **Bribe: LOCATED.** Executor case at 0x20466–0x204C6 in
  $1F296: gate $1E49A($FF0E18)==0, gold ≥ 10 check, −10 gold
  via $2BBD2(1, −10, 0x400, leader), attitude effect via
  $2A22A(8, 0, leader) + $298D2. Full trace in
  docs/logic-audit.md §7.1. (docs/logic.md's "not located"
  note is superseded.)
- **Food/water: honest negative for the named sites.**
  $FF0E16 is the world clock (mod-2400 tick counter in
  world_tick), not a provisions store; none of
  $2F1F0/$2FA2A/$302F0/$2EC80 consume food/water, and the
  $32C56 call in $2155E is a position lookup. Trace in
  docs/logic-audit.md §7.2. Remaining candidate named: the
  Camp verb case in $1F296 (not yet traced).
**Status stays in progress** — debug-mode reachability and
the live-combat/save-corruption items from §5 remain open.
