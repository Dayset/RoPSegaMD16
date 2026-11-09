#!/usr/bin/env python3
"""Decode and draw Rings of Power (Mega Drive, 1992) tilemaps.

Tilemaps live as records in the $96120 table (ROM 0x096120, sources at
0x09638C). Each record is $DD5C-compressed (see tools/extract_text.py) and
decompresses to a row-major array of u16 tilemap entries:

    bits 0-10   tile index (offset from the tileset's VRAM base)
    bit 11      0x0800 flip-H (passes through into the VRAM word)
    bit 12      0x1000 flip-V (passes through into the VRAM word)

Maps are drawn by $1194A(src, base, rows, cols, yoff, xoff, stride, dest)
(verified from disasm/rop.s, 0x1194A-0x11A18):

    VRAM word written = map_word + base
        (base = tileset VRAM tile index + palette/priority bits:
         +$2000 palette 1, +$4000 palette 2, +$6000 palette 3,
         +$8000 priority bit, palette 0)
    dest byte address for map row r, col c:
        ((r + yoff) * stride + xoff + c) * 2 + dest
        (stride is in WORDS / tiles: $40 = 64-wide plane, $80 = 128-wide)
    Flip bits in the BASE (0x0800 / 0x1000) select reversed traversal;
    every observed call has them 0, and the flip-path arithmetic looks
    inconsistent (likely dead/generic code) -- see docs/maps.md.

Loader chain (verified): $1383C(index) loads one $96120 record and
returns its decompressed pointer in d0 (one word arg); $11ABC(count,
base, src) uploads count tiles from src to VRAM at base; $11A7C(src,
count) uploads count tiles at the running cursor $FF0076. The tileset
for each map is the record loaded with a count push immediately before
the map's own $1383C load in the same routine -- and it always matches:
the map's max tile index is exactly one less than the tileset's tile
count (rec 9 max 437 vs rec 6's 438 tiles, rec 35 max 280 vs rec 34's
281, rec 54 max 535 vs rec 53's 536, rec 57 max 289 vs rec 56's 290).

Usage (from the repo root):
    python3 tools/decode_map.py list
    python3 tools/decode_map.py stats 9
    python3 tools/decode_map.py grid 22
    python3 tools/decode_map.py draw 9 [--tileset 6] [--palette 11]
        [--rows 28 --cols 40] [--scale 3] [--out disasm/maps/world_map_rec09.png]
    python3 tools/decode_map.py draw 54 --out /tmp/rec54.png
    python3 tools/decode_map.py indexgrid 9 --out /tmp/rec09_idx.png
        (one pixel per tile, colour = hash of tile index: shows the map's
         shape independent of tiles/palette)
"""

import argparse
import hashlib
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_text import dd5c_decompress
from render_tiles import decode_tile_packed, get_palette

ROM = Path(__file__).resolve().parent.parent / "rop-original.gen"
TABLE = 0x96120
DATA_BASE = 0x9638C

