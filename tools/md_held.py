#!/usr/bin/env python3
"""Where the picture update is held (#289 step 2).

  md_held.py ROM ROUTE [--from A] [--to B]

ROM: a topdown build with ROP_DEFINES=HELDPC=1 (td_vint stores the
interrupted PC at $FF7E00 and the frame at $FF7E04 every VBlank).
Per frame in the iso view while walking (game camera moved in the last
64 frames): if no picture update happened this frame (TD_LASTFR behind
the frame counter), count the routine the VBlank found the main thread
in (disasm/ghidra/functions.txt, names from disasm/symbols where known,
"topdown" for our blob). Prints held frames by routine.
"""
import argparse, bisect, csv, glob, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import md_run
from md_iso_cadence import equs

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def routines():
    names = {}
    for f in glob.glob(os.path.join(ROOT, "disasm", "symbols", "*.csv")):
        for row in csv.reader(open(f)):
            if len(row) > 1 and row[0].startswith(("0x", "$")):
                try:
                    names[int(row[0].replace("$", "0x"), 16)] = row[1]
                except ValueError:
                    pass
    rs = []
    for line in open(os.path.join(ROOT, "disasm", "ghidra", "functions.txt")):
        p = line.split()
        if len(p) >= 4 and p[0] == "FUNC":
            a, b = int(p[1], 16), int(p[2], 16)
            rs.append((a, b, names.get(a, p[3])))
    rs.sort()
    return rs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("route")
    ap.add_argument("--from", dest="a", type=int, default=0)
    ap.add_argument("--to", dest="b", type=int, default=0)
    ap.add_argument("--pc", action="store_true", help="per PC")
    ap.add_argument("--lst", help="vasm listing of the topdown blob "
                    "(labels of our own code)")
    a = ap.parse_args()
    E = equs()
    rs = routines()
    starts = [r[0] for r in rs]
    labs = []
    if a.lst:
        import re
        for line in open(a.lst, errors="replace"):
            m = re.match(r"([0-9A-F]{8}) ([a-z_][a-z0-9_]*)$", line.strip())
            if m:
                labs.append((int(m.group(1), 16), m.group(2)))
        labs.sort()
    md = md_run.MD(a.rom)
    seq = []
    for n, pad in md_run.parse_route(a.route):
        seq += [pad] * n
    end = a.b or len(seq)
    w = md_run.w
    last_move, cam, held, walk = -999, None, {}, 0
    for i in range(end):
        md.step(seq[i] if i < len(seq) else "")
        if i < a.a:
            continue
        r = md.ram()
        c = (w(r, 0xFF0E8E), w(r, 0xFF0E90))
        if c != cam:
            cam, last_move = c, i
        if not w(r, E["TD_ISO"]) or i - last_move > 64:
            continue
        walk += 1
        fr = w(r, 0xFF0012)
        if w(r, E["TD_LASTFR"]) == fr:
            continue
        pc = (w(r, 0xFF7E00) << 16) | w(r, 0xFF7E02)
        if pc >= 0xFD0CC and pc < 0x100000 or pc >= 0x1F0000:
            name = "topdown"
            k = bisect.bisect_right([l[0] for l in labs], pc) - 1
            if k >= 0:
                name = "topdown " + labs[k][1]
        else:
            k = bisect.bisect_right(starts, pc) - 1
            name = rs[k][2] if k >= 0 and pc <= rs[k][1] else f"${pc:06X}"
        if not w(r, 0xFF7E08):
            continue                    # scene loading: no picture yet
        if a.pc:
            name += f" ${pc:06X}"
        held[name] = held.get(name, 0) + 1
    tot = sum(held.values())
    print(f"walking iso frames {walk}, without an update {tot}")
    for n, c in sorted(held.items(), key=lambda x: -x[1])[:20]:
        print(f"  {c:5d}  {n}")


if __name__ == "__main__":
    main()
