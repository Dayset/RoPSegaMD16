# tall-objects-diag — solid-white tall top

## Diagnosis (probe-verified, 2026-11-13)

Dayset tested `rop-tall-objects.rom` in the Academy (location 156,
chunk 233) and saw NO tall objects, though the room HAS walls/trees
(286 impassable cells). The room is not the problem.

A diagnostic probe (hook at `.fill` $FD4DC + `map_chunk_pos` entry,
BlastEm, slot_0 state) logged one complete render (100 fill calls):

- `.blocked` **IS** taken: **43 tall calls per render**. The $1C892
  impassable rule marks the Academy's walls/trees, and the tall
  patterns ARE written.
- The tall patterns **survive** in the final buffer: **129 tall-top +
  31 tall-base tiles** (simulation replaying the 100 fills in draw
  order into the 36x23 buffer). The top row survives 100% (129/129
  writes); the dark base only 24% (31/129) — the rest is overwritten
  by later-drawn cells — and the survivors are scattered single
  tiles, not a coherent band.
- The tall objects were invisible because the tall **TOP blended with
  the land**: its average luminance (idx 11 lum 182 / idx 9 lum 109
  -> 145.5) sits squarely inside land's range (127-173), so the 129
  surviving bright tiles read as ground, not as objects. The dark
  base (idx 7/0, avg 36) is the only distinctive part, but it is
  mostly overwritten and scattered.

So: the rule works, the branch works, the patterns are written and
survive — but the top is the wrong brightness to read as an object.

## Fix

Make the tall TOP solid white (palette idx 15): the brightest index
in both palettes (day pal 10: lum 255; night pal 19: lum 117) and an
index land/water never use. The tall object becomes an unmistakable
solid highlight. The dark base is unchanged.

Change (on top of `rop-tall-objects.rom`):

- `noise_tbl[8]` $FD5D6: `$BBBBBBBB` -> `$FFFFFFFF` (tall top-even)
- `noise_tbl[9]` $FD5DA: `$99999999` -> `$FFFFFFFF` (tall top-odd)

Only these two longwords change (plus the header checksum). The
runtime checksum is unchanged — $FD5D6 is past the self-test's range
end ($FD07C), so the self-test does not cover it.

## Build

```
python3 build.py
```

Reads `../rop-tall-objects.rom` (MD5 `9846c168f559bb8acf4a14aca46623b7`),
applies the two-longword patch, fixes the header checksum, writes
`../rop-tall-objects-diag.rom`, and emits `changed-bytes.txt` +
`tall-objects-diag.ips` (round-trip verified).

## ROM

`rop-tall-objects-diag.rom` — MD5 `9ea6aa19c407bca7d8f5df4d2e480827`,
header checksum `$FE06`. 10 bytes differ from the base (8 table +
2 header checksum). Original ROM untouched
(MD5 `30c18fdbe2183f64702ae9f1a45d63f9`).

## What was NOT verified

Dayset is the tester. No playtest verification of this ROM: whether
the white tall objects read clearly on his screen (and at night) is
for him to judge. The probe that diagnosed the problem ran on the
tall-objects base, not on this fix ROM.
