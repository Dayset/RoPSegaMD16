# #028 — Cameras: classic vs modern (design)

Status 2026-11-09: **design complete**; prototypes wait on
#023 + #025 (the issue's own dependencies).

## Classic mode — faithful, not textbook-isometric

The original overworld is a **top-down scaled map the player
walks**, with the full-size map revealed on demand (B button) —
`docs/maps.md` / #025. So "classic" = an orthographic camera
locked over the walking-scale map at the original's fixed
presentation angle, tile-based look from the #024 exported assets,
original pacing (movement tied to the step counter rhythm,
`$FF0E16` mod 2400 world tick). A true isometric projection is
explicitly NOT the goal; if a slight diamond tilt is used to echo
the world map's diamond frame (rec 9), it is a TRIBUTE flourish
and must be toggleable back to flat top-down. The B-button map
reveal is part of classic presentation (shared with #025).

## Modern mode — decision (the issue asks us to decide)

**Orbit/zoom free camera** (right-drag orbit, wheel zoom, WASD/
edge pan) over the same terrain — chosen over first-person/WASD-
mouse-look because the game is party/party-position based, and
orbit keeps the party and nearby cities framed like the original's
map readability. Same game state, same logic tick; only the camera
rig and rendering style (lit 3D terrain vs flat tiles) change.

## The switch

Runtime toggle (key + menu), **no world reload, no state loss**:
both rigs read the same `World` model through #025's camera hook;
the switch swaps the active rig and render style only. Game state
(party position, step counter, flags) is camera-independent by
construction — enforced by keeping all state in `tribute/logic/`,
none in `tribute/presentation/`.

## Performance acceptance — how it will be measured

Record machine + measured FPS for both modes in issue #028 on the
dev machine once #023 builds (acceptance item 4). Target: stable
60 FPS for classic (2D-bound), stable ≥30 for modern on the same
machine. **Not measurable in this VM** (no engine) — the numbers
are owed, not estimated here.
