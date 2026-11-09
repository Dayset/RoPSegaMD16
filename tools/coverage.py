#!/usr/bin/env python3
"""coverage.py — how much of the ROM is real source (GitHub issue #6).

Reads disasm/src/r_*.s (the rebuild tree from PR #1) and reports, per
region file and in total, how the 1 MB ROM is represented:

  asm       labelled instructions
  fallback  .dc.b lines carrying a "was: <insn>" comment (instructions
            the assembler would re-encode differently — see issue #7)
  dcb       other .dc.b / .dc.w / .dc.l written inline. CAUTION: in the
            PR #1 tree most of these, inside code regions, are also
            instruction fallbacks emitted without the "was:" comment
            (e.g. `.dc.b 0x90,0x7C,…` = sub.w #imm) — ~57 KB in r_010000
  incbin    bytes pulled in verbatim from ROM slices
  fill      .fill / dcb padding

Instruction bytes are counted as the remainder of each region after the
other categories, so the region's address span must be known: it is
taken from the "0xLO-0xHI" range in each file's first comment line.

Usage: python3 tools/coverage.py [disasm/src] [--md]
M8 is done when no code remains in incbin or fallback, and every incbin
range is classified as known data in disasm/map.md.
"""
import re
import sys
from pathlib import Path

HDR = re.compile(r"(0x[0-9A-Fa-f]{6})-(0x[0-9A-Fa-f]{6})")
INC = re.compile(r"\.incbin\b.*\((\d+) bytes\)")
FILL = re.compile(r"\.(?:fill|skip|space)\s+(0x[0-9A-Fa-f]+|\d+)")
DC = re.compile(r"\.(?:dc\.)?(b|byte|w|word|short|l|long)\b\s+(.*)", re.I)
SIZE = {"b": 1, "byte": 1, "w": 2, "word": 2, "short": 2, "l": 4, "long": 4}


def data_bytes(kind, args):
    args = args.split("/*")[0]
    n = len([a for a in args.split(",") if a.strip()])
    return n * SIZE[kind.lower()]


def scan(path):
    c = dict(asm=0, fallback=0, dcb=0, incbin=0, fill=0, insns=0, span=0)
    lines = path.read_text().splitlines()
    for line in lines[:3]:
        m = HDR.search(line)
        if m:
            lo, hi = int(m.group(1), 16), int(m.group(2), 16)
            c["span"] = hi - lo + 1  # header ranges are inclusive
            break
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith(("/*", "*", "#", ";")) or s.endswith(":"):
            continue
        m = INC.search(s)
        if m:
            c["incbin"] += int(m.group(1))
            continue
        m = FILL.match(s)
        if m:
            c["fill"] += int(m.group(1), 0)
            continue
        m = DC.match(s)
        if m:
            n = data_bytes(m.group(1), m.group(2))
            c["fallback" if "was:" in s else "dcb"] += n
            continue
        if s.startswith("."):
            continue
        c["insns"] += 1
    c["asm"] = max(0, c["span"] - c["incbin"] - c["fill"] - c["dcb"] - c["fallback"])
    return c


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    md = "--md" in sys.argv
    src = Path(args[0] if args else "disasm/src")
    files = sorted(src.glob("r_*.s"))
    if not files:
        print(f"coverage: no r_*.s files in {src} (rebuild tree not present)")
        return 1
    keys = ["asm", "fallback", "dcb", "incbin", "fill"]
    tot = dict.fromkeys(keys + ["insns", "span"], 0)
    rows = []
    for f in files:
        c = scan(f)
        rows.append((f.name, c))
        for k in tot:
            tot[k] += c[k]
    if md:
        print("| file | span | asm | fallback | dc.* | incbin | fill |")
        print("|---|---:|---:|---:|---:|---:|---:|")
    for name, c in rows + [("TOTAL", tot)]:
        span = c["span"] or 1
        cells = [f"{c[k]} ({c[k] / span:.1%})" for k in keys]
        if md:
            print(f"| {name} | {c['span']} | " + " | ".join(cells) + " |")
        else:
            print(f"{name:12s} span {c['span']:8d}  " + "  ".join(
                f"{k} {v}" for k, v in zip(keys, cells)))
    if tot["span"] != 1 << 20:
        print(f"coverage: WARNING spans sum to {tot['span']}, expected 1048576 "
              "(a region header is missing or its range is off)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
