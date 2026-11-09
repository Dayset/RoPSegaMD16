# Tools

- `checksum.py` — verify / fix the Genesis header checksum (issue #001)
- `extract_text.py` — dump strings with offsets (issue #004); also the `$DD5C` LZSS decoder (`dd5c_decompress`)
- `disassemble.py` — Capstone-based first-pass disassembly (issue #002)
- `build.sh` — assemble `disasm/src/` back to a ROM (issue #009; scaffold — blocked on #012)
- `verify_rebuild.py` — byte-identical rebuild gate (issue #013; `--selftest` passes without a ROM)
- `split_disasm.py` — split plan / dry-run for `disasm/src/` (issue #012)
- `test_harness.sh` — build → gate → BlastEm headless smoke harness (issue #014; scaffold)
- `render_tiles.py` — render packed tiles/sprites/maps to PNG (issue #005/#016)
- `decode_map.py` — decode `$96120` tilemap records (issue #006)
- `extract_assets.py` — ROM → `tribute/assets/` export pipeline (issue #024; scaffold + palettes)
- `decode_gamegenie.py` — decode Genesis Game Genie codes to (address, word); `--selftest`, `--rop` for the #033 table (issue #021)
