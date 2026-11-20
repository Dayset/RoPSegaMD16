# walk-frames-fix — route the Y-shift hook through map_promote_record

Base: `~/workspace/rop-work/walk-frames/rop-walk-frames.rom`
(MD5 `a698a2f697939fd8a5b11b94837f32f7`) — flat only on mode 2, feet
fix, cutscene loop-walk, frame doubling (one cell per 8 ticks) +
Y-shift hook in hero_track ($023202, blob at $FDA00).
Deliverable: `~/workspace/rop-work/walk-frames-fix/rop-walk-frames-fix.rom`
(MD5 `9ba279759436b96a732d11d9a3f6be0d`, header 0xA6F7, runtime
0xF07ACFB5). Patch in `patches/walk-frames-fix/` (source.s,
build.py, README.md, changed-bytes.txt, walk-frames-fix.ips 43 B,
IPS round-trip verified). Original ROM untouched
(MD5 `30c18fdbe2183f64702ae9f1a45d63f9`).

## Problem

The walk-frames ROM's Y-shift hook is in `hero_track` ($023202,
blob at $FDA00), but Buc is drawn via `map_promote_record`, NOT
`hero_track`. Record+$A selects the figure-draw routine in
`map_chunk_pos` (jump table $01BE86): +$A=0 → hero_track, +$A=1 →
`map_promote_record`, and Buc's record+$A = 1 (probe-confirmed in
the cutscene room, rec10 = 1 in every record; see the interp-fix2
report for the full diagnosis). So the Y-shift hook never fires for
Buc. The frame doubling (one cell per 8 ticks, in the loop driver
blob at $FD800) DOES work, but the smaller Y shift (8,12,16,20,24)
does NOT happen — Buc still jumps by 8 px per step.

## Fix (one 6-byte change, no new blob)

`map_promote_record` $023480: `lea.l $197B0,a0`
(`41F9 000197B0`) → `jsr $FDA00.l` (`4EB9 000FDA00`), routing the
EXISTING walk-hook blob through map_promote_record. The hero_track
hook at $023202 is kept intact (harmless; hero_track never runs
for Buc).

Verified against the disassembly (`disasm/src/rop.s`, read in full
for $02343A–$0234FE) — the frame layout matches hero_track:

| | hero_track | map_promote_record |
|---|---|---|
| record | 8(a6) | 8(a6) (`movea.l $8(a6),a0` at $023442) |
| X | 12(a6) | $C(a6) = 12(a6) (`add.w $c(a6),d0` at $0234AA) |
| Y | 14(a6) | $E(a6) = 14(a6) (`add.w $e(a6),d0` at $02349C) |
| heightOff | 16(a6) | $10(a6) = 16(a6) (`add.w $10(a6),d0` at $0234A0) |
| template offset | d0 | d0 (computed at $023462–$02347E, before the hook) |

d0 is computed before the hook ($023466 `move.w $2(a0),d0`,
$02346A `add.w d4,d0`, $02346C `muls.w #$24,d0`, $023476–$02347E
phase*8 added). a3 is set AFTER the hook (`movea.l d0,a3` at
$023486). X/Y are read AFTER the hook ($02349C/$0234AA), so the
hook's writes to 12(a6)/14(a6) take effect. The blob saves/restores
d1-d3/a0-a2, preserves d0, never touches d4/d5/a3/a6 — safe here.
The blob ends with the displaced `lea.l $197B0,a0` + `rts` (at
$FDAAA, verified in the base ROM), which is exactly what both hook
sites need.

## Dayset's playtest verdict on the walk-frames ROM (factored in)

> "in the cutscene Buc was actually slower than before, smooth but
> after 2 steps he was standing still for longer, so the additional Y
> values did worse."

The Y-shift hook did NOT fire in the ROM he tested (Buc is drawn
via map_promote_record), so the slowness and the stands he saw are
from the frame doubling (one cell per 8 ticks), NOT from the Y shift
— the "additional Y values" he judged were never actually applied.
This fix makes the Y shift actually fire.

**This is NOT assumed to be an improvement.** Dayset's prior verdict
on the Y values was negative. Whether the Y shift, once it fires,
reads as smoother or as worse is for his playtest of THIS ROM to
judge — the Y shift may still read as worse (e.g. if the smaller
steps read as a crawl, or if the stands after 2 steps, which come
from the 8-tick frame doubling and are unchanged by this fix,
dominate what he sees). Judge this ROM on its own merits; do not
treat the Y shift firing as a success in itself.

## Build verification (minimal checks only)

- Base ROM MD5 verified (`a698a2f697939fd8a5b11b94837f32f7`); original
  ROM MD5 verified unchanged (`30c18fdbe2183f64702ae9f1a45d63f9`).
- Hook-site bytes verified before patching: $023480 was
  `41f9000197b0` (`lea.l $197B0,a0`); $023202 was `4eb9000fda00`
  (hero_track hook intact).
- Walk-hook blob verified intact at $FDA00: `48e770e0` (movem.l
  d1-d3/a0-a2,-(a7)) at the start; displaced `lea.l $197B0,a0` +
  `rts` (`41f9000197b04e75`) at $FDAAA; half_tab tail
  `0007fffc00070004fff90004fff9fffc` (N +7,−4; E +7,+4; S −7,+4;
  W −7,−4).
- `source.s` assembles (vasm) to exactly `4eb9000fda00`
  (jsr $FDA00.l, 6 bytes).
- `checksum.py verify-all` exit 0 (header 0xA6F7, runtime
  0xF07ACFB5).
- 10 bytes differ, confined to the header checksum ($0018E–$0018F),
  the hook site ($023480–$023481, $023483–$023485 — 5 of the 6 jsr
  bytes actually change), and the runtime immediate ($FD098–$FD099,
  $FD09B). The walk-hook blob, flat blob ($FD400), feet-fix blob
  ($FD600), and loop blob ($FD800) are byte-identical to the base
  (asserted in build.py).
- IPS round-trip verified: base + walk-frames-fix.ips == fixed ROM.

## What was NOT verified (Dayset is the tester — no live tests)

No probes, screenshots, cadence measurements, or playtest
verification of this ROM. In particular not verified: whether the Y
shift now fires for Buc in the cutscene loop (all four directions);
whether the smaller Y steps (8,12,16,20,24) read as smoother or as
worse (Dayset's prior verdict was negative — see above); whether
the stands after 2 steps persist (they are from the 8-tick frame
doubling, unchanged by this fix); standing-still (no jitter);
menu/teleport; other rooms; the cutscene dialog and Thalmus's moves
still running. The big world stays textured. The flat, feet fix,
loop-walk, frame doubling, and cutscene dialog/script are unchanged.

## Playtest asks for Dayset

1. Does Buc's Y movement now step by 4 px (8,12,16,20,24) instead
   of 8 px (8,16,24) in the cutscene loop?
2. Does the smaller Y shift read as smoother — or does it still
   read as worse (your prior verdict was negative; judge this ROM
   on its own merits)?
3. Do the stands after 2 steps persist (they are from the 8-tick
   doubling, not the Y shift)?
4. Flat room, textured big world, feet still visible, dialog and
   Thalmus still fine?
