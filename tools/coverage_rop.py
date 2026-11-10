#!/usr/bin/env python3
"""coverage_rop.py — how much of the ROM is real source in disasm/src/rop.s (issue #6).

Reads the single generated file and classifies every byte of the ROM:

  code     bytes covered by instruction lines (computed as the remainder)
  raw      .dc.b / .dc.w / .dc.l / .fill written inline (instruction fallbacks, issue #7)
  incbin   bytes pulled verbatim from rop-original.gen (data, issue #15/#13)

The ROM size is taken from rop-original.gen when present, else 1048576.
Usage: python3 tools/coverage_rop.py [disasm/src/rop.s] [--md]
M8 is done when raw == 0 in code ranges and every incbin range is classified.
"""
import re
import sys
from pathlib import Path

ROM_SIZE = 1048576
INC = re.compile(r'incbin\s+"rop-original\.gen",\s*(\$[0-9A-Fa-f]+|\d+),\s*(\$[0-9A-Fa-f]+|\d+)')
RAW = re.compile(r'^\s*\.(dc|fill|ds)\.?[bwl]?\b')
INSN = re.compile(r'^\s+[a-z]\S*\s.*;\s*\$[0-9A-Fa-f]{6}')


def num(tok):
    return int(tok[1:], 16) if tok.startswith('$') else int(tok)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    src = Path(args[0] if args else 'disasm/src/rop.s')
    rom = Path('rop-original.gen')
    size = rom.stat().st_size if rom.exists() else ROM_SIZE
    incbin = raw = insns = 0
    for line in src.read_text(errors='replace').splitlines():
        m = INC.search(line)
        if m:
            incbin += num(m.group(2))
            continue
        if RAW.match(line):
            raw += 1
            continue
        if INSN.match(line):
            insns += 1
    code = size - incbin
    rows = [
        ('ROM bytes', size, '—'),
        ('code (instructions, remainder)', code, f'{insns} mnemonic lines'),
        ('incbin (data verbatim)', incbin, f'{sum(1 for l in src.read_text(errors="replace").splitlines() if INC.search(l))} incbin lines'),
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
