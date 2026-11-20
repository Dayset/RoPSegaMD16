# interp-fix2 — zoom-view legs + on-screen + straight walk

Base: `~/workspace/rop-work/interp-fix/rop-interp-fix.rom`
(MD5 `44353892c7a006300bfae2535ad6eaf8`).
Output: `~/workspace/rop-work/interp-fix2/rop-interp-fix2.rom`
(MD5 `30233662e411ecf0046ffc43c734c971`, header `0x5604`,
runtime `0x0CB56500`, both verify via `checksum.py verify-all`).
Patch: `patches/interp-fix2/` (`source.s`, `build.py`, `README.md`,
`changed-bytes.txt`, `interp-fix2.ips` 266 B, round-trip verified).
128 bytes differ from the base, confined to the three hook sites, the
camdelay blob region, and the two checksums.
Original ROM untouched (MD5 `30c18fdbe2183f64702ae9f1a45d63f9`).

## Dayset's playtest (interp-fix ROM, 2026-11-12 ~23:12 EST)

> "this one is not good, his legs are not moving at all in zoom view,
> walking speed like default rom or slighltly worse, and BUC can run
> behing the screen, sometimes he is doing zigzag walk. Cutscene was
> fast normal walking (both legs were moving as expected)."

Problems are specific to the zoom view (mode 2, overworld walk), not
the cutscene. This ROM fixes them. One fix only (zoom-view legs +
on-screen + straight walk). No live tests — Dayset is the tester.

## Diagnosis

### 1. Dead legs — the root cause (confirmed from ROM bytes + disassembly)

**Record+$A selects the figure-draw routine in `map_chunk_pos`.**
Jump table at `$01BE86` (re-dumped at the correct offset 114310;
words `0xFEBC`/`0xFF08`/`0xFF54`/`0xFF9E`; target = `$01BE9E` +
signed word; `jmp *+2(pc,d0.w)` at `$01BE9C`; dispatch at `$01BE8E`,
index = record+$A, `cmp.l #$4`):

| record+$A | routine | address |
|---|---|---|
| 0 | `hero_track` | $0231D8 (block L01BD5A) |
| 1 | `map_promote_record` | $02343A (block L01BDA6) |
| 2 | `map_tile_at_offset` | $0232AC (block L01BDF2) |
| 3 | `map_animated_tile` | $0232D2 (block L01BE3C, animated terrain tiles) |

The interp/subcell hooks live ONLY in `hero_track` (`$023202`).
Record+$A is set at creation by `map_grid_create` arg6
(record+$A = `$14(a6)`): the first `combat_move_unit` call site
(`$024620`) passes `world_vessel_class(char+0x06)`; the second call
site (`$024862`) passes `-world_vessel_grid_value`.

**Buc's record+$A = 1** (probe-confirmed in the cutscene room,
rec10 = 1 in every record, v3/v4; Buc's +0x06 is the same on foot in
any room, so +$A = 1 in room 30 too) → **Buc is drawn via
`map_promote_record`, NOT `hero_track`.** `map_promote_record`
(`$02343A`) uses the SAME template computation as `hero_track`
(d0 = (record+2 + record+4)*36 + phase*8, a3 = `$197B0` + d0;
(a3)=stream, 2(a3)=param, 4(a3)=dx, 6(a3)=dy) but reads the RECORD's
own template — Buc's record template in the zoom view is the static
template 6 (the record in RAM is never modified by the subcell/interp
hooks, which only override d0 inside `hero_track`) → **the image never
cycles → legs don't move.** In the cutscene his record IS a walk
template (38), so `map_promote_record` cycles the image per phase →
legs move.

This also explains every earlier "no subcell movement" playtest
(subcell, pacing, interp ROMs): the `hero_track` hooks never fired
for Buc in the zoom view. Probe v1 (hero_track never runs in the
cutscene room, hero_calls = 0) corroborates — the leader scaffold
(char 0) is off-map at (117,113), so `hero_track` never runs there.
Whether Buc's record+$A is 1 (`map_promote_record`) or negative
(the L01BEA0 path, via the second call site), it is NOT 0
(`hero_track`) — the `hero_track` hooks are dead for Buc either way.

