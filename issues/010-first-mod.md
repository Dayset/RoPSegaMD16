# Issue #010 — Patch workflow + first mod (target TBD)

**Milestone:** M6  
**Epic 4**  
**Status:** open

## Goal
Ship the first real change as a patch file, tested in an emulator.

## Acceptance
- [ ] Mod target picked by Dayset (difficulty / spell / dialogue / fix — TBD)
- [ ] Patch in `patches/` with a description + before/after
- [ ] Checksum fixed, emulator smoke test passed
- [ ] Original ROM untouched; patch applies cleanly to a verified dump

## Notes
- Do NOT start this before #009, or the patch cannot be maintained.
- Target is still open — Dayset to pick.



## Work done 2026-11-09 (agent session, no ROM in VM)

- **Deliverable:** Analysis in docs/first-mod-proposal.md: patch workflow proven by the shipped music-off patch (IPS + changed-bytes + fix-all + round-trip) is documented as the template; five candidate targets analysed from the #021 audit with a recommendation (NOT a pick).
- **Acceptance:** MET: patch-workflow documentation. PARTIAL/BLOCKED: target pick is Dayset's (acceptance item 1) — agent must not pick it; emulator test needs the ROM + BlastEm on the owner's machine. Issue's own note says do not start before #009 — that dependency is still blocked.

**Status after this session:** in progress — partial (see below). Not marked done.
