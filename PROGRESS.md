# Progress — Rings of Power disassembly

Started 2026-11-09. Owner: Dayset. This file is the status board.
GitHub: https://github.com/Dayset/RoPSegaMD16
Issues live in `issues/` — one file each. Update both together.

## Milestones

| # | Milestone | Status |
|---|---|---|
| M1 | Repo + toolchain + first disassembly | ✅ done 2026-11-09 |
| M2 | Code/data map + labelled entry/interrupts | 🟡 in progress |
| M3 | Text + graphics + maps identified | ⬜ not started |
| M4 | Game logic mapped (stats/XP/gold/combat/spells) | ⬜ not started |
| M5 | Rebuildable, byte-identical disassembly | ⬜ not started |
| M6 | First real mod, shipped as a patch | ⬜ not started |

## Issue board

| Issue | Title | Status | Milestone |
|---|---|---|---|
| #001 | Toolchain: Ghidra + Capstone + assembler + emulator | ✅ done | M1 |
| #002 | First linear disassembly + code/data map | ✅ done | M1 |
| #003 | Entry point, vectors, VBlank/HBlank interrupts | 🟡 in progress | M2 |
| #004 | Text / dialogue extraction + tables | ⬜ not started | M3 |
| #005 | Graphics: tiles, sprites, palettes, compression | ⬜ not started | M3 |
| #006 | Maps / world data | ⬜ not started | M3 |
| #007 | Game logic: stats, XP, gold, combat | ⬜ not started | M4 |
| #008 | Spells / skills system | ⬜ not started | M4 |
| #009 | Rebuildable byte-identical disassembly | ⬜ not started | M5 |
| #010 | Patch workflow + first mod (target TBD) | ⬜ not started | M6 |

## Done so far (2026-11-09)

- [x] ROM verified: 1 MB, MD5 `30c18fdb…`, header checksum `0x8B9F` matches computed.
- [x] Dialogue confirmed plain ASCII in-ROM (Void death message, guild/shop text).
- [x] Repo created with issues + progress tracking.
- [x] Toolchain installed (Capstone 5.0.9 venv, Ghidra 11.4.2 + JDK 21, GNU as 2.42, BlastEm 0.6.3.4). vasm NOT installed (404 upstream, deferred to #009).
- [x] First disassembly generated in `disasm/` — `disasm/rop.s` (273,209 insn, 20 MB, byte-identical regen) + `disasm/map.md`.
- [x] Runtime checksum self-test found at `0xFD07C` (expected `0x8F33608C`, hang on mismatch) — `tools/checksum.py fix-all` fixes both checksums, proven on a copy.
- [x] Original ROM boots and runs under BlastEm (headless via Xvfb + dummy audio); address log confirms boot through checksum into game code.
- [x] Fixed `.gitignore` `*.md` rule that silently ignored every doc/issue file (skeleton commit 68e4f98 contained only `.gitignore`).

## Next

1. #003 (entry/vectors/interrupts — incl. `$4323C` save validation, `$42FC8`/`$DCE2`) and #004 (text extraction, incl. the packed dialogue blob at `0x0D6EBA`).
2. Dayset picks the first mod target for #010 — difficulty, a spell, dialogue, or a fix.
3. Decide GitHub repo name + push (needs `gh auth login` — not logged in yet).
