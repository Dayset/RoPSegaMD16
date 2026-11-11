#!/bin/sh
# shift_test.sh — #16 item 3. Build the ROM with SHIFT bytes of padding inserted before the code at $200,
# fix both checksums, then run original and shifted ROMs headless in BlastEm and compare hardware event logs.
# Needs tools/vasm, rop-original.gen, and BlastEm ($BLASTEM, default blastem on PATH). SHIFT default 0x100, FRAMES default 600.
set -eu
cd "$(dirname "$0")/.."
SHIFT=${SHIFT:-0x100}
FRAMES=${FRAMES:-600}
BLASTEM=${BLASTEM:-blastem}
TMP=build/shift
mkdir -p "$TMP"
SHIFT=$SHIFT ROP_SRC=$TMP/rop-shift.s python3 tools/gen_src.py >/dev/null
tools/vasm/vasmz80_oldstyle -Fbin -o build/z80_snd_driver.bin disasm/z80/snd_driver.s
printf 'RUNTIME_SUM\tequ\t0\nHEADER_SUM\tequ\t0\n' > build/checksum.inc
tools/vasm/vasmm68k_mot -Fbin -m68000 -no-opt -o $TMP/pass1.gen $TMP/rop-shift.s >/dev/null 2>&1
python3 tools/checksum.py inc $TMP/pass1.gen build/checksum.inc "$SHIFT"
tools/vasm/vasmm68k_mot -Fbin -m68000 -no-opt -o $TMP/shifted.gen $TMP/rop-shift.s >/dev/null 2>&1
python3 tools/checksum.py inc $TMP/shifted.gen build/checksum.inc "$SHIFT" >/dev/null
python3 - "$TMP/shifted.gen" "$SHIFT" <<'PY'
import sys
from pathlib import Path
rom = Path(sys.argv[1]).read_bytes()
assert len(rom) == 1048576, len(rom)
print(f"shifted ROM {len(rom)} bytes, SHIFT={sys.argv[2]}")
PY
"$BLASTEM" -b "$FRAMES" -e "$TMP/orig.log" rop-original.gen >"$TMP/orig.out" 2>&1 || true
"$BLASTEM" -b "$FRAMES" -e "$TMP/shifted.log" "$TMP/shifted.gen" >"$TMP/shifted.out" 2>&1 || true
if cmp -s "$TMP/orig.log" "$TMP/shifted.log"; then
    echo "PASS shift test: $FRAMES frames, event logs identical"
else
    echo "FAIL shift test: event logs differ"; cmp "$TMP/orig.log" "$TMP/shifted.log" || true; exit 1
fi
