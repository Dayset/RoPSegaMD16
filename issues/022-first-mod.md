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

## Update 2026-11-09 — PATCH SHIPPED + VERIFIED

Dayset supplied the ROM (verified MD5 30c18fdb…); the VM toolchain
(Capstone/GNU as/BlastEm, docs/toolchain-vm.md) ran the full process:

- **Locate:** bug pinned at 0x3B2B2 (`moveq #1,d1; ext.l d1;
  divs.w d0,d1` after `jsr $3778E` + `addq #2,d0`).
- **Patch:** `patches/distance-fix/rings-of-power-distance-fix.ips`
  (54 bytes) — jmp hook at 0x3B2B2 to a 14-byte trampoline at
  0xFD138 computing base/(dist+2); checksums fix-all (header
  0x4F95, runtime 0x46818AFC, verify-all OK); IPS round-trip OK.
- **Boot:** BlastEm boots the patched ROM past its runtime
  checksum to the main loop; address-log diff vs original is
  exactly the two new targets (FD138, 3B2BC) — the hook fires
  during the attract sequence.
- **Harness:** #007 D1–D7 in the emulator read back exactly as
  pre-registered: D1 [31,69,31], D7 [31,100,31], D2–D6 unchanged.
  (Harness build carried the trampoline at 0xFE000 — the harness
  binary occupies FD0CC–FD606; shipped FD138 build is the
  boot/hook-traced one. See patches/distance-fix/README.md §6.)
- **Acceptance:** target picked ✓; change as minimal binary patch
  with written reason ✓ (labelled asm awaits #012); both checksums
  fixed ✓; boots in BlastEm ✓; affected scene — attract/combat
  code path exercised via harness + hook trace, a human-played
  combat scene and real hardware remain untested (same status as
  music-off); patch in patches/ with description + before/after ✓.
  Rebuild gate (#009/#013) with no changes: verify_rebuild.py
  ROM-vs-itself PASS; a full disasm/src rebuild gate remains #012
  work, so this item is recorded as shipped under the music-off
  precedent (binary patch workflow), not via the rebuild gate.

**Status after this update:** done as a shipped, verified patch
(human-played scene + hardware test noted as open follow-ups).
