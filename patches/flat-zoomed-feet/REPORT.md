# Flat-zoomed feet fix — REPORT

## Summary

**Fix: Buc's feet are no longer cut/hidden by the flat fill.** The figure
draws are deferred to a post-pass after all terrain fills, so figures
render on top of the flat plane. **ROM:
`rop-flat-zoomed-feet.rom`, MD5 `9373c0d01cf08c20f28e256daa9ea142`.**
Verified by probe screenshot (before/after below). One fix only, on top
of the re-gated flat ROM. Dayset is the tester.

## The problem (Dayset's playtest, 2026-11-12 ~20:37 EST)

The re-gated flat ROM (`rop-flat-zoomed.rom`) was "done right, zoomed
world is fast no textures but the BUCs feet most of the times are cut or
hidden". He added (~20:38 EST): "so even if we add subcell animations
they will be invisible" — the feet being cut is a blocker for the subcell
step. Screenshot `~/workspace/user/media_library/image/image-27.png`:
Buc visible from the hood down to the waist/belt/hands, legs/feet missing,
covered by flat green.

## Diagnosis — the fill overwrites the figure (confirmed)

In Dayset's screenshot Buc is visible from the hood down to the
waist/belt/hands, but his legs/feet are missing — covered by flat green.
Comparing the flat-zoomed probe screenshots `zoom_probe_orig_zoom.png`
vs `zoom_probe_rz_zoom.png` (cropped and magnified): the original shows
the green robe + yellow feet at the bottom; the flat shows the robe cut
off, no yellow feet.

Cause: `map_chunk_pos` ($01BA4E) draws per window cell — the terrain for
that cell (face / hidden / top), then the figure for that cell. The
original $E358 terrain decode writes only the diamond-shaped tile pixels
(transparent corners), so a later cell's terrain never covers a figure
drawn by an earlier cell. The flat_top 3x2 block fill is a SOLID 24x16
px rectangle. A cell processed AFTER the figure's cell whose solid fill
overlaps the figure's lower pixels covers the feet — in particular the
cell at (d4+1, d5+1) has the same buffer X and Y+16, so its fill lands
exactly on the tile the figure's feet stand on. No fill-shrinking fixes
it: even a 1x1 fill of that tile covers the feet, because the feet ARE on
that tile. The figure must be drawn after the fills that overlap it.

The height offset is NOT the cause: the fig_* stubs already zero it so
the figure stands on the flat plane at baseY, and the figure is at the
correct Y — only its lower pixels are overwritten. (Same mechanism that
made Thalmus invisible in the flat ROOM ROM — flat-zoom report §5b/§7.)

## Design — defer figure draws to a post-pass

The 8 fig_* stubs (which already hook the figure call sites in
map_chunk_pos) RECORD the call instead of drawing when gated (mode 2):
(routine addr, record, X, Y, heightOff=0) into a list in RAM.
`fig_replay`, hooked at the end of map_chunk_pos ($01C0D6, replacing the
6-byte `tst.w $FF013C.l` with a jsr), draws every recorded figure on top
of the finished terrain, then re-executes the tst and returns so the beq
at $01C0DC works as before. When not gated (mode 1, big world) the stubs
draw immediately exactly as before (the original textured render orders
figures correctly via the diamond transparency), and the replay is a
no-op.

The map-promote side effect is NOT deferred: the $B36C/$B76C map update
in map_chunk_pos (L01BF22) runs inline, before the jsr to the fig_* stub,
so it still happens during the cell loop. Only the DRAW is deferred. The
update moves a record between the two cell→record maps for the CURRENT
cell only, so deferring the draw cannot affect any other cell's lookup
in the same render.

Figure list (RAM): count (word) at $FFD800, entries at $FFD802, 14 bytes
each (routine addr 4, record ptr 4, X 2, Y 2, heightOff 2). Max 128
entries ($FFD802-$FFDF02). If the list is full the stub falls back to
drawing immediately (old behaviour, height offset zeroed). Free: no code
references $FFD800+ (grep in rop.s found nothing); ram.csv names
nothing there except $FFD2EA (below this region, used by attract_scroll
and gfx_bitmap_dither_fill); probes used $FFD800 for logs without
breaking the game; the stack only reaches ~$FFEB42.

