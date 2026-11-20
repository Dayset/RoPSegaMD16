# Pacing gate — subcell movement in the B-zoom view

## Deliverable

- **ROM:** `~/workspace/rop-work/pacing/rop-pacing.rom`
  - MD5 `6abeec0bea66365f223c75760983df8b`
  - Header checksum `0xFF82`, runtime immediate `0xBDA562F2` (both verify,
    `checksum.py verify-all` exit 0)
- **Patch:** `~/workspace/rop-work/pacing/patches/pacing/`
  (`source.s`, `build.py`, `README.md`, `changed-bytes.txt`,
  `pacing.ips` — 90 B, round-trip verified: base + IPS == ROM exactly)
- **Base ROM:** `rop-dither.rom` (MD5 `09d74baa339314b40e02344545f67f66`) —
  flat checkerboard only on mode 2, feet fix, subcell template override.
  The base ROM and the original ROM (`30c18fdbe2183f64702ae9f1a45d63f9`)
  are untouched (MD5s re-verified after the build).

## What it does

One fix only: the leader figure's (Buc, char 1) cell commits once per 4
ticks (phase 3→0 wrap) instead of every tick, so the subcell
walk-template offsets (already in place from the subcell ROM) interpolate
across the cell instead of the figure jumping a whole cell per tick. Same
pacing as the Buc cutscene walk, which Dayset confirmed is "wow so smooth".

## Diagnosis (static — no probe was needed; every finding below is grounded
in ROM bytes, not just the disassembly)

Dayset's playtest (2026-11-12): he could not see subcell movement in the
subcell ROM. The subcell report's open question was whether the cell
commits every 4 ticks or every tick. The static read settles it: **every
tick**. Root cause is the grid's phase divisor:

1. `world_tick` `$02155E`: grid+$A = (old+1) mod 4
   (`move.w $A(a1),d0; addq #1; ext.l; divs.w #4; swap; move.w d0,$A(a0)`,
   ROM bytes `3029 000A 5240 48C0 81FC 0004 4840`), and
   `$FF0094 = phase mod grid+$8`
   (`move.w $A(a0),d0; divs.w $8(a1),d0; swap; move.w d0,$FF0094`).
2. `new_game_init` `$01B5D6` sets grid+$8 via `table_init_b` (field +8 =
   the 5th word arg, `$12(a6)`). ROM bytes of the immediates:
   - overworld `$FFB08C`: `move.w #$1,-(a7)` at `$01B6A8` → +8 = 1
   - room `$FFB09C` (the B-zoom room, location 30): `#$1` at `$01B6AC`
     → +8 = 1
   - room `$FFB0AC` (the Buc cutscene room, location 156): `#$1` at
     `$01B6EC` → +8 = 1
   - room `$FFB0BC`: `#$4` at `$01B70C` → +8 = 4 (the only 4-tick grid)
   So for the B-zoom room, `$FF0094 = phase mod 1 = 0` **always**.
3. `combat_turn_run` `$022790`: the per-char movement loop runs only when
   `$FF0094 == 0` (`tst.w $FF0094.l`, ROM `4A79 00FF0094`) — in the room
   that is every tick, so the `$022790` gate never fires.
4. Path A (`$022826`, mode 2): pops the leader's queued direction and
   calls `combat_move_unit` (`$024984`), which commits the cell (writes
   char X/Y at `$024CE8`–`$024D64`, gated only on move cost `d4 != 0`),
   with no phase gate. So Buc's cell commits every tick — the figure
   jumps a full cell per tick and the subcell template only adds a ±6 px
   wobble. This is the "every tick" case, now proven, not hypothesised.
5. Why the cutscene is smooth: `sys_event_run` runs only at grid+$A == 0
   (`$022764` gate: `tst.w $FF0110; tst.w $A(a0); bne skip`, ROM
   `2079 00FFA7FC` / `4A68 000A`), and the movement block is skipped
   while a script runs (`$FF0110 != 0`, `$0227C6`). So Buc moves one cell
   per 4 ticks via op-5. The player walk has no such gate — until this ROM.
6. Precedent: the NPC wander path (`$022B56`) already gates its
   `combat_move_unit` call on grid+$A == 0 (`tst.w $A(a0)`, ROM `4A68
   000A`).

No diagnostic probe was run: the grid+$8 = 1 finding is decisive (it
makes `$FF0094` identically 0), and it was verified against the ROM
bytes, so a timing measurement could add nothing.

## Design

A single hook in `combat_turn_run` Path A at `$0228CC`
(`cmpi.w #$4,-$e(a6)`, 6 bytes) → `jsr pace_gate`, blob 34 bytes at
`$FD900` (0xFF padding; the free run `$FD8DE`–`$100000`).

