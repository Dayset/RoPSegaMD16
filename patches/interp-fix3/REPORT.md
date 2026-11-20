# interp-fix3 — direction-change camera yoink + face-rotation sluggishness

Base: `rop-interp-fix2.rom` (MD5 `30233662e411ecf0046ffc43c734c971`).
Output: `rop-interp-fix3.rom` (MD5 `8ada8b985aad8ae6c3929ae6d39d4139`).
Worktree: `~/workspace/rop-work/interp-fix3/`.
Patch: `patches/interp-fix3/` (`pace.s`, `camsnap.s`, `build.py`,
`README.md`, `changed-bytes.txt`, `interp-fix3.ips` — IPS round-trip
verified: base + IPS == ROM exactly).

Dayset's playtest of the interp-fix2 ROM (2026-11-12 ~23:34 EST):
holding a direction walks beautifully (smooth, subcell), but (1) the
camera YOINKS (jerks/snaps abruptly) on a direction change, and (2)
after stopping, it takes 3-4 short presses just to rotate Buc's face
— a single short press (tap) does not turn him.

One fix only: the two direction-change problems, fixed on top of the
interp-fix2 ROM. The flat / checkerboard, feet fix, subcell override,
interp slide, and map_promote_record hook are byte-identical to the
base. Big world stays textured. Cell rate unchanged (1 cell / 4
ticks). Cutscene unchanged.

No live probes, screenshots, cadence measurements, or playtest
verification were run for this build (Dayset's rule: he tests it
himself). Diagnosis is static, from the disassembly (`disasm/src/rop.s`)
and the interp-fix2 / pacing reports, plus ROM-byte verification of
every hook site and blob. The original ROM is untouched (MD5
`30c18fdbe2183f64702ae9f1a45d63f9`, re-verified).

## 1. Diagnosis — the camera yoink

### The room camera mechanism (interp-fix2, re-read)

`world_reposition_leader` (`$02513E`) is `combat_move_unit`'s
epilogue. It runs after every Buc step. In the room (grid+$C == 0) it
takes the L0251EE path:

```
$02513E: link.w a6,#$fff2
         ... map_grid_clear writes Buc's new cell to -$6(a6) (X), -$4(a6) (Y)
$02517E: movea.l ram_map_grid_base.l,a0
         tst.w $c(a0)                 ; grid+$C
         beq.b L0251EE                ; == 0 (room) -> L0251EE
         ... overworld path (leader_spawn mode 5 loop) ...
L0251EE:
$0251EE: clr.w -$8(a6)
$0251F2: move.w $FF0E8E,-$a(a6)       ; -$a = camX
$0251FA: move.w $FF0E90,-$c(a6)       ; -$c = camY
$025202: move.w $a(a6),d0             ; dispatch index (from combat_move_unit)
         ext.l d0
         bra.w L0253A8                ; jump-table dispatch, 5 cases
```

The dispatch selects one of five blocks (L02520C / L025228 /
L025250 / L02526C / L025294). Four are edge checks that set
-$8(a6)=1; the fifth, L025294, is the dead-zone check. The
interp-fix2 report already established that the room camera only
moves when Buc is 3+ cells from the camera centre; this read pins
down exactly how, and why a direction change yoinks.

### The L025294 block, read in full (rop.s, $025294-$0252F8)

