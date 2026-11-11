#!/usr/bin/env python3
"""classify_regions.py — content tags for every incbin data region (playbook T-50).

Reads incbin pieces of disasm/src/rop.s, merges adjacent ones and writes
disasm/regions.csv: start,end,class,name,doc_ref,tier.
Classes from bytes alone: padding, ascii, pointer-table (big-endian longs inside ROM,
even), word-offset-table, zero-fill, high-entropy, unknown. Documented regions
(disasm/region-classes.txt) keep their class and doc_ref at tier 2.
Doc-proven regions (disasm/doc_regions.csv, Phase 1A T-10/T-12/T-13) take
priority: each incbin span is split at their boundaries, so a doc row becomes
its own regions.csv row with its class, name, doc_ref and tier. doc_regions.csv
ends are EXCLUSIVE ([start, end)), matching disasm/text/inventory.json (end of
one range = start of the next); regions.csv ends are INCLUSIVE.
Usage: python3 tools/classify_regions.py
"""
import csv
import math
import re
from collections import Counter
from pathlib import Path

ROM = Path('rop-original.gen').read_bytes()
INC = re.compile(r'incbin\s+"rop-original\.gen",\s*(\$[0-9A-Fa-f]+|\d+),\s*(\$[0-9A-Fa-f]+|\d+)')


def num(t):
    return int(t[1:], 16) if t.startswith('$') else int(t)


def entropy(b):
    n = len(b)
    return -sum((c / n) * math.log2(c / n) for c in Counter(b).values()) if n else 0


def classify(b):
    if not b:
        return 'empty'
    if set(b) <= {0x00}:
        return 'zero-fill'
    if set(b) <= {0xFF}:
        return 'padding-ff'
    text = sum(1 for c in b if 0x20 <= c <= 0x7E or c in (0x0A, 0x0D)) / len(b)
    if text > 0.9:
        return 'ascii'
    if len(b) >= 8 and len(b) % 4 == 0:
        longs = [int.from_bytes(b[i:i + 4], 'big') for i in range(0, len(b), 4)]
        if all(0 < v < len(ROM) and v % 2 == 0 for v in longs):
            return 'pointer-table'
    if len(b) >= 32 and len(b) % 2 == 0:
        words = [int.from_bytes(b[i:i + 2], 'big', signed=True) for i in range(0, len(b), 2)]
        even = sum(1 for w in words if w % 2 == 0) / len(words)
        if even >= 0.95:
            return 'word-offset-table'
    if entropy(b) > 7.0:
        return 'high-entropy'
    return 'unknown'


def load_doc_classes():
    out = []
    p = Path('disasm/region-classes.txt')
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.split('#')[0].strip()
            if line:
                s, e, cls = line.split(None, 2)
                out.append((int(s, 16), int(e, 16), cls))
    return out


def load_doc_regions():
    """disasm/doc_regions.csv: start,end,class,name,doc_ref,tier.
    Ends are EXCLUSIVE ([start, end)). Returns (start, end_excl, class, name,
    doc_ref, tier) sorted by start."""
    out = []
    p = Path('disasm/doc_regions.csv')
    if p.exists():
        with p.open(newline='') as fh:
            for r in csv.DictReader(fh):
                out.append((int(r['start'], 16), int(r['end'], 16),
                            r['class'], r['name'], r['doc_ref'], r['tier']))
    out.sort()
    return out


def main():
    spans = []
    for line in Path('disasm/src/rop.s').read_text(errors='replace').splitlines():
        m = INC.search(line)
        if m:
            spans.append((num(m.group(1)), num(m.group(2))))
            continue
        d = re.search(r'dcb\.b\s+(\$[0-9A-Fa-f]+|\d+),\s*\$FF\s*;\s*\$([0-9A-Fa-f]+)', line)
        if d:  # all-$FF padding (dcb.b)
            spans.append((num('$' + d.group(2)), num(d.group(1))))
            continue
        t = re.match(r'^\tdc\.w\s+(\S.*?)\s*;\s*table\s+\$([0-9A-Fa-f]+)\s*$', line)
        if t:  # structured table record (#14)
            spans.append((num('$' + t.group(2)), 2 * len(re.findall(r'\$[0-9A-Fa-f]+', t.group(1)))))
            continue
        z = re.search(r'incbin\s+"build/z80_snd_driver\.bin"\s*;\s*\$([0-9A-Fa-f]+)', line)
        if z:  # Z80 sound driver blob (#78): assembled code, length from the built file
            spans.append((num('$' + z.group(1)), Path('build/z80_snd_driver.bin').stat().st_size))
    spans.sort()
    merged = []
    for s, n in spans:
        if merged and merged[-1][0] + merged[-1][1] == s:
            merged[-1][1] += n
        else:
            merged.append([s, n])
    doc = load_doc_classes()
    regions = load_doc_regions()
    rows = []
    for s, n in merged:
        e = s + n - 1
        # Split the span at doc-region boundaries (doc ends are exclusive).
        cuts = {s, e + 1}
        for ds, de, *_ in regions:
            if ds < e + 1 and s < de:
                cuts.add(max(ds, s))
                cuts.add(min(de, e + 1))
        cuts = sorted(cuts)
        for a, b in zip(cuts, cuts[1:]):
            pe = b - 1
            hit = None
            for ds, de, cls, name, ref, tier in regions:
                if ds <= a and b <= de:
                    hit = (cls, name, ref, tier)
                    break
            if hit:
                cls, name, ref, tier = hit
                rows.append((a, pe, cls, name, ref, tier))
            else:
                doc_hits = [(cs, ce, c) for cs, ce, c in doc if cs <= a and pe <= ce]
                if doc_hits:
                    cls, tier, ref = doc_hits[0][2], '2', 'disasm/region-classes.txt'
                else:
                    cls, tier, ref = classify(ROM[a:pe + 1]), '1', ''
                rows.append((a, pe, cls, f'region_{a:06x}', ref, tier))
    rows.sort()
    with Path('disasm/regions.csv').open('w') as fh:
        fh.write('start,end,class,name,doc_ref,tier\n')
        for s, e, cls, name, ref, tier in rows:
            fh.write(f'0x{s:06X},0x{e:06X},{cls},{name},{ref},{tier}\n')
    unk = sum(e - s + 1 for s, e, c, *_ in rows if c in ('unknown', 'high-entropy'))
    print(f'regions: {len(rows)}; unknown/high-entropy bytes: {unk:,}')


if __name__ == '__main__':
    main()
