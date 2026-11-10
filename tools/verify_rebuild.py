#!/usr/bin/env python3
"""verify_rebuild.py REBUILT ORIGINAL — byte-compare the rebuild (issue #013).

Exits non-zero on any mismatch, printing the first differing address.
The two Genesis checksum fields (header 0x18E, runtime 0xFD098) are reported
separately: they are the only bytes allowed to differ before `checksum.py fix-all`.
"""
import sys

CHECKSUM_FIELDS = {0x18E, 0x18F, 0xFD098, 0xFD099}


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    rebuilt = open(sys.argv[1], "rb").read()
    orig = open(sys.argv[2], "rb").read()
    if len(rebuilt) != len(orig):
        print(f"FAIL size: rebuilt={len(rebuilt)} original={len(orig)}")
        return 1
    diffs = [i for i in range(len(orig)) if rebuilt[i] != orig[i]]
    if not diffs:
        print(f"PASS byte-identical ({len(orig)} bytes)")
        return 0
    non_checksum = [i for i in diffs if i not in CHECKSUM_FIELDS]
    if not non_checksum:
        print(f"PASS except checksum fields {sorted(hex(i) for i in diffs)}")
        return 0
    first = non_checksum[0]
    print(f"FAIL first difference at 0x{first:06X}: rebuilt=0x{rebuilt[first]:02X} original=0x{orig[first]:02X} ({len(non_checksum)} bytes differ)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
