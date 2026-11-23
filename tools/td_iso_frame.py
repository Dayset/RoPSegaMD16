#!/usr/bin/env python3
"""Generate the fixed parchment frame of the smooth iso view (#252).

The iso picture scrolls on Plane B; the window (which never scrolls)
holds a parchment frame with a diamond hole in the middle. The hole is
the camera's cells within +-4 of it (du, dv in [-4, 4] in cell units:
14 px per du-dv, 8 px per du+dv), centred where the original draws the
camera cell (screen 162, 98), cut at line 152 (the HUD rows). The render
covers cells -5..+4 around its own camera cell, so the hole stays
inside the last render while the camera glides up to one cell away.

Writes the asm data block between the `; ti_frame data` markers in
patches/topdown/feature.s: per window row the first/last fully inside
column, the edge cells (column, tile id) per row, and the edge tiles as
1 bit per pixel (1 = parchment).

  td_iso_frame.py [--check]
"""
import sys
from pathlib import Path

CX, CY, HW, HH, YCUT = 162, 98, 112, 64, 152
FEATURE = Path(__file__).resolve().parent.parent / "patches/topdown/feature.s"
BEGIN, END = "; ti_frame data (tools/td_iso_frame.py)", "; ti_frame data end"


def inside(x, y):
    return HH * abs(x - CX) + HW * abs(y - CY) <= HW * HH and y < YCUT


def build():
    rows, edges, tiles = [], [], {}
    for r in range(28):
        full, row_edges = [], []
        for c in range(40):
            m = [[inside(c * 8 + i + 0.5, r * 8 + j + 0.5) for i in range(8)] for j in range(8)]
            if all(all(row) for row in m):
                full.append(c)
            elif any(any(row) for row in m):
                bits = tuple(sum((0 if m[j][i] else 1) << (7 - i) for i in range(8)) for j in range(8))
                tid = tiles.setdefault(bits, len(tiles))
                row_edges.append((c, tid))
        lo, hi = (min(full), max(full)) if full else (1, 0)
        rows.append((lo, hi))
        edges.append(row_edges)
    return rows, edges, list(tiles)


def commit_rows():
    """Per bitmap row: first/last column the commit writes. A bitmap tile
    (col k, row r) sits at screen (16 + 8k - e, 8r) with the camera on the
    render's cell (e = the -4..2 px alignment shift); it can show through
    the hole while the camera glides up to one cell (14, 8 px) away."""
    lim = HW * HH + 14 * HH + 8 * HW + 8 * HH + 4 * HW
    out = []
    for r in range(23):
        cy = 8 * r + 4
        ks = [k for k in range(36)
              if HH * abs(16 + 8 * k + 4 - CX) + HW * abs(cy - CY) <= lim and 8 * r < YCUT + 8]
        out.append((min(ks), max(ks)) if ks else (1, 0))
    return out


def asm():
    rows, edges, tiles = build()
    out = [BEGIN, f"TI_NEDGE\tequ {len(tiles)}", "ti_crow:\t; per bitmap row: first, last column the commit writes"]
    crow = commit_rows()
    for r in range(0, 23, 8):
        out.append("\tdc.b\t" + ", ".join(f"{lo},{hi}" for lo, hi in crow[r:r + 8]))
    out.append("ti_rows:\t; per window row: first, last fully inside column")
    for r in range(0, 28, 7):
        out.append("\tdc.b\t" + ", ".join(f"{lo},{hi}" for lo, hi in rows[r:r + 7]))
    out.append("ti_eoff:\t; per window row: offset of its edge cells in ti_ecel (+ end)")
    offs, n = [], 0
    for e in edges:
        offs.append(n)
        n += len(e)
    offs.append(n)
    for r in range(0, 29, 10):
        out.append("\tdc.b\t" + ", ".join(str(o) for o in offs[r:r + 10]))
    out.append("ti_ecel:\t; edge cells: column, tile id")
    flat = [v for e in edges for cell in e for v in cell]
    for i in range(0, len(flat), 16):
        out.append("\tdc.b\t" + ", ".join(str(v) for v in flat[i:i + 16]))
    out.append("ti_etil:\t; edge tiles, 1 bit per pixel (1 = parchment), 8 rows each")
    for t in tiles:
        out.append("\tdc.b\t" + ", ".join(f"${b:02X}" for b in t))
    out += ["\teven", END]
    return "\n".join(out) + "\n"


def main():
    text = FEATURE.read_text()
    i, j = text.index(BEGIN), text.index(END) + len(END) + 1
    new = text[:i] + asm() + text[j:]
    if "--check" in sys.argv:
        sys.exit(0 if new == text else 1)
    FEATURE.write_text(new)


if __name__ == "__main__":
    main()
