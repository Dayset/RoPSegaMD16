# Grey-noise flat fill (noise)

Base: `rop-dither.rom` (MD5 `09d74baa339314b40e02344545f67f66`) — flat
checkerboard only on mode 2, figures deferred to a post-pass (feet fix),
subcell template override (hero_track hook).

This patch rebuilds the `$FD400` flat blob, replacing the checkerboard
fill with a deterministic grey-noise fill, and draws impassable terrain
(walls, trees) in the darkest grey so Dayset can navigate by sight
instead of by memory.

## What it does

Three categories, tested in order per cell (terrain type from the
`$5EDC4` props word at `-$6(a6)`, bits 10–15):

| Category | Terrain types | Grey (palette idx) | Day luminance (avg) |
|---|---|---|---|
| Walkable land | everything else | 11 / 9 | ~145 |
| Water | 0, 2, 3, 10, 11, 15, 21, 22, 23 | 9 / 7 | ~90 |
| Impassable (walls/trees) | 4, 12, 13, 14, 16, 29, 30, 31, 32, 33, 34 (+ 35–63 out of range) | 7 / 0 | ~36 |

Land : water ≈ 1.6×, land : impassable ≈ 4×, water : impassable ≈ 2.5×
(day palette). The exact darkening factor does not matter — impassable
must only read clearly darker than the walkable ground.

The impassable rule is the `$1C892` move-path gate (`move_cost_calc`
returning 0 = blocked), NOT the `$02DC0C` statue-summon gate (which
would wrongly mark Grass as a wall). Validated on chunk 233 (location
156, the Buc cutscene room): 286 impassable cells (Forest 4 ×184,
31 ×84, 32 ×6, 33 ×12); the `$02DC0C` rule would mark 475.

## Noise

4 precomputed longword patterns per category (all-A, 6A+2B, alternating
A/B, all-B), selected per cell by a deterministic hash of
(tile_col, tile_row): `h = ((col*0x9E37 + row*0x7F4A) >> 8) & 3`.
Even rows use pattern[h], odd rows pattern[(h+1)&3]. Deterministic per
cell — no flicker. The fill is still 48 straight-line longword writes
per cell, the same count as the solid/checkerboard fill.

## Files

- `source.s` — the rebuilt `$FD400` blob (flat_skip `$FD400`,
  flat_top `$FD412`, noise table at `$FD59A`). The four fig_* stubs
  from the flat-zoomed blob are removed — they are dead code on this
  base (figure call sites point at the `$FD600` feet-fix stubs).
- `build.py` — assembles with vasm, verifies the base ROM MD5 and the
  flat call sites, writes the blob, fixes both checksums, emits
  `noise.ips` (round-trip verified) and `changed-bytes.txt`, and
  asserts the feet-fix blob (`$FD600`) and subcell blob (`$FD800`)
  are byte-identical to the base.
- `noise.ips` — patch against `rop-dither.rom`.
- `changed-bytes.txt` — byte ranges that differ from the base ROM.

## Result

- ROM: `rop-noise.rom`, MD5 `b35a634181a99271af6e9c829beb7339`
- Header checksum `0x7BFB`, runtime immediate `0xA24C62E7`
  (unchanged — the blob sits past `$FD07B`, outside the
  runtime-checksummed range, as in the dither build).
- Blob: 458 bytes (`$FD400`–`$FD5C9`), 54 bytes free to `$FD600`.
- 407 bytes differ from the base, all inside the blob or the two
  checksums.

## What was NOT verified

No live tests (Dayset's rule — he is the tester). Not verified: whether
the noise reads as texture (not speckle) on screen; whether the
impassable grey is clearly distinguishable from the walkable ground in
real play (day and night); the look in other rooms (multi-level, water);
menu/teleport; the 128-entry figure-list cap. At night (pal 19) all
greys go very dark (land avg ~31, water ~2, impassable 0) — the same
weak distinction as the original flat fill at night.

## Build

```
python3 build.py
```
