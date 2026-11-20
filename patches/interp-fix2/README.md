# interp-fix2 — zoom-view legs + on-screen + straight walk

Base: `rop-interp-fix.rom` (MD5 `44353892c7a006300bfae2535ad6eaf8`).
Output: `rop-interp-fix2.rom` (MD5 `30233662e411ecf0046ffc43c734c971`).

## What was wrong (Dayset's playtest of the interp-fix ROM)

In the zoom view (mode 2, overworld walk): Buc's legs do not move at all,
Buc can run behind/off the screen, and sometimes he does a zigzag walk.
The cutscene is fine (fast, normal walking, both legs moving). So the
problems are specific to the zoom view, not the cutscene.

## Diagnosis (static; full read in `.scratch-interp-fix2/REPORT.md`)

1. **Dead legs — the root cause.** Record+$A selects the figure-draw
   routine in `map_chunk_pos` (jump table at `$01BE86`): +$A=0 ->
   `hero_track`, +$A=1 -> `map_promote_record`. The interp/subcell hooks
   live ONLY in `hero_track` (`$023202`). Buc's record+$A = 1
   (probe-confirmed in the cutscene room), so Buc is drawn via
   `map_promote_record`, NOT `hero_track`. `map_promote_record` reads
   the RECORD's own template — the static template 6 in the zoom view —
   so the image never cycles and the legs don't move. In the cutscene
   his record IS a walk template (38), so the legs move there. This also
   explains every earlier "no subcell movement" playtest.
2. **Off-screen / zigzag — the camera delay is fundamentally flawed for
   the room.** It hooks ONLY the step-mode camera writes in
   `leader_spawn` (`$01C2D8`/`$01C300`), but in the room grid+$C == 0,
   so `world_reposition_leader` calls `leader_spawn(mode 6)` — the
   absolute set — on every step, writing the camera at `$01C242`/
   `$01C264` (NOT hooked) and NOT clearing `PEND_VALID`. The step-mode
   hooks fire only unpredictably, applying a STALE pending camera from
   a different step/direction — the camera jumps to the wrong cell
   (Buc off-screen) and the offset flips (zigzag). The room camera
   needs NO delay: `world_reposition_leader` only moves it when Buc is
   3+ cells from the camera centre (the L025294 dead zone), so the
   slide IS visible without a delay.

## The fix (three byte changes, no new code)

A. Hook `map_promote_record` at `$023480` (`lea.l $197B0,a0`) ->
   `jsr $FDA00.l`, routing it through the EXISTING interp blob
   (unchanged). Fixes the legs (walk template cycles), the slide
   (position interpolates), and the figure zigzag. The slide is gated
   off while a script runs, so the cutscene is unchanged.
B. Revert the camera-delay step-mode hooks to the original moves
   (`$01C2D8` -> `move.w d0,$FF0E8E.l`; `$01C300` ->
   `move.w d0,$FF0E90.l`). The camera returns to the original mode-6
   behaviour (3-cell dead zone + clamp), which keeps Buc on-screen
   and the walk straight.
C. Restore the camdelay blob region `$FDE00-$FDE7B` (124 bytes) to
   `0xFF` padding (now unreferenced).

## Build

`python3 build.py` — verifies the base ROM (MD5 + exact hook-site
bytes), applies the three changes, fixes both checksums via
`tools/checksum.py fix-all`, writes `interp-fix2.ips` (round-trip
verified) and `changed-bytes.txt`, and asserts every earlier blob
(flat/dither `$FD400`, feet fix `$FD600`, subcell `$FD800`, pacing
`$FD900`, interp `$FDA00`) and every other hook site is byte-identical
to the base. No live probes / screenshots / cadence measurements were
run (Dayset tests it himself).

## What was NOT verified

No playtest verification. In particular not verified: whether Buc's
legs animate in the zoom view, whether he stays on-screen, whether
the walk is straight, whether the slide reads as smooth in real play,
standing-still (no jitter), all four directions, direction-change
responsiveness, menu/teleport, other rooms, the cutscene (code-gated
only), or speed in real play (cell rate unchanged, 1 cell / 4 ticks;
restoring original walk speed is a separate pacing decision).
