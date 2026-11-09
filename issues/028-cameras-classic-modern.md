# Issue #028 — Presentation: classic isometric vs modern 3D camera

**Milestone:** M7
**Epic 5** (Tribute remake)
**Status:** open

## Goal
Two presentations of the same world and logic, switchable at
runtime: **classic** (isometric view, original pacing and feel) and
**modern** (free 3D camera). Same terrain, same game state — only
the camera and rendering style change.

## Acceptance
- [ ] Classic mode: isometric camera over the #025 world, with the
  original's presentation feel (fixed angle, tile-based look from
  the exported assets)
- [ ] Modern mode: free 3D camera (orbit/zoom, or WASD + mouse —
  decide in the issue and document it)
- [ ] A runtime switch toggles classic/modern without reloading the
  world or losing game state
- [ ] Both modes run at a stable frame rate on the dev machine
  (record the machine and the measured rate in the issue)

## Notes
- The original is not isometric in the strict sense — its overworld
  is a top-down scaled map the player walks, with the full-size map
  revealed on demand. "Classic" means faithful to that feel, not a
  textbook isometric projection; document the camera choice.
- Owns: `tribute/presentation/` (cameras, render modes, the switch).
  Uses the camera hook from #025; do not edit world generation.
- New 3D art (if any) is a later decision — start with the faithful
  exported assets from #024.

## Depends on
#025 (world), #023 (engine skeleton), #024 (assets). Camera
prototypes can start as soon as #023 lands.

## Status
open
