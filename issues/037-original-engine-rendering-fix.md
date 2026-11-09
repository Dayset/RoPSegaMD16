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