# rec -> (rows, cols, tileset rec, palette index, loader address, note)
# Dimensions from $1194A call sites; tileset from the $FF86xx base register
# traced back to the $11A7C upload that set it; palette from the base's
# +$2000/+$4000/+$6000 bits and the $11082 loads in the same routine.
KNOWN = {
    9:  (28, 40, 6,  11, 0x12EA0, "world map: diamond of Ushka Bau + compass rose"),
    13: (8,  40, 12, None, 0x14A4E, "8-row strip, text/scene screen"),
    14: (8,  40, 12, None, 0x14A12, "8-row strip, drawn x7 as bands at yoff 8..56"),
    15: (8,  40, 12, None, 0x14BCE, "8-row strip, text/scene screen"),
    22: (21, 38, 21, 15, 0x15ECE, "title logo layer 1 (arg==0): 'RING'"),
    23: (21, 9,  21, 15, 0x15F14, "title logo layer 1: 'O'"),
    24: (7,  8,  21, 15, 0x15F5A, "title logo layer 1: 'F'"),
    25: (21, 21, 21, 15, 0x15FA0, "title logo layer 1: 'P'"),
    26: (21, 35, 21, 15, 0x15FE6, "title logo layer 1: 'OWER'"),
    35: (28, 40, 34, 30, 0x17954, "full-screen map, alt. to rec 9 in routine 0x17860"),
    39: (24, 40, 37, None, 0x18818, "landscape picture (mountains/forest/snow), yoff 40"),
    40: (8,  40, 37, None, 0x187D8, "8-row strip above rec 39 (variable yoff)"),
    43: (9,  32, 42, None, 0x180C2, "small map at runtime (d6,d7) position"),
    44: (7,  8,  42, None, 0x18116, "small map at runtime (d6,d7) position"),
    48: (21, 38, 21, 15, 0x16036, "title logo layer 2 (arg==1): 'RING' variant"),
    49: (21, 9,  21, 15, 0x1607C, "title logo layer 2: 'O' variant"),
    50: (7,  8,  21, 15, 0x160C2, "title logo layer 2: 'F' variant"),
    51: (21, 21, 21, 15, 0x16108, "title logo layer 2: 'P' variant"),
    52: (21, 35, 21, 15, 0x1614E, "title logo layer 2: 'OWER' variant"),
    54: (25, 40, 53, 17, 0x18D6C, "location picture: stone archway/trellis, yoff 2"),
    57: (21, 27, 56, 27, 0x18858, "location picture: castle, yoff 43 xoff 4"),
}


def read_rom():
    return open(ROM, "rb").read()


def record_bytes(data, n, table=TABLE, base=DATA_BASE):
    ptr, ln, typ = struct.unpack_from(">IIH", data, table + n * 10)
    out, _used = dd5c_decompress(data, base + ptr, max_out=200000)
    return out


