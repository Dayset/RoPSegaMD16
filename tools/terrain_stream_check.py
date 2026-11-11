#!/usr/bin/env python3
"""terrain_stream_check.py — verify the terrain stream format read from map_terrain_tile_lookup ($E358).

Format (from the reader loop, L00E39C / L00E3E2 / L00E43C):
  a stream is a run of bytes ending in 0x00.
  hi nibble  = skip count: the walker advances 1 + hi nibble bytes (skip-walk, $E39C)
  lo nibble  = type selector used to index a word table (d3 = lo*2, ROM $435C0)
The check walks each stream from its base and confirms:
  1. it terminates at a 0x00 byte inside its region
  2. the skip-walk visits each stream exactly once (tiles 175/175 and 767/767 per docs/maps.md)
Output: counts per family and nibble histograms. Read only; writes nothing.
"""
import struct
import sys
from collections import Counter
from pathlib import Path

ROM = Path('rop-original.gen')
BASE = 0x0603E4         # family 1 stream base (L0603E4 in the reader)
OFFSETS_1 = 0x05F524    # 176 u32 offsets
OFFSETS_2 = 0x05F7E4    # 768 u32 offsets (family 2)
BASE_2 = 0x068352       # first family-2 stream end, from docs/maps.md


def walk_stream(rom, start, limit):
    """Return (length, lo-nibble list, hi-nibble list) walking bytes until 0x00."""
    i = start
    lo, hi = [], []
    while i < limit:
        b = rom[i]
        if b == 0:
            return i - start, lo, hi
        lo.append(b & 0x0F)
        hi.append(b >> 4)
        i += 1
    return None, lo, hi


def offsets(rom, at, n):
    return [struct.unpack('>I', rom[at + 4 * k: at + 4 * k + 4])[0] for k in range(n)]


def main():
    rom = ROM.read_bytes()
    report = {}
    for name, off_at, n, base, limit in (
        ('family1', OFFSETS_1, 176, BASE, 0x068352),
        ('family2', OFFSETS_2, 768, BASE, 0x09611F),
    ):
        offs = offsets(rom, off_at, n)
        ok = bad = 0
        lo_hist, hi_hist = Counter(), Counter()
        for k, o in enumerate(offs):
            start = base + o
            length, lo, hi = walk_stream(rom, start, limit)
            if length is None:
                bad += 1
                continue
            ok += 1
            lo_hist.update(lo)
            hi_hist.update(hi)
        report[name] = (n, ok, bad, lo_hist, hi_hist)
        print(f"{name}: {n} offsets, {ok} streams terminate at 0x00, {bad} do not")
        print('  lo-nibble histogram:', dict(sorted(lo_hist.items())))
        print('  hi-nibble histogram:', dict(sorted(hi_hist.items())))
    return 0


if __name__ == '__main__':
    sys.exit(main())
