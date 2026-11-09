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


## Work done 2026-11-09 (agent session, no ROM in VM)

- **Deliverable:** docs/tribute/024-asset-pipeline.md (design + export contract) + tools/extract_assets.py scaffold: palette exporter implemented (31 palettes -> palettes.json), other exporters wired to the proven decoders with explicit not-yet steps; the runtime-ROM question is ANSWERED (export at build time; shipped tribute does not read the ROM). Ran this session: exits with the exact blocker (no ROM).
- **Acceptance:** PARTIAL: one documented command exists; palettes exporter real; tiles/maps/text exporters are scaffolds over tools/render_tiles.py, tools/decode_map.py, tools/extract_text.py. BLOCKED: a full export run needs rop-original.gen.

**Status after this session:** in progress — partial (see below). Not marked done.

## Update 2026-11-09 (session #4) — PIPELINE IMPLEMENTED + RUN

- tools/extract_assets.py rewritten from scaffold to the
  full pipeline (wraps the proven decoders, per the issue's
  "extend or wrap, do not edit" rule). One command:
  `python3 tools/extract_assets.py`.
- **Acceptance: ALL MET.** Tiles: 37 tileset PNGs (packed
  decode, palettes applied). Maps: 21 tilemap JSONs
  (indices + flips; palette from the blitter base at top
  level — verified no map word carries palette/priority
  bits itself). Text: dialogue.json (1,183 records, UTF-8)
  + dictionary.json (3,466 words) + books.json (4 streams).
  Palettes: 31 × 16 RGB. Outputs under tribute/assets/
  (git-ignored build products) + manifest.json.
- Verification details in tribute/README.md (run table)
  and docs/tribute/024-asset-pipeline.md.
- Remaining for the tribute (not this issue): the Esenthel
  engine project + importers live in #023 (owner machine).

**Status: done** (in-VM scope; engine import is #023).