- The blob reads grid+$A (`ram_map_grid_base` `$FFA7FC`, +`$A`).
- If phase != 0, it discards the `jsr` return address (`addq.l #$4,a7`)
  and jumps to `$022960`, the block's standard skip exit (`bra.b
  L022972` — the same exit the dir==4 check uses). The move is skipped.
- If phase == 0, it executes the displaced `cmpi.w #$4,-$E(a6)` and
  returns to `$0228D2` (`beq.w L022960`), so the dir==4 check and the
  move proceed exactly as before.
- The hook sits AFTER `queue_pop` (`$0228C0`), deliberately: the
  direction queue still drains every tick, so there is no accumulation
  and no direction-change lag. (The queue is a 34-entry FIFO that drops
  pushes when full — `queue_push` returns `$FE` — so gating before the
  pop would have filled it with the old direction and stalled direction
  changes for up to 34 cells.) A brief tap during phases 1–3 is
  discarded; holding a direction walks one cell per 4 ticks, as in the
  cutscene.

Register discipline: `a0` is saved/restored with `movem` (it is dead at
the hook site — reloaded at `$0228B2` — but the hook clobbers nothing
either way); `d0` is set by the displaced instruction, as the original
code expects. The `cmpi.w` runs after the phase test, so the flags the
`beq` at `$0228D2` reads are the `cmpi`'s, not the `tst`'s.

Unaffected (by construction, all verified as byte-identical or by the
code path): the cutscene (the movement block is skipped while `$FF0110
!= 0`, so the hook never fires during a script), the overworld (Path A
only runs in mode 2), the turn effects, the NPC/follower placement, the
record stepper (`$022F52`), and the projectile stepper (`$02309C`) — all
still run every tick. The flat/checkerboard blob (`$FD400`–`$FD600`), the
feet-fix blob (`$FD600`–`$FD800`), and the subcell blob (`$FD800`–`$FD8DE`)
are byte-identical to the base, as are the hook sites `$023202`
(subcell), `$01C0D6` (fig_replay), `$01BC1A`/`$01BC3C`/`$01BC84` (flat).

## Build checks (minimal only — no live tests, per Dayset's rule)

- `vasm` assembled the 34-byte blob cleanly; `pace_gate` parsed from the
  listing at `$FD900` (== blob base).
- Listing hand-verified instruction by instruction: `movem.l a0,-(a7)`
  `48E7 0080` (mask bit 7 = a0 in predecrement order); `movea.l
  $FFA7FC,a0` `2079 00FFA7FC`; `tst.w $A(a0)` `4A68 000A`; vasm's
  single-register `movem.l (a7)+,a0` optimised to `movea.l (a7)+,a0`
  `205F`; `bne.s` `6608` (target `$FD91A`, displacement +8 from `$FD912`,
  correct); displaced `cmpi.w #$4,-$E(a6)` `0C6E 0004 FFF2` byte-identical
  to the original; `rts` `4E75`; `addq.l #$4,a7` `588F`; `jmp $022960.l`
  `4EF9 00022960`.
- Hook-site bytes verified before patching: `$0228CC` was `0c6e 0004
  fff2`; after patching it is `4eb9 000fd900` (`jsr $FD900.l`).
- Blob region `$FD900`–`$FD921` was 0xFF padding in the base ROM.
- `checksum.py verify-all` on the built ROM: header `0xFF82` OK, runtime
  `0xBDA562F2` OK (exit 0). The runtime immediate changed (the hook site
  is inside the runtime-checksummed range `$000000`–`$FD07B`); the blob
  itself is outside it.
- Changed bytes: **42**, confined to the header checksum (2 B), the hook
  site (5 B — one byte coincides), the runtime immediate (3 B), and the
  blob (`$FD900`–`$FD921`). Full ranges in `changed-bytes.txt`.
- IPS round-trip verified: base ROM + `pacing.ips` == built ROM exactly.

## What was NOT verified

No live probes, screenshots, cadence measurements, or playtest
verification were run on this ROM (Dayset's rule: he tests it himself).
In particular NOT verified:

- Whether the movement actually reads smooth in real play (the playtest
  is the check — this is the point of the ROM).
- Standing still (no jitter), all four directions, direction-change
  responsiveness (max 3-tick lag on a change, by the queue reasoning
  above — not measured).
- Menu / teleport on this ROM (code-gated only).
- The look in any room, the Buc cutscene room, or the overworld.
- Speed / cadence before vs after (the hook adds a handful of cycles per
  leader-move-block execution, negligible against ~8 frames/render, but
  that is an estimate, not a measurement).

## Playtest asks (for Dayset)

1. In the B-zoom view, walk Buc in a straight line. Does he glide
   smoothly across cells (like the cutscene walk), or does he still jump
   a whole cell per step?
2. Stand still. Buc should be perfectly still (no jitter).
3. Walk in all four directions; change direction mid-walk — does the new
   direction take effect promptly (within a step)?
4. Menu dismiss + teleport still work; the room stays checkerboard flat;
   the big world stays textured; Buc's feet stay visible.

If case 1 is smooth, the rendering sequence is flat → feet fix → subcell
→ dither → pacing, all on top of each other, and the next question is
whether anything else in the sequence still needs work.