```
$025294: clr.w -$8(a6)
$025298: move.w -$6(a6),d0            ; d0 = BucX (target X)
$02529C: sub.w $FF0E8E,d0             ; d0 = BucX - camX
$0252A2: tst.w d0
$0252A4: bge.b L0252B4
$0252A6: move.w -$6(a6),d0
$0252AA: sub.w $FF0E8E,d0
$0252B0: neg.w d0
$0252B2: bra.b L0252BE
$0252B4: move.w -$6(a6),d0
$0252B8: sub.w $FF0E8E,d0
$0252BE: cmp.w #$3,d0                 ; |dX| >= 3?
$0252C2: bge.b L025300                ; yes -> clamp, target = Buc's cell (BOTH axes)
$0252C4: move.w -$4(a6),d0            ; d0 = BucY
$0252C8: sub.w $FF0E90,d0             ; d0 = BucY - camY
$0252CE: tst.w d0
$0252D0: bge.b L0252E0
$0252D2: move.w -$4(a6),d0
$0252D6: sub.w $FF0E90,d0
$0252DC: neg.w d0
$0252DE: bra.b L0252EA
$0252E0: move.w -$4(a6),d0
$0252E4: sub.w $FF0E90,d0
$0252EA: cmp.w #$3,d0                 ; |dY| >= 3?
$0252EE: bge.b L025300                ; yes -> clamp, target = Buc's cell (BOTH axes)
$0252F0: move.w $FF0E8E,-$6(a6)       ; both < 3: target = current camera (BOTH axes)
$0252F8: move.w $FF0E90,-$4(a6)
$025300: (clamp; then leader_spawn(mode 6, targetX, targetY) at $025394)
```

The snap is **all-or-nothing per axis pair**: if EITHER |dX| or |dY|
is >= 3, the target is Buc's cell on BOTH axes; if both are < 3, the
target is the current camera on both axes. There is no per-axis
decision anywhere in the block.

### Why a direction change yoinks

Walk east: the camera re-centres on Buc only every 3rd east step,
so between snaps Buc's X offset from the camera centre is 0, 1, or 2
(uniformly, depending on when he turns relative to the last snap).
Turn north and hold it: his Y offset grows 1, 2, 3 as he walks
north, while his X offset stays at whatever it was (1 or 2). The
moment |dY| hits 3, the camera snaps to Buc's cell on BOTH axes —
a **diagonal** jump of (Xoffset, 3): 1-2 cells sideways plus 3 cells
up. That diagonal snap is the yoink Dayset sees. It fires on ~2/3 of
turns (whenever the X offset is 1 or 2 at the turn); a turn made
exactly on a re-centre (X offset 0) snaps purely north and reads
fine, which is why it is intermittent rather than constant.

It is NOT a stale pending camera (the interp-fix camera delay was
already reverted in interp-fix2, and the mode-6 writes at
`$01C242`/`$01C264` are unhooked original moves — verified in the
base ROM). It is NOT the slide/camera interaction (the slide is
room-relative and the camera tracks the committed cell; the slide
itself is smooth). It is the dead-zone logic snapping both axes at
once. The fix is to make the snap per-axis.

### The fix — per-axis snap (blob at $FDE00, hook at $02529C)

Hook site: `$02529C`, `sub.w $FF0E8E,d0` (6 bytes, verified in the
base ROM as `90 79 00 ff 0e 8e`) -> `jsr $FDE00.l`. The hook is
inside the L025294 block, so it fires exactly when the dead-zone
check runs (the four edge-check blocks never reach `$02529C`).

The blob (`camsnap.s`, 102 bytes at `$FDE00`, the old camdelay
region restored to 0xFF by interp-fix2):

- Gate: mode 2 AND no script (`$FF0110 == 0`). The cutscene keeps
  the original all-or-nothing snap (unchanged). The L025294 block is
  only reached on the room path (grid+$C == 0), so the overworld is
  untouched by construction.
- Per-axis target: if |BucX - camX| < 3, targetX = camX (keep X);
  else targetX = BucX (already in -$6(a6)). Same for Y with camY /
  -$4(a6). Only the axis that crossed the dead zone moves to Buc's
  cell. A north turn after walking east now moves the camera purely
  north (0, 3); the sideways offset stays put until Buc actually
  drifts 3 cells sideways.
- After setting the per-axis target it discards the jsr return
  address (`addq.l #4,a7`) and jumps to `$025300` (the clamp),
  bypassing the rest of the dead-zone logic. The clamp and the
  `leader_spawn(mode 6, targetX, targetY)` call at `$025394` then run
  exactly as before, on the per-axis target.
- -$8(a6) stays 0 (cleared at `$025294`, nothing here sets it), so the
  extra `leader_spawn` call at `$0253F2` is skipped, as in the
  original path.
