# Tools

- `checksum.py` — verify / fix the Genesis header checksum (issue #001)
- `extract_text.py` — dump strings with offsets (issue #004)
- `disassemble.py` — Capstone-based first-pass disassembly (issue #002)
- `build.sh` — assemble `disasm/` back to a ROM (issue #009)
- `build_rom.py` — feature build: `make rom FEATURES=a,b,c` (issue #239).
  Assembles each `patches/<name>/feature.s` into a free-space allocator
  (regions from `disasm/regions.csv`), applies `patches/<name>/hooks.csv`,
  fails on hook/blob collisions or split instructions, fixes both
  checksums, writes `build/rop-<features>.rom` + `.ips` + `.manifest.json`.
  See `docs/toolchain.md` for the feature format.
