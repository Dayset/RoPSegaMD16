#!/usr/bin/env python3
"""regions_inventory.py — every incbin (data-verbatim) region of rop.s, merged.

For each merged region prints start, end, size and the class taken from
disasm/region-classes.txt (one line per known class: START END CLASS # source).
Regions with no matching class line are reported as UNCLASSIFIED.
Usage: python3 tools/regions_inventory.py [disasm/src/rop.s] [--md]
"""
import re
import sys
from pathlib import Path

INC = re.compile(r'incbin\s+"rop-original\.gen",\s*(\$[0-9A-Fa-f]+|\d+),\s*(\$[0-9A-Fa-f]+|\d+)')


def num(t):
    return int(t[1:], 16) if t.startswith('$') else int(t)


def load_classes(path):
    out = []
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        line = line.split('#')[0].strip()
        if not line:
            continue
        s, e, cls = line.split(None, 2)
        out.append((int(s, 16), int(e, 16), cls))
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    src = Path(args[0] if args else 'disasm/src/rop.s')
    classes = load_classes(Path('disasm/region-classes.txt'))
    rs = []
    for line in src.read_text(errors='replace').splitlines():
        m = INC.search(line)
        if m:
            rs.append([num(m.group(1)), num(m.group(2))])
    rs.sort()
    merged = []
    for s, L in rs:
        if merged and merged[-1][0] + merged[-1][1] == s:
            merged[-1][1] += L
        else:
            merged.append([s, L])
    rows = []
    for s, L in merged:
        e = s + L - 1
        cuts = [(s, e, None)]
        for cs, ce, c in sorted(classes):
            nxt = []
            for a, b, lab in cuts:
                if lab is not None or ce < a or cs > b:
                    nxt.append((a, b, lab))
                    continue
                if a < cs:
                    nxt.append((a, cs - 1, None))
                nxt.append((max(a, cs), min(b, ce), c))
                if ce < b:
                    nxt.append((ce + 1, b, None))
            cuts = nxt
        for a, b, lab in cuts:
            rows.append((a, b, b - a + 1, lab or 'UNCLASSIFIED'))
    unc = [r for r in rows if r[3] == 'UNCLASSIFIED']
    print(f'regions={len(rows)} unclassified={len(unc)} unclassified_bytes={sum(r[2] for r in unc)}')
    if '--md' in sys.argv:
        print('| Start | End | Size | Class |')
        print('|---|---|---:|---|')
        for s, e, L, c in rows:
            print(f'| 0x{s:06X} | 0x{e:06X} | {L:,} | {c} |')
    else:
        for s, e, L, c in rows:
            print(f'0x{s:06X}-0x{e:06X} {L:>8,}  {c}')


if __name__ == '__main__':
    main()
