# Issue #017 — Compression identification: Nemesis / Kosinski / Enigma

**Epic 3**
**Milestone:** M3
**Status:** done 2026-11-09

## Goal
Identify the codec(s) in the high-entropy blocks `0x044000–0x05FFFF`
and `0x094000–0x0CBFFF`, and write a decoder.

## Acceptance
- [x] Each block tested against Nemesis, Kosinski, Enigma (and
      uncompressed) with evidence for/against each
- [x] Decoder script in `tools/` that reproduces the decompressed bytes
- [x] Which block is graphics vs maps decided with decompressed evidence
- [x] `disasm/map.md` updated with the answer

## Verdict

**Neither block is a new codec.** Both blocks are the already-proven
`$DD5C` LZSS codec (#004/#005), plus tables and two small
unidentified regions. Nemesis, Kosinski and Enigma were all tested
against the genuinely unknown bytes with reference decoders and
rejected. The issue's premise (two unknown high-entropy blocks) was
wrong in one respect: most of both ranges was already `$DD5C` data
whose tables sit inside the ranges themselves.

## Block 1 — 0x044000–0x05FFFF: map chunks ($DD5C)

The block is a third `$DD5C` table, `$43850` (252 records), exactly
parallel to the `$96120` / `$B86AE` tables of #005 — record
`[u32 offset, u32 decompressed length, u16 type]`, offsets **relative**
to a data base (here `0x44228`, the byte after the table). First parse
attempt treated offsets as absolute and failed; the relative-base
correction makes all 252 records decode cleanly.

| Sub-range | Contents |
|---|---|
| `0x43800–0x43850` | u16 values, +4 steps in groups of 8 — unidentified |
| `0x43850–0x44228` | `$43850` table, 252 records, all type 1 |
| `0x44228–0x05EDC4` | 252 `$DD5C` streams, contiguous, no gaps (109,468 B compressed) |
| `0x05EDC4–0x05F1C4` | `$5EDC4`: 512-word table (min 1, max 34829, 147 distinct; `0x1901` heavily repeated) — likely per-tile properties, indexed by (tile & 0x1FF) at `0x1BAAC` etc. Semantics open |
| `0x05F1C4–0x05F524` | 864 B unidentified (starts 32× u16 `0x0001`, then varied values) |
| `0x05F524–0x060000` | `$5F524` terrain offset table: 176 u32 offsets (0–0x7E77); streams at `0x603E4+`, last ends ~`0x68300` |

The 252 records split into two sizes, both VDP-tilemap chunks
(big-endian u16 words: bits 0–10 tile index, `0x0800` flip-H,
`0x1000` flip-V, bits 13–14 palette, bit 15 priority):

- **99 × 2048 B = 32×32 tilemap chunks** (recs 0–76, 230–251).
  Rec 0 renders as a coherent map: `0x24` ground field, `0x1C/0x1D/0x22`
  terrain mass, `0x10/0x11` features, `0x56/0x57` border column.
  521 distinct tile indices (max 2027) across all 99.
- **153 × 242 B = 11×11 tilemap chunks** (recs 77–229, contiguous).
  Rec 77 renders as a coherent 11×11 grid: `0x00` open space,
  `0x59/0x5A/0xCD` features, flag bits `0x0800/0x2000` on the lower
  rows. 294 distinct tile indices (max 1799) — the same tileset space
  as the 32×32 chunks, same flag bits, so one map system, two chunk
  sizes (large-area vs small-area chunks; which maps use which is
  open — the `$1C7DA`/`$1C83E` chunk-index computation divides position
  by the location record's words in `$FFA7FC`).

Loader: `$19692` (0x19692–0x197AE, `link #-4`) is a 4-slot
round-robin cache — counter `$FFA894` & 3, count/limit
`$FFA880`/`$FFA882`, id table `$FFA884`, pointer table `$FFA896`,
buffers at `$FF868C` + slot×2048 (2048 B/slot, matching the big
records). Single caller: `$1C802` (lazy getter: if
`$FFA896[idx×4] == 0` call `$19692`, return the pointer), called from
7 sites (`0x1C1C2`, `0x31A44`, `0x31AF4`, `0x31FBE`, `0x32194`,
`0x38952`, `0x3F720`). The `$13654` dispatcher (verified head) takes
(dest, index, table, data base) and dispatches on record type
(0 → `$DE1A`, 1 → `$DD5C`, 5 → `$136FC`); its 5 call sites cover all
three tables (`$96120` ×2, `$B86AE`, `$43850`, `$DDBD8`).

**This block is MAPS** (tilemap chunks), not graphics: the decoded
bytes are tilemap words, and the loader is the map-chunk cache.
(The walkable terrain grid itself is still not located — #020/#021
narrowed its decoder to the threaded `$E3B4`/`$E412` reading terrain
streams at `0x603E4+`, which is the `$5F524` table's data, not this
block's chunks.)

## Block 2 — 0x094000–0x0CBFFF: graphics ($DD5C) + one unknown gap

Almost the whole range was already `$DD5C` data from #005:

| Sub-range | Contents |
|---|---|
| `0x094000–0x096120` | **8,608 B unidentified structured data** — see below |
| `0x096120–0x09638C` | `$96120` table, 62 records (base `0x09638C`) |
| `0x09638C–0x0B86AE` | 62 `$DD5C` streams, contiguous (#005: maps + tilesets) |
| `0x0B86AE–0x0B8A32` | `$B86AE` table, 90 records (base `0x0B8A32`) |
| `0x0B8A32–0x0CC9D8` | 90 `$DD5C` streams, contiguous (#005: palettes + 36-tile sets) |
| `0x0CC9D8–0x0CCDB8` | Master palette table, 31 palettes (#005) |

**This block is GRAPHICS** (tiles/sprites/palettes, #005) — the
`$96120`/`$B86AE` streams decode to packed 2-px/byte tiles that
render coherently. The `$DD5C` verdict for both tables is 62/62 +
90/90 clean decodes to exactly their stated lengths.

## The 0x094000–0x096120 gap — tested against all four, all rejected

The only genuinely unknown bytes in block 2 (8,320 B at
`0x094000–0x096000` + 288 high-entropy bytes at `0x096000–0x096120`).
Reference decoders: Clownacy `clownlzss` (Kosinski + Enigma) and
`clownnemesis` (Nemesis), built from source and **round-trip
validated first** on the decompressed rec-0 tilemap (Kosinski
2048 → 736 B → 2048 exact; Enigma 2048 → 1280 B → 2048 exact;
Nemesis 2048 → 1202 B → 2048 exact). Controls: feeding a known
`$DD5C` stream (`0x44228`) to each decoder establishes the
known-garbage profile.

| Codec | Result on 0x094000 (8 KB) | Result on 0x096000 (288 B) | Verdict |
|---|---|---|---|
| Nemesis | **decoder hard-fails** (exit 1, 0 bytes out) | **hard-fails** (exit 1, 0 bytes) | NOT Nemesis — the strict decoder that round-trips a real Nemesis stream rejects both outright |
| Kosinski | exit 0, 21,163 B out — but 809/1024 zero words in the first 2048 B, entropy 3.11 | exit 0, 660 B out — 300 of its 330 words zero (91%) | NOT Kosinski — output matches the known-garbage profile (known `$DD5C` stream → Kosinski gives 869/1024 zero words, entropy 1.02); a real tilemap has 44 distinct words with a few dominant tiles, not 79% zeros copied from a zero-filled window |
| Enigma | exit 0, 18,808 B out — 504 distinct words in the first 2048 B | **IO failure** (decoder ran off the end, no valid end marker) | NOT Enigma — output matches the known-garbage profile (known `$DD5C` stream → Enigma gives 322 distinct words, top value `0xEB00` ×264); a real tilemap has 44 distinct words |
| Uncompressed | packed 4bpp render = noise; planar 4bpp render = noise (nearly uniform nibble histogram); 1bpp at width 256 = bands/repeating motifs only; as a tilemap the words are invalid (`0x6666` → tile 1638, no tileset is that large) | — | NOT raw tiles / NOT a raw tilemap |
| `$DD5C` | fails at `0x94000`/`0x94100`/`0x95000`/`0x96000`/`0x96100`; no table entry points here | fails at `0x96100` | NOT `$DD5C` |

Supporting numbers: entropy of the gap is 5.0–5.5 (full 8 KB: 5.76),
far below a real compressed bitstream of the same data (Kosinski
6.97, Enigma 6.45, Nemesis 7.62). The gap's fingerprint is 4-bit
periodic words (`0x1111`, `0x6666`, `0xAAAA`, `0xDDDD`, `0xA6A6`,
`0x6A6A`, `0x0101`; nibble histogram D 25%, 0 13%, 1 9%) with 0 solid
single-byte tiles. No code references the gap (0 PC-relative
references into either gap from real code; only 14 code references
into `0x044000–0x0C0000` at all, all to the known tables/terrain
driver). **What it is remains open** — best hypotheses are a lookup
table or bitplane/font data — but all four codec hypotheses are
excluded with evidence. Same verdict for the `0x05F1C4` 864-byte
region (Nemesis hard-fail; Kosinski 1023/1024 zero words; Enigma IO
failure; entropy 3.13).

## Decoder

`tools/decode_chunks.py` — parses the `$43850` table, decompresses
all 252 records with the proven `$DD5C` decoder from
`tools/extract_text.py:dd5c_decompress`, verifies each length against
its table entry, writes `disasm/chunks/chunk_000.bin` …
`chunk_251.bin`, and renders chunks as ASCII tile-index grids.

```
tools/.venv/bin/python tools/decode_chunks.py --verify-only
tools/.venv/bin/python tools/decode_chunks.py [--render N]
```

Verification run 2026-11-09: **252/252 records decode to exactly
their table lengths, zero mismatches, streams contiguous
`0x44228–0x05EDC4`**. ROM MD5 unchanged:
`30c18fdbe2183f64702ae9f1a45d63f9`.

## Still open (not #017's codec question)

- `0x094000–0x096120` (8,608 B): structured data, purpose unknown.
  No codec fits; needs its own investigation.
- `0x05F1C4–0x05F524` (864 B): unidentified; same negative codec
  results.
- `0x068300–0x093FFF` (~172 KB): not terrain streams (those end
  ~`0x68300`) and not `$DD5C` sources — unknown, out of #017 scope.
- `0x43800–0x43850` u16 table and `$5EDC4` word-table semantics.
- Which maps use 32×32 vs 11×11 chunks (via `$1C7DA`/`$FFA7FC`
  location records).
- `disasm/map.md` correction applied: the #011 note claiming
  `0x060000–0x093FFF` is "the start of the `$96120` compressed
  streams" was wrong — the `$96120` sources start at `0x09638C`.

## Notes
- Depends on #011. Entropy 7.0–7.6 alone proves compression, not which one.
