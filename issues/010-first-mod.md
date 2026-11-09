# Issue #010 — Patch workflow + first mod (target TBD)

**Milestone:** M6  
**Epic 4**  
**Status:** done (2026-11-09)

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

## Update 2026-11-09 — target picked via #022

Dayset picked the #022 target: **Candidate A, fix the dead
distance term in `$3B1EE`** (see issues/022-first-mod.md update and
patches/distance-fix/). That is also this issue's mod target.
Patch generation remains blocked on the ROM/toolchain (as #022).

## Close-out 2026-11-09 (agent session #3, ROM + BlastEm in VM)

Decision the file asked for: **this issue is DONE.** Every
acceptance item is satisfied by the shipped #022 work; nothing
genuinely remains at this issue's scope.

- [x] **Mod target picked by Dayset** — Candidate A, fix the dead
      distance term in `$3B1EE` (picked 2026-11-09; recorded in
      the update above and in issues/022-first-mod.md).
- [x] **Patch in `patches/` with description + before/after** —
      `patches/distance-fix/`: README.md (spec, §6 build +
      verification record), `rings-of-power-distance-fix.ips`
      (54 bytes, 4 runs / 26 bytes), `changed-bytes.txt`,
      `build_patch.py`. Change: `jmp` hook at 0x3B2B2 to a
      14-byte trampoline at 0xFD138 computing `base/(dist+2)`.
- [x] **Checksum fixed, emulator smoke test passed** — fix-all:
      header 0x4F95, runtime 0x46818AFC, `verify-all` OK. BlastEm
      boots the patched ROM past its runtime checksum to the
      main loop; address-log diff vs the original is exactly the
      two new targets (0xFD138, 0x3B2BC); the #007 harness
      D1–D7 read back exactly as pre-registered (D1/D7 28→31,
      D2–D6 unchanged, canaries intact).
- [x] **Original ROM untouched; patch applies cleanly to a
      verified dump** — original MD5 re-verified this session
      (`30c18fdbe2183f64702ae9f1a45d63f9`); IPS round-trip
      byte-for-byte verified in the #022 session.

Carried follow-ups (not acceptance items here; same status as
the earlier music-off patch): a human-played combat scene and a
real-hardware test of the patched ROM remain untested. The
labelled-asm form of the change awaits the #012 source tree
being the patch vehicle — the shipped binary patch stands under
the music-off precedent, as recorded in issues/022.

**Status: done.**
