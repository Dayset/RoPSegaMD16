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
below; `docs/maps.md` "The walkable terrain grid"), and the three
remaining bits pinned live the same day: walkability is a `$5EDC4`
terrain-type test (type ∈ {5, 9, 18} or tile `$24`) via `$02dc0c`
(13/13 harness cases); the `$FFB36C` / `$FFB76C` byte meanings and
the `$FFB0CC` 12-byte record layout are live-confirmed (harness
B1/B2, incl. the `$2343A` promotion); the `$197B0` 36-byte record
layout is determined. Still open: the `$197B0` group 1–3 selection,
the `$253FE` mode-`$17` walkability path, the player's arrow-key
step gate, and the chunk tileset/palette pairing (blocks full tile
renders of the 252 chunks). Also open: which screen rec 35 is,
title layer 2's purpose, rec 39's display palette + its scene's
top half, city markers on the world map, `$1194A` flip-path
arithmetic.

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

**Pal 11 vs pal 13 — RESOLVED live (2026-11-10).** The sea uses
**pal 11, not pal 13.** A harness (`.scratch006/harness_cram.s`,
test ROM `9d48497b051c9e105effbcfb78e2a026`) called the map routine
`$17860(0)` and snapshotted all 64 CRAM words before and after.
After the call, CRAM slot 1 is pal 11 exactly (16/16 words); it
matches pal 13 on only 1/16 words. The sea (tile 18, pixel 12) is
CRAM slot 1 entry 12 = `$066C`; the land (tile 131, pixel 0) is
entry 0 = `$0000` (black). Under the corrected CRAM order
(r=(w>>1)&7, g=(w>>5)&7, b=(w>>9)&7, proven live in #016 §10.2)
`$066C` is RGB (218,109,109) — a dusty rose / brownish-red, NOT
blue. The old "blue-grey sea" (pal 11) / "dark-blue sea" (pal 13)
descriptions were from the pre-fix R/B-swapped renderer and are
corrected in `docs/maps.md`; the regenerated PNGs already show the
true colours. The same snapshot confirms slot 0 = pal 10 (day, from
`$170DA`), slot 2 = pal 30, and slot 3 = a sprite palette (from
`$11AE4`). This is the live re-verification `docs/graphics.md`
§10.2 called for. Still open: which screen rec 35 is, city markers
on the world map, the chunk tileset/palette pairing.

**Terrain grid resolved** (details in `docs/maps.md`): there is no
ROM terrain-grid table. The walkable terrain is a runtime assembly:
chunk tilemaps (`$43850`, loaded by `$19692` into a 4-slot cache
at `$FF868C`, chunk index from position via `$1C83E`/`$1C7DA`) +
per-tile properties (`$5EDC4`, 512 words; bits 10–15 = a 6-bit
terrain type, bits 5–9 = flags, low byte = stream-index offset)
+ 176 terrain streams (`$5F524`, decoded by `$E358` → `$E3B4`/`$E412`
into the `$FF1EC0` 1bpp bitmap) + RAM cell grids (`$FFB36C`,
`$FFB76C` byte-per-cell, `$FFB0CC` 12-byte records) driven by the
per-cell routine `$1BA4E`. `$FF1EC0` is shared scratch, NOT a
persistent grid (cleared by `$11DE8`, 26,496 bytes, each redraw;
also used by the `$96120` and sprite loaders). Grid geometry is
per-location in a RAM struct at `$FFB08C` (pointed to by `$FFA7FC`).

**Terrain grid follow-up (2026-11-10) — walkability + record layouts
pinned live** (harnesses in `.scratch006/`, hook at the attract loop
`0x35C`, results in `$FFD000+`):
- **Walkability**: no single flag bit. `$02dc0c` returns walkable
  iff the `$5EDC4` terrain type (bits 10–15) is 5, 9, or 18, or the
  tile index is `$24`. 13/13 live cases (types 5/9/18 → 1; tile
  `$24` type 6 → 1; types 0/1/2/3/4/6/7/8/10 → 0).
- **Correction**: the `$E358` row count (tile bits 13–15) is in the
  TILE word, not in `$5EDC4` — the earlier note misattributed it.
- **`$FFB36C`/`$FFB76C`**: 32×32 byte grids, screen-relative
  (cell = (screen_col+1)×32 + (screen_row+1)); a byte is a `$FFB0CC`
  record index or `$FF` (empty). Type ≥ 0 → `$FFB36C`, type < 0 →
  `$FFB76C`; grid 1 is dispatched (drawn) first, grid 0 second.
- **`$FFB0CC` (12 B)**: +0 type (`$270F` = free), +2/+4 template-index
  components, +6 offset, +8 = 0, +$A dispatch index (0–3). Live:
  two created records matched their args exactly; `$FF0096` is the
  active-record count. Records are per-character draw records
  (created by `$0243d6`; the character slot's +`0x04` holds its index).
- **`$2343A` promotion [live]**: in `$1BA4E`'s `$FFB36C` dispatch,
  a dispatch-1 record moves to `$FFB76C` when that cell is `$FF`.
- **`$197B0` (36 B × 56)**: 4 groups of 8 bytes + 4-byte tail;
  group 0 = (stream-index offset, `$E358` param, x-offset, y-offset);
  index = `$FFB0CC` record's (+2 + +4). Groups 1–3 are variants
  (selection open). Harness B2 exercised `$197B0` records 12 and 24
  through `$1BA4E` with valid streams (18, 28).
- **Attract-context gotcha**: the grids/records are cold (zeroed)
  RAM before any map load, so `$20C5E` must run before `$20E7E`
  or it errors via `$12FA0` (which hangs waiting for input).