- Gated out (mode != 2 or a script running): executes the displaced
  `sub.w $FF0E8E,d0` and returns to `$0252A2` (rts) — the original
  code runs untouched.
- Buc can never go off-screen from this: the non-snapped axis keeps
  him within 2 cells of the camera centre (the dead zone is 3), and
  the snapped axis centres him. The room is ~36x23 cells; he stays
  well inside the window.
- Registers: saves/restores d0 only (movem); a6 untouched (it is
  `world_reposition_leader`'s frame pointer; -$6/-$4 are the target).
  The clamp reloads d0/d1/a0 from memory, so nothing else needs
  preserving. The `jmp $025300.l` is the deliberate bypass, the same
  pattern the pacing gate uses for its skip path — never a jmp on a
  path that must return.

## 2. Diagnosis — the face-rotation sluggishness

### The pacing gate discards the tap (pacing report, re-read)

Path A (`$022826`, mode 2) pops the leader's queued direction every
tick, then hits the pacing hook at `$0228CC` (which replaced
`cmpi.w #$4,-$E(a6)` with `jsr $FD900.l`). The v1 pacing blob
(`$FD900`, 34 bytes):

```
pace_gate:
    movem.l a0,-(a7)
    movea.l $FFA7FC,a0
    tst.w $A(a0)                  ; phase (grid+$A, 0-3)
    movem.l (a7)+,a0
    bne pace_skip                 ; phase != 0: discard
    cmpi.w #$4,-$E(a6)            ; displaced instruction
    rts
pace_skip:
    addq.l #4,a7
    jmp $022960.l                 ; Path A block's standard skip exit
```

The gate discards ANY popped direction when grid+$A != 0 (phases
1-3), BEFORE the dir==4 check. A brief tap lands on phase 0 only 1
time in 4, so a single tap to turn is discarded ~75% of the time.
The hook sits AFTER `queue_pop`, so the direction queue is drained
by the pop — a discarded tap is LOST, it does not stay queued.
That is exactly Dayset's symptom: 3-4 short presses to rotate the
face (each tap has a ~25% chance of landing on phase 0).

### A turn updates the heading even when the step is blocked

`combat_move_unit` (`$024984`) is what Path A calls after the gate.
It commits the cell (writes char X/Y at `$024CE8-$024D64`) AND
updates Buc's heading. The heading write, read in rop.s:

```
$024CE8: tst.w d4
$024CEA: beq.b L024D68              ; d4 == 0 (no step): skip the X/Y write
$024CEC: ... X/Y commit ($024CEC-$024D64) ...
L024D68:
$024D68: move.w -$34(a6),d0         ; d0 = char index
$024D6C: muls.w #$34,d0
$024D70: lea.l $FF02BE,a0           ; char struct +0x0A base
$024D76: move.w d6,(a0,d0.l)        ; char[char].+0x0A = d6 (the facing, 0-3)
```

`$FF02BE` is the char struct base (`$FF02B4`) + 0x0A, so
`$FF02F2` is char 1 (Buc) +0x0A — the same `BUC_DIR` the interp
blob reads. The heading write is in the shared epilogue, reached
via the d4==0 skip as well as the step path — so a tap in a NEW
direction turns Buc's face in one press even when the cell ahead is
blocked (a wall). The only reason the tap does not turn him is the
pacing gate discarding it before `combat_move_unit` ever runs.

### The fix — a turn always goes through (pacing blob v2, $FD900)

The v2 blob (`pace.s`, 58 bytes at `$FD900`) REPLACES the v1 blob
in place — same address, grown into the free 0xFF padding at
`$FD922+`. The hook at `$0228CC` already points to `$FD900`, so
there is no hook-site change for this half.

```
pace_gate:
    movem.l d0-d1/a0,-(a7)
    move.w -$E(a6),d0              ; d0 = popped direction (0-4)
    move.w $FF02F2,d1              ; d1 = Buc's heading
    andi.w #3,d1                   ; mask heading to 0-3 (safety)
    cmp.w d1,d0
    bne pace_allow                 ; different direction = turn: allow
    movea.l $FFA7FC,a0
    tst.w $A(a0)                   ; phase (grid+$A, 0-3)
    bne pace_skip                  ; phase != 0: discard
pace_allow:
    movem.l (a7)+,d0-d1/a0
    cmpi.w #$4,-$E(a6)             ; displaced instruction
    rts
pace_skip:
    movem.l (a7)+,d0-d1/a0
    addq.l #4,a7
    jmp $022960.l
```

- Turn check BEFORE the phase gate: if the popped direction differs
  from Buc's heading, the move goes through immediately (turn), no
  phase check. A single short press in a new direction now rotates
  the face (and steps one cell if the cell is walkable; if it is
  blocked, the face still turns — the heading write is in the shared
  epilogue).
- Same-direction moves keep the v1 phase gate (the cell still commits
  once per 4 ticks while holding a direction), so the walk pace and
  the slide are unchanged. Holding a direction still walks
  beautifully; only turning is un-gated.
- The dir==4 stop sentinel still works: dir 4 != any heading 0-3,
  so it takes the allow path, the displaced `cmpi.w` sets the flags,
  and Path A's `beq` at `$0228D2` skips the move exactly as before.
  (Verified: the v1 report's `expect(0x0228D2, '6700008c')` — the
  `beq.w L022960` — is unchanged in the base and in the fixed ROM.)
- Registers: saves/restores d0-d1/a0 (movem); a6 untouched (it is
  `combat_turn_run`'s frame pointer; -$E(a6) is the popped
  direction). Exits with rts on the allow path, or discards the
  return address and jmps to `$022960` on the gated path — exactly as
  the v1 blob did.
- No RAM written (reads `$FF02F2` and grid+$A only).
- The turn check never fires during a script: the movement block is
  skipped while `$FF0110 != 0` (`combat_turn_run` `$0227C6`), so the
  cutscene is unchanged.

Known minor artifact (stated, not hidden): a turn commits the cell
mid-phase (not on the phase 3->0 wrap), so the interp slide starts
at that phase's offset — e.g. a turn at phase 2 starts halfway
(slide table phase 2 = -step + step/2), so Buc jumps about half a
cell, then slides the rest. The legs still cycle and the face turns
in one press. Re-timing the slide to start at the commit phase would
mean touching the interp blob, which is out of scope for this fix;
whether the half-cell jump on a turn reads as worse is for Dayset's
playtest to judge.

## 3. What was NOT changed

- Flat / checkerboard blob (`$FD400-$FD600`), feet-fix blob
  (`$FD600-$FD800`), subcell blob (`$FD800`), interp blob
  (`$FDA00-$FDBED`): byte-identical to the base (asserted in
  build.py).
- Hook sites untouched: hero_track `$023202` (jsr `$FDA00`),
  map_promote_record `$023480` (jsr `$FDA00`), fig_replay
  `$01C0D6`, flat face/hidden/top call sites
  (`$01BC1A`/`$01BC3C`/`$01BC84`), mode-6 camera writes
  (`$01C242`/`$01C264` — still the original moves, teleports snap
  immediately), pacing hook `$0228CC` (still jsr `$FD900`).
- The interp-fix camera-delay blob region (`$FDE00-$FDE7B`) is now
  occupied by the cam_snap blob (102 bytes, `$FDE00-$FDE65`); the
  tail `$FDE66-$FDE7B` stays 0xFF padding. It was unreferenced since
  interp-fix2 reverted the delay.
- No new RAM used by either blob (the camera blob reads
  `$FF00AE`/`$FF0110`/`$FF0E8E`/`$FF0E90` only; the pacing blob reads
  `$FF02F2`/grid+$A only). No collision with the feet-fix list
  (`$FFD800`/`$FFD802`), subcell latch (`$FFD000-$FFD006`), interp
  OLD_X/OLD_Y (`$FFD008`/`$FFD00A`) or slide scratch
  (`$FFD00C`/`$FFD00E`).

## 4. Build verification (minimal checks only)

`python3 build.py` (in `patches/interp-fix3/`):

- vasm assembled both blobs cleanly; addresses parsed from the
  listings (never hardcoded): `pace_gate $FD900` (58 bytes),
  `cam_snap $FDE00` (102 bytes). Both listings hand-verified
  instruction by instruction: every branch displacement lands on
  its target (`bne pace_allow` +12 -> `$FD922`; `bne pace_skip`
  +12 -> `$FD92E`; `bne cs_orig` +76/+68 -> `$FDE5A`;
  `bpl` +2 skipping each `neg.w`; `bge` +8 skipping each 8-byte
  `move.w`); movem masks correct (predecrement reversal:
  `d0-d1/a0` -> `0xC080`, `d0` -> `0x8000`; postincrement
  `0x0103` / `0x0001`); displaced instructions byte-identical to
  the originals (`cmpi.w #$4,-$E(a6)` = `0c6e 0004 fff2`;
  `sub.w $FF0E8E,d0` = `90 79 00 ff 0e 8e`).
- Base ROM verified before patching: MD5
  `30233662e411ecf0046ffc43c734c971`; hook sites exact
  (`$02529C` = `90 79 00 ff 0e 8e`, `$0228CC` = `4e b9 00 0f d9 00`,
  next instruction `$0252A2` = `4a 40 6c 0e`); cam blob region
  all 0xFF; pace extension region (`$FD922+`) all 0xFF; v1 pacing
  blob entry, interp blob entry, both interp hooks, and the mode-6
  camera writes all intact; original ROM MD5 re-verified.
- Fixed ROM: MD5 `8ada8b985aad8ae6c3929ae6d39d4139`; header
  checksum `0x2475`, runtime immediate `0x9A676410` —
  `checksum.py verify-all` exit 0 (both OK).
- 155 bytes differ from the base, all confined to the two blobs,
  the cam hook site, and the two checksums (see
  `changed-bytes.txt`). The bytes between each blob's end and the
  next region (`$FD93A-$FDA00`, `$FDE66-$FDE7B`) stay 0xFF.
- IPS round-trip verified: base + `interp-fix3.ips` (263 B) ==
  fixed ROM exactly.

## 5. What was NOT verified

No playtest verification (Dayset tests it himself). In particular
not verified:

- Whether the camera moves purely along the new direction on a
  turn (no diagonal jump) — the per-axis claim is static (the
  target is set per axis before the clamp; the clamp and the
  mode-6 set run on that target).
- Whether a single short press rotates Buc's face after a stop —
  the turn-bypass claim is static (the heading comparison lets
  the move through; `combat_move_unit` writes the heading in its
  epilogue).
- Whether holding a direction still walks beautifully (smooth,
  subcell) — the same-direction phase gate is unchanged, but the
  feel in real play is his to judge.
- Whether the legs / slide / on-screen / straight-walk from
  interp-fix2 stay intact; standing-still (no jitter); all four
  directions; menu/teleport; other rooms.
- The cutscene (code-gated only: the camera blob is gated off
  while a script runs; the pacing turn check never fires during a
  script because the movement block is skipped).
- Speed in real play (cell rate unchanged, 1 cell / 4 ticks;
  restoring original walk speed is a separate pacing decision,
  Dayset's call).
- Whether the half-cell jump on a mid-phase turn (slide starting
  at the commit phase's offset) reads as acceptable or as worse —
  flagged in §2, for his playtest to judge.

## 6. Open questions / follow-ups (NOT in this ROM)

- Restoring original walk speed (pacing change — the walk is 1
  cell per 4 ticks, ~half speed) — Dayset's call, separate fix.
- Slowing the cutscene (tick-rate change — ~1.6x faster on the
  flat render) — Dayset's call, separate fix.
- The big rework (fractional camera / scroll-and-patch) — the only
  thing that fully smooths the world shift at the commit; the
  camera still jumps once per cell at the commit (now purely along
  the walk direction, never diagonally).
