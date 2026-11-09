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



## Work done 2026-11-09 (agent session, no ROM in VM)

- **Deliverable:** docs/tiles-sprites-palettes.md — documents the decoded reality and CORRECTS the issue premise: 0x060000-0x093FFF is NOT raw tiles (noise in every layout, #005) but the start of the $96120 compressed streams. Packed 2px/byte decoding, palettes (31 x 16 at 0x0CC9D8, loader $11082), sprite record format ($B86AE: [palette][36 tiles] = 48x48), and render_tiles.py extension notes.
- **Acceptance:** MET: palettes located + listed; tile data confirmed as tiles (in the compressed tables, with rendered PNGs from #005 already under disasm/graphics/: font/terrain/logo/portraits); sprite record decoded + rendered (recs 0/1/5). PARTIAL: VDP sprite attribute-table behaviour at runtime is undocumented — needs a live VRAM trace (no ROM/emulator in VM). The literal acceptance wording (decode 0x060000 as tiles) is impossible because its premise is disproven — see the doc §0.

**Status after this session:** in progress — partial (see below). Not marked done.
