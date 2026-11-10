# Maps — format and findings

Issue #006, done 2026-11-09. Tool: `tools/decode_map.py`.
Rendered maps + per-record inventory: `disasm/maps/`.
Chunk renders: `disasm/maps/chunks/` (tool `tools/render_chunks.py`).

Note (2026-11-10): the six colour PNGs in `disasm/maps/` were
regenerated with the corrected CRAM order (r=(w>>1)&7, g=(w>>5)&7,
b=(w>>9)&7) — the #005 renders had R and B swapped (the pixel
content matched the fresh renders exactly under an R↔B swap, all
pixels). The title logo was already correct and is untouched.
`world_map_rec09_index.png` is also unaffected (index colours,
not palette colours).

## Summary (verified)

There is no separate "map file" format in Rings of Power. **Maps are
tilemaps stored as `$DD5C`-compressed records in the `$96120` table**
(the same table that holds the tilesets), and drawn by one blitter,
`$1194A`. 21 of the 62 records are tilemaps: two full-screen maps
(the world map and a starfield map), the title logo (10 pieces in two
layers), three location pictures, a landscape + starfield strip, and
border/small strips. Every map was paired with its tileset by tracing
the loader call sites, and the pairing rule held for all 21: **the
map's max tile index is exactly one less than the tileset's tile
count** (e.g. world map max 437 vs rec 6's 438 tiles).

The **walkable overworld / town / dungeon terrain grid is not a ROM
table** — resolved 2026-11-10 (see "The walkable terrain grid"
below). It is a runtime structure: the 252 chunk tilemaps in the
`$43850` table, per-tile properties in `$5EDC4`, and 176 terrain
streams decoded by `$E358`/`$E3B4`, assembled at runtime into
RAM cell grids (`$FFB36C`, `$FFB76C`) and a 4-slot chunk cache.
None of the `$96120` records is a terrain grid.

## The record format (verified)

`$96120` table, ROM `0x096120`, 62 records, sources `0x09638C–
0x0B86AE`. Each record is 10 bytes: `[ptr:u32][declen:u32][type:u16]`.

- `ptr` is relative to the data base `0x09638C`.
- `declen` is the **decompressed** length (verified: rec 9's field is
  2240 = 1120 words × 2, while its compressed stream is only 1223
  bytes — the gap to rec 10's pointer). The compressed length is
  implicit from the next record's pointer.
- `type` 1 = `$DD5C` LZSS (the only type seen; all 62 records in
  #005 + all 21 tilemaps here decompress cleanly with it).

## The tilemap entry format (verified)

A decompressed tilemap record is a row-major array of u16 words,
`rows × cols` entries, no header:

| bits | meaning |
|------|---------|
| 0–10 | tile index (offset from the tileset's VRAM base) |
| 11 | `0x0800` flip-H — passes through into the VRAM word |
| 12 | `0x1000` flip-V — passes through into the VRAM word |

Per-tile flips are used (world map rec 9: 30 flip-H + 9 flip-V
entries; starfield rec 35: 83 flip-H + 160 flip-V). The tile index is
**not** a VRAM tile number by itself — it is added to the tileset's
base by the blitter.

## The blitter `$1194A` (verified from disassembly, 0x1194A–0x11A18)

Signature: `$1194A(src, base, rows, cols, yoff, xoff, stride, dest)`.

- VRAM word written = `map_word + base`. `base` = the tileset's VRAM
  tile index plus palette/priority bits: `+$2000` palette 1, `+$4000`
  palette 2, `+$6000` palette 3, `+$8000` priority bit (palette 0).
  The map word's own flip bits pass through into the VRAM word, so a
  tile flips exactly when its map entry says so.
- Dest byte address for map row `r`, col `c`:
  `((r + yoff) * stride + xoff + c) * 2 + dest`.
  **Stride is in words (tiles)**, not bytes: `$40` = 64-wide plane,
  `$80` = 128-wide plane. (An earlier reading of stride-as-bytes made
  the title logo look like it wrapped past the plane edge; in words
  it fits: the title pieces span xoff 1–119 in a 128-wide plane.)
- Flip bits in the **base** (`0x0800` / `0x1000`) select reversed
  row/column traversal. Every observed call has them 0, and the
  flip-path arithmetic looks inconsistent (it adds the base value into
  the source index) — likely dead/generic code. Open question; it does
  not affect any decoded map.
- `$DC60` (called per row) sets the VDP write address; `$D9EE`
  writes each word. The plane is selected by `dest` (`$0000` plane B
  at R4=0, `$2000` plane A at R2=8) and its size by VDP R16
  (`$01` = 64x32, `$11` = 64x64, `$03` = 128x32).

## The loader chain (verified)

- `$1383C(index)` — loads one `$96120` record, returns its
  decompressed pointer in d0. Takes one word arg; the count/base
  pushes that appear before some `$1383C` calls belong to the
  following upload call, not to `$1383C`.
- `$11ABC(count, base, src)` — uploads `count` tiles from `src` to
  VRAM at `base`. (Count matches the record's tile count every time:
  438 for rec 6, 281 for rec 34, 55 for rec 21.)
- `$11A7C(src, count)` — uploads `count` tiles at the running cursor
  `$FF0076`, returns the old cursor.
- `$13654(dest, index, table, base)` — dispatcher: record type 0 →
  `$DE1A` plain copy, 1 → `$DD5C`, 5 → `$136FC` word expansion.
- `$11082(table_ptr, slot)` — loads one 16-word palette from the
  master table at ROM `0x0CC9D8` (31 palettes × 32 bytes) into CRAM
  slot 0–3. Palette index = `(table_ptr − 0x0CC9D8) / 32`: `$CCAD8`
  = pal 8, `$CCAF8` = 9, `$CCB18` = 10, `$CCB38` = 11, `$CCB98` = 14,
  `$CCBB8` = 15, `$CCBD8` = 16, `$CCBF8` = 17, `$CCD18` = 26,
  `$CCD38` = 27, `$CCD98` = 30, `$CCCF8` = 25.
- Pal 8 is all black: routines load it into all four slots first
  (blank the screen), draw, then load the real palettes.

## The tilemap records

Full table with ROM sources: `disasm/maps/inventory.md`. Summary:

| recs | dims | tileset | pal | what |
|------|------|---------|-----|------|
| 9 | 28x40 | 6 | 11 | world map of Ushka Bau |
| 35 | 28x40 | 34 | 30 | starfield map (alt. to rec 9) |
| 22–26 / 48–52 | 21x38 … 7x8 | 21 | 15 | title logo, layers 1 / 2 |
| 54 | 25x40 | 53 | 17 | archway location picture |
| 57 | 21x27 | 56 | 27 | castle location picture |
| 39 | 24x40 | 37 | ? (14 best-fit) | night landscape |
| 40 | 8x40 | 37 | ? | starfield strip above rec 39 |
| 13, 14, 15 | 8x40 | 12 | ? | ornate border strips |
| 43, 44 | 9x32, 7x8 | 42 | ? | small starfield/night maps |

## The world map (rec 9) — decoded and drawn (verified)

- 28 rows x 40 cols, 1120 words, indices 0–437 (all 438 tiles of
  rec 6 used), drawn at (yoff 0, xoff 0), dest `$0000`, stride `$40`
  (64-wide plane, R16 = `$01` = 64x32).
- Drawn by three routines: `0x12EA0` (in 0x12C20), `0x16360`, and
  `0x178FC` (in 0x17860). The 0x12C20 routine is reached from the
  intro/story flow (`0x15008`, `0x1552C`, `0x195C4`).
- Content: a **diamond landmass** on a sea, an ornate frame, and a
  **compass rose** (bottom-right, with the letter N). Two tiles do
  almost all the work: tile 18 (311 cells, solid pixel 12) is the sea,
  tile 131 (302 cells, solid pixel 0) is the land; the remaining 507
  cells are the frame, coastline detail and the compass.
- Palette: **pal 11** (code-pinned — both the 0x12C20 and 0x17860
  routines load `$CCB38` → slot 1, and the map's base is
  `+$2000` = palette slot 1). With pal 11 the land renders black and
  the sea blue-grey (`disasm/maps/world_map_rec09_pal11.png`).
  `world_map_rec09_pal13_fancolours.png` shows the same map with pal
  13 (green land, dark-blue sea) for comparison — pal 13 is *not*
  what the code loads; it is included because its colours match the
  fan world map's modern render.
- `world_map_rec09_index.png` (one pixel per tile, colour = hash of
  the tile index) shows the diamond shape independent of tiles or
  palette.

### Validation against the fan world map (verified)

`docs/research/rings-of-power-ru/RingsOfPower-World.png` (8076x4654,
the complete world of Ushka Bau) — **Dayset checked it himself on
2026-11-09 and says it is legit and perfect as it is. Treat it as
verified ground truth for this issue.**

What the decoded in-game map confirms against it:

- **Diamond orientation**: the fan map is a diamond (isometric,
  N pointing up-left); rec 9's landmass is the same diamond shape,
  spanning most of the 40x28 grid. ✓
- **Compass rose**: present in both (fan map top-left, in-game map
  bottom-right). ✓
- **Land/sea split**: rec 9 has exactly two bulk tiles — land
  interior vs sea surround — matching the fan map's single landmass
  in an ocean. ✓

What differs, and why it is not a contradiction:

- The in-game map is **schematic**: the land is one solid tile (no
  desert, ice, coastline detail or cities in the tilemap itself).
  The fan map is a modern full-colour render with terrain detail
  (pale-yellow desert lower-middle, white ice caps, brown/red city
  clusters). The in-game Map screen evidently overlays its detail
  another way — city markers / the player position are most likely
  sprites or objects (`$11AE4` loads a `$B86AE` sprite, rec 23, in
  the map routine; `$11C9A` places objects in related routines).
  Which sprites mark which cities is an open question.
- The fan map's colours (green land, blue sea) match pal 13, not the
  code-pinned pal 11 (black land, blue-grey sea). The fan map is a
  re-render with its own palette, not a screenshot of the in-game
  map screen — so the colour difference does not invalidate it as a
  layout reference, and the layout (diamond, compass, land/sea) is
  what was validated.

## The starfield map (rec 35) — decoded and drawn (verified)

- 28x40, 1120 words, indices 0–280 (all 281 tiles of rec 34 used),
  palette 30 (code-pinned: routine 0x17860 loads `$CCD98` → slot 2,
  base `+$4000`), loader `0x17954`.
- Routine 0x17860 draws **either** rec 9 or rec 35 depending on its
  arg (`tst.w $8(a6); bne $17908` — arg == 0 → rec 9 with tileset
  rec 6; arg != 0 → rec 35 with tileset rec 34; a `bra` after the
  rec-9 blit skips the rec-35 block). They are alternatives, not
  layers.
- Content (`disasm/maps/starfield_map_rec35_pal30.png`): a grey
  speckled diamond on a dark-red starfield with planets (blue, red,
  grey) and a bright-green bottom bar (the bar is solid pixel 0 of
  pal 30 — likely a text area, or a palette that gets swapped). Which
  screen this is (a second world? the Void? a space view?) is an open
  question. Note the tileset correction: an early read had rec 35
  paired with rec 12 (the shared `$FF8676` base variable); the
  count-push at `0x17908` (`#$119` = 281) and rec 35's max index 280
  prove the tileset is rec 34.

## The title logo (recs 22–26 / 48–52) — decoded and drawn (verified)

- Five pieces per layer, tileset rec 21 (55 letter-stroke tiles),
  palette 15 (slot 0 — base `+$8000`, priority bit, palette 0),
  dest `$2000`, stride `$80` words (128-wide plane), yoff 3 (10 for
  the small piece). Together they spell **RINGS OF POWER**:
  rec 22 = "RING" (38x21, rendered), rec 23 = "O", rec 24 = "F",
  rec 25 = "P", rec 26 = "OWER".
- The routine's arg selects the layer (arg == 0 → recs 22–26 at
  xoff 1/41/52/62/85; arg == 1 → recs 48–52 at xoff 1/39/52/55/76).
  They are alternatives — the `tst.w $8(a6)` / `cmpi.w #$1` branches
  skip the other layer — not overlays. Why two layers exist (and why
  the xoffsets differ, with recs 50/51 overlapping in columns 55–59)
  is an open question.
- The maps' u16 values are only 0–11 (+ flips): each piece is a
  letterform built from a dozen stroke tiles (visible in the
  text-grid dumps: repeating "456"/"78"/"9"/"A"/"B" strokes).

## Location pictures — decoded and drawn (verified)

- **Rec 54** (`archway_rec54_pal17.png`): 25x40, tileset rec 53
  (536 tiles, max index 535), palette 17 (code-pinned: routine loads
  `$CCBF8` → slot 2, base `+$4000`), drawn at (yoff 2, xoff 0),
  loader `0x18D6C`. A stone archway/trellis with vines, checkered
  floor and cyan star emblems. Its index grid is near-sequential
  (0,1,2,…) with tile 144 repeated 197x — a full-screen picture of
  mostly unique tiles.
- **Rec 57** (`castle_rec57_pal27.png`): 21x27, tileset rec 56
  (290 tiles, max index 289), palette 27 (code-pinned: `$CCD38` →
  slot 0, base `+$8000`), drawn at (yoff 43, xoff 4), loaders
  `0x18858` / `0x191A6`. A castle with teal roofs/towers.
- **Rec 39** (`landscape_rec39_pal14_bestfit.png`): 24x40, tileset
  rec 37 (586 tiles, max index 583), base `+$6000` = palette slot 3,
  drawn at yoff 40, loaders `0x18818` / `0x19166`. A night landscape:
  mountains, dark forest, snow field, starry sky. **Palette is
  best-fit, not code-pinned**: its routine loads pal 8 (blank) into
  slot 3 and never reloads it; pal 14 (loaded by the same routine
  into slot 2) renders it most coherently of the candidates tried
  (pal 10 = red forest, pal 25 = orange sunset, pal 26 = magenta
  snow). The display palette probably comes from the caller or from
  `$17586` — open question.
- **Rec 40**: 8x40 starfield strip, same tileset (rec 37), base
  `+$6000`, drawn with rec 39 at a variable yoff (presumably 32–39),
  loaders `0x187D8` / `0x19126`. Together rec 40 + rec 39 fill rows
  32–63 of a 64-row plane; what occupies rows 0–31 is an open
  question.

## Border strips and small maps (decoded, partially rendered)

- **Recs 13/14/15** (8x40 each, tileset rec 12, 374 tiles): ornate
  border strips for the text/story screens, drawn by the `$147D0`
  text-loader routine — rec 13 at (0,0), rec 14 as 7 stacked bands
  at yoff 8,16,…,56, rec 15 at a variable yoff. Rendered in scratch
  (pal 1 placeholder): rune-patterned frames around a solid field.
  Their display palettes are TBD.
- **Recs 43/44** (9x32 and 7x8, tileset rec 42, 40 tiles): small
  starfield/night-sky maps drawn at runtime-computed (d6,d7)
  positions in the 0x17B88 scene routine (which also loads Book of
  Buc rec 55 and calls `$11C9A` object placement). Rendered in
  scratch (pal 14 placeholder): dark blue with small stars.

## What is NOT map data (verified)

- **`0x0CC000–0x0D7FFF` is not a map table.** Sampled content:
  high-entropy block at `0x0CC000`; palette table `0x0CC9D8` (31
  palettes); menu strings ("MAIN", "Inven", "Spells", "Party",
  "Search"); "Load" at `0x0CD000`, "Sunder" at `0x0CE000`;
  small-number tables at `0x0CF000–0x0D6000`; dialogue text from
  `0x0D7000`.
- **Item-name table at `0x0CEB00`**: 17-byte records
  `[0x11][name, NUL-padded]` — "War Key", "Intu Key", "Sun Key",
  "Twst Key", "Crwn Key", "Skul Key", "Div Key", "Ship", "Boat",
  "Dino", "Dragon", "Gold", "Exper", "Heal", "Pow Up", "Life",
  "note", "tome", **"MM map"**, "scrap", "file", "book", "map",
  **"mapbit"**, "pic", "contrct", "pass", "ID", "log", "diary",
  "memo". "MM map" / "map" / "mapbit" are leads for the in-game Map
  screen and map-reveal mechanics, not map data themselves.
- A blind `$DD5C` scan of `0x040000–0x096000` produced 4808 hits —
  a false-positive flood (the decoder is too permissive); it is **not**
  evidence of additional streams. The only `jsr $DD5C` in the ROM is
  from `$13654`, so all `$DD5C` data goes through record tables.

## World coordinates (leads, from the walkthrough + dialogue)

The in-game coordinate system (from
`docs/research/rings-of-power-ru/txt/RingsofPower.txt` and the
dialogue blob) spans roughly 0–33 x 0–19, e.g. City of the Mind
11'9'' 11'4'', Kaos 10'6'' 8'0'', Cathedral 5'0'' 8'2'', City of
Speed 1'1'' 8'1'', Dragon Tower 30'3'' 11'9'', Magic B Us 24'3''
2'5''; dialogue coordinates reach 32'9'' 18'4'', and road signs give
distances in "klicks". This is a separate system from the 40x28
tilemap — the tilemap is a picture of the world, not the grid the
player walks on.

## The chunk tilemaps — `$43850` table (verified 2026-11-10)

Block 1 (`0x044000–0x05FFFF`) holds a second map system, distinct
from the `$96120` picture tilemaps: **252 chunk tilemaps** in a
`$DD5C` table at `$43850` (records decoded to `disasm/chunks/`,
tool `tools/decode_chunks.py`).

- **99 × 2048 B chunks (32×32 tiles)**: recs 0–76 and 230–251.
- **153 × 242 B chunks (11×11 tiles)**: recs 77–229.
- Chunk words are full VDP tilemap words (tile index + flip/palette/
  priority bits — all flag bits `0x0800`–`0x8000` seen in the data).
- Tile indices span 0–2027 (560 distinct), in fragmented ranges
  (dense 0–287, then 464–560ish, scattered to 2027); 1,468 indices
  in 0–2027 are unused. **No `$96120` tileset holds that many tiles**
  (largest rec 37 = 586), so no tileset/palette pairing is pinned
  for chunks yet — a full tile render is blocked on it.
- **Renders** (`disasm/maps/chunks/`, tool `tools/render_chunks.py`):
  all 252 chunks as INDEX images (one pixel per tile, colour = MD5
  hash of the tile index — the same method as the index grids here),
  plus `CHUNKS.md` inventory (distinct-tile counts, index ranges,
  most common tiles). The renders show coherent structure, not noise:
  e.g. chunk 0 has a large uniform region and distinct clusters; the
  dominant tiles recur across chunks (28, 29, 36, 86, 87, 47 are the
  bulk tiles). 32×32 and 11×11 chunks share 255 tile indices, with
  266 only in 32×32 and 39 only in 11×11 — same tileset space,
  different subsets (consistent with overworld/town vs room chunks,
  unproven).
- **Loader**: `$19692(index)` — a 4-slot round-robin cache
  (buffers at `$FF868C` + slot×2048; slot counter `$FFA894` & 3;
  pointer table `$FFA896`; slot→index table `$FFA884`). It calls
  `$13654` with table `$43850`, base `$44228`. `$1C802(index)`
  is the lazy getter (returns the cached chunk pointer, loading via
  `$19692` if null).
- **Chunk index from position**: `$1C83E` computes
  `(y / H) * W + (x / W)` using the geometry struct at `$FFA7FC`
  (`+4` = height divisor, `+6` = row width) plus base `$FF0E98`
  (+`$4D` if not `$FFFF`). `$1C7DA` computes the current chunk
  index from the player position (`$FF0E8E`/`$FF0E90`) into
  `$FF0E94`. So the chunk index is a function of position — the
  chunks ARE the walkable map, indexed by where the player stands.

## The walkable terrain grid (resolved 2026-11-10)

There is no ROM "terrain grid" table. The walkable terrain is a
runtime assembly of four ROM sources plus RAM grids:

| part | where | role |
|------|-------|------|
| chunk tilemaps | `$43850` table, 252 recs | the map itself (see above) |
| per-tile properties | `$5EDC4`, 512 words | per-tile data, indexed by tile & `$1FF` |
| terrain streams | `$5F524`, 176 u32 offsets, streams at `$603E4+` (last ends ~`$6823B`) | per-tile terrain detail, decoded by `$E358` |
| RAM cell grids | `$FFB36C`, `$FFB76C` (bytes per cell) + `$FFB0CC` (12-byte records) | runtime walkable state |

**`$5EDC4` (512 words, ROM `0x05EDC4`)**: indexed by tile index &
`$1FF` at 9 sites (e.g. `0x01BAAC`, `0x01BB82`). Value structure
(verified from the bit tests in `$1BA4E`): bits 13–15 are a count
(0–7) — the number of `$E358` terrain-decode rows for that tile;
bits 5–9 and 12 and the low byte are flags. Most common value is
`0x240B` (×177); 147 distinct values; low byte most often `0x0B`
(×177) or `0x01` (×101). Which flag bit means "walkable" is **not
yet pinned** — the bit fields the code actually tests are listed
above, the semantics are open.

**`$E358` threaded terrain decoder** (entry, 114 direct `jsr`
call sites in 15 caller functions — correcting the earlier "no direct
callers" note): args
are (d2 = stream index into `$5F524`, d0, d1, d3 = variant). It
selects one of the 176 terrain streams (`lea $5f524;
movea.l (a1,d4.w), a0; adda.l #$603e4, a0`), seeks by high nibble,
then d3==0 → `$E3B4` path (d0 − `$40`), d3!=0 → `$E412` path
(d0 − `$26`). Both set a1=`$435C0`, a2=`$436E0`, a3=`$433C0`,
a4=`$FF1EC0`, then a computed jump via the `$DF58` table
(longwords, high word 0) into handler routines; the `$E47C`
unrolled writer emits 4 bytes/group with a +`0x1D` skip → 33-byte
output rows (1bpp bitmap) into `$FF1EC0`.

**`$1BA4E` per-cell terrain driver** (`0x01BA4E–0x01BC56+`): for
each cell it calls `$1C176` to get the tile word, looks up
`$5EDC4[tile & $1FF]`, extracts bit fields, then loops calling
`$E358` per row (d3 = a value ≥ `$22F`, so always the `$E412`
path, or `#$230` = 560). After the decode it computes a cell
index from position via the `$FFA7FC` geometry struct and reads
two bytes: `$FFB36C[index]` and `$FFB76C[index]`. The `$FFB76C`
byte is a record key: if not `$FF`, it is ×12 and used to index
`$FFB0CC` (a 12-byte-record table), whose word at +`$A` is read.
So `$FFB36C`/`$FFB76C` are byte-per-cell RAM grids and `$FFB0CC`
is a per-cell record table — the runtime walkable-state grids.

**`$FF1EC0` is shared scratch, NOT a persistent grid** (settled):
9 references — the `$E3B4`/`$E412` decoder writes there
(`0x00E3C6`, `0x00E424`), `$1383C` (the `$96120` loader) and
`$11AE4` (the `$B86AE` sprite loader) also use it as decompression
scratch. `$11DE8` clears it (26,496 bytes, `0x19E0` longwords) and
is called from the `$1B958` scroll routine — it is re-cleared each
redraw. The `$E358` output bitmap is transient.

**Grid geometry is per-location, in RAM**: `$FFA7FC` is set once
(`0x01B74E`, in the map-load routine) to `$FFB08C` — a RAM struct
initialized by `$1DA10` calls with per-location values (fields
used: +0 width divisor, +2 height divisor, +4 chunk-height
divisor, +6 row width, +`$A` ×8). A second `$E358` caller,
`$231D8`, processes 36-byte records from the `$197B0` table
(mostly zeros with small values) and calls `$E358` with stream
index `#$209` (521) when a record's first word is `$1CC` (460).

Still open on the terrain grid: which `$5EDC4` flag bit means
walkable (needs a live check — e.g. a harness that steps onto a
cell and reads `$FFB36C`/`$FFB76C`); the byte meanings of
`$FFB36C`/`$FFB76C` and the `$FFB0CC` 12-byte record layout; the
`$197B0` 36-byte record layout; the chunk tileset/palette pairing
(blocks full tile renders of the chunks).

## Open questions (for #020 / #011 / #015)

1. **The walkable overworld / town / dungeon terrain grid — resolved
   as a runtime structure 2026-11-10 (see above).** Remaining open
   bits: which `$5EDC4` flag bit means walkable; the `$FFB36C` /
   `$FFB76C` byte meanings and the `$FFB0CC` 12-byte record layout;
   the `$197B0` 36-byte record layout; the chunk tileset/palette
   pairing (blocks full tile renders of the 252 chunks).
2. **Which screen is rec 35?** Starfield + grey diamond, selected by
   routine 0x17860's arg. Candidates: a second world, the Void, a
   space view. Needs a live check (drive the game to the map screen
   in BlastEm) or the caller's arg traced.
3. **Which screen is the 0x12C00 routine / rec 9's first draw?**
   Reached from the intro/story flow; likely the Map screen itself
   (Start → Map) or a story map interlude. Same live-check need.
4. **Title layer 2's purpose** (recs 48–52 vs 22–26) and the rec
   50/51 column overlap.
5. **Rec 39/40 scene's top half** (rows 0–31 of the 64-row plane)
   and rec 39's display palette (slot 3).
6. **Recs 13/14/15/40/43/44 display palettes** (rendered here only
   with placeholders).
7. **`$1194A` flip-path arithmetic** — the base flip bits select a
   traversal whose source-index math looks inconsistent; no observed
   call uses it, so it may be dead code, but it should be settled
   before anyone relies on flips.
8. **City markers on the world map**: which sprites/objects mark
   which cities, and how the player's position is shown.
