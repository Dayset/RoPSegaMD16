#!/usr/bin/env python3
"""status.py — generated status numbers, computed from the repo (never typed by hand).

Prints one markdown table. Sources:
  disasm/names.txt        routines named (must equal count of unique names/addresses)
  disasm/ghidra/functions.txt   total routines
  disasm/src/rop.s        code bytes, incbin bytes, raw fallback lines
Usage: python3 tools/status.py
"""
import re
import subprocess
import sys
from pathlib import Path

ROM = 1048576
INC = re.compile(r'incbin\s+"rop-original\.gen",\s*(\$[0-9A-Fa-f]+|\d+),\s*(\$[0-9A-Fa-f]+|\d+)')
RAW = re.compile(r'^\s*\.?(dc|fill|ds)\.[bwl]\b|^\s*\.fill\b')


def num(t):
    return int(t[1:], 16) if t.startswith('$') else int(t)


def main():
    names = [l for l in Path('disasm/names.txt').read_text().splitlines() if re.match(r'^0x', l.strip())]
    addrs = {l.split()[0] for l in names}
    nset = {l.split()[1] for l in names}
    if len(addrs) != len(names) or len(nset) != len(names):
        sys.exit('names.txt: duplicate address or name')
    funcs = 0
    fpath = Path('disasm/ghidra/functions.txt')
    if fpath.exists():
        funcs = sum(1 for _ in fpath.read_text().splitlines() if _.strip())
    incbin = raw = 0
    src = Path('disasm/src/rop.s').read_text(errors='replace').splitlines()
    for l in src:
        m = INC.search(l)
        if m:
            incbin += num(m.group(2))
        elif RAW.match(l):
            raw += 1
    code = ROM - incbin
    rows = [
        ('Routines named', f'{len(names)} of {funcs}', f'{100 * len(names) / max(funcs, 1):.0f}%'),
        ('Code bytes (instructions)', f'{code:,}', f'{100 * code / ROM:.2f}%'),
        ('Data bytes (incbin)', f'{incbin:,}', f'{100 * incbin / ROM:.2f}%'),
        ('Raw fallback lines in code', f'{raw}', 'must be 0 (#7)'),
    ]
    print('| Measure | Value | Share / note |')
    print('|---|---:|---|')
    for a, b, c in rows:
        print(f'| {a} | {b} | {c} |')


if __name__ == '__main__':
    main()
