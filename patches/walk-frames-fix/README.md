# walk-frames-fix — route the Y-shift hook through map_promote_record

Base: `rop-walk-frames.rom` (MD5 `a698a2f697939fd8a5b11b94837f32f7`) —
flat only on mode 2, feet fix, cutscene loop-walk, frame doubling
(one cell per 8 ticks) + Y-shift hook in hero_track ($023202, blob
at $FDA00).

## Problem

The Y-shift hook is in `hero_track` ($023202), but Buc is drawn via
`map_promote_record`, NOT `hero_track`. Record+$A selects the
figure-draw routine in `map_chunk_pos` (jump table $01BE86):
+$A=0 → hero_track, +$A=1 → map_promote_record, and Buc's
record+$A = 1 (probe-confirmed in the cutscene room, rec10 = 1 in
every record). So the Y-shift hook never fires for Buc. The frame
doubling (one cell per 8 ticks, in the loop driver blob at $FD800)
DOES work, but the smaller Y shift (8,12,16,20,24) does NOT happen
— Buc still jumps by 8 px per step.

## Fix (one 6-byte change, no new blob)

`map_promote_record` $023480: `lea.l $197B0,a0` → `jsr $FDA00.l`,
routing the EXISTING walk-hook blob through map_promote_record.
The blob ends with the displaced `lea.l $197B0,a0` + `rts` (at
$FDAAA), which is exactly what both hook sites need, and the frame
layout matches hero_track (record 8(a6), X 12(a6), Y 14(a6),
heightOff 16(a6), d0 template offset — d0 is computed at
$023462–$02347E, before the hook; a3 is set AFTER the hook at
$023486; X/Y are read AFTER the hook at $02349C/$0234AA). The blob
saves/restores d1-d3/a0-a2, preserves d0, never touches d4/d5/a3/a6
— safe here. The hero_track hook at $023202 is kept intact
(harmless; hero_track never runs for Buc).

## Dayset's playtest verdict on the walk-frames ROM (factored in)

> "in the cutscene Buc was actually slower than before, smooth but
> after 2 steps he was standing still for longer, so the additional Y
> values did worse."

The Y-shift hook did NOT fire in the ROM he tested (Buc is drawn
via map_promote_record), so the slowness and the stands he saw are
from the frame doubling (one cell per 8 ticks), NOT from the Y shift
— the "additional Y values" he judged were never actually applied.
This fix makes the Y shift actually fire. Whether the Y shift, once
it fires, reads as better or worse is for Dayset's playtest to judge;
it is NOT assumed to be an improvement, and his prior verdict on the
Y values was negative.

## What stays unchanged

Flat ($FD400), feet fix ($FD600), loop driver ($FD800, frame
doubling one cell per 8 ticks), walk-hook blob ($FDA00), hero_track
hook ($023202), cutscene dialog/script. Big world stays textured.

## Build

`python3 build.py` — verifies the base ROM MD5 and the site bytes,
assembles `source.s` (jsr $FDA00.l, 6 bytes), writes it at $023480,
fixes both checksums via `checksum.py fix-all`, emits
`walk-frames-fix.ips` (round-trip verified) + `changed-bytes.txt`.

## Not verified (Dayset is the tester — no live tests)

No probes, screenshots, cadence measurements, or playtest
verification. In particular not verified: whether the Y shift now
fires for Buc in the cutscene loop (all four directions); whether
the smaller Y steps (8,12,16,20,24) read as smoother or as worse
(Dayset's prior verdict was negative — judge this ROM on its own
merits); whether the stands after 2 steps persist (they are from
the 8-tick frame doubling, unchanged by this fix); standing-still;
menu/teleport; other rooms; the cutscene dialog and Thalmus's moves
still running.
