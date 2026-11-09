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

