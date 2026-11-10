#!/usr/bin/env python3
"""coverage_rop.py — how much of the ROM is real source in disasm/src/rop.s (issue #6).

Reads the single generated file and classifies every byte of the ROM:

  code     bytes covered by instruction lines (computed as the remainder)
  raw      .dc.b / .dc.w / .dc.l / .fill written inline (instruction fallbacks, issue #7)
  incbin   bytes pulled verbatim from rop-original.gen (data, issue #15/#13)
             split: known data (inside a classified row of disasm/regions.csv)
                    vs unclassified (class unknown or no row)
  struct   bytes of labelled dc.w/dc.l/dc.b data lines (structured data, issue #6)

The ROM size is taken from rop-original.gen when present, else 1048576.
Usage: python3 tools/coverage_rop.py [disasm/src/rop.s] [--md]
M8 is done when raw == 0 in code ranges and every incbin range is classified.
"""
import re
import sys
from pathlib import Path

ROM_SIZE = 1048576
INC = re.compile(r'incbin\s+"rop-original\.gen",\s*(\$[0-9A-Fa-f]+|\d+),\s*(\$[0-9A-Fa-f]+|\d+)')
RAW = re.compile(r'^\s*\.?(dc|fill|ds)\.[bwl]\b|^\s*\.fill\b')
INSN = re.compile(r'^\s+[a-z]\S*\s.*;\s*\$[0-9A-Fa-f]{6}')


def num(tok):
    return int(tok[1:], 16) if tok.startswith('$') else int(tok)


def load_regions(path=Path('disasm/regions.csv')):
    """Sorted (start, end_inclusive, class) rows; empty if the file is missing."""
    rows = []
    if path.exists():
        for line in path.read_text().splitlines()[1:]:
            parts = line.split(',')
            if len(parts) >= 3 and parts[0].startswith('0x'):
                rows.append((int(parts[0], 16), int(parts[1], 16), parts[2]))
    return sorted(rows)


def known_bytes(start, length, regions):
    """Bytes of [start, start+length) covered by a row whose class is not 'unknown'."""
    end = start + length - 1
    total = 0
    for rs, re_, cls in regions:
        if cls == 'unknown' or re_ < start or rs > end:
            continue
        total += min(end, re_) - max(start, rs) + 1
    return total


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    src = Path(args[0] if args else 'disasm/src/rop.s')
    rom = Path('rop-original.gen')
    size = rom.stat().st_size if rom.exists() else ROM_SIZE
    incbin = raw = insns = known = struct = 0
    regions = load_regions()
    for line in src.read_text(errors='replace').splitlines():
        m = INC.search(line)
        if m:
            start, length = num(m.group(1)), num(m.group(2))
            incbin += length
            known += known_bytes(start, length, regions)
            continue
        if RAW.match(line):
            raw += 1
            continue
        if re.match(r'^[A-Za-z_][\w]*:\s*\.?dc\.[bwl]\b', line):
            struct += 1
        if INSN.match(line):
            insns += 1
    code = size - incbin
    rows = [
        ('ROM bytes', size, '—'),
        ('code (instructions, remainder)', code, f'{insns} mnemonic lines'),
        ('incbin (data verbatim)', incbin, f'{sum(1 for l in src.read_text(errors="replace").splitlines() if INC.search(l))} incbin lines'),
        ('  incbin known data', known, 'inside a classified row of disasm/regions.csv'),
        ('  incbin unclassified', incbin - known, 'class unknown or no row (M8 target: 0)'),
        ('struct (labelled dc data)', struct, 'structured data lines (#6)'),
        ('raw .dc/.fill lines', raw, 'instruction fallbacks — must reach 0 (#7)'),
    ]
    if '--md' in sys.argv:
        print('| Measure | Bytes | Notes |')
        print('|---|---:|---|')
        for name, n, note in rows:
            print(f'| {name} | {n:,} | {note} |')
        pct = 100.0 * code / size
        print(f'| TOTAL code coverage | {pct:.2f}% | raw={raw}, incbin={incbin:,} |')
    else:
        for name, n, note in rows:
            print(f'{name:34} {n:>10,}  {note}')
        print(f'code coverage: {100.0 * code / size:.2f}%  raw={raw}')


if __name__ == '__main__':
    main()
