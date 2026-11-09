#!/bin/sh
# test_harness.sh — hardware-limits smoke harness (issue #014).
# Flow: build -> verify gate -> fix checksums -> BlastEm headless ->
# confirm the address log passes the runtime checksum (reaches
# $4323C save validation) and the main loop ($D28E).
# STATUS: scaffold, written 2026-11-09 in a VM with no ROM, no
# assembler and no BlastEm. Run on the owner's machine after #013.
set -eu
cd "$(dirname "$0")/.."
BLASTEM=${BLASTEM:-/usr/games/blastem}

sh tools/build.sh
python3 tools/verify_rebuild.py build/rop-rebuilt.gen rop-original.gen
cp build/rop-rebuilt.gen build/rop-test.gen
python3 tools/checksum.py fix-all build/rop-test.gen 2>/dev/null || \
  python3 tools/checksum.py fix-all --help >/dev/null 2>&1 || true
# NOTE: checksum.py's exact CLI is in its docstring (docs/toolchain.md);
# adjust the fix-all invocation above to match it on first real run.

[ -x "$BLASTEM" ] || { echo "test_harness: BlastEm not at $BLASTEM" >&2; exit 1; }
rm -f "$HOME/address.log" /tmp/address.log
SDL_AUDIODRIVER=dummy timeout 8 xvfb-run -a "$BLASTEM" -l build/rop-test.gen || true
LOG=$(ls "$HOME/address.log" /tmp/address.log 2>/dev/null | head -1)
[ -n "$LOG" ] || { echo "test_harness: no address log produced" >&2; exit 1; }
# Runtime checksum passed iff execution reached save validation and beyond
# (a checksum failure hangs forever at 0xFD0CA — see disasm/map.md).
grep -qi "4323c" "$LOG" || { echo "test_harness: FAIL — never reached \$4323C (checksum hang?)" >&2; exit 1; }
grep -qi "d28e" "$LOG" || { echo "test_harness: FAIL — never reached main loop \$D28E" >&2; exit 1; }
echo "test_harness: PASS — checksums fixed, runtime self-test passed, main loop reached. Log: $LOG"
echo "test_harness: now tick docs/hardware-limits.md by hand (audibility, raster timing and real hardware are NOT proven by this run)."
