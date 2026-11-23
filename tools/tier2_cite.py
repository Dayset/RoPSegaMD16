#!/usr/bin/env python3
"""tier2_cite.py — doc-citation proposals for tier-2 promotion (issue #282).

For each tier-1 routine, list doc lines in docs/ that cite an address
inside the routine's [start, end) range (from disasm/ghidra/functions.txt).
A citation of the routine's own start address is strongest; a citation of
an address inside the body also counts (the doc pins code inside the
routine). Output is a JSON proposal file; nothing is modified.

Address forms recognised: $XXXXXX / $XXXX (4-6 hex digits) and 0xXXXXXX /
0xXXXX. Citations >= 0xFF0000 (RAM) and 0xA00000-0xEFFFFF (hardware) are
ignored — only ROM code addresses count. Short ($XXXX) citations are kept
but flagged `short: true`, because a 4-digit value can also be a VRAM /
tile / data address in prose; the reviewer must check the line text
before promoting on a short citation alone.

Usage:
  python3 tools/tier2_cite.py [--out build/tier2_cite.json]
"""
import argparse
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
FUNCS = ROOT / "disasm" / "ghidra" / "functions.txt"
SYM_GLOBS = ["code_*.csv", "extra.csv", "auto.csv"]

# $XXXXXX / $XXXX (4-6 hex) and 0xXXXXXX / 0xXXXX; avoid matching the
# $ in "$FF..." RAM refs by range-filtering later, and avoid matching
# hex inside longer words.
DOLLAR = re.compile(r"\$([0-9A-Fa-f]{4,6})\b")
HEX0X = re.compile(r"0x([0-9A-Fa-f]{4,6})\b")


def load_funcs():
    """addr -> (end_exclusive, ghidra_name)."""
    funcs = {}
    for line in (FUNCS).read_text().splitlines():
        p = line.split()
        if len(p) >= 2 and p[0] == "FUNC":
            funcs[int(p[1], 16)] = (int(p[2], 16) + 1, p[3] if len(p) > 3 else "")
    return funcs


def load_symbols():
    rows = []
    for pat in SYM_GLOBS:
        for path in sorted((ROOT / "disasm" / "symbols").glob(pat)):
            with path.open(newline="") as fh:
                for r in csv.DictReader(fh):
                    rows.append({**r, "file": path.name})
    return rows


def scan_docs():
    """Return list of (addr, doc_relpath, lineno, line_text)."""
    hits = []
    for path in sorted(DOCS.rglob("*.md")):
        rel = str(path.relative_to(ROOT))
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for n, line in enumerate(lines, 1):
            for m in DOLLAR.finditer(line):
                hits.append((int(m.group(1), 16), rel, n, line.strip(), True))
            for m in HEX0X.finditer(line):
                hits.append((int(m.group(1), 16), rel, n, line.strip(), False))
    return hits


def usable(addr, doc, text):
    """False for citations that cannot be 68K ROM code references.

    - docs/sound.md $XXXX (4-digit) cites are Z80-driver addresses, which
      collide numerically with 68K ROM $000000-$00FFFF; only 5-6 digit
      cites there are 68K code.
    - A cite that only appears as an endpoint of a `$A-$B` range in the
      line is a region boundary, not a routine reference.
    """
    if doc == "docs/sound.md" and addr < 0x10000:
        return False
    if re.search(r"\$[0-9A-Fa-f]{4,6}\s*[-\u2013\u2014]\s*\$[0-9A-Fa-f]{4,6}", text):
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="build/tier2_cite.json")
    args = ap.parse_args()
    funcs = load_funcs()
    syms = load_symbols()
    # Routine ranges sorted by start; a citation belongs to the routine
    # whose [start, end) contains it.
    starts = sorted(funcs)
    # Precompute doc hits in ROM code range only.
    code_hits = []
    for addr, doc, n, text, dollar in scan_docs():
        if addr >= 0xA00000:  # RAM / hardware / Z80 window
            continue
        code_hits.append((addr, doc, n, text, dollar))
    code_hits.sort()

    def routine_for(addr):
        import bisect
        i = bisect.bisect_right(starts, addr) - 1
        if i < 0:
            return None
        s = starts[i]
        if addr < funcs[s][0]:
            return s
        return None

    # Group citations by routine (usable ones only).
    by_routine = {}
    for addr, doc, n, text, dollar in code_hits:
        if not usable(addr, doc, text):
            continue
        s = routine_for(addr)
        if s is None:
            continue
        by_routine.setdefault(s, []).append(
            {"addr": f"0x{addr:06X}", "doc": doc, "line": n,
             "text": text[:220], "short": len(f"{addr:X}") <= 4,
             "at_start": addr == s})

    proposals = []
    for r in syms:
        if r["tier"] != "1":
            continue
        a = int(r["addr"], 16)
        if a not in funcs:
            continue
        cits = by_routine.get(a, [])
        # Prefer start-address citations, then doc order; dedupe by doc+line.
        seen, uniq = set(), []
        for c in sorted(cits, key=lambda c: (not c["at_start"], c["doc"], c["line"])):
            k = (c["doc"], c["line"])
            if k not in seen:
                seen.add(k)
                uniq.append(c)
        proposals.append({
            "addr": r["addr"], "name": r["name"], "file": r["file"],
            "note": r["note"], "citations": uniq[:5],
            "n_citations": len(uniq),
            "has_start_cite": any(c["at_start"] for c in uniq),
            # strong: the doc cites the routine's own start address (not a
            # Z80-side or range-boundary cite — those are filtered above).
            # in-body-only citations need a human read of the line text.
            "strong": any(c["at_start"] for c in uniq),
        })
    with_cite = [p for p in proposals if p["n_citations"] > 0]
    with_start = [p for p in proposals if p["has_start_cite"]]
    strong = [p for p in proposals if p["strong"]]
    inbody_only = [p for p in with_cite if not p["has_start_cite"]]
    out = {
        "tier1_total": len(proposals),
        "with_citation": len(with_cite),
        "with_start_citation": len(with_start),
        "strong": len(strong),
        "inbody_only": len(inbody_only),
        "proposals": proposals,
    }
    op = ROOT / args.out
    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_text(json.dumps(out, indent=1))
    print(f"tier-1 routines: {len(proposals)}")
    print(f"with >=1 usable doc citation in range: {len(with_cite)}")
    print(f"with start-address citation (strong): {len(with_start)}")
    print(f"in-body-only citations (needs human read): {len(inbody_only)}")
    print(f"wrote {op}")


if __name__ == "__main__":
    main()
