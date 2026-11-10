# Issue #037 — Original-engine rendering fix: multilevel lag + smooth tile movement

**Epic 3**
**Milestone:** M3
**Status:** in progress (session #8: scroll architecture + intro traced; cutscene mechanism not yet pinned; no patch yet — see the work log at the end of this file)

## Goal
Fix the two rendering weaknesses of the original Mega Drive engine, both
discussed 2026-11-09: multilevel terrain costs far more than flat ground,
and tile movement is jerky (8-pixel snaps).

The lag is not inherent to multilevel terrain, even on hardware with no
GPU. The 68000 draws nothing — the VDP scans the planes out in hardware.
The CPU only updates name tables (2 bytes per cell), and scrolling is a
register write, i.e. free. What chokes is the naive method: redrawing
whole name tables layer by layer every frame. The fix is to let the
hardware do the layering and write only what changed.

## Acceptance
- [ ] Multilevel terrain rendered without per-frame full redraws: high
      ground on one VDP scroll plane, low ground on the other (window /
      sprites for raised features), each scrolled by its own register;
      only the newly revealed strip of each name table written per
      frame. Verified in BlastEm: no frame drops vs the flat-plane case.
- [ ] Smooth tile movement: pixel-precision camera — scroll registers
      stepped 1 px/frame, interpolating between tile positions, with
      the name-table strip updated only when a tile boundary is
      crossed. No abrupt snap at tile boundaries. Game logic stays
      tile-based (`$1C21A` position setter, `$32C56` tile scan); only
      the camera interpolates. **Preload the facing direction:** the
      name tables are already 128×32 cells (R16=`$03`) vs 40 visible,
      so the strip in the facing direction — and the neighbouring map
      chunk, via the `$19692` 4-slot cache — is streamed in during
      VBlank before it scrolls into view. Facing is known before
      movement starts, so the preload can begin a few frames early.
      Vertical headroom is only 4 rows, so horizontal is the easy win.
- [ ] Master Talamus cutscene traced FIRST, before designing the fix:
      identify the mechanism of its soft in-between tile-movement
      animation and of the abrupt whole-screen shift that follows it
      (H-scroll table? sprite/tile slide? name-table swap?). The fix
      builds on the game's own technique, not a guess at it.
- [ ] Shipped as an `.ips` patch in `patches/` with a BlastEm smoke
      test, once the rebuild gate (#013) exists. Original ROM untouched.
- [ ] Patched ROM delivered to Dayset right after the patch, to see
      it working: built from the original + the `.ips`, checksums
      re-fixed (`fix-all`), boots in BlastEm, scroll register steps
      1 px/frame with no snap. The ROM itself is never committed —
      only the `.ips` is; the ROM is handed over as a file.

## Notes
- Depends on #015 (VDP map — done: register sets, G/L layouts, DMA
  `$DA04`, blitter `$1194A`, sprite writers, scroll `$DC16`) and #016
  (the packed-vs-planar paradox affects how tile uploads work).
- Blocked for shipping on the rebuild gate #013 (same as any ROM
  patch — cf. the music-off patch, which was an explicit exception).
- Evidence the hardware already supports the technique: the attract
  animation at `$4E6` rewrites the per-line H-scroll table every
  frame (`[−X, $140, +X, $140]` per line pair, X decrementing) — the
  game already animates scroll values per frame; the movement code
  just doesn't use it.
- Dayset's call: smooth motion is preferred — the cutscene's soft
  animation is the model, its abrupt shift is not.

## Work done 2026-11-09 (session #8) — scroll architecture mapped; cutscene hunt narrowed, NOT solved; no patch built

**What is now established (code census, this session):**

- **All scroll writes funnel through one function: $DC16.**
  Its body (74 bytes) writes all four scroll values in one
  call — VSRAM vertical scroll for planes A/B, then the
  H-scroll table's first line for A/B — from four stack
  words. A whole-ROM census finds exactly **five `jsr $DC16`
  sites**: 0x11F22 and 0x12CF8 (in $12C20, world-map draw —
  both pass zeros: setup, not animation), 0x166FA and
  0x16D6A (the map screen FUN_0001664E — scroll computed
  from frame locals, including a `$10000 − x` two's-complement
  for the register), and 0x1702C (a screen routine passing
  zeros). Design consequence: a pixel-precision camera does
  not need to touch the movement code at all — it needs to
  own the values passed to this one choke point (plus the
  strip writer), which is a far smaller patch surface than
  the issue assumed.