`combat_move_unit` (`$024984`) DOES write char X/Y (at `$024D24`/
`$024D64`: X to `$FF02C0` + char*0x34, Y to `$FF02C2` + char*0x34;
for char 1 that is `$FF02F4`/`$FF02F6`), gated on d4 != 0 — so the
interp latch (based on BUC_X/BUC_Y) would turn ON if the hook fired;
the problem is the hook never fires, not the latch. Path A (`$022826`,
mode 2) calls `combat_move_unit(d5, dir)` where d5 is the char
returned by `npc_attitude_raise` whose +0x27 == party leader — for
the leader's movement that is Buc (char 1).

### 2. Off-screen / zigzag — the camera delay is fundamentally flawed for the room

**`leader_spawn` (`$01C21A`):** mode 6 (`$8(a6)==6`, absolute set)
writes cam X at `$01C242` and cam Y at `$01C264` (NOT hooked by the
camera delay) and snaps immediately; modes 0–3 and 5 fall through to
L01C2BA, which writes cam X at `$01C2D8` and cam Y at `$01C300`
(both hooked) — straight-line code, so BOTH hooks fire on every
step-mode call, X then Y. Mode 5 = relative step + window-grid shift
(sign_quadrant).

**`world_reposition_leader` (`$02513E`, `combat_move_unit`'s epilogue)
calls `leader_spawn(mode 5)` in a LOOP (L0251C8, while `-$8(a6)` <
`$c(a6)`) when grid+$C != 0; when grid+$C == 0 it goes to L0251EE
and calls `leader_spawn(mode 6)` at `$02537E`/`$025394`/`$0253D4`
(and mode `$A(a6)` at `$0253F2`).**

**grid+$C = 0 for the room grids, 1 for the overworld.**
`table_init_b` (`$01DA10`) writes grid+$C = `$14(a6)` (the sixth
arg). `new_game_init` (`$01B5D6`) passes 1 for the overworld
(`$FFB08C`) and 0 for the room grids (`$FFB09C`/`$FFB0AC`/`$FFB0BC`).
So **in the room, `world_reposition_leader` takes the L0251EE path
and calls `leader_spawn(mode 6)` — the absolute set — on (nearly)
every Buc step.** Mode 6 sets the camera ABSOLUTELY and does NOT go
through the camera-delay hooks (`$01C2D8`/`$01C300` are only in the
step path). **And it does NOT clear PEND_VALID.**

So the camera delay (interp-fix) is INERT for the room's main camera
path — the camera is set absolutely each step, tracking Buc. But the
step-mode hooks DO fire unpredictably: via the `$0253F2`
`leader_spawn($a(a6), 0, 0)` call in the L0251EE path (mode =
`$a(a6)`, conditional on `-$8(a6)` != 0 and `$c(a6)` != 0) and via
other step-mode `leader_spawn` callers (`$02580C`, `$02F98E`). When
one fires, it applies the STALE pending camera (from a different
step/direction, since mode-6 sets never cleared it) → **the camera
jumps to the wrong cell → Buc appears off-screen** — and the offset
direction flips on a turn → **zigzag**. The delay is also per-call,
not per-step, so the X and Y hooks can desync (X delayed, Y
immediate) on a turn.

**The room camera needs NO delay.** `world_reposition_leader`'s
L0251EE path only moves the camera when Buc is 3+ cells from the
camera centre (L025294: `|dX| >= 3` or `|dY| >= 3` via `cmp.w #$3`;
else the target = the current camera). That **3-cell dead zone** is
the original game's behaviour — the camera stays put while Buc walks
within 3 cells, so the slide IS visible on screen without any delay,
and the camera follows him (snapping at 3 cells) exactly as in the
original ROM. The camera delay adds nothing in the room and causes
the desync. **The camera-delay approach is fundamentally flawed for
the zoom view; this ROM reverts it (see below), it does not try to
fix it.**

### 3. Speed ("like default rom or slightly worse")

Not fully explained statically. The pacing gate is untouched by the
interp/camera-delay hooks, so the cell rate should still be 1 per 4
ticks (~36 frames/cell vs ~22 original). Likely perceptual (full-cell
jumps + camera jumps read as faster than the gradual slide). Not a
separate fix item; the slide fix changes the feel. Restoring original
walk speed needs a pacing change — Dayset's call, not part of this fix.

### 4. Zigzag mechanism (from the missing slide)

Without the slide, Buc's drawn position = his committed cell (no
interpolation) and the camera is one step behind, so Buc sits 1 full
cell ahead of the camera centre in the direction of his last step.
When he changes direction, the offset direction changes instantly →
his on-screen position jumps diagonally → zigzag. Fixing the slide
(via `map_promote_record`) fixes the figure zigzag. The background's
one-step-lag jump on turns (the room jumps in the old direction
because the pending camera is from the old direction) is inherent to
the one-step camera delay and is removed with it. The room still
jumps once per cell at the commit (and the camera snaps at 3 cells) —
fully smoothing the world shift needs the fractional camera (big
rework), not this fix.

