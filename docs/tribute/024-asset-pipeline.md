# #024 — Asset pipeline design (ROM → engine assets)

Status 2026-11-09: **design complete + exporter scaffold shipped**
(`tools/extract_assets.py`); full export blocked on the ROM.
Sources: #004/#005/#006 results (`disasm/text/`, `disasm/graphics/`,
`disasm/maps/`, `docs/maps.md`).

## Runtime-ROM question — ANSWERED (issue asks to confirm)

**The shipped tribute does NOT read the ROM at runtime.** Export
runs at build time from the user's own dump via one command:
`python3 tools/extract_assets.py`. Rationale: the tribute is a
new executable, not an emulator; baking exported assets keeps the
ROM (which we never distribute) out of the shipped artefact, and
matches `docs/tribute-remake.md`'s default.

## Export contract — `tribute/assets/`

| Asset | Source (proven) | Format | Exporter |
|---|---|---|---|
| Tilesets | `$96120` records (tiles class), `$DD5C`-decompressed, **packed 2px/byte** decode | PNG, palette applied | wrap `tools/render_tiles.py` |
| Sprites/portraits | `$B86AE` 90 records `[32B palette][36 tiles]` | PNG 48×48, embedded palette | wrap `render_tiles.py sprite` |
| Maps | 21 `$96120` tilemap records | JSON: rows, cols, u16 entries split into {tile, flipH (0x0800), flipV (0x1000), palette/priority from blitter base} | wrap `tools/decode_map.py` |
| Text | `$DDBD8` 1,184 records + dictionary (`$136FC`, 3,466 words, blob `0x0D6EBA–0x0DC0C0`, table `0x0DC0C2`) + 4 `$DD5C` text streams | `dialogue.json` UTF-8 + `books.json` for the streams | wrap `tools/extract_text.py` |
| Palettes | master table `0x0CC9D8`, 31×16, 9-bit BGR `0BBB0GGG0RRR0` | `palettes.json` RGB triples | **implemented** in `extract_assets.py` |

## The paradox rule (from #005, binding on this pipeline)

Decompressed tiles are packed, yet the VDP path shows no
packed→planar conversion. **The exporter reproduces what the game
displays** — i.e. the packed decode that renders coherent faces/
fonts — not the textbook planar format. If #015/#016 ever resolves
the paradox, the exporter changes in exactly one place
(`decode_tile_packed`) and this doc gets a correction note.

## Known data caveats to carry into the export

- Record-0 dialogue drops "An" (likely original bug, #004) — export
  records verbatim; the tribute UI (#029) decides display.
- `$96120` rec 61 (bestiary text) is a text stream hiding in the
  graphics table — route it to `books.json`, not tiles.
- Tilemap paired records (22/48 etc.) are alternative layers, not
  overlays (`docs/maps.md`) — export both, tag `layer_alt`.
