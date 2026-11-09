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
