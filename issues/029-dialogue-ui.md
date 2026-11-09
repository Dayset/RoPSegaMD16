# Issue #029 — Dialogue & UI (verb list, dialogue, menus)

**Milestone:** M7
**Epic 5** (Tribute remake)
**Status:** open

## Goal
Recreate the game's interface in the tribute: the fixed verb list,
dialogue display (from the decoded dictionary text), menus (Music
menu, status, inventory), and the sextant coordinate readout.

## Acceptance
- [ ] Verb list implemented (talk / show inventory / bribe / buy /
  sell / pick a fight, as in the original interface) and working
  against placeholder NPCs
- [ ] Dialogue displays from the exported #004 text data (1,184
  records + dictionary) with the original's line behaviour
- [ ] Sextant readout shows coordinates in the original format
  (degrees-minutes, as in locations.htm) once the player has the
  sextant
- [ ] Music menu present (it is where the original's Quiet option
  lives — see the music-off patch in `patches/music-off/`)

## Notes
- Builds on #004 (dictionary, `$136FC`, 3,466 words, 1,184 records).
  The dialogue blob is tokenised, not plain text — the UI must use
  the #024 export, not the raw ROM.
- The original interface never changes regardless of who Buc talks
  to — keep that property (one verb list everywhere).
- Known quirk to reproduce or note: the player can pick a fight with
  anyone, including quest-critical NPCs (the "doomed world you have
  created") — decide in the issue whether classic mode keeps it and
  say so.
- Owns: `tribute/ui/` (verbs, dialogue, menus, HUD). Do not touch
  game logic (#026) — call its hooks.

## Depends on
#004 (done), #024 (text export). Start now.

## Status
open


## Work done 2026-11-09 (agent session, no ROM in VM)

- **Deliverable:** docs/tribute/029-dialogue-ui.md — spec from #020's verb table (MAIN/FIGHT/MOOD/PARTY/TACTIC/shop sets verbatim, incl. Feather-not-Arrow and the Keys/Rings C-value anomaly), dialogue display rules from #004 (dictionary export only, queue capacity initialised — F10 not reproduced), sextant readout format + sextant-item gating, Music menu with a WORKING Quiet, and the fight-anyone quirk decision (kept in both modes).
- **Acceptance:** PARTIAL: spec complete; implementation waits on #023 + #024 text export (dialogue.json).

**Status after this session:** in progress — partial (see below). Not marked done.
