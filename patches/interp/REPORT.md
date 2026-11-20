# Interpolation — smooth slide for the leader figure (Buc)

Worktree: `~/workspace/rop-work/interp/`
Base ROM: `rop-pacing.rom` (MD5 `6abeec0bea66365f223c75760983df8b`)
Deliverable: `rop-interp.rom` (MD5 `309d87c5a97cdbc5c2066f11a2f98399`,
header 0xB7C8, runtime 0xBDA564F2; both verify with `checksum.py
verify-all`, exit 0)
Patch: `patches/interp/` (`source.s`, `build.py`, `README.md`,
`changed-bytes.txt`, `interp.ips` — IPS round-trip verified)

## 1. Diagnosis

### 1.1 How the cutscene walk achieves its smooth slide

Read statically (no probe run for the final ROM; two one-shot RAM reads
from the slot_0 save state were used to pin the facts below).

- The figure's drawn position = record-cell screen position + template
  group[phase] dx/dy. The record's cell commits on the phase 3→0 wrap
  (grid+$A, writer world_tick $02155E). The template groups give a
  per-phase image (stream offset) AND a per-phase position offset.
- In the cutscene, Buc is a walker (template 38, stepcode 3 = south,
  stepphase 2). The record stepper ($022F52) moves the draw record at
  phase == stepphase; sys_event_run (op-5) moves the char at phase 0.
  The camera ($FF0E8E/$FF0E90, only writer leader_spawn $01C21A)
  follows the walker, so the figure stays centred on screen.
- The cutscene's smoothness is NOT a positional slide across the
  screen: the figure stays centred and wobbles ±6 px (template dx/dy)
  while its image cycles per phase (legs step), and the room jumps one
  cell per 4 ticks (the world scrolls past). The leg cycle + sway +
  slow cadence (1 cell per 4 ticks) is what reads as smooth walking.
- The template dx/dy are a sway, not a slide: tpl 38 (south) groups
  are (0,0), (-4,2), (6,-4), (2,-2) — non-monotonic, net ~0. They do
  not progress from the old cell to the new cell.

### 1.2 Why the overworld walk did not slide

- The overworld walk has the same cadence (1 cell per 4 ticks, pacing
  gate) and the same walk template (subcell hook), so the image cycles
  (Dayset: "cape moving"). But the figure does not translate: it sits
  at the room centre (the camera follows the committed cell) wobbling
  a few px, then the room jumps. The feet look "dead" because the feet
  never travel across the ground; the jump reads as a teleport.
- RAM read (slot_0 save state, cutscene room, before the script):
  party leader is char 0 (scaffold at (117,113), record index $FF =
  none); Buc is char 1 (record 0, word0=384, template 6 at rest,
  heading south at (8,7)). Buc's walk frames are 384+0/6/1/7 — the same
  tiles the subcell walk template (36+dir) selects. So the image cycle
  was already the right walk cycle; only the position was missing.
  The subcell hook fires (fig_replay calls hero_track with the record
  at 8(a6)); the missing piece was translation, not the template.
- A true on-screen slide is impossible with this renderer: the room is
  tile-based in the window plane and the camera is an integer grid cell,
  so the room can only jump whole cells. The achievable slide is the
  ROOM-RELATIVE one: the figure's drawn cell interpolates from the old
  cell to the new cell over phases 0-3 (0, 1/4, 1/2, 3/4, then the
  commit). Relative to the room the motion is continuous and monotonic;
  the whole-screen jump at the commit is the room scrolling, exactly as
  in the cutscene.
- Screen step per cell, measured from the live map_chunk_pos tables
  ($FFAE7A X, $FFAF42 Y) in RAM: East (+14,+8), South (-14,+8),
  North (+14,-8), West (-14,-8). Uniform across the window.
- The walk template's dx/dy wobble (±6 px) is LARGER than one slide
  step (~3.5 px/phase), so leaving it on top of the slide would make
  the motion non-monotonic (jerk back and forth). The hook therefore
  subtracts the template's dx/dy for the current phase, so the net
  drawn position is exactly the slide. The image still cycles (legs
  step); the position is purely the slide.

