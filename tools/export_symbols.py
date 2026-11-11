#!/usr/bin/env python3
"""export_symbols.py — one derived symbol table from the shard CSVs (issue #20).

Reads disasm/symbols/*.csv (code, extra, auto, ram) and writes disasm/symbols.csv:
  address, name, kind (code|ram), tier, status (named if tier >= 1 else tier0), note
Generated, never hand-edited. Run after any symbol change; does not touch the ROM.
Not done here: a BlastEm/MAME .sym file (format not verified against an emulator).
"""
import csv
import glob
from pathlib import Path

OUT = Path('disasm/symbols.csv')


def rows():
    for f in sorted(glob.glob('disasm/symbols/code_*.csv')) + ['disasm/symbols/extra.csv', 'disasm/symbols/auto.csv']:
        p = Path(f)
        if not p.exists():
            continue
        for r in csv.DictReader(p.open(newline='')):
            yield r['addr'].strip(), r['name'].strip(), 'code', str(r.get('tier', '1')).strip(), r.get('note', '').strip()
    p = Path('disasm/symbols/ram.csv')
    if p.exists():
        for r in csv.DictReader(p.open(newline='')):
            yield r['addr'].strip(), r['name'].strip(), 'ram', str(r.get('tier', '1')).strip(), r.get('note', '').strip()


def main():
    seen = set()
    out = []
    for addr, name, kind, tier, note in rows():
        if addr in seen:
            continue
        seen.add(addr)
        status = 'named' if tier in ('1', '2') else 'tier0'
        out.append((int(addr, 16), name, kind, tier, status, note.replace(',', ';')))
    out.sort()
    with OUT.open('w', newline='') as fh:
        w = csv.writer(fh, lineterminator='\n')
        w.writerow(['address', 'name', 'kind', 'tier', 'status', 'note'])
        for a, name, kind, tier, status, note in out:
            w.writerow([f'0x{a:06X}', name, kind, tier, status, note])
    print(f'wrote {OUT}: {len(out)} rows, named {sum(1 for o in out if o[4] == "named")}, tier0 {sum(1 for o in out if o[4] == "tier0")}')


if __name__ == '__main__':
    main()
