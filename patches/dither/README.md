# dither — checkerboard pattern on the flat ground plane

One fix only, on top of the subcell ROM (`rop-subcell.rom`,
MD5 `fa3255df47fe90efc6cb1c36c2e495db`): the flat plane (mode 2, the
zoomed view / room) fills with a **checkerboard pattern** instead of a
solid colour. The big world (mode 1) stays textured.

## Design

The flat fill (`flat_top` in the `$FD400` blob) writes a solid 24×16 px
rectangle per cell. This patch replaces the solid fill with a pixel-level
checkerboard — the flat colour alternating with black (palette idx 0,
the cleared-buffer background):

- Land: even lines `$30303030` (pixels 3,0,3,0,3,0,3,0),
  odd lines `$03030303` (pixels 0,3,0,3,0,3,0,3).
- Water: even lines `$10101010`, odd lines `$01010101`.

The pattern is FIXED (the same pixels every frame, so no flicker) and
GLOBALLY CONSISTENT: each block is 8 px wide and 8 lines tall (both
even), so the phase at the start of every block matches the global
pixel/line parity — the checkerboard is continuous across the whole
plane, not per-block.

Cost is identical to the solid fill (the same 48 longword writes per
cell, no decoder calls); only one extra `move.l #imm` per `flat_top`
call. The speed the flat fill bought is preserved.

## What stays intact

- Flat gate (mode 2 only), flat colours (land green / water dark blue
  as the checkerboard's bright nibble), the feet fix (figures deferred
  to a post-pass, `$FD600` blob byte-identical), and the subcell
  override (hero_track hook, `$FD800` blob byte-identical).
- The `$FD400` blob is rebuilt from the flat-zoomed source with only
  `flat_top` changed (colour immediates + alternating fill writes);
  `flat_skip` (`$FD400`) and `flat_top` (`$FD412`) entry points are
  unchanged, so the existing call sites still land. The rebuilt blob
  is 508 bytes (was 496), ending at `$FD5FC`, before the feet-fix blob
  at `$FD600`.

## Build

`python3 build.py` — assembles `source.s` with vasm, verifies the base
ROM, overwrites the `$FD400` blob in place, fixes both checksums, and
emits `rop-dither.rom` + `dither.ips` (round-trip verified) +
`changed-bytes.txt`. Stub addresses are parsed from the vasm listing,
never hardcoded. The base ROM and the original ROM are never modified.

## Not verified

Dayset's playtest (he is the tester — no live tests were run for this
build). The look (checkerboard legibility, land/water contrast) and the
speed in real play are his check. The pacing-gate fix for the subcell
movement is a separate fix and is NOT in this ROM.
