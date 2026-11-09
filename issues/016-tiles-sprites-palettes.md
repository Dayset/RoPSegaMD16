# Issue #016 — Tile/sprite/palette decoding + first rendered tileset

**Epic 3**  
**Milestone:** M3  
**Status:** open

## Goal
Turn the provisional tile region into visible pictures.

## Acceptance
- [ ] `0x060000–0x093FFF` decoded as 4-bpp tiles; first tileset rendered
      to PNG under `disasm/graphics/`
- [ ] Palette(s) located in CRAM format and listed
- [ ] Sprite table format + at least one sprite decoded
- [ ] Tile data confirmed as tiles (not misread code/text)

## Notes
- Depends on #015 and #017 (tiles may be compressed in the other blocks).

