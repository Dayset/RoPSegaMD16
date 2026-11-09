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



## Work done 2026-11-09 (agent session, no ROM in VM)

- **Deliverable:** disasm/ghidra/README.md + disasm/ghidra/function_map.csv — framework + 57-row seed map; every row cites the repo doc that evidences it (436-function / 1,434-edge Ghidra run from #003 indexed; the /tmp dump is lost and must be re-exported). Entry, VBlank, $4323C and $EB772 call trees are already mapped in docs/architecture.md.
- **Acceptance:** MET: call-tree acceptance item (by #003 evidence, indexed here). PARTIAL: function list export exists only as the seed CSV. BLOCKED: full auto-analysis re-run + per-function code/data boundaries for 0x010000-0x043FFF and 0x0E0000-0x0FBFFF need rop-original.gen + Ghidra 11.4.2 + JDK 21 on the owner's machine; disasm/map.md ranges therefore stay likely/provisional.

**Status after this session:** in progress — partial (see below). Not marked done.
