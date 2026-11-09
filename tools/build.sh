#!/bin/sh
# build.sh — assemble disasm/src/ into a ROM (issues #009/#013).
#
# STATUS (2026-11-09, agent session, no ROM in VM): SCAFFOLD.
# disasm/src/ does not exist yet — it is produced by #012
# (tools/split_disasm.py) once #011's function map settles the
# code/data boundaries. Until then this script fails loudly with
# the exact reason instead of pretending to build.
#
# Contract (docs/overview.md "rebuild contract"):
#   1. assemble disasm/src/*.s with GNU as (m68k-linux-gnu-as)
#   2. output must be exactly 1,048,576 bytes
#   3. tools/verify_rebuild.py must pass (byte-identical except the
#      two checksum fields; fix-all then makes it fully identical)
# Assembler choice: GNU as 2.42. vasm was NOT installable on
# 2026-11-09 (upstream tarball 404) — see docs/toolchain.md.
# SYNTAX TRAP: GAS wants 0x hex; vasm-style $53454741 assembles
# silently as #0. Always verify with objdump / verify_rebuild.py.
set -eu
cd "$(dirname "$0")/.."

AS=${AS:-m68k-linux-gnu-as}
OBJCOPY=${OBJCOPY:-m68k-linux-gnu-objcopy}
OUT=${OUT:-build/rop-rebuilt.gen}
SRC_DIR=disasm/src

fail() { echo "build.sh: $*" >&2; exit 1; }

[ -d "$SRC_DIR" ] || fail "no $SRC_DIR yet — blocked on #012 (split) / #011 (function map). See issues/009-rebuildable.md work-done section."
command -v "$AS" >/dev/null 2>&1 || fail "$AS not found — install: sudo apt-get install -y binutils-m68k-linux-gnu (see docs/toolchain.md). Not available in the 2026-11-09 agent VM."
ls "$SRC_DIR"/*.s >/dev/null 2>&1 || fail "$SRC_DIR contains no .s sources yet."

mkdir -p build
# Entry file must come first / define the origin; layout is #012's call.
"$AS" -m68000 -o build/rop.o "$SRC_DIR"/main.s
"$OBJCOPY" -O binary build/rop.o "$OUT"
SIZE=$(wc -c < "$OUT")
[ "$SIZE" = "1048576" ] || fail "output is $SIZE bytes, expected 1048576 (1 MB flat ROM, no bank switching)"
echo "build.sh: wrote $OUT ($SIZE bytes)"
echo "build.sh: next gate -> python3 tools/verify_rebuild.py $OUT rop-original.gen"
