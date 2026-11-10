# Issue #006 — Maps / world data

**Milestone:** M3  
**Epic 3**  
**Status:** ✅ done 2026-11-09

## Goal
Locate the world/map data: towns, dungeons, overworld layout.

## Acceptance
- [x] Map data regions identified with addresses
- [x] At least one map decoded and drawn (even roughly)
- [x] Map format documented in `docs/maps.md`

## Evidence

- **Format** (`docs/maps.md`): maps are `$DD5C` tilemap records in the
  `$96120` table (record = `[ptr][declen][type]`, declen = decompressed
  length), drawn by the `$1194A` blitter (`src, base, rows, cols, yoff,
  xoff, stride, dest`; stride in words; VRAM word = map word + base).
  21 tilemap records identified; every one paired with its tileset by
  tracing loader call sites (max tile index = tileset tile count − 1
  in all 21 cases).
- **Decoded and drawn** (`disasm/maps/`, tool `tools/decode_map.py`):
  the world map of Ushka Bau (rec 9, 28x40 — diamond + compass rose),
  the starfield map (rec 35, 28x40), the title logo "RING" (rec 22),
  the archway (rec 54), the castle (rec 57), the night landscape
  (rec 39, palette best-fit). Renders reproduced byte-identically by
  the tool for the four code-pinned palettes.
- **Validation**: the fan world map
  (`docs/research/rings-of-power-ru/RingsOfPower-World.png`) — Dayset
  checked it himself 2026-11-09, legit and perfect as-is, treated as
  verified ground truth. The decoded in-game map matches it on diamond
  orientation, compass rose, and land/sea split; the in-game map is
  schematic (solid land tile, no terrain detail in the tilemap).
- **`0x0CC000–0x0D7FFF` is not map data** (item-name table at
  `0x0CEB00` incl. "MM map"/"map"/"mapbit", palette table `0x0CC9D8`,
  menu strings, dialogue).

## Open (carried to #020 / #011 / #015)

The **walkable overworld / town / dungeon terrain grid** — RESOLVED
2026-11-10 as a runtime structure, not a ROM table (see follow-up
below; `docs/maps.md` "The walkable terrain grid"). Remaining open
bits: which `$5EDC4` flag bit means walkable, the `$FFB36C` /
`$FFB76C` byte meanings, the `$FFB0CC` 12-byte record layout, the
`$197B0` 36-byte record layout, and the chunk tileset/palette pairing
(blocks full tile renders of the 252 chunks). Also open: which
screen rec 35 is, title layer 2's purpose, rec 39's display
palette + its scene's top half, city markers on the world map,
`$1194A` flip-path arithmetic.

## Follow-up (2026-11-10) — chunk renders + terrain grid resolved

**Rendered** (`disasm/maps/chunks/`, tool `tools/render_chunks.py`):
all 252 decoded chunks from the `$43850` table as INDEX images
(one pixel per tile, colour = MD5 hash of the tile index) +
`CHUNKS.md` inventory. 99 × 32×32 (recs 0–76, 230–251), 153 × 11×11
(recs 77–229). Coherent structure (regions, not noise); bulk tiles
28, 29, 36, 86, 87, 47 recur. No tileset/palette pairing is pinned
(tile indices span 0–2027; largest `$96120` tileset is 586 tiles),
so full tile renders are blocked.

**World map re-verified**: regenerating rec 9 reproduces
`world_map_rec09_index.png` byte-identically. The six colour PNGs
(world map pal 11 + pal 13, starfield, archway, castle, landscape)
were R/B-swapped (the #005 renders predated the #016 CRAM-order
correction) and were replaced with corrected renders 2026-11-10
(pixel content matched the fresh renders exactly under an R↔B
swap, all pixels); the title logo was already correct.

**Terrain grid resolved** (details in `docs/maps.md`): there is no
ROM terrain-grid table. The walkable terrain is a runtime assembly:
chunk tilemaps (`$43850`, loaded by `$19692` into a 4-slot cache
at `$FF868C`, chunk index from position via `$1C83E`/`$1C7DA`) +
per-tile properties (`$5EDC4`, 512 words; bits 13–15 = a count of
`$E358` decode rows, bits 5–9/12 + low byte = flags) + 176 terrain
streams (`$5F524`, decoded by `$E358` → `$E3B4`/`$E412` into the
`$FF1EC0` 1bpp bitmap) + RAM cell grids (`$FFB36C`, `$FFB76C`
byte-per-cell, `$FFB0CC` 12-byte records) driven by the per-cell
routine `$1BA4E`. `$FF1EC0` is shared scratch, NOT a persistent
grid (cleared by `$11DE8`, 26,496 bytes, each redraw; also used by
the `$96120` and sprite loaders). Grid geometry is per-location in
a RAM struct at `$FFB08C` (pointed to by `$FFA7FC`).
