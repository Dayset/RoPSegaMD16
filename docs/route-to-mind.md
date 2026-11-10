# Route to Mind — solved statically (session #10)

**Correction (session #10, live):** the town at the end of the
southern loop below is a *different* east-coast city, not Mind.
Mind is the town immediately NE of spawn (§11.1), and it was
**reached live by a clean 21-step route** — see "Driven route"
at the end of this file. The loop analysis stands as the solved
route to the east-coast cluster.

The east band is walled at ground level; the only foot route from
spawn to the east-coast town cluster ($D1D00 point
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

## Driven route — spawn → Mind, CLEAN (session #10, live, item 1 DONE)

Mind's south gate is the class-30 tile **(118,121)**. BFS from
spawn (tools/passability.py model, class 30 admitted as a goal
tile) = **21 steps**, driven tile-exact with 400 ms holds
(1 hold = 1 step; position verified by debugger reads after
every leg):

```
(109,130) spawn
→ N×5 (109,125)          road north; passes the south tax post's
                         tiles WITHOUT firing it (overworld
                         pass-through does not trigger the event)
→ E×2, N×1, E×3 (114,124)  bank an in-game SAVE here (outside;
                         restores at the road with COMBAT kept)
→ N×1, E×6 (120,123)
→ N×2 (120,121)
→ W×1, N×1, W×2 (118,120) (119,120) is class 10 (E/W-only),
                         entered going west ✓; (119,121) and
                         (119,122) are class 2 — the direct row
                         south of the gate is walled
→ S×1 onto (118,121)     GATE: garden location loads ($FF0E98=$10)
```

From the gate's garden, the city district lies through the
garden's NW exit; the Academy of Sorcery is the large complex
SE of the fountain plaza (doorstep banner: "WELCOME TO THE CITY
OF THE MIND, HOME OF THE WORLD FAMOUS ACADEMY OF SORCERY.").
Arrival state on the clean run: **gold 970 intact** (no tax),
after camps to dawn at spawn (HP 15→20, Food 1472→1272).

Hazards and traps (logic-audit §23.4 has the full record):

- A **gate Wyvern** guards the doorstep approach (killed Buc
  from HP 10); knight pairs patrol the city at night; roaming
  parties attack even an idle party inside the city.
- **Never SAVE on the south post's tiles** (e.g. (109,125)):
  the restore lands inside the tax demand and every YES
  re-charges 150 (observed 970→820→670). The (114,124) save
  above is the safe bank (rop9live/save-114124.eeprom).
- The north gate (117,110) is also class 30 and reachable —
  (116,120) → N×4, E×1, N×6 — but a second tax post
  (~(117,114), $FF0E98=$1B) fires on that approach; a third
  post hides in a building south of the Academy courtyard
  ($FF0E98=$1E). Driven into (not restored into), a post
  charges once: pay, exit with C, step away.
