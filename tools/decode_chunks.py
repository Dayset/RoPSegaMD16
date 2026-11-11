#!/usr/bin/env python3
"""Issue #017 — decode the $43850 chunk table (block 0x044000-0x05FFFF).

VERDICT (2026-11-09): neither high-entropy block is a new codec.
Both blocks are the already-proven $DD5C LZSS codec (#004/#005), plus
tables and two small unidentified regions. Nemesis, Kosinski and
Enigma were all tested against the genuinely unknown bytes and
rejected — see the evidence table in issues/017-compression.md.

Block 1 — 0x044000-0x05FFFF (112 KB):
  0x43800-0x43850  u16 values, +4 steps in groups of 8 (unidentified)
  0x43850-0x44228  $43850 table: 252 records [u32 off, u32 declen, u16 type=1]
                   offsets are RELATIVE to data base 0x44228
  0x44228-0x05EDC4 252 $DD5C streams (contiguous, no gaps):
                   99 x 2048 B = 32x32 tilemap chunks (recs 0-76, 230-251)
                   153 x 242 B = 11x11 tilemap chunks (recs 77-229)
  0x05EDC4-0x05F1C4 $5EDC4: 512-word table (per-tile properties, likely)
  0x05F1C4-0x05F524 864 B unidentified
  0x05F524-0x060000 $5F524 terrain offset table: 176 u32 offsets;
                   streams at 0x603E4+, last ends ~0x68300
  (0x068300-0x093FFF is out of #017 scope, still unknown.)

Block 2 — 0x094000-0x0CBFFF (224 KB):
  0x094000-0x096120 8,608 B unidentified structured data (see below)
  0x096120-0x09638C $96120 table: 62 records (base 0x09638C)
  0x09638C-0x0B86AE 62 $DD5C streams, contiguous (#005: maps + tilesets)
  0x0B86AE-0x0B8A32 $B86AE table: 90 records (base 0x0B8A32)
  0x0B8A32-0x0CC9D8 90 $DD5C streams, contiguous (#005: palettes + tiles)
  0x0CC9D8-0x0CCDB8 master palette table, 31 palettes (#005)

The 0x094000-0x096120 gap is NOT any tested codec: Nemesis decoder
hard-fails (exit 1, 0 bytes); Kosinski decodes to 79% zero words (the
same garbage signature as feeding a known $DD5C stream to Kosinski);
Enigma decodes to 504 distinct words (a real tilemap has 44); $DD5C
fails at 0x94000/0x94100/0x95000/0x96000/0x96100; packed/planar tile
renders are noise and the words (0x1111/0x6666/0xAAAA...) are not valid
tile indices (0x6666 -> tile 1638, no tileset is that large). Entropy
5.0-5.5 is far below a real compressed bitstream (Kosinski 6.97,
Enigma 6.45, Nemesis 7.62 on the same data). Reference decoders used:
Clownacy clownlzss (Kosinski + Enigma) and clownnemesis (Nemesis),
both round-trip validated on the decompressed rec-0 tilemap before use.

Chunk format (both sizes): big-endian u16 words, packed tile-type +
flags — NOT VDP tilemap format (corrected 2026-11-11; the earlier
VDP reading is wrong). Bits 0-8 tile-type index (0-511), bit 9 height-stack
flag, bit 10 step-tile flag (world_step_tile, tiles 0x107/0x108),
bit 11 hazard floor (damaging ground), bit 12 variant flag,
bits 13-15 height / row count (0-7). The 2048-byte records use 307 distinct tile-type
indices; the 242-byte records use 211, all within 0-511. Display goes
through the $1AE98 descriptor table (tile-type -> 0-63 tile + flips,
within the tileset loaded at the $FF8678 base), properties through
$5EDC4. Loaded by $19692 (4-slot round-robin cache, buffers $FF868C +
slot*2048) via the lazy getter $1C802; chunk index comes from
$1C7DA/$1C83E (position / location-record words).

Usage:
  tools/.venv/bin/python tools/decode_chunks.py [--rom PATH]
      [--outdir DIR] [--render INDEX] [--verify-only]
  --verify-only : decode every record in memory, check each
      decompressed length against its table length, print the summary.
      Default also writes chunk_000.bin .. chunk_251.bin to --outdir
      (default disasm/chunks/) and renders rec 0 (32x32) + rec 77 (11x11)
      as ASCII tile-index grids.
"""