### 5. Cutscene order (Dayset, 2026-11-12 ~22:31 EST)

"In a cutscene first goes the world jump then BUC catches up — is
that so? but in normal ROM we are jumping with BUC and with the
world." Confirmed: in the original ROM they jump together (the room
is re-rendered each tick with the camera and the figure at their
current positions, so a cell commit moves them in the same render).
What Dayset sees in the cutscene on the patched ROM — the world
jumping first, then Buc catching up — is the record+10 mechanism
(the record steps at phase 2, the camera at phase 0). This fix does
not touch the cutscene.

## The fix (three byte changes, no new code)

### A. Hook `map_promote_record` → the existing interp blob

`$023480`: `lea.l $197B0,a0` (`41F9 000197B0`) →
`jsr $FDA00.l` (`4EB9 000FDA00`). 6 bytes, same size.

This routes `map_promote_record`'s template computation through the
EXISTING interp blob at `$FDA00` (unchanged, 494 bytes
`$FDA00-$FDBED`: code + slide table; the "150 bytes" figure in the
interp report was the code without the table). The blob ends with the
displaced `lea.l TPLBASE,a0; rts` (`41F9 000197B0` at `$FDBA4`,
then `rts`), which is exactly what both hook sites need, and the
frame layout matches `hero_track`:

| | hero_track | map_promote_record |
|---|---|---|
| record | 8(a6) | 8(a6) (`movea.l $8(a6),a0` at $023442) |
| X | 12(a6) | $C(a6) = 12(a6) (`add.w $c(a6),d0` at $0234AA) |
| Y | 14(a6) | $E(a6) = 14(a6) (`add.w $e(a6),d0` at $02349C) |
| heightOff | 16(a6) | $10(a6) = 16(a6) (`add.w $10(a6),d0` at $0234A0) |
| template offset | d0 | d0 (computed at $023462-$02347E, before the hook) |

The blob saves/restores d1-d3/a0-a2 and never touches d4/d5/a3/a6.
`map_promote_record` sets d4 = record+4 (or 0x20) BEFORE the hook
and uses it at `$023466-$02346A` (before the hook); d4 is dead after
the hook. a3 is set AFTER the hook (`movea.l d0,a3` at `$023486`).
So the blob is safe here. The blob gates on mode 2 + Buc's record,
so non-Buc figures pass through with d0 unchanged (small overhead
only). The slide is gated off while a script runs (`$FF0110` != 0),
so the cutscene keeps its own walk template + wobble exactly as
before (during a cutscene the template override selects 36+dir, the
same walk template the script uses — e.g. 38 for Buc walking south —
and the latch turns off at rest, so the standing figure keeps its
static template).

This fixes the legs (walk template 36+dir cycles per phase), the
slide (position interpolates old → new over phases 0–3, with the
template wobble subtracted), and the figure zigzag (smooth direction
changes). The `hero_track` hook at `$023202` is kept intact
(harmless; `hero_track` never runs for Buc in the zoom view, and it
still serves any +$A=0 figure).

The feet-fix replay calls the recorded routine, so for Buc
(`map_promote_record`) the hook fires at the actual draw time
(during `fig_replay`, after the terrain is drawn) — the slide and
template apply on the flat room, and the figure is drawn on top of
the finished terrain (feet visible).

