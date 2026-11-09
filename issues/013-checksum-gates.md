
## Update 2026-11-09 (continuation) — GATE PASSES

tools/verify_rebuild.py on the #012 rebuild: **PASS** (identical
except the exempted checksum fields — and `cmp` shows even those
match, since the source reproduces the original bytes verbatim).
The gate is no longer a scaffold: it runs against a real rebuild
produced by tools/build.sh from disasm/src/. **Status: done.**
