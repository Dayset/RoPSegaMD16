# Flat ground plane patch

One fix only: the overworld ground becomes a single flat geometric plane
(no texture, no height steps), and it renders ~2.7x faster than the
original. Built on the ORIGINAL ROM (not v3, not the flat-world ROM).

## What it does

- **Gate** (every stub): `$FF00AE == 1` (overworld mode) AND grid base
  `$FFA7FC == $FFB08C` (overworld grid). This covers the normal world view
  and the zoomed world view (both use the overworld grid; the zoomed view
  differs only in `$FF0E98 == $FFFF`). The room (inside buildings, grid
  `$FFB09C`/`$FFB0AC`/`$FFB0BC`, mode 2) is untouched, and the normal world
  view is flattened too — the zoomed view could not be gated separately
  from the normal world view by grid/mode alone (see the report).
- **Face / hidden height-stack calls** (`$01BC1A`, `$01BC3C`): skipped
  entirely when gated (no `$E358`). The ground has no steps.
- **Top call** (`$01BC84`): replaced by a 3x2 block fill at the BASE Y
  (`-$C(a6)`, not the height-adjusted Y), so all ground cells sit on one
  level. Land = `0x33` (green), water = `0x11` (dark blue, terrain types
  0,2,3,10,11,15,21,22,23). The 3-wide fill bridges the 14-px isometric
  X step (1.75 tiles): a 1-block fill leaves a checkerboard, because the
  central tile column takes only even values.
- **Figures** (hero_track / map_promote_record / map_tile_at_offset /
  map_animated_tile, 8 call sites): the height-offset arg is zeroed when
  gated, so figures stand on the flat plane instead of floating 7-49 px
  above it. Figures are otherwise drawn normally (textured).

## What it does NOT do

- No subcell movement, no dithering, no other changes.
- Buildings flatten with the ground (they are terrain tiles). Trees are
  terrain in the City of Division, so they flatten there too; in locations
  where trees are entities they are drawn by the (untouched) figure path
  and stay detailed. See the report for the image-25.png tree finding.
- The diamond's bottom edge has a small black gap (a few tiles) where the
  fill does not reach the scatter-only edge tiles. The interior plane is
  solid.

## Build

```
python3 build.py
```

Assembles `source.s` with vasm, parses the stub addresses from the
listing (never hardcoded), verifies all 11 patch sites byte-for-byte
against the original ROM, fixes both checksums (`tools/checksum.py
fix-all`), writes `flat-ground-plane.ips` (round-trip verified) and
`changed-bytes.txt`. Output: `~/workspace/rop-work/flat-world/
rop-flat-ground-plane.rom`.

## Result (measured)

| ROM | cadence (frames/render, overworld) |
|---|---|
| original | 22.5 |
| flat ground plane (3x2 fill) | 8.44 |

Speedup **2.67x**. Measured with the safe JMP-pattern probe in
`.scratch-flat-zoomed/` (see `measure_flat_measure.json`); the earlier
1-block figures-corrupted build measured 7.71, the fixed 1-block 8.18,
the 2x2 8.31 — the fill width costs a little speed, the plane is what
matters. Room boot-check passed (fully textured room, Thalmus visible).

ROM MD5: `992465cc0a8dd958febcadf3eede430e` (header 0x45D9, runtime
0xA003394B). Original ROM untouched (MD5 `30c18fdbe2183f64702ae9f1a45d63f9`).
