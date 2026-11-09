# #025 — World & overworld spec (Ushka Bau)

Status 2026-11-09: **spec written from #006 data**; implementation
waits on #023 (engine) + #024 (export). Sources: `docs/maps.md`,
`disasm/maps/inventory.md`, `docs/research/ringsofpower-co-uk-guides.md`
(locations.htm coordinates), `docs/research/rings-of-power-ru/` world map.

## What we build from (verified)

- **Schematic world map:** `$96120` rec 9, 28×40 tilemap, tileset
  rec 6 (438 tiles), palette 11 (code-pinned), loaders at
  `0x12EA0`/`0x16360`/`0x178FC`. Diamond landmass + ornate frame +
  compass rose. Dayset verified it matches the fan world map
  (`RingsOfPower-World.png`, 8076×4654) — diamond orientation,
  compass rose, land/sea split.
- **Cities:** the 20 city coordinates from locations.htm
  (degrees-minutes sextant format) place onto this map; the fan
  map and walkthrough coordinates are cross-checks, ROM data wins
  on conflict.
- **Scaled-map behaviour (must reproduce):** the player walks a
  small-scale map; the full-size map is revealed on demand
  (original: press B). Implement as two zoom states over one world
  model, not two worlds.

## The open grid — design around it honestly

The **walkable terrain grid is NOT in the `$96120` records** (#006,
carried by #020): the in-game map is schematic (solid land tile);
desert/ice/cities are overlaid objects/sprites in the original.
Current best lead: the threaded bitmap decoder `0xE3B4/0xE412`
output at `$FF1EC0` (33-byte rows), stream source unknown
(`docs/logic-audit.md` §5). Therefore:

- **Phase 1 (this issue's acceptance allows it):** terrain from
  rec 9's land/sea mask + fan-map terrain colours as a *labelled
  first approximation* — the approximation flag lives in the world
  data file header, not just in docs.
- **Phase 2 (swap-in):** when the real grid lands, rebuild terrain
  from it and note the swap in issue #025 (its acceptance demands
  exactly this note). Gavin hand-laid the map "one block at a
  time" over six months (Genesis Temple) — the grid exists.

## Terrain-type representation (decision the issue asks for)

Phase 1 represents terrain as a per-cell enum
{sea, land, desert, ice, city, special} derived from the fan map's
verified geography, because the original's tilemap carries none of
it. Movement/food-water costs key off this enum (#026), so the
Phase-2 grid swap changes data, not code.
Camera: expose `World::cameraHook()`; #028 owns both cameras.
