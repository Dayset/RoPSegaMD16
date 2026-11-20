# Subcell movement — patch

One fix only, on top of the flat + feet-fix ROM
(`rop-flat-zoomed-feet.rom`, MD5 `9373c0d01cf08c20f28e256daa9ea142`).

## Goal

The leader figure's movement in the B-zoom view (mode 2, the room) becomes
smooth subcell movement — the figure moves in small steps across a cell
instead of jumping a whole cell per tick. Same feel as the Buc cutscene
walk, which already moves subcell.

## Design

A single hook inside `hero_track` (`$023202`, the `lea.l $197B0,a0` that
loads the template-table base). The hook overrides the template index in
register `d0` — it never modifies the draw record in RAM.

- Gate: mode 2 only (`$FF00AE == 2`, room / B-zoom view) and only Buc's
  draw record (char 1; record index at `$FF02EC` = char `+0x04`, the
  index `map_grid_create` assigned). All other figures and the big world
  (mode 1) use the original template.
- Walk template: `36 + facing dir` (dir 0=N, 1=E, 2=S, 3=W). Template 38
  is the cutscene walkers' template (Buc walking south); 36/37/39 are its
  siblings (stepcodes 1/2/4 = dirs 0/1/3). Per-phase dx/dy come from the
  `$197B0` table, indexed by the grid+`$A` phase (0–3).
- Movement latch (RAM `$FFD000`–`$FFD006`, free scratch): latches ON when
  Buc's cell changes, OFF at the next phase-0 render with no cell change.
  A standing Buc keeps the original static template (no idle wobble);
  walk-template group 0 has dx/dy (0,0), so phase 0 is exact in any case.
- Safety: the record in RAM is never touched, so the `$022F52` record
  stepper still sees the original static template (stepcode 0 = no-op)
  and never moves the record on its own. The flat gate, flat colours,
  and feet-fix replay are untouched.

## What it does NOT do

- No change to the flat colours, the mode-2 gate, the feet fix, the room,
  or the big world. No dithering, no scroll-and-patch, no sprites.
- No change to movement pacing: the cell still commits when the game
  commits it. Whether the leader figure's cell commits every 4 ticks
  (phase 3→0 wrap, as `docs/subcell.md` says) or every tick is an open
  static question — if it commits every tick, the figure will still jump
  a full cell per tick with a wobble on top, and a pacing gate in the
  movement block would be the follow-up. Dayset's playtest is the check.

## Build

```
python3 build.py
```

Assembles `source.s` with vasm, verifies the base ROM MD5 and that
`$FD800` is `0xFF` padding, writes the blob at `$FD800`, patches the
single hook site `$023202` (`jsr subcell_hook.l`), fixes both checksums
(`checksum.py fix-all`, unshifted ROM), writes `changed-bytes.txt` and
`subcell.ips`, and verifies the IPS round-trip (base + IPS == ROM).

Output: `../rop-subcell.rom`.

## Verification

Minimal build checks only (Dayset's rule — he tests it himself):

- checksums verify (header + runtime immediate),
- IPS round-trip: base + IPS == ROM exactly,
- byte counts / changed ranges listed in `changed-bytes.txt`,
- flat blob (`$FD400`–`$FD600`) and feet-fix blob (`$FD600`–`$FD780`)
  byte-identical to the base ROM,
- base ROM and original ROM MD5s unchanged.

NOT verified: no live probes, screenshots, cadence measurements, or
playtest. In particular the pacing question above, the look in real play,
menu/teleport, and other rooms are all Dayset's playtest.
