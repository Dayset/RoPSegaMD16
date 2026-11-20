# Big-rework PoC — build report

**Date:** 2026-11-13. **Status:** PoC ROM built to DESIGN.md §8.
**Nothing landed on main. Original ROM untouched.**

## Deliverables

- PoC ROM: `~/workspace/rop-work/big-rework/rop-big-rework-poc.rom`
  (MD5 `64b742edf92cf8b3b2227b8654d550e9`, 1,048,576 bytes)
- Patch: `~/workspace/rop-work/big-rework/patches/big-rework/`
  - `source.s` — the patch source (three trampolines, 980 bytes)
  - `source.bin` — the assembled blob
  - `build.py` — rebuilds ROM + IPS from the original
  - `rings-of-power-big-rework-poc.ips` — 1,426 bytes, 101 records
  - `changed-bytes.txt` — full original → patched listing
  - `README.md` — patch readme (usage, checks, limitations)
- Design read: `.scratch-big-rework/DESIGN.md` (§§0–10 + appendices,
  in full) and `.scratch-big-rework/DAYSET_DESIGN_CLARIFICATION.md`.

## What was built (to §8.2, step by step)

1. Base is `rop-original.gen` (MD5 `30c18fdbe2183f64702ae9f1a45d63f9`,
   re-verified after the build). Fresh decode-once implementation,
   **not** layered on the interp/camera-slide line.
2. Scene setup: R4 = `$02` (Plane B `$4000`, static patch at
   `$12C9A`). R16 needs no patch — `world_map_draw` already sets
   `$9001` (planes 64×32; verified at `$12CDE`).
3. Load (once): the existing path runs unmodified —
   `clear_decode_buffer` + `map_chunk_pos` (`$01BA4E`, camera = room
   camera) + `dma_upload` (`$FF1EC0 → VRAM $FF8674×32`, `$33C0`
   words). Figures are baked in, frozen.
