# Route to Mind — solved statically (session #10)

The east band is walled at ground level; the only foot route from
spawn to the east-coast town cluster (presumed Mind, $D1D00 point
cluster at (162–178, 105–117)) is a long **southern loop**: west
around the lake, south down the west side, east along the deep-south
corridor, then north up the x≈120 and x≈155/x≈164 corridors into the
town. Computed with `tools/passability.py` over the passability grid
derived from FUN_0001C892 (see `docs/logic-audit.md` session #10 for
the step/terrain model and its validation).

## The route (335 steps, BFS-minimal; spawn → (171,110))

Waypoints (close-view tile coordinates, x east / y south):

```
(109,130) spawn
→ (109,124) → (104,123) → (96,121) → (88,123) → (83,127) → (77,128)
→ (76,135) → (72,144) → (65,153) → (65,158) → (71,160) → (74,165)
→ (76,172) → (82,172) → (89,175) → (89,179) → (97,180) → (99,187)
→ (106,192) → (113,187) → (117,190) → (120,188)
→ north up x=120 to (120,178)
→ (124,176) → (129,176) → (140,175) → (142,178) → (142,170)
→ (141,167) → (153,167) → (154,163) → (155,163)
→ north up x=155 to (155,143)
→ (158,140) → (164,140)
→ north up x=164 to (164,119)
→ (169,119) → (169,116) → (172,116) → (171,114) → (171,110)  town point cluster
```

Terrain notes:

- The direct east band (y ≈ 100–140) is solid from x ≈ 128: ridge
  classes 4/8/33 and height deltas ≥ 4 — this is the wall that
  stopped sessions #8/#9. It is a *band*, not a line: no crossing
  exists anywhere in y 100–140.
- The pond-village enclave (113–127, 105–125, ~20 $D1D00 points) has
  **no east exit**: its east edge (x ≈ 126–127) is blocked classes,
  and beyond it the band above. Micro-route (a) of §14.3 is closed
  by the grid.
- The lake's east end (x 114–128, y 126–146) is sealed: a class-17
  forest band whose pockets are isolated by class 4/33/8/16 cells.
  Micro-route (b) of §14.3 is closed by the grid; the loop passes
  around the lake's **west and south** instead.
- Audited steps in the x 118–152 crossing band: all destination
  classes 5/6/9/10/11 with |height delta| ≤ 2. Class-11 tile at
  (120,187) is entered going north (dx=0 ✓); class-10 tiles at
  (126,176), (139,175), (141,178) going E/W (dy=0 ✓) — the
  direction-gated classes are used legally.
- Provisioning: step costs are mode-1 defaults (food 3 / water 1),
  class 9 road = (1,1), class 19 = (6,7), plus slope delta/2 food.
  The 335-step route costs on the order of 900–1,100 food. The
  970-gold save's ~1,472 food (before camps) makes the clean run
  feasible but tight; walk roads (class 9) where the corridor
  offers them.

## Fallback: teleport landing connects (grant-assisted)

The pad-2 teleport landing (171,125) is a class-1 water tile — the
party is *placed* there by the teleport's direct position write —
but its neighbours connect to the same reachable component as spawn
(9,069 cells from the landing vs 9,068 from spawn). From the
landing it is **13 steps to (164,119)** and **21 steps to
(171,110)**, walking west then north along the town's south edge.
A scratch-grant teleport + this short walk is a legitimate fallback
for reaching Mind, and must be labelled grant-assisted, distinct
from the clean 335-step run.

## Validation anchors

- Spawn (109,130): tile 8199, prop $1901, class 6, H 3 — grassland,
  walkable ✓ (every session starts here).
- Pond-village entry (109,124): tile $8080, class 9 (road) ✓.
- Overworld descriptor confirmed live in session #10: $FFB08C =
  W 352, H 224, chunk 32, 11 chunks/row; $FF0E98 = $FFFF (base-0
  record set = archive records 0–76) ✓ matches the grid assembly.
- The walled enclave and the sealed lake east end match session
  #9's live probes (ridge and inlet impassable; §14.3).
