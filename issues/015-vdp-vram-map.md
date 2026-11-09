# Issue #015 — VDP register + VRAM layout map

**Epic 3**  
**Milestone:** M3  
**Status:** done (2026-11-09)
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



## Work done 2026-11-09 (agent session, no ROM in VM)

- **Deliverable:** docs/graphics.md — VDP register sets documented (boot table 0x28E value-by-value, $A14 set, display-on sequence, $11E06 game set), VRAM layout table per configuration, and the per-frame section CORRECTED: $EB772 is sound-only (#003), drawing lives in the main loop ($1B918, $1194A, $170DA).
- **Acceptance:** MET: register sets + VRAM layout (verified pieces) + write-up in docs/graphics.md. NOT MET / NOT EVIDENCED: the issue's '$4323C tail writes' — $4323C is the save routine; no VDP writes are attributed to it in any repo doc (recorded in graphics.md §1d as a stale premise, not filled in). PARTIAL: full per-screen register sets + per-frame draw list remain open (need live trace).

**Status after this session:** in progress — partial (see below). Not marked done.

## Update 2026-11-09 (session #3, ROM + BlastEm debugger) — DONE

The remaining live-trace work is done; write-up in
docs/graphics.md §5 (per-screen register table §5a, draw
trace §5b, paradox note §5c). ROM used: the ORIGINAL
(scratch copy; byte-identical to the M5 rebuild).

- **Per-screen register sets — captured live** (`vr` at
  breakpoints 0x242 / 0x334 / 0x388 / $11E06 / $14FB6,
  VBlank-stepped intro samples, $D28E samples): boot table
  and $A14 set **confirmed value-for-value** against §1a/§1c;
  $A14's R11=$03 (per-line H-scroll) made explicit; $119E's
  R10 restore ($FF) caught between the animation and $11E06;
  $11E06's set confirmed exactly at $14FB6 entry.
- **New:** the intro driver runs **its own register sets**
  (planes $2000/$F000/$0000, SAT $4400, H-scroll $4000;
  R11 full on screen A, line on screen B), and by main-loop
  entry R16 is $01 (64×32), not $11E06's $03 — a later setup
  pass shrinks the planes (write not isolated).
- **Draw trace (the $11E06 → intro transition):** $11E06
  issues no DMA (CPU VRAM clear via $DC60/$D9EE); tile
  uploads are $11A7C → $DA04 DMA (13/13 sampled hits return
  to 0x11A98); nametables via the $1194A blitter from the
  intro draw cluster $15ECE–$15FA0; window rows via
  $DC60($F000 + n×$80); SAT written entry-by-entry by CPU
  (see #016). Per-frame main-loop redraw stays the $1B918
  flag dispatcher; its tile re-upload is one $DA04 DMA
  ($33C0 words from $FF1EC0 to $FF8674<<5).
- **Acceptance:** register sets ✓ (the '$4323C tail writes'
  sub-item stays recorded as a disproven premise in §1d —
  $4323C is the save routine and writes no VDP registers);
  VRAM layout ✓ (now per-configuration, runtime-verified);
  per-frame draw dispatch ✓ (the 'from VBlank $EB772'
  wording rests on the premise #003 disproved — $EB772 is
  sound-only; the actual dispatch is traced instead);
  write-up ✓ (docs/graphics.md §5).
- **Not covered:** register sets for post-intro gameplay
  screens (combat, towns) — unreachable without gameplay
  input in this headless setup; every screen reachable
  without input is captured.

**Status: done.**
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
