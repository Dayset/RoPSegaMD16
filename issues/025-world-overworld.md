# Issue #025 — World & overworld (Ushka Bau in 3D)

**Milestone:** M7
**Epic 5** (Tribute remake)
**Status:** open

## Goal
Recreate Ushka Bau as a walkable 3D world in the tribute: terrain,
cities at their real coordinates, and the world map the player
navigates by. Start from what is known; the walkable terrain grid
is still an open question from #006.

## Acceptance
- [ ] Terrain built from the decoded world map (rec 9, 28×40 tilemap)
  + the 20 city coordinates from `docs/research/ringsofpower-co-uk-guides.md`
  (locations.htm) placed on it
- [ ] Player can walk the overworld and reach cities (even if the
  underlying grid is a first approximation — label it as such)
- [ ] The scaled-map behaviour is reproduced: the small map the
  player walks, with the full-size map revealed (original: press B)
- [ ] When the #006 walkable-grid lead lands (threaded decoder
  0xE3B4/0xE412, 0x044000 block), the terrain is re-built from the
  real grid and the issue notes the swap

## Notes
- History that matters: Gavin spent "six months to lay out the map,
  one block at the time" (Genesis Temple article,
  `docs/research/genesis-temple-last-pure-game.md`) — the grid was
  hand-laid, so it exists somewhere; it is not in the `$96120`
  tilemap records.
- The in-game map is schematic (solid land tile); desert/ice/cities
  are overlaid objects/sprites in the original — the remake must
  decide how terrain types are represented (document the choice).
- Owns: `tribute/world/` (terrain, map data, city placement). Do
  not touch the camera modes (#028) — expose a camera hook for it.

## Depends on
#006 (done, with the open grid gap), #024 (asset pipeline) for map
data. Start now on the known map; grid-dependent parts wait for #006.

## Status
open
