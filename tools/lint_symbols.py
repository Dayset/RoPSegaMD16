#!/usr/bin/env python3
"""lint_symbols.py — schema and uniqueness lint for disasm/symbols/*.csv (playbook T-02).

Fails on: bad header, missing tier, tier not in 0/1/2, duplicate name or address,
name not a legal identifier (lower snake case, <= 32 chars), address not a 0x-hex value.
Warns (does not fail) when an address is not a Ghidra routine start.
Usage: python3 tools/lint_symbols.py
"""
import csv
import re
import sys
from pathlib import Path

HEADER = ['addr', 'name', 'tier', 'note']
NAME = re.compile(r'^[a-z][a-z0-9_]{0,31}$')
ADDR = re.compile(r'^0x[0-9A-Fa-f]{6}$')


def main():
    errors, warns = [], []
    starts = set()
    f = Path('disasm/ghidra/functions.txt')
    if f.exists():
        starts = {int(l.split()[1], 16) for l in f.read_text().splitlines() if l.startswith('FUNC ')}
    seen_addr, seen_name = {}, {}
    files = sorted([*Path('disasm/symbols').glob('code_*.csv'), Path('disasm/symbols/extra.csv'), Path('disasm/symbols/auto.csv')])
    if not files:
        sys.exit('lint: no symbol files in disasm/symbols')
    for path in files:
        with path.open(newline='') as fh:
            rd = csv.reader(fh)
            header = next(rd, [])
            if header != HEADER:
                errors.append(f'{path}: header is {header}, want {HEADER}')
                continue
            for n, row in enumerate(rd, 2):
                if not row:
                    continue
                if len(row) != 4:
                    errors.append(f'{path}:{n}: {len(row)} columns, want 4')
                    continue
                addr, name, tier, note = row
                if not ADDR.match(addr):
                    errors.append(f'{path}:{n}: address {addr!r} is not 0x + 6 hex digits')
                    continue
                if not NAME.match(name):
                    errors.append(f'{path}:{n}: name {name!r} is not lower snake case <= 32 chars')
                if tier not in ('0', '1', '2'):
                    errors.append(f'{path}:{n}: tier {tier!r} not 0, 1 or 2')
                a = int(addr, 16)
                if a in seen_addr:
                    errors.append(f'{path}:{n}: address {addr} already in {seen_addr[a]}')
                seen_addr.setdefault(a, f'{path}:{n}')
                if name in seen_name:
                    errors.append(f'{path}:{n}: name {name} already in {seen_name[name]}')
                seen_name.setdefault(name, f'{path}:{n}')
                if starts and a not in starts:
                    warns.append(f'{path}:{n}: {addr} {name} is not a Ghidra routine start')
    for w in warns:
        print('warn:', w)
    for e in errors:
        print('error:', e)
    total = len(seen_addr)
    print(f'lint: {total} names, {len(errors)} errors, {len(warns)} warnings')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
