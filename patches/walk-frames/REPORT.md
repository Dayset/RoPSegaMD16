# walk-frames — double Buc's cutscene walk animation

Base: `~/workspace/rop-work/cutscene-loop/rop-cutscene-loop.rom`
(MD5 `79bccdcd927707802332f64f38faa641`) — flat only on mode 2, feet
fix, cutscene loop-walk (Buc walks the loop in all four directions).
Deliverable: `~/workspace/rop-work/walk-frames/rop-walk-frames.rom`
(MD5 `a698a2f697939fd8a5b11b94837f32f7`, header 0x08BB, runtime
0xA16ACFA7). Patch in `patches/walk-frames/` (loop.s, hook.s,
build.py, README.md, changed-bytes.txt, walk-frames.ips 629 B,
IPS round-trip verified). Original ROM untouched
(MD5 `30c18fdbe2183f64702ae9f1a45d63f9`).

## Dayset's direction (applied exactly)

- "Just repeat the existing frames (do not create new art — reuse the
  existing walk frames, repeated), and use a smaller Y coordinate
  shift (when repeating the frames, offset the Y coordinate by a
  smaller amount, so the repeated frames create a smoother/more
  detailed animation without new art)."
- "If the Y coordinate shift was 8, 16, 24, make it 8, 12, 16, 20, 24
  now. Same start (8) and end (24), but step by 4 instead of 8, with
  the intermediate values 12 and 20 added."

## How many frames exist

Buc (char 1) has base tile 384 and 16 tile streams (384–399), all
byte-distinct (no two identical; lengths 247–331 bytes). The walk
template table $197B0 (36 bytes per template; group = stream offset,
param, dx, dy) gives, per direction, 4 walk frames:

| Direction | Template | Frames (tile offsets) | dx | dy |
|---|---|---|---|---|
| North | 36 | 8, 14, 9, 15 | — | — |
| East | 37 | 0, 6, 1, 7 | — | — |
| South | 38 | 0, 6, 1, 7 | 0,−4,6,2 | 0,2,−4,−2 |
| West | 39 | 9, 14, 8, 15 | — | — |

Static templates use frames [2,3,2,3] (tpl 0/3), [1,0,1,0] (tpl 1/2),
[0,0,0,0] (tpl 5/6), [8,8,8,8] (tpl 4/7). **Offsets 4, 5, 10, 11,
12, 13 are NEVER used by any template 0–55.** All 16 poses were
rendered via BlastEm screenshots (`poses/pose_00..15.png`, slot_0
state, Buc at rest in the cutscene room) — they confirm the 16 streams
are distinct poses. They are NOT used in this ROM: per Dayset's
direction the doubling repeats the existing walk frames, and no new
art was created.

Timing limit (established earlier): the figure's image changes only
at the render, once per world tick, and the cell commits every 4
ticks — so at most 4 distinct images per cell at the old cadence.
The doubling therefore slows the cell to 8 ticks (below), which is
what makes 8 frames per cell possible. Rendering twice per tick does
NOT give two visible frames (both uploads happen before the next
VBlank; only the last is displayed).

## How the doubling works

Two parts, one fix:

