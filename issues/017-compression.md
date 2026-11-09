# Issue #017 — Compression identification: Nemesis / Kosinski / Enigma

**Epic 3**  
**Milestone:** M3  
**Status:** done (2026-11-09, session #5)

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

## Update 2026-11-09 (continuation) — RANGE TESTED, VERDICT IN

Full results in docs/compression-audit.md ("0x044000–0x05FFFF
TESTED"): entropy/structure measured; head = 55×10-byte index
table (monotonic BE offsets); Ghidra (#011) finds 0 functions
and no callers into the range → not code; exhaustive $DD5C scan
→ only false positives (all-space outputs) → not $DD5C;
Nemesis/Kosinski/Enigma header parses at the block head all
fail → no evidence any of their streams starts the block.
disasm/map.md updated for both blocks (0x094000 row upgraded to
verified-$DD5C as this audit proposed).
Remaining acceptance gap: graphics-vs-maps for the 0x044000
block is still undecided — the threaded-decoder ($E3B4) stream
hypothesis is the only one standing, and its decisive test
(trace a0 at $E3B4 entry) belongs to the #020 follow-up.
**Status: in progress** — range tested, codec question narrowed
to the $E3B4 trace.

## Update 2026-11-09 (session #4) — $E3B4 TRACED, DECODER WRITTEN

- **Entry found:** $E358 (stack-arg prologue). a0 =
  table[$5F524][index] + $603E4; variant selects $E3B4/$E412.
  Direct callers: $1BC1A/$1BC3C/$1BC84 + $23234 family.
- **Decoder written:** tools/decode_e358.py — full threaded
  format (command byte → cell offset $435C0 + row band $436E0
  → writer via $DF58; mask table $433C0; variant-B expansion
  $434C0; output bitmap $FF1EC0, 33-byte rows). All 114 writer
  targets modelled symbolically; **943/943 records consume
  exactly their table length under both variants.**
- **Hypothesis verdict:** decoder CONFIRMED (custom threaded
  codec); "streams = the 0x044000 block" REFUTED — streams are
  at $0603E4–$096069 (944 records); the block's tail
  ($5F524–$603E3) is the decoder's pointer table.
- **Graphics-vs-maps:** the streams are map data (band
  renderer $1BCxx → $FF1EC0 "MM map" bitmap).
- disasm/map.md rows updated for both blocks.
- **Remaining gap:** the 0x044000 block's bulk + its head
  index (55×10 B) still have no identified consumer (no
  longword refs to $044000 exist). That is now the block's
  only open question; the codec question this issue was
  opened for is answered for every region except that bulk.

**Status: in progress** — codec/decoders done; 0x044000 bulk
consumer unidentified.

## Update 2026-11-09 (session #5) — SOLVED: archive + consumer identified. ISSUE DONE

Full write-up: docs/compression-audit.md (session #5 section);
decoder: tools/decode_44000.py (252/252 byte-exact).

- **The bulk is a $DD5C record archive**, like $96120/$B86AE:
  252 streams packed at 0x044228–0x05EDC3 (99×2048 B + 153×242 B
  decompressed), described by a 252×10-byte descriptor table at
  0x043850–0x044227 in $13654 format (u32 offset, u32 size,
  u16 type=1). The block-head "55×10 index" was records
  197–251 of that table, read 2 bytes misaligned — the
  continuation session's "not $DD5C" verdict is CORRECTED
  (its scan discarded the real streams as false positives).
- **Consumer identified:** FUN_00019692 (via thunk
  FUN_0001C802) → $13654 (pea $43850 / pea $44228 at
  0x01976C/0x019772) → type-1 path → $DD5C (jsr at 0x0136BA);
  4-slot rotating 2048-byte cache at $FF868C.
- **Content:** VDP nametable map data — 32×32 u16 grids
  (2048 B records) and 11×11 u16 grids (242 B records).
  Graphics-vs-maps is decided: maps.
- disasm/map.md row for 0x044000–0x05FFFF rewritten.

**Status: DONE** — all acceptance items met (codec tests,
decoder in tools/, graphics-vs-maps decided, map.md updated).
