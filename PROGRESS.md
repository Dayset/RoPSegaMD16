# Progress — Rings of Power disassembly

Started 2026-11-09. Owner: Dayset. This file is the status board.
GitHub: https://github.com/Dayset/RoPSegaMD16
Project overview (epics, rebuild contract, hardware limits, structure,
graphics pipeline): `docs/overview.md`.
Issues live in `issues/` — one file each. Update both together.

## Epics

| Epic | Name | Goal | Status |
|---|---|---|---|
| 1 | Rebuildable ROM | Decompile → recompile byte-identical → boot on emulator + real hardware | 🟡 in progress (M1 done) |
| 2 | Game structure & logic | Entry, main loop, save, stats, combat, spells; weak/strong points + logic-flaw audit | 🟡 in progress (#003 done, #019 open) |
| 3 | Graphics & audio pipeline | VDP, tiles, sprites, palettes, compression, Z80 sound | ⬜ not started |
| 4 | Mods | A few chosen changes, each as a tested patch | ⬜ not started (target TBD) |

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

| Issue | Epic | Title | Status | Milestone |
|---|---|---|---|---|
| #001 | 1 | Toolchain: Ghidra + Capstone + assembler + emulator | ✅ done | M1 |
| #002 | 1 | First linear disassembly + code/data map | ✅ done | M1 |
| #003 | 2 | Entry point, vectors, VBlank/HBlank interrupts | ✅ done 2026-11-09 | M2 |
| #004 | 3 | Text / dialogue extraction + tables | ⬜ not started | M3 |
| #005 | 3 | Graphics: tiles, sprites, palettes, compression | ⬜ not started | M3 |
| #006 | 3 | Maps / world data | ⬜ not started | M3 |
| #007 | 2 | Game logic: stats, XP, gold, combat | ⬜ not started | M4 |
| #008 | 2 | Spells / skills system | ⬜ not started | M4 |
| #009 | 1 | Rebuildable byte-identical disassembly | ⬜ not started | M5 |
| #010 | 4 | Patch workflow + first mod (target TBD) | ⬜ not started | M6 |
| #011 | 1 | Ghidra recursive analysis + function map | ⬜ not started | M2 |
| #012 | 1 | Split rebuildable asm: code vs incbin data | ⬜ not started | M2 |
| #013 | 1 | Assembler verification: byte-identical rebuild gate | ⬜ not started | M5 |
| #014 | 1 | Hardware-limits checklist + emulator/hardware test harness | ⬜ not started | M5 |
| #015 | 3 | VDP register + VRAM layout map | ⬜ not started | M3 |
| #016 | 3 | Tile/sprite/palette decoding + first rendered tileset | ⬜ not started | M3 |
| #017 | 3 | Compression identification: Nemesis / Kosinski / Enigma | ⬜ not started | M3 |
| #018 | 3 | Sound: Z80 driver + music/SFX map | ⬜ not started | M3 |
| #019 | 2 | Save/SRAM validation + $DCE2 / $42FC8 / $43012 | ⬜ not started | M2 |
| #020 | 2 | Main loop + game state machine | ⬜ not started | M4 |
| #021 | 2 | Combat / XP / gold / spell tables + logic-flaw audit | ⬜ not started | M4 |
| #022 | 4 | First mod: pick target + patch + verify | ⬜ not started | M6 |

## Done so far (2026-11-09)

- [x] ROM verified: 1 MB, MD5 `30c18fdb…`, header checksum `0x8B9F` matches computed.
- [x] Dialogue confirmed plain ASCII in-ROM (Void death message, guild/shop text).
- [x] Repo created with issues + progress tracking; pushed to GitHub as Dayset/RoPSegaMD16 (remote main at c6cec1f, local synced).
- [x] Toolchain installed (Capstone 5.0.9 venv, Ghidra 11.4.2 + JDK 21, GNU as 2.42, BlastEm 0.6.3.4). vasm NOT installed (404 upstream, deferred to #009).
- [x] First disassembly generated in `disasm/` — `disasm/rop.s` (273,209 insn, 20 MB, byte-identical regen) + `disasm/map.md`.
- [x] Runtime checksum self-test found at `0xFD07C` (expected `0x8F33608C`, hang on mismatch) — `tools/checksum.py fix-all` fixes both checksums, proven on a copy.
- [x] Original ROM boots and runs under BlastEm (headless via Xvfb + dummy audio); address log confirms boot through checksum into game code.
- [x] Fixed `.gitignore` `*.md` rule that silently ignored every doc/issue file (skeleton commit 68e4f98 contained only `.gitignore`).
- [x] Project overview written (`docs/overview.md`): 4 epics, rebuild contract, hardware limits, verified structure, strong/weak points, graphics pipeline, logic-flaw audit list. Issues restructured into epics + smaller tasks #011–#022.
- [x] **#003 done 2026-11-09** — reset vector traced `0x200 → $FD07C → $4323C → $119E → $D25C` (TMSS/SEGA init, VDP table `0x28E`, display on `$8174`, attract loop, `"MANX"` init); VBlank `0x1272` fully traced (frame counter `$FF0010`, 3-frame debounce, 16-entry joypad ring `$FF001C`); HBlank `0x1270` is a single `rte` that never fires (R0=`$04`); `$EB772` is the per-frame **sound** tick (not a draw dispatch — corrects an `overview.md` line, fix left for review); `$4323C` helpers mapped at call-graph level (Microwire-style serial EEPROM via `$200000`, `$DCE2` = joypad port 2, `$E0`/`$B0` = pad-2 button combos). Verified by Capstone range dumps + Ghidra headless call graph (436 functions, 1,434 edges) + BlastEm address log (2,487 unique addresses; `1272` hit, `1270` 0 hits; BlastEm auto-detected a 128-byte EEPROM). Written up in `docs/architecture.md`; `disasm/map.md` updated; open questions 1–2 answered/partially answered. M2 stays in progress (#011, #019 remain).

## Next

1. #011 (Ghidra recursive analysis) + #019 (save validation) — the remaining M2 cluster.
2. #004 (text extraction, packed dialogue blob at `0x0D6EBA`) and #017 (compression) — the two hard unknowns in Epic 3.
3. Dayset picks the first mod target for #022 — difficulty, a spell, dialogue, or a fix.
