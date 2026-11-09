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
