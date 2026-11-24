# Toolchain

One command installs everything: `sh tools/setup.sh` (re-runnable, prints a version check).

## Versions in use
- Assembler for the 68000: **vasm** `vasmm68k_mot -Fbin -m68000 -no-opt` (Motorola syntax, `$hex`), built by `tools/install_vasm.sh` at the pinned mirror commit in that script.
- Assembler for the Z80 driver: `vasmz80_oldstyle`, same build.
- Disassembly library: **capstone 5.0.7** (pinned in `tools/setup.sh`).
- Emulator for tests: **BlastEm 0.6.3.4** (Debian/Ubuntu `blastem` package), run headless under `xvfb-run`.
- Helpers: `xdotool`, `binutils-m68k-linux-gnu` (GNU as, used only by the hand-written scene harnesses in `tools/test_*_harness.s`).
- Java 21 headless, for Ghidra helper scripts.

## Assembler decision
GNU as rewrites some encodings (`cmp.w #imm,Dn` becomes `cmpi.w`, and other "optimal" forms), which broke byte-identity and is why the old tree carried `.dc.b` fallbacks. vasm with `-no-opt` keeps the original encodings and uses Motorola syntax. It is the assembler for `disasm/src/rop.s` and for the Z80 driver. GNU as stays only for the scene harnesses, which were written for it.

## Known traps
- Running `vasmm68k_mot` with no arguments waits on stdin. Check for the binary with `-x`; do not run it to test it.
- Stale `build/` output can hide a failed assembly; `tools/build.sh` removes old output first.

## Feature build (`make rom FEATURES=…`, issue #239)
A patch ships as a feature, never as a hand-assembled ROM: a directory
`patches/<name>/` holding `feature.s` (the new code) and `hooks.csv`
(one hook per line: `addr,len,kind,target`, kind ∈ `jsr|jmp|bytes`).
A `jsr`/`jmp` hook longer than 6 bytes is padded with `nop`s, so it
can replace an 8-byte first instruction. `feature.s` must start with `org ORGVAL`; the build supplies ORGVAL as
the allocator-chosen address, so no source hardcodes where it lands.
In-blob branches must be PC-relative (labels); absolute-long references
to fixed game addresses are fine. For `jsr`/`jmp`, `target` is a label
defined in `feature.s` and `len` is 6 (`jsr.l`/`jmp.l`); for `bytes`,
`target` is a hex byte string written verbatim and `len` is its length.

`tools/build_rom.py` builds the byte-identical base first (`make build`,
MD5-checked against the original), assembles each feature into a
first-fit free-space allocator (regions from `disasm/regions.csv` —
any class starting with `padding`, plus `zero-fill`; the file's only
padding region today is class `padding-ff`, `$FD0CC–$FFFFF`), and
fails the build if two hooks overlap, a hook splits an instruction
(checked against the `; $ADDR` boundaries in `disasm/src/rop.s`), a
hook target falls outside its feature's blob, or blobs collide. It
then fixes both checksums (runtime immediate first, header last) and
writes `build/rop-<features>.rom` + `.ips` + `.manifest.json`
(features, hooks, blob addresses, MD5). `FEATURES=` (empty) writes
`build/rop-base.rom`, byte-identical to the original ROM. Tests:
`python3 tools/tests/test_build_rom.py` (also run by `make unit`).

## Deterministic playtest harness (issue #240)

`make playtest` prints the metrics table for the original,
flat-zoomed, and walk-unused-frames ROMs (input-replay overlay
applied as a test-only overlay; never part of a shipped ROM).
Each trace is ~100 s wall (BlastEm runs at real-time 60 fps
under Xvfb :99); traces are cached in `.scratch-smooth240/`
and reused when the overlay ROM + route are unchanged.

- Input replay: `patches/input-replay/` — hooks
  `joypad_queue_pop` ($1350), NOT `pad_latch_11bb8` ($11BB8,
  dead code, nothing calls it). Blob at $FE000, table of
  (frame_count, pad1) pairs. Build:
  `python3 patches/input-replay/build.py --base <base.rom>
  --route <route.txt> --out <out.rom>`.
- Driver/metrics: `tools/playtest_metrics.py` — `trace`
  (BlastEm debugger: VBlank $1272 + room DMA $1B9E8
  breakpoints, `di` samples), `metrics`, `table`,
  `determinism` (two fresh runs, metric dicts must match).
- Frozen routes: `tools/playtest_route_orig.txt` (original,
  18 f room holds = 1 step), `_flat.txt` / `_walk.txt`
  (flat-zoomed, walk-unused-frames: 18 f holds = 2 steps,
  half the presses). All three walk the same western loop
  (L4 U4 D4 R4) in the Academy room from spawn (8,5).
- Room leader is entity 1, cell `$FF02F4`/`$FF02F6`
  (stride 0x34 from $FF02B4, cell at +$C/+$E); entity 0
  ($FF02C0/$FF02C2) is the overworld leader and freezes at
  the entrance cell inside a room.
- Room exits: pressing into the north wall (y=0) or standing
  on (0,0) exits the room; the east side has a wall at (6,1)
  and teleports past (10,3). Routes must use exact step
  counts and stay in open cells.
- Cadence is reported per phase (overworld / room) and
  overall; the original overall is ~19.86 (acceptance band
  19-22). `bg_jump_px` and `leader_jitter_px` are one cell
  vector (~16.1 px) on all three ROMs in v1 — the harness
  separates the original (room 16.67 f) from the fast ROMs
  (room 8.11 f) but not flat from walk-unused-frames; sub-cell
  smoothness needs framebuffer/sub-cell tracking.
