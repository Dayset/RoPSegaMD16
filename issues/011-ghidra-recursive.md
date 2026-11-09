# Issue #011 — Ghidra recursive analysis + function map

**Epic 1**  
**Milestone:** M2  
**Status:** open

## Goal
Replace the linear sweep's guesses with Ghidra's recursive disassembly:
a function map of the whole ROM, with code/data boundaries proven.

## Acceptance
- [ ] Ghidra project (already in `tools/ghidra/projects/rop`) re-run with
      auto-analysis; function list exported under `disasm/ghidra/`
- [ ] Code/data boundary for `0x010000–0x043FFF`, `0x0E0000–0x0FBFFF`
      decided per function, not per entropy guess
- [ ] `disasm/map.md` updated: provisional ranges become verified/likely
      with function addresses as evidence
- [ ] At least the entry, VBlank, `$4323C`, and `$EB772` call trees mapped

## Notes
- Depends on #001 (Ghidra installed) and #002 (first map).
- Linear-sweep density is not evidence — only vector/call-reached code counts.

