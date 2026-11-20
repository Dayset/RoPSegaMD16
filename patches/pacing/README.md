# Pacing gate — subcell movement in the B-zoom view

One fix only, on top of `rop-dither.rom` (flat checkerboard only on mode 2,
feet fix, subcell template override): the leader figure's (Buc, char 1)
cell commits once per 4 ticks (phase 3→0 wrap) instead of every tick, so
the subcell walk-template offsets interpolate across the cell instead of
the figure jumping a whole cell per tick.

## Diagnosis (static, from `disasm/src/rop.s`)

- `world_tick` `$02155E`: grid+$A = (old+1) mod 4; `$FF0094 = phase mod
  grid+$8`.
- `new_game_init` `$01B5D6`: grid+$8 = 1 for the overworld (`$FFB08C`) and
  the room grids `$FFB09C` / `$FFB0AC`, and 4 only for `$FFB0BC`. The
  B-zoom room (location 30) uses `$FFB09C`, so `$FF0094 = phase mod 1 = 0`
  always.
- `combat_turn_run` `$022790`: the per-char movement loop runs only when
  `$FF0094 == 0` — in the room that is every tick.
- Path A (`$022826`, mode 2): pops the leader's queued direction and calls
  `combat_move_unit` (`$024984`), which commits the cell (writes char X/Y
  at `$024CE8`–`$024D64`), with no phase gate. So Buc's cell commits every
  tick — the figure jumps a full cell per tick and the subcell template
  only adds a ±6 px wobble. This is the "every tick" case the subcell
  report predicted, now proven statically.
- The cutscene is smooth because `sys_event_run` runs only at grid+$A == 0
  (`$022764` gate) and the movement block is skipped while a script runs
  (`$FF0110 != 0`, `$0227C6`), so Buc moves one cell per 4 ticks via op-5.
- Precedent: the NPC wander path (`$022B56`) already gates its
  `combat_move_unit` call on grid+$A == 0.

## Design

Hook at `$0228CC` (`cmpi.w #$4,-$e(a6)`, 6 bytes) → `jsr pace_gate` (blob
at `$FD900`, 0xFF padding). The blob:

- reads grid+$A (`ram_map_grid_base` `$FFA7FC`, +`$A`);
- if phase != 0, discards the `jsr` return address and jumps to `$022960`,
  the block's standard skip exit (same as the dir==4 skip);
- if phase == 0, executes the displaced `cmpi.w` and returns to `$0228D2`,
  so the dir==4 check and the move proceed exactly as before.

The hook sits AFTER `queue_pop`, so the direction queue still drains
every tick — no accumulation, no direction-change lag (the queue is a
34-entry FIFO that drops pushes when full, so gating before the pop
would have stalled direction changes). The move itself only happens on
phase-0 ticks. A brief tap during phases 1–3 is discarded; holding a
direction walks one cell per 4 ticks, as in the cutscene.

Unaffected: the cutscene (the movement block is skipped while `$FF0110 !=
0`, so the hook never fires during a script), the overworld (Path A only
runs in mode 2), the turn effects, the NPC/follower placement, the record
stepper (`$022F52`), and the projectile stepper (`$02309C`) — all still
run every tick. The flat/checkerboard, the feet fix, and the subcell
override are untouched (blobs and hook sites byte-identical to the base).

## Build

`python3 build.py` — assembles `source.s` with vasm (stub address parsed
from the listing, never hardcoded), verifies the hook-site bytes, writes
the blob + hook, fixes both checksums with `tools/checksum.py fix-all`,
and emits `pacing.ips` (round-trip verified) + `changed-bytes.txt`.

## Files

- `rop-pacing.rom` (in `~/workspace/rop-work/pacing/`)
- `source.s`, `build.py`, `README.md` (this file), `changed-bytes.txt`,
  `pacing.ips`
- Report: `~/workspace/rop-work/pacing/.scratch-pacing/REPORT.md`

## Not verified

No live tests were run for this build (Dayset's rule: he tests it
himself). In particular NOT verified: whether the movement reads smooth
in real play, standing-still (no jitter), all four directions,
menu/teleport, other rooms, the cutscene room, or the speed in real play.
