#!/usr/bin/env python3
"""status.py — generated status (never typed by hand). Playbook §3 metrics.

Writes STATUS.md and replaces the README block between
<!-- status:start --> and <!-- status:end -->.
Sources: disasm/symbols/*.csv, disasm/ghidra/functions.txt, disasm/src/rop.s,
         disasm/regions.csv (M8 bytes-accounted; high-entropy on its own line),
         rop-original.gen (size, if present).
Usage: python3 tools/status.py
"""
import csv
import re
import subprocess
import sys
from pathlib import Path

ROM_SIZE = 1048576
INC = re.compile(r'incbin\s+"rop-original\.gen",\s*(\$[0-9A-Fa-f]+|\d+),\s*(\$[0-9A-Fa-f]+|\d+)')
DCB = re.compile(r'dcb\.b\s+(\$[0-9A-Fa-f]+|\d+),\s*\$FF\s*;')  # all-$FF padding (#13)
TBL = re.compile(r'^\tdc\.([wb])\s+(\S.*?)\s*;\s*table\s+\$([0-9A-Fa-f]+)\s*$')
HDR = re.compile(r'^\tdc\.w HEADER_SUM\b')  # header checksum word, data (#16)
VEC = re.compile(r'^\tdc\.l \S+\t; \$[0-9A-F]+ vector$')  # vector-table code pointer, 4 bytes (#16 item 1)
RAW = re.compile(r'^\s*\.?(dc|fill|ds)\.[bwl]\b|^\s*\.fill\b')
START, END = '<!-- status:start -->', '<!-- status:end -->'


def num(t):
    return int(t[1:], 16) if t.startswith('$') else int(t)


def measure():
    names = []
    for path in sorted([*Path('disasm/symbols').glob('code_*.csv'), Path('disasm/symbols/extra.csv'), Path('disasm/symbols/auto.csv')]):
        with path.open(newline='') as fh:
            names += [(r['addr'], r['name'], r.get('tier', '1')) for r in csv.DictReader(fh)]
    if len({a for a, _, _ in names}) != len(names) or len({n for _, n, _ in names}) != len(names):
        sys.exit('status: symbol files have a duplicate address or name')
    # Count only rows that are Ghidra functions, so named can never exceed funcs (#status-denominator).
    func_addrs = set()
    f = Path('disasm/ghidra/functions.txt')
    if f.exists():
        for l in f.read_text().splitlines():
            parts = l.split()
            if len(parts) >= 2 and parts[0] == 'FUNC':
                func_addrs.add(int(parts[1], 16))
    funcs = len(func_addrs)
    names = [(a, n, t) for a, n, t in names if int(a, 16) in func_addrs]
    tier1 = sum(1 for _, _, t in names if str(t).strip() in ('1', '2'))
    tier0 = sum(1 for _, _, t in names if str(t).strip() == '0')
    incbin = raw = 0
    incbin_slices = []  # (start, len) of raw incbin slices, for the ptr-table line (#281)
    for l in Path('disasm/src/rop.s').read_text(errors='replace').splitlines():
        m = INC.search(l)
        d = DCB.search(l)
        t = TBL.match(l)
        if m:
            incbin += num(m.group(2))
            incbin_slices.append((num(m.group(1)), num(m.group(2))))
        elif d:
            incbin += num(d.group(1))
        elif HDR.match(l):
            incbin += 2
        elif VEC.match(l):
            incbin += 4
        elif t:  # structured table record (#14)
            incbin += (2 if t.group(1) == 'w' else 1) * len(re.findall(r'\$[0-9A-Fa-f]+', t.group(2)))
        elif RAW.match(l):
            raw += 1
    size = ROM_SIZE
    code = size - incbin
    # M8 region join: regions.csv must cover exactly the incbin bytes.
    regions = None
    ptr_incbin = 0  # pointer-bearing bytes still emitted as raw incbin (#281)
    rp = Path('disasm/regions.csv')
    if rp.exists():
        unknown = high_entropy = total = z80 = 0
        ptr_rows = []
        with rp.open(newline='') as fh:
            for r in csv.DictReader(fh):
                n = int(r['end'], 16) - int(r['start'], 16) + 1
                if r['class'] == 'ptr-table':
                    ptr_rows.append((int(r['start'], 16), int(r['end'], 16)))
                if r['class'] == 'z80-driver-blob':  # assembled code, counted in code (#78)
                    z80 += n
                    continue
                total += n
                if r['class'] == 'unknown':
                    unknown += n
                elif r['class'] == 'high-entropy':
                    high_entropy += n
        if total != incbin:
            sys.exit(f'status: regions.csv covers {total} bytes, incbin is {incbin}')
        for ps, pe in ptr_rows:
            for s, n in incbin_slices:
                lo, hi = max(ps, s), min(pe, s + n - 1)
                if lo <= hi:
                    ptr_incbin += hi - lo + 1
        regions = {
            'accounted': code + (total - unknown),
            'unknown': unknown, 'high_entropy': high_entropy,
        }
    return {
        'named': tier1, 'tier0': tier0, 'funcs': funcs,
        'code': code, 'incbin': incbin, 'raw': raw, 'size': size,
        'regions': regions, 'ptr_incbin': ptr_incbin,
        'roundtrip': roundtrip_count(),
    }


