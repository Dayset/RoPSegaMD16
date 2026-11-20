# interp-fix3 — no camera yoink on a direction change; one tap turns the face

Base: `rop-interp-fix2.rom` (MD5 `30233662e411ecf0046ffc43c734c971`).
Output: `rop-interp-fix3.rom` (MD5 `8ada8b985aad8ae6c3929ae6d39d4139`).

## What was wrong (Dayset's playtest of the interp-fix2 ROM)

Holding a direction walks beautifully (smooth, subcell). But: (1) the
camera YOINKS (jerks/snaps abruptly) on a direction change; (2) after
stopping, it takes 3-4 short presses just to rotate Buc's face — a
single short press (tap) does not turn him.

## Diagnosis (static; full read in `.scratch-interp-fix3/REPORT.md`)

1. **Camera yoink — the dead-zone snap is all-or-nothing per axis
   pair.** The room camera is mode-6 (absolute set) with a 3-cell dead
   zone: `world_reposition_leader` (`$02513E`, `combat_move_unit`'s
   epilogue) takes the L0251EE path when grid+$C == 0 (room), and the
   L025294 block computes |dX| and |dY| from the camera centre. If
   EITHER is >= 3 it leaves the target as Buc's cell on BOTH axes; if
   both are < 3 it keeps the current camera on both axes. When Buc
   turns (e.g. east -> north), his X offset is whatever it drifted to
   while walking east (0, 1 or 2), and his Y offset grows to 3 — so the
   camera snaps diagonally by (Xoffset, 3). That diagonal snap is the
   yoink (it fires ~2/3 of turns).
2. **Face rotation — the pacing gate discards the tap.** Path A pops
   the queued direction every tick, and the v1 pacing gate discards ANY
   popped direction when grid+$A != 0 (phases 1-3), before the dir==4
   check. A brief tap lands on phase 0 only 1 time in 4, so a single
   tap to turn is discarded ~75% of the time; the queue is drained by
   the pop, so a discarded tap is LOST. But `combat_move_unit` updates
   Buc's heading (+0x0A, `$FF02F2`) to the new direction even when the
   step is blocked (the heading write at `$024D76` is in the shared
   epilogue) — so a tap in a NEW direction turns the face in one press,
   IF the move reaches `combat_move_unit`.

## The fix (two halves of the same direction-change problem)

A. **Camera — per-axis snap.** Hook `world_reposition_leader`'s
   L025294 block at `$02529C` (`sub.w $FF0E8E,d0`) -> `jsr $FDE00.l`.
   The new blob (102 bytes at `$FDE00`, the old camdelay region) sets
   the target per axis: an axis that has not crossed the 3-cell dead
   zone keeps the current camera on that axis; only the axis that
   crossed moves to Buc's cell. A north turn now moves the camera
   purely north. Gated to mode 2 AND no script, so the cutscene keeps
   the original snap. The blob jumps to the clamp at `$025300`; the
   clamp + `leader_spawn(mode 6)` call run exactly as before on the
   per-axis target. Buc stays on-screen (the non-snapped axis keeps
   him within 2 cells of the centre).
B. **Face — a turn always goes through.** Replace the v1 pacing blob
   at `$FD900` in place (58 bytes; the `$0228CC` hook already points
   there, no hook-site change). The v2 blob adds a turn check BEFORE
   the phase gate: if the popped direction (-$E(a6)) differs from
   Buc's heading (`$FF02F2`), the move goes through immediately (turn),
   no phase check. Same-direction moves keep the v1 phase gate, so the
   walk pace (1 cell / 4 ticks) and the slide are unchanged. The dir==4
   stop sentinel still works (it takes the allow path, the displaced
   `cmpi.w` sets the flags, Path A's `beq` skips the move).

Known minor artifact (stated, not hidden): a turn commits the cell
mid-phase, so the interp slide starts at that phase's offset (e.g. a
turn at phase 2 starts halfway) — Buc jumps about half a cell, then
slides the rest. The legs still cycle and the face turns in one press.

## Build

`python3 build.py` — assembles both blobs with vasm (addresses parsed
from the listings, never hardcoded), verifies the base ROM (MD5 + exact
hook-site bytes + free 0xFF padding in both blob regions), writes the
blobs and the cam hook, fixes both checksums via
`tools/checksum.py fix-all`, writes `interp-fix3.ips` (round-trip
verified) and `changed-bytes.txt`, and asserts every earlier blob
(flat/dither `$FD400`, feet fix `$FD600`, subcell `$FD800`, interp
`$FDA00`) and every other hook site is byte-identical to the base. No
live probes / screenshots / cadence measurements were run (Dayset
tests it himself).

## What was NOT verified

No playtest verification. In particular not verified: whether the
camera moves purely along the new direction on a turn (no diagonal
jump), whether a single tap rotates Buc's face, whether holding a
direction still walks beautifully (smooth, subcell), whether the legs
/ slide / on-screen / straight-walk from interp-fix2 stay intact,
standing-still (no jitter), all four directions, menu/teleport, other
rooms, the cutscene (code-gated only), or speed in real play (cell
rate unchanged, 1 cell / 4 ticks; restoring original walk speed is a
separate pacing decision).
