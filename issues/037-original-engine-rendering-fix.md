# Issue #037 — Original-engine rendering fix: multilevel lag + smooth tile movement

**Epic 3**
**Milestone:** M3
**Status:** in progress — patch shipped 2026-11-09 (items 2–5) and
verified by measurement (H-scroll 1 px/frame, no snap), but Dayset did
**not** accept the initial fix (visual check, 2026-11-10). A follow-up
investigation into framerate and sub-cell animations with Claude
stalled. Item 1 (multilevel terrain) is design-only — see Notes.

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
      **NOT BUILT 2026-11-09:** the design is documented in
      `patches/smooth-move/README.md` ("Multilevel terrain without lag"),
      but no two-plane layout was built or tested. Open as a follow-up.
- [x] Smooth tile movement: pixel-precision camera — scroll registers
      stepped 1 px/frame, interpolating between tile positions, with
      the name-table strip updated only when a tile boundary is
      crossed. No abrupt snap at tile boundaries. Game logic stays
      tile-based (`$1C21A` position setter, `$32C56` tile scan); only
      the camera interpolates. **DONE 2026-11-09, verified live:**
      `$1B918` hook + `$DC16` stepping, H-scroll `-1,…,-15` then `0`
      per +2-tile camera step, V-scroll `0`, DMA delayed to the
      boundary (`patches/smooth-move/`, `.scratch037/traceP_out.txt`).
      **Open sub-item:** the facing-direction preload (strip + neighbour
      chunk via `$19692`/`$1C802` during VBlank) is NOT implemented —
      v1 leaves a stale edge strip for up to 15 frames per step; v2
      preload would remove it.
- [x] Master Talamus cutscene traced FIRST, before designing the fix:
      identify the mechanism of its soft in-between tile-movement
      animation and of the abrupt whole-screen shift that follows it
      (H-scroll table? sprite/tile slide? name-table swap?). The fix
      builds on the game's own technique, not a guess at it.
      **DONE 2026-11-09:** soft = `$171D6` H-scroll table rewritten
      every VBlank (4–8 px/frame); abrupt = `$15C08` loop exit at
      counter 1000 → 14-frame gap with no scroll calls → wholesale
      redraw (`.scratch037/cutscene-findings.md`).
- [x] Shipped as an `.ips` patch in `patches/` with a BlastEm smoke
      test, once the rebuild gate (#013) exists. Original ROM untouched.
      **DONE 2026-11-09, #013 exception (Dayset's direction, same as the
      music-off patch):** hand-assembled, `patches/smooth-move/
      rings-of-power-smooth-move.ips` (1294 bytes, 95 records),
      round-trip byte-identical; original MD5
      `30c18fdbe2183f64702ae9f1a45d63f9` re-verified.
- [x] Patched ROM delivered to Dayset right after the patch, to see
      it working: built from the original + the `.ips`, checksums
      re-fixed (`fix-all`), boots in BlastEm, scroll register steps
      1 px/frame with no snap. The ROM itself is never committed —
      only the `.ips` is; the ROM is handed over as a file.
      **DONE 2026-11-09:** `patches/smooth-move/rop-smooth.gen`
      (git-ignored, MD5 `3676f49a4a2dfcf7ff70a323a5bef298`),
      header `0x8FA9` / runtime `0x15E8609D` OK, boots, H-scroll
      steps `-1,…,-15` → `0`, no snap.

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
