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

## Update 2026-11-09 — TARGET PICKED: Candidate A

- **Dayset picked A: fix the dead distance term in `$3B1EE`.**
  Acceptance item 1 (target picked) is now **MET** — one system
  (combat damage), one routine (`$3B1EE`–`$3B408`).
- **Deliverables:** `patches/distance-fix/README.md` (full spec:
  bug, fix designs inline-vs-trampoline, verification table —
  harness D1 28→31 and D7 28→31, all other D-cases unchanged,
  plus a dist 0/5/13 sweep 38/31/30) and
  `patches/distance-fix/build_patch.py` (ROM verify + Capstone
  locate step; apply is guarded — it refuses to generate patch
  bytes from a guess, because docs/logic.md proves the term's
  semantics but not its exact bytes).
- **Prior art checked:** the 2008 *Hand of Nexus* v2.0 hack
  (Whipon; romhacking.net/hacks/354) is a cheat set (invincibility,
  infinite resources, all spells) with no damage-formula change in
  its published description — no evidence it fixed this term.
- **Still blocked:** rebuild gate (#009/#013) + locate/apply/harness
  runs need `rop-original.gen` + Capstone/BlastEm on Dayset's
  toolchain machine. No IPS generated yet, deliberately.

**Status after this update:** in progress — target picked, spec + builder ready, patch generation blocked on ROM/toolchain.
