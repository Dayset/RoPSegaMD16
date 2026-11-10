# Graphics inventory (issue #005)

Generated 2026-11-09 by decompressing every record with the `$DD5C`
re-implementation (`tools/extract_text.py: dd5c_decompress`). All 62
`$96120` records and all 90 `$B86AE` records decompress cleanly
(declen == record length field).

## $96120 table — records at 0x96120, data base 0x9638C

| rec | declen | tiles | src (ROM) | class |
|----:|------:|------:|-----------|-------|
| 0 | 3296 | 103 | 0x09638C | FONT + UI ("MORE", solid blocks). Rendered: `font_rec00_pal10.png` |
| 1 | 800 | 25 | 0x096655 | tiles |
| 2 | 4608 | 144 | 0x0966F7 | tiles |
| 3 | 2048 | 64 | 0x097297 | tiles (sparse, 74% zeros) |
| 4 | 256 | 8 | 0x09757D | tiles, dense (0% zeros) |
| 5 | 8064 | 252 | 0x097686 | tiles |
| 6 | 14016 | 438 | 0x0985ED | tiles, terrain (orange diamond / blue wave). Rendered: `terrain_rec06_pal1.png` |
| 7 | 8192 | 256 | 0x09A740 | tiles |
| 8 | 6144 | 192 | 0x09B66C | tiles |
| 9 | 2240 | 70 | 0x09C30D | tiles |
| 10 | 2048 | 64 | 0x09C7D4 | tiles, dense (0% zeros) |
| 11 | 3072 | 96 | 0x09CE1C | tiles |
| 12 | 11968 | 374 | 0x09D3A5 | tiles, dense strata. Rendered: `logo_rec12_pal1.png` |
| 13 | 640 | 20 | 0x09F867 | tiles |
| 14 | 640 | 20 | 0x09FA47 | tiles |
| 15 | 640 | 20 | 0x09FB67 | tiles |
| 16 | 4096 | 128 | 0x09FD50 | tiles |
| 17 | 2432 | 76 | 0x0A045C | tiles |
| 18 | 3840 | 120 | 0x0A0770 | tiles |
| 19 | 960 | 30 | 0x0A10D3 | tiles |
| 20 | 12768 | 399 | 0x0A1203 | tiles |
| 21 | 1760 | 55 | 0x0A27D7 | tiles |
| 22 | 1596 | — | 0x0A2912 | TILEMAP (798 u16; paired with rec 48) |
| 23 | 378 | — | 0x0A2A5B | TILEMAP (189 u16; paired with rec 49) |
| 24 | 112 | — | 0x0A2AF1 | TILEMAP (56 u16; paired with rec 50) |
| 25 | 882 | — | 0x0A2B49 | TILEMAP (441 u16; paired with rec 51) |
| 26 | 1470 | — | 0x0A2C17 | TILEMAP (735 u16; paired with rec 52) |
| 27 | 1536 | 48 | 0x0A2D34 | tiles, dense (0% zeros) |
| 28 | 12288 | 384 | 0x0A31A7 | tiles |
| 29 | 10752 | 336 | 0x0A4AC4 | tiles |
| 30 | 448 | 14 | 0x0A62D2 | tiles |
| 31 | 2048 | 64 | 0x0A63B4 | tiles |
| 32 | 2105 | — | 0x0A66E6 | TEXT — Book of Nexus (see `disasm/text/`) |
| 33 | 10496 | 328 | 0x0A6C16 | tiles |
| 34 | 8992 | 281 | 0x0A89F5 | tiles |
| 35 | 2240 | 70 | 0x0A9E3D | tiles |
| 36 | 8640 | 270 | 0x0AA382 | tiles (64% zeros; uploaded by `0x14872`) |
| 37 | 18752 | 586 | 0x0AAA8E | tiles, largest set |
| 38 | 4224 | 132 | 0x0ADD39 | tiles |
| 39 | 1920 | 60 | 0x0AE543 | tiles |
| 40 | 640 | 20 | 0x0AEB7C | tiles |
| 41 | 4608 | 144 | 0x0AECD9 | tiles |
| 42 | 1280 | 40 | 0x0AFA01 | tiles |
| 43 | 576 | 18 | 0x0AFB38 | tiles |
| 44 | 112 | — | 0x0AFC78 | TILEMAP (56 u16) |
| 45 | 896 | 28 | 0x0AFCC9 | tiles |
| 46 | 10240 | 320 | 0x0AFE9A | tiles |
| 47 | 2400 | 75 | 0x0B12FE | tiles (83% zeros) |
| 48 | 1596 | — | 0x0B1550 | TILEMAP (798 u16; paired with rec 22) |
| 49 | 378 | — | 0x0B1630 | TILEMAP (189 u16; paired with rec 23) |
| 50 | 112 | — | 0x0B1669 | TILEMAP (56 u16, ALL ZEROS; paired with rec 24) |
| 51 | 882 | — | 0x0B167D | TILEMAP (441 u16; paired with rec 25) |
| 52 | 1470 | — | 0x0B1726 | TILEMAP (735 u16; paired with rec 26) |
| 53 | 17152 | 536 | 0x0B180F | tiles |
| 54 | 2000 | — | 0x0B36AC | TILEMAP (1000 u16, sequential-ish indices) |
| 55 | 1810 | — | 0x0B3D40 | TEXT — Book of Buc (see `disasm/text/`) |
| 56 | 9280 | 290 | 0x0B41DA | tiles |
| 57 | 1134 | — | 0x0B5B33 | TILEMAP-like (567 u16, mostly zeros) |
| 58 | 2592 | 81 | 0x0B5E0C | tiles |
| 59 | 1590 | — | 0x0B6221 | TEXT — title credits (see `disasm/text/`) |
| 60 | 11776 | 368 | 0x0B666C | tiles |
| 61 | 1188 | — | 0x0B83A1 | TEXT — bestiary/classes, 4th stream (NEW in #005; fold into #004) |

Tilemap records are NOT multiples of 32 bytes; their u16 entries carry
small tile indices with 0x0800 (flip-H) / 0x1000 (flip-V) bits.
The paired tilemaps (22/48, 23/49, 24/50, 25/51, 26/52) have identical
sizes but different content — likely two layers / two variants of the
same maps.

## $B86AE table — records at 0xB86AE, data base 0xB8A32

90 records, ALL type 1 (`$DD5C`), ALL exactly 1184 bytes decompressed
= [32-byte palette][1152 bytes = 36 tiles, 6×6 = 48×48 px].
Loader: `$11AE4(record, vram_tile, palette_slot)`.
Sources span `0x0B8A32–~0x0CC761` (max data offset 0x13D2F); the two
tables are adjacent in the `0x094000–0x0CBFFF` compressed block.

Palette word 0 per record (first word of the embedded 16-word palette):

| recs | palette word 0 |
|-----|----------------|
| 0 | 0080 |
| 1, 2, 3, 5, 6, 9, 10, 17, 20, 23, 36, 37, 42, 44, 47, 49, 56, 62, 65, 74, 75, 76, 78, 84, 86, 87 | 04E4 |
| 4, 15, 24, 41, 88 | 0060 |
| 7, 13, 16, 19, 27, 31, 43, 45, 58, 66, 73, 81, 85, 89 | 00E0 |
| 8, 12, 18, 25, 26, 29, 35, 48, 54, 63, 72, 77, 79, 80 | 00A0 |
| 11, 50, 51, 61, 71, 83 | 0E0E |
| 14, 21, 30, 32, 46 | 0080 |
| 22, 33, 38, 40, 64, 67, 68, 69 | 0E4E |
| 28, 55 | 00C0 |
| 34, 52, 53, 57, 59, 60, 70, 82 | 0000 |
| 39 | 00E6 |

Rendered examples: rec 0 (`portrait_b86ae_rec00.png`, face),
rec 1 (`portrait_b86ae_rec01.png`, face), rec 5
(`portrait_b86ae_rec05.png`, non-face textured graphic).
Render any record with:
`python3 tools/render_tiles.py sprite <N> --out disasm/graphics/sprite_<N>.png`

## Palette table — ROM 0x0CC9D8, 31 palettes × 16 colours

| pal | words (first 4 shown) | note |
|----:|------------------------|------|
| 0 | 0000 0A00 00A0 0AA0 … | MD test ramp |
| 1 | 0000 0000 0444 0888 … | blues/greys |
| 2 | 00E0 0000 000C 004E … | greens/cyans |
| 8 | 0000 ×16 | all black (fade) |
| 9 | 0EEE ×16 | all white (fade) |
| 10 | 0000 0A00 0C60 0080 … | title slot 0 (`$11E06`) |
| 13 | 00A0 0000 0008 00EE … | logo screen (live CRAM) |
| 14 | 0E0E 0000 0222 0444 … | logo screen (live CRAM) |
| 15 | 0000 00E0 0EEC 0ECA … | red/orange ramp, logo screen |
| 16 | 0000 00E0 0020 0060 … | red/orange ramp, logo screen |
| 20 | 0000 0EEE 0EEE 0EEE … | white (fade; word 0 is 0000) |

Full 31-palette dump: read ROM `0x0CC9D8 + n*32`, 16 big-endian words
each. Word format `0BBB0GGG0RRR0`; RGB = channel × 255/7.

## Regenerated 2026-11-10 (corrected colour order) + systematic sheets

The #005 PNGs were rendered with R and B swapped (the old
`md_word_to_rgb`). `tools/render_tiles.py` was fixed in #016 to
`r=(w>>1)&7, g=(w>>5)&7, b=(w>>9)&7` (proven by the minimal VDP test
ROM: CRAM[1]=`0x0E00` displays pure blue). The seven #005 PNGs
(`font_rec00_pal0`, `font_rec00_pal10`, `terrain_rec06_pal1`,
`logo_rec12_pal1`, `portrait_b86ae_rec00/01/05`) were re-rendered with
the fixed renderer, same parameters as the originals (font: 16 cols,
scale 6; terrain/logo: 32 cols, scale 4; portraits: 6 cols, scale 8).
Verified: same dimensions as the originals, and every palette pixel
is exactly the R/B swap of the original (background fill unchanged);
the font's index-1 colour is now blue `(0,0,182)`, matching the live
logo screen, and the rec 0 portrait is warm browns/reds (skin tones)
with no blue-dominant colours.

