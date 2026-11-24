#!/usr/bin/env python3
"""Iso figures against the original view (#278, #300).

  md_figure_check.py ROM ROUTE FRAME [FRAME ...]

Per frame: run ROUTE to FRAME, stand 60 frames, screenshot the smooth
iso view and note each figure's 32x32 box (TD_LIST, kind 1); then A+B+C
to the original view, stand 120 frames, screenshot. Prints the pixels
that differ inside the figure boxes (0 = the figure and whatever covers
it look as in the original; water animation adds a few px).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from md_run import MD, w, parse_route  # noqa: E402
from md_iso_cadence import equs  # noqa: E402


def check(rom, route, n, E):
    md = MD(rom)
    seq = []
    for k, pad in parse_route(route):
        seq += [pad] * k
    for i in range(n):
        md.step(seq[i] if i < len(seq) else "")
    for _ in range(60):
        md.step("")
    r = md.ram()
    s = lambda v: v - 65536 * (v > 32767)
    igy = s(w(r, E["TD_IGY"]))
    boxes, kinds = [], []
    for k in range(w(r, E["TD_NB"])):
        e = E["TD_LIST"] + 8 * k
        x, y, kd = s(w(r, e)), s(w(r, e + 2)), w(r, e + 6)
        if x == -32768:
            continue
        kinds.append(kd & 0xFF)
        if kd & 0xFF == 1:
            boxes.append((x, y - (kd >> 8) - 8 - igy))
    iso = md.screen().astype(int)
    for _ in range(4):
        md.step("ABC")
    for _ in range(120):
        md.step("")
    org = md.screen().astype(int)
    d = np.abs(iso - org).sum(2) != 0
    px = sum(int(d[max(0, y):y + 32, max(0, x):x + 32].sum()) for x, y in boxes)
    return kinds, px


def main():
    rom, route = sys.argv[1], sys.argv[2]
    E = equs()
    for f in sys.argv[3:]:
        kinds, px = check(rom, route, int(f), E)
        print(f"frame {f}: sprites {kinds} (1 figure, 2 overlay), "
              f"figure-box px off {px}")


if __name__ == "__main__":
    main()
