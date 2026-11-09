
## Update 2026-11-09 (continuation) — HARNESS RUNS GREEN

tools/test_harness.sh run end-to-end in the VM (after the M5
rebuild landed): build OK → verify_rebuild PASS → checksum
fix-all (no changes needed; rebuild already byte-identical) →
BlastEm headless → **PASS** (reached $4323C and $D28E).
One real bug found and fixed in the harness itself: it looked
for BlastEm's address log in $HOME and /tmp, but BlastEm
0.6.3.4 writes ./address.log in the CWD — the script now checks
./address.log first.
Still NOT proven by this run (by design): audibility, raster
timing, real hardware — see docs/hardware-limits.md.
**Status: done** (the harness itself; hardware checks remain
open as documented hardware follow-ups, not harness work).
