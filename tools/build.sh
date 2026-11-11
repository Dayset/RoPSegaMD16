#!/bin/sh
# build.sh — assemble disasm/src/ to build/rop-rebuilt.gen (issues #009, #013).
# Run from anywhere; needs tools/vasm/ (tools/install_vasm.sh) and rop-original.gen.
# Old output is removed first, so a failed assembly can never leave a stale ROM behind.
set -eu
cd "$(dirname "$0")/.."
mkdir -p build
rm -f build/rop-rebuilt.gen
# Z80 sound driver first: its bytes are incbin'd by rop.s (#78)
tools/vasm/vasmz80_oldstyle -Fbin -o build/z80_snd_driver.bin disasm/z80/snd_driver.s
tools/vasm/vasmm68k_mot -Fbin -m68000 -no-opt -o build/rop-rebuilt.gen disasm/src/rop.s
test -f build/rop-rebuilt.gen
