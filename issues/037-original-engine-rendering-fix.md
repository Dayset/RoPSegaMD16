# Issue #037 — Original-engine rendering fix: multilevel lag + smooth tile movement

**Epic 3**
**Milestone:** M3
**Status:** open

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
