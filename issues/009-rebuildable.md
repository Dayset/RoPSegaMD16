# Issue #009 — Rebuildable byte-identical disassembly

**Milestone:** M5  
**Epic 1**  
**Status:** open

## Goal
The disassembly reassembles to a byte-identical ROM (checksum aside).

## Acceptance
- [ ] `tools/build.sh` assembles `disasm/` → ROM
- [ ] Output matches original byte-for-byte except the checksum field
- [ ] Build is repeatable from a clean checkout + own ROM dump



## Work done 2026-11-09 (agent session, no ROM in VM)

- **Deliverable:** tools/build.sh scaffold (fails loudly with the blocker until disasm/src/ exists; assembler decision = GNU as, vasm 404 per docs/toolchain.md) + disasm build plan in disasm/src/README.md (#012) + gate in tools/verify_rebuild.py (#013, self-test PASS).
- **Acceptance:** MET: none fully. PARTIAL: build.sh exists (scaffold). BLOCKED: byte-identical output + clean-checkout repeatability need disasm/src/ (#012), rop-original.gen and m68k-linux-gnu-as — none present in this VM (verified: no ROM file, no assembler).

**Status after this session:** in progress — partial (see below). Not marked done.
