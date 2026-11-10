#!/bin/sh
# test_harness.sh — headless boot check for the rebuilt ROM (issue #014).
#   1. build the ROM (tools/build.sh) and run the byte-identity gate
#   2. boot original and rebuilt ROMs headless in BlastEm for N frames (-b N)
#   3. compare their hardware event logs (-e): identical logs = identical behaviour
# Needs: tools/vasm (tools/install_vasm.sh), rop-original.gen, and a BlastEm binary
# named by $BLASTEM (default: blastem on PATH). Frames default to 600.
set -eu
cd "$(dirname "$0")/.."
BLASTEM=${BLASTEM:-blastem}
FRAMES=${FRAMES:-600}
TMP=${TMPDIR:-/tmp}/rop-harness.$$
mkdir -p "$TMP"
trap 'rm -rf "$TMP"' EXIT

sh tools/build.sh >/dev/null
python3 tools/verify_rebuild.py build/rop-rebuilt.gen rop-original.gen

"$BLASTEM" -b "$FRAMES" -e "$TMP/orig.log" rop-original.gen >"$TMP/orig.out" 2>&1
"$BLASTEM" -b "$FRAMES" -e "$TMP/rebuilt.log" build/rop-rebuilt.gen >"$TMP/rebuilt.out" 2>&1
if cmp -s "$TMP/orig.log" "$TMP/rebuilt.log"; then
    echo "PASS headless boot: $FRAMES frames, event logs identical ($(wc -c <"$TMP/orig.log") bytes)"
else
    echo "FAIL headless boot: event logs differ"
    cmp "$TMP/orig.log" "$TMP/rebuilt.log" || true
    exit 1
fi
