#!/usr/bin/env python3
"""roundtrip.py — one `make roundtrip` target for the 4 asset classes (issue #285, M10).

Runs the per-class extract -> re-pack -> byte-identical checks and
prints one PASS line per class:

  lzss    tools/lzss_roundtrip.py  — 404 $DD5C records decode +
          Okumura re-compress byte-identical, decode back
  text    tools/text_roundtrip.py  — 1184 dialogue records export +
          re-encode byte-identical (writes assets/text/dialogue.txt,
          which is git-ignored, never committed)
  assets  tools/asset_roundtrip.py — 400 records export to a scratch
          dir + rebuild from that export byte-identical; the scratch
          dir is deleted, so no extracted assets touch the repo
  song    tools/song_roundtrip.py  — 19 songs parse as documented and
          re-serialize byte-identical

Each class check is imported, not reimplemented here; a class that
fails prints FAIL with its reason and the run continues so all four
results are visible. Exit 0 only when all 4 pass.

tools/status.py runs this driver to emit the "Asset round-trip" row
in STATUS.md, so the row is measured, never typed by hand.

Usage: python3 tools/roundtrip.py
(Runs from the repo root; the ROM is always rop-original.gen there.
The per-class scripts accept --rom for standalone use.)"""
import os
import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

ROOT = _here.parent

import asset_roundtrip  # noqa: E402
import lzss_roundtrip  # noqa: E402
import song_roundtrip  # noqa: E402
import text_roundtrip  # noqa: E402

CLASSES = ("lzss", "text", "assets", "song")


def run_class(name):
    """Run one class check. Returns (ok, summary_or_error)."""
    try:
        if name == "lzss":
            return True, lzss_roundtrip.check()
        if name == "song":
            return True, song_roundtrip.check()
        if name == "assets":
            return True, asset_roundtrip.check()
        if name == "text":
            # text_roundtrip.main() prints its own detail line and
            # returns 0/1; it writes assets/text/dialogue.txt
            # (git-ignored). Re-derive the counts from its return.
            rc = text_roundtrip.main()
            if rc != 0:
                return False, "re-encode differs (see above)"
            return True, ("1184/1184 dialogue records re-encode "
                          "byte-identical")
    except Exception as e:  # noqa: BLE001 — report and continue
        return False, str(e)
    return False, f"unknown class {name}"


def main(argv=None):
    # The checks resolve the ROM and their outputs relative to the
    # repo root; run from there whatever the caller's cwd is.
    os.chdir(ROOT)
    passed = 0
    for name in CLASSES:
        ok, summary = run_class(name)
        if ok:
            passed += 1
            print(f"PASS {name}: {summary}")
        else:
            print(f"FAIL {name}: {summary}", file=sys.stderr)
    print(f"roundtrip: {passed}/{len(CLASSES)} classes pass")
    return 0 if passed == len(CLASSES) else 1


if __name__ == "__main__":
    sys.exit(main())
