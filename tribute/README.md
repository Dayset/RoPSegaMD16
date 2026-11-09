# tribute/ — Rings of Power tribute remake (Esenthel/Titan)

Skeleton created 2026-11-09 (agent session) for issue #023.
Design: `docs/tribute-remake.md`; per-issue specs: `docs/tribute/`.

- Engine: Esenthel Engine (Titan), C++, by Grzegorz Slazinski.
  Source: https://github.com/Esenthel/EsenthelEngine — cloned as a
  sibling checkout, **never committed to this repo**.
- Engine commit: <fill on clone — see docs/tribute/023-engine-setup.md>
- Licence file: <path inside the engine clone — read before shipping>
- This project is based on Esenthel Engine (licence requirement).

## Layout (each subdirectory is owned by one issue)

| Dir | Owner issue | Contents |
|---|---|---|
| `assets/` | #024 | Exported by `tools/extract_assets.py` from your own ROM dump; not committed if derived from the ROM |
| `world/` | #025 | Terrain, map data, city placement |
| `logic/` | #026 | Stats, XP, gold, shops (all game state lives here) |
| `combat/` | #027 | Classic + new combat and the switch |
| `presentation/` | #028 | Classic/modern cameras and render styles |
| `ui/` | #029 | Verbs, dialogue, menus, HUD |
| `audio/` | #030 | Music/SFX, Quiet flag |
| `save/` | #031 | Versioned JSON saves |

## Build (once #023's engine steps are done on this machine)

1. Clone the engine (see `docs/tribute/023-engine-setup.md`).
2. `python3 ../tools/extract_assets.py` (needs `../rop-original.gen`).
3. Open this project in the Esenthel Editor; build for Windows/Linux.

Status: **skeleton only** — no engine project files yet; the first
build (window + one textured quad) is #023's remaining acceptance.

## Asset pipeline — RUN 2026-11-09 (issue #024)

`python3 tools/extract_assets.py` (system python3; needs PIL)
ran end-to-end against the verified ROM. All exporters are
implemented as wrappers over the repo's proven decoders
(render_tiles / decode_map / extract_text). Outputs
(git-ignored, regenerable; see `tribute/assets/manifest.json`
for per-file provenance):

| Output | Count | Verification |
|---|---|---|
| `assets/palettes.json` | 31 × 16 RGB | table shape checked |
| `assets/tiles/tileset_recNN.png` | 37 tilesets, 7,149 tiles (packed decode, palette 1, scale 2) | classes from the #005 inventory; maps/text records excluded |
| `assets/sprites/sprite_recNN.png` | 90, all exactly 48×48, embedded palettes | rec 0 pixel-matches the committed #005 portrait render |
| `assets/maps/map_recNN.json` | 21 maps, {tile, flipH, flipV} entries + tileset/palette/loader from the $1194A call sites | every map rectangular (entries == rows×cols); no map word carries bits beyond tile/flips (max word 0x19DC), so the split is lossless; paired layers tagged `layer_alt` |
| `assets/text/dialogue.json` | 1,183 records (1183 malformed excluded; 1181/1182 expand to the literal `"<NA>"`) | record 0 = "unknown building." — the shipped dropped-"An" bug, exported verbatim per the spec's paradox rule |
| `assets/text/books.json` | 4 streams (Nexus, Buc, credits, bestiary) | Book of Nexus opening matches the in-game intro text |
| `assets/text/dictionary.json` | 3,466 words | count = $136FC table size |

**What the Esenthel import step (owner machine, #023) still
needs:** the engine-side loader for these formats (PNG
tilesets/sprites are direct textures; maps/dialogue JSON
need a small importer into Esenthel's data model), the
engine project itself (no engine files exist yet — #023's
first-build acceptance is open), and per-screen palette
assignment for tilesets beyond the export default (palette 1;
the map JSONs already carry their call-site palettes where
known). The $E358 map-bitmap streams (issue #017) are a
separate data family (terrain/MM-map bitmaps) and are NOT
part of this export contract; tools/decode_e358.py covers
them if #025 wants the bitmaps.
