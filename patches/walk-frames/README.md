# walk-frames — double Buc's cutscene walk animation

Base: `rop-cutscene-loop.rom` (MD5 `79bccdcd927707802332f64f38faa641`) —
flat only on mode 2, feet fix, cutscene loop-walk (Buc walks the loop
in all four directions).

## What it does (one fix only)

Doubles Buc's walk animation in the cutscene (including the loop-walk),
exactly as Dayset directed:

1. **Repeat the existing frames — no new art.** The loop driver now
   steps Buc every OTHER `sys_event_run` call: one cell per **8 ticks**
   instead of 4. The walk template is indexed by `grid+$A`, a 4-phase
   counter (0–3, one phase per tick). Over an 8-tick cell the counter
   cycles TWICE, so each of the 4 existing walk frames is shown twice
   per cell (8 frames per cell instead of 4).
2. **Smaller Y shift.** A new `hero_track` hook draws Buc half a cell
   toward the next cell during the second half of the cell
   (`walk_half==1`, ticks 4–7). The half-step is half the cell step
   vector (N +7,−4; E +7,+4; S −7,+4; W −7,−4). So for a south step
   Buc's drawn Y goes **8, 12, 16, 20, 24** (step 4) instead of
   8, 16, 24 (step 8) — Dayset's exact values: same start (8) and end
   (24), step by 4 instead of 8, with the intermediate values 12 and
   20 added. The hook also subtracts the template's dx/dy wobble so
   the drawn position is exactly the slide (the wobble is larger than
   the half-step and would make the motion non-monotonic); the image
   still cycles (legs step).

The walk frames (existing, repeated): south/east tiles 384+0/6/1/7,
north 384+8/14/9/15, west 384+9/14/8/15. Buc's 16 tile streams
(384–399) are all distinct; offsets 4, 5, 10, 11, 12, 13 are never
used by any template 0–55 — but per Dayset's direction they are NOT
used here; the doubling repeats the existing frames.

## Files

- `loop.s` — rebuilt loop driver (org $FD800, 310 bytes). Same as the
  cutscene-loop driver plus the `walk_half` ($FFD104) pacing: step on
  every other call, `walk_half` 0/1 per half-cell. `loop_op5` moved
  $FD8E2 → $FD90E (parsed from the listing, hook site updated).
- `hook.s` — `hero_track` hook (org $FDA00, 196 bytes). Half-cell
  slide + wobble subtraction; gates on mode 2, Buc's record, and the
  Buc cutscene ($FF0110!=0, pointer in [$1A228,$1A390]).
- `build.py` — assembles both blobs with vasm, verifies the base
  bytes at the three hook sites, patches, fixes both checksums,
  writes the IPS and `changed-bytes.txt`, verifies the IPS round-trip.
- `walk-frames.ips` (629 bytes) — against the cutscene-loop base ROM.
- `changed-bytes.txt` — 406 bytes differ, confined to the header
  checksum, the three hook sites, the runtime immediate, and the two
  blobs. The flat ($FD400–$FD600) and feet-fix ($FD600–$FD780) blobs
  are byte-identical to the base.

## Build

```
python3 build.py
```

Output: `~/workspace/rop-work/walk-frames/rop-walk-frames.rom`
MD5 `a698a2f697939fd8a5b11b94837f32f7`
(header 0x08BB, runtime 0xA16ACFA7; `checksum.py verify-all` exit 0).

## What was NOT verified

No live tests (Dayset is the tester): no probes, screenshots, cadence
measurements, or playtest verification. In particular not verified:
whether the doubled animation reads as smoother in real play; whether
the half-cell slide is visible in all four directions; standing-still
(no jitter); the first step (4 ticks later than before — 8 ticks after
the reset call instead of 4, while the dialog is up); menu/teleport;
other rooms; the cutscene dialog and Thalmus's moves still running.

The big world stays textured; the flat, feet fix, loop-walk, and
cutscene dialog/script are unchanged. The original ROM is untouched
(MD5 `30c18fdbe2183f64702ae9f1a45d63f9`).
