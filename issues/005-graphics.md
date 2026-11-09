# Issue #005 — Graphics: tiles, sprites, palettes, compression

**Milestone:** M3  
**Epic 3**  
**Status:** ✅ done 2026-11-09

## Goal
Find how tiles, sprites, and palettes are stored, and whether they are compressed.

## Acceptance
- [x] Tile data regions identified; at least one tileset rendered to PNG
- [x] Palette format + locations documented
- [x] Compression scheme identified (or proven uncompressed) for graphics

## Evidence (verified 2026-11-09; full write-up in `disasm/graphics/README.md` + `inventory.md`)

### Tile data regions
- **$96120 table** — 62 × 10-byte records at `0x96120`, data base
  `0x9638C`, sources `0x09638C–0x0B86AE`. Most records are tile sets
  (largest: rec 37, 586 tiles; rec 53, 536 tiles; rec 6, 438 tiles);
  recs 22–26 / 48–52 are paired tilemaps; recs 32/55/59 are the known
  text streams. Loader `$1383C` → `$13654` → `$DD5C` into `$FF1EC0`;
  upload `$11A7C` → `$DA04` VDP DMA (verbatim). Title/logo loader at
  `0x12440` uploads recs 0, 2, 3, 4, 5, 7-or-8 (VRAM tile `0x234`
  first); `0x14872` uploads recs 36 (270 tiles) + 12 (374 tiles).
- **$B86AE table (NEW)** — 90 × 10-byte records at `0xB86AE`, data base
  `0xB8A32`, sources `0x0B8A32–~0x0CC761`. Every record is exactly
  1184 bytes = `[32-byte palette][36 tiles]`. Loader `$11AE4`:
  palette via `$11082($FF1EC0, slot)`, tiles via
  `$11B2E($FF1EE0, 0x24, vram_tile)` → `$DA04` DMA (verbatim).
- Raw ROM `0x060000–0x093FFF` is NOT raw tile data (noise in every
  layout) — `disasm/map.md`'s "tile graphics" label there is wrong.

### Rendered tilesets (`disasm/graphics/`, packed layout — see below)
- `font_rec00_pal10.png` — $96120 rec 0, 103 tiles: complete ASCII
  font (0x21–0x7E in order) + "MORE" UI element + solid blocks.
- `terrain_rec06_pal1.png` — $96120 rec 6, 438 tiles: repeating
  orange-diamond / blue-wave terrain.
- `logo_rec12_pal1.png` — $96120 rec 12, 374 tiles: dense strata.
- `portrait_b86ae_rec00.png` / `portrait_b86ae_rec01.png` — $B86AE
  recs 0/1, 36 tiles each, embedded palettes: character portraits
  (48×48 px). `portrait_b86ae_rec05.png` is a non-face textured
  graphic. Renderer: `tools/render_tiles.py` (`record` / `sprite` /
  `raw` modes, `--layout`).
- Renders cross-checked against BlastEm's VRAM debugger on the live
  logo screen (same font renders correctly there).

### Tile layout — PACKED (verified)
Decompressed tile bytes are **packed, 2 pixels/byte, high nibble
first** (byte `b` → pixels `b>>4`, `b&15`). Proof: the $B86AE rec 0
portrait and the $96120 rec 0 font render coherently ONLY in packed
layout; both planar layouts give vertical bars/noise; byte stats
(62.6% of rec 0 tile bytes have hi==lo nibble vs ~6% for bitplane
data). **Open paradox for #015/#016:** the textbook VDP format is
bitplanar and the DMA path shows no conversion, yet the game displays
correctly — a conversion routine is not yet located, or the format is
genuinely packed.

### Palette format + locations
- 9-bit BGR word `0BBB0GGG0RRR0` (bits 1–3 B, 5–7 G, 9–11 R);
  RGB = channel × 255/7. 16 colours/palette, 4 palettes in CRAM.
- Master table ROM `0x0CC9D8–0x0CCDB8`: 31 palettes × 16 colours.
  Pal 0 = MD test ramp; pal 8 = all black; pal 9/20 = all white
  (fade); pal 15/16 = red/orange ramps.
- Loader `$11082(table_ptr, slot)` → CRAM via `$D9E2` (control
  `$C00004`) / `$D9EE` (data `$C00000`). `$11E06` loads pal 10 → slot 0,
  pal 0 → slot 1. $B86AE records embed their own palette (first
  32 bytes). Live CRAM at the logo screen holds pal 8/15/16/14/13.

### Compression
- **$DD5C LZSS** (from #004) for ALL graphics in both tables: 62/62
  and 90/90 records decompress cleanly. No Nemesis/Kosinski/Enigma in
  these tables (#017 stays open for other tables).

### Side finding (fold into #004)
- **$96120 rec 61 is a 4th $DD5C text stream** (1188 B, bestiary/class
  text: "Here are but some of the beings you will encounter: The Red
  Priests are the servants of Nexus…"). Missed by #004's scan.

## Open questions (for #015 / #016 / #017)
- Packed-vs-planar paradox: locate the conversion, if any (re-check
  `$11A7C`/`$11B2E`/`$DA04` callers, `0x1485E` past `0x14986`); parse
  the BlastEm save-state section table to compare VRAM bytes directly.
- Font's live CRAM slot (logo font renders blue; pal 0/10 give red at
  index 1). True palettes for rec 6/12/36 and other large tilesets.
- What the tilemap records (22–26, 48–52, 44, 54, 57) map, and which
  tile sets they reference. $B86AE record → character/sprite mapping;
  rec 5's subject. Whether any graphics live outside the two tables.
- Sprite table layout (80 sprites, VRAM `$F000`) — untouched here.
- Russian 2012 patch font-upload routines (`$FD0D0`, `$1AA70`,
  `$E8C70`) — not yet traced.
