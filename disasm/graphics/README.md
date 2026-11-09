# Graphics — tiles, sprites, palettes, compression (issue #005)

Status: DONE 2026-11-09. All claims below are verified by tool runs
(Capstone disassembly, $DD5C re-implementation, BlastEm VRAM debugger,
save-state probes). Confidence is labelled per claim.

## TL;DR

- Tile/sprite graphics live in TWO $DD5C-compressed tables, not in raw
  ROM: the `$96120` table (62 records) and the `$B86AE` table
  (90 records, each `[32-byte palette][36 tiles]`).
- The decompressed tile bytes are **PACKED, 2 pixels/byte, high nibble
  first** — not bitplanar. This is the layout that renders correctly
  (font, terrain, character portraits) and matches BlastEm's VRAM
  debugger on the live logo screen.
- Palette format is Mega Drive 9-bit BGR, `0BBB0GGG0RRR0`, 16 colours
  per palette, 4 palettes in CRAM. Master table at ROM `0x0CC9D8`
  (31 palettes). `$B86AE` records embed their own palette.
- Compression for ALL graphics in both tables is the `$DD5C` LZSS from
  #004 (LE32 length, mask bytes, 4 KB space-prefilled ring). 62/62 and
  90/90 records decompress cleanly. No Nemesis/Kosinski/Enigma found
  in these tables.
- The raw ROM region `0x060000–0x093FFF` is NOT raw tile data
  (renders as noise in every layout) — it is compressed data;
  `disasm/map.md`'s "tile graphics" label for that range is wrong.

## 1. Tile data regions (verified)

### $96120 table — the main asset table
- Records: `0x96120`, 62 × 10-byte records
  (`u32 data_offset, u32 length, u16 type`; offsets relative to the
  data base). Data base `0x9638C`; sources span `0x09638C–0x0B86AE`.
- Every record is type 1 (`$DD5C`) and decompresses cleanly
  (declen == record length field, 62/62).
- Loader: `$1383C(record)` → `$13654` dispatcher → `$DD5C` into RAM
  `$FF1EC0`, returns the pointer. Upload: `$11A7C(src, count)` →
  `$DA04` VDP DMA, verbatim, starting at VRAM tile `$FF0076`
  (running cursor). The title/logo loader at `0x12440` uploads
  records 0, 2, 3, 4, 5 and 7-or-8 with `$FF0076 = 0x234` first;
  `0x14872` uploads records 36 (270 tiles) and 12 (374 tiles).
