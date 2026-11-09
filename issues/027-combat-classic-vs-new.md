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
