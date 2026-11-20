# Dither — checkerboard pattern on the flat ground plane

## Deliverable

- **ROM:** `~/workspace/rop-work/dither/rop-dither.rom`,
  MD5 `09d74baa339314b40e02344545f67f66`
  (header checksum `0xB932`; runtime immediate `0xA24C62E7`, unchanged
  from the subcell ROM — the blob sits past `$FD07B`, outside the
  runtime-checksummed range).
- **Patch:** `~/workspace/rop-work/dither/patches/dither/`
  (`source.s`, `build.py`, `README.md`, `changed-bytes.txt`,
  `dither.ips` 516 B, round-trip verified: base + IPS == ROM exactly).
- **Base ROM unchanged** (`rop-subcell.rom`, MD5
  `fa3255df47fe90efc6cb1c36c2e495db`); **original ROM untouched**
  (MD5 `30c18fdbe2183f64702ae9f1a45d63f9`).

One fix only, on top of the subcell ROM: the flat plane (mode 2, the
zoomed view / room) fills with a checkerboard pattern instead of a
solid colour. The big world (mode 1) stays textured.

## Design

The flat fill (`flat_top` in the `$FD400` blob) writes a solid 24×16 px
rectangle per cell. This patch replaces the solid fill with a
pixel-level checkerboard — the flat colour alternating with black
(palette idx 0, the cleared-buffer background):

- Land: even lines `$30303030` (pixels 3,0,3,0,3,0,3,0),
  odd lines `$03030303` (pixels 0,3,0,3,0,3,0,3).
- Water: even lines `$10101010`, odd lines `$01010101`.

The pattern is FIXED (the same pixels every frame, so no flicker) and
GLOBALLY CONSISTENT: each block is 8 px wide and 8 lines tall (both
even), so the phase at the start of every block matches the global
pixel/line parity — the checkerboard is continuous across the whole
plane, not per-block. (A block-level alternating pattern would have
been coarser; pixel-level matches Dayset's original checkerboard idea
— texture pixels alternating with background, a dithered/halftone
look.)

Cost is identical to the solid fill: the same 48 longword writes per
cell, no decoder calls. The only extra work is one `move.l #imm` per
`flat_top` call (to load the odd-line pattern into d0). The speed the
flat fill bought is preserved.

### Second colour choice

Black (idx 0) for both land and water. It is the one second colour
known for certain (the cleared buffer renders black), it is neutral
(it cannot be mistaken for another terrain type), and it matches the
original checkerboard idea (flat colour alternating with background).
Land reads as a dithered (half-brightness) green, water as a dithered
dark blue; the hue difference between them is preserved.

### Implementation

Rebuilt the `$FD400` flat blob from the flat-zoomed source with only
`flat_top` changed:

- Colour selection: land sets d4 = `$30303030` (even lines) and
  d0 = `$03030303` (odd lines); water sets d4 = `$10101010` and
  d0 = `$01010101`. d0 is scratch here — the caller (`map_chunk_pos`)
  reloads d0/d1 after the call (verified: d0 is reloaded at `$01BC92`,
  `move.w (a0),d0`, right after the top call returns; d2/d3 are dead).
- Fill writes: the 48 `move.l d4,(a0)+` writes (6 blocks × 8 lines)
  now alternate d4/d0 per line (line 0 = d4, 1 = d0, 2 = d4, …).

`flat_skip` (`$FD400`) and `flat_top` (`$FD412`) entry points are
unchanged, so the existing call sites (face `$01BC1A`, hidden
`$01BC3C`, top `$01BC84`) still land. The rebuilt blob is 508 bytes
(was 496), ending at `$FD5FC`, before the feet-fix blob at `$FD600`
(the 12 extra bytes extend into free `0xFF` padding, verified in the
build). The `fig_*` stubs and `water_tbl` in the blob are
byte-identical to the flat-zoomed blob, shifted +12 bytes (they are
only referenced from inside the blob; the `fig_*` stubs are dead code
— the call sites point to the `$FD600` feet-fix stubs).

## Build checks (minimal only)

- vasm assembles cleanly; blob 508 bytes, fits `$FD400`–`$FD600`.
- `checksum.py verify-all` passes (header `0xB932`, runtime
  `0xA24C62E7`).
- 333 bytes differ from the base ROM, all inside `$FD400`–`$FD600`
  or the header checksum — verified by an explicit invariant in
  `build.py` (no byte changed outside the blob/checksums).
- Feet-fix blob (`$FD600`–`$FD800`) and subcell blob (`$FD800`–`$FD900`)
  byte-identical to the base; the hero_track subcell hook site
  (`$023202`) and the fig_replay hook (`$01C0D6`) untouched.
- Listing-level verification before the build: `flat_skip`/`flat_top`
  entry addresses match the original blob exactly; the only differing
  bytes in the blob head are 6 branch/lea displacement bytes (+12/+6,
  as expected from the +12-byte shift); the fill writes are 24× d4 +
  24× d0 (was 48× d4); the `fig_*` stubs and `water_tbl` are
  byte-identical, shifted +12.
- IPS round-trip verified: base + `dither.ips` == ROM exactly.

## What was NOT verified

No live tests were run for this build, per Dayset's rule (he is the
tester — no probes, screenshots, cadence measurements, or playtest
verification). In particular, NOT verified:

- The look: checkerboard legibility, land/water contrast, whether the
  dithered plane reads well in the zoomed view and in the cutscene
  room.
- The speed in real play (the fill writes the same number of
  longwords, so no slowdown is expected, but it was not measured).
- Menu/teleport, other rooms (multi-level, water), and the subcell
  movement on this ROM (the subcell override is untouched, but the
  combination was not live-checked).

## Open items (not in this ROM)

- The pacing-gate fix for the subcell movement (Dayset could not see
  subcell movement in the subcell ROM — the leader's cell likely
  commits every tick, not every 4 ticks). That is a separate fix,
  still open, and is NOT in this ROM.
- If Dayset confirms the dithered plane, the next sequence item is the
  pacing gate on top of this ROM (or as he directs).
