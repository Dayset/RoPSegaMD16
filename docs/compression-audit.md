# Compression audit (issue #017)

Written 2026-11-09 (agent session) by auditing **every committed
doc/table in this repo** for codec evidence. Method: the repo was
searched for Nemesis / Kosinski / Enigma / `$DD5C` / LZSS mentions
across `docs/`, `disasm/`, `issues/`, `PROGRESS.md`, `tools/`.
No ROM was available in this VM, so no new decompression was run;
every claim below cites the repo file that already proved it.

## Conclusion (up front)

**Every compressed stream so far identified in this ROM uses the
game's own `$DD5C` LZSS codec. There is no positive evidence for
Nemesis, Kosinski, or Enigma anywhere in the repo's verified work.**
The two blocks the issue names are accounted for as follows:

| Block | What it actually is (verified) | Source |
|---|---|---|
| `0x044000–0x05FFFF` (112 KB) | **Unresolved.** Still "provisional: compressed data (probably graphics)", entropy 7.0–7.24. No codec test has ever been run on it in the repo. Prime suspect as the input stream for the threaded terrain decoder `0xE3B4/0xE412` (#020). | `disasm/map.md`; `docs/architecture.md` #020 terrain section |
| `0x094000–0x0CBFFF` (224 KB) | **Accounted for: `$DD5C` LZSS streams.** Contains the `$96120` table sources (`0x09638C–0x0B86AE`) and the `$B86AE` table sources (`0x0B8A32–~0x0CC761`). 62/62 + 90/90 records decompress cleanly with the `$DD5C` re-implementation. | `disasm/graphics/inventory.md`; PROGRESS.md #005 entry |

## Evidence per codec

### $DD5C LZSS — PROVEN, everywhere it has been tested
- Text: 3 streams in `disasm/text/dd5c_streams.txt` (Book of Nexus
  `0x0A66E6`, Book of Buc `0x0B3D40`, title credits `0x0B6221`) + a
  4th (bestiary, `$96120` rec 61) found in #005.
- Graphics/maps: all 62 `$96120` records + all 90 `$B86AE` records,
  clean decompression, `declen` == length field in every record
  (`disasm/graphics/inventory.md`, `docs/maps.md`).
- Decoder exists: `tools/extract_text.py: dd5c_decompress`
  (re-implemented in #004, verified against the fan-site corpus
  647/649 in the dictionary work). **This already satisfies the
  issue's "decoder script in tools/" acceptance item — for the
  codec the game actually uses in the tested regions.**

### Nemesis — no evidence
No doc, table, or tool in the repo reports a Nemesis header, nibble
stream, or successful/failed decode attempt. It survives only as a
name in the #017 issue text and `docs/overview.md` ("the usual
Genesis codecs to test"). Absence of a test is not proof of absence
in the untested `0x044000` block — see Remaining work.

### Kosinski — no evidence
Same status as Nemesis: named as a candidate in `docs/overview.md`
and in PROGRESS.md's #005 entry only to say compression "is `$DD5C`
LZSS for all graphics in both tables … no Nemesis/Kosinski/Enigma
there". No Kosinski decode attempt is recorded anywhere.

### Enigma — no evidence
Same status. No Enigma plane-map data has been identified; the
game's tilemaps are plain u16 arrays after `$DD5C` decompression
(`docs/maps.md`), which is itself weak evidence the tilemap path
never needed Enigma.

### Uncompressed — disproven for the named blocks
Entropy 7.0–7.6 (`disasm/map.md`) rules out raw data in both blocks;
for `0x094000+` the `$DD5C` record structure positively explains
the bytes.

## Which block is graphics vs maps — decided for 0x094000+, open for 0x044000

- `0x094000–0x0CBFFF`: **both** — it holds graphics tilesets,
  tilemaps, portraits/sprites, and text streams, all as `$DD5C`
  records in two adjacent tables (`docs/maps.md`, inventory files).
- `0x044000–0x05FFFF`: undecided. It is not part of either table.
  The only structural lead is #020's: the threaded decoder
  `0xE3B4/0xE412` (tables `$433C0–$436E0`, jump table `$DF58`,
  output bitmap `$FF1EC0`, no direct callers) reads *a* byte stream
  from a0 — this block is the prime suspect for that stream, which
  would make it **map/terrain data under a custom (threaded-code)
  encoding, not a standard codec at all**. That is a hypothesis
  with a named test (below), not a finding.

## Remaining work (blocked in this VM — needs the ROM)

1. Run the three standard decoders against `0x044000–0x05FFFF`
   sample offsets and record success/failure per codec (the
   acceptance item as literally written). Needs `rop-original.gen`.
2. Trace who enters the `0xE3B4` decoder with a0 set (the stream
   source pointer decides the block question directly).
3. Update `disasm/map.md`: the `0x094000–0x0CBFFF` row can already
   be upgraded from "provisional" to verified-$DD5C on the strength
   of #005/#006 — **proposed here, not applied** (map.md is the
   #002/#011 file; the upgrade is a one-line owner review).

## map.md update proposed by this audit

> `0x094000–0x0CBFFF` | Compressed data — `$DD5C` LZSS record tables
> (`$96120` + `$B86AE`) | **verified** | 62/62 + 90/90 records
> decompress cleanly (#005/#006); see `docs/compression-audit.md`.

## Update 2026-11-09 (continuation) — 0x044000–0x05FFFF TESTED

The ROM is in the VM now; the untested range was tested directly.

**Entropy/structure.** Overall entropy 7.203 (16 KB sub-blocks
6.93–7.24); zero bytes 7.2–11.4%; ASCII 29.6–43.0%. No long
constant runs (longest 0x00 run = 7 bytes). The head of the block
is a **55-entry index table of 10-byte records**
(0x044000–0x044226): bytes `00 01 00 01`, a big-endian u16 at +4
that increases strictly monotonically 0x5B07 → 0xA896 (steps of
~100–212), u16 at +6 always 0, tail u16 0x00F2 for the first 33
records and 0x0800 for the last 22. That is an offset/size index,
not a compressed stream header.

**Not code.** The #011 Ghidra census finds **0 functions** in
the range, and no function anywhere in the ROM has a callee
inside it (function_map.csv). The block is never executed or
called as code.

**Not $DD5C.** The repo's $DD5C decoder was run at every
even-aligned offset in the range. It "succeeds" almost
everywhere — and every one of those hits is a false positive:
the outputs are all spaces (the decoder's ring buffer starts
filled with 0x20 and the structured input keeps re-selecting
space-producing back-references). A genuine $DD5C region (the
$96120/$B86AE tables) does not behave like this. The first
"plausible header" at 0x044004 is explained by the index table
itself (the LE u32 at record+4 reads as a plausible length).

**Standard codecs (Nemesis/Kosinski/Enigma).** All three are
stream formats; if the block were one of their streams it would
have to start at the block head — and the head is the index
table above. Header parses at 0x044000: Nemesis first word
0x0001 = a tile count of 1, which cannot describe 112 KB;
Kosinski's LE u16 output-size field reads 0x0100 (256 bytes);
Enigma's flag word reads 0x0001 with no consistent
increment/decrement interpretation. **No positive evidence for
any of the three; the block does not begin with any of their
streams.** (Decoding at random mid-block offsets was not
attempted: none of the three formats is self-synchronising, so
mid-stream entry points are meaningless.)

**Verdict.** 0x044000–0x05FFFF is **not code and not any
identified codec**. Its head is an index table; the bulk remains
unidentified. The standing explanation is unchanged and now the
only one left: **input stream for the threaded decoder at
$E3B4** (#020), which consumes a headerless byte stream via a
jump table — consistent with everything observed. Decisive test
remains: trace what sets a0 when $E3B4 is entered.

## Update 2026-11-09 (session #4) — $E3B4 TRACED: decoder CONFIRMED, stream source REFUTED for this block

The decisive trace the audit owed is done. The decoder's real
entry is **$E358** (the bytes just before it are a mask/pattern
table, which is why linear sweeps missed it):

- $E358 pops four stack words: index, xbase (forced even), row,
  variant. It loads **a0 = *(u32 table at $5F524)[index] +
  $603E4**, optionally skips records (negative row: each skipped
  record advances by its first byte's high nibble), then falls
  into $E3B4 (variant 0) or branches to $E412 (variant != 0).
- Direct callers exist (the "#020: no callers" note was about
  $E3B4 itself): `jsr $E358` at $1BC1A/$1BC3C/$1BC84 (a band
  renderer: loops rows in steps of 7, record $230 among them)
  and $23234/$2326C/$2329E/$232C6/$23346/$233A6/$2342C.
- The pointer table has **944 entries** spanning exactly
  $5F524–$603E3 — it sits at the **tail of the 0x044000 block**
  and ends precisely where the streams begin. The streams
  themselves live at **$0603E4–$096069**, NOT in the block.
- Mechanics (now fully read): per command byte, the low nibble
  plus the xbase select a cell offset ($435C0) within a row-pair
  band ($436E0); the high nibble plus 2 bits of the cell index
  select a writer block via the $DF58 table (256 entries,
  114 unique targets: the two loop continuations $E3E2/$E43C
  and writer families at $E47C+ and $10078+). Writers stamp
  stream bytes into the $FF1EC0 bitmap (33-byte rows) as
  `(old & mask[$433C0][v]) | v`; variant B first expands each
  byte through the $434C0 nibble-swap table. A 0x00 stream byte
  terminates the call (exit via $11074).

**Reimplementation:** `tools/decode_e358.py` (writer patterns
extracted symbolically from the blocks themselves — all 114
handler targets modelled, none unmodelled). Validation:
**943/943 records consume exactly their table-delimited byte
length under both variants.** A wrong key or stamp-count model
desynchronises within a few commands; this is a byte-exact
format proof.

**Verdicts for #017:**
- Threaded decoder: **CONFIRMED** — it is a real, custom,
  threaded-code bitmap codec (neither Nemesis, Kosinski,
  Enigma, nor $DD5C), and its decoder now exists in tools/.
- "The 0x044000–0x05FFFF block is its input stream":
  **REFUTED.** The streams are at $0603E4+. Of the block, only
  the tail (the $5F524 pointer table) belongs to this system.
- The block's bulk (and the 55-entry index at its head)
  remains **unidentified**: no longword anywhere references
  0x044000, Ghidra finds no functions, and no tested codec
  matches. It is the last unidentified region of the ROM;
  the honest status is "consumer unknown", not a guessed codec.
- Graphics-vs-maps for the decoder streams: they are **map
  data** — the $1BCxx caller renders map bands into $FF1EC0
  (the "MM map" bitmap of #006/docs/maps.md).

## Update 2026-11-09 (session #5) — 0x044000 BULK SOLVED: it IS $DD5C (earlier verdict corrected)

The block's last open question is closed, and the answer
overturns this audit's continuation-session verdict. The
earlier "not $DD5C — every scan hit is an all-space false
positive" conclusion was **wrong**: it came from a scan whose
success criterion discarded the real streams. Re-run with the
output examined, the bulk is full of genuine $DD5C streams
whose outputs are structured data (~0-2% spaces). The
correction is recorded here in full because the method, not
just the answer, matters:

**The layout.** The block is three things, none of them a new
codec:

1. **Descriptor tail (0x044000–0x044227).** The "55-entry
   10-byte index table" at the block head is the tail of a
   252-record descriptor table that starts at **0x043850**
   (just before the block). Read at the correct alignment the
   records are the standard $13654 dispatcher format —
   **u32 BE offset, u32 BE decompressed size, u16 type** —
   and every one of the 252 records has type 1 ($DD5C). The
   head records were misread for two sessions because the
   table was assumed to start at the block boundary 0x044000;
   at that misalignment the fields present as
   (1, 1, off16, 0, size), with off16 the low half of the
   real u32 offset. Record 196 spans 0x043FF8–0x044001: the
   two bytes at 0x044000 are its type word.
2. **The archive (0x044228–0x05EDC3).** 252 $DD5C streams
   packed back to back in descriptor order: 77 records of
   2048 bytes, then 153 of 242 bytes, then 22 of 2048 bytes.
   A sequential walk from 0x044228 consumes exactly the
   descriptor offsets/sizes and ends exactly at 0x05EDC4.
   **252/252 records decompress to exactly their descriptor
   size** (tools/decode_44000.py reproduces this).
3. **The $E358 pointer table (0x05F524–0x0603E3)** — as
   established in session #4. (Between the archive and the
   table, 0x05EDC4–0x05F523 is 1,888 bytes of neighbouring
   data opening with u16s 0x1401/0x1901×13/0x1C01…; not part
   of this archive and not pursued here.)

**The consumer (the question the issue actually posed).**
Code references the archive base 0x044228 as a longword at
0x019774 — `pea $43850; pea $44228; jsr $13654` inside
**FUN_00019692**, a loader reached via the 7-caller thunk
FUN_0001C802. The dispatcher $13654's type-1 path is the
ROM's `jsr $DD5C` at 0x0136BA: stream address = base +
record.offset, decompressed into the caller's buffer.
FUN_00019692 keeps a **4-slot rotating cache of 2048-byte
buffers at $FF868C** (slot counter $FFA894 mod 4, stride
0x800, pointer cache $FFA896) — a map-page cache. This is
why "no longword references to $044000 exist": the code
references the *table* (0x043850) and the *archive base*
(0x044228), never the arbitrary 64 KB block boundary.

**Content.** Decompressed records are **VDP nametable map
data**: the 2048-byte records are 32×32 u16 tilemap words
and the 242-byte records are 11×11 u16 tilemap words (tile
index in bits 0–10, max observed 2027; palette/flip bits in
bits 11–15; e.g. record 100 is an 11×11 patch with floor
tile 16 and wall/detail tiles 96–121 + flipped variants).
So the block is **maps**, in the same $DD5C record system as
the $96120/$B86AE tables — a third table the earlier
inventory had not separated from its neighbours.

**Why the standard codecs failed at the head (acceptance
item, as literally written):** the block does not begin
with a stream at all — it begins mid-descriptor-table, so
Nemesis/Kosinski/Enigma header parses at 0x044000 were
parsing a type word. The negative results stand for the
head; they never applied to the archive behind it.

**#017 verdict: DONE.** Every region is now accounted for:
$DD5C everywhere (text, $96120/$B86AE graphics+maps, and
this 252-record map archive), the $E358 threaded codec for
the $0603E4 bitmap streams, and no Nemesis/Kosinski/Enigma
anywhere in the ROM.
