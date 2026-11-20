# interp-fix — one-step camera delay for the B-zoom room walk

Base: `rop-interp.rom` (MD5 `309d87c5a97cdbc5c2066f11a2f98399`).
Output: `rop-interp-fix.rom` (see `../../rop-interp-fix.rom`).

## The problem

The interpolation slide (in `hero_track`) is room-relative, but the
camera tracks the figure's committed cell exactly, so on screen the
figure stays centred and the slide just oscillates ~10 px behind the
centre — net on-screen progress zero. Dayset's playtest: "even slower,
no subcell movement". Dayset's loop-walk playtest confirms the split:
Buc can walk in all directions (the loop works), but the world shift is
still jumpy — the remaining jumpiness is the integer-cell camera jumping
a whole cell at each commit, not the figure's slide.

## The fix (one fix only)

Delay the camera by one step during the walk in the room (mode 2).
Hooks the two step-mode camera writes in `leader_spawn` ($01C21A):
`$01C2D8` (cam X) and `$01C300` (cam Y). When a new camera is computed
during a walk, the hook stores it as the pending camera and leaves
`$FF0E8E/$FF0E90` at the old cell; on the next step-mode camera write
(the next commit, 4 ticks later) it first writes the pending camera,
then stores the new one. So the camera is always one step behind the
figure's committed cell, and the figure slides visibly across a static
room (centre → centre+step over phases 0–3) before the room jumps one
cell at the next commit.

Gate: delay ONLY when no event script runs (`$FF0110 == 0`) AND mode
== 2. The cutscene and the overworld update the camera immediately,
exactly as before. A script starting, or leaving mode 2, clears any
pending camera. Mode 6 (absolute set, teleports) is NOT hooked and
snaps immediately.

The room still jumps once per cell at the commit — fully smoothing the
world shift needs a fractional (smooth-scrolling) camera, which is the
big rework, NOT this fix. Cell rate is unchanged (1 cell / 4 ticks);
speed is not worse than the pacing ROM.

## What was NOT verified

No live probes, screenshots, cadence measurements, or playtest
verification of this ROM (Dayset's rule — he tests it himself).
Dayset's playtest asks: (1) does Buc slide visibly across the room
while walking (all four directions)? (2) does the room still jump once
per cell at the commit (expected — the big-rework item)? (3) cutscene
unchanged (fast, world jumps first then Buc catches up — the record
+10 == 1 mechanism, untouched)? (4) overworld walk unchanged?
(5) menu / teleport unchanged?

## Files

- `source.s` — the camdelay hooks (blob at `$FDE00`, RAM `$FFD010–$FFD014`).
- `build.py` — assembles, patches, fixes both checksums, emits the IPS
  (round-trip verified) and `changed-bytes.txt`.
- `interp-fix.ips` — the patch against `rop-interp.rom`.
- `changed-bytes.txt` — byte ranges that differ from the base ROM.
