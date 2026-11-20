# flat-zoomed — one flat ground plane for the ZOOMED view only

Base: ORIGINAL ROM (MD5 `30c18fdbe2183f64702ae9f1a45d63f9`).
Output: `~/workspace/rop-work/flat-zoomed/rop-flat-zoomed.rom`
MD5 `4ee66e521ac9a636d2167c0d55409d92` (header 0x686D, runtime 0x9EBD3873).

## What it does

The flat ground plane (one flat green plane, water dark blue, 3x2 block
fill, the decoder's face/hidden calls skipped — the same mechanism as
`flat-ground-plane`) applies ONLY to the **zoomed view** — the location
interior (room) reached by pressing B (ENTER) in the overworld. The **big
world** (the overworld, mode 1) stays fully textured, at the original
speed.

## The gate — and why $FF0E98 is NOT the discriminator

The brief's hypothesis was that the zoomed view is distinguished by
`$FF0E98 == $FFFF` (mode 1 + overworld grid + `$FF0E98==$FFFF`). Two probe
runs (run 1 + run 2, `.scratch-zoomed-gate/`) REFUTE that:

- `$FF0E98` is **always** `$FFFF` in the overworld (mode 1, grid
  `$FFB08C`) — in every mode-1 observation across both runs, including
  after walking and after exiting a room back to the overworld. It is a
  location number only in a room (mode 2: `$FF0E98` = 30, 156, ...).
- So a gate of (mode 1 + grid `$FFB08C` + `$FF0E98==$FFFF`) is
  **identical** to the flat-ground-plane gate (mode 1 + grid `$FFB08C`):
  it would still flatten the big world and change nothing.
- **B in the overworld ENTERS a room** (confirmed twice): mode flips 1
  -> 2, grid `$FFB08C` -> `$FFB09C`, `$FF0E98` `$FFFF` -> `$001E`
  (location 30). Walking Right out of the room flips it back (mode 1,
  `$FF0E98` `$FFFF`). B = ENTER / "zoom in on the current location" —
  the zoomed view IS the room (mode 2).

The real discriminator is the **mode**: mode 1 = big world (textured),
mode 2 = zoomed view / room (flat). This patch gates on `$FF00AE==2`
only (mode 2 implies a room grid: `$FFB09C`/`$FFB0AC`/`$FFB0BC`).

## Design (same as flat-ground-plane, re-gated)

- 11 patch sites: `$01BC1A` (face) + `$01BC3C` (hidden) -> `flat_skip`
  (draw nothing when gated); `$01BC84` (top) -> `flat_top` (32-byte
  block fill at the tile's own block, base Y, so the ground is one
  plane); 8 figure call sites (`hero_track` `$01BD98`/`$01BF14`,
  `map_promote_record` `$01BDE4`/`$01C006`,
  `map_tile_at_offset` `$01BE30`/`$01C052`,
  `map_animated_tile` `$01BE7A`/`$01C09C`) -> `fig_*` (zero the
  height-offset arg when gated, so figures stand ON the plane).
- Blob at `$FD400` (496 bytes, free 0xFF padding). Land 0x33 (green),
  water 0x11 (dark blue), terrain types {0,2,3,10,11,15,21,22,23}.
- When not gated, every stub tail-calls the original `$E358` / routine.
- Debug counters kept in the ROM: `$FFD7F6` gated calls, `$FFD7F8`
  bounds skips, `$FFD7FA` fills.

## Measured (probe, Buc save state -> cutscene -> B -> room)

Zoomed view (room, location 30), original ROM -> this ROM:

| condition | original | this ROM | speedup |
|---|---|---|---|
| room, no menu | 15.71 f/render | 7.86 f/render | 2.00x |
| room, menu open | 18.71 f/render | 9.35 f/render | 2.00x |

Big world (overworld, mode 1): **unchanged**. Clean mode-1 windows give
identical cadences on both ROMs (20.0 / 22.0 / 25.45 f/render), and the
overworld screenshot is pixel-identical to the original (2,584 of
1,310,720 pixels differ, 0.20% — animated tiles only, not a flat).
Flat debug counters on the re-gated runs: 19,410 gated calls / 0 bounds
skips / 19,409 fills (probe 1); 11,085 / 0 / 11,085 (probe 2).

Visual: the room is a flat green plane with the figure standing on it
(`zoom_probe_rz_zoom.png` vs the textured original
`zoom_probe_orig_zoom.png`); the overworld is fully textured
(`zoom_probe2_rz_zoom.png` vs `zoom_probe2_orig_zoom.png`).

## Known defects (same as the flat-ground-plane family)

- Small black gap at the diamond's bottom edge (a few tiles; scatter-only
  edge tiles the fill does not reach; interior solid).
- In the room, the furniture flattens with the ground (barrels are
  terrain tiles — they are gone on the flat room; the figure, an entity,
  stays detailed and visible).
- The cutscene room (Buc classroom, mode 2) is also flat — the gate is
  mode 2, which covers every interior, not just the B-entered room.

## NOT verified

- Cadence / look in real play outside the probe (the probe drives the
  Buc save state, B into location 30, and a short walk).
- The B+START map screen: in the overworld probe it produced no visible
  state change (no mode/grid/`$FF00AC` change, renders continued) — the
  map screen itself was not cleanly observed, so whether B on the map
  screen is a different zoom path is still open. What IS established is
  that B (in the overworld) enters the room, and that is the zoomed
  view this ROM flattens.
- Menu / teleport on this ROM (code-gated only, not live-verified).
- The room's water (no water cells in location 30) and multi-level rooms.

## Build

`python3 build.py` — assembles `source.s` with vasm, patches the
original ROM (MD5 asserted), fixes both checksums, writes
`rop-flat-zoomed.rom`, `changed-bytes.txt` (519 bytes differ) and
`flat-zoomed.ips` (677 B, round-trip verified: original + IPS == ROM).
The original ROM is never modified.
