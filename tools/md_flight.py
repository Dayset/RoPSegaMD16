#!/usr/bin/env python3
"""Frames per world tick during the attract dragon flight (no input from
power-on; the flight starts ~frame 8,800), against terrain under the
10x10 view: cell height (bits 13-15) and open-water cells (#258).
  md_flight.py ROM [FRAMES]
"""
import struct
import sys
import warnings

import numpy as np

warnings.filterwarnings("ignore")
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import md_run  # noqa: E402
from td_height_mock import overworld  # noqa: E402


def main():
    rom_path = sys.argv[1]
    frames = int(sys.argv[2]) if len(sys.argv) > 2 else 30000
    rom = open("rop-original.gen", "rb").read()
    grid = overworld(rom)
    height = ((grid >> 13) & 7).astype(int)
    desc = struct.unpack_from(">512H", rom, 0x1AE98)

    def maptile(w):
        d = desc[w & 0x1FF]
        return ((d >> 8 if w & 0x1000 else d) >> 2) & 63
    water = np.vectorize(lambda w: maptile(int(w)) in (9, 13, 14))(grid)
    md = md_run.MD(rom_path)
    p0, ev = None, []
    for i in range(frames):
        md.step("")
        r = md.ram()
        p = (md_run.w(r, 0xFF0E8E), md_run.w(r, 0xFF0E90))
        if md_run.w(r, 0xFF0E98) == 0xFFFF and p != p0 and (not ev or i - ev[-1][0] > 3):
            ev.append((i, p))
        p0 = p
    rows = []
    for (f0, (x, y)), (f1, _) in zip(ev, ev[1:]):
        if f1 - f0 > 60 or not (5 <= x < 347 and 5 <= y < 219):
            continue
        rows.append((f1 - f0, height[y - 5:y + 5, x - 5:x + 5].sum(),
                     water[y - 5:y + 5, x - 5:x + 5].sum()))
    a = np.array(rows)
    print("ticks %d, frames/tick median %.1f mean %.1f" % (len(a), np.median(a[:, 0]), a[:, 0].mean()))
    for lo, hi in ((0, 1), (1, 30), (30, 80), (80, 800)):
        s = a[(a[:, 1] >= lo) & (a[:, 1] < hi)]
        if len(s):
            print("  height sum %3d-%3d: %3d ticks, %.1f frames/tick" % (lo, hi - 1, len(s), s[:, 0].mean()))
    for lo, hi in ((90, 101), (50, 90), (10, 50), (0, 10)):
        s = a[(a[:, 2] >= lo) & (a[:, 2] < hi)]
        if len(s):
            print("  water cells %3d-%3d: %3d ticks, %.1f frames/tick" % (lo, hi - 1, len(s), s[:, 0].mean()))


if __name__ == "__main__":
    main()
