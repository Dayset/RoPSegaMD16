#!/usr/bin/env python3
"""ram_map.py — every $FFxxxx operand in disasm/src/rop.s with reference count and users (playbook T-70).

Writes disasm/symbols/ram_refs.csv: addr,count,users (top 5 routine labels, by first use).
Named RAM rows (ram.csv) are maintained by hand from docs; this file is the work list.
Usage: python3 tools/ram_map.py
"""
import csv
import re
from collections import defaultdict
from pathlib import Path

OP = re.compile(r'\$(ff[0-9a-fA-F]{4})\.[wl]\b')
LAB = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*):')


def main():
    refs = defaultdict(lambda: {'count': 0, 'users': []})
    routine = '?'
    for line in Path('disasm/src/rop.s').read_text(errors='replace').splitlines():
        m = LAB.match(line)
        if m and not m.group(1).startswith('L'):
            routine = m.group(1)
        for hit in OP.finditer(line):
            addr = int(hit.group(1), 16)
            r = refs[addr]
            r['count'] += 1
            if routine not in r['users'] and len(r['users']) < 5:
                r['users'].append(routine)
    out = Path('disasm/symbols/ram_refs.csv')
    with out.open('w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['addr', 'count', 'users'])
        for a in sorted(refs, key=lambda a: -refs[a]['count']):
            w.writerow([f'0x{a:06X}', refs[a]['count'], ' '.join(refs[a]['users'])])
    print(f'ram: {len(refs)} distinct $FF operands, {sum(r["count"] for r in refs.values())} references -> {out}')


if __name__ == '__main__':
    main()