- **The game already animates scroll smoothly in its
  presentation layer.** The attract animation at $4E6
  rewrites the per-line H-scroll table every frame (#015,
  live-verified: `[−X, $140, +X, $140]` per line pair). The
  title logo assembles letter-by-letter with horizontal
  slides (observed live this session). The INTRO sequence
  (below) is a smooth plane scroll. Only *world movement*
  is tile-stepped — through the tile-based position setter
  $1C21A and tile scan $32C56, exactly as the acceptance
  says the fix must preserve.
- **The INTRO sequence is traced, and it is not the
  cutscene.** Menu INTRO (and the attract loop) runs
  $14FB6 → on $123B0's return: scenes $147D0(0, 0x20),
  $147D0(0, 0x3D), $147D0(0, 0x3B), then $12C20 (world-map
  draw). Live this session: the scenes are "Book of Nexus"
  text crawls — the whole page (text + embedded portrait,
  e.g. Void's face) scrolls up as one plane composition in
  small per-frame steps (frames in docs/037-evidence/).
  A full `jsr` census of $147D0 (2,020 B) and its picture
  helper $15C08 (1,782 B) shows **no $DC16 call, no sprite
  writer ($11BD8/$11C9A), no scroll work of any kind** —
  they are static picture/text composition ($1383C record
  loads, $1194A/$11A1A blits, $DE30 text). The crawl's own
  smoothness is therefore produced by the callers' frame
  loop ($123B0/$15012 side), not by the scene player.

**The blocker, exactly (acceptance item 3 not yet met):**
the "Master Talamus" (in-game spelling: **Thalmus**)
cutscene — a character's soft in-between tile movement
followed by an abrupt whole-screen shift — has not been
matched to a code path. It is not in the intro crawl code
(above). The remaining candidates, in order: (1) the
sprite-composed story scenes — the unrolled sprite-picture
composer at 0x13916–0x14782 (~70 $11BD8/$11C9A calls at a
0x2E stride) and $15012's own sprite work (0x1516A–
0x15A12), which build the #016 "intro screens A/B" (30/45
sprites); if a figure slides there, its per-frame position
update is in $15012's frame loop; (2) an in-game story
event at the Academy (Thalmus is Buc's headmaster there)
driven by the $1F296 command-script system, where the
movement would be an entity-step variant of FUN_00024984
with sub-tile position fields. The decisive experiment
for (1): run INTRO in BlastEm with a watchpoint on the
SAT-writer $11BD8 and on $C00004 scroll writes during the
pictured scenes; for (2): start a new game and breakpoint
$DC16 + $11BD8 through the Academy opening. Neither was
completed this session — the live time went to #021's
road attempts (docs/logic-audit.md §13.2).

**Not done, deliberately:** no `.ips` was built and no
patched ROM is delivered. The acceptance orders the
cutscene trace FIRST ("the fix builds on the game's own
technique, not a guess at it"), and the multilevel
half needs a frame-drop comparison in BlastEm that was
not run. Shipping a guessed camera patch would violate
the issue's own gating. The $DC16 choke-point finding
above is the design's foundation when the work resumes:
interpolate the camera at $DC16's five call sites'
level (in practice: the world-view caller to be added),
step 1 px/frame toward the tile target set by $1C21A,
and drive strip updates off tile-boundary crossings —
the name tables' 128×32 geometry (R16=$03) and the
$19692 4-slot chunk cache already provide the preload
surface the acceptance describes.

## Session #9 work log (2026-11-09) — candidates narrowed to the shared stack; gate still unmet, no patch

**Candidate (1) — the $15012 scenes — statically characterised.**
FUN_00015012 (2,982 B) has exactly **one caller**: the story
dispatcher at 0x14FB4, which loops `bsr $15012` → dispatch on
its return code (1/2/3 → $147D0 text crawls 0x20/0x3D/0x3B) →
on 0 calls $12C20 and returns. $15012's 27 callees include
$1194A (blitter), $11BD8/$11C9A (sprite writers), $147D0 +
$15C08 (crawls), $12C20, and the $17860-family map drawers —
it is the pictured-scene player, full stop. **It never calls
$DC16** (not among its callees; $DC16's function-level
callers are exactly $11E06, $12C20, $1664E). Whatever a
$15012 scene does, it does not scroll via the choke point.

**Correction to the session-#8 framing of the "composer".**
The unrolled block at 0x13916–0x14782 is the tail of
**$138A8**, which the repo docs already know as the
**menu-display formatter** (docs/graphics.md §586) — a
per-frame display routine that also draws entity sprites
from the $1B446 6-byte frame-record table (its first $11BD8
call, at 0x13916, draws the $FF02B2-indexed entity). It has
**ten direct jsr call sites** (0x1207C, 0x16308, 0x1B97E,
0x207CE, 0x209E6, 0x20BA8, 0x275D8, 0x29136, 0x2D4CA,
0x2EE62 — fatal-error screen, map draw, verb executor
cases, and more). Ghidra's exported call_edges.txt contains
**none** of them — the "uncalled composer block" reading was
an artefact of the export, the same failure mode the #011
reconciliation documented. $138A8 is shared infrastructure:
free play, menus, conversations, scripts and combat all
composite through it. There is no cutscene-only renderer
at this layer.

**Candidate (2) — the Academy script event — its movement
player is identified.** FUN_00020A88 (374 B) is called by
the verb executor $1F296, by script-case code at 0x207D8,
and by $D28E/$26A8C/$298D2/$2B6E0/$2D56A; it calls $138A8
(the compositor) and the $26xxx step helpers ($26076,
$26CCA, $26DD2, $26E44) — the **same helper family the
free-play step handler FUN_00024984 uses**. Scripted entity
movement is therefore the free-play movement stack driven
by scripts, rendered by the shared compositor: candidate
(2)'s "entity-step variant" is a parameterisation, not a
separate engine.

**Live checks (BlastEm, clean ROM).** (i) The session's
address-coverage log (BlastEm `-l`, ~35 min of driven play:
restores, camps, conversations, the beggar event + fight,
two combats, menus) contains 15012, 138A8, 20A88, 1F296,
DC16, 11BD8 and 24984 — all executed at least once across
play + title attract (the attract runs the story dispatcher,
so 15012's presence there is the intro flow, not free play).
(ii) Breakpoints on $15012 and $20A88 armed during the
intro's Book-of-Nexus crawl: **neither fired** in 30 s of
crawl play, nor across the crawl→logo transition (the logo
is drawn by the $147D0 family, maps.md) — both functions
are scene-level, not per-frame, in that flow. The Academy
beat itself was not reached (the #021 road blocker,
docs/logic-audit.md §14.3, consumed the session's live
time), so the issue's decisive driven experiment — $DC16 /
$11BD8 watchpoints through the Academy opening — remains
unrun.

**Verdict.** Both named candidates collapse into the
game's shared movement/compositing stack, and $15012 is
positively excluded from the $DC16 scroll path. A
Thalmus-specific frame drop, if real, must come from scene
content (sprite count through $138A8's unrolled loop) or
from script-step parameterisation ($20A88 driving the
$26xxx helpers at a different rate) — neither of which a
camera patch at $DC16 would address, and neither of which
has been observed in the actual scene. **The trace-first
gate is still unmet: no patch built, none shipped.** When
the work resumes, the order is: reach the Academy opening
(blocked on the same road as #021's follow-on), watchpoint
$DC16 + breakpoint $20A88/$11BD8 through the Thalmus beat,
and only then decide whether there is a mechanism to fix.

**Session #10 log (2026-11-09).** The road blocker is
CLEARED: the route to Mind was solved from code and driven
clean (docs/logic-audit.md §23.4, docs/route-to-mind.md —
21 steps, gate tile (118,121), SAVE banked at (114,124)).
The Academy of Sorcery's doorstep was reached and its banner
read ("WELCOME TO THE CITY OF THE MIND, HOME OF THE WORLD
FAMOUS ACADEMY OF SORCERY.", evidence s10-acad2 in the
session-#10 rig), but the interior was not entered before
the session's live time ran out: six road/city deaths (gate
Wyvern, knight pairs, an idle-wait ambush inside the city)
consumed the margin. The decisive experiment — $DC16
watchpoints + $20A88/$11BD8 breakpoints through the Thalmus
beat — remains unrun, exactly as scoped in session #9's
verdict. **Gate still unmet: no patch built, none shipped.**
Resume: restore rop9live/save-114124.eeprom (or
save-970.eeprom), drive the 21-step route by day, enter the
Academy from the fountain plaza, and run the experiment
inside; the Academy interior is also the largest untested
location for the #021-follow-on Map purchase.
