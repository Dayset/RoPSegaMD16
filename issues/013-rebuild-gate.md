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



## Work done 2026-11-09 (agent session, no ROM in VM)

- **Deliverable:** tools/verify_rebuild.py — the gate script: byte-compare exempting only the header checksum (0x18E) and the runtime immediate (0xFD098), prints the FIRST differing address + total count, exits non-zero on mismatch. Self-test run this session: PASS (exempt-field and real-diff cases). tools/build.sh scaffold shared with #009.
- **Acceptance:** MET: gate script behaviour (by self-test); vasm question settled — GNU as is the assembler (vasm tarball 404 on 2026-11-09, docs/toolchain.md; the $hex trap is documented there and in build.sh). BLOCKED: an actual assemble-and-compare run needs disasm/src/ (#012) + assembler + ROM.

**Status after this session:** in progress — partial (see below). Not marked done.
