# Highlighted tall objects — report

Base: `rop-noise.rom` (MD5 `b35a634181a99271af6e9c829beb7339`) — grey-noise
fill, flat gate (mode 2 only), feet fix, subcell override.
Deliverable: `rop-tall-objects.rom`, MD5 `9846c168f559bb8acf4a14aca46623b7`
(header `0xA8B2`, runtime `0xA24C62E7`, both verify via
`checksum.py verify-all`, exit 0). 297 bytes differ from the base, all
inside the `$FD400` blob or the header checksum. IPS round-trip verified
(base + `tall-objects.ips` == the ROM, byte-identical).

Worktree: `~/workspace/rop-work/tall-objects/`
Patch: `patches/tall-objects/` (`source.s`, `build.py`, `README.md`,
`changed-bytes.txt`, `tall-objects.ips`).
Scratch/evidence: `.scratch-tall-objects/` (`tall.bin`, `tall.lst`).

One fix only: grey shading/texture on the tall objects (walls/trees —
the solid impassable objects), so they read as tall and stand out
clearly. Dayset's direction: "leave the subcell as it is add gray tall
objects shading/texture", then "textures are the missing piece now, at
least some solid should be highlighted." The subcell is untouched.
Flat gate (mode 2 only), feet fix, subcell override, and the big world
are byte-identical to the base. The original ROM is untouched (MD5
`30c18fdbe2183f64702ae9f1a45d63f9`, re-verified).

## The tall design

The noise ROM already made impassable cells darker (grey ladder: land
idx 11/9 avg lum ~145, water 9/7 ~90, impassable 7/0 ~36), but they
were still flat — a flat dark grey fill. This patch gives them
shading/texture in grey:

| Tile row | Rows alternate | Palette idx | Day luminance |
|---|---|---|---|
| Top (lit top edge, the highlight) | idx 11 / idx 9 | 11 / 9 | 182 / 109 |
| Bottom (shadowed base) | idx 7 / idx 0 | 7 / 0 | 72 / 0 |

Whole object avg luminance ~91 (day), vs land ~145 and water ~90.
The object stays clearly darker than land on average (reads as a
solid, not ground), while its bright top edge (idx 11, the brightest
grey in the ladder) highlights it so it stands out clearly. The
alternating rows are the texture (stone courses); the bright-top /
dark-base gradient is the height cue (reads as tall, lit from above).
The gradient repeats per cell (each cell is bright at its top and dark
at its base), so a wall reads as stacked courses — the fill only ever
sees one cell at a time, so a per-object gradient is not possible.
At night (pal 19) the greys go very dark, as in the noise ROM — the
day distinction is the one that carries.

## The impassable rule (unchanged from the noise ROM)

The terrain type comes from the `$5EDC4` props word at `-$6(a6)`
(bits 10–15), read in `flat_top` before the fill. The rule is the
`$1C892` terrain jump table — the move-path gate (`move_cost_calc`
returning 0 = blocked):

