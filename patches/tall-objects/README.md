# Highlighted tall objects (tall-objects)

Base: `rop-noise.rom` (MD5 `b35a634181a99271af6e9c829beb7339`) — grey-noise
fill, flat gate (mode 2 only), figures deferred to a post-pass (feet fix),
subcell template override (hero_track hook).

This patch rebuilds the `$FD400` flat blob, keeping the grey-noise fill
for walkable land and water, and giving the tall objects (walls, trees —
the solid impassable objects) a grey shading/texture so they read as
tall and stand out clearly, not just a flat dark grey. Dayset: "textures
are the missing piece now, at least some solid should be highlighted."

## What it does

The impassable category is now 4 FIXED tall patterns (not 4 hash
variants): a vertical gradient + horizontal courses, in grey.

| Tile row | Rows alternate | Palette idx | Day luminance |
|---|---|---|---|
| Top (lit top edge, the highlight) | idx 11 / idx 9 | 11 / 9 | 182 / 109 |
| Bottom (shadowed base) | idx 7 / idx 0 | 7 / 0 | 72 / 0 |

Whole object avg luminance ~91 (day), vs land ~145 and water ~90.
The object stays clearly darker than land on average (reads as a
solid, not ground), while its bright top edge (idx 11, the brightest
grey) highlights it so it stands out clearly. The alternating rows are
the texture (stone courses); the bright-top / dark-base gradient is the
height cue (reads as tall). The gradient repeats per cell (each cell is
bright at its top and dark at its base), so a wall reads as stacked
courses — the fill only ever sees one cell at a time, so a per-object
gradient is not possible.

The impassable rule is unchanged from the noise ROM (the `$1C892`
move-path gate, `move_cost_calc` returning 0 = blocked), NOT the
`$02DC0C` statue-summon gate (which would wrongly mark Grass as a
wall). Validated on chunk 233 (location 156, the Buc cutscene room):
286 impassable cells (Forest 4 ×184, 31 ×84, 32 ×6, 33 ×12).

## Implementation

- `.blocked` loads all 4 tall patterns directly (d4/d0 = top pair,
  d1/d2 = base pair) and jumps to `.fill`, skipping the hash-based
  `.patterns` load.
- `.patterns` (land/water) copies d4/d0 into d1/d2, so the base pair
  equals the top pair (flat ground/water, no gradient).
- The fill writes the top 3 blocks with d4/d0, then swaps d1/d2 into
  d4/d0 and writes the bottom 3 blocks with the base pair.
- The fill is still 48 straight-line longword writes per cell. Added
  cost is ~30 cycles per cell (the tall load for impassable cells
  only, plus 2 moves in `.patterns` and 2 in the fill) — negligible.

## Files

- `source.s` — the rebuilt `$FD400` blob (flat_skip `$FD400`,
  flat_top `$FD412`, table at `$FD5B6`).
- `build.py` — assembles with vasm, verifies the base ROM MD5 and the
  flat call sites, writes the blob, fixes both checksums, emits
  `tall-objects.ips` (round-trip verified) and `changed-bytes.txt`,
  and asserts the feet-fix blob (`$FD600`) and subcell blob (`$FD800`)
  are byte-identical to the base.
- `tall-objects.ips` — patch against `rop-noise.rom`.
- `changed-bytes.txt` — byte ranges that differ from the base ROM.

## Result

- ROM: `rop-tall-objects.rom`, MD5 `9846c168f559bb8acf4a14aca46623b7`
- Header checksum `0xA8B2`, runtime immediate `0xA24C62E7`
  (unchanged — the blob sits past `$FD07B`, outside the
  runtime-checksummed range, as in the noise build).
- Blob: 486 bytes (`$FD400`–`$FD5E5`), 26 bytes free to `$FD600`.
- 297 bytes differ from the base, all inside the blob or the header
  checksum.

## What was NOT verified

No live tests (Dayset's rule — he is the tester). Not verified: whether
the tall objects read as tall and clearly highlighted on screen (the
bright top vs the dark base, the course texture); whether the bright
top edge blends with the land (its top rows are as bright as land's
brightest noise); the look in other rooms (multi-level, water);
menu/teleport; the 128-entry figure-list cap. At night (pal 19) all
greys go very dark (land avg ~31, water ~2, impassable 0) — the same
weak distinction as the original flat fill at night.

## Build

```
python3 build.py
```
