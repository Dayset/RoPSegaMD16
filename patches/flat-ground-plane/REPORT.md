# Flat ground plane — investigation + build report

Date: 2026-11-12 (evening, ~18:18–00:30 EST)
Worktree: `~/workspace/rop-work/flat-world/`
Report: `.scratch-flat-zoomed/REPORT.md`
ROM: `~/workspace/rop-work/flat-world/rop-flat-ground-plane.rom`
Patch: `patches/flat-ground-plane/` (source.s, build.py, README.md,
changed-bytes.txt, flat-ground-plane.ips)

Dayset's build order (2026-11-12 ~18:22 EST): "Make one flat ground
plane and show me the speed difference" — he sees it with his eyes, then
subcell, then dithering on top, one fix at a time.

## Headline result

| ROM | overworld cadence (frames/render) |
|---|---|
| original | **22.5** |
| flat ground plane (this ROM, 3x2 fill) | **8.44** |

**Speedup 2.67x.** The overworld is one solid flat green plane (blue
water patches), the figure stands on it, the room is untouched
(textured). A small black gap remains at the diamond's bottom edge
(§6). Dayset is the tester.

---

## 1. The zoomed view — distinguishing condition

### How B works

Pad byte `$FF0018`: A = bit 6 ($40), B = bit 4 ($10), C = bit 5 ($20),
START = bit 7. In `menu_verb_input` ($01333A), with no menu open
(`$FF0110 == 0`), B alone sets **verb $1E (30)** when `$FF00AE == 1`
(verb $23 (35) when mode == 2; verb $15 (21) when a menu is open).
Command switch `$00D740`: verb 30 → `$00D612` →
`sys_struct52_flag_test(leader, direction)` ($0265BE). B alone
(direction == 4) with d6 != 0 and d7 == 0/2 takes the mode-1 `$026846`
branch (enter a location via `$D1D00`); B+D-pad (direction != 4) or
d6 == 0 goes to `$026876` (which can recurse with direction = 4 or take
the mode-1 `$02692A` transition); the mode-0 transition (`$026ADA`) is
in the `$02693A` region (d7 dispatch).

### The zoomed view's state

`world_location_transition` mode 0 ($01DD6C): `tst.w $8(a6)` (mode == 0)
→ releases chars by type (1,4,5), sets **grid = `$FFB08C`**
($01DE02/$01DE08), location **`$FF0E98 = $FFFF`** ($01DE44), leader
placed at the staged coords (`$FF0E9A`/`$FF0E9C`, read at
$01DE4C/$01DE52), and **`move.w #1, $FF00AE`** ($01DE6A — mode = 1).

So the **zoomed view is: `$FF00AE == 1` AND `$FFA7FC == $FFB08C` AND
`$FF0E98 == $FFFF`**. The normal world view is `$FF00AE == 1`,
`$FFA7FC == $FFB08C`, `$FF0E98 == <location number>`. **The ONLY
distinguishing state is `$FF0E98 == $FFFF`.** Mode-1 (enter) sets grid
`$FFB09C`/`$FFB0AC` (room, by (loc+0x4D) >= 0xE6) + mode = 2; the mode-2
path ($01DF08) sets grid = `$FFB0BC`.

### The flat-world contradiction (UNRESOLVED)

The flat-world gate (mode == 1 AND grid == `$FFB08C`) does NOT check
`$FF0E98`, so it should have flattened the zoomed view too — but Dayset
reports "World Zoomed is unchanged - default". Possible explanations:

- (a) the branch mapping for the zoom is wrong somewhere (mode-0 may be
  a different path, e.g. the cutscene stage-1 reposition, not the B-zoom);
- (b) the zoomed view re-renders through a path that bypasses the hook
  (ruled out for terrain — `map_chunk_pos` is the only terrain renderer,
  3 call sites, and the hook fires on return addr + mode + grid);
- (c) Dayset's "World Zoomed" is a different screen than the B-button
  zoom — e.g. the world MAP screen, B+START, drawn by `world_map_draw`
  `$012C20`, which uses **no `$E358`** (0 call sites in `$012Cxx`), so
  the flat-world hook cannot affect it.

### Build decision

