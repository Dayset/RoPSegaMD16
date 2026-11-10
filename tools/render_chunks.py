#!/usr/bin/env python3
"""Render the $43850 chunk table (issue #006/#017 follow-up) as images.

Each decoded chunk (disasm/chunks/chunk_NNN.bin, big-endian u16 VDP
tilemap words) is rendered as an INDEX image: one pixel per tile, colour
= MD5 hash of the tile index (the same method as decode_map.py
indexgrid). This needs no tileset or palette, so it is verifiable
directly against the ROM: the image shows the chunk's structure (which
tiles, where) without guessing a tileset.

Why index renders, not tile renders: the chunks' tile indices span
0-2027 (560 distinct) and no single $96120 tileset holds that many
tiles (largest is rec 37, 586 tiles), so no tileset/palette pairing
is pinned for the chunks. A tile render would need that pairing; the
index render is the honest, checkable form. If a tileset is pinned
later, render full tiles with tools/decode_map.py's _draw rules
(packed tiles, CRAM order r=(w>>1)&7, g=(w>>5)&7, b=(w>>9)&7).

Usage (from the repo root):
    tools/.venv/bin/python tools/render_chunks.py [--outdir DIR] [--scale N]
    --outdir default disasm/maps/chunks/; --scale default 8 (px per tile).
    Writes chunk_000.png .. chunk_251.png plus CHUNKS.md (per-chunk stats).
"""

import hashlib
import os
import struct
import sys
from collections import Counter

from PIL import Image

CHUNK_DIR = "disasm/chunks"
OUT_DIR = "disasm/maps/chunks"


def index_colour(tile_index):
    h = hashlib.md5(str(tile_index).encode()).digest()
    return (h[0], h[1], h[2])


def render_chunk(data, scale):
    nwords = len(data) // 2
    words = struct.unpack(">%dH" % nwords, data[: nwords * 2])
    width = 32 if nwords == 1024 else 11
    rows = nwords // width
    img = Image.new("RGB", (width * scale, rows * scale), (0, 0, 0))
    px = img.load()
    for r in range(rows):
        for c in range(width):
            col = index_colour(words[r * width + c] & 0x07FF)
            for y in range(scale):
                for x in range(scale):
                    px[c * scale + x, r * scale + y] = col
    return img, words


def main():
    outdir = sys.argv[sys.argv.index("--outdir") + 1] if "--outdir" in sys.argv else OUT_DIR
    scale = int(sys.argv[sys.argv.index("--scale") + 1]) if "--scale" in sys.argv else 8
    os.makedirs(outdir, exist_ok=True)
    names = sorted(f for f in os.listdir(CHUNK_DIR) if f.startswith("chunk_") and f.endswith(".bin"))
    assert len(names) == 252, "expected 252 chunk files, found %d" % len(names)
    stats = []
    for name in names:
        idx = int(name[6:9])
        data = open(os.path.join(CHUNK_DIR, name), "rb").read()
        img, words = render_chunk(data, scale)
        out = os.path.join(outdir, "chunk_%03d.png" % idx)
        img.save(out)
        ti = [w & 0x07FF for w in words]
        flags = sorted(set(w & 0xF800 for w in words))
        stats.append((idx, len(data), len(set(ti)), min(ti), max(ti),
                      Counter(ti).most_common(3), flags))
    print("wrote %d chunk images to %s (scale %d)" % (len(stats), outdir, scale))
    # inventory
    lines = ["# Chunk renders — $43850 table (252 records)",
             "",
             "Issue #006/#017 follow-up. Each PNG is an INDEX render of one decoded",
             "chunk (disasm/chunks/chunk_NNN.bin): one pixel per tile, colour = MD5",
             "hash of the tile index (same method as decode_map.py indexgrid). No",
             "tileset or palette is assumed — the chunk tileset/palette pairing is",
             "not pinned (tile indices span 0-2027; no $96120 tileset holds that",
             "many tiles). Regenerate with: `tools/.venv/bin/python",
             "tools/render_chunks.py`.",
             "",
             "| rec | size | distinct tiles | index range | most common tiles |",
             "|-----|------|----------------|-------------|-------------------|"]
    for idx, size, nd, lo, hi, common, flags in stats:
        common_s = ", ".join("%d×%d" % (t, c) for t, c in common)
        lines.append("| %d | %s | %d | %d–%d | %s |" % (
            idx, "32×32" if size == 2048 else "11×11", nd, lo, hi, common_s))
    with open(os.path.join(outdir, "CHUNKS.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote %s" % os.path.join(outdir, "CHUNKS.md"))
    big = [s for s in stats if s[1] == 2048]
    small = [s for s in stats if s[1] == 242]
    print("32x32 chunks: %d (recs %d-%d, %d-%d); 11x11 chunks: %d (recs %d-%d)" % (
        len(big), big[0][0], big[76][0], big[77][0], big[-1][0],
        len(small), small[0][0], small[-1][0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
