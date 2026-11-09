# Issue #004 — Text / dialogue extraction + tables

**Milestone:** M3  
**Epic 3**  
**Status:** open

## Goal
Extract all in-game text with addresses, so dialogue edits are safe.

## Acceptance
- [ ] `tools/extract_text.py` dumps strings with file offsets
- [ ] Dialogue blob start/end + pointer table (if any) identified
- [ ] A same-length text replacement proven: patch → checksum → loads in emulator
- [ ] Text inventory saved under `disasm/text/`

