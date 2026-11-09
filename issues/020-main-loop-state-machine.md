# Issue #020 — Main loop + game state machine

**Epic 2**  
**Milestone:** M4  
**Status:** open

## Goal
Trace the game past boot: the main loop and its state machine.

## Acceptance
- [ ] Main loop located (from `$EB772` per-frame dispatch onward)
- [ ] States identified (title, overworld, town, combat, menu, dialogue…)
      with addresses and transitions
- [ ] Where input from the VBlank joypad queue is consumed
- [ ] Written up in `docs/architecture.md`

## Notes
- Depends on #003 and #011.

