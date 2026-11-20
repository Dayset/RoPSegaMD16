# flat-zoomed-feet — fix Buc's feet being cut/hidden by the flat fill

## Problem

Dayset's playtest of the re-gated flat ROM (`rop-flat-zoomed.rom`,
MD5 `4ee66e521ac9a636d2167c0d55409d92`) reported: "this one is done right,
zoomed world is fast no textures but the BUCs feet most of the times are
cut or hidden". The zoomed view (room, mode 2) is flat and fast, but the
figure's feet are covered by the flat green fill most of the time. The
subcell step would be invisible if the feet are covered, so this is a
blocker for the next sequence item.

## Cause (diagnosed, not guessed)

`map_chunk_pos` ($01BA4E) draws per window cell: the terrain for that cell
(face / hidden / top), then the figure for that cell. The original $E358
terrain decode writes only the diamond-shaped tile pixels (transparent
corners), so a later cell's terrain never covers a figure drawn by an
earlier cell. The flat_top 3x2 block fill is a SOLID 24x16 px rectangle.
A cell processed AFTER the figure's cell whose solid fill overlaps the
figure's lower pixels covers the feet — in particular the cell at
(d4+1, d5+1) has the same buffer X and Y+16, so its fill lands exactly on
the tile the figure's feet stand on. No fill-shrinking fixes it: even a
1x1 fill of that tile covers the feet, because the feet ARE on that tile.
The figure must be drawn after the fills that overlap it.

The figure's height offset is NOT the cause: the fig_* stubs already zero
it, so the figure stands on the flat plane at baseY, at the correct Y —
only its lower pixels are overwritten. (Same mechanism that made Thalmus
invisible in the flat ROOM ROM — flat-zoom report §5b/§7.)

## Fix — defer figure draws to a post-pass

The 8 fig_* stubs (which already hook the figure call sites in
map_chunk_pos) RECORD the call instead of drawing when gated (mode 2):
(routine addr, record, X, Y, heightOff=0) into a list in RAM. `fig_replay`,
hooked at the end of map_chunk_pos ($01C0D6, replacing the 6-byte
`tst.w $FF013C.l` with a jsr), draws every recorded figure on top of the
finished terrain, then re-executes the tst and returns so the beq at
$01C0DC works as before. When not gated (mode 1, big world) the stubs
draw immediately exactly as before (the original textured render orders
figures correctly via the diamond transparency), and the replay is a no-op.

The map-promote side effect is NOT deferred: the $B36C/$B76C map update in
map_chunk_pos (L01BF22) runs inline, before the jsr to the fig_* stub, so
it still happens during the cell loop. Only the DRAW is deferred. The
update moves a record between the two cell→record maps for the CURRENT
cell only, so deferring the draw cannot affect any other cell's lookup in
the same render.

## Figure list (RAM)

- Count (word) at $FFD800, entries at $FFD802, 14 bytes each
  (routine addr 4, record ptr 4, X 2, Y 2, heightOff 2).
- Max 128 entries ($FFD802-$FFDF02). If the list is full the stub falls
  back to drawing immediately (old behaviour, height offset zeroed).
- Free: no code references $FFD800+ (grep in rop.s found nothing);
  ram.csv names nothing there except $FFD2EA (below this region, used by
  attract_scroll and gfx_bitmap_dither_fill); probes used $FFD800 for logs
  without breaking the game; the stack only reaches ~$FFEB42.

## Patch sites (all in the flat-zoomed base ROM)

| Address | Original bytes | Patched to |
|---|---|---|
| $01BD98, $01BF14 | `4eb9 000fd560` (jsr fig_hero $FD560) | jsr fig_hero $FD600 |
| $01BDE4, $01C006 | `4eb9 000fd574` (jsr fig_promote $FD574) | jsr fig_promote $FD64C |
| $01BE30, $01C052 | `4eb9 000fd588` (jsr fig_tile $FD588) | jsr fig_tile $FD698 |
| $01BE7A, $01C09C | `4eb9 000fd59c` (jsr fig_anim $FD59C) | jsr fig_anim $FD6E4 |
| $01C0D6 | `4a79 00ff013c` (tst.w $FF013C.l) | jsr fig_replay $FD730 |

Blob: 384 bytes at $FD600 (free 0xFF padding, after the flat-zoomed blob
at $FD400-$FD5F0; padding $FD5F0-$100000 verified all 0xFF in the base
ROM). fig_hero $FD600, fig_promote $FD64C, fig_tile $FD698, fig_anim
$FD6E4, fig_replay $FD730.

## Build

```
python3 build.py
```

Reads `rop-flat-zoomed.rom` (MD5 verified), assembles with vasm, parses
stub addresses from the listing (never hardcoded), verifies the patch
sites, writes the blob, patches the 9 sites, fixes both checksums, emits
`changed-bytes.txt` + `flat-zoomed-feet.ips` (round-trip verified),
asserts the flat-zoomed blob/terrain sites are untouched and the original
ROM is unchanged. Output: `rop-flat-zoomed-feet.rom`.

## Result

- ROM: `rop-flat-zoomed-feet.rom`, MD5
  `9373c0d01cf08c20f28e256daa9ea142` (header 0x5311, runtime 0xA23E15D7).
- 388 bytes differ from rop-flat-zoomed.rom. IPS 576 bytes, round-trip
  verified (base + IPS == fixed ROM).
- Verified by probe (same drive as the flat-zoomed zoom probe): Buc is
  fully visible in the room, green robe down to the yellow feet, on the
  flat green plane. Before/after crops in the report. Room cadence
  7.86 frames/render (unchanged from the flat-zoomed ROM); flat debug
  counters identical (19410 gated, 0 bounds skips, 19409 fills). Big
  world unchanged (textured, cadence unchanged).
- One fix only. Flat colours, gate (mode 2 only), room, and big world
  unchanged. No subcell, no dithering, no scroll-and-patch, no sprites.
  Original ROM untouched (MD5 `30c18fdbe2183f64702ae9f1a45d63f9`).

## Pitfalls (for the next agent)

- `addq.w #10,a7` is invalid (ADDQ immediate only 1..8) — vasm error
  2026. Use `lea.l 10(a7),a7` to pop 10 bytes of args (the same pattern
  the original code uses).
- The $01C0D6 instruction is `tst.w $FF013C.l` = `4a79 00ff013c`
  (opcode 0x4A79, absolute long), not 0x4A39 (absolute short).
- The probe RAM log at $FFD800 collides with this patch's figure list.
  A probe run against this ROM must move its log base (the feet probe
  used $FFDF80). The shipped ROM has no probe code, so this only
  matters for verification.
