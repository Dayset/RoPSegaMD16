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

