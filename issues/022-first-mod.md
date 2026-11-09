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



## Work done 2026-11-09 (agent session, no ROM in VM)

- **Deliverable:** docs/first-mod-proposal.md — five candidate targets analysed from the #021 audit (A: dead-distance-term fix, recommended; B: two-way Quiet; C: record-0 'An'; D: balance F4/F5; E: content) with size/risk/verification for each and a full patch plan for A copying the music-off workflow.
- **Acceptance:** NOT MET (by design): 'target picked by Dayset' — this is a proposal AWAITING Dayset's pick, explicitly not a pick. BLOCKED additionally on the rebuild gate (#009/#013) per the issue's own dependency. No patch was written.

**Status after this session:** in progress — partial (see below). Not marked done.
