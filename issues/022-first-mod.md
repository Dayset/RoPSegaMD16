# Issue #022 — First mod: pick target + patch + verify

**Epic 4**  
**Milestone:** M6  
**Status:** open

## Goal
Ship the first real change as a patch, through the full Epic 4 process.

## Acceptance
- [ ] Target picked by Dayset (one system, one address range)
- [ ] Rebuild gate passes with no changes first (Epic 1 done)
- [ ] Change implemented in labelled asm if possible, else minimal
      binary patch with a written reason
- [ ] Both checksums fixed; boots in BlastEm; affected scene played
      through; hardware-limits checklist ticked (#014)
- [ ] Patch in `patches/` with description + before/after

## Notes
- Depends on #009/#013/#014. Do NOT start before the rebuild gate passes.
- Supersedes #010 as the implementation task; #010 stays the Epic 4 milestone.

## Rendering-fix breakdown (GitHub #22 / L037) — corrected status 2026-11-10

Smooth movement and the multilevel fix are **not done** (status correction
posted by Dayset on GitHub #22, 2026-11-10). The multilevel part was only
designed, and the smooth-move v1 patch was reported broken (teleports,
skipped tiles, no in-between motion). Measured on the original ROM: the
picture updates every ~19–20 frames (~3 Hz) in world view, cell view and
the Buc cutscene alike; the cutscene looks smoother because each update
moves a few pixels (sub-cell), while walking jumps a whole cell.

Work breakdown (all under milestone M6 "Patches in between", part of
GitHub #22 / L037), suggested order #31 → #26 → #27 → #28 → #29/#30 → #32:
- #26 Diagnose the ~3 Hz update tick: frame-counter wait or redraw cost?
- #27 Reverse the Buc-cutscene sub-cell offset mechanism (reference for smooth walking) — the Buc cutscene is one of the few rare cutscenes where sub-cell motion is used, and that sub-cell motion is what's desirable for world navigation too
- #28 Sub-cell walking: interpolate camera and sprites, commit cell at the end (replaces smooth-move v1)
- #29 World view: cut the per-step redraw and DMA cost in `$1BA4E` and `$E358`
- #30 Cell (zoomed) view: smooth stepping and a responsiveness measurement
- #31 Repro harness: save state / route + 60 fps cadence measurement script
- #32 Tracker and docs correction for L037 (smooth-move / multilevel not done)

Repro input for #31 (Dayset, 2026-11-10): `workspace/user/files/slot_0_1_ou3l.state`
is the moment **before the Buc cutscene starts**; `workspace/user/files/save_0_inhm.eeprom`
is the matching EEPROM save. Dayset is starting with #31 and #26; the local
`issues/037-original-engine-rendering-fix.md`, the log and the patch README
are updated under #32 (Dayset).