4. Nametable (once): the room table (23 rows × 36 cols, base
   `$FF8674`) is drawn into **Plane B** `$4000` instead of the
   window plane (static patches at `$12E68` in `world_map_draw`
   and `$16326` in `world_map_redraw`; the second site was found
   by tracing `world_map_redraw`'s callers — see below). The
   install hook additionally blanks the whole Plane B table with
   tile `$7FF` and blanks the window room rect with tile `$7FF`,
   so Plane B shows through. Load scroll is **(0,0)** — see
   "Corrections to the design".
5. Per frame: a VBlank hook reads the D-pad (`$FF0018`) and
   adjusts the Plane B scroll via `$DC16`, 1 px per frame
   horizontally, 9/16 px vertically (see "Scroll"), clamped to
   ±1 cell (ΔhScroll ±14 px, ΔvScroll ±8 px). The hook writes
   `$DC16` only when the scroll changed.
6. Per-tick re-render disabled: a `redraw_check` hook clears
   `$FF0098` at entry once the room is installed (room 156 only).
   The menu/panel/dialog arms of `redraw_check` do not depend on
   `$FF0098` and keep running; tick logic (`combat_turn_run`)
   keeps running.

## Corrections to the design (found by reading the disassembly)

These are deviations from DESIGN.md §8.2 as literally written,
each verified against `disasm/src/rop.s`:

1. **Load scroll is (0,0), not (16,0).** §8.2 step 4 assumes the
   image at plane origin (0,0). The actual room-draw call
   (`$12E50`) passes x0=2, so the image sits at plane (2,0) cells
   — already aligned with the viewport (screen cols 2–37) at
   scroll 0. The PoC keeps the draw's args and uses load scroll
   (0,0). Pixel-identical first frame follows by construction.
2. **R16 is already `$01` in `world_map_draw`.** §8.2 step 2 says
   to set R16=`$01`. `$12CDE` already writes `$9001` (64×32).
   (`gfx_layout_game` sets `$9003`, but `world_map_draw` re-sets
   it before gameplay.) No patch was made for R16; the install
   hook still writes `$9001` at the transition so the save-state
   path is covered.
3. **Tile 0 is NOT blank — the PoC uses tile `$7FF`.** §3.3/§9 R3
   say tile 0 is 32 zero bytes and to verify it. It is not: VRAM
   `$0000-$001F` (tile 0's pattern) is also the Plane A nametable,
   which the first `gfx_tilemap_fill` fills with `$0134` words —
   so tile 0's "pattern" is nametable bytes, not zeros. The PoC
   instead fills with tile `$7FF` (pattern VRAM `$FFE0-$FFFF`):
   VRAM is cleared at boot (`$11E06` loop), and the highest tile
   upload ends at tile `$7F5` (VRAM `$FEBF`), so `$7FF` is 32 zero
   bytes = transparent. (Separately verified by decompressing the
   font record: the font's tile 0 itself IS all zeros, so the
   game's window fills with the font-base tile are transparent —
   but the PoC does not rely on that.)
4. **The Plane B table must be blanked whole before the image
   draw.** Cells outside the image rect would otherwise hold
   rec-6 tile-pattern bytes (world_map_draw uploads rec 6 to
   `$3680-$6D3F`, covering `$4000-$4FFF`) interpreted as
   nametable entries — visible garbage in the screen margins
   (cols 0–1, 38–39, rows 23–27), where the transparent window
   lets Plane B show through. The install hook fills all of
   Plane B (`$4000`, 64×32) with `$7FF` before drawing the image
   rect. This also covers the overworld, which gets the same
   clean install at scroll 0.
5. **`world_map_redraw` is a second room-draw site.** The room
   table is drawn not only by `world_map_draw` (`$12E50`) but
   also by `world_map_redraw` (`$16`2FE, called from `map_view`'s
   exit path to restore the room after the map closes). Its
   `pea $001000.w` at `$16326` is redirected to `$4000` too,
   otherwise closing the map would repaint the room into the
   window (unscrolling, on top of the scrolling Plane B image).
6. **The install is self-contained in the `redraw_check` hook,
   not dependent on `world_map_draw` having run under the PoC
   ROM.** This matters for the save-state path: a state saved
   under the original ROM resumes with the room table in the
   window plane and R4=`$00`. At the first tick with `$FF0098`
   set (it is set at the end of every tick, even standing still
   — `redraw_flag_set` at `$0231CA`), the hook writes R4/R16,
   blanks + draws Plane B, blanks the window rect, and lets the
   body's decode+DMA run. A third hook (world_map_draw entry)
   additionally resets the install state on every scene setup,
   so a re-setup always reinstalls (a setup re-uploads rec 6
   over `$4000-$4FFF`).
7. **Panel routines are unchanged and harmless.** `gfx_fill_panel_plain`
   (rows 0–11) / `gfx_fill_panel_flagged` (rows 12–17) repaint
   bands of the window grid via `gfx_tilemap_fill_seq` at scene
   entry, exactly as in the original; they paint identical static
   window content in both versions, so no scroll-mismatch artifact
   is introduced (in the original the same bands are static window
   content too).

## Scroll (re-verified arithmetic)

- Signs (§5.2, checked against the emmd rule in §1.6 and the
  §1.3 step vectors): screenX = planeX + hScroll,
  screenY = planeY − vScroll. ΔhScroll = −(dcx−dcy)×14,
  ΔvScroll = +(dcx+dcy)×8. Right (east) (−14,+8), Left (+14,−8),
  Down (south) (+14,+8), Up (north) (−14,−8) per cell.
- Per VBlank: dh = ±16/16 px, dv = ±9/16 px. The vertical rate
  9/16 = 0.5625 vs the ideal 8/14 = 0.5714: after a 14-frame cell
  traverse the vertical offset is 7 px instead of 8 px — a 1 px
  shortfall per cell of travel, irrelevant under the ±1-cell
  clamp. Opposite directions cancel (sums are linear in the
  camera delta, so diagonal D-pad input is exact).
- Pad bits confirmed from `map_view` usage (`$16B26-$16C20`):
  bit0 Up, bit1 Down, bit2 Left, bit3 Right, from `$FF0018`
  (the VBlank handler's pad byte, one frame stale at hook time —
  irrelevant at 1 px/frame).
- Design numbers re-verified by script: whole chunk 896×512 px =
  112×64 tiles = 7,168 tiles = 229,376 B (3.50× VRAM — §2.1
  confirmed); viewport 36×23 = 828 tiles = 26,496 B = `$33C0`
  words; Plane B table 64×32 = 4,096 B.

## Build checks performed (minimal, per task)

- `tools/checksum.py verify-all` on the patched ROM: header
  `0x4C25` OK, runtime `0x334083AE` OK. (Original: header
  `0x8B9F`, runtime `0x8F33608C` — both re-verified.)
- IPS round-trip, checked twice (once in `build.py`, once by an
  independent script): applying
  `rings-of-power-big-rework-poc.ips` to the original reproduces
  the patched ROM byte-for-byte.
- Diff audit (independent script): the only changed bytes are
  the header checksum (`0x18E`), the three hooks (`0x1272`,
  `0x1B918`, `0x12C20`), the three statics (`0x12C9A`,
  `0x12E68`, `0x16326`), the runtime immediate (`0xFD098`), and
  the blob (`0xFD900-0xFDCD3`, 980 bytes). The first `0x200`
  bytes are identical except the header checksum. Nothing else
  in the ROM differs.
- Blob disassembly read back: entries vbl +0, redraw +`$224`,
  scene +`$3AA`; `pea`/`jsr`/`movem`/`link` encodings as
  intended; the `$DC16` argument order (push d,c,b,a) checked
  against `$DC16`'s `$4/$6/$8/$A(a7)` reads.
- Byte counts: blob 980 bytes at `$FD900` (past the runtime
  checksum's summed range `$000000-$FD07B`); IPS 1,426 bytes,
  101 records (records fragment where blob bytes equal `$FF`).
- Original ROM untouched: MD5 `30c18fdbe2183f64702ae9f1a45d63f9`
  re-verified after the build. Nothing landed on main.
- `python3 patches/big-rework/build.py` rebuilds everything
  from the original (deterministic; re-run to confirm).

## What was NOT verified (Dayset is the tester)

- **No live run of any kind.** The ROM was never booted in an
  emulator or on hardware: no boot check, no screenshot, no
  pixel-compare of the first frame vs the original at the same
  camera, no breakpoint/log proof that `$E358` / `map_chunk_pos`
  stay silent after load, no cadence measurement, no D-pad
  scroll observation. §8.3 criteria 1–5 are all unproven live;
  the mechanism is established by construction + code reading
  only. This is the one-phase scope: no live probes, no
  screenshots, no cadence measurements by the build.
- **Tile `$7FF`'s zero pattern** is established by code reading
  (boot VRAM clear + upload ranges), not by a live VRAM read.
  If anything writes VRAM `$FFE0-$FFFF` at runtime, the blank
  would not be blank — the first frame would show it.
- **The §9 R1/R2/R4 gating measurements** (`sim_span2.py`
  re-centre comparison, banded-vs-unbanded bytes, figure
  separability) were not run — they gate the full-game build,
  not the PoC.
- **The map-view scroll fight and the resume jump** (below) are
  reasoned, not observed.

## Known limitations / open items for the playtest

- **World map:** while the PoC is armed, opening the world map
  fights the map's own scroll writes if the D-pad is held (both
  write all four scroll values via `$DC16`). The map may not
  scroll properly while open. Closing it restores the room, but
  the first D-pad step after closing can jump by the stored
  scroll offset: the VBlank hook writes only on change, so it
  does not notice the map zeroed the scroll, and the next step
  writes the full stored offset at once. Out of the §8 demo
  scope; a full-game build needs a map-active guard.
- **D-pad walks Buc logically.** Game input is untouched, so
  holding the D-pad also advances the leader (and the camera)
  while his baked figure stays put. Walking through a door
  changes location; the PoC disarms and the new room installs
  fresh on entry.
- **VBlank-hook VDP interleave:** the scroll write runs in
  interrupt context (same accepted hazard class as the debug
  overlay's hook). It writes only when the scroll changed, and
  a corrupted write self-corrects on the next VBlank.
- **Water frozen** at one `$FF0092` phase; **figures frozen**;
  no strip streaming, no banded decode, no tick governor, no
  sprites — all §8.4, by design. The overworld is not proven
  (same mechanism, but the PoC's gate/scroll are room-156-only).
- **First frame after a save-state load:** the install fires on
  the first tick (`$FF0098` is set every tick). If Dayset loads
  the state while a menu is open, it fires after the menu
  closes. The room may show in the window plane for that first
  tick — that is the original layout, not a defect.

## How Dayset checks it

1. Run `rop-big-rework-poc.rom` (or apply the IPS to a clean
   original). 2. Load the Buc save state (`slot_0_1_ou3l.state`,
   Academy room). 3. The room should look exactly like the
   original. 4. Hold the D-pad: the whole room slides smoothly
   under the fixed frame; release and it stays. No figure moves.
   No hitch, no jump, no flicker. 5. At the ±1-cell clamp the
   room stays correct.

## Not built (one phase only)

Full chunked world, strip streaming (Scheme A), banded decode,
figure sprites (§6), the tick governor (§5.5 — Dayset's call),
NPC/script pacing, overworld proof, chunk-edge loading. The
governor is flagged as Dayset's call in the design and was not
built. Design §9 risks R1/R2/R4/R5/R6 stay open for the
full-game build.
