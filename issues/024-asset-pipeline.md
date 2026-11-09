# Issue #024 — Asset extraction pipeline (ROM → engine-ready assets)

**Milestone:** M7
**Epic 5** (Tribute remake)
**Status:** open

## Goal
Build the exporters that turn the decoded ROM data into assets the
Esenthel project can load: tiles, palettes, maps, sprites, text.
The pipeline runs at build time from the user's own ROM dump — the
shipped tribute does not read the ROM at runtime (confirm this in
the issue; if it changes, say why).

## Acceptance
- [ ] Tiles: `tools/render_tiles.py` output (packed 2px/byte, 9-bit
  BGR palettes) exported as engine-loadable images (e.g. PNG) with
  palettes applied
- [ ] Maps: the 21 decoded `$96120` tilemaps exported as engine
  map data (tile indices + flips + palette/priority bits)
- [ ] Text: the 1,184 `$DDBD8` dialogue records + dictionary
  (`$136FC`, 3,466 words) exported as engine text data (UTF-8)
- [ ] Palettes: the 31 master palettes (ROM `0x0CC9D8`) exported
- [ ] One documented command (script) that runs the whole export
  from `rop-original.gen` and lands files under `tribute/assets/`

## Notes
- Builds on #004 (text/dictionary/LZSS), #005 (packed tiles,
  `$DD5C`, palettes), #006 (tilemaps, blitter `$1194A`).
  Read `docs/research/` and `disasm/graphics/`, `disasm/maps/`.
- Open paradox from #005: decompressed tiles are PACKED, yet the
  VDP path shows no packed→planar conversion — the exporter must
  reproduce what the game displays, not what the textbook VDP
  format says. If the paradox resolves (#015/#016), update the
  exporter and say so in the issue.
- Owns: `tools/export_*` (new exporter scripts) and the export
  output contract (`tribute/assets/` layout). Do not edit the #004–
  #006 decoders themselves — extend them or wrap them.

## Depends on
#004, #005, #006 (done). #015/#016 if the tile paradox resolves.
Start now.

## Status
open
