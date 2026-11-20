# big-rework PoC fix2 — camera-aware re-decode gate

Fixes the PoC (`patches/big-rework`) per Dayset's 2026-11-13 playtest:
the room image went stale / looked small and stuck, and only Buc was
visible, because the PoC's redraw gate suppressed EVERY room
re-decode after install. The frozen image never followed the camera
and the baked figures never updated.

## The fix (one change only)

The gate in `redraw_entry` now tracks the install camera
(`$FF00BC`/`$FF00C0`, dead RAM, 0 refs) and re-installs — lets the
body run its decode+DMA for the new camera, which updates the Plane B
image (the room draws are redirected to Plane B and the patterns are
re-uploaded) and re-bakes the figures at their current positions —
whenever the camera has moved from the install camera:

- camera unmoved: suppress as before (decode-once holds);
- camera exactly 1 cell away AND the D-pad scroll has caught up to
  that move (accumulators equal the expected values): seamless
  re-install (new image at scroll 0 == old image at the scroll
  extreme), scroll reset to (0,0) via `$DC16`;
- camera >1 cell away (teleport / fast move / scroll lagged):
  re-install with a 1-cell jump (strip streaming, the full rework,
  will close that gap; the jump is still half as often as the
  original's per-cell jump).

The gate runs on every `redraw_check` (main_loop calls it every
iteration), so a 1-cell move that hasn't caught up yet is suppressed
until the scroll reaches it a few frames later. No strip streaming,
no sprites, no tick governor, no decoration restore.
Dialogues/panels/menus are untouched (they don't depend on `$FF0098`).

## Diagnosis summary (full version: `.scratch-big-rework-poc-fix2/REPORT.md`)

- The diamond is the SAME size as the original (283x169 vs 278x160
  game px, same aspect) — it only LOOKS small because the install
  blanks the pink decoration/HUD, leaving the diamond floating on
  black. The black background is an accepted side effect (Dayset
  doesn't mind); this fix does NOT restore the decoration.
- Only Buc is visible at the save state's camera (7,7) in the
  ORIGINAL too: Thalmus (9,17) and the students (20,13)/(19,12) are
  outside the 10x10 window (x 2-11, y 2-11). Not a PoC bug at that
  camera — but the frozen image made it permanent. The fix re-bakes
  the figures on camera moves, so they come into view as he walks.
- The install can fire late (first `redraw_check` with `$FF0098`
  set), i.e. at a walked-to camera — Dayset's shot shows the big blue
  pool, not the (7,7) stone-walls view.

## Build

`python3 build.py` — assembles `source.s`, places the 1318-byte blob
at `$FD900`, patches the three hook sites + three static sites
(asserting the original bytes first), fixes both checksums, and
writes `rop-big-rework-poc-fix2.rom` (MD5
`d4fc661f333ca2425987d2407693bce9`), the IPS
(`rings-of-power-big-rework-poc-fix2.ips`, 1928 bytes, 145 records,
round-trip verified), and `changed-bytes.txt`. The original ROM
(`MD5 30c18fdbe2183f64702ae9f1a45d63f9`) is never modified.

## Build checks done

- Checksums verify (header `0x9818`, runtime `0x34B283AE`).
- IPS round-trip: base + IPS == ROM exactly.
- Hook bytes + blob + statics verified in place.
- Blob disassembled and the new gate verified instruction by
  instruction (suppress / seamless re-install / >1-cell re-install /
  scroll reset / stack balance / prologue re-execution).
- Smoke check (BlastEm + slot_0, 180 frames): installs correctly
  (magic `$9C07`, armed, installed, install camera (7,7)); renders
  pixel-identical to the PoC at the same state/frames (0/480,000 px
  differ) — the fix doesn't change the base rendering when the
  camera is still.

## NOT verified (Dayset is the tester)

- The live re-install behaviour: room following the camera as he
  walks, actors appearing, scroll staying smooth, dialogues working.
  The re-install path is verified by disassembly only — a live
  camera-move probe was blocked because this BlastEm debugger build
  has no memory-write command (`se` is register-only).
- The 1-cell jump on >1-cell moves (and a partial jump on diagonal
  1-cell moves, where the scroll clamp covers only half the move)
  is a known PoC limitation; report whether it's noticeable.