### 1.3 Why the overworld walk is half speed

Expected consequence of the pacing gate + the flat render, not a bug.

- Original walk: 1 cell per tick, tick ~22 frames → ~1 cell per
  22 frames.
- With the pacing gate: 1 cell per 4 ticks. With the flat render the
  tick is ~14 frames (render 16 → 7.86). So ~1 cell per 56 frames.
- Ratio ~56/22 ≈ 2.5× slower in real time ("about half" is Dayset's
  reading; the exact ratio depends on the tick, ~11–14 frames with
  the flat). The pacing gate slows the walk 4× in ticks; the flat
  makes ticks ~2× faster in real time; net ~2× slower.
- The slide makes the walk LOOK smooth (like the cutscene, which is
  also 1 cell per 4 ticks), but the cell rate (cells per second) is
  still ~half the original. Restoring the original speed would need a
  pacing change (e.g. 1 cell per 2 ticks) — a separate decision, not
  part of this fix. The 1-cell-per-4-ticks cadence matches the cutscene,
  which is the reference for "smooth".

### 1.4 Why the cutscene is "fast as a rocket"

The pacing gate is NOT the cause. The cutscene is fast because the
flat render makes each tick faster, and that was already true on the
feet-fix ROM (which Dayset called "very fast").

- The pacing gate CANNOT fire during a script. Verified in the code:
  combat_turn_run $0227C6 does `tst.w $FF0110; bne.w L022F3E` — when a
  script is active ($FF0110 != 0) the whole per-char movement block
  (Path A at $022826, pacing hook at $0228CC) is skipped. The pacing
  hook is never reached during a cutscene.
- The cutscene advances one record per 4 ticks (sys_event_run at
  grid+$A == 0, $022764 gate). With the flat render the tick is
  ~14 frames instead of ~22, so sys_event_run fires ~1.6× more often
  in real time and the script plays ~1.6× faster. This was already the
  case on the feet-fix ROM ("superb, very fast").
- The dither is cost-identical to the solid fill and the subcell hook
  adds only a few dozen cycles per hero_track call, so neither changes
  the tick rate during a cutscene. The pacing ROM's cutscene speed is
  the same as the feet-fix ROM's; "rocket fast" is the same "very fast"
  described more emphatically, made more noticeable by the contrast
  with the half-speed walk in the same session.
- If Dayset wants the cutscene at original speed, that needs a tick-rate
  change (e.g. a frame delay during scripts) — a separate decision, not
  part of this fix. This fix does not touch the cutscene's timing or its
  figure presentation (the slide is gated off while a script runs).

## 2. The fix

Hook site: hero_track `$023202` (the `lea.l $197B0,a0`), repointed from
`jsr $FD800` (subcell) to `jsr $FDA00` (this blob). The `$FD800` subcell
blob bytes are left untouched (unreferenced); this blob contains the
subcell template-override logic verbatim plus the slide.

Blob: `$FDA00`, 494 bytes (interp_hook + slide table), 0xFF padding in
the base ROM. RAM: `$FFD000-$FFD00E` (subcell latch `$FFD000-$FFD006`
plus OLD_X/OLD_Y `$FFD008/$FFD00A` and slide scratch `$FFD00C/$FFD00E`).
No collision with the feet-fix list (`$FFD800+`) or the pacing blob
(`$FD900`).

Behaviour, in hero_track, for Buc's draw record (char 1, record index
at `$FF02EC`) in mode 2 only:

1. Latch (as the subcell hook): ON when Buc's cell changes, OFF at the
   next phase-0 render with no change. PLUS it remembers the PREVIOUS
   cell (OLD_X/OLD_Y) so the step direction is known. A standing Buc
   is drawn with the original static template (no slide, no wobble).
2. Template: walk template 36+dir (dir = Buc heading), in d0 — the
   subcell behaviour, verbatim. The image cycles per phase (legs step).
   The record in RAM is never modified, so the `$022F52` record stepper
   still sees the original static template (stepcode 0 = no-op).
