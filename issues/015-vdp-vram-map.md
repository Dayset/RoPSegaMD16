# Issue #015 — VDP register + VRAM layout map

**Epic 3**  
**Milestone:** M3  
**Status:** done 2026-11-09

## Goal
Map how the game programs the VDP: registers, VRAM layout, draw dispatch.

## Acceptance
- [x] VDP register sets documented (boot table `0x28E`, `$A14` set,
      `$4323C` tail writes) with what each register value means
- [x] VRAM layout found: name tables, pattern base, sprite table,
      scroll values (addresses in VRAM, not ROM)
- [x] Per-frame draw dispatch traced — **from `$D28E`, not from
      `$EB772`** (see the correction below)
- [x] Written up in `docs/graphics.md`

## Notes
- Depends on #011. 103 `$C00004` references in the sweep are leads,
  not answers — most are in data regions.

## Correction (2026-11-09)
The third acceptance bullet as originally written said "traced from
VBlank `jsr $EB772`". That premise is **wrong**: `$EB772` is the
per-frame **sound** tick only (PAL/NTSC tempo tick to Z80 RAM
`$A000E6`, `jsr $EBAC6` sound command queue, every 16 frames
`jsr $EBA00` music streamer; #003/#020). It does no drawing. The
real per-frame draw path lives in the main loop `$D28E`: the
`$1B918` redraw checker (called twice per iteration), the `$170DA`
palette routine, and the upload helpers `$1194A`/`$11A7C`/`$11B2E`/
`$DA04`. The write-up in `docs/graphics.md` §6 traces the dispatch
from `$D28E`.

## Findings (summary — full write-up in `docs/graphics.md`)
- Four register sets: boot table `0x28E` (R2=`$30` Plane A `$C000`,
  R5=`$6C` sprites `$D800`, R13=`$37` H-scroll `$DC00`), `$A14`
  (attract: Plane A/B `$A000`, sprites `$DC00`, H-scroll `$2000`,
  R11=`$03` per-line), `$11E06` (game: Plane A/B `$0000`, Window
  `$1000`, sprites `$2400`, H-scroll `$2000`), `$4323C` tail (hang:
  everything `$0000`, R12=`$00` H32 256 px).
- Two runtime layouts: G (game/overworld — Plane A/B `$0000`,
  sprites `$2400`, H-scroll `$2000`) and L (intro/story/location —
  Plane A `$2000`, Plane B `$0000`, Window `$F000`, sprites `$4400`,
  H-scroll `$4000`); R2/R3/R5/R13 take only the G or L values in
  the whole ROM. The sprite-base variable `$FF8644` follows the
  active layout (`$2400` / `$4400`).
- Draw dispatch: `$1B918` flag dispatch (`$FF0098` → map-chunk DMA
  `$DA04($FF1EC0 → VRAM $FF8674×32, $33C0 words)`; `$FF009A` →
  `$275B0`; `$FF009C` → `$26E44`; `$FFB08A` → `$1E5A0`/`$26DD2`;
  `$FF009E` → `$17860` location picture) + always `$138A8` menu
  formatter; `$170DA` palette (mode 2 cross-fades pal 10↔19 via
  `$1225C`, 9 steps); upload via blitter `$1194A` / DMA `$DA04` /
  sprite writers `$11BD8`/`$11C4A`/`$11C9A` / scroll `$DC16`.
- Live-verified in BlastEm (harness `tools/test_vdp_harness.s`,
  90 frames, snapshot at `$FFC002`=70): `vr` prints the `$A14`
  set exactly; H-scroll VRAM `$2000` holds the `$4E6` zigzag
  `[−X, $140, +X, $140]` per line (X = `$FFC002`+1, Plane A
  first); name-table row 0 at `$A000` blank; sprite table at
  `$DC00` matches BlastEm's `vs` word for word (first 4 sprites);
  window `$C000` empty; CRAM palette 0 read live. VRAM-read
  note: the first read after setting the address returns the word
  **at** that address — no dummy word.
- Open: packed-vs-planar paradox (#016); `$16512` column-writer
  cell semantics; `$FF8674`/`$FF8678` tile bases; R18=`$94`
  window position in `$123B0`; `$4E6` phase-2 visuals; `$D28E`
  case-23 writer (open since #021).