Register discipline (documented in source.s): the record stubs use only
d0/d3/a1 (scratch) and never touch d4-d7/a3-a4/a6 (map_chunk_pos's loop
counters / frame pointer) or the stack (no pushes, so the arg offsets
4/8/10/12 stay valid). On stub entry the stack is
[ret(4)][record(4)][X(2)][Y(2)][heightOff(2)]. fig_replay saves/restores
d0-d7/a0-a5 around the loop (a6 untouched) and keeps the stack balanced.

## Build

- Base: `~/workspace/rop-work/flat-zoomed/rop-flat-zoomed.rom`
  (MD5 `4ee66e521ac9a636d2167c0d55409d92`).
- Patch: `~/workspace/rop-work/flat-zoomed-feet/patches/flat-zoomed-feet/`
  (source.s, build.py, README, changed-bytes.txt, flat-zoomed-feet.ips).
- Blob: 384 bytes at $FD600 (free 0xFF padding, after the flat-zoomed
  blob at $FD400-$FD5F0; padding $FD5F0-$100000 verified all 0xFF in the
  base ROM). fig_hero $FD600, fig_promote $FD64C, fig_tile $FD698,
  fig_anim $FD6E4, fig_replay $FD730.
- Patch sites (9): the 8 figure sites `4eb9 000fd560` (hero,
  $01BD98/$01BF14), `4eb9 000fd574` (promote, $01BDE4/$01C006),
  `4eb9 000fd588` (tile, $01BE30/$01C052), `4eb9 000fd59c` (anim,
  $01BE7A/$01C09C) — all jsr to the flat-zoomed blob stubs
  ($FD560/$FD574/$FD588/$FD59C), repointed to the new stubs; plus
  $01C0D6 `4a79 00ff013c` (tst.w $FF013C.l) → jsr fig_replay $FD730.
  All sites verified in the base ROM before patching.
- Build ran clean. **ROM:
  `~/workspace/rop-work/flat-zoomed-feet/rop-flat-zoomed-feet.rom`, MD5
  `9373c0d01cf08c20f28e256daa9ea142`** (header 0x5311, runtime
  0xA23E15D7). 388 bytes differ from rop-flat-zoomed.rom. IPS
  `flat-zoomed-feet.ips` 576 bytes, round-trip verified (base + IPS ==
  fixed ROM). build.py asserts the flat-zoomed blob/terrain sites are
  untouched and the original ROM is unchanged.
- Assembly verified from the vasm listing (feet.lst): `cmpi.w
  #2,$FF00AE.l` = `0C79 0002 00FF00AE`; `move.w $00FFD800.l,d3` =
  `3639 00FFD800`; `mulu.w #14,d0` = `C0FC 000E`; `tst.w
  $00FF013C.l` = `4A79 00FF013C`; `jsr (a0)` = `4E90`; `movem.l
  d0-d7/a0-a5,-(a7)` = `48E7 FFFC`, restore `4CDF 3FFF`; `lea.l
  10(a7),a7` = `4FEF 000A`; stub arg reads `move.l 4(a7),(a1)+` /
  `move.w 8(a7),(a1)+` / `move.w 10(a7),(a1)+` / `clr.w (a1)+`
  correct.
- Build pitfall fixed en route: `addq.w #10,a7` is invalid (ADDQ
  immediate only 1..8) — vasm error 2026. Fixed with `lea.l
  10(a7),a7` (the same pattern the original code uses: `lea.l
  $a(a7),a7` to pop 10 bytes of args).

## Verification — probe screenshot (before/after)

