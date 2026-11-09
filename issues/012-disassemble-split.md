
## Update 2026-11-09 (continuation) — SPLIT DONE

`tools/split_disasm.py --emit` implemented: reads the #011
function map + ROM, emits disasm/src/ (16 region files + main.s
include chain; code as GAS from Capstone with per-block
round-trip verification, data as generated .incbin slices —
git-ignored, regenerated from the ROM). tools/build.sh assembles
the tree to a 1,048,576-byte ROM. Layout and fidelity mechanism
documented in disasm/src/README.md ("As built" section).
**Status: done.**
