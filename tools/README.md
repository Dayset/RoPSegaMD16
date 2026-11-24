# Tools

- `checksum.py` — verify / fix the Genesis header checksum (issue #001)
- `extract_text.py` — dump strings with offsets (issue #004)
- `disassemble.py` — Capstone-based first-pass disassembly (issue #002)
- `build.sh` — assemble `disasm/` back to a ROM (issue #009)
- `md_run.py` — frame-stepped Mega Drive runner (Genesis Plus GX via
  `pip install stable-retro`): route files, per-frame RAM words, screen
  CRC, screenshots; ~500 frames/s, no X display (issue #249).
- `md_stress.py` — N frames of seeded random pad input (A+B+C
  included, or `--no-abc` after a `--prefix ROUTE:N` opening, to stay
  in one view); longest VBlank gap and longest still screen.
- `td_iso_frame.py` — generates the smooth iso view's frame data block
  in `patches/topdown/feature.s` (hole, edge tiles, commit columns).
- `md_smooth.py` — smoothness of a route segment from the rendered
  frames: background shift per frame, redraws, palette changes, blob
  steps (issue #249).
- `md_vram.py` — VRAM/CRAM/VSRAM/registers from a GPGX savestate.
- `md_video.py` — side-by-side 60 fps MP4 of ROMs on routes.
- `build_rom.py` — feature build: `make rom FEATURES=a,b,c` (issue #239).
  Assembles each `patches/<name>/feature.s` into a free-space allocator
  (regions from `disasm/regions.csv`), applies `patches/<name>/hooks.csv`
  (and `patches/<name>/data.csv` for data-only features), fails on
  hook/blob/data collisions or split instructions, fixes both checksums,
  writes `build/rop-<features>.rom` + `.ips` + `.manifest.json`.
  See `docs/toolchain.md` for the feature format.