### B. Revert the camera-delay step-mode hooks (the delay is the cause)

`$01C2D8`: `jsr $FDE00` (`4EB9 000FDE00`) →
`move.w d0,$FF0E8E.l` (`33C0 00FF0E8E`, the original bytes).
`$01C300`: `jsr $FDE3A` (`4EB9 000FDE3A`) →
`move.w d0,$FF0E90.l` (`33C0 00FF0E90`, the original bytes).

This removes the flawed delay. The camera returns to the original
mode-6 behaviour (3-cell dead zone + clamp), which keeps Buc
on-screen and the walk straight. The overworld is unchanged (the
hooks took the immediate path in mode 1; the original moves ARE the
immediate path). The cutscene is unchanged (the hooks took the
immediate path while a script ran; the original moves are the
immediate path, and the cutscene camera moves via mode 6 anyway).
The task explicitly sanctions this: the camera delay "must stay
intact unless the diagnosis shows one of them is the cause" — the
diagnosis above shows it IS a cause (it desyncs the camera in the
room), so it is reverted, not rebuilt.

### C. Restore the camdelay blob region to 0xFF padding

`$FDE00-$FDE7B` (124 bytes) → `0xFF`. The blob is now unreferenced
(both hook sites reverted); restoring it to padding keeps the ROM
clean. It sits above the runtime checksum range (`$000000-$FD07B`),
so this does not affect the runtime sum.

## What stays intact

Flat/checkerboard (`$FD400`), feet fix (`$FD600`), subcell override
(`$FD800`), pacing gate (`$FD900`), interp slide (`$FDA00`) — all
byte-identical to the base (asserted in `build.py`). The `hero_track`
interp hook (`$023202`), pacing gate hook (`$0228CC`), `fig_replay`
hook (`$01C0D6`), flat call sites (`$01BC1A`/`$01BC3C`/`$01BC84`),
and mode-6 camera writes (`$01C242`/`$01C264`) are untouched. Big
world stays textured. Cell rate unchanged (1 cell / 4 ticks).

## Build checks (minimal only)

- Base ROM MD5 verified (`44353892c7a006300bfae2535ad6eaf8`); original
  ROM MD5 verified unchanged (`30c18fdbe2183f64702ae9f1a45d63f9`).
- Hook-site bytes verified before patching (`$023480` was
  `41F9 000197B0`; `$01C2D8` was `4EB9 000FDE00`; `$01C300` was
  `4EB9 000FDE3A`; the original moves were read back from the
  original ROM, not assumed).
- Interp blob intact (`movem.l d1-d3/a0-a2,-(a7)` at `$FDA00`;
  displaced `lea.l $197B0,a0` at `$FDBA4`; slide table `$FDBAC`).
- Camdelay blob present before removal (`tst.w $FF0110` at `$FDE00`).
- Checksums: header `0xD0E0` → `0x5604`, runtime `0x92B36312` →
  `0x0CB56500`; `checksum.py verify-all` exit 0 (both OK).
- 128 bytes differ, all inside the three hook sites, the camdelay
  blob region, or the two checksums (see `changed-bytes.txt`).
- IPS round-trip verified: base + `interp-fix2.ips` == fixed ROM.

## What was NOT verified

No live probes, screenshots, cadence measurements, or playtest
verification (Dayset's rule). In particular not verified: whether
Buc's legs animate in the zoom view, whether he stays on-screen,
whether the walk is straight, whether the slide reads as smooth in
real play, standing-still (no jitter), all four directions,
direction-change responsiveness, menu/teleport, other rooms, the
cutscene (code-gated only), or speed in real play. The probe drive
to room 30 never succeeded in 4 iterations (interp-fix report), so
the `map_promote_record` hook firing for Buc in the room-30 walk
is inferred from the cutscene data (record+$A = 1) and the static
read, not probe-confirmed. The 128-entry feet-fix list-cap fallback
is untested live. The room still jumps once per cell at the commit
(and the camera snaps at 3 cells) — that is the big-rework item,
not this fix.
