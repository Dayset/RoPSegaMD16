# Issue #009 — Rebuildable byte-identical disassembly

**Milestone:** M5  
**Status:** open

## Goal
The disassembly reassembles to a byte-identical ROM (checksum aside).

## Acceptance
- [ ] `tools/build.sh` assembles `disasm/` → ROM
- [ ] Output matches original byte-for-byte except the checksum field
- [ ] Build is repeatable from a clean checkout + own ROM dump

