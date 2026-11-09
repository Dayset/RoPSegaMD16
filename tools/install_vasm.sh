#!/bin/sh
# install_vasm.sh — build vasm (m68k Motorola syntax + z80) into tools/vasm/ (GitHub issue #4).
# Source: GitHub mirror of Volker Barthelmann's vasm (the sun.hasenbraten.de tarball URL is dead).
# Needs: git, make, a C compiler (macOS: xcode-select --install; Debian/Ubuntu: apt install build-essential git).
# Verified 2026-11-09: vasm 2.0f, m68k backend 2.8c, mirror commit a13e7e7.
# Use:  tools/vasm/vasmm68k_mot -Fbin -m68000 -no-opt -o out.bin in.s
# `cmp.w #imm,d7` -> BE7C, `sub.w #imm,d0` -> 907C, `sub.l #imm,d0` -> 90BC: the original encodings
# that GNU as rewrites (issue #7).
set -eu
cd "$(dirname "$0")"
REF=${VASM_REF:-a13e7e728a3dd5a9ba468bf479119e0bc23e70fd}
rm -rf vasm-src vasm
git clone -q https://github.com/mbitsnbites/vasm-mirror vasm-src
git -C vasm-src checkout -q "$REF"
JOBS=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 2)
make -C vasm-src CPU=m68k SYNTAX=mot -j"$JOBS" >/dev/null
make -C vasm-src CPU=z80 SYNTAX=oldstyle -j"$JOBS" >/dev/null
mkdir vasm
cp vasm-src/vasmm68k_mot vasm-src/vasmz80_oldstyle vasm/
rm -rf vasm-src
vasm/vasmm68k_mot 2>&1 | head -1
echo "installed: tools/vasm/vasmm68k_mot, tools/vasm/vasmz80_oldstyle"