def roundtrip_count():
    """Asset round-trip (M10): run tools/roundtrip.py and count its
    PASS lines (one per class: lzss, text, assets, song).

    Measured live, never typed by hand — a fail, unknown or skipped
    class never aggregates to a pass. Returns (pass count 0-4,
    driver output) or (None, '') when rop-original.gen is absent
    (the check cannot run without the ROM; the row then reads
    "no ROM").
    """
    if not Path('rop-original.gen').exists():
        return None, ''
    try:
        proc = subprocess.run(
            [sys.executable, 'tools/roundtrip.py'],
            capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 0, f'roundtrip driver did not run: {e}'
    out = proc.stdout + proc.stderr
    n = sum(1 for line in proc.stdout.splitlines()
            if line.startswith('PASS '))
    return n, out


def tables(m):
    pct = lambda a, b: f'{100.0 * a / b:.2f}%'
    rows = [
        '| Metric | Now | Target | Share |',
        '|---|---:|---:|---:|',
        f"| Routines named (tier ≥ 1) | {m['named']} of {m['funcs']} | {m['funcs']} | {100 * m['named'] // max(m['funcs'], 1)}% |",
        f"| Routines at tier 0 (structural only) | {m['tier0']} | — | — |",
        f"| Bytes in code | {m['code']:,} | {m['size']:,} | {pct(m['code'], m['size'])} |",
        f"| Bytes in incbin data | {m['incbin']:,} | 0 | {pct(m['incbin'], m['size'])} |",
        f"| Raw fallbacks in code | {m['raw']} | 0 | — |",
    ]
    if m['regions'] is not None:
        r = m['regions']
        rows += [
            f"| Bytes accounted (M8) | {r['accounted']:,} | {m['size']:,} | {pct(r['accounted'], m['size'])} |",
            f"| Bytes unknown | {r['unknown']:,} | 0 | {pct(r['unknown'], m['size'])} |",
            f"| Bytes high-entropy (opaque, counted in M8) | {r['high_entropy']:,} | 0 | {pct(r['high_entropy'], m['size'])} |",
            f"| Pointer-bearing bytes still incbin | {m['ptr_incbin']:,} | 0 | {pct(m['ptr_incbin'], m['size'])} |",
        ]
    # Asset round-trip (M10, issue #285): classes passing of 4.
    n, _out = m['roundtrip']
    if n is None:
        rows.append('| Asset round-trip | no ROM | 4 of 4 | — |')
    else:
        rows.append(f"| Asset round-trip | {n} of 4 | 4 of 4 | {100 * n // 4}% |")
    return rows


def main():
    m = measure()
    body = '\n'.join(tables(m))
    Path('STATUS.md').write_text(
        '# Status (generated by tools/status.py — do not edit)\n\n'
        'Measured from the repo. Issue counts are on GitHub, not here.\n\n' + body + '\n')
    readme = Path('README.md')
    text = readme.read_text()
    if START not in text or END not in text:
        sys.exit('status: README is missing the status markers')
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    readme.write_text(head + START + '\n' + body + '\n' + END + tail)
    extra = ''
    if m['regions'] is not None:
        r = m['regions']
        extra = (f"; M8 accounted {r['accounted']:,} "
                 f"({100.0 * r['accounted'] / m['size']:.2f}%), "
                 f"unknown {r['unknown']:,}, high-entropy {r['high_entropy']:,}")
    rt, rt_out = m['roundtrip']
    rt_extra = ('; round-trip no ROM' if rt is None
                else f'; round-trip {rt}/4')
    print(f"status: {m['named']} of {m['funcs']} named (tier>=1), {m['tier0']} tier 0; code {m['code']:,}; incbin {m['incbin']:,}; raw {m['raw']}; ptr-incbin {m['ptr_incbin']:,}{extra}{rt_extra}")
    if rt is not None and rt != 4:
        # STATUS.md / README already carry the failing count above;
        # surface the driver's output, then fail the gate.
        print(rt_out, file=sys.stderr)
        sys.exit(f'status: asset round-trip {rt}/4 (see above)')


if __name__ == '__main__':
    main()
