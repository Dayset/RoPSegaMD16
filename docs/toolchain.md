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
