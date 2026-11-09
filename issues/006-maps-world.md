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

The **walkable overworld / town / dungeon terrain grid was not
located** — no `$96120` record is a terrain grid. Leads in
`docs/maps.md`: the threaded decoder at `0xE3B4`/`0xE412` + nibble
tables `$433C0–$436E0`, the `0x044000–0x05FFFF` block, the "MM map"
item. Also open: which screen rec 35 is, title layer 2's purpose,
rec 39's display palette + its scene's top half, city markers on the
world map, `$1194A` flip-path arithmetic.