Reused the flat-zoomed zoom-probe drive (probe 1: Buc save state →
cutscene → overworld → B enters room location 30 → B+START menu →
observe). One adaptation: the probe's RAM log at $FFD800 collides with
this patch's figure list, so the probe log base was moved to $FFDF80
(probe sources feet_probe1.s / build_feet_probe1.py / run_feet_probe1.py
in this scratch dir; the shipped ROM has no probe code). Two probe runs:

- Probe 2 (ends in the overworld): LOG_FULL after 42.9 s, logcount 122,
  renders 168, zoomed_seen 1. Room phase 5 cadence 7.86 frames/render
  (frames 3760-3980, renders 100→128) — matches the flat-zoomed ROM.
  Screenshot feet_probe_zoom.png: overworld textured, unchanged.
- Probe 1 (ends in the room, menu open): LOG_FULL after 39.8 s,
  logcount 111, renders 201, zoomed_seen 1. Flat debug counters
  IDENTICAL to the flat-zoomed probe 1: gated calls 19410, bounds skips
  0, fills 19409. Screenshot feet_probe1_zoom.png: room is a flat green
  plane, menu open (INVEN/GOODS/ITEMS/PAPERS/KEYS/RINGS, "THERE IS
  NOTHING OF INTEREST THERE.").

**Before/after (same crop, 680,440–920,700, 3x):**

- BEFORE (flat-zoomed, `zoom_probe_rz_zoom.png`): Buc's green hood and
  upper robe visible; the robe is truncated at the waist/belt; NO yellow
  feet — the lower robe and feet are covered by flat green.
- AFTER (this ROM, `feet_probe1_zoom.png`): Buc FULLY visible — green
  hood, green robe down to the bottom, **yellow feet clearly visible**
  (two yellow horizontal dashes) with the dark outline/shadow under
  them, standing on the flat green plane.

Speed preserved: room cadence 7.86 frames/render in probe 2 phase 5
(same as the flat-zoomed ROM's 7.86). The replay adds no measurable
cost (the figures are drawn once either way; the list is a handful of
entries per render).

## What was NOT verified

- Dayset's playtest (he is the tester). The probe's room is location 30
  (the B-entered room from the City of Division); other rooms (multi-level,
  water) not probed. The Buc cutscene room (mode 2) is also flat and the
  figures there are deferred the same way, but no cutscene screenshot was
  taken on this ROM. Menu/teleport on this ROM not re-checked (code-gated
  only — the replay hook is after the cell loop and re-executes the tst,
  so the beq path is unchanged). The 128-entry list cap was not hit in
  the probe (a room has far fewer figures); the full-list fallback
  (draw immediately) is untested live. Big-world cadence/look in real
  play not re-checked (probe 2's overworld screenshot is textured and
  the mode-1 path is byte-identical to the flat-zoomed ROM).

## Files

- ROM: `~/workspace/rop-work/flat-zoomed-feet/rop-flat-zoomed-feet.rom`
  (MD5 `9373c0d01cf08c20f28e256daa9ea142`)
- Patch: `~/workspace/rop-work/flat-zoomed-feet/patches/flat-zoomed-feet/`
  (source.s, build.py, README.md, changed-bytes.txt,
  flat-zoomed-feet.ips)
- This report: `~/workspace/rop-work/flat-zoomed-feet/.scratch-flat-zoomed-feet/REPORT.md`
- Probe artifacts (same dir): feet_probe1.rom / feet_probe1_zoom.png /
  feet_probe1_zoom.json / feet_probe1_run.log (room screenshot + drive
  log); feet_probe.rom / feet_probe_zoom.png / feet_probe_zoom.json /
  feet_probe_run.log (overworld run); feet_probe1.s / build_feet_probe1.py
  / run_feet_probe1.py (probe 1, log base $FFDF80); feet_probe.s /
  build_feet_probe.py / run_feet_probe.py (probe 2, log base $FFDF80).
- Base ROM untouched: `~/workspace/rop-work/flat-zoomed/rop-flat-zoomed.rom`
  (MD5 `4ee66e521ac9a636d2167c0d55409d92`). Original ROM untouched
  (MD5 `30c18fdbe2183f64702ae9f1a45d63f9`).
