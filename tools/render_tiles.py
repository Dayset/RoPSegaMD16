#!/usr/bin/env python3
"""Render Mega Drive 4bpp tiles from Rings of Power to PNG.

Usage:
    python3 tools/render_tiles.py <record|sprite|raw> <spec> [options]

  record mode:  render_tiles.py record <N> [--palette P] [--out FILE]
                [--cols C] [--scale S] [--tile-first F] [--tile-count K]
                Decompresses $96120 record N ($DD5C LZSS) and renders it
                as 8x8 4bpp tiles.
  sprite mode:  render_tiles.py sprite <N> [--palette P] [--out FILE] ...
                Decompresses $B86AE record N ($DD5C LZSS, 90 records).
                Each record is [32-byte palette][36 tiles]; by default
                the record's own embedded palette is used (pass --palette
                to override with a table palette).
  raw mode:     render_tiles.py raw <ROM_OFFSET> <BYTES> [--palette P] ...
                Renders raw ROM bytes at the offset as tiles.

Tile layout (issue #005, VERIFIED): the decompressed bytes are PACKED,
2 pixels per byte, high nibble first: byte b at row r, position k gives
pixels (b >> 4) then (b & 15) at x = 2k, 2k+1. This is the layout that
renders coherent graphics -- a character portrait ($B86AE rec 0) shows
a face, $96120 rec 0 shows the "MORE" UI text and font, rec 6 shows
terrain -- and it matches what BlastEm's VRAM debugger displays for
the same data on the live logo screen. Byte statistics confirm it:
62.6% of $B86AE rec 0 tile bytes have hi==lo nibble (solid 2-pixel
runs), vs ~6% expected for bitplane data.

PARADOX (RESOLVED in #016, see docs/graphics.md §7): the textbook Mega
Drive VDP pattern format is bitplanar, and the upload path ($1383C ->
$11A7C -> $DA04 DMA, $11AE4 -> $11B2E -> $DA04 DMA) shows NO
packed->planar conversion -- because there is none to find. Live
BlastEm VRAM snapshots (harness 2) show the decompressed tile bytes
arrive in VRAM byte-identical, and a minimal VDP test ROM proves the
VDP consumes them as packed (2 px/byte, hi nibble first): a packed
tile displays as the intended glyph, an interleaved planar copy of the
same tile displays as its packed reading. The game's tile format IS
packed; the textbook "bitplanar" description is the thing that needs
re-verification, not the data. --layout planar / planar-seq are kept
for comparison; they render the same data as vertical bars / noise.

Palettes come from the master table at ROM 0x0CC9D8 (31 palettes x 16
colours, 9-bit BGR words: 0BBB0GGG0RRR0). --palette N selects table entry
N (default 1). --palette raw:R,G,B,... uses explicit RGB triples.
--palette grey uses a greyscale ramp (pixel value -> brightness).

Palette word -> RGB: r = (w >> 1) & 7, g = (w >> 5) & 7, b = (w >> 9) & 7,
each channel scaled x * 255 // 7. (Corrected in #016: the old order had
r and b swapped; proven by the minimal VDP test ROM, which writes
CRAM[1] = 0x0E00 and shows it as pure blue, and by the $B86AE rec 0
embedded palette decoding to warm skin tones only under this order.)

Palette loading is $11082(table_ptr, slot) -> 16 words into CRAM; the
title screen ($11E06) loads table pal 10 -> slot 0 and pal 0 -> slot 1.
$B86AE records carry their own 16-word palette in the first 32 bytes,
loaded by $11AE4 via $11082($FF1EC0, slot).
"""
import argparse
import struct
import sys

from PIL import Image

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from extract_text import dd5c_decompress

ROM_PATH = "rop-original.gen"
PALETTE_TABLE = 0x0CC9D8
N_PALETTES = 31


def load_rom(path=ROM_PATH):
    with open(path, "rb") as f:
        return f.read()


