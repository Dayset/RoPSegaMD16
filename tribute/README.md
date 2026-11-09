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
