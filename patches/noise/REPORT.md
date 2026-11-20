# Grey-noise ROM — report

Base: `rop-dither.rom` (MD5 `09d74baa339314b40e02344545f67f66`) — flat
checkerboard only on mode 2, feet fix, subcell override.
Deliverable: `rop-noise.rom`, MD5 `b35a634181a99271af6e9c829beb7339`
(header `0x7BFB`, runtime `0xA24C62E7`, both verify via
`checksum.py verify-all`). 407 bytes differ from the base, all inside
the `$FD400` blob or the two checksums. IPS round-trip verified
(base + `noise.ips` == the ROM, byte-identical).

Worktree: `~/workspace/rop-work/noise/`
Patch: `patches/noise/` (`source.s`, `build.py`, `README.md`,
`changed-bytes.txt`, `noise.ips`).
Scratch/evidence: `.scratch-noise/` (`palettes.txt`, `chunk_types.py`,
`check_fig.py`, `hash_test.py`, `hash_test2.py`, `verify.py`,
`noise.bin`, `noise.lst`).

One fix only: the grey-noise fill (+ the darker impassable objects,
Dayset's follow-up). Flat gate (mode 2 only), feet fix, subcell
override, and the big world are byte-identical to the base. The
original ROM is untouched (MD5 `30c18fdbe2183f64702ae9f1a45d63f9`,
re-verified).

## The noise design

The flat fill is just writes — 48 longwords per cell (6 tiles × 8
longwords, tile-major buffer `$FF1EC0`: 36×23 tiles, 32 bytes per
tile). Varying the value per write costs almost nothing extra: same
48 writes, just different values, still far cheaper than the `$E358`
decode (which the flat fill skips entirely).

**Shades.** The room render uses CRAM slot 0 (pal 10 day / pal 19
night, cross-faded). The grey ladder is monotonic in BOTH palettes,
so the light→dark ordering holds day and night:

| Palette idx | Day (pal 10) | Night (pal 19) |
|---|---|---|
| 11 | (182,182,182) lum 182 | (72,36,145) lum 59 |
| 9  | (109,109,109) lum 109 | (0,0,36) lum ~4 |
| 7  | (72,72,72) lum 72 | black (0,0,0) |
| 0  | black | black |

Three categories (tested in order, per cell):

| Category | Grey indices | Day avg luminance | Night avg luminance |
|---|---|---|---|
| Walkable land | 11 / 9 | ~145 | ~31 |
| Water | 9 / 7 | ~90 | ~2 |
| Impassable (walls/trees) | 7 / 0 | ~36 | 0 |

Ratios (day): land:water ≈ 1.6×, land:impassable ≈ 4×,
water:impassable ≈ 2.5×. The exact darkening factor does not matter
(Dayset's correction) — impassable must only read clearly darker
than the walkable ground, so he can navigate by sight instead of
by memory. At night all greys go very dark (the same weak distinction
as the original flat fill at night: land idx 3 lum 29, water idx 1
lum 4); the day distinction is the one that carries.

**Noise pattern.** 4 precomputed longword patterns per category
(all-A, 6A+2B with B at pixel positions 2 and 6, alternating A/B,
all-B), 12 longwords = 48 bytes in `noise_tbl` at `$FD59A`.
Selected per cell by a deterministic hash of (tile_col, tile_row):
`h = ((col*0x9E37 + row*0x7F4A) >> 8) & 3`. Even rows use
pattern[h], odd rows pattern[(h+1)&3], so the shade varies per cell
AND per line. Deterministic per cell — no flicker. The hash was
chosen over five candidates for scatter: uniform distribution
(205/209/205/209 over the 36×23 room grid), no all-same rows or
columns, 14% adjacent-equal (vs 75% for the naive `((c*31+r*17)>>2)&3`
and 22% for the first candidate).

The 12 pattern longwords:

| Category | P0 (all A) | P1 (6A+2B) | P2 (alt) | P3 (all B) |
|---|---|---|---|---|
| Land (11/9) | `$BBBBBBBB` | `$BB9BBB9B` | `$B9B9B9B9` | `$99999999` |
| Water (9/7) | `$99999999` | `$99799979` | `$97979797` | `$77777777` |
| Impassable (7/0) | `$77777777` | `$77077707` | `$70707070` | `$00000000` |

## The impassable rule

The terrain type comes from the `$5EDC4` props word at `-$6(a6)`
(bits 10–15), read in `flat_top` before the fill. The rule is the
`$1C892` terrain jump table (`docs/logic.md` §3.7, 35 entries, types
0–34) — the move-path gate (`move_cost_calc` returning 0 = blocked):

- type ≥ 32 → blocked (types 30–34 are mode-7-only; types 35–63 are
  out of the jump table's range and set the blocked flag);
- type < 32 → water mask `$00E08C0D` (types 0,2,3,10,11,15,21,22,23),
  then blocked-low mask `$E0017010` (types 4,12,13,14,16,29,30,31);
- else walkable land.

Type 15 is in both the water set and the blocked set; water is
tested first, so it draws as water. The masks are computed from the
type sets in `build.py` and asserted against the assembled blob —
not trusted from hand arithmetic.

This is deliberately NOT the `$02DC0C` gate (`map_walkable_test`,
walkable iff type ∈ {5,9,18} or tile == `$24`): that is the
statue-summon gate with exactly one caller (`$02E508`), never on
the move path, and it would wrongly mark Grass (type 1) as a wall.

**Validation on chunk 233 (location 156, the Buc cutscene room):**
1024 cells, 15 terrain types. Floor is type 9 (Road, 502 cells).
Impassable by the `$1C892` rule: 286 cells — Forest type 4 ×184,
type 31 ×84, type 32 ×6, type 33 ×12. The `$02DC0C` rule would mark
475 cells (including Grass type 1 ×74, type 7 ×53, Swamp ×17,
type 19 ×28) — over-marking walkable ground as walls. Water:
type 3 ×1 cell. Tile `$24` cells: 0 in this chunk.

## The blob

Rebuilt `$FD400` blob, 458 bytes (`$FD400`–`$FD5C9`), 54 bytes free
to `$FD600`. Entry points unchanged: flat_skip `$FD400`,
flat_top `$FD412`, so the existing call sites (`jsr $FD400` from
`$01BC1A`/`$01BC3C`, `jsr $FD412` from `$01BC84`) still land.
`noise_tbl` at `$FD59A`.

Changes vs the dither blob:
- Removed the four `fig_*` stubs (~80 bytes) — verified dead code:
  only `jsr $FD400` / `jsr $FD412` target the `$FD400` blob; the
  figure call sites point at the `$FD600` feet-fix stubs
  (`$FD600`, `$FD64C`, `$FD698`, `$FD6E4`) and `fig_replay` at
  `$FD730`, plus the subcell hook (`jsr $FD800` from `$023202`).
- Removed the 64-byte `water_tbl` (replaced by the two bitmask
  immediates).
- Added: tile_row/tile_col/base-offset computation (moved before the
  terrain test, since the hash needs them), the cell hash
  (2× `mulu.w`, `add.l`, `lsr.l #8`, `andi.w #3`), the terrain
  test (range check + 2× `btst`), the pattern loads
  (`lea noise_tbl` + indexed `(a1,dX.w)` loads into d4/d0),
  and the 48-byte noise table.
- The fill itself is byte-for-byte the dither fill's structure
  (6 blocks × 8 consecutive longwords, offsets +0/+32/+64 and
  +1152/+1184/+1216, bounds checks `tc==35`, `tc>=34`, `tr==22`),
  with d4/d0 now loaded from the noise table instead of the
  checkerboard immediates. (An earlier draft used a scanline
  structure with `adda.w #128` between lines — wrong: the buffer is
  tile-major, 8 consecutive longwords per tile. Caught by the blob
  size, 730 bytes vs the 512-byte region, and corrected before
  building.)

The assembled blob was disassembled (capstone) and read
instruction-by-instruction: gate, bounds checks, movem, tile/base,
hash (`mulu #$9E37` / `mulu #$7F4A` / `add.l` / `lsr.l #8` /
`andi #3`), terrain type (`-$6(a6)`, `lsr #8`, `lsr #2`), water
mask `$00E08C0D` and blocked mask `$E0017010` (`btst`), category
bases 0/16/32, pattern loads, fill — all as intended.

## Cost

Same as the solid/checkerboard fill: 48 longword writes per cell.
The only added cost is the per-cell setup before the fill: the hash
(2× `mulu.w` ≈ 80 cycles), the terrain test (range check + up to
2× `btst` ≈ 20 cycles), and the two indexed table loads (≈ 30
cycles) — roughly 130 cycles per cell, ~13,000 cycles per 100-cell
render, ≈ 0.1 frames at 60 Hz. Negligible next to the ~8 frames
per render the flat fill already costs, and still far cheaper than
the `$E358` decode it replaces (the original decode is ~16 frames
per render in the room). No decoder calls, no per-frame randomness.

## What was NOT verified

No live tests (Dayset's rule — he is the tester). Not verified:
whether the noise reads as texture rather than speckle on screen;
whether the impassable grey is clearly distinguishable from the
walkable ground in real play, day and night; the look in other
rooms (multi-level, water); menu/teleport; the 128-entry
figure-list cap. The night distinction is weak by construction
(see the shades table) — if the night room is unreadable, that is
a palette problem, not a fill problem.
