# Issue #014 — Hardware-limits checklist + emulator/hardware test harness

**Epic 1**  
**Milestone:** M5  
**Status:** open

## Goal
A check every build and every mod must pass: it fits the hardware.

## Acceptance
- [ ] `docs/hardware-limits.md`: ROM/RAM/VRAM/CRAM/sprite/CPU budgets
      from `docs/overview.md`, as a checklist
- [ ] Harness script: build → fix checksums → boot in BlastEm headless
      → confirm it passes the runtime checksum and reaches gameplay
      (log-based, like the #001 boot proof)
- [ ] Every mod issue must tick the checklist before it lands
- [ ] Known emulator-vs-hardware gaps written down (what BlastEm
      forgives that real hardware would not)

## Notes
- Depends on #013. A mod that only works in an emulator is a failed mod.



## Work done 2026-11-09 (agent session, no ROM in VM)

- **Deliverable:** docs/hardware-limits.md — full checklist (ROM/RAM/VRAM/CRAM/sprite/CPU/DMA/Z80-bus/no-fault-handler/TMSS budgets from docs/overview.md) + emulator-vs-hardware gap list + tools/test_harness.sh scaffold (build -> gate -> fix-all -> BlastEm headless -> address-log grep for $4323C/$D28E).
- **Acceptance:** MET: checklist doc; gaps written down. PARTIAL: harness script exists but has never run — BLOCKED on #013 + BlastEm + ROM in this VM. 'Every mod ticks the checklist' is process, adopted via docs/first-mod-proposal.md referencing it.

**Status after this session:** in progress — partial (see below). Not marked done.

## Update 2026-11-09 (continuation, VM toolchain + ROM supplied)

BlastEm 0.6.3.4 now installed in the VM at /usr/games/blastem;
original ROM boots headless (Xvfb + dummy audio, still running
at timeout = pass signature). Both harness .s files assemble
cleanly with GNU as 2.42. BUG FIXED in tools/test_harness.sh:
its fix-all call missed the <dst> argument and swallowed the
error with `|| true` — would have tested an un-fixed ROM.
The full harness run still needs a rebuilt ROM (#013 gate).
