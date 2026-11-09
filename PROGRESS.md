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
| 3 | Graphics & audio pipeline | VDP, tiles, sprites, palettes, compression, Z80 sound | 🟡 in progress (#004, #005 done) |
| 4 | Mods | A few chosen changes, each as a tested patch | 🟡 in progress (first patch shipped: music-off 2026-11-09; #022 target still TBD) |

## Milestones

| # | Milestone | Status |
|---|---|---|
| M1 | Repo + toolchain + first disassembly | ✅ done 2026-11-09 |
| M2 | Code/data map + labelled entry/interrupts | 🟡 in progress |
| M3 | Text + graphics + maps identified | 🟡 in progress (#004, #005, #006 done) |
| M4 | Game logic mapped (stats/XP/gold/combat/spells) | ⬜ not started |
| M5 | Rebuildable, byte-identical disassembly | ⬜ not started |
| M6 | First real mod, shipped as a patch | 🟡 in progress (first patch shipped separately as music-off 2026-11-09; #022 target still TBD) |

## Issue board

| Issue | Epic | Title | Status | Milestone |
|---|---|---|---|---|
| #001 | 1 | Toolchain: Ghidra + Capstone + assembler + emulator | ✅ done | M1 |
| #002 | 1 | First linear disassembly + code/data map | ✅ done | M1 |
| #003 | 2 | Entry point, vectors, VBlank/HBlank interrupts | ✅ done 2026-11-09 | M2 |
| #004 | 3 | Text / dialogue extraction + tables | ✅ done 2026-11-09 | M3 |
| #005 | 3 | Graphics: tiles, sprites, palettes, compression | ✅ done 2026-11-09 | M3 |
| #006 | 3 | Maps / world data | ✅ done 2026-11-09 | M3 |
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
- [x] **#004 done 2026-11-09** — text/dialogue fully decoded (`disasm/text/README.md`): dictionary system proven — 3,466 words, 1-based indices, blob `0x0D6EBA–0x0DC0C0` + offset table `0x0DC0C2`; `$136FC` exact semantics (skip array[0], read one past, separator top-2-bits); `$DDBD8` 1,184 records (0–1180 real, 1181–82 `<NA>`, 1183 malformed); `$DD5C` LZSS re-implemented and verified (3 text streams: Book of Nexus `0x0A66E6`, Book of Buc `0x0B3D40`, title credits `0x0B6221`); ground-truth validation vs fan-site corpus **647/649 (99.7%)**; Russian fan translation (bybyc9lc9l, 2012) independently confirms dictionary-based original — its IPS patch diffed (new `$D7030` pointer table + compressed blocks, `$D6F50` reader, font uploads `$FD0D0`/`$1AA70`/`$E8C70`, runtime checksum NOP'd at `0xFD09C`); same-length replacement proven (`Continue` → `Resumed ` at `0x15BE1`, fix-all, verify-all, BlastEm boot to Naughty Dog logo). Open: record-0 dropped `An` (likely real 1992 bug, needs live check), `&` separator source, `$B8A32` layout, `$DD5C` control codes. M3 in progress.
- [x] **#003 done 2026-11-09** — reset vector traced `0x200 → $FD07C → $4323C → $119E → $D25C` (TMSS/SEGA init, VDP table `0x28E`, display on `$8174`, attract loop, `"MANX"` init); VBlank `0x1272` fully traced (frame counter `$FF0010`, 3-frame debounce, 16-entry joypad ring `$FF001C`); HBlank `0x1270` is a single `rte` that never fires (R0=`$04`); `$EB772` is the per-frame **sound** tick (not a draw dispatch — corrects an `overview.md` line, fix left for review); `$4323C` helpers mapped at call-graph level (Microwire-style serial EEPROM via `$200000`, `$DCE2` = joypad port 2, `$E0`/`$B0` = pad-2 button combos). Verified by Capstone range dumps + Ghidra headless call graph (436 functions, 1,434 edges) + BlastEm address log (2,487 unique addresses; `1272` hit, `1270` 0 hits; BlastEm auto-detected a 128-byte EEPROM). Written up in `docs/architecture.md`; `disasm/map.md` updated; open questions 1–2 answered/partially answered. M2 stays in progress (#011, #019 remain).
- [x] **#005 done 2026-11-09** — graphics fully identified (`disasm/graphics/README.md` + `inventory.md`): tile/sprite graphics live in two `$DD5C`-compressed tables, not raw ROM — `$96120` (62 records, sources `0x09638C–0x0B86AE`) and `$B86AE` (90 records, each `[32-byte palette][36 tiles]`, sources `0x0B8A32–~0x0CC761`); decompressed tile bytes are **packed, 2 pixels/byte, high nibble first** (proven by the $B86AE rec 0 portrait and the $96120 rec 0 ASCII font rendering coherently only in packed layout, cross-checked against BlastEm's VRAM debugger; byte stats 62.6% hi==lo nibble); palette format Mega Drive 9-bit BGR `0BBB0GGG0RRR0`, master table ROM `0x0CC9D8` (31 palettes), loader `$11082(table_ptr, slot)` → CRAM via `$D9E2`/`$D9EE`, `$B86AE` records embed their own palette; compression is `$DD5C` LZSS for all graphics in both tables (62/62 + 90/90 clean, no Nemesis/Kosinski/Enigma there); upload `$1383C` → `$11A7C` → `$DA04` VDP DMA and `$11AE4` → `$11B2E` → `$DA04` DMA, both verbatim. Rendered: full ASCII font + "MORE" (`font_rec00_pal10.png`), terrain rec 6, logo rec 12, two character portraits + one textured graphic (`portrait_b86ae_rec00/01/05.png`); renderer `tools/render_tiles.py` (record/sprite/raw modes, `--layout`). Side finding: `$96120` rec 61 is a 4th `$DD5C` text stream (bestiary/class text) — fold into #004. Open paradox for #015/#016: textbook VDP format is bitplanar yet the DMA path shows no packed→planar conversion and the game displays correctly. Raw ROM `0x060000–0x093FFF` is NOT raw tiles (noise in every layout) — `disasm/map.md`'s label there is wrong. M3 stays in progress (#015–#018 remain).
- [x] **#006 done 2026-11-09** — maps fully identified (`docs/maps.md`, `disasm/maps/` + `tools/decode_map.py`): maps are `$DD5C` tilemap records in the `$96120` table (record `[ptr][declen][type]`, declen = decompressed length), drawn by the `$1194A` blitter (VRAM word = map word + base; stride in **words**, not bytes — corrected this session; `$1383C(index)` → pointer, `$11ABC(count, base, src)` uploads tiles). 21 tilemap records, every one paired with its tileset by tracing loader call sites (max tile index = tileset tile count − 1 in all 21). Decoded and drawn: the world map of Ushka Bau (rec 9, 28x40, diamond + compass rose, pal 11 code-pinned), the starfield map (rec 35, 28x40, tileset rec 34 not rec 12 — corrected via the `#$119` count push, pal 30), the title logo "RING" (rec 22, two alternative layers recs 22–26 / 48–52), the archway (rec 54, pal 17), the castle (rec 57, pal 27), the night landscape (rec 39, pal 14 best-fit). Validated against the fan world map (`RingsOfPower-World.png`) — **Dayset verified it himself 2026-11-09, legit and perfect as-is** — diamond orientation, compass rose and land/sea split all match; the in-game map is schematic (solid land tile, no terrain detail in the tilemap). `0x0CC000–0x0D7FFF` is not map data (item-name table `0x0CEB00` incl. "MM map"/"map"/"mapbit", palette table, menu strings). Open: the **walkable overworld terrain grid was not located** (leads: threaded decoder `0xE3B4`/`0xE412` + nibble tables `$433C0–$436E0`, `0x044000–0x05FFFF` block, "MM map" item — #020/#011 territory); rec 35's screen identity, title layer 2's purpose, rec 39's display palette + scene top half, city markers, `$1194A` flip-path arithmetic. M3 stays in progress (#015–#018 remain).
- [x] **Music-off patch shipped 2026-11-09** (`patches/music-off/`): makes the Music menu's Quiet choice actually silence the music and keep it off across location changes — Quiet was song index 18, a no-op dispatch entry, and `$EB7C8` stop-sound was dead code; two hooks (`0x173C0`, `0x173F4`) + trampolines in the `0xFF` padding at `0xFD0CC+`; IPS round-trip verified, checksums fixed; limit: one-way off switch, reset restores music. Pushed separately (remote main `9d0fe38`, commits `1484062` + `c7f22ec`) — a user-requested fix, NOT the #022 first-mod pick; the #022 target is still TBD.

## Next

1. #011 (Ghidra recursive analysis) + #019 (save validation) — the remaining M2 cluster.
2. #017 (compression — `$DD5C` LZSS now identified + re-implemented in #004 and proven for all graphics in #005; remaining: check whether Nemesis/Kosinski/Enigma appear elsewhere) — the rest of Epic 3.
3. Dayset picks the first mod target for #022 — difficulty, a spell, dialogue, or a fix.
