# Issue #017 — Compression identification: Nemesis / Kosinski / Enigma

**Epic 3**  
**Milestone:** M3  
**Status:** open

## Goal
Identify the codec(s) in the high-entropy blocks `0x044000–0x05FFFF`
and `0x094000–0x0CBFFF`, and write a decoder.

## Acceptance
- [ ] Each block tested against Nemesis, Kosinski, Enigma (and
      uncompressed) with evidence for/against each
- [ ] Decoder script in `tools/` that reproduces the decompressed bytes
- [ ] Which block is graphics vs maps decided with decompressed evidence
- [ ] `disasm/map.md` updated with the answer

## Notes
- Depends on #011. Entropy 7.0–7.6 alone proves compression, not which one.

