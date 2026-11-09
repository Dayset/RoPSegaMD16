# Issue #027 — Combat: classic (old) vs new, switchable

**Milestone:** M7
**Epic 5** (Tribute remake)
**Status:** open

## Goal
Implement combat twice behind one switch: **old** = the original
combat, bugs and all; **new** = a fixed combat. The player can
switch between them. This is the tribute's answer to the broken/
crutched combat — preserve it, don't pretend the fix is the original.

## Acceptance
- [ ] Old combat implemented from #007's traced damage routine
  (formula, spell-only team combat, manual mode, no team movement)
- [ ] New combat implemented with the #021 flaw-audit findings fixed
  (each fix listed in the issue with the flaw it addresses)
- [ ] A runtime switch (menu or key) toggles old/new, and the current
  mode is visible to the player
- [ ] Old mode reproduces at least one known original behaviour that
  new mode changes (named in the issue, with the #007 address)

## Notes
- Background: the game itself jokes about the combat being redone
  a fifth time ($DDBD8 rec 1004: "Did someone say redo the combat
  a fifth time? I need a haircut."). Expect layered/vestigial code
  from ~5 revisions — #007 is finding which damage path actually
  runs; old mode implements THAT path, not a guessed one.
- Do NOT attribute a combat-rework story to the Jason Rubin interview
  — the word "combat" never appears in it
  (`docs/research/jason-rubin-interview-2012.md`). The in-game line
  is the only evidence.
- Owns: `tribute/combat/` (both modes + the switch). Depends on the
  spell data from #008/#029 for spell lists.

## Depends on
#007 (damage routine), #021 (flaw audit — which bugs exist), #008
(spell tables). Spec work (listing the fixes) can start now; code
waits for #007.

## Status
open


## Work done 2026-11-09 (agent session, no ROM in VM)

- **Deliverable:** docs/tribute/027-combat.md — design: classic implements the traced $3A62E dispatch + $3B1EE formula verbatim (dead distance term included); new combat = fix list N1-N5, each mapped to a #021 flaw (F1/F4/F5/flat codes/revive asymmetry); runtime switch design; acceptance proof named (D1 case: 28 classic vs 31 new).
- **Acceptance:** PARTIAL: design + fix list complete (acceptance items 1-2 on paper); no code until #023/#026. Live-combat half of the dispatch question (F9) remains open in the original-game sense but does not block the design.

**Status after this session:** in progress — partial (see below). Not marked done.
