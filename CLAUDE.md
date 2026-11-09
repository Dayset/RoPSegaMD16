# Working rules for agent sessions (and humans)

Rings of Power (Mega Drive, 1992) disassembly. Current goal: **finish the
full disassembly** (milestones M5 → M8 → M9 → M10 → M11), with small
patches in between (M6). The tribute remake (M7) is on hold until M9.

## Tracker
- GitHub issues + milestones are canonical. `issues/NNN-*.md` are the
  older local notes (local numbers collide with GitHub numbers — write
  local ones as `L018` or link the file; `#N` means GitHub).
- One issue → one branch (`gh-<N>-short-name`) → one PR, merged in the
  same session. Never leave work on a long-lived branch: PR #1 diverged
  from `main` and six issues were done twice.
- Each PR body reports every acceptance item as met / partial / blocked
  with evidence. Never tick an item without evidence.

## Evidence standard
A claim about the ROM needs an address + bytes, and where possible an
emulator trace or harness result. Disagreeing findings are recorded side
by side with their evidence, not silently overwritten.

## The ROM
- Never committed (`*.gen` is git-ignored). Bring your own dump as
  `rop-original.gen`, MD5 `30c18fdbe2183f64702ae9f1a45d63f9`.
- After any byte change: `tools/checksum.py fix-all` (runtime checksum
  at `0xFD098` first, header `0x18E` last).

## Before pushing anything that touches `disasm/src` or `tools/`
1. `tools/build.sh` → `tools/verify_rebuild.py build/rop-rebuilt.gen rop-original.gen` must PASS
2. `python3 tools/coverage.py --md` → paste the TOTAL row in the PR
3. If code paths changed: BlastEm headless boot (`tools/test_harness.sh`)

## Assembler traps
- GNU as wants `0x` hex; `$1234` assembles silently as `#0`.
- GNU as re-encodes some instructions (`cmp.w #imm,Dn` → `cmpi.w`,
  `sub.w #imm` → `subi.w`, …). Such instructions are kept as `.dc.b` with
  a `/* was: … */` comment until the assembler question (#4/#7) is settled.
  Never "clean up" a `.dc.b` into the mnemonic without re-running verify.

## Logs
Session logs go in `docs/log/YYYY-MM-DD.md`, not PROGRESS.md. PROGRESS.md
keeps epics, milestones, the board and the coverage table only.
