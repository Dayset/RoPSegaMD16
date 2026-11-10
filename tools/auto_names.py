#!/usr/bin/env python3
"""auto_names.py — tier-0 structural names for every unnamed routine (playbook T-20).

Writes disasm/symbols/auto.csv for each routine start in disasm/ghidra/functions.txt
that has no name yet. Subsystem from the hardware it touches in disasm/src/rop.s:
  vdp  $C00000-$C00007    pad  $A10000-$A1001F    z80  $A00000-$A0FFFF / $A11100-$A11300
  else sys
Name: <subsys>_unk_<addr6>, tier 0, note = touched ports. Never overwrites a named routine.
Usage: python3 tools/auto_names.py
"""
import csv
import re
from pathlib import Path

ROUTINE = re.compile(r'\$([0-9A-Fa-f]{6})')


def subsystem(ports):
    for p in ports:
        if 0xC00000 <= p <= 0xC00007:
            return 'vdp'
    for p in ports:
        if 0xA10000 <= p <= 0xA1001F or 0xA11100 <= p <= 0xA11300 or 0xA00000 <= p <= 0xA0FFFF:
            return 'z80' if 0xA00000 <= p <= 0xA0FFFF or 0xA11100 <= p <= 0xA11300 else 'pad'
    return 'sys'


def main():
    starts = [int(l.split()[1], 16) for l in Path('disasm/ghidra/functions.txt').read_text().splitlines() if l.startswith('FUNC ')]
    named = set()
    for p in list(Path('disasm/symbols').glob('code_*.csv')) + [Path('disasm/symbols/extra.csv')]:
        with p.open(newline='') as fh:
            for r in csv.DictReader(fh):
                named.add(int(r['addr'], 16))
    # ports touched per routine, from the generated source
    body = {}
    cur = None
    label = re.compile(r'^(?:FUN_([0-9a-fA-F]{6})|L([0-9a-fA-F]{6})|([A-Za-z_]\w*)):')
    for line in Path('disasm/src/rop.s').read_text(errors='replace').splitlines():
        m = label.match(line)
        if m:
            if m.group(1):
                cur = int(m.group(1), 16)
            body.setdefault(cur, [])
        if cur is not None:
            body[cur].extend(int(h, 16) for h in ROUTINE.findall(line))
    rows = []
    for a in starts:
        if a in named:
            continue
        # ROM code addresses are below $100000; only hardware/RAM operands name a subsystem
        ports = [p for p in body.get(a, []) if p >= 0x100000]
        sub = subsystem(ports)
        touched = ' '.join(f'${p:06X}' for p in sorted(set(ports))[:6])
        rows.append((a, f'{sub}_unk_{a:06x}', touched or 'none'))
    with Path('disasm/symbols/auto.csv').open('w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['addr', 'name', 'tier', 'note'])
        for a, n, t in rows:
            w.writerow([f'0x{a:06X}', n, '0', f'auto: touches {t}'])
    print(f'auto: {len(rows)} unnamed routines named at tier 0 -> disasm/symbols/auto.csv')


if __name__ == '__main__':
    main()