def md_word_to_rgb(w):
    """Mega Drive CRAM word -> (R, G, B) 0-255.

    CORRECTED in #016 (was r=(w>>9)&7, b=(w>>1)&7 -- R and B swapped).
    Proof: the minimal VDP test ROM (.scratch016/vdp_test.s) writes
    CRAM[1] = 0x0E00 and CRAM[7] = 0x000E; on screen, pixel value 1
    displays as pure BLUE (0,0,255) and pixel value 5 (word 0x00E0)
    as pure GREEN. So bits 9-11 are BLUE and bits 1-3 are RED:
    R = bits 1-3, G = bits 5-7, B = bits 9-11. Corroborated by the
    $B86AE rec 0 embedded palette, which decodes to warm browns/reds
    (skin tones) only under this order; under the old order it is all
    blues/greens. NOTE: PNGs rendered by #005 with the old order have
    red and blue swapped (shapes are correct; colours are not)."""
    r = (w >> 1) & 7
    g = (w >> 5) & 7
    b = (w >> 9) & 7
    return (r * 255 // 7, g * 255 // 7, b * 255 // 7)


def get_palette(data, n):
    if n < 0 or n >= N_PALETTES:
        raise ValueError("palette %d out of range 0-%d" % (n, N_PALETTES - 1))
    off = PALETTE_TABLE + n * 32
    words = struct.unpack_from(">16H", data, off)
    return [md_word_to_rgb(w) for w in words]


def get_palette_words(data, n):
    off = PALETTE_TABLE + n * 32
    return struct.unpack_from(">16H", data, off)


def decode_tile_packed(data, off):
    """One 8x8 tile, PACKED layout: 2 pixels/byte, high nibble first."""
    px = []
    for r in range(8):
        for k in range(4):
            b = data[off + r * 4 + k]
            px.append(b >> 4)
            px.append(b & 15)
    return px


def decode_tile_packed_lo(data, off):
    """Packed, low nibble first (for comparison; renders mirrored pairs)."""
    px = []
    for r in range(8):
        for k in range(4):
            b = data[off + r * 4 + k]
            px.append(b & 15)
            px.append(b >> 4)
    return px


def decode_tile_planar(data, off):
    """One 8x8 tile, planar interleaved (textbook VDP format).

    8 rows x 4 bytes; row r bytes are the 4 bitplanes, bit 7 = leftmost
    pixel. pixel = b0 | b1<<1 | b2<<2 | b3<<3.
    """
    px = []
    for r in range(8):
        b0, b1, b2, b3 = data[off + r * 4: off + r * 4 + 4]
        for x in range(8):
            bit = 7 - x
            px.append(((b0 >> bit) & 1) | (((b1 >> bit) & 1) << 1)
                      | (((b2 >> bit) & 1) << 2) | (((b3 >> bit) & 1) << 3))
    return px


def decode_tile_planar_seq(data, off):
    """One 8x8 tile, planar sequential (plane-major: 8 bytes/plane)."""
    px = []
    for r in range(8):
        for x in range(8):
            bit = 7 - x
            px.append(((data[off + r] >> bit) & 1)
                      | (((data[off + 8 + r] >> bit) & 1) << 1)
                      | (((data[off + 16 + r] >> bit) & 1) << 2)
                      | (((data[off + 24 + r] >> bit) & 1) << 3))
    return px


DECODERS = {
    "packed": decode_tile_packed,
    "packed-lo": decode_tile_packed_lo,
    "planar": decode_tile_planar,
    "planar-seq": decode_tile_planar_seq,
}


def render_tiles(tile_bytes, palette, cols=16, scale=8, first=0, count=None,
                 gap=1, transparent=False, layout="packed"):
    """tile_bytes: bytes, multiple of 32. Returns a PIL Image."""
    dec = DECODERS[layout]
    ntiles = len(tile_bytes) // 32
    if count is not None:
        ntiles = min(ntiles, count)
    tiles = [dec(tile_bytes, (first + i) * 32)
             for i in range(ntiles)]
    rows = (ntiles + cols - 1) // cols
    W = cols * (8 * scale + gap) + gap
    H = rows * (8 * scale + gap) + gap
    img = Image.new("RGB", (W, H), (32, 32, 40))
    px = img.load()
    for ti, t in enumerate(tiles):
        cx = ti % cols
        cy = ti // cols
        ox = gap + cx * (8 * scale + gap)
        oy = gap + cy * (8 * scale + gap)
        for y in range(8):
            for x in range(8):
                v = t[y * 8 + x]
                if transparent and v == 0:
                    c = ((128, 128, 128) if (x + y) % 2 == 0
                         else (96, 96, 96))
                else:
                    c = palette[v]
                for sy in range(scale):
                    for sx in range(scale):
                        px[ox + x * scale + sx, oy + y * scale + sy] = c
    return img


def record_bytes(data, n):
    """Decompress $96120 record n -> (bytes, src_offset, declen)."""
    table = 0x96120
    base = 0x9638C
    ptr, ln, typ = struct.unpack_from(">IIH", data, table + n * 10)
    assert typ == 1, "record %d type %d, not $DD5C" % (n, typ)
    res = dd5c_decompress(data, base + ptr, max_out=200000)
    assert res is not None, "record %d failed to decompress" % n
    out, used = res
    return out, base + ptr, len(out)


def sprite_bytes(data, n):
    """Decompress $B86AE record n -> (bytes, src_offset, declen).

    $B86AE table: 90 x 10-byte records, data base $B8A32. Each record
    is [32-byte palette][1152 bytes = 36 tiles], all type 1 ($DD5C).
    """
    table = 0xB86AE
    base = 0xB8A32
    ptr, ln, typ = struct.unpack_from(">IIH", data, table + n * 10)
    assert typ == 1, "sprite record %d type %d, not $DD5C" % (n, typ)
    res = dd5c_decompress(data, base + ptr, max_out=200000)
    assert res is not None, "sprite record %d failed to decompress" % n
    out, used = res
    return out, base + ptr, len(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["record", "sprite", "raw"])
    ap.add_argument("spec", help="record N, or raw ROM offset (hex)")
    ap.add_argument("length", nargs="?", help="raw mode: byte count")
    ap.add_argument("--palette", default=None,
                    help="table index 0-30, 'grey', or 'raw:r,g,b;...' "
                         "(sprite mode: default is the record's own "
                         "embedded palette; record/raw default is 1)")
    ap.add_argument("--layout", default="packed",
                    choices=list(DECODERS),
                    help="tile layout (default packed)")
    ap.add_argument("--skip", type=int, default=0,
                    help="bytes to skip at the start of the blob "
                         "(sprite mode default: 32, the palette)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--cols", type=int, default=16)
    ap.add_argument("--scale", type=int, default=8)
    ap.add_argument("--tile-first", type=int, default=0)
    ap.add_argument("--tile-count", type=int, default=None)
    ap.add_argument("--transparent", action="store_true")
    args = ap.parse_args()

    data = load_rom()
    palette = None
    if args.mode == "record":
        n = int(args.spec)
        blob, src, declen = record_bytes(data, n)
        print("record %d: src 0x%06X, decompressed %d bytes = %d tiles"
              % (n, src, declen, declen // 32))
        if declen % 32:
            print("WARNING: decompressed length not a multiple of 32 "
                  "(%d leftover bytes) -- not pure tile data" % (declen % 32))
        skip = args.skip
    elif args.mode == "sprite":
        n = int(args.spec)
        blob, src, declen = sprite_bytes(data, n)
        print("sprite %d: src 0x%06X, decompressed %d bytes "
              "(32 palette + %d tile bytes = %d tiles)"
              % (n, src, declen, declen - 32, (declen - 32) // 32))
        words = struct.unpack_from(">16H", blob, 0)
        print("embedded palette words:",
              " ".join("%04X" % w for w in words))
        if args.palette is None:
            palette = [md_word_to_rgb(w) for w in words]
        skip = args.skip if args.skip else 32
        blob = blob[skip:]
    else:
        off = int(args.spec, 16)
        blob = data[off:off + int(args.length)]
        print("raw: ROM 0x%06X, %d bytes = %d tiles"
              % (off, len(blob), len(blob) // 32))
        skip = args.skip

    if palette is None:
        if args.palette == "grey":
            palette = [(i * 17, i * 17, i * 17) for i in range(16)]
        elif args.palette and args.palette.startswith("raw:"):
            palette = [tuple(int(c) for c in t.split(","))
                       for t in args.palette[4:].split(";")]
        elif args.palette is not None:
            palette = get_palette(data, int(args.palette))
        else:
            palette = get_palette(data, 1)
    print("palette:", palette)
    print("layout:", args.layout)

    img = render_tiles(blob, palette, cols=args.cols, scale=args.scale,
                       first=args.tile_first, count=args.tile_count,
                       transparent=args.transparent, layout=args.layout)
    out = args.out or ("%s%s_pal%s.png" % (args.mode, args.spec,
                                            args.palette or "emb"))
    img.save(out)
    print("wrote", out, img.size)


if __name__ == "__main__":
    main()
