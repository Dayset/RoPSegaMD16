# cutscene-loop — drive Buc in a loop during the Buc cutscene

## What Dayset asked for

Walk further than the cutscene allows — 20 cells south, 20 east, 20 north,
20 west — so he can see the walk from all four directions. In the cutscene,
after that he doesn't care if Thalmus is angry (the scripted path and
Thalmus's moves may break; the dialog and Thalmus's moves run as normal,
but Buc's position is driven by the loop).

## The full 20-cell loop does NOT fit

The room (location 156, chunk 233) is a 32x32 **maze**, not an open floor.
Chunk 233 was decoded (`tools/decode_chunks.py`) and walkability mapped
(terrain 5/9/18 or tile $24, no height stack, no step-tile, no hazard;
verified against the doc's known cells). Results:

- A 20x20 square loop from Buc's start (6,17) is impossible: south runs
  out of bounds at Y=37, and the room's south wall is at Y=29.
- The largest fitting **rectangle** from (6,17) avoiding the students is
  only **7x2** (7 south, 2 east, 7 north, 2 west). Even ignoring the
  students it is only 11x2.
- Straight runs from (6,17): south 8 cells (to Yoppa at (6,25)),
  east 3 (to Thalmus at (9,17)), north 14, west 0 (wall).

So instead of a fixed square, Buc walks **up to 20 cells per leg** in the
order S,E,N,W (Dayset's "20 down, 20 right, 20 up, 20 left") and **turns
to the next direction when blocked** (wall/student) or after 20 steps.
He walks each direction as far as the room allows, keeps moving (no long
stands on blocked legs), and the loop repeats while the cutscene is
active. The full 20-cell square loop does not fit; the 20-cell leg length
is kept as the per-leg maximum.

## Mechanism — two hooks, on top of the feet-fix ROM

Base: `rop-flat-zoomed-feet.rom` (MD5
`9373c0d01cf08c20f28e256daa9ea142`) — flat only on mode 2, feet fix.
The flat gate and the feet fix are untouched; the big world stays
textured. Blob 266 bytes at `$FD800` (free 0xFF padding).

### Hook 1 — loop driver, `sys_event_run $02D56E`

Replaces `tst.w $FF010A.l` (6 bytes, `4a79 00ff010a`) with
`jsr loop_drive`. While the Buc cutscene is active, steps Buc one cell
along the loop via `combat_move_unit(1, dir)`, once per `sys_event_run`
call (one cell per 4 ticks, the script's pace). It sits **before**
`sys_event_run`'s `$FF010A==0` early return, so Buc keeps walking even
while a dialog message is on screen (the hook runs on every
`sys_event_run` call, stalled or not). The displaced `tst.w $FF010A.l`
is re-executed last, so the `bne` at `$02D574` reads the correct flags.
All registers are saved/restored (`movem.l d0-d7/a0-a6`).

Gate: `$FF0110 != 0` AND script pointer `$FFC384` in `[$1A228, $1A390]`.
On the first call (pointer == `$1A228`) the state is reset (dir=S,
step=0) and the move is skipped (the op-1 teleport runs in the same
call, placing Buc at (6,17)).

A leg ends after 20 steps OR when Buc is blocked (his X/Y unchanged by
`combat_move_unit`); on a block Buc turns immediately. Next direction =
(dir+3) mod 4, giving the order S(2),E(1),N(0),W(3).

### Hook 2 — suppress the script's Buc moves, op-5 handler `$02D7F6`

Replaces `jsr combat_move_unit.l` (6 bytes, `4eb9 00024984`) with
`jsr loop_op5`. If the move is for Buc (char 1) and the Buc cutscene is
active (pointer in `[$1A228, $1A390]`), it returns without moving
(the op-5 handler then pops its args and advances the script pointer
normally). Otherwise it tail-calls the real `combat_move_unit` with
`jmp` (the stack already holds ret/char/dir exactly as a direct `jsr`
would). This keeps the loop's step count in sync with Buc's position —
without it the script would move Buc a second cell in the same tick.
Thalmus's moves (char 3) and other scripts are unaffected. Only d0 is
used (scratch).

The camera follows Buc through `combat_move_unit`'s epilogue
(`world_reposition_leader` → `leader_spawn`), exactly as it does for
the script's own moves — Buc passes the camera gate
(`(type>>4)&0x3F == 0`).

## Loop state (RAM)

Free: not in `disasm/symbols/ram.csv`; not the feet-fix list
`$FFD800/$FFD802`; not the subcell latch `$FFD000-$FFD006`.

- `$FFD100`: loop_dir (word) 0=N,1=E,2=S,3=W. Start 2 (S).
- `$FFD102`: loop_step (word) steps taken in the current leg (0..19).

## Build

```
python3 build.py
```

Reads `rop-flat-zoomed-feet.rom` (MD5 verified), assembles with vasm,
parses entry addresses from the listing (never hardcoded), verifies the
patch sites, writes the blob, patches the 2 sites, fixes both checksums,
emits `changed-bytes.txt` + `cutscene-loop.ips` (round-trip verified),
asserts the flat/feet blobs are untouched and the original ROM is
unchanged. Output: `rop-cutscene-loop.rom`.

## Result

- ROM: `rop-cutscene-loop.rom`, MD5
  `79bccdcd927707802332f64f38faa641` (header 0x1A9D, runtime 0xA15C806B).
- 258 bytes differ from `rop-flat-zoomed-feet.rom` (blob + 2 hook sites
  + both checksums). IPS 406 bytes, round-trip verified.
- `loop_drive $FD800`, `loop_op5 $FD8E2`, blob `$FD800-$FD909`
  (266 bytes). Listing hand-verified instruction by instruction
  (all branch displacements land exactly; the movem masks are the
  correct complementary encodings for predecrement/postincrement).

## What was NOT verified

No live tests (Dayset is the tester): no probes, screenshots, cadence
measurements, or playtest verification. In particular not verified:
whether Buc actually walks the loop in real play, whether the camera
follows him around the loop, whether the dialog/Thalmus's moves still
run, whether the students get picked up as followers (Buc may step
onto a student's cell — the "pickup" path — which would make that
student follow him), how far Buc gets before the script ends (the loop
repeats, but the script's ~22 record-executing calls plus dialog stalls
set how many cells he covers — lingering at the dialogs lets him cover
more), or the walk in other rooms. The flat gate (mode 2 only) and the
feet fix are byte-identical to the base, so the render path is unchanged.
