# assets/gfx/ — graphics & map sources for `make assets` (issue #19)

The build input for the $DD5C asset records. `make assets` (tools/build_assets.py)
imports every record from these sources, compresses it with tools/dd5c.py
(Okumura encoder, #17), and splices it into a copy of the ROM at its table
offset. The output ROM (build/assets.gen) is byte-identical to the original
when every record round-trips — that is the proof the sources are complete.

## Layout

```
assets/gfx/
  manifest.json                  the record list (the build reads this)
  tilesets/tileset_recNN.png     $96120 tileset, indexed PNG (mode P)
  tilesets/tileset_recNN_pal.json  display palette (16 CRAM words + index)
  sprites/sprite_recNN.png       $B86AE sprite, indexed PNG (mode P)
  sprites/sprite_recNN_pal.json  embedded palette (16 CRAM words)
  maps/map_recNN.json            $96120 tilemap (rows/cols/entries)
  chunks/chunk_recNNN.json       $43850 chunk (rows/cols/entries + pal/prio)
```

400 records: 37 tilesets + 21 maps ($96120), 90 sprites ($B86AE),
252 chunks ($43850). The 4 $96120 text records (32, 55, 59, 61) are NOT
here — they are #18's text pipeline and are copied through untouched.

## Indexed PNGs (required)

Every PNG is **indexed (mode `P`)**: each pixel IS the palette index
(0–15). This is the only input that round-trips byte-identically.

RGB PNGs are provably lossy and MUST NOT be used as build input:
palettes have duplicate RGB values (palette 1 has entries 0 and 1 both
black; 59/90 sprite palettes have duplicates), so a black RGB pixel
cannot be told apart — the importer resolves it to the lowest index
and the record comes back different. The importer reports every
ambiguous pixel; `make assets` fails if any record differs.

PNG geometry (must match tools/assets_import.py's defaults):
- tileset: 16 columns, scale 2, gap 0 — each tile 16x16 px, grid 256 px wide.
  `tiles` = decompressed length / 32. The last row may have padding slots;
  they must be a single uniform colour (index 0 here).
- sprite: 6 columns, scale 1, gap 0, 36 tiles — 48x48 px, no padding.

The attached PNG palette is for viewing only (the importer reads pixel
values as indices). Tileset PNGs carry the display palette (see below);
sprite PNGs carry the record's embedded palette.

## Palette JSONs

Two shapes (tools/assets_import.py `load_palette_json`):
- `{"palette_words": [16 ints]}` — CRAM words, big-endian u16 as stored.
  Used for sprites (the record's embedded palette) and tilesets.
- `{"palette": [[r,g,b], ...]}` — RGB triples, converted with the
  corrected CRAM order (r=(w>>1)&7, g=(w>>5)&7, b=(w>>9)&7).

Tileset palette JSONs also carry `"palette_index"` — the master-table
palette the tileset is displayed with (from the first KNOWN map that
uses it, else 1). It is documentary for indexed PNGs (the importer
ignores the palette in mode P); it is the fallback if someone swaps in
an RGB PNG. A tileset can be displayed with different palettes in
different contexts (e.g. rec 6 with pal 11 and pal 30), so the index
is the primary context, not a property of the tileset.

## Map / chunk JSON

```json
{"record": 9, "rows": 28, "cols": 40,
 "entries": [{"tile": 0, "flipH": false, "flipV": false}, ...]}
```

Entries are row-major. Each entry: `tile` (0–2047), `flipH`, `flipV`.
Chunk entries additionally carry `"palette"` (0–3) and `"priority"`
(bool) when set — REQUIRED for $43850 chunks (25,223 words use palette
bits 13–14, 3,835 use priority bit 15). $96120 maps never set bits
13–15, so those keys are omitted there. The importer packs entries to
big-endian u16 VDP tilemap words (bits 0–10 tile, 0x0800 flip-H,
0x1000 flip-V, bits 13–14 palette, bit 15 priority).

Map dimensions come from tools/decode_map.py's KNOWN table (rows/cols
from the $1194A call sites). Chunks are 32x32 (2048 B) or 11x11 (242 B).

## Rebuilding from scratch

The sources were generated from rop-original.gen by a one-time export
(.scratch-assets/gen_sources.py in the worktree — not a repo tool):
decompress each record, unpack tiles / tilemap words, write the indexed
PNGs + JSONs + manifest. The canonical regeneration path is
tools/extract_assets.py once it lands on main with indexed-PNG export
and sprite-palette JSON export (it currently emits RGB PNGs and does not
export sprite palettes — those are known gaps, not fixed here).

To rebuild the assets from these sources:

```
make assets        # -> build/assets.gen (+ build/assets/*.dd5c per record)
cmp build/assets.gen rop-original.gen   # byte-identical == proof
```

If any record differs, the build fails with the record id and both
lengths. Growing a record past its original compressed size needs M9
(#16, shiftable build) — until then the pipeline rebuilds
byte-identically.
