# Tiles, sprites, palettes (issue #016)

Written 2026-11-09 (agent session) from `disasm/graphics/README.md`
+ `inventory.md` (#005) and `tools/render_tiles.py`. **Read the
correction first — it changes what this issue can claim.**

## 0. Correction to the issue's premise — verified in #005

Issue #016 asks for `0x060000–0x093FFF` "decoded as 4-bpp tiles".
#005 already disproved that: raw ROM in that range renders as
**noise in every layout** (packed, planar, planar-sequential). The
range is the start of the `$96120` **compressed streams**, not raw
tiles, and `disasm/map.md`'s old "tile graphics" label there is
wrong. The real tiles live compressed in two `$DD5C` tables (below)
and only exist as tiles **after decompression**. This doc therefore
documents the decoded reality instead of the stale premise; the
acceptance item "tile data confirmed as tiles (not misread
code/text)" is met — by showing where the tiles actually are.

## 1. Tile sources — verified (#005)

| Table | Records | Record content | ROM sources |
|---|---|---|---|
| `$96120` | 62 | tilesets, tilemaps, 4 text streams (see inventory) | `0x09638C–0x0B86AE` |
| `$B86AE` | 90 | each `[32-byte palette][36 tiles]` = 48×48 px sprite/portrait | `0x0B8A32–~0x0CC761` |

- Decompressed tile bytes are **packed: 2 pixels/byte, high nibble
  first**. Proof: `$B86AE` rec 0 renders a coherent face only in
  packed layout; `$96120` rec 0 renders the ASCII font + "MORE";
  cross-checked against BlastEm's VRAM debugger; byte statistics
  62.6% hi==lo nibble in rec 0 (solid 2-px runs) vs ~6% expected
  for bitplane data.
- Upload: `$1383C → $11A7C → $DA04` DMA and `$11AE4 → $11B2E →
  $DA04` DMA, both verbatim — no conversion step found (the paradox,
  `docs/graphics.md` §4).

## 2. First rendered tilesets — DONE in #005 (acceptance evidence)

Already rendered to PNG under `disasm/graphics/`:
`font_rec00_pal10.png` (full ASCII font + "MORE"), `terrain_rec06_pal1.png`
(rec 6 terrain), `logo_rec12_pal1.png` (rec 12), and portraits
`portrait_b86ae_rec00/01/05.png`. Render any record with
`tools/render_tiles.py record|sprite|raw` (modes + `--layout`
comparisons; planar layouts render as bars/noise — kept as the
negative control).

## 3. Palettes — verified (#005)

- Format: Mega Drive 9-bit BGR word `0BBB0GGG0RRR0`; RGB per channel
  = 3-bit value × 255/7.
- Master table: ROM `0x0CC9D8`, **31 palettes × 16 colours**.
  Loader `$11082(table_ptr, slot)` → CRAM via `$D9E2`/`$D9EE`.
  Title screen (`$11E06`) loads pal 10 → slot 0, pal 0 → slot 1.
- `$B86AE` records embed their **own** palette (first 32 bytes),
  loaded by `$11AE4` via `$11082($FF1EC0, slot)`.
- Notable table entries (from `disasm/graphics/inventory.md`):
  pal 0 = test ramp, pal 8 = all black (fade), pal 9/20 = white
  (fade), pals 13–16 = logo-screen live CRAM.

## 4. Sprite format — partially verified

- The `$B86AE` records ARE the sprite/portrait unit: 36 tiles in a
  6×6 arrangement = 48×48 px, one embedded palette, loaded by
  `$11AE4(record, vram_tile, palette_slot)`.
- What is **not** yet documented: the VDP sprite attribute table
  entries at runtime (VRAM sprite base `$D800` boot / `$DC00` in
  the `$A14` set — `docs/graphics.md` §2), i.e. how these 48×48
  blocks are linked/sized as hardware sprites vs plane tiles.
  That needs a live VRAM/sprite-table trace — **blocked in this
  VM (no ROM/emulator)** and recorded as the remaining #016 item.

## 5. Extension notes for tools/render_tiles.py

- The renderer's docstring already carries the packed-layout proof
  and the paradox warning — keep it; exporters (#024) must import
  `decode_tile_packed`, not re-derive planar decoding.
- Suggested next renderer work (owner's machine, needs ROM):
  batch-render all 62 + 90 records to a contact sheet for the
  tribute art pass; dump all 31 palettes as a single PNG strip so
  `tribute/assets/` can pin palette indices visually.
