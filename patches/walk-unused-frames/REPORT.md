# walk-unused-frames — cutscene Y fix (unused poses are combat/cast, not walk frames)

Base: `~/workspace/rop-work/walk-frames-fix/rop-walk-frames-fix.rom`
(MD5 `9ba279759436b96a732d11d9a3f6be0d`) — flat only on mode 2, feet
fix, cutscene loop-walk, frame doubling (one cell per 8 ticks) +
Y-shift hook in hero_track ($023202) and map_promote_record
($023480), blob at $FDA00.
Deliverable: `~/workspace/rop-work/walk-unused-frames/rop-walk-unused-frames.rom`
(MD5 `6764e6ee86976e1a3607388f4cb5faa3`, header 0x639F, runtime
0xA15C8097). Patch in `patches/walk-unused-frames/` (source.s,
build.py, README.md, changed-bytes.txt, walk-unused-frames.ips
61 B, IPS round-trip verified). Original ROM untouched
(MD5 `30c18fdbe2183f64702ae9f1a45d63f9`).

## Part 1 — the unused poses: Dayset's correction, verified

Dayset: the unused poses (offsets 4, 5, 10, 11, 12, 13) are NOT
walk frames — they are combat moves / a cast. He laughed at them
looking like a dance, but they're combat/cast animations. So they
must NOT be fitted into the walk routine.

Verified rigorously from the ROM template table $197B0 (group
layout confirmed against the hero_track disassembly in
disasm/src/rop.s: group+0 = stream offset, group+2 = param,
group+4 = dx, group+6 = dy; group stride 8, template stride 36):

| Template range | Offsets used |
|---|---|
| Walk 36–55 | 0, 1, 6, 7, 8, 9, 14, 15 |
| 28–35 | 0, 1, 6, 7, 8, 9, 14, 15 |
| Static 0–15 | 0, 1, 2, 3, 8, 9 |
| **16–27 (combat/cast)** | **0, 2, 3, 4, 5, 8, 10, 11, 12, 13** |

ALL 16 offsets are used by some template 0–55. The walk-frames
report's claim that offsets 4, 5, 10, 11, 12, 13 are "NEVER used
by any template 0–55" is WRONG — its scan missed templates 16–27.
Offsets 4, 5, 10, 11, 12, 13 are actively used by the combat/cast
templates 16–27. The pose renders agree (viewed again): poses 04,
05 are front-facing arms-out/cast; 10, 11 are back-facing with a
staff; 12, 13 are back-facing arms-out/cast. The 8 walk-frame
poses (0, 1, 6, 7 front; 8, 9, 14, 15 back) are already used by
the walk templates. The 2 attack poses (2, 3, front, staff across
the body) are used by static templates 0/3.

**Conclusion: there are no unused poses that are walk frames.
There are no unused poses at all.** The unused-poses idea for the
walk routine is dropped entirely. No combat/cast pose is fitted
into the walk routine. This ROM changes nothing about the walk
frames — the zoom walk keeps the exact walk templates it already
had (which Dayset says is very good).

## Part 2 — the cutscene Y problem: diagnosis

Dayset's playtest of the walk-frames-fix ROM:

> "this one walks even better than previous, no yoinks, movement
> begins with 1-2 press (rarely from 2nd) but cutscene Y is
> completely off. He is doing 2 steps and then waiting for longer
> than usual and jumps screen, and repeat"
> "Like he is waiting and running after 2 cells"
> "But zoomed movement is very good"

The "walks even better" part is the ZOOM walk. The cutscene Y is
the problem. Diagnosed statically (loop.s / hook.s source + the
loop-blob disassembly from the base ROM, capstone):

The cutscene walk on the fix ROM is the walk-frames mechanism:
the loop driver steps Buc every OTHER sys_event_run call (one
cell per 8 ticks, walk_half flag $FFD104), and the Y-shift hook
(blob $FDA00, now routed through map_promote_record so it fires
for Buc) draws him half a cell toward the next cell during the
second half (walk_half==1), subtracting the template wobble so
the drawn position is exactly the slide.

Two causes for the symptom:

1. **The Y shift decouples Buc's drawn position from the camera.**
   The camera follows Buc's RECORD cell (world_reposition_leader
   in combat_move_unit's epilogue, 3-cell dead zone); the hook
   draws him half a cell ahead of it during the second half.
   At a turn, loop_dir changes, so the half-step direction flips
   and Buc's drawn position jumps back/forward. When the camera
   re-centres (dead-zone crossing), the screen jumps. Buc's drawn
   position is no longer locked to the camera — that is the
   "jumps screen".
2. **The 8-tick cadence makes Buc slow and the waits long.**
   Each cell takes 8 ticks instead of 4, and at a turn there is
   an extra 4-tick delay (the non-step call after the turn: turn
   call, non-step call, step call = 12 ticks between steps
   instead of 8). The legs are short (2–3 cells) because the
   room is crowded — Buc turns when blocked by a student or a
   wall — so the pattern is: 2 steps, a long pause at the turn,
   screen jump, repeat. That is the "waiting for longer than
   usual" and the "waiting and running after 2 cells".
   Dayset already judged the frame doubling alone (walk-frames
   ROM, Y shift not firing) as "slower than before" with Buc
   "standing still for longer after 2 steps", so the doubling
   has no value without the Y shift — and the Y shift made it
   worse ("Y is completely off").

