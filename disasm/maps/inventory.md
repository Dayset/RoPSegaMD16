# Maps inventory — $96120 tilemap records

Issue #006. All records are type 1 (`$DD5C` LZSS) in the `$96120` table
(sources `0x09638C–0x0B86AE`). Record layout: `[ptr:u32][declen:u32]
[type:u16]`; `declen` is the *decompressed* length (the compressed
length is the gap to the next record's pointer). Every tilemap record
decompresses to a row-major array of u16 tilemap entries (see
`docs/maps.md` for the entry format and the `$1194A` blitter).

Dimensions, tileset and palette were read off the `$1194A` call sites.
Tileset pairing rule (verified for every record): the map's max tile
index is exactly one less than the tileset's tile count.

## Full-screen maps (28 rows x 40 cols)

| rec | src (ROM) | declen | tileset | pal | loader | what it is |
|-----|-----------|--------|---------|-----|--------|------------|
| 9 | 0x09C30D | 2240 | rec 6 (438 tiles) | 11 | 0x12EA0, 0x16360, 0x178FC | **World map of Ushka Bau**: diamond landmass + ornate frame + compass rose. Drawn by three routines. |
| 35 | 0x0A9E3D | 2240 | rec 34 (281 tiles) | 30 | 0x17954 | **Starfield map**: grey diamond on a starfield with planets + green bottom bar. Alternative to rec 9 in routine 0x17860 (arg != 0). Screen identity TBD. |

## Title logo (tileset rec 21, 55 tiles; palette 15, slot 0)

Drawn by the routine containing 0x15E50 to VRAM `$2000` at yoff 3
(10 for the small piece), stride `$80` words (128-wide plane). The
routine's arg selects the layer: arg == 0 draws recs 22–26, arg == 1
draws recs 48–52; they are alternatives, not overlays. Together the
five pieces spell **RINGS OF POWER** (rendered rec 22 = "RING").

| rec | src (ROM) | dims | xoff | layer |
|-----|-----------|------|------|-------|
| 22 | 0x0A2912 | 21x38 | 1 | 1 — "RING" |
| 23 | 0x0A2A5B | 21x9 | 41 | 1 — "O" |
| 24 | 0x0A2AF1 | 7x8 | 52 | 1 — "F" |
| 25 | 0x0A2B49 | 21x21 | 62 | 1 — "P" |
| 26 | 0x0A2C17 | 21x35 | 85 | 1 — "OWER" |
| 48 | 0x0B1550 | 21x38 | 1 | 2 — "RING" variant |
| 49 | 0x0B1630 | 21x9 | 39 | 2 — "O" variant |
| 50 | 0x0B1669 | 7x8 | 52 | 2 — "F" variant |
| 51 | 0x0B167D | 21x21 | 55 | 2 — "P" variant |
| 52 | 0x0B1726 | 21x35 | 76 | 2 — "OWER" variant |

## Location pictures

| rec | src (ROM) | dims | tileset | pal | loader | what it is |
|-----|-----------|------|---------|-----|--------|------------|
| 54 | 0x0B36AC | 25x40 | rec 53 (536 tiles) | 17 | 0x18D6C | Stone archway / trellis with vines, checkered floor, cyan star emblems. Drawn at (yoff 2, xoff 0). |
| 57 | 0x0B5B33 | 21x27 | rec 56 (290 tiles) | 27 | 0x18858, 0x191A6 | Castle with teal roofs/towers. Drawn at (yoff 43, xoff 4). |
| 39 | 0x0AE543 | 24x40 | rec 37 (586 tiles) | ? (14 best-fit) | 0x18818, 0x19166 | Night landscape: mountains, dark forest, snow field, starry sky. Drawn at yoff 40. |
| 40 | 0x0AEB7C | 8x40 | rec 37 (586 tiles) | ? | 0x187D8, 0x19126 | Starfield strip; drawn with rec 39 (variable yoff, presumably 32–39). |

## Small / strip maps

| rec | src (ROM) | dims | tileset | pal | loader | what it is |
|-----|-----------|------|---------|-----|--------|------------|
| 13 | 0x09F867 | 8x40 | rec 12 (374 tiles) | ? | 0x14A4E | Ornate top border strip for text screens (drawn at (0,0)). |
| 14 | 0x09FA47 | 8x40 | rec 12 (374 tiles) | ? | 0x14A12, 0x14EC4 | Ornate side border strip; drawn x7 as bands at yoff 8,16,…,56. |
| 15 | 0x09FB67 | 8x40 | rec 12 (374 tiles) | ? | 0x14BCE | Ornate border strip at variable yoff (`-$4(a6)`). |
| 43 | 0x0AFB38 | 9x32 | rec 42 (40 tiles) | ? | 0x180C2 | Small starfield/night-sky map at runtime (d6,d7) position. |
| 44 | 0x0AFC78 | 7x8 | rec 42 (40 tiles) | ? | 0x18116 | Small map at runtime (d6,d7) position. |

## Tilesets used by the maps above

| rec | src (ROM) | tiles | used by maps |
|-----|-----------|-------|--------------|
| 6 | 0x0985ED | 438 | 9 (world map) |
| 12 | 0x09D3A5 | 374 | 13, 14, 15 (borders) |
| 21 | 0x0A27D7 | 55 | 22–26, 48–52 (title logo) |
| 34 | 0x0A89F5 | 281 | 35 (starfield map) |
| 37 | 0x0AAA8E | 586 | 39, 40 (landscape + strip) |
| 42 | 0x0AFA01 | 40 | 43, 44 |
| 53 | 0x0B180F | 536 | 54 (archway) |
| 56 | 0x0B41DA | 290 | 57 (castle) |

## What is NOT here

- The **walkable overworld / town / dungeon terrain grid** is not in
  this table: none of the `$96120` records is a terrain grid (all 21
  tilemap records above are screens, pictures, borders or the
  schematic world map). Leads are in `docs/maps.md` (open questions).
- `0x0CC000–0x0D7FFF` is not map data (item-name table, palette
  table, menu strings, small-number tables, dialogue text) — see
  `docs/maps.md`.