def map_words(data, n):
    b = record_bytes(data, n)
    return struct.unpack(">%dH" % (len(b) // 2), b)


def tile_indices(words):
    return [w & 0x07FF for w in words]


def cmd_list(_args):
    print("tilemap records in the $96120 table (from $1194A call sites):")
    print(" rec  rows x cols  tileset  pal  loader   note")
    for n in sorted(KNOWN):
        rows, cols, ts, pal, loader, note = KNOWN[n]
        print(f" {n:3d}  {rows:2d} x {cols:<3d}  {ts:<7d}  "
              f"{str(pal) if pal is not None else '?':<4} 0x{loader:05X}  {note}")


def cmd_stats(args):
    data = read_rom()
    w = map_words(data, args.rec)
    idx = tile_indices(w)
    print(f"rec {args.rec}: {len(w)} words "
          f"({len(w)} = rows*cols if the map is rectangular)")
    print(f"  tile index range {min(idx)}..{max(idx)}, "
          f"{len(set(idx))} distinct")
    print(f"  flip-H entries: {sum(1 for x in w if x & 0x800)}, "
          f"flip-V entries: {sum(1 for x in w if x & 0x1000)}")
    print(f"  most common tiles: {Counter(idx).most_common(8)}")
    if args.rec in KNOWN:
        rows, cols, ts, pal, loader, note = KNOWN[args.rec]
        print(f"  known: {rows}x{cols} into tileset rec {ts} "
              f"(palette {pal}), loader 0x{loader:05X} -- {note}")
        ts_bytes = record_bytes(data, ts)
        print(f"  tileset rec {ts} has {len(ts_bytes) // 32} tiles; "
              f"max index {max(idx)} "
              f"{'fits' if max(idx) < len(ts_bytes) // 32 else 'EXCEEDS tileset!'}")


def cmd_grid(args):
    data = read_rom()
    w = map_words(data, args.rec)
    rows, cols = args.rows, args.cols
    if rows is None or cols is None:
        if args.rec in KNOWN:
            rows, cols = KNOWN[args.rec][0], KNOWN[args.rec][1]
        else:
            raise SystemExit("give --rows and --cols (record not in KNOWN table)")
    if rows * cols != len(w):
        print(f"warning: {rows}x{cols}={rows * cols} != {len(w)} words",
              file=sys.stderr)
    for r in range(rows):
        row = w[r * cols:(r + 1) * cols]
        print(" ".join(f"{x & 0x7FF:3d}" for x in row))


def _draw(args, tileset_bytes, pal_rgb, scale, rows, cols):
    data = read_rom()
    w = map_words(data, args.rec)
    from PIL import Image
    img = Image.new("RGB", (cols * 8 * scale, rows * 8 * scale), (0, 0, 0))
    px = img.load()
    for r in range(rows):
        for c in range(cols):
            entry = w[r * cols + c]
            ti = entry & 0x07FF
            fh = bool(entry & 0x0800)
            fv = bool(entry & 0x1000)
            if ti * 32 + 32 > len(tileset_bytes):
                continue
            t = decode_tile_packed(tileset_bytes, ti * 32)
            for y in range(8):
                for x in range(8):
                    sx = 7 - x if fh else x
                    sy = 7 - y if fv else y
                    col = pal_rgb[t[sy * 8 + sx]]
                    for py in range(scale):
                        for qx in range(scale):
                            px[c * 8 * scale + x * scale + qx,
                               r * 8 * scale + y * scale + py] = col
    img.save(args.out)
    print(f"saved {args.out} ({img.size[0]}x{img.size[1]})")


def cmd_draw(args):
    data = read_rom()
    rows, cols, ts, pal = args.rows, args.cols, args.tileset, args.palette
    if args.rec in KNOWN:
        krows, kcols, kts, kpal = KNOWN[args.rec][:4]
        rows = rows if rows is not None else krows
        cols = cols if cols is not None else kcols
        ts = ts if ts is not None else kts
        pal = pal if pal is not None else kpal
    if rows is None or cols is None or ts is None:
        raise SystemExit("need rows/cols/tileset (record not in KNOWN table?)")
    if pal is None:
        raise SystemExit("no palette known for this record -- pass --palette N")
    _draw(args, record_bytes(data, ts), get_palette(data, pal), args.scale,
          rows, cols)


def cmd_indexgrid(args):
    data = read_rom()
    w = map_words(data, args.rec)
    rows, cols = args.rows, args.cols
    if rows is None or cols is None:
        if args.rec in KNOWN:
            rows, cols = KNOWN[args.rec][0], KNOWN[args.rec][1]
        else:
            raise SystemExit("give --rows and --cols")
    from PIL import Image
    s = args.scale
    img = Image.new("RGB", (cols * s, rows * s), (0, 0, 0))
    px = img.load()
    for r in range(rows):
        for c in range(cols):
            h = hashlib.md5(str(w[r * cols + c] & 0x7FF).encode()).digest()
            col = (h[0], h[1], h[2])
            for y in range(s):
                for x in range(s):
                    px[c * s + x, r * s + y] = col
    img.save(args.out)
    print(f"saved {args.out} ({img.size[0]}x{img.size[1]})")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list known tilemap records")
    s = sub.add_parser("stats", help="word/index stats for a record")
    s.add_argument("rec", type=int)
    s.set_defaults(fn=cmd_stats)
    s = sub.add_parser("grid", help="print the u16 grid as text")
    s.add_argument("rec", type=int)
    s.add_argument("--rows", type=int)
    s.add_argument("--cols", type=int)
    s.set_defaults(fn=cmd_grid)
    s = sub.add_parser("draw", help="render a tilemap to PNG")
    s.add_argument("rec", type=int)
    s.add_argument("--rows", type=int)
    s.add_argument("--cols", type=int)
    s.add_argument("--tileset", type=int)
    s.add_argument("--palette", type=int)
    s.add_argument("--scale", type=int, default=2)
    s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_draw)
    s = sub.add_parser("indexgrid", help="one pixel per tile, colour = tile index")
    s.add_argument("rec", type=int)
    s.add_argument("--rows", type=int)
    s.add_argument("--cols", type=int)
    s.add_argument("--scale", type=int, default=12)
    s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_indexgrid)
    sub.choices["list"].set_defaults(fn=cmd_list)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
