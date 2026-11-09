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

## 6. Runtime sprite behaviour (2026-11-09, session #3 — BlastEm debugger)

This closes the item §4 left open. Method as in
docs/graphics.md §5 (`vr`/`vs` at breakpoints, VBlank
stepping); static mechanism from the disassembly + Ghidra map.

### 6a. There is no RAM sprite buffer and no SAT DMA

Sprites are written **directly to VRAM, one entry at a time**,
by `$11BD8(index, X, Y, width_code, height_code, link,
pattern_word)`:

- VRAM address = `$FF8644 + index*8`, set via $DC60; four
  words follow via $D9EE: Y word (arg), size/link word
  composed as `(height_code << 8) | (width_code << 10) |
  link` (link arg −1 → 0), pattern word (arg), X word (arg)
  — the standard SAT entry layout, in SAT order.
- `$FF8644` is the **current SAT base variable**: written
  $4400 by the intro screen setups (0x1491A, 0x15D4A,
  0x17C9E, 0x18C1C, and at 0x12550) and $2400 by the game
  setup (0x12CB2) — matching the R5 bases captured live
  (docs/graphics.md §5a states 5–8).
- Siblings: `$11B76` clears the entry at the SAT base
  (4 zero words — observed live as the $DC60($4400) call
  from 0x11B84 at intro start); `$11C4A` rewrites only an
  entry's size/link word (at base + index*8 + 2).
- Callers of $11BD8 (Ghidra map + sweep): $13D84 (55 call
  sites — a large unrolled scene builder), $17B88 (23),
  $15012 (12, intro driver), $138A8 (9, the HUD/status
  renderer), $1664E (8), $17A40 (4), $1E4E6 (2). Sprite
  indices are owned per draw routine — e.g. the HUD's first
  $11BD8 call uses index $43 = 67, which is exactly the
  tail sprite (67) of the main-loop list in §6b.

Consequences: SAT entries **persist in VRAM** across frames;
nothing re-uploads them per frame; a screen's sprite list is
exactly what its draw routines last wrote (plus whatever
earlier screens left at untouched indices — the main-loop
list's sparse indices 0/22–25/67 are this, read through the
link chain).

### 6b. Observed sprite lists (VDP `vs`, live)

- **Boot animation** (SAT $DC00): 2 sprites — both 32×8,
  palette 0, priority 1, patterns $4020/$40A0, linked
  0→1→end; X≈247/246, Y 204→208 across sampled iterations
  (the pair drifts downward as $4E6 animates).
- **$14FB6 entry** (SAT $2400): a single null entry
  (index 0, X=Y=−128 off-screen, link 0 = end).
- **Intro screen A** (SAT $4400, +600 VBlanks): 30 sprites —
  a 3×3 grid of 32×32 (indices 0–8, X 224–319, Y 50–145,
  patterns stepping 16 tiles) plus 21 sprites of 32×24 in
  three rows (indices 16–36, palette 2, Y 61/85/109).
- **Intro screen B** (SAT $4400, +1800 VBlanks): 45 sprites
  (indices 0–44, all palette 2) — two large sprites (32×32
  and 24×32 at screen pos ≈181–218, 25–65) and a 7×5 grid
  of 16×32 cells (X 205–317, Y 9–201, patterns stepping
  8 tiles): a big illustration assembled from hardware
  sprites, next to plane-drawn content.
- **Main loop / attract start scene** (SAT $2400, stable
  from +600 to +2400 VBlanks, list unchanged): entry 0 is a
  hidden root (X=Y=−128) linking to 22 → four 32×32
  palette-1 sprites (22–25, a 2×2 block at 246–310,
  152–216, patterns $D940/$DF40) → 67, a 16×8 palette-2
  sprite (the HUD's, per §6a) → end. At the exact $D28E
  entry only entry 0 (pattern $2680, link 0) is present;
  the 22–25 block appears within the first 600 VBlanks.
  The attract scene is **static** — no demo play occurs;
  the game waits for input at the start location.

### 6c. Cross-check against §1–§4

- The runtime lists corroborate the static claim that the
  $B86AE 48×48 records are **not** hardware-sprite units:
  no observed SAT entry uses a 48×48 arrangement or a
  $B86AE pattern layout; observed sprites are 8–32 px
  cells composed into pictures by $11BD8 calls, while the
  portraits remain plane/tile uploads via $11AE4.
- Pattern words in the lists index the same VRAM tile
  space the $1383C/$11A7C uploads fill (e.g. screen B's
  grid steps by exactly one 16×32 sprite = 8 tiles per
  cell) — the sprite and plane paths share uploaded tiles,
  as §1's upload table implies.
- §4's "VRAM sprite base $D800 boot / $DC00 in the $A14
  set" is confirmed live, and the game/intro bases
  ($2400/$4400) are now pinned by both the register capture
  and the $FF8644 writes.
