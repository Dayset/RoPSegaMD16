# Issue #013 — Assembler verification: byte-identical rebuild gate

**Epic 1**  
**Milestone:** M5  
**Status:** open

## Goal
Prove the rebuild: assemble `disasm/src/` and get the original ROM back.

## Acceptance
- [ ] `tools/build.sh` assembles the tree to a ROM
- [ ] Output is byte-identical to the original except the two checksum
      fields; `fix-all` then makes it fully identical
- [ ] Gate script exits non-zero on any mismatch, with the first
      differing address printed
- [ ] vasm question settled (install it, or document GNU as as the
      assembler with its `$hex` trap noted in `docs/toolchain.md`)

## Notes
- Depends on #012. GAS silently assembles vasm-style `$53454741` hex
  as `#0` — use `0x` and verify with objdump.

