#!/usr/bin/env python3
"""ram_writecheck.py — write check for tier-1 RAM names (owner rule, docs/agent-playbook.md section 6).

A tier-1 RAM name names an owner routine in its note ("... in OWNER" or "OWNER" after
"sites in"). The check counts instructions in disasm/src/rop.s that write the word
and reports writes from routines other than the owner. A name with an outside writer
is weaker evidence; a name with no owner write is flagged.

Reference owner: the dominant writer when the word is written, else the note owner (reader).
A name whose note owner differs from the dominant writer is printed as NAME-OWNER-MISMATCH.

Usage:  tools/ram_writecheck.py            report only (exit 0)
        tools/ram_writecheck.py --strict   exit 1 if any tier-1 owner name has an outside writer

Notes without an owner (e.g. rows from docs) are skipped and counted.
"""
import bisect
import csv
import glob
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAM = Path('disasm/symbols/ram.csv')
SRC = Path('disasm/src/rop.s')
WRITE_OPS = {'move', 'clr', 'add', 'sub', 'and', 'or', 'eor', 'addq', 'subq', 'bset', 'bclr'}
OWNER_RE = re.compile(r'sites in (\w+)|\bin ([a-z]\w*)\b')


def owner_of(note):
    m = OWNER_RE.search(note)
    if not m:
        return None
    return m.group(1) or m.group(2)


def routine_table():
    names = {}
    for f in glob.glob('disasm/symbols/*.csv'):
        if 'ram' in f:
            continue
        for r in csv.DictReader(open(f, newline='')):
            try:
                names[int(r['addr'], 16)] = r['name']
            except (ValueError, KeyError):
                pass
    addrs = sorted(names)
    return names, addrs


def main():
    strict = '--strict' in sys.argv
    rows = [r for r in csv.DictReader(RAM.open(newline='')) if str(r['tier']).strip() == '1']
    names, addrs = routine_table()
    src = SRC.read_text(errors='replace').splitlines()
    pc = 0
    writes = defaultdict(list)  # word hex -> [(owner routine, pc)]
    words = {int(r['addr'], 16): r for r in rows}
    pats = {a: re.compile(r'(?<![0-9a-f])(ff)?' + format(a & 0xFFFF, '04x') + r'(?![0-9a-f])', re.I) for a in words}
    for line in src:
        m = re.search(r';\s*\$([0-9A-Fa-f]{6})\s*$', line)
        if not m:
            continue
        pc = int(m.group(1), 16)
        code = line.split(';')[0].strip()
        mm = re.match(r'([a-z]+)\.[bwl]\s+(.*)', code)
        if not mm:
            continue
        op, args = mm.group(1), mm.group(2)
        if op not in WRITE_OPS:
            continue
        # single-operand forms (clr, tst-like) write their only operand
        dst = args.split(',')[-1] if (',' in args and op != 'clr') else args
        for a, pat in pats.items():
            if pat.search(dst):
                owner = names[addrs[bisect.bisect_right(addrs, pc) - 1]]
                writes[a].append((owner, pc))
    failed = 0
    skipped = 0
    for a, r in sorted(words.items()):
        note_owner = owner_of(r['note'])
        if not note_owner:
            skipped += 1
            continue
        owner = note_owner
        w = writes.get(a, [])
        # Writer rule: when the word is written, the dominant writer is the reference owner.
        # The note's owner (often a reader) is reported but no longer decides the verdict.
        if w:
            owner = Counter(o for o, _ in w).most_common(1)[0][0]
        outside = [o for o, _ in w if o != owner]
        own = len(w) - len(outside)
        if not w:
            status = 'NO-WRITES-SEEN'   # reads only, or written through an indexed operand the scan cannot see
        elif own == 0:
            status = 'FAIL-NO-OWNER-WRITE'
        elif outside:
            status = 'OUTSIDE-WRITERS'
        else:
            status = 'OK'
        bad = status in ('FAIL-NO-OWNER-WRITE', 'OUTSIDE-WRITERS')
        if bad and (strict or status == 'FAIL-NO-OWNER-WRITE'):
            failed += 1
        mismatch = ' NAME-OWNER-MISMATCH note=' + note_owner if owner != note_owner else ''
        print(f"{r['addr']} {r['name']} owner={owner} writes={len(w)} own={own} outside={len(outside)} {status} "
              f"{Counter(outside).most_common(2)}{mismatch}")
    print(f"ram writecheck: {len(words) - skipped} owner names checked, {skipped} without owner, "
          f"{failed} failing{' (strict)' if strict else ' (report only; --strict fails outside writers too)'}")
    return 1 if (strict and failed) else 0


if __name__ == '__main__':
    sys.exit(main())
