# Issue #011 — Ghidra recursive analysis + function map

**Epic 1**  
**Milestone:** M2  
**Status:** done (2026-11-09)
**Status:** done 2026-11-09

## Goal
Replace the linear sweep's guesses with Ghidra's recursive disassembly:
a function map of the whole ROM, with code/data boundaries proven.

## Acceptance
- [x] Ghidra project (already in `tools/ghidra/projects/rop`) re-run with
      auto-analysis; function list exported under `disasm/ghidra/`
- [x] Code/data boundary for `0x010000–0x043FFF`, `0x0E0000–0x0FBFFF`
      decided per function, not per entropy guess
- [x] `disasm/map.md` updated: provisional ranges become verified/likely
      with function addresses as evidence
- [x] At least the entry, VBlank, `$4323C`, and `$EB772` call trees mapped

## Done 2026-11-09 — results

- **446 functions, 1,449 direct call edges** (auto-analysis found 435;
  11 created manually — see `disasm/ghidra/README.md`). Exports under
  `disasm/ghidra/`: `functions.txt`, `call_edges.txt`,
  `function_bodies.txt` (exact body addresses; 54 non-contiguous
  bodies), `call_trees.txt`, `not_reachable_from_entry.txt`, `README.md`.
  Scripts preserved under `tools/ghidra_011_*.py`.
- **Coverage (exact body addresses):** `0x010000–0x043FFF` 90.7%
  (193,264/212,992 B); `0x0E0000–0x0FBFFF` 0.9% (984 B, sound cluster
  only); all compressed blocks 0.0%. Every gap ≥64 B in both ranges
  classified with function-address evidence (data references /
  call targets): 15 data + 1 code (`$1E022` case blocks) in the main
  range; 2 data gaps in the sound range.
- **Call trees mapped:** entry `0x200` → 405 functions (depth 1 is
  exactly the verified trace; depth 3 holds the seven `$D25C`
  callees); VBlank `0x1272` → 10; `$4323C` → 14; `$EB772` → 9.
  All agree with the Capstone-verified traces in `docs/architecture.md`.
- **Ghidra limitations found (not silently picked):** it misses code
  reached only via computed dispatch (11 manual functions created);
  it merges flow-connected routines (`$2B240` into `FUN_0002b190`,
  `$2B4B0` into `FUN_0002b402`, `$35600` into `FUN_000354a4`); the
  `jsr $EBA00` at `0xEB7BE` was in the listing but the analyser never
  created the callee. Cross-check vs the linear sweep: of 218 direct
  targets, 196 are function entries; 20 of the 21 non-body targets
  are sweep misdecodes in compressed data, 1 was real (`$EBA00`).
- `disasm/map.md` updated (new #011 section, address-map rows,
  open question 1 answered; also fixed the `$43012`/`$430F4`
  read/write swap that file still carried from #003).
  `docs/architecture.md` counts updated (436/1,434 → 446/1,449).
- Mid-issue the VM was replaced and `/tmp` wiped (incl. the system
  JDK); the JDK was reinstalled (OpenJDK 21.0.12.1) and all dumps
  re-generated from the project, which survived with all 11 manual
  functions intact. ROM MD5 unchanged
  (`30c18fdbe2183f64702ae9f1a45d63f9`).

## Notes
- Depends on #001 (Ghidra installed) and #002 (first map).
- Linear-sweep density is not evidence — only vector/call-reached code counts.



## Work done 2026-11-09 (agent session, no ROM in VM)

- **Deliverable:** disasm/ghidra/README.md + disasm/ghidra/function_map.csv — framework + 57-row seed map; every row cites the repo doc that evidences it (436-function / 1,434-edge Ghidra run from #003 indexed; the /tmp dump is lost and must be re-exported). Entry, VBlank, $4323C and $EB772 call trees are already mapped in docs/architecture.md.
- **Acceptance:** MET: call-tree acceptance item (by #003 evidence, indexed here). PARTIAL: function list export exists only as the seed CSV. BLOCKED: full auto-analysis re-run + per-function code/data boundaries for 0x010000-0x043FFF and 0x0E0000-0x0FBFFF need rop-original.gen + Ghidra 11.4.2 + JDK 21 on the owner's machine; disasm/map.md ranges therefore stay likely/provisional.

**Status after this session:** in progress — partial (see below). Not marked done.

## Update 2026-11-09 (continuation) — GHIDRA RUN DONE

Toolchain installed in the agent VM: Temurin JDK 21.0.13 +
Ghidra 11.4.2 PUBLIC (GitHub release). Headless import of a ROM
copy + auto-analysis per docs/toolchain.md (52 s, exit 0), plus
CreateMissingFunctions.py for the vector targets and
ExportFunctions.py for the export (scripts in tools/ghidra/).

- **438 functions, 1,434 unique-callee edges** exported to
  disasm/ghidra/function_map.csv (full format: address, name,
  size, caller/callee counts, callees, source). Auto-analysis
  alone: 435/1,432; the three manual vector functions bring the
  edge count to **exactly #003's 1,434** (function census +2 vs
  #003's DumpCalls-derived 436 — different measure, recorded in
  disasm/ghidra/README.md).
- Boundaries decided: 0x010000–0x043FFF = 368 functions, 90.3%
  coverage → **verified code** (rest embedded data).
  0x0E0000–0x0FBFFF = only 18 functions/692 B (sound cluster +
  tail) → **mostly data**, per-function split now in the CSV.
  disasm/map.md updated for all three ranges.
- Entry/VBlank/$4323C/$EB772 call trees: in the CSV (callees
  columns) on top of the #003 architecture.md mapping.

**Status after this update:** done (all acceptance items met).
