#!/bin/sh
# build.sh — assemble disasm/src/ to build/rop-rebuilt.gen (issues #009, #013).
# Run from anywhere; needs tools/vasm/ (tools/install_vasm.sh) and rop-original.gen.
set -eu
cd "$(dirname "$0")/.."
mkdir -p build
tools/vasm/vasmm68k_mot -Fbin -m68000 -no-opt -o build/rop-rebuilt.gen disasm/src/rop.s
