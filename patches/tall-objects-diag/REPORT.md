# Tall-objects diagnosis + fix — REPORT

Date: 2026-11-13. Base ROM: `rop-tall-objects.rom`
(MD5 `9846c168f559bb8acf4a14aca46623b7`).
Worktree: `~/workspace/rop-work/tall-objects-diag/`.

## Dayset's answer (the room is not the problem)

He tested the Academy — location 156, chunk 233 — which HAS objects
(walls/trees): 286 impassable cells (Forest x184, 31 x84, 32 x6,
33 x12). So "the room has no tall objects in view" is ruled out.
The diagnosis focused on (a) whether the rule marks those cells,
(b) whether `.blocked` is taken and the tall patterns are written,
(c) whether the tall patterns blend with the land.

## Diagnosis — probe-verified

### Method

A diagnostic probe ROM (`tall-probe.rom`, MD5
`93c1c55a4a4c9ac6fdd891a1b237fb5a`) built on the tall-objects ROM:
- Hook A: `map_chunk_pos` entry $01BA4E -> `probe_render`
  (increments RENDER_ID, resets LOGCOUNT on the first full render
  after state load so the log holds one complete render).
- Hook B: `.fill` $FD4DC -> `probe_fill` (logs one 16-byte record
  per fill call: render_id, tc, tr, tall_flag, d4, d0).
- Log at $FFDF80, 100 records, `log_full` at $FD9AC (debugger
  breakpoint). Ran in BlastEm (restored 0.6.3.4) with the slot_0
  state (Buc cutscene room, loc 156, mode 2).

Probe bug found and fixed during the run: I read the low words of
d5/d6 at `12(a7)`/`8(a7)`, but the 68000 is big-endian — `move.l
d5,-(a7)` stores the high word at the lower address, so the low
word (tc/tr) is at offset+2 (`14(a7)`/`10(a7)`). The first run
logged tc=tr=0 for all records; the d4/d0 longword reads were
correct, which is how the bug was spotted.

### Results (one complete render, 100 fill calls, mode 2)

- **(a) The rule marks the cells.** `.blocked` is taken **43 times
  per render** (43 tall calls, 57 land/water). The $1C892
  impassable rule works on the Academy's walls/trees.
- **(b) The tall patterns ARE written.** `.blocked` loads the tall
  top pair from `noise_tbl[8]/[9]` ($BBBBBBBB/$99999999) and the
  base pair from `noise_tbl[10]/[11]` ($77777777/$00000000), and
  the fill writes them. The `noise_tbl` values in the shipped ROM
  were verified byte-for-byte against the design (land
  $BBBBBBBB/$BB9BBB9B/$B9B9B9B9/$99999999, water
  $99999999/$99799979/$97979797/$77777777, tall
  $BBBBBBBB/$99999999/$77777777/$00000000). The `.blocked` load
  and the fill swap are correct as shipped.
- **(c) The tall patterns blend with the land — this is the cause.**
  A Python simulation replaying the 100 logged fills in draw order
  into the 36x23 buffer shows the final buffer holds **129
  tall-top + 31 tall-base tiles** (216 land, 0 water, 452
  unwritten). So the patterns survive — but:
  - The tall TOP (the bulk, 129 tiles) has average luminance
    (182+109)/2 = **145.5**, squarely inside land's range
    (land tile averages 127-173, overall ~150). It is the same
    brightness as the ground, so the 129 surviving bright tiles
    read as ground texture, not as objects. Its stripe pattern
    (even rows all idx 11, odd rows all idx 9) is a combination
    land never produces exactly, but it is too subtle at phone
    scale to read as an object.
  - The tall BASE (the only distinctive part, idx 7/0, avg 36)
    survives only **24%** (31/129 writes). The rest is
    overwritten by later-drawn cells (each cell writes a 3x2
    block and blocks overlap; the bottom row is the one the next
    row down overwrites). The 31 survivors are scattered single
    tiles, not a coherent dark band, so they read as speckles,
    not as a "shadow base."
  - The top row survives 100% (129/129 writes) — the overwrite
    hits the dark base, not the bright top. The original
    "tall dark base is overwritten" hypothesis is half right:
    the base IS mostly overwritten, but the top is fully there
    and it is the top that is invisible (because it blends).

In short: the rule works, the branch works, the patterns are
written and survive — but the top is the wrong brightness to read
as an object, and the base is too overwritten/scattered to carry
the "tall" cue on its own.

## Fix

Make the tall TOP solid white (palette idx 15). It is the
brightest index in both palettes (day pal 10: lum 255; night
pal 19: lum 117) and an index land/water never use, so the tall
object becomes an unmistakable solid highlight. The dark base is
unchanged. This is a two-longword table change on top of the
tall-objects ROM — no draw-order rework, no post-pass, no change
to the flat gate, feet fix, or subcell.

- `noise_tbl[8]` $FD5D6: `$BBBBBBBB` -> `$FFFFFFFF`
- `noise_tbl[9]` $FD5DA: `$99999999` -> `$FFFFFFFF`

## Deliverable

- ROM: `~/workspace/rop-work/tall-objects-diag/rop-tall-objects-diag.rom`
  - MD5 `9ea6aa19c407bca7d8f5df4d2e480827`, header checksum `$FE06`.
  - 10 bytes differ from the base (8 table + 2 header checksum).
  - Runtime checksum unchanged (`$A24C62E7`, verified) — $FD5D6 is
    past the self-test's range end ($FD07C), so the self-test does
    not cover the change and the ROM boots. `checksum.py
    verify-all` passes (header + runtime OK).
- Patch: `~/workspace/rop-work/tall-objects-diag/patches/tall-objects-diag/`
  - `source.s` (the two changed longwords, documented),
    `build.py`, `README.md`, `changed-bytes.txt`,
    `tall-objects-diag.ips` (28 bytes, IPS round-trip verified:
    base + IPS == fixed ROM).
- Probe artifacts (diagnosis only, not the deliverable):
  `probe.s`, `build_probe.py`, `run_tall_probe.py`,
  `simulate.py`, `.scratch-tall-objects-diag/tall-probe.json`
  (100 records), `tall-probe.rom`.

## What was NOT verified

- No playtest verification of the fix ROM. Dayset is the tester:
  whether the white tall objects read clearly on his screen (and
  at night) is for him to judge. The probe ran on the
  tall-objects base, not on this fix ROM.
- The dark base is still only ~24% surviving and scattered; if the
  white top alone does not read as "tall" (vs just "highlighted"),
  the next step would be a tall post-pass (redraw the base after
  all terrain, like the feet fix) — not attempted here, one fix
  only.
- The original ROM is untouched (MD5
  `30c18fdbe2183f64702ae9f1a45d63f9`).
