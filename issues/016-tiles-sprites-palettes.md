# Issue #016 — Tile/sprite/palette decoding + first rendered tileset

**Epic 3**  
**Milestone:** M3  
**Status:** done (2026-11-09)

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

## Update 2026-11-09 (session #3, ROM + BlastEm debugger) — DONE

The one remaining item — VDP sprite attribute-table
behaviour at runtime — is now documented in
docs/tiles-sprites-palettes.md §6:

- **Mechanism (static + live):** there is no RAM sprite
  buffer and no per-frame SAT DMA. Sprites are written
  directly to VRAM one entry at a time by
  $11BD8(index, X, Y, width_code, height_code, link,
  pattern_word) at $FF8644 + index×8 ($FF8644 = current
  SAT base variable: $4400 intro / $2400 game, matching the
  live R5 captures). $11B76 clears the base entry (its
  $DC60($4400) call was caught live at intro start, caller
  0x11B84); $11C4A rewrites an entry's size/link word.
  $11BD8 callers: $13D84 (55 sites), $17B88 (23), $15012
  (12), $138A8 HUD (9 — its index $43 = 67 is the main-loop
  list's tail sprite), $1664E (8), $17A40 (4), $1E4E6 (2).
- **Live lists (`vs`):** boot animation = 2 linked 32×8
  sprites drifting down; intro screen A = 30 sprites
  (3×3 grid of 32×32 + 21 of 32×24, pal 2); intro screen
  B = 45 sprites (a 7×5 grid of 16×32 + two large ones,
  all pal 2); main-loop start scene = hidden root 0 →
  22–25 (2×2 of 32×32, pal 1) → 67 (HUD, 16×8, pal 2),
  static over 2400 VBlanks (no demo play).
- **Cross-check:** no observed SAT entry uses the $B86AE
  48×48 portrait arrangement — those records stay
  plane-drawn tile uploads ($11AE4); hardware sprites are
  a separate, per-screen $11BD8 mechanism sharing the same
  uploaded tile space.
- **Acceptance:** palettes ✓; sprite table format +
  decoded sprites ✓ (both the $B86AE record format from
  #005 and now the hardware SAT format + live lists);
  tile data confirmed as tiles ✓. The literal first item
  (decode 0x060000–0x093FFF as tiles) remains impossible —
  its premise was disproven in #005 and is documented as
  such in the doc §0; the tiles were decoded where they
  actually live and rendered under disasm/graphics/.

**Status: done.**