The alternative considered and rejected: gating the Y-shift hook
to the zoom walk only. Wrong — the hook reads loop_dir and
walk_half, which the loop driver sets only during the cutscene;
in the zoom walk they are stale (leftover from the last cutscene),
so the half-step would point in a stale direction. And the zoom
walk is already very good without it. The Y shift is a cutscene
mechanism that fails in the cutscene; it has no correct home.

## The fix (three byte changes, no new blob)

1. `$023202` (hero_track): `jsr $FDA00.l` (`4EB9 000FDA00`) →
   `lea.l $197B0,a0` (`41F9 000197B0`). Y-shift hook off.
2. `$023480` (map_promote_record): `jsr $FDA00.l` →
   `lea.l $197B0,a0`. Y-shift hook off (this is the routine Buc
   is actually drawn through). Both sites restore the original
   figure-draw entry, so both routines work exactly as in the
   original ROM. The `$FDA00` walk-hook blob becomes dead code
   (unreferenced). Left in place (0xFF padding region, outside
   the runtime checksum range) — harmless, and the patch stays
   reversible.
3. `$FD866` (loop_drive): `beq.b $FD86A` (`67 02`) →
   `bra.b $FD88A` (`60 22`). Always step Buc on every
   sys_event_run call. The `.half` non-step block ($FD86A–$FD875)
   becomes dead code, walk_half stays 0. Restores the original
   cutscene-loop cadence: one cell per 4 ticks, not 8. (The
   `tst.w $FFD104.l` at $FD860 and the `bra.b $FD88A` at $FD868
   are now unreachable/dead but harmless; the patch stays minimal.)

After the fix the cutscene walk is the cutscene-loop walk, which
Dayset already saw working ("he walks a bit more, other
directions seen"): Buc walks the loop S,E,N,W, turning when
blocked or after 20 steps, at 4 ticks/cell, with no Y shift.
The world shift is still jumpy (integer-cell camera) — that is
the big rework (fractional / smooth camera), not this fix.
The zoom walk is untouched (it uses neither the loop driver nor
the Y-shift hook — both are gated to the cutscene). The flat,
feet fix, loop driver (except the cadence), and cutscene
dialog/script are otherwise unchanged. The big world stays
textured.

## Build verification (minimal checks only)

- Base ROM MD5 verified (`9ba279759436b96a732d11d9a3f6be0d`);
  original ROM MD5 verified unchanged
  (`30c18fdbe2183f64702ae9f1a45d63f9`).
- All three site bytes verified before patching: $023202 and
  $023480 were `4eb9000fda00` (jsr $FDA00.l); $FD866 was `6702`
  (beq.b $FD86A), with the surrounding walk_half gating matching
  the capstone disassembly of the base ROM ($FD860 tst.w
  $FFD104.l, $FD868 bra.b $FD88A, .half block $FD86A–$FD875).
- Byte encodings verified with vasm before building:
  `lea.l $197B0,a0` = `41f9000197b0`;
  `bra.b $FD88A` from $FD866 = `6022` (target $FD88A, PC after
  $FD868, disp $22 — consistent with the existing `bra.b $FD88A`
  at $FD868 encoding as `6020`).
- Walk-hook blob verified intact at $FDA00 (movem, displaced
  lea+rts at $FDAAA) — left in place, now unreferenced.
- `checksum.py verify-all` exit 0 (header 0x639F, runtime
  0xA15C8097). (Note: the runtime immediate changed because the
  two hook sites are inside the runtime-checksummed range
  $000000–$FD07B; $FD866 is outside it and does not affect the
  runtime sum.)
- Patched sites re-disassembled with Capstone: $023202 and
  $023480 decode as `lea.l $197b0.l,a0`; $FD866 decodes as
  `bra.b $fd88a`.
- 18 bytes differ, confined to the header checksum (2), the two
  hook sites (5 bytes each — jsr `4EB9 000FDA00` vs lea
  `41F9 000197B0` share the `00` byte at offset +2), the runtime
  immediate (4), and $FD866 (2). The flat ($FD400), feet-fix
  ($FD600), loop blob (except $FD866), and walk-hook blob are
  byte-identical to the base (asserted in build.py).
- IPS round-trip verified: base + walk-unused-frames.ips == ROM.

## What was NOT verified (Dayset is the tester — no live tests)

No probes, screenshots, cadence measurements, or playtest
verification of this ROM. In particular not verified: whether
the cutscene walk now reads as smooth (no long waits, no screen
jumps); whether the 2-step legs still read as stuttery (they
are short because the room is crowded — Buc turns when blocked,
unchanged by this fix); the zoom walk still very good; standing
still; menu/teleport; other rooms; the cutscene dialog and
Thalmus's moves still running. The big world stays textured.

## Playtest asks for Dayset

1. Does Buc's cutscene walk now read as smooth — no long waits
   after 2 steps, no screen jumps?
2. Is the zoom walk still very good (unchanged)?
3. Flat room, textured big world, feet still visible, dialog and
   Thalmus still fine?