Systematic sheets (same renderer, corrected palette):
- `$96120` tile records: `recNN_pal1.png` (16 cols, scale 8, master
  pal 1) — all 45 tile records (0–21, 27–31, 33–43, 45–47, 53, 56,
  58, 60). The 17 tilemap/text records (22–26, 32, 44, 48–52, 54,
  55, 57, 59, 61) are NOT rendered as tiles (declen is not a
  multiple of 32). Pal 1 is the default placeholder; the true
  per-record palettes remain open (#005).
- `$B86AE` records: `spriteNN.png` (6 cols, scale 8, each record's
  own embedded palette) — all 90 records, 36 tiles each (6×6).
- Cross-check: `rec00_pal1.png`, `rec06_pal1.png` and `sprite00.png`
  are byte-identical to the #016 `016_font_rec00_full.png`,
  `016_terrain_rec06_full.png` and `016_portrait_b86ae_rec00_full.png`
  (same parameters), so the systematic set and the #016 renders agree.
- Render commands: `python3 tools/render_tiles.py record <N>
  --palette 1 --cols 16 --scale 8 --out disasm/graphics/recNN_pal1.png`
  and `python3 tools/render_tiles.py sprite <N> --cols 6 --scale 8
  --out disasm/graphics/spriteNN.png`.
