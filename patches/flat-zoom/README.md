# flat-zoom — flat texture in the zoomed (room) view only

**Status: BUILT and VERIFIED for speed, NOT clean visually — see "Verdict" below.
Flat-only. No subcell-movement change (subcell is a separate step, built on
top of this ROM afterwards, per Dayset 2026-11-12 ~16:34 EST).**

## What it is

In the zoomed-in (cell/room) view, the terrain-stream decodes are replaced by
flat fills — one fill per floor level, water its own colour, no texture. The
world (overworld) view is untouched: textured terrain, jerky ~3 Hz tick, as
before. Base is the **original ROM** (MD5
`30c18fdbe2183f64702ae9f1a45d63f9`), NOT v3 — the v3 glide must not be in
this ROM.

## How it works

`map_chunk_pos` ($01BA4E) is the shared room renderer. It calls the terrain
decoder $E358 three times per window cell (face, hidden level, top tile).
This patch retargets those three call sites to flat stubs in the free
0xFF padding at $FD400:

| Site | Was | Now |
|---|---|---|
| $01BC1A (face) | `jsr $E358` | `jsr flat_level` ($FD400) |
| $01BC3C (hidden) | `jsr $E358` | `jsr flat_level` ($FD400) |
| $01BC84 (top tile) | `jsr $E358` | `jsr flat_top` ($FD418) |

Each stub checks the view selector $FF00AE: if it is 2 (room/zoomed view) it
fills; otherwise it tail-calls the original $E358 (`jmp $00E358.l`), so the
world view (mode 1) runs the original decode byte-identically.

The fill (`flat_fill8`, $FD458) writes the flat colour byte `(k<<4)|k` to the
8 line positions the decoder computes for a tile — `row[Y+k] + col[k +
(X-64)/2]` for k=0..7, 4 bytes each, using the ROM row table $436E0 and col
table $435C0 — with out-of-range lines skipped. Colours: land `k = level+1`
(1–8), water tiles 28/29/494 `k = 9`. Figures are NOT hooked: `hero_track`'s
$E358 calls are untouched, so characters still draw through the original
decoder.

The view selector $FF00AE is 1 = overworld/world view, 2 = room/cell/zoomed
view (writers: $00D29E =1, $01DC1C =2, $01DE6A =1). `map_chunk_pos` is shared;
the mode flag selects the grid at a higher level, so the hook checks it at
render time.

## Verdict (measured 2026-11-12, Buc cutscene state, 150 VBlanks)

- **Speed: MET.** Room tick settles at **~9 frames/tick** (render deltas
  11,11,11,13,10,10, then 9×9; phase runs settle at 9 frames/phase) vs
  **~21.5 frames/tick on the original** — a **2.4× speedup**. The remaining
  ~9 frames are tick logic + DMA + clear + other fixed costs, about the floor
  for this architecture.
- **Coverage: MET.** The whole room diamond is filled; no terrain texture
  remains.
- **Look: NOT CLEAN.** The room renders as **dark blue dashes on black**,
  not distinct per-level flat colours. The intended level colours
  (pink floor, etc.) do not show as separate colours.
- **Figure regression: Thalmus is INVISIBLE in the room.** Confirmed twice
  (byte-identical screenshots). The fill writes outside the tile's true
  footprint and overwrites figure pixels drawn by earlier cells in the
  per-cell loop (terrain fill and figure draw are interleaved per cell).

## Why the look is not clean (blocker)

The decoder scatters a tile's bytes via `row[Y] + col[(X-64)/2 + lowNibble]`,
and the low nibble comes from the **stream data** — it is not derivable from
(X, Y) alone. The v5 fill assumes low nibbles 0..7, which do not match the
stream's actual low nibbles, so it writes to the wrong columns (the dashes)
and onto neighbouring figure pixels (Thalmus gone). Earlier iterations proved
the same point the other way: a contiguous 32-byte tile fill (v1) only lands
on ~half the tiles (scattered squares, black interior).

**Correct next step (not built): hook $E358's handler dispatch ($E40C) and
write flat bytes to the already-computed a5 per line, letting $E358 compute
the positions and advance the stream.** That is the only approach that
replicates the decoder's addressing exactly. It needs the handler's
stream-advance behaviour (the $DF58/$434C0 dispatch tables and the $E47C
AND/OR copy fragment are mapped in the report).

## Limits (honest)

- The per-level colours do not render distinctly; the room is dark blue
  dashes on black. Do not judge the flat *palette* from this ROM.
- Thalmus (and, by the same mechanism, any figure sharing buffer positions
  with a later cell's fill) is invisible. Do not judge character-on-flat
  readability from this ROM.
- The player animation rate (frames per cell-crossing, subcell steps per
  crossing) was **not measured**: the probe state has the leader standing
  still (117,113) in a cutscene, and the subcell movement itself is the
  separate next step, not in this ROM. The phase counter runs at 9
  frames/phase (vs ~21.5 originally), so a cell commit gated to the 3→0 wrap
  would be ~36 frames/cell — but that is arithmetic, not a measured walk.
- World-view pixel-identity was **not screenshot-verified** in this session
  (no world-view save state); it rests on the $FF00AE gate, which tail-calls
  the original $E358 for mode 1. Menu/teleport were not live-tested either.
- Cold boot verified (600 frames, exit 0, checksums OK). HUD, border,
  minimap, and controller overlay are unchanged.

## Build

`python3 patches/flat-zoom/build.py` — assembles `source.s` with vasm,
builds from the original ROM (MD5 asserted), fixes checksums with
`tools/checksum.py fix-all`, writes `rop-flat-zoom.rom` (also copied to
`~/workspace/rop-flat-zoom.rom`), generates `rop-flat-zoom.ips` (259 bytes,
10 records; round-trip verified: original + IPS == patched ROM exactly) and
`changed-bytes.txt`. Rebuilding reproduces the ROM byte-identically
(MD5 `d9139010ac84119d6dc0feba5086b8a5`).

## Files

- `source.s` — flat stubs + `flat_fill8` (vasm mot syntax, 190-byte blob)
- `build.py` — reproducible builder (assembles, patches, checksums, IPS)
- `rop-flat-zoom.rom` — patched ROM (git-ignored deliverable)
- `rop-flat-zoom.ips` — IPS patch (apply to a clean original ROM)
- `changed-bytes.txt` — original → patched diff (205 bytes changed:
  header checksum, 3 call sites, runtime checksum, 190-byte blob)
- `flat.bin`, `flat.lst` — assembled blob + listing