Gate the flat ground plane on **grid `$FFA7FC == $FFB08C`** (overworld
grid, any mode) — this covers the normal world view AND the zoomed view
if it keeps the overworld grid, and excludes interiors (room grids
`$FFB09C`/`$FFB0AC`/`$FFB0BC`). The built patch gates on mode == 1 AND
grid == `$FFB08C` (both checks, matching the flat-world gate). If Dayset
reports the zoomed view is still unflattened after this ROM, that
falsifies the hypothesis and points to (c) or a hook subtlety.

`redraw_check` ($01B918) callers: main_loop `$00D2B8` and `$00D9CE`. It
calls `map_chunk_pos` ($01B96A) when `$FF0098 != 0` (after
`clear_decode_buffer` $01B958, pushing cam Y `$FF0E90` / cam X
`$FF0E8E`).

Grid struct init (`table_init_b` $01DA14): grid+0=arg2, +2=arg3,
+4=arg4, +6=arg2/arg4, **+8=arg5**, +$A=0, +$C=arg6, +$E=$230. Boot
inits: `$FFB08C` (overworld) args (352, 224, 32, 1, 1) → **grid+8=1**;
`$FFB09C` (11,11,11,1,0) → **grid+8=1**; `$FFB0AC` (32,32,32,1,0) →
**grid+8=1**; `$FFB0BC` (11,11,11,4,0) → **grid+8=4**.

---

## 2. Speed — why the dispatch-hook flat is the same speed, and the fill

### The dispatch hook keeps $E358, so it keeps the cost

The flat-world patch's flat handlers (gen_flatworld.py) replace
`move.b (a0)+,d5` with `addq.l #1,a0` and omit the remap, but **copy the
AND/OR + writes verbatim** — they still paint, just with the flat byte
instead of the pixel byte. So the dispatch-hook flat does essentially
the same work as the original: the stream walk + position computation +
handler paint all still run. The saving comes only from **NOT calling
`$E358` at all**. `$E358` is ~15,300 cycles/call; a block fill is
~100 cycles (8 longword writes).

### Are the fill positions tile-derivable? NO — but the block fill doesn't need them

`$E358` low-nibble / position analysis (via `tools/sim_terrain.py`):
every stream has 22 dispatches. The dispatch-byte low-nibble sequences
are **d0-independent for ALL 944 streams** (both path A and path B —
tested d0 in (0,2,4,6), 0/944 differ). There are **599 distinct
low-nibble sequences** (most common: 86 streams
`[1,1,1,1,1,1,1,6,5,4,3,2,1,0,0,0,1,2,3,4,5,6]`; 35 streams
`[6,5,4,3,2,1,0,0,0,0,0,0,0,0,0,0,1,2,3,4,5,6]`; 31 streams
all-zeros (30 entries); 15 streams empty). The last 6 entries are
ALWAYS `[1,2,3,4,5,6]`; the first 7 are a per-stream constant; then a
descending run, then 0s. So the fill positions are **stream data, NOT a
simple function of the tile index** — a precomputed low-nibble table
would be ~10.4 KB (944x22 nibbles) or ~7.5 KB with distinct-sequence
compression (599x11 B + 944-B index), and the handler paint extents
(hsize per dispatch) would roughly double it — it does not fit cleanly
in the 12,084 B free padding alongside the blob. **BUT the block-fill
approach does not need the low nibbles at all** (see §3).

### The block fill and the checkerboard (found live, fixed)

