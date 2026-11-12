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
# rop.s also names RAM operands (ram_<subsys>_<thing>.l); resolve them through ram.csv
SYM = re.compile(r'\b(ram_[a-z0-9_]+)\.[wl]\b')
LAB = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*):')


def count(rop_text, ram_names):
    """Count RAM operand references in rop.s text. ram_names maps symbol name -> address."""
    refs = defaultdict(lambda: {'count': 0, 'users': []})
    routine = '?'
    for line in rop_text.splitlines():
        m = LAB.match(line)
        if m and not m.group(1).startswith('L'):
            routine = m.group(1)
        code = line.split(';')[0]
        hits = [int(h.group(1), 16) for h in OP.finditer(code)]
        hits += [ram_names[h.group(1)] for h in SYM.finditer(code) if h.group(1) in ram_names]
        for addr in hits:
            r = refs[addr]
            r['count'] += 1
            if routine not in r['users'] and len(r['users']) < 5:
                r['users'].append(routine)
    return refs


def main():
    names = {}
    with open('disasm/symbols/ram.csv', newline='') as fh:
        for row in csv.DictReader(l for l in fh if not l.startswith('#')):
            names[row['name']] = int(row['addr'], 16)
    refs = count(Path('disasm/src/rop.s').read_text(errors='replace'), names)
    out = Path('disasm/symbols/ram_refs.csv')
    with out.open('w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['addr', 'count', 'users'])
        for a in sorted(refs, key=lambda a: -refs[a]['count']):
            w.writerow([f'0x{a:06X}', refs[a]['count'], ' '.join(refs[a]['users'])])
    print(f'ram: {len(refs)} distinct $FF operands, {sum(r["count"] for r in refs.values())} references -> {out}')


if __name__ == '__main__':
    main()
