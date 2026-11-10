# Maps — decoded tilemaps

Issue #006. Tool: `tools/decode_map.py` (see `docs/maps.md` for the
format). Regenerate any PNG with, e.g.:

    python3 tools/decode_map.py draw 9 --scale 3 --out disasm/maps/world_map_rec09_pal11.png
    python3 tools/decode_map.py draw 35 --scale 2 --out disasm/maps/starfield_map_rec35_pal30.png
    python3 tools/decode_map.py indexgrid 9 --out disasm/maps/world_map_rec09_index.png

## Rendered maps

- `world_map_rec09_pal11.png` — **the world map of Ushka Bau**
  (rec 9, 28x40, tileset rec 6, palette 11 — the palette both drawing
  routines load into the map's slot). A black diamond landmass on a
  blue-grey sea, ornate frame, compass rose bottom-right. The in-game
  map is schematic: the land is one solid tile, no desert/ice/cities
  in the tilemap itself. **Regenerated 2026-11-10** with the
  corrected CRAM order — the #005 render had R and B swapped.
- `world_map_rec09_pal13_fancolours.png` — the same map with palette
  13 (green land, dark-blue sea). **Not** what the code loads — shown
  for comparison because pal 13's colours match the fan world map's
  modern render.
- `world_map_rec09_index.png` — one pixel per tile, colour = hash of
  the tile index. Shows the diamond shape independent of tiles or
  palette: solid green interior (tile 131, 302 cells), solid brown
  surround (tile 18, 311 cells), speckled ornate border.
- `starfield_map_rec35_pal30.png` — rec 35, 28x40, tileset rec 34,
  palette 30. Grey diamond on a dark-red starfield with planets and a
  bright-green bottom bar. The alternative full-screen map in routine
  0x17860 (drawn when its arg != 0); which screen this is is TBD.
- `title_logo_rec22_pal15.png` — rec 22, 21x38, tileset rec 21,
  palette 15. The title logo's first piece: "RING" in giant
  letter-stroke tiles. The five pieces (recs 22–26) spell
  RINGS OF POWER; recs 48–52 are the alternate layer.
- `archway_rec54_pal17.png` — rec 54, 25x40, tileset rec 53,
  palette 17. Stone archway/trellis with vines, checkered floor, cyan
  star emblems — a location picture.
- `castle_rec57_pal27.png` — rec 57, 21x27, tileset rec 56,
  palette 27. Castle with teal roofs/towers — a location picture.
- `landscape_rec39_pal14_bestfit.png` — rec 39, 24x40, tileset
  rec 37, palette 14 (**best-fit, not code-pinned** — the map's
  palette slot 3 is not loaded by its routine; pal 14 is the most
  coherent of the candidates tried). Night landscape: mountains, dark
  forest, snow field, starry sky.

## Chunk renders — `chunks/`

The 252 decoded chunks from the `$43850` table (`disasm/chunks/`,
tool `tools/decode_chunks.py`) are rendered as INDEX images in
`chunks/` (tool `tools/render_chunks.py`):

    python3 tools/render_chunks.py

- `chunk_NNN.png` — one pixel per tile (scale 8), colour = MD5 hash
  of the tile index (same method as the index grids above). No
  tileset or palette is assumed — the chunk tileset/palette pairing
  is not pinned (tile indices span 0–2027; no `$96120` tileset holds
  that many tiles), so a full tile render is not possible yet.
  The renders show coherent structure (regions, not noise); the
  bulk tiles 28, 29, 36, 86, 87, 47 recur across chunks.
- `CHUNKS.md` — inventory: size (32×32 for recs 0–76, 230–251;
  11×11 for recs 77–229), distinct-tile counts, index ranges,
  most common tiles per chunk.

## Palette confidence

- **Code-pinned** (the drawing routine loads this palette into the
  map's slot): rec 9 → pal 11, rec 35 → pal 30, rec 54 → pal 17,
  rec 57 → pal 27, title recs 22–26/48–52 → pal 15.
- **Best-fit** (renders coherently; the routine does not pin it):
  rec 39 → pal 14.
- **Unknown**: recs 13/14/15/40/43/44 (rendered in scratch with pal 1
  / pal 14 as placeholders; not shipped here).