The tile's 32-byte block start is
`$FF1EC0 + (Y//8)*1152 + ((X-64)//8)*32` (row[Y] = (Y//8)*1152 +
(Y%8)*4; col word index (X-64)/2 → tile column (X-64)//8). The first
build (1-block fill) produced a **sparse checkerboard**: only ~34% of
the diamond green (pixel count on the screenshot: green 11.1% of the
play-area crop). Debug counters (added to the stub, §7) proved the fill
ran for every call (7600 gated calls, 0 bounds skips, 7600 fills) — so
the blocks were being written, but to the wrong tiles.

Root cause: the isometric X step is **14 px = 1.75 tiles**, so the
central tile column of the window cells takes only **EVEN values
(0,2,4,...,32)** — the odd columns are never any cell's central tile.
A 1-block fill leaves the odd columns black. A **2-wide fill**
(tc..tc+1) bridges the column gaps; a **3-wide x 2-tall fill**
(tc..tc+2, tr..tr+1) also covers the diamond's bottom-right tip
(scatter-only edge tiles). Final fill: 6 blocks x 8 longwords per top
call, ~0.3 frames vs `$E358`'s ~12. Overlap at land/water borders
resolves by processing order (last cell wins) — at most a 1-2 tile
boundary wobble.

Measured green fraction of the play-area crop: 1-block 11.1% → 3x2
**41.8%** (the crop includes the pink border and the black outside the
diamond, so the diamond interior is essentially solid; see §6 for the
remaining edge gap).

### Figure draw order

Figures are drawn per-cell, interleaved — hero_track calls at $01BD98
and $01BF14 sit INSIDE the `map_chunk_pos` d4/d5 loop, after the
terrain calls ($01BC84) and before the d5 increment ($01C0C2). A figure
in cell (r,c) is drawn after that cell's terrain. Figures extend upward
(into blocks of cells processed earlier) and their feet are in their own
block (drawn after its fill), so a block fill should NOT make figures
invisible; the main residual risk is the figure's right edge extending
into a later-processed cell's block. The v1 block fill did NOT make
Thalmus invisible (flat_room3.png) — evidence the block fill is
figure-safe in practice. Dayset is the visual check.

---

## 3. Single flat ground — height is the cause

### The mechanism (confirmed by code + census)

The flat fill only removes the texture (colour); the height stacks
(face/hidden levels) are still rendered by the dispatch-hook flat (it
tail-calls `$E358`, which draws face/hidden sides), so the ground is
still stepped/terraced. **Flat zones are the naturally height-0 /
uniform-height zones; stepped zones are the ones with height stacks.**

### Fix shape (built)

Skip the face ($01BC1A) and hidden ($01BC3C) `$E358` calls when gated
(stub returns immediately, no `$E358` — the height-stack sides are not
drawn). Draw ONLY the top ($01BC84), at the **BASE Y** (`-$C(a6)`, from
`$FFAF42` — NOT the height-adjusted Y = `-$C(a6) − height*7`). All
ground cells at one level → a single geometric plane.

### Figure consequence (resolved in code)

`hero_track` ($0231D8) receives the height offset as an arg — the call
sites ($01BD98/$01BF14 and the `map_promote_record` $01BDE4/$01C006,
`map_tile_at_offset` $01BE30/$01C052, `map_animated_tile` $01BE7A/$01C09C
sites) compute d0 = -(height*7 + bit adjustments) from the cell word
(rol #3, and #7, mulu #7, neg) and push it as the first arg; hero_track
uses it as $10(a6) in its `$E358` calls ($023218–$023230: X =
template+6 + baseY + heightOffset). **So if the ground is flattened
but figures keep the height offset, figures FLOAT above the flat ground
by height*7 px (up to 49 px for height 7).** Height distribution across
119,889 chunk cells (decoded via tools/dd5c + lzss_check): h=0: 92,530
(77.2%), h=1: 12,820 (10.7%) → 7 px float, h=2: 6,883 (5.7%) → 14 px,
h=3: 3,821 (3.2%) → 21 px, h=4: 2,136 (1.8%) → 28 px, h=5: 1,044
(0.9%) → 35 px, h=6: 323 (0.3%) → 42 px, h=7: 332 (0.3%) → 49 px.
**Elevated (h>0): 27,359 (22.8%) — NOT rare.** So the figure-Y
flattening is REQUIRED for the flat plane to look right (zero the
height-offset arg for figures when gated). The four figure routines all
take the same 4 args (record long, X, baseY, heightOffset) and start
with `link a6,#0`; they are called ONLY from `map_chunk_pos`'s figure
dispatch (2 sites each, 8 total). See §7 for the stub bug found and
fixed.

### Colour question (answered: not the cause)

The face/hidden levels in the dispatch-hook flat write the SAME flat
byte as the top calls (the flat byte is set from the cell terrain type
in RAM `$FF00B0`, shared by all three call sites). So the stepped look
is geometric (height), not a colour difference. The top/face/hidden
calls all write land 0x33 / water 0x11.

### "Some zones are single plane" (confirmed)

Dayset (2026-11-12 ~18:21 EST): "Some zones are single plane." This
matches the height hypothesis exactly: the zones that are a single
plane are the ones with no height variation (naturally flat terrain),
while the zones that are not are the ones with height stacks. The flat
zones are exactly the height-0/uniform-height zones and the stepped
zones are exactly the ones with height stacks (the height census above
and the face/hidden code path). No zone-by-zone table was built (the
location in image-25.png was not identified from chunk data — see §4).

---

## 4. Trees and image-25.png

### The screenshot

`~/workspace/user/media_library/image/image-25.png`: the diamond play
area has a large FLAT grey centre region and FLAT green regions around
the edges (the ground is flat, no texture — this zone IS a single plane
for the ground), the character is visible standing on the grey, and the
HUD/minimap/compass are intact. **BUT the trees are still FULLY
DETAILED (brown trunks, green canopies with shading) — they did NOT
flatten.** That contradicts the flat-world report's claim that
"buildings/trees flatten with the ground". Minimap shows a volcano /
mountain (orange/yellow eruption). Gold reads $1000, TIME 4 AM. The
grey centre is UNEXPLAINED (not the flat-world ROM's land green 0x33
nor water 0x11 — possibly a road/clearing tile type, or unpainted
buffer showing palette idx 0, or a tile drawn by a path the hook
doesn't cover). **Location NOT yet identified from chunk data.**

### Trees are entities, not terrain (resolved)

The flat-world hook flattens ALL `map_chunk_pos` `$E358` terrain calls
(return addrs $01BC20/$01BC42/$01BC8A), yet the trees in image-25.png
stayed fully detailed — so trees are NOT drawn by those calls. They are
drawn via hero_track / the draw records (`$FFB0CC`) as entities (the
$023234/$02326C `$E358` calls, NOT hooked). **The flat-world report's
claim "buildings/trees flatten with the ground" is WRONG for trees.**
Buildings ARE terrain (the City of Division probe showed "one flat
green plane" with no building structures) — they flatten with the
ground. For the flat-plane ROM: trees stay detailed automatically
(entities, separate path); buildings flatten (terrain).

### Caveat — location-dependent

In the City of Division (the Buc save state used for the measurement),
the trees ARE terrain tiles and flatten with the ground (the flat-world
diagnostic screenshot showed "one flat green plane... no texture", and
the flat-plane screenshots show no trees). The trees-stay-detailed
finding is from image-25.png's location (volcano minimap, unidentified),
where the trees are entities. **The ROM does not touch the entity /
figure path (except zeroing the height offset), so entity trees should
stay wherever they are — but this was NOT verified in an entity-tree
location**, because that location was never identified. Dayset's
playtest in a tree-entity location is the check.

---

## 5. Collision — Dayset's hypothesis (measured, not guessed)

Dayset (2026-11-12 ~18:34 EST): "Maybe each step is checked on the
colision too adds to the frametime."

### Count

`move_cost_calc` ($01C892): exactly **3 call sites** — $024B6E and
$024B9C (both inside `combat_move_unit` $024984) and $025446 (inside
`world_reposition_leader` $02513E). It sets move costs by vessel type
(foot (3,1), Dino (3,1), Boat (1,1), Ship (1,1), Dragon (38,38) — the
(2,2) write at $01C8C6 falls through into the mode-1 block; live base
is (3,1)), then calls `world_get_mode_portrait` +
`map_chunk_cache_read` (reads the target chunk cell), does bounds
checks, and in the overworld path does a `divs.w` to compute the cell
index. Returns 0 if blocked (sets char +0x18 = $FE). The `$02DC0C`
walkability gate has exactly ONE caller ($02E508, statue-summon
direction search) and is NEVER on the move path.

`combat_move_unit` ($024984) calls `move_cost_calc` 1–2 times per
invocation ($024B6E first; if it returns 0/blocked, a second call at
$024B9C as a fallback). It has ~17 call sites (combat_turn_run movement
block: $0224B8, $022676, $022928, $022A96, $022AE6, $022B5C, $022DCA,
$022EC0, $022EFC, $023162, $0231B8; plus $026980, $02D7F6 (op-5 handler),
$03271E, $033834, $0338D6, $03394C).

Movement block iterates d4 = 0..55 (56 characters) per tick (loop end
$022F34: `addq.w #1,d4; cmp.w #$38,d4; blt L0227FC`). `$FF0146`++ mod 4
at $0227DA (NPC placement-order round-robin). Path A ($022826, mode 2
room) vs Path B ($022A18, mode 1 overworld); Path B calls
`combat_move_unit` at $022A96 and $022AE6.

### Per tick or per cell commit? PER TICK (subcell angle answered)

`world_tick` ($02159A–$0215B2) derives **`$FF0094 = (grid+$A) mod
(grid+$8)`**. Grid+8 = 1 for `$FFB08C`/`$FFB09C`/`$FFB0AC` and 4 for
`$FFB0BC` (see §1). So **`$FF0094` is ALWAYS 0 for the overworld and
most rooms** (x mod 1 = 0); it is 0 only when phase==0 for the `$FFB0BC`
grid. Therefore the combat_turn_run movement gates at $0226FA and
$022790 (`tst.w $FF0094; bne …` — skip the movement block) **never fire
for the overworld** — the movement block (and hence combat_move_unit /
move_cost_calc) runs **EVERY tick**, not once per 4 ticks. The CELL
COMMIT is once per 4 ticks (on the 3→0 wrap of grid+$A), but the
collision check runs per tick per moving character. **Collision is
checked per subcell phase (every tick), NOT per cell commit.**

### Cost — STATIC ESTIMATE (not live-measured; a live counting probe was not built)

When walking in the overworld: leader 1 combat_move_unit/tick → 1–2
move_cost_calc; followers (~3) via world_reposition_leader → 1 each;
NPCs (a few, area-dependent) → 1–2 each. Total roughly **~6–15
move_cost_calc calls/tick**. Each call is roughly ~500–800 cycles
(prologue + world_get_mode_portrait + map_chunk_cache_read + bounds +
divs.w + jsr/rts overhead) → ~3,000–12,000 cycles/tick = **~0.02–0.09
frames/tick** (1 frame ≈ 127,700 cycles at 7.67 MHz). Against the
decomposition (tick logic 2.41 frames/tick, total cadence 22.13), that
is **~1–4% of the tick logic, ~0.1–0.4% of the total cadence**.

**Verdict: collision is NOT a meaningful contributor to the frametime;
the render (15.98 frames/tick) dominates.** Even eliminating ALL
collision checks would move the cadence from ~22.13 to ~22.05 frames —
a ~0.4% speedup. Cheapest cut if it ever mattered: check only on cell
commit (every 4th tick) instead of every tick — but it does NOT belong
in the flat-plane ROM and is not worth doing on its own. This verdict is
a static estimate; the live count probe was not built.

---

## 6. The flat ground plane ROM — design, result, and defects

### Design

- **Gate:** `$FF00AE == 1` AND grid `$FFA7FC == $FFB08C` (overworld).
  Room untouched; normal world view and zoomed view both flattened
  (see §1 — they share the overworld grid).
- **Face/hidden:** skipped when gated (`flat_skip` $FD400 — rts, no
  `$E358`). No height-stack sides.
- **Top:** 3x2 block fill at the BASE Y (see §2). Land 0x33 green,
  water 0x11 dark blue (terrain types {0,2,3,10,11,15,21,22,23} via a
  64-byte water table). If ungated, tail-calls the original `$E358`.
- **Figures:** 4 stubs (`fig_hero`/`fig_promote`/`fig_tile`/`fig_anim`)
  zero the height-offset arg when gated (see §7), else pass through
  and tail-jmp the real routine. Figures drawn normally (textured),
  standing on the plane.
- **Patch:** `patches/flat-ground-plane/` — source.s (vasm mot syntax,
  blob at $FD400), build.py (assembles, parses stub addrs from the
  listing, verifies all 11 patch sites byte-for-byte, fixes both
  checksums via tools/checksum.py fix-all, writes changed-bytes.txt +
  .ips with round-trip verification). 11 patch sites: $01BC1A (face),
  $01BC3C (hidden), $01BC84 (top), $01BD98/$01BF14 (hero_track),
  $01BDE4/$01C006 (map_promote_record), $01BE30/$01C052
  (map_tile_at_offset), $01BE7A/$01C09C (map_animated_tile).
- **ROM:** `rop-flat-ground-plane.rom`, MD5
  `992465cc0a8dd958febcadf3eede430e` (header 0x45D9, runtime
  0xA003394B), 607 bytes differ from the original. IPS 825 B,
  round-trip verified. Original ROM untouched (MD5
  `30c18fdbe2183f64702ae9f1a45d63f9`, re-verified in build.py).

### Speed (measured, same view/state, both ROMs)

Measurement probe (`.scratch-flat-zoomed/`, safe JMP-pattern — see §8):
Buc save state → cutscene → overworld, cadence = frames per
view-render in the overworld.

| ROM | frames/render | renders / 540 frames |
|---|---|---|
| original | **22.5** | 24 |
| flat plane, 1-block (figures CORRUPTED, §7) | 7.71 | 70 |
| flat plane, 1-block (fig fix) | 8.18 | 66 |
| flat plane, 2x2 fill | 8.31 | 65 |
| flat plane, 3x2 fill (this ROM) | **8.44** | 64 |

**Speedup (this ROM): 22.5 / 8.44 = 2.67x.** The 1-block figure-corrupt
build was artificially faster (corrupted figure draws skipped work);
the fixed builds are 8.18–8.44. Each widening of the fill costs a
little speed (more block writes) but the plane is what matters. Both
numbers confirmed by an identical second run (byte-identical logs —
deterministic).

### Look (screenshots in `.scratch-flat-zoomed/`)

- **Overworld (this ROM):** solid flat green plane with blue water
  patches; the figure stands on the plane (not floating); "LESSON
  OVER." text lingers (normal — same as the original at that point);
  HUD/minimap/compass intact. Green fraction of the play-area crop:
  41.8% (1-block: 11.1%).
- **Room (boot check, this ROM):** fully textured — pink floor, blue
  water, grey stone walls, bookshelves, Thalmus visible in the centre,
  HUD intact (Gold $1000, TIME 4 AM). Gate correctly fails in the room.
- **Known defects:**
  - A small **black gap at the diamond's bottom edge** (a few tiles)
    where the fill does not reach the scatter-only edge tiles. The
    interior plane is solid. A wider fill (3x3 / 4x2) could close it at
    the cost of more boundary wobble; not attempted (diminishing
    return).
  - **Trees flatten in the City of Division** (they are terrain tiles
    there). Entity trees in other locations stay detailed (§4) — not
    verified in an entity-tree location.
  - **Buildings flatten** (terrain) — the town becomes a flat green
    plane. By design.
  - The **blue water patches are larger** than the fountain/pool in the
    original (the 3-wide fill spreads water colour ~1-2 tiles past the
    water cells at land/water borders — the last-cell-wins overlap).
    Cosmetic.

### What was NOT verified

- **Cadence in real play** (walking, battles, other locations) — measured
  only in the Buc-save-state overworld (City of Division, standing
  still after the cutscene). Player animation rate not measured.
- **Look in real play** — overworld outside the City of Division, room,
  menu, teleport not re-checked on the final ROM (room boot-checked
  only). World-view pixel-identity not live-verified (code-gated only).
- **The zoomed view specifically** — the measurement is the normal
  world view after the cutscene; whether the B-button zoomed view is
  flattened on this ROM is Dayset's playtest check (§1).
- **Trees staying detailed** in an entity-tree location (§4).
- **Collision cost** is a static estimate (§5); no live counting probe.
- **image-25.png location** not identified from chunk data; the grey
  centre unexplained.

---

## 7. Bugs found and fixed during the build

### Fig-stub stack offset (found live, fixed)

The figure stubs first used `clr.w 4(a7)` to zero the height-offset
arg. But the figure call sites push (heightOffset, baseY, X,
record-long) — heightOffset FIRST, record LAST — so on stub entry the
stack is [ret addr (4)][record (4)][X (2)][baseY (2)][heightOffset
(2)]: the height offset is at **12(a7)**, and **4(a7) is the record
pointer's HIGH word**. `clr.w 4(a7)` zeroed the record pointer's high
word, CORRUPTING the record pointer passed to hero_track /
map_promote_record / map_tile_at_offset / map_animated_tile — the
figure routines then read garbage records (wrong figure, missing trees;
the corrupted `$E358` draws could also clear fill pixels to black via
the and/or composite's zero mask, contributing to the checkerboard).
**Fix: all 4 fig stubs now use `clr.w 12(a7)`** (source.s lines
122/131/140/149). After the fix the figure is visible standing on the
plane and the cadence rose 7.71 → 8.18 (figures actually drawing).

**Open check:** a background grep was verifying that the SECOND-block
figure call sites ($01BF14/$01C006/$01C052/$01C09C) push in the same
order (heightOffset, baseY, X, record). That grep was killed by a
service restart before finishing and was NOT re-run; the first-block
sites were verified directly in rop.s, and the second block uses the
identical dispatch pattern. The empirical evidence (figure visible,
trees/figures drawing) supports the fix, but the second-block push
order is formally unconfirmed — if any site differs, that site's stub
needs adjustment.

### vasm branch range (found at build)

The 2x2/3x2 fill made `flat_top` long enough that the early
bounds-check branches (`bmi.s`/`bge.s`/`blt.s` to `.skip`) exceeded the
short-branch ±127-byte range (vasm error 2029). Fixed by changing those
four branches to `.w` (word) form.

### vasm gotchas (from this build)

- `cmpi.l #imm,An` is NOT a valid 68000 instruction — the grid compare
  must use a data register (terrain stubs use d6, saved/restored via
  movem; fig stubs use d0, dead at the figure call sites).
- PC-relative indexed displacement is 8-bit only — the water table was
  too far from flat_top for `(water_tbl,pc,d3.w)`, so it uses `lea.l
  water_tbl,a1` + `(a1,d3.w)` with a1 in the movem save list.
- vasm `jmp <label>` → absolute SHORT from section offset; use `bra.w`.

---

## 8. Measurement probe (safe pattern)

`.scratch-flat-zoomed/`: measure_probe.s (vasm; auto-advance VBlank
hook copied from probe_overworld.s — trigger Buc script `$FFC384 =
$1A228` + `$FF0110 = $FFFF` after 60 frames, set `$FF010A = 2` when a
message is on screen; logs every 30 frames to `$FFD800`, 150 records x
12 B: frame, mode, script ptr LOW, `$FF010A`, `$FF0110`, render
counter; breaks via log_full after 20 straight overworld logs),
build_measure.py (builds measure_orig.rom + measure_flat.rom, probe blob
280 bytes at `$FFBC8`), run_measure.py (pty debugger driver: sets
LOG_FULL breakpoint 0xFFCCA, clicks the vsync dialog OK at (510,315)
after 3 s, waits up to 420 s, screenshots at the breakpoint via mss,
reads the RAM log via pipelined p/x reads, computes the cadence, writes
JSON).

**Key fix vs the crashed cadence probe:** the `_render` hook
(map_chunk_pos $01BA4E entry, counts renders in `$FFD7F4`) uses the
**JMP pattern** (`jmp _render`, re-executes displaced `link a6,#-28` +
`movem.l d4-d7/a3-a4,-(a7)`, `jmp $01BA56`; addq.w touches flags only,
no registers saved) — the cache-test pattern, proven safe. The crashed
probe used the JSR-discard pattern (`jsr _render + nop`, `addq.w #4,a7`
to discard the return address). The JMP-pattern probe ran cleanly 6
times (orig x2, flat 1-block x2, flat 2x2 x1, flat 3x2 x1), all hitting
LOG_FULL. ROMs: measure_orig.rom MD5 4d5396ac809375325935eab8a9ce72e0;
measure_flat.rom (3x2) MD5 412c2ecdab0058a735e76c156f66bd07. LOG_FULL =
0xFFCCA, _render = 0xFFCCC.

**Debug counters** (added to flat_top during the checkerboard
investigation, kept in the shipped ROM): `$FFD7F6` = gated calls,
`$FFD7F8` = bounds-check skips, `$FFD7FA` = fills written. Final run:
7600 / 0 / 7600 — the fill runs for every gated call and is never
skipped. (These counters are harmless scratch writes; they do not
affect the game.)

**Driver lessons:** run the driver with the VENV python
(~/workspace/rings-of-power/tools/.venv/bin/python) — system python3
lacks mss. The driver needs DISPLAY=:99 in ITS OWN environment for the
mss screenshot (not just in the env dict passed to BlastEm). Launch as
`DISPLAY=:99 nohup <venv-python> run_measure.py <rom> 420`. The
driver's wait loop re-issues "c" every 2 s; it worked in practice (6/6
LOG_FULL hits), but there is a theoretical race where a breakpoint
could be consumed by a send() drain — watch for it. Log validation
(frame == i*30) accepts the i=0 zero record (frame 0, mode 0) as
"valid" — harmless (mode 0, excluded from the overworld set).
Overworld records number 19, not 20, because mode flips to 1 before
the grid switches, so 1–2 early mode-1 records don't count toward the
20-counter; the cadence uses the mode-1 records' counter deltas, which
is correct.

**Stuck probe cleanup (2026-11-12 ~23:46 EST):** the earlier
probe_overworld.rom processes (PIDs 6659, 6977) had been running 67
minutes; a screenshot showed the game at the "YOU HAVE BEEN KILLED IN
BATTLE..." screen — the auto-advance drive to the overworld had died
in a random battle (it never froze; it just ran past the breakpoint
into a battle because the breakpoint was never set in that run). Killed
both PIDs (by PID, not pkill — pkill self-match trap: a `pkill -f
'blastem.*rop-flat-ground-plane'` inside an exec matched the exec's own
command line and SIGTERMed the exec itself; use bracket patterns or
kill by PID — and note the bracket pattern alone is NOT sufficient when
the ROM filename and the blastem path both appear in the command line,
as happened again at 00:27 EST; kill by PID). Lesson: the auto-advance
approach works but risks a random-battle death; the measure probe
breaks after ~10 s in the overworld, fast enough to usually avoid a
battle.

### BlastEm / toolchain wiped mid-task (restored)

A service restart during the 3x2 measurement wiped BlastEm
(`/usr/games/blastem`), the cached .deb, xdotool, libGLEW, libxdo3,
libXtst, and Xvfb :99. Restored from the Ubuntu mirrors (blastem
0.6.3.4-1build1 + libglew2.2 from ubuntu.cs.utah.edu; xdotool +
libxdo3 + libxtst6 from archive.ubuntu.com) via `dpkg -i` (never
`apt-get install -f`). Durable copies of all five .debs are now in
`~/workspace/rop-work/tooling/` (blastem, libglew2.2, xdotool,
libxdo3, libxtst6) plus /var/cache/apt/archives/, so the next wipe is
a one-command restore. BlastEm config restored from
/etc/blastem/default.cfg.dpkg-new → ~/.config/blastem/blastem.cfg
(already present). Xvfb :99 restarted (1280x1024).

---

## 9. Files

- ROM: `~/workspace/rop-work/flat-world/rop-flat-ground-plane.rom`
  (MD5 `992465cc0a8dd958febcadf3eede430e`)
- Patch: `~/workspace/rop-work/flat-world/patches/flat-ground-plane/`
  (source.s, build.py, README.md, changed-bytes.txt,
  flat-ground-plane.ips)
- Measurement: `~/workspace/rop-work/flat-world/.scratch-flat-zoomed/`
  (measure_probe.s, build_measure.py, run_measure.py,
  measure_orig.rom, measure_flat.rom, measure_orig_measure.json,
  measure_flat_measure.json, measure_orig_overworld.png,
  measure_flat_overworld.png, run logs)
- Toolchain restore: `~/workspace/rop-work/tooling/` (5 .debs)
- Evidence: `~/workspace/user/media_library/image/image-25.png`
  (Dayset's single-plane zone screenshot)