3. Slide: ONLY when no event script is running (`$FF0110 == 0`).
   During a cutscene the figure keeps the walk template + wobble
   exactly as before. The step direction comes from the cell delta
   (new − old); if it is not a single-cell step, no slide is applied
   (safe fallback: template only). The slide offset for [dir][phase]
   is a table in the blob (measured step vectors, quarter steps):
   phase 0 = −step (old cell), phase 1 = −step + step/4,
   phase 2 = −step + step/2, phase 3 = −step + 3·step/4.
   The hook writes the adjusted X/Y to 12(a6)/14(a6) (hero_track's X/Y
   args) BEFORE hero_track reads them, with the template's dx/dy for
   the current phase subtracted, so the net drawn position is exactly
   the slide.
4. Exits with `rts` (jsr hook). Saves/restores d1-d3/a0-a2; d0 is the
   template offset for hero_track; a6 untouched; stack balanced.

Slide offset table (dx, dy, screen px, relative to the base X/Y):

| dir | phase 0 | phase 1 | phase 2 | phase 3 |
|-----|---------|---------|---------|---------|
| N   | (-14,+8) | (-11,+6) | (-7,+4) | (-4,+2) |
| E   | (-14,-8) | (-11,-6) | (-7,-4) | (-4,-2) |
| S   | (+14,-8) | (+11,-6) | (+7,-4) | (+4,-2) |
| W   | (+14,+8) | (+11,+6) | (+7,+4) | (+4,+2) |

## 3. Build checks (minimal only)

- vasm assembled the 494-byte blob cleanly; `interp_hook` parsed from
  the listing at `$FDA00`, `slide_tab` at `$FDBAE` (last 64 bytes).
  Slide table bytes verified against the expected values in build.py.
  The displaced `lea.l $197B0,a0` is in the blob. The listing was
  spot-checked: stack peek `move.l (a7),a0`, 12(a6)/14(a6) writes,
  movem mask 0x070E (d1-d3/a0-a2) consistent, displaced lea + `rts`.
- Hook-site bytes verified before patching: `$023202` was
  `4EB9 000FD800` (`jsr $FD800`); after patching `4EB9 000FDA00`.
- Blob region `$FDA00-$FDBEE` was 0xFF padding in the base ROM.
- `checksum.py verify-all` on the built ROM: header `0xB7C8` OK,
  runtime `0xBDA564F2` OK (exit 0).
- Changed bytes: **437**, confined to the header checksum (2 B), the
  hook site (1 B — `$023206` 0xD8→0xDA), the runtime immediate (1 B),
  and the blob (`$FDA00-$FDBEE`). Full ranges in `changed-bytes.txt`.
- Every earlier blob is byte-identical to the base: flat/dither
  (`$FD400-$FD600`), feet fix (`$FD600-$FD800`), subcell (`$FD800-
  $FD8DE`), pacing (`$FD900-$FD922`). The other hook sites are
  untouched (pacing `$0228CC`, fig_replay `$01C0D6`, flat `$01BC1A/
  $01BC3C/$01BC84`).
- IPS round-trip verified: base ROM + `interp.ips` == built ROM exactly.
- Original ROM untouched (MD5 `30c18fdbe2183f64702ae9f1a45d63f9`).

## 4. What was NOT verified

No live probes, screenshots, cadence measurements, or playtest
verification were run on this ROM (Dayset's rule: he tests it himself).
In particular NOT verified:

- Whether the slide reads as smooth in real play (Dayset's playtest is
  the check). The screen still jumps at each commit (the room scrolls,
  as in the cutscene); the claim is that the figure's room-relative
  slide + leg cycle reads as walking, not that the screen is jump-free.
- The look in any room other than the B-zoom room (the slide applies
  to Buc in any mode-2 room).
- The cutscene (code-gated only — the slide is skipped while a script
  runs; the cutscene's figure presentation is unchanged).
- Menu / teleport on this ROM (code-gated only).
- Multi-level rooms, room water, or a direction change mid-step
  (the step direction is latched at the commit; a mid-step turn keeps
  the latched direction until the next commit).
- The 1-px rounding in the quarter-step table (invisible by
  construction, not measured).