- Contents (see `inventory.md` for the full table):
  - Most records are tile sets (decompressed length a multiple of 32).
    Largest: rec 53 (536 tiles), rec 37 (586 tiles), rec 6 (438 tiles),
    rec 20 (399 tiles), rec 28 (384 tiles), rec 12 (374 tiles).
  - Recs 22–26 and 48–52 are PAIRED tilemaps (identical sizes, different
    content: 1596/378/112/882/1470 bytes); rec 44 (112 B), rec 54
    (2000 B = 1000 u16), rec 57 (1134 B) are also tilemap-like
    (u16 entries, small tile indices, 0x0800 flip-H / 0x1000 flip-V
    bits). Rec 50 is 112 bytes of zeros.
  - Recs 32, 55, 59 are the three known `$DD5C` TEXT streams
    (Book of Nexus, Book of Buc, title credits — see `disasm/text/`).
  - **Rec 61 is a 4th text stream** (1188 B, bestiary/class text:
    "Here are but some of the beings you will encounter: The Red
    Priests are the servants of Nexus… Knights… Archers…
    Necromancers… Enchanters… Conjurers… Sorcerers…"). Missed by
    #004's scan; fold into #004's record.
  - Rec 4 (256 B, 8 tiles) and rec 10 (2048 B, 64 tiles) are dense
    small tilesets (0% zeros).

### $B86AE table — sprite / portrait table (NEW in #005)
- Records: `0xB86AE`, 90 × 10-byte records (same `$13654` format);
  data base `0xB8A32`. All 90 are type 1 (`$DD5C`), all decompress
  cleanly to exactly 1184 bytes each.
- Each record is `[32-byte palette][1152 bytes = 36 tiles]`.
  The palette is loaded by `$11AE4` via `$11082($FF1EC0, slot)`;
  the 36 tiles are uploaded by `$11B2E($FF1EE0, 0x24, vram_tile)`
  → `$DA04` DMA, verbatim.
- Loader: `$11AE4(record, vram_tile, palette_slot)`.
- Contents: 36-tile graphics, 6×6 tiles = 48×48 pixels each.
  Rec 0 and rec 1 are character portraits (faces); rec 5 is a
  non-face textured graphic (creature/texture — subject TBD).
  Likely character portraits + monster/item sprites; the mapping
  record → character is not yet known (#006/#007).

### Raw ROM regions
- `0x060000–0x093FFF`: NOT raw planar tiles. Rendered as interleaved
  planar at 0x060000/0x070000/0x080000/0x090000 it is noise.
  High entropy (7.0–7.6) — compressed data, not tile graphics.
- `0x094000–0x0CBFFF`: high-entropy block containing the `$96120`
  streams (from `0x09638C`) and the `$B86AE` streams (from `0x0B8A32`).

## 2. Tile layout — PACKED (verified, with one open paradox)

Decompressed tile bytes are **packed, 2 pixels per byte, high nibble
first**: byte `b` at row `r`, position `k` gives pixels `b >> 4` then
`b & 15` at x = 2k, 2k+1. 8 rows × 4 bytes = 32 bytes per 8×8 tile.

Evidence (all verified):
- `$B86AE` rec 0 renders as a coherent character portrait (face, eyes,
  mouth, hooded garment) ONLY in packed layout; both planar layouts
  (interleaved and sequential) render it as vertical bars / noise.
  See `portrait_b86ae_rec00.png`. Rec 1 is a second portrait.
- `$96120` rec 0 renders as a complete readable ASCII font + "MORE"
  UI element ONLY in packed layout. See `font_rec00_pal10.png`.
- Rec 6 renders as coherent repeating orange-diamond / blue-wave
  terrain ONLY in packed layout. See `terrain_rec06_pal1.png`.
- Byte statistics: 62.6% of `$B86AE` rec 0 tile bytes have hi==lo
  nibble (solid 2-pixel runs), vs ~6% expected for bitplane data;
  top byte value is `0x11` (342 occurrences); zero `0xFF` bytes.
- BlastEm's VRAM debugger (live logo screen) shows the same font
  rendering correctly, matching the packed renders.
- The packed decoder round-trips exactly on synthetic data, and the
  planar decoder round-trips exactly on synthetic standard-planar
  data — so neither decoder is buggy; the DATA is packed.

PARADOX (open, for #015/#016): the textbook Mega Drive VDP pattern
format is bitplanar, and the upload path (`$1383C` → `$11A7C` →
`$DA04` DMA; `$11AE4` → `$11B2E` → `$DA04` DMA) shows NO
packed→planar conversion in the disassembly — the DMA is verbatim —
yet the game displays correctly. Either a conversion routine is not
yet located (re-check `$11A7C`/`$11B2E`/`$DA04` callers and the
`0x1485E` routine past `0x14986`), or the game's tile format is
genuinely packed. `tools/render_tiles.py` keeps `--layout planar` /
`planar-seq` for comparison; they render the same data as bars.

## 3. Palettes (verified)

Format: Mega Drive 9-bit BGR word `0BBB0GGG0RRR0` — bits 1–3 blue,
5–7 green, 9–11 red; bits 0, 4, 8, 12–15 are zero. RGB = channel ×
255/7. 16 colours per palette, 4 palettes (64 colours) in CRAM
(128 bytes). Colour 0 of a palette is the transparent colour for
sprites (and the background colour for planes, per the tilemap).

Locations:
- Master table: ROM `0x0CC9D8–0x0CCDB8`, 31 palettes × 16 colours
  (496 words, 992 bytes). Found by scanning for runs of
  palette-valid words. After the table: "MAIN", "Inven", "Spells",
  "Party", "Search" menu strings — this region (`0x0CC000–0x0D7FFF`)
  holds UI data.
  - Pal 0: standard MD test ramp (0000 0A00 00A0 0AA0 000A 0A0A 004A
    0AAA 0444 0E44 04E4 0EE4 044E 0E4E 04EE 0EEE).
  - Pal 1: blues/greys. Pal 2: greens/cyans. Pal 8: all black.
    Pal 9 and 20: all white (0EEE) — fade palettes. Pal 15/16:
    red/orange ramps.
- Loader: `$11082(table_ptr, slot)` — computes CRAM write address =
  slot×32 bytes, writes command word `0xC000|(slot<<5)` then `0x0000`
  via `$D9E2` (VDP control `$C00004`), then loops 16 times reading
  words from the table and writing them via `$D9EE` (VDP data
  `$C00000`). `$D9E2` = write word to `$C00004`; `$D9EE` = write word
  to `$C00000`.
- Call sites: `$11E06` (title setup) loads pal 10 (`$CCB18`) → slot 0
  and pal 0 (`$CC9D8`) → slot 1; the `0x148xx` routine loads pal 8
  (all black, `$CCAD8`) → slots 1, 2, 3 (fade-to-black).
- `$B86AE` records embed their own 16-word palette in the first
  32 bytes of the decompressed record (loaded by `$11AE4`).
  Example: rec 0 palette words `0080 0000 0AAA 0666 0444 0008 0068
  0048 0046 0026 0024 0004 0002 0088 00AA 0EEE` (green background,
  blue face tones, white highlight).
- Live CRAM (BlastEm save state, logo screen) contains pal 8 (black),
  pal 15, pal 16, pal 14, pal 13 in sequence — the logo uses the
  red/orange ramp palettes. The font glyphs are pixel value 1; on the
  live logo screen they render blue, while pal 0 / pal 10 both give
  red at index 1 — the exact CRAM slot the font uses is TBD (#015).

## 4. Compression (verified)

All graphics in both tables go through the `$DD5C` LZSS from #004:
LE32 decompressed length, mask bytes LSB-first (1 = literal,
0 = 2-byte backref: 12-bit offset, length = low nibble + 3), 4 KB ring
at `$FF0EAC` pre-filled with spaces (`0x20`), write position `0xFEE`.
- `$96120`: 62/62 records decompress cleanly.
- `$B86AE`: 90/90 records decompress cleanly.
- No Nemesis, Kosinski, or Enigma scheme found in either table
  (#017 overlap: for THESE tables the answer is `$DD5C`; whether any
  other table uses another scheme is still open for #017).
- The three text streams and the 4th (rec 61) are the same `$DD5C`
  scheme — graphics and text share one decompressor.

## 5. Upload / VDP routines (verified by Capstone)

- `$13654(table, database, index, dest)` — asset dispatcher:
  record = table + index×10; type at record+8: 0 → `$DE1A` (plain
  copy), 1 → `$DD5C` (decompress), 5 → `$136FC` (dictionary word
  expansion). Type field is a word; the dispatch is
  `tst → 0: $DE1A; -1: $DD5C; -4: $136FC`.
- `$1383C(index)` — loads a `$96120` record into `$FF1EC0`, returns
  the pointer. (Args: `$96120` data base, `$9638C` record table.)
- `$11A7C(src, count)` — uploads `count` tiles from `src` to VRAM at
  the running cursor `$FF0076` (tile index), advances the cursor,
  returns the old cursor. DMA length = count×16 words, dest =
  `$FF0076 << 5` (VRAM byte address).
- `$11B58(count)` — allocates `count` tiles (returns old cursor,
  advances it). `$11B2E(src, count, vram_tile)` — uploads `count`
  tiles to an explicit VRAM tile index.
- `$DA04(src, dest, len)` — textbook VDP DMA: R15=2, R19/R20 = length
  (words), R21–R23 = source>>1, DMA trigger control word
  `0x4000|(dest&0x3FFF)` then `0x80|((dest>>14)&3)`, waits for the
  DMA-busy bit 1 of `$C00004` to clear.
- `$11AE4(record, vram_tile, palette_slot)` — loads a `$B86AE`
  record: `$13654` into `$FF1EC0`, `$11B2E($FF1EE0, 0x24, vram_tile)`
  for the 36 tiles, `$11082($FF1EC0, slot)` for the palette.
- `$11082(table_ptr, slot)` — palette loader (see §3).
- `$FF0076` is the running VRAM tile-index cursor; `$FF1EC0` is the
  shared decompression buffer; `$FF0EAC` is the `$DD5C` ring buffer.

## 6. Rendered tilesets (in this directory)

All rendered with `tools/render_tiles.py` (packed layout, the
verified format). Regenerate with e.g.:
`python3 tools/render_tiles.py sprite 0 --out disasm/graphics/portrait_b86ae_rec00.png`

- `font_rec00_pal10.png` — `$96120` rec 0, 103 tiles, pal 10.
  Complete ASCII font (0x21–0x7E in order: `!"#$%…`, digits,
  `A–Z`, lowercase) + "MORE" UI element + solid white blocks.
  Uploaded by the `0x12440` title/logo loader (103 tiles, VRAM tile
  0x234 first). Also rendered with pal 0 (`font_rec00_pal0.png`;
  identical — both palettes have red at index 1).
- `terrain_rec06_pal1.png` — `$96120` rec 6, 438 tiles, pal 1.
  Repeating orange-diamond / blue-wave patterned terrain (floor/wall
  or map art). True palette TBD (pal 1 shown as an example).
- `logo_rec12_pal1.png` — `$96120` rec 12, 374 tiles, pal 1. Dense
  blue/white/orange strata; uploaded with rec 36 by `0x14872`.
  True palette TBD.
- `portrait_b86ae_rec00.png` — `$B86AE` rec 0, 36 tiles, embedded
  palette. Character portrait (face, hooded garment), 48×48 px.
- `portrait_b86ae_rec01.png` — `$B86AE` rec 1, 36 tiles, embedded
  palette. Second character portrait (moustached face, red garment).
- `portrait_b86ae_rec05.png` — `$B86AE` rec 5, 36 tiles, embedded
  palette. Non-face textured graphic (creature/texture — subject TBD).

Earlier planar renders (`rec00_pal1.png`, `rec03_pal1.png`,
`rec03_pal10.png`) were deleted — they showed the WRONG layout
(vertical bars) and are superseded by the packed renders above.

## 7. Open questions for #015 / #016 / #017

- Packed-vs-planar paradox (§2): locate the conversion, if any, or
  confirm the tile format is genuinely packed. Re-check `$11A7C` /
  `$11B2E` / `$DA04` callers and the `0x1485E` routine past `0x14986`
  (where `$FF4EC0` is used). The BlastEm save-state section table was
  never fully parsed — decoding it would pin down VRAM/CRAM offsets
  and let VRAM bytes be compared directly against packed vs planar
  conversions of the on-screen records.
- Which palette slot does the font use on the logo screen? (Live
  font renders blue; pal 0 and pal 10 both give red at index 1.)
- True palettes for rec 6 (terrain), rec 12, rec 36, and the other
  large `$96120` tilesets — which `$11082` call loads each, and which
  CRAM slot the tilemap assigns.
- What are the `$96120` tilemap records (22–26, 48–52, 44, 54, 57)
  maps OF? Which tile sets do they reference (base tile indices)?
- `$B86AE` record → character/sprite mapping (which record is which
  character, monster, or item). Rec 5's subject.
- Do any graphics live OUTSIDE the two tables (e.g. a Nemesis /
  Kosinski / Enigma stream elsewhere)? #017 still open for that.
- Sprite attributes / sprite table layout (80 sprites, VRAM `$F000`
  per the VDP map) — not touched in #005.
- The Russian 2012 fan patch added VDP font-upload routines at
  `$FD0D0`, `$1AA70`, `$E8C70` — not yet traced; they may show where
  the font tiles are (re)loaded from.