- type >= 32 -> blocked (types 30–34 are mode-7-only; types 35–63 are
  out of the jump table's range and set the blocked flag);
- type < 32 -> water mask `$00E08C0D` (types 0,2,3,10,11,15,21,22,23),
  then blocked-low mask `$E0017010` (types 4,12,13,14,16,29,30,31);
- else walkable land.

Type 15 is in both the water set and the blocked set; water is
tested first, so it draws as water. This is deliberately NOT the
`$02DC0C` gate (`map_walkable_test`, walkable iff type in {5,9,18}
or tile == `$24`): that is the statue-summon gate with exactly one
caller (`$02E508`), never on the move path, and it would wrongly
mark Grass (type 1) as a wall. Validated on chunk 233 (location 156,
the Buc cutscene room): 286 impassable cells (Forest 4 x184,
31 x84, 32 x6, 33 x12).

## Implementation

The impassable category in the table is now 4 FIXED tall patterns
(top-even idx 11, top-odd idx 9, base-even idx 7, base-odd idx 0),
not 4 hash variants. Land and water keep their 4 hash patterns each.

- `.blocked` loads all 4 tall patterns directly (`lea noise_tbl,a1`;
  `move.l 32(a1),d4` / `36(a1),d0` / `40(a1),d1` / `44(a1),d2`) and
  jumps to `.fill`, skipping the hash-based `.patterns` load.
  d4/d0 = top pair (lit), d1/d2 = base pair (shadow).
- `.patterns` (land/water) loads d4/d0 from the hash as before, then
  copies them into d1/d2 (`move.l d4,d1` / `move.l d0,d2`), so the
  base pair equals the top pair — flat ground/water, no gradient.
- The fill writes the top 3 blocks with d4/d0, then swaps d1/d2 into
  d4/d0 (`move.l d1,d4` / `move.l d2,d0`, placed after the tr==22
  check, before the first bottom block) and writes the bottom 3
  blocks with the base pair.

The fill is still 48 straight-line longword writes per cell, the
same count as the solid/checkerboard/noise fill. Added cost is the
tall load for impassable cells only (lea + 4 moves + bra) plus 2
moves in `.patterns` and 2 in the fill — roughly 30 cycles per cell,
~0.1 frames per 100-cell render at most. Negligible next to the ~8
frames per render the flat fill already costs, and still far cheaper
than the `$E358` decode it replaces.

## The blob

Rebuilt `$FD400` blob, 486 bytes (`$FD400`–`$FD5E5`), 26 bytes free
to `$FD600`. Entry points unchanged: flat_skip `$FD400`,
flat_top `$FD412`, so the existing call sites (`jsr $FD400` from
`$01BC1A`/`$01BC3C`, `jsr $FD412` from `$01BC84`) still land.
Table at `$FD5B6` (land + water + tall, 48 bytes, last in the blob).

The assembled blob was disassembled (capstone) and read
instruction-by-instruction: gate, bounds checks, movem, tile/base,
hash (`mulu #$9E37` / `mulu #$7F4A` / `add.l` / `lsr.l #8` /
`andi #3`), terrain type (`-$6(a6)`, `lsr #8`, `lsr #2`), water
mask `$00E08C0D` and blocked mask `$E0017010` (`btst`), the tall
load (`lea $FD5B6(pc),a1`; `move.l $20/$24/$28/$2C(a1),d4/d0/d1/d2`;
`bra .fill`), the hash pattern loads plus the base-pair copy
(`move.l d4,d1` / `move.l d0,d2`), the fill with the base-pair swap
(`move.l d1,d4` / `move.l d2,d0`) after the tr==22 check, and the
table values — all as intended. The `lea noise_tbl` assembled as
PC-relative (`lea $FD5B6(pc),a1`); the fixed offsets 32/36/40/44
from the table base land on the tall row, confirmed in the
disassembly and by the table-content assertion in `build.py`.

d1/d2 hold the base pair. They are scratch (not in the movem list
`d4-d7/a0-a1/a3`), consistent with the noise blob, which already
clobbered d1 (terrain type / category base), d2 (hash), and d3 (base
offset) — the caller (`map_chunk_pos`) does not rely on d0–d3 across
the `jsr`.

## Cost

Same as the noise fill: 48 longword writes per cell, plus ~30 cycles
of per-cell setup for the tall load / base-pair copy / swap.
Negligible.

## What was NOT verified

No live tests (Dayset's rule — he is the tester). Not verified:
whether the tall objects read as tall and clearly highlighted on
screen (bright top edge vs dark base, the course texture); whether
the bright top edge blends with the land (its top rows are as bright
as land's brightest noise — the regular striping vs the random noise
is the distinguishing feature, but only his eye can judge it); the
look in other rooms (multi-level, water); menu/teleport; the
128-entry figure-list cap. The night distinction is weak by
construction (see the shades table) — if the night room is
unreadable, that is a palette problem, not a fill problem.
