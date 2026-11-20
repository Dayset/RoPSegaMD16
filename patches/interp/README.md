# interp — smooth slide for the leader figure (Buc) in the B-zoom view

Base: `rop-pacing.rom` (MD5 `6abeec0bea66365f223c75760983df8b`).

## The problem (Dayset's playtest of the pacing ROM)

With a direction held, Buc stands for 4 ticks (cape moving, feet dead),
then teleports 1 cell. The pacing gate works (the cell commits once per
4 ticks) but the slide is missing: the figure's drawn position jumps at
the commit instead of interpolating between cells over the 4 phases.

Dayset also reported two timing observations, both diagnosed here (see
REPORT.md): the overworld walk runs at about half the normal game's
speed, and the cutscene plays "fast as a rocket".

## The fix (one fix only)

In `hero_track`, for Buc's draw record (char 1) in mode 2 (the room /
B-zoom view), override the drawn X/Y so the figure slides from the old
cell to the new cell over the 4 phases (old + phase/4 * step), with the
walk template's dx/dy wobble subtracted so the motion is monotonic.
The image still cycles per phase through the walk template (legs step).
The slide applies only when no event script is running (`$FF0110 == 0`),
so the cutscene keeps the walk template + wobble exactly as before.

## What stays intact

- Flat checkerboard (mode 2 only), feet fix (figures deferred to a
  post-pass), pacing gate (cell commits once per 4 ticks) — all
  byte-identical to the base ROM.
- Subcell override behaviour: the walk template (36+dir) is still
  applied to Buc's record in mode 2; the logic is kept verbatim inside
  this blob. The hook site `$023202` is repointed from `$FD800` to
  `$FDA00`; the `$FD800` subcell blob bytes are left untouched
  (unreferenced).
- Big world (mode 1) stays textured.

## Files

- `source.s` — the hook source (vasm, Motorola syntax).
- `build.py` — assembles, patches the base ROM, fixes both checksums,
  writes `changed-bytes.txt` + `interp.ips` (round-trip verified).
- `interp.ips` — patch against `rop-pacing.rom`.
- `changed-bytes.txt` — byte ranges that differ from the base ROM.

## Build

```
python3 build.py
```

Output: `~/workspace/rop-work/interp/rop-interp.rom`
MD5 `309d87c5a97cdbc5c2066f11a2f98399`
(header 0xB7C8, runtime 0xBDA564F2; both verify with checksum.py
verify-all).

## What was NOT verified

No live probes, screenshots, cadence measurements, or playtest
verification were run on this ROM (Dayset's rule: he tests it himself).
In particular NOT verified: whether the slide reads as smooth in real
play (Dayset's playtest is the check); the look in any room other than
the B-zoom room; the cutscene (code-gated only — the slide is skipped
while a script runs); menu / teleport on this ROM (code-gated only);
multi-level rooms, room water, or a direction change mid-step.