import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_text import dd5c_decompress  # noqa: E402  ($DD5C LZSS, #004)

ROM_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "rop-original.gen")
TABLE_ADDR = 0x43850
DATA_BASE = 0x44228
N_RECORDS = 252


def parse_table(rom):
    """Return [(index, src_offset, declen, type)] for the $43850 table."""
    recs = []
    for i in range(N_RECORDS):
        off, ln, typ = struct.unpack_from(">IIH", rom, TABLE_ADDR + i * 10)
        recs.append((i, off, ln, typ))
    return recs


def decode_record(rom, rec):
    """Decompress one record; returns (bytes, bytes_consumed)."""
    idx, off, declen, _typ = rec
    out, used = dd5c_decompress(rom, DATA_BASE + off)
    return out, used


def verify_all(rom):
    """Decode every record, check length vs table; return (ok, summary)."""
    recs = parse_table(rom)
    sizes = {}
    bad = []
    total_src = 0
    for rec in recs:
        idx, off, declen, typ = rec
        out, used = decode_record(rom, rec)
        if typ != 1:
            bad.append((idx, "type != 1: %d" % typ))
        if len(out) != declen:
            bad.append((idx, "len %d != table %d" % (len(out), declen)))
        sizes[declen] = sizes.get(declen, 0) + 1
        total_src += used
    # contiguity: each stream must start where the previous ended
    gaps = []
    prev_end = 0
    for idx, off, declen, _typ in recs:
        if off != prev_end:
            gaps.append((idx, off, prev_end))
        _out, used = decode_record(rom, recs[idx])
        prev_end = off + used
    return recs, sizes, bad, gaps, total_src, prev_end


def render_grid(data, width, label):
    """Render a tilemap chunk as hex tile indices (low byte) + flag note."""
    nwords = len(data) // 2
    words = struct.unpack(">%dH" % nwords, data[: nwords * 2])
    lines = ["%s (%d words, %dx%d):" % (label, nwords, width, nwords // width)]
    for r in range(nwords // width):
        row = words[r * width:(r + 1) * width]
        lines.append("  " + " ".join("%02X" % (w & 0xFF) for w in row))
    flags = sorted(set(w & 0xF800 for w in words))
    lines.append("  flag-bits used: %s" % ", ".join("0x%04X" % f for f in flags))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rom", default=ROM_DEFAULT)
    ap.add_argument("--outdir", default=None,
                    help="write chunk_NNN.bin here (default: disasm/chunks/)")
    ap.add_argument("--render", type=int, default=None,
                    help="render one record index as an ASCII grid")
    ap.add_argument("--verify-only", action="store_true")
    args = ap.parse_args()

    rom = open(args.rom, "rb").read()
    recs, sizes, bad, gaps, total_src, stream_end = verify_all(rom)

    print("$43850 table: %d records" % len(recs))
    print("  decompressed sizes: %s"
          % ", ".join("%d x %d B" % (n, s) for s, n in sorted(sizes.items())))
    print("  streams: 0x%06X-0x%06X (%d B compressed, contiguous: %s)"
          % (DATA_BASE, DATA_BASE + stream_end, stream_end,
             "yes" if not gaps else "NO gaps=%r" % (gaps,)))
    print("  length/type mismatches: %s" % ("none" if not bad else bad))
    big = [r for r in recs if r[2] == 2048]
    small = [r for r in recs if r[2] == 242]
    print("  32x32 chunks: recs %d-%d and %d-%d"
          % (big[0][0], big[76][0], big[77][0], big[-1][0]))
    print("  11x11 chunks: recs %d-%d" % (small[0][0], small[-1][0]))

    if args.verify_only:
        return 0 if not bad and not gaps else 1

    outdir = args.outdir
    if outdir is None:
        outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "..", "disasm", "chunks")
    os.makedirs(outdir, exist_ok=True)
    for rec in recs:
        out, _used = decode_record(rom, rec)
        with open(os.path.join(outdir, "chunk_%03d.bin" % rec[0]), "wb") as f:
            f.write(out)
    print("  wrote %d chunks to %s" % (len(recs), outdir))

    for idx in ([0, 77] if args.render is None else [args.render]):
        out, _used = decode_record(rom, recs[idx])
        width = 32 if len(out) == 2048 else 11
        print(render_grid(out, width, "rec %d" % idx))
    return 0 if not bad and not gaps else 1


if __name__ == "__main__":
    sys.exit(main())
