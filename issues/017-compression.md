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



## Work done 2026-11-09 (agent session, no ROM in VM)

- **Deliverable:** docs/compression-audit.md — full audit of every repo doc/table: $DD5C LZSS is PROVEN for all tested regions (62/62 + 90/90 records + 4 text streams; decoder already in tools/extract_text.py); the 0x094000-0x0CBFFF block is thereby accounted for; NO positive evidence for Nemesis/Kosinski/Enigma anywhere; the 0x044000-0x05FFFF block remains untested with the threaded-decoder (0xE3B4) hypothesis named. map.md upgrade proposed in the doc (not applied — that file belongs to #002/#011 review).
- **Acceptance:** MET: decoder-in-tools (for the codec actually used); graphics-vs-maps decided for 0x094000+ (it is both, as $DD5C tables). PARTIAL/BLOCKED: running the three named standard decoders against 0x044000-0x05FFFF needs rop-original.gen (absent); map.md update proposed, not applied.

**Status after this session:** in progress — partial (see below). Not marked done.
