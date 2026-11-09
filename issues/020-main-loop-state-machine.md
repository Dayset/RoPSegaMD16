# Issue #020 — Main loop + game state machine

**Epic 2**  
**Milestone:** M4  
**Status:** done (2026-11-09)

## Goal
Trace the game past boot: the main loop and its state machine.

## Acceptance
- [x] Main loop located (from `$EB772` per-frame dispatch onward)
- [x] States identified (title, overworld, town, combat, menu, dialogue…)
      with addresses and transitions
- [x] Where input from the VBlank joypad queue is consumed
- [x] Written up in `docs/architecture.md`

## Notes
- Depends on #003 and #011.

## Done — what was delivered
- `docs/architecture.md`: new "Main loop + game state machine"
  section. `$D28E` (0xD28E–0xD9DE) is the eternal main loop;
  loop-back `tst $FF00BE; beq $D2BE`, exit only via `$FF00BE=-1`
  (set at one site, 0x20188, inside the `$1F296` verb executor)
  → `$179B6` soft reset → `$200`. The seven `$D25C` callees
  identified; `$1B5D6` new-game init traced (confirms the
  `$FF0E18[2]` capacity-8 initialiser at 0x1B5DA via
  `$1E390`); `$23B84` entity spawner + 24-byte templates at
  `$CF1AC` traced; `$D28E` command switch at `$D740`
  re-verified (15 cases); `$12FE8` menu/verb input decoder
  traced; `$1350` joypad-pop call sites mapped (16);
  `$2155E` per-frame world tick traced (step counter
  `$FF0E16`, palette fades via `$170DA`, merchant attitude
  drift); verb table at 0xCCDB8 re-parsed (14-byte items,
  12-byte headers; six disciplines named in ROM).
- `disasm/main-loop/`: `verb_menus.txt`, `d28e_switch.txt`,
  `entity_templates.txt`, `README.md`.
- Open threads carried to #021: verb-table (A,B,C,grp) →
  `$D28E` switch-code mapping; full `$1F296` case map; where
  `+0x14` gets the party names 57–62 (leader is created as
  template 0 "Man"); food/water consumption routine (narrowed
  to `$FF0E16` readers); terrain-grid stream source +
  `$FF1EC0` consumers (decoder mechanism at 0xE3B4/0xE412 now
  documented); live-combat half of #007 Q1 (needs a
  save-state/input driver — not attempted headlessly, no
  credible path with the harness pattern alone).
- ROM untouched (MD5 `30c18fdbe2183f64702ae9f1a45d63f9`
  re-verified at close).

