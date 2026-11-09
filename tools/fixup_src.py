#!/usr/bin/env python3
"""fixup_src.py — converge disasm/src/ to a byte-identical rebuild (#012/#013).

Reads disasm/src/manifest.json (ROM offset -> [file, line, text, bytes])
written by split_disasm.py --emit. Two modes:

  --errors-from LOGFILE : parse GNU-as errors (file:line: Error:) from a
      build log and replace those source lines with .dc.b of the
      original ROM bytes.
  --diff BUILT ORIGINAL : compare a built ROM against the original and
      replace the source line of every instruction whose bytes differ
      with .dc.b of the original bytes.

Replacements preserve byte length exactly, so no address ever shifts.
Run build.sh + this tool alternately until verify_rebuild.py passes.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "disasm" / "src"


def load_manifest():
    return json.loads((SRC / "manifest.json").read_text())


def replace_lines(edits):
    """edits: dict fname -> dict lineno -> newtext"""
    n = 0
    for fname, lines_edits in edits.items():
        p = SRC / fname
        lines = p.read_text().splitlines()
        for lineno, newtext in lines_edits.items():
            old = lines[lineno - 1]
            if old.strip().startswith(".dc.b"):
                continue
            lines[lineno - 1] = newtext + "  /* was: %s */" % old.strip()
            n += 1
        p.write_text("\n".join(lines) + "\n")
    return n


def dc_line(hexbytes, orig_text):
    bs = bytes.fromhex(hexbytes)
    return "    .dc.b " + ",".join("0x%02X" % b for b in bs)


def main():
    man = load_manifest()
    by_line = {}
    for off, (fname, lineno, text, hexb) in man.items():
        by_line[(fname, lineno)] = (int(off), hexb)
    edits = {}
    if sys.argv[1] == "--errors-from":
        log = Path(sys.argv[2]).read_text(errors="replace")
        seen = set()
        for m in re.finditer(r"^(r_[0-9A-F]+\.s):(\d+): Error:", log, re.M):
            key = (m.group(1), int(m.group(2)))
            if key in seen or key not in by_line:
                continue
            seen.add(key)
            off, hexb = by_line[key]
            edits.setdefault(key[0], {})[key[1]] = dc_line(hexb, "")
        print(f"fixup: {replace_lines(edits)} error lines -> .dc.b")
    elif sys.argv[1] == "--diff":
        built = Path(sys.argv[2]).read_bytes()
        orig = Path(sys.argv[3]).read_bytes()
        assert len(built) == len(orig), (len(built), len(orig))
        offs = sorted(int(o) for o in man)
        import bisect
        diff_bytes = [i for i in range(len(orig)) if built[i] != orig[i]]
        hit = set()
        for i in diff_bytes:
            j = bisect.bisect_right(offs, i) - 1
            if j >= 0:
                start = offs[j]
                fname, lineno, text, hexb = man[str(start)]
                if start <= i < start + len(bytes.fromhex(hexb)):
                    hit.add((fname, lineno, hexb))
        for fname, lineno, hexb in hit:
            edits.setdefault(fname, {})[lineno] = dc_line(hexb, "")
        n = replace_lines(edits)
        print(f"fixup: {len(diff_bytes)} diff bytes in {len(hit)} instructions, {n} lines -> .dc.b")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
