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
# Reach check (#16 item 3): overwrite the prologue at $D28E (shifted by SHIFT) with a logged VDP write.
# If the probe runs, the event logs diverge from their baselines at the same byte offset in both builds.
python3 - "$SHIFT" "$TMP" <<'PY'
import sys
from pathlib import Path
shift, tmp = int(sys.argv[1], 0), sys.argv[2]
probe = bytes.fromhex("31fc8f0200c00004")  # move.w #$8F02,$C00004.l
for name, src, at in [("orig", "rop-original.gen", 0xD28E), ("shift", f"{tmp}/shifted.gen", 0xD28E + shift)]:
    rom = bytearray(Path(src).read_bytes())
    rom[at:at + len(probe)] = probe
    Path(f"{tmp}/probe_{name}.gen").write_bytes(bytes(rom))
PY
"$BLASTEM" -b "$FRAMES" -e "$TMP/probe_orig.log" "$TMP/probe_orig.gen" >/dev/null 2>&1 || true
"$BLASTEM" -b "$FRAMES" -e "$TMP/probe_shift.log" "$TMP/probe_shift.gen" >/dev/null 2>&1 || true
div_o=$(cmp "$TMP/orig.log" "$TMP/probe_orig.log" 2>/dev/null | sed -n 's/.*char \([0-9]*\).*/\1/p' || true)
div_s=$(cmp "$TMP/shifted.log" "$TMP/probe_shift.log" 2>/dev/null | sed -n 's/.*char \([0-9]*\).*/\1/p' || true)
if [ -n "$div_o" ] && [ "$div_o" = "$div_s" ]; then
    echo "PASS reach \$D28E: probe diverges at byte $div_o in both original and shifted builds"
else
    echo "FAIL reach \$D28E: probe divergence orig=${div_o:-none} shift=${div_s:-none}"; exit 1
fi
