# Ghidra function map — framework (issue #011)

Created 2026-11-09 (agent session, no ROM/Ghidra in this VM) from
evidence already committed in the repo. This is a **framework plus a
seed map**, not the finished #011 export.

## What exists

- `function_map.csv` — every function the repo's verified docs name,
  with address, the doc that evidences it, confidence, and notes.
  Seed: 57 rows, all traced to `docs/architecture.md`,
  `docs/logic.md`, `docs/spells.md`, `docs/maps.md`,
  `disasm/map.md`, or `patches/music-off/README.md`. No address in
  the CSV was invented in this session; each row cites its source.
- The headline numbers from the owner's Ghidra run (#003,
  `docs/architecture.md` "Ghidra note"): **436 functions, 1,434 call
  edges** (Ghidra 11.4.2 headless, `-noanalysis` on the existing
  project + `DumpCalls.py`). The full dump lived at
  `/tmp/ghidra_calls.txt` — scratch, NOT in the repo, now lost.
  Re-exporting it into this directory is the first #011 step on the
  owner's machine.

## Known Ghidra traps (from docs/architecture.md, verified)

1. Ghidra did **not** auto-create functions at `0x1270` (HBlank),
   `0x1272` (VBlank) or `$EB772` (sound tick) — vector targets have
   no call sites. Create them manually before trusting coverage.
2. The headless flag is `-postScript`, not `-script`; scripts need
   the `@author/@description/@category` header.
3. `$DE8E` is a 32-bit multiply, not a table lookup — Ghidra
   decompiles of `$3B51E`/`$36E2E`/`$3B748` mislead; asm wins
   (`docs/spells.md` §6.6).

## What #011 still needs (blocked here)

- [ ] Re-run auto-analysis on `tools/ghidra/projects/rop` with the
      ROM present; export the full 436+ function list to
      `function_map.csv` format (address, name, source, confidence).
- [ ] Decide code/data boundaries for `0x010000–0x043FFF` and
      `0x0E0000–0x0FBFFF` **per function**. Current state in
      `disasm/map.md`: those ranges are only "likely"/"provisional".
- [ ] Entry, VBlank, `$4323C`, `$EB772` call trees: **already mapped**
      at call-graph level in `docs/architecture.md` (#003) — this
      acceptance item is met by existing repo evidence; the CSV
      above indexes it.

**Blocker (exact):** needs `rop-original.gen` + Ghidra 11.4.2 + JDK 21
on the owner's machine. Neither ROM, Ghidra, nor an m68k assembler
exists in the 2026-11-09 agent VM.