1. **Loop driver rebuilt (loop.s, blob $FD800, 310 bytes).** Buc now
   steps every OTHER `sys_event_run` call: one cell per **8 ticks**
   instead of 4. The walk template is indexed by `grid+$A`, a 4-phase
   counter (0–3, one phase per tick). Over an 8-tick cell the counter
   cycles TWICE, so each of the 4 existing walk frames is shown twice
   per cell — 8 frames per cell, the frames REPEATED, no new art. A
   `walk_half` flag ($FFD104, new RAM) tracks which half of the cell
   the render is in: 0 = first half (ticks 0–3, Buc drawn at the
   record cell), 1 = second half (ticks 4–7, Buc drawn half a cell
   toward the next cell). `loop_drive` sets it once per call; the
   reset call (pointer == $1A228) sets it to 0. The first step after
   the reset is therefore 8 ticks after the reset call, not 4 — a
   4-tick delay at the very start of the cutscene, while the dialog
   is up. Everything else in the loop driver is unchanged (20-cell
   legs, S,E,N,W order, turn on block, `loop_op5` suppressing the
   script's own Buc moves). `loop_op5` moved $FD8E2 → $FD90E because
   the driver grew; the $02D7F6 hook site was updated to the new
   address (parsed from the vasm listing, never hardcoded).
2. **New hero_track hook (hook.s, blob $FDA00, 196 bytes).** Hook site
   $023202 (`lea.l $197B0,a0`) → `jsr walk_hook`. During the second
   half (`walk_half==1`) it draws Buc half a cell toward the next
   cell, using a half-step table indexed by `loop_dir` ($FFD100):
   N (+7,−4), E (+7,+4), S (−7,+4), W (−7,−4) — half the measured
   cell step vectors (N +14,−8; E +14,+8; S −14,+8; W −14,−8). It
   also subtracts the template's dx/dy wobble for the current phase,
   so the drawn position is exactly the slide (the wobble, ±6 px, is
   larger than the half-step, 4 px Y / 7 px X, and would otherwise
   make the motion non-monotonic — same reasoning as the interp ROM).
   The image still cycles (legs step); the position is purely the
   slide. Gates: mode 2 only, Buc's draw record only (char 1,
   $FF02EC), cutscene active ($FF0110!=0, pointer in
   [$1A228,$1A390]). d0 (the template offset) is preserved, so the
   record's own walk template drives the image cycle; the displaced
   lea is re-executed before the `rts`. It fires whether the draw
   comes from `map_chunk_pos` or the feet-fix `fig_replay` post-pass.

Result for a south step: Buc's drawn Y goes **8, 12, 16, 20, 24**
(step 4) instead of 8, 16, 24 (step 8) — Dayset's exact values. The
same holds in the other directions (north: −8, −12, −16, −20, −24;
east/west: the Y component is +4 per half-cell, the X ±7).

## Build verification (minimal checks only)

- vasm assembled both blobs cleanly: loop 310 bytes, hook 196 bytes.
- `loop_drive` $FD800, `loop_op5` $FD90E, `walk_hook` $FDA00 (all
  parsed from the listings).
- Both listings hand-verified instruction by instruction: all 6 `.w`
  branches in the loop blob land exactly on `.done` ($FD902); all 14
  `.s` branches land on their targets; all 9 gate branches in the
  hook land exactly on `wh_orig` ($FDAB2); both `beq.s` land on
  `wh_nox`/`wh_noy`; the PC-relative `lea half_tab` lands on $FDAB4;
  the half-table values are correct; the movem masks are the correct
  complementary pairs (loop 0xFFFE/0x7FFF, hook 0x70E0/0x070E);
  d0 is never modified by the hook; the displaced `lea.l $197B0,a0`
  is byte-identical to the original.
- Hook-site bytes verified before patching: $02D56E was
  `4eb9 000fd800`, $02D7F6 was `4eb9 000fd8e2`, $023202 was
  `41f9 000197b0`; $FDA00–$100000 was all 0xFF padding.
- `checksum.py verify-all` exit 0 (header 0x08BB, runtime 0xA16ACFA7).
- 406 bytes differ, confined to the header checksum, the three hook
  sites, the runtime immediate, and the two blobs. The flat
  ($FD400–$FD600) and feet-fix ($FD600–$FD780) blobs are
  byte-identical to the base (asserted in build.py).
- IPS round-trip verified: base + walk-frames.ips == fixed ROM.
- Base ROM and original ROM MD5s re-verified unchanged after the build.

## What was NOT verified (Dayset is the tester — no live tests)

No probes, screenshots, cadence measurements, or playtest verification
of this ROM. In particular not verified: whether the doubled animation
reads as smoother in real play; whether the half-cell slide is visible
in all four directions (S, E, N, W) in the loop; standing-still (no
jitter); the first step (4 ticks later than before); menu/teleport;
other rooms; the cutscene dialog and Thalmus's moves still running.
The big world stays textured. The flat, feet fix, loop-walk, and
cutscene dialog/script are unchanged.

## Playtest asks for Dayset

1. Does Buc's walk look 2x more animated / smoother in the cutscene
   loop (all four directions)?
2. Is the Y movement visibly smoother (smaller steps), or does it
   still read as a jump?
3. Does Buc still walk the loop correctly (no stalls, no wrong turns)?
4. Flat room, textured big world, feet still visible, dialog and
   Thalmus still fine?
